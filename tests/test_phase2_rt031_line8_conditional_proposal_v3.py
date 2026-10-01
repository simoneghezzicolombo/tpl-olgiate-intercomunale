import gzip
import hashlib
import json
import unittest
from pathlib import Path

from scripts.phase2_package_rt031_line8_conditional_proposal_v3 import (
    OUT,SHAPE,DOC,ROOT,FS,OMITTED,build)


class ConditionalProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=json.loads(OUT.read_text(encoding='utf-8'))
        cls.shape=json.loads(SHAPE.read_text(encoding='utf-8'))

    def test_all_consumed_sources_and_requirement_pointers_resolve(self):
        r=self.r
        for key,path in r['source_paths'].items():
            self.assertEqual(r['source_sha256'][key],hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
        self.assertEqual(len(r['requirements']),13)
        for req in r['requirements']:
            path=ROOT/req['source_path'];raw=path.read_bytes()
            self.assertEqual(req['source_sha256'],hashlib.sha256(raw).hexdigest())
            data=json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
            for part in req['source_json_pointer'].split('/')[1:]:
                data=data[int(part)] if isinstance(data,list) else data[part]
            self.assertIsNotNone(data)

    def test_design_sites_are_not_platforms_or_occurrence_guarantees(self):
        r=self.r
        self.assertEqual(r['served_design_site_count_including_fs'],27)
        self.assertEqual(r['inventory_site_count_including_fs'],24)
        self.assertEqual(r['proposed_site_count'],3)
        self.assertEqual(r['nonhub_ordered_occurrence_count_per_trip'],28)
        self.assertIsNone(r['physical_platform_count'])
        self.assertTrue(all(s['physical_platform_count'] is None and not s['boarding_authorised'] for s in r['served_sites']))
        self.assertTrue(set(OMITTED).isdisjoint({s['site_id'] for s in r['served_sites']}))
        for sid in ('RT031::P2V2S_0031_PROJECTED_ROAD_POINT','PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE'):
            site=next(s for s in r['served_sites'] if s['site_id']==sid)
            self.assertEqual(len(site['ordered_occurrences']),2)
            self.assertLess(site['ordered_occurrences'][0]['path_node_index'],site['ordered_occurrences'][1]['path_node_index'])
            opportunities=site['station_journey_opportunities_nominal']
            self.assertEqual(len(opportunities),17)
            self.assertTrue(all(o['from_fs_alight_occurrence_id']!=o['to_fs_board_occurrence_id'] for o in opportunities))
            for o in opportunities:
                self.assertAlmostEqual(o['to_fs_arrival_min']-o['to_fs_board_min'],site['nominal_fs_access_min']['to_fs_min'])
                self.assertAlmostEqual(o['from_fs_alight_min']-o['from_fs_departure_min'],site['nominal_fs_access_min']['from_fs_min'])
                self.assertFalse(o['physical_boarding_authorised'])

    def test_one_identical_complete_path_every_trip(self):
        r=self.r
        self.assertEqual(len(r['ordered_stop_event_ledger_nominal']),17)
        expected_sites={s['site_id'] for s in r['served_sites']}-{FS}
        for ledger in r['ordered_stop_event_ledger_nominal']:
            events=ledger['events']
            self.assertEqual(events[0]['role'],'FULL_TRIP_START_FS')
            self.assertEqual(events[-1]['role'],'FULL_TRIP_END_FS')
            self.assertEqual(sum(e['role']=='INTERMEDIATE_FS_STAY_ONBOARD_DESIGN' for e in events),1)
            self.assertEqual({e['site_id'] for e in events if 'site_id' in e},expected_sites)
            self.assertEqual({e['wing'] for e in events if 'wing' in e},{'east_A','west_B'})
            self.assertTrue(all(not e['physical_boarding_authorised'] for e in events if 'site_id' in e))
        paths={f['properties']['wing']:f['geometry']['coordinates'] for f in self.shape['features']
               if f['properties']['role']=='WING_OF_SAME_LINE'}
        complete=next(f['geometry']['coordinates'] for f in self.shape['features']
                      if f['properties']['role']=='COMPLETE_PUBLIC_ITINERARY_EXAMPLE')
        self.assertEqual(complete,paths['east_A']+paths['west_B'][1:])
        self.assertEqual(len([f for f in self.shape['features'] if f['properties']['role']=='DESIGN_SITE']),27)

    def test_no_implicit_policy_or_probabilistic_certification(self):
        r=self.r
        for name in ('network_selected','primary_selection_authorised','runner_up_selection_authorised',
                     'full_trip_count_change_adopted','stop_omissions_adopted','calendar_adopted',
                     'ready_for_final_recommendation','ready_for_public_timetable',
                     'physical_passenger_continuity_certified','full_history_legality_certified'):
            self.assertFalse(r[name])
        for name in ('decision_budget_km','uncertainty_band_min','demand_weighted_gjt_improvement_min',
                     'missed_connection_probability','annual_noncommercial_km','complete_operator_cost'):
            self.assertIsNone(r[name])
        self.assertEqual(r['caller_adopted_full_trips_per_day'],16)
        self.assertEqual(r['full_trips_per_comparison_day'],17)
        self.assertEqual(set(r['municipality_names']),set(r['coverage_fraction'])-{'TOTAL'})
        self.assertAlmostEqual(r['annual_service_km_260_day_comparison'],120323.89578791281)

    def test_package_rebuild_is_identical(self):
        r,shape=build()
        self.assertEqual(r,self.r)
        self.assertEqual(shape,self.shape)
        text=DOC.read_text(encoding='utf-8')
        self.assertIn('120.324',text)
        self.assertIn('non27 paline',text)


if __name__=='__main__':unittest.main()
