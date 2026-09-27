import copy
import csv
import json
import unittest

from scripts.phase2_refresh_rt031_s8_service_date_v3 import active_services,extract,signature,OUTPUT as RAIL,ROOT
from scripts.phase2_close_rt031_line8_fixed_geometry_timetable_v3 import OUTPUT,CONFIRMATION,BASE,digest
from scripts.phase2_export_rt031_line8_working_timetable_v3 import build,report,DOC,CONNECTIONS
from scripts.phase2_compare_rt031_line8_deep_offpeak_v3 import build_problem
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import FLAGS,verify


class WorkingTimetableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=json.loads(OUTPUT.read_text(encoding='utf-8'))
        cls.rail=json.loads(RAIL.read_text(encoding='utf-8'))
        cls.p=build_problem((600,960),120)

    def test_geometry_authority_is_not_operating_or_budget_approval(self):
        c=json.loads(CONFIRMATION.read_text(encoding='utf-8'))
        self.assertTrue(c['geometry_confirmed_by_caller'])
        self.assertEqual(digest(ROOT/c['geometry_source']),c['geometry_source_sha256_normalized_newlines'])
        self.assertEqual(self.r['source_sha256_normalized_newlines'],{
            'reference':digest(BASE/'deep_offpeak_witness.json'),'rail':digest(RAIL),'confirmation':digest(CONFIRMATION)})
        self.assertEqual(set(self.r['patterns_used']),set(c['patterns']))
        for obj in (c,self.r):
            for k in FLAGS:self.assertFalse(obj[k])
            for k in ('decision_budget_km','uncertainty_band_min','approved_uplift_percent'):self.assertIsNone(obj[k])
            self.assertFalse(obj['timetable_accepted_by_caller']);self.assertFalse(obj['midday_window_adopted'])

    def test_calendar_dates_apply_additions_removals_and_fail_duplicates(self):
        cal=[{'service_id':'a','start_date':'20260901','end_date':'20260930','monday':'1'}]
        exceptions=[{'service_id':'a','date':'20260928','exception_type':'2'},
                    {'service_id':'b','date':'20260928','exception_type':'1'}]
        self.assertEqual(active_services(cal,exceptions,'2026-09-28'),{'b'})
        self.assertEqual(active_services([],exceptions,'2026-09-28'),{'b'})
        with self.assertRaises(ValueError):active_services(cal,exceptions+exceptions[:1],'2026-09-28')

    def test_direction_from_downstream_not_train_id(self):
        tables={'routes.txt':[{'route_id':'S8','route_short_name':'S8'}],
                'trips.txt':[{'trip_id':'even_fake_number','route_id':'S8','service_id':'a'}],
                'calendar_dates.txt':[{'service_id':'a','date':'20260928','exception_type':'1'}],
                'stop_times.txt':[{'trip_id':'even_fake_number','stop_id':sid,'stop_sequence':str(i),
                                   'arrival_time':clock,'departure_time':clock} for i,(sid,clock) in enumerate([('S01514','07:26:00'),('S01645','08:00:00')])]}
        self.assertEqual(extract(tables,'2026-09-28')[0]['direction'],'MILANO')
        with self.assertRaises(ValueError):extract(tables,'2026-09-29')
        tables['stop_times.txt'].append({'trip_id':'even_fake_number','stop_id':'S01520','stop_sequence':'2','arrival_time':'09:00:00','departure_time':'09:00:00'})
        with self.assertRaises(ValueError):extract(tables,'2026-09-28')

    def test_current_dates_new_trip_ids_and_unchanged_station_clocks(self):
        with (ROOT/'outputs/phase2/s8_events.csv').open(encoding='utf-8') as stream:old=list(csv.DictReader(stream))
        self.assertEqual(len(self.rail['events']),74)
        self.assertTrue(self.rail['same_station_clock_signature_as_20260903'])
        self.assertFalse(self.rail['reuses_legacy_trip_ids'])
        self.assertFalse({e['trip_id'] for e in old}&{e['trip_id'] for e in self.rail['events']})
        self.assertEqual(signature(self.rail['events']),sorted((e['direction'],float(e['arrival_min']),float(e['departure_min'])) for e in old))
        self.assertTrue(all(c['same_station_clock_signature_as_reference_day'] and c['event_count']==74 for c in self.rail['weekday_checks']))
        self.assertFalse(self.rail['annual_calendar_certified'])

    def test_full_service_recheck_exact_counts_peaks_and_cost(self):
        self.assertEqual(verify(self.p,self.r['trips'],self.r['comparison_peak_windows'],4),self.r['conditional_scenarios'])
        self.assertEqual(self.r['patterns_used'],{'west_B':17,'east_A':17})
        self.assertEqual(self.r['comparison_peak_windows'],[{'peak':'AM','start_min':420,'end_min':540},{'peak':'PM','start_min':1015,'end_min':1135}])
        self.assertAlmostEqual(sum(t['service_km'] for t in self.r['trip_ledger'])*260,self.r['annual_service_km'])
        self.assertAlmostEqual(self.r['annual_service_km'],122339.720989,places=5)
        self.assertEqual(self.r['worst_grid_vehicle_count_conditional'],6)

    def test_only_declared_clockface_exceptions(self):
        exceptions=[]
        for t in self.r['trips']:
            if t['departure_min']==1180:continue
            band='before_10' if t['departure_min']<600 else 'from_10'
            phase=next(x for x in self.r['clockface_phases'] if x['wing']==t['loop'].split('_')[0] and x['band']==band)
            if t['departure_min']%30!=phase['modulo_30']:exceptions.append(t)
        self.assertEqual(exceptions,[{'loop':'west_B','departure_min':600}])
        self.assertEqual(exceptions,self.r['clockface_exceptions'])
        self.assertTrue(self.r['minimum_exception_count_in_declared_domain'])
        strict=json.loads((BASE/'best_practices_readiness.json').read_text(encoding='utf-8'))['banded_same_peak_windows_comparison']
        self.assertTrue(strict['optimality_proven_in_this_domain'])
        self.assertGreater(strict['annual_service_km_lower_bound_in_domain'],self.r['annual_service_km'])

    def test_every_target_binds_a_current_directional_train(self):
        events={e['trip_id']:e for e in self.rail['events']}
        bindings=self.r['dated_rail_target_bindings']
        self.assertEqual(len(bindings),297)
        for b in bindings:
            e=events[b['rail_trip_id']]
            if b['kind']=='bus_to_rail':self.assertEqual((e['direction'],e['departure_min']),('MILANO',b['rail_min']))
            else:self.assertEqual((e['direction'],e['arrival_min']),('LECCO',b['rail_min']))

    def test_rail_ledger_and_report_reproduce(self):
        r,c=build()
        self.assertEqual(c,json.loads(CONNECTIONS.read_text(encoding='utf-8')))
        self.assertEqual(report(r,c['connections']),DOC.read_text(encoding='utf-8'))
        self.assertEqual(len(c['connections']),68)
        for row in c['connections']:
            self.assertGreaterEqual(row['train_to_bus_wait_including_transfer_min'],3)
            self.assertGreaterEqual(row['bus_to_train_wait_grid_including_transfer_min_range'][0],3-1e-8)
            self.assertFalse(row['passenger_connection_certified'])


if __name__=='__main__':unittest.main()
