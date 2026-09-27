import copy
import json
import unittest

from scripts.phase2_close_rt031_line8_31_trips_v3 import (
    AUTH,OUTPUT,FLAGS,PATTERNS,PEAKS,sources,verify_schedule,attempt,maximum_wait)
from scripts.phase2_export_rt031_line8_31_trips_v3 import build,report,CONNECTIONS,DOC


class ThirtyOneTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=sources();cls.r=json.loads(OUTPUT.read_text(encoding='utf-8'))

    def test_authority_is_specific_not_general_budget_or_operating_approval(self):
        a=json.loads(AUTH.read_text(encoding='utf-8'))
        self.assertEqual(a['daily_trip_count_approved'],31)
        self.assertEqual(a['pattern_counts'],{'west_B':15,'east_A':16})
        self.assertTrue(self.r['specific_service_km_scenario_accepted_by_caller'])
        for obj in (a,self.r):
            for k in FLAGS:self.assertIs(obj[k],False)
            for k in ('decision_budget_km','uncertainty_band_min','total_operating_km'):self.assertIsNone(obj[k])
            self.assertFalse(obj['precise_offpeak_timetable_accepted_by_caller'])
            self.assertFalse(obj['funding_secured'])
        self.assertFalse(a['annual_calendar_adopted'])

    def test_full_independent_recheck_and_arithmetic(self):
        result=verify_schedule(self.p,self.r['trips'],self.r['wait_limit_min_by_pattern'],True)
        for k,v in result.items():self.assertEqual(self.r[k],v)
        self.assertEqual(self.r['daily_trip_count'],31)
        self.assertAlmostEqual(self.r['annual_service_km'],111460.88278433659)
        self.assertAlmostEqual(self.r['service_km_excess_vs_reference'],41.88278433659)
        for pattern,limit in {'west_B':155,'east_A':120}.items():
            self.assertAlmostEqual(self.r['maximum_ready_wait_min_by_pattern'][pattern],limit)
        self.assertEqual(self.r['comparison_peak_windows'],PEAKS)
        self.assertEqual(len(self.r['conditional_scenarios']),27)
        self.assertEqual(max(s['minimum_vehicle_count_conditional'] for s in self.r['conditional_scenarios']),6)

    def test_unrestricted_and_readable_minima_remain_separate(self):
        unrestricted,regular=self.r['finite_domain_comparisons']
        self.assertEqual(unrestricted['independent_wing_minima_min'],{'west_B':155,'east_A':115})
        self.assertEqual(regular['independent_wing_minima_min'],{'west_B':155,'east_A':120})
        for case in (unrestricted,regular):
            self.assertTrue(case['joint_minima_attainable'])
            joint=case['joint_witness']
            verify_schedule(self.p,joint['trips'],joint['limits_min'],case['clockface_restricted'])
            for pattern in PATTERNS:
                prior=case['independent_wing_minima_min'][pattern]-5
                self.assertTrue(any(c['infeasible_in_finite_domain'] and c['limits_min'][pattern]==prior for c in case['checks']))

    def test_reproduce_adjacent_lower_bound_certificates(self):
        for regular,pattern,limit in ((False,'west_B',150),(False,'east_A',110),(True,'east_A',115)):
            case=attempt(self.p,{p:limit if p==pattern else 180 for p in PATTERNS},regular)
            self.assertTrue(case['infeasible_in_finite_domain'])
            self.assertFalse(case['witness_found'])

    def test_all_297_targets_bind_active_directional_trains_and_selected_buses(self):
        events={e['trip_id']:e for e in self.p['rail']['events']}
        selected={(t['loop'],t['departure_min']) for t in self.r['trips']}
        self.assertEqual(len(self.r['dated_rail_target_bindings']),297)
        for b in self.r['dated_rail_target_bindings']:
            e=events[b['rail_trip_id']]
            direction,clock=('MILANO','departure_min') if b['kind']=='bus_to_rail' else ('LECCO','arrival_min')
            self.assertEqual((e['direction'],e[clock]),(direction,b['rail_min']))
            self.assertTrue(b['eligible_bus_trips'])
            self.assertTrue(all((t['loop'],t['departure_min']) in selected for t in b['eligible_bus_trips']))

    def test_cannot_relabel_old_h60_h120_policy_as_preserved(self):
        self.assertTrue(self.r['old_34_trip_offpeak_policy_violations'])
        with self.assertRaisesRegex(ValueError,'offpeak wait violation'):
            verify_schedule(self.p,self.r['trips'],{'west_B':120,'east_A':120},True)

    def test_counterexamples_trip_loss_duplicates_later_start_and_peak_gap(self):
        trips=self.r['trips']
        with self.assertRaises(ValueError):verify_schedule(self.p,trips[:-1],self.r['wait_limit_min_by_pattern'])
        with self.assertRaises(ValueError):verify_schedule(self.p,trips[:-1]+[trips[0]],self.r['wait_limit_min_by_pattern'])
        moved=copy.deepcopy(trips)
        next(t for t in moved if t['loop']=='west_B' and t['departure_min']==390)['departure_min']=400
        with self.assertRaises(ValueError):verify_schedule(self.p,moved,self.r['wait_limit_min_by_pattern'])
        moved=copy.deepcopy(trips)
        next(t for t in moved if t['loop']=='west_B' and t['departure_min']==450)['departure_min']=605
        with self.assertRaises(ValueError):verify_schedule(self.p,moved,self.r['wait_limit_min_by_pattern'])

    def test_continuous_wait_counts_boundaries_and_missing_last_trip(self):
        self.assertEqual(maximum_wait([390,420,540,695,845,995,1180],390,1180),185)
        self.assertEqual(maximum_wait([380,400,430],390,430),30)
        with self.assertRaises(ValueError):maximum_wait([390,420],390,430)

    def test_report_and_all_62_connections_reproduce(self):
        r,c=build()
        self.assertEqual(c,json.loads(CONNECTIONS.read_text(encoding='utf-8')))
        self.assertEqual(report(r,c['connections']),DOC.read_text(encoding='utf-8'))
        self.assertEqual(len(c['connections']),62)
        for row in c['connections']:
            self.assertGreaterEqual(row['train_to_bus_wait_including_transfer_min'],3)
            self.assertGreaterEqual(row['bus_to_train_wait_grid_including_transfer_min_range'][0],3-1e-8)
            self.assertFalse(row['passenger_connection_certified'])


if __name__=='__main__':unittest.main()
