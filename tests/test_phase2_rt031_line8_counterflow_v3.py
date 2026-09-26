import json
from pathlib import Path
import unittest

from scripts.phase2_probe_rt031_line8_local_counterflow_v3 import evaluate, site_rides, VIRTUAL, NORTH
from scripts.phase2_rt031_ordered_via_node_path_v3 import ordered_path

BASE=Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3'


class CounterflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((BASE/'local_counterflow.json').read_text(encoding='utf-8'))
        cls.wings=json.loads((BASE/'independent_wings.json').read_text(encoding='utf-8'))
        cls.timetable=json.loads((BASE/'peak_direction_retimed.json').read_text(encoding='utf-8'))

    def test_no_hidden_intermediate_station_return(self):
        edges={}
        for eid,u,v,cost in [('sx','s','x',1),('xs','x','s',1),('sp','s','p',1),
                             ('xq','x','q',2),('qp','q','p',2),('ps','p','s',1)]:
            edges[eid]=dict(edge_id=eid,u_node_id=u,v_node_id=v,osm_way_id=eid,
                            length_m=str(cost),running_minutes_model=str(cost))
        relaxed=ordered_path(edges,[],['s','x','p','s'])
        strict=ordered_path(edges,[],['s','x','p','s'],allow_internal_origin=False)
        self.assertEqual(relaxed['_path_edge_ids'],['sx','xs','sp','ps'])
        self.assertEqual(strict['_path_edge_ids'],['sx','xq','qp','ps'])
        self.assertFalse(strict['full_history_via_way_legality_certified'])

    def test_distinct_directional_occurrences_not_identity_shortcut(self):
        loop={'road_minutes':40,'events':[{'stop_place_id':'s','offset_from_wing_origin_min':4.5},
                                         {'stop_place_id':'s','offset_from_wing_origin_min':37}]}
        self.assertEqual(site_rides(loop,'s',.5),{'from_fs_min':4,'to_fs_min':3})
        loop['events'].pop()
        self.assertEqual(site_rides(loop,'s',.5)['to_fs_min'],35.5)
        with self.assertRaises(ValueError):
            site_rides(loop,'absent',.5)

    def test_counterflow_benefit_has_real_distance_cost(self):
        a=self.data
        self.assertEqual(len(a['cases']),15)
        base,full=(next(c for c in a['cases'] if c['case_id']==name) for name in ('baseline','both'))
        self.assertAlmostEqual(base['annual_service_km'],115800.435154,places=5)
        self.assertAlmostEqual(full['annual_service_km'],130567.294131,places=5)
        self.assertAlmostEqual(full['added_annual_service_km'],14766.858977,places=5)
        for row in full['network_priority_rides_nominal']:
            self.assertLess(row['best_from_fs_min'],4.32)
            self.assertLess(row['best_to_fs_min'],4.14)
        self.assertEqual(a['trips_unchanged'],self.timetable['trips'])
        for c in a['cases']:
            self.assertTrue(all(not lost for lost in c['lost_original_site_ids'].values()))
            self.assertEqual(len(c['scenarios']),27)
        for name,loop in a['candidate_loops'].items():
            sid=VIRTUAL if name.startswith('west') else NORTH
            occurrences=[e for e in loop['events'] if e['stop_place_id']==sid]
            self.assertGreaterEqual(len({e['path_node_index'] for e in occurrences}),2)
            self.assertEqual(len({e['occurrence_id'] for e in loop['events']}),len(loop['events']))
            self.assertTrue(all(not e['boarding_authorised'] for e in loop['events']))

    def test_preserve_bad_rail_gap_and_fleet_results(self):
        full=next(c for c in self.data['cases'] if c['case_id']=='both')
        cross=next(c for c in self.data['cases'] if c['case_id']=='cross_north_only')
        self.assertFalse(full['all_scenarios_same_morning_targets_retained'])
        self.assertFalse(cross['all_scenarios_optimistic_h60'])
        self.assertEqual(max(r['minimum_vehicle_count_conditional'] for r in full['scenarios']),6)
        for flag in ('network_selected','primary_selection_authorised','runner_up_selection_authorised'):
            self.assertFalse(self.data[flag])
        for field in ('decision_budget_km','uncertainty_band_min','total_operating_km','approved_uplift_percent'):
            self.assertIsNone(self.data[field])

    def test_replay_fixed_timetable_comparisons(self):
        a=self.data
        for case in a['cases']:
            cid=case['case_id']
            if cid.startswith('joint_'):
                _,wing,am_order,rest_order=cid.split('_')
                am,rest=('west_A','west_B') if wing=='west' else ('east_B','east_A')
                pool={am:a['joint_candidate_loops'][am_order][am],rest:a['joint_candidate_loops'][rest_order][rest]}
            else:
                pool=a['cross_candidate_loops'] if cid.startswith('cross_') else a['candidate_loops']
            loops={name:pool[name] if name.split('_')[0] in case['changed_wings'] else value
                   for name,value in self.wings['loops'].items()}
            replay=evaluate(loops,self.wings['loops'],a['trips_unchanged'],case['represented_via_node_joins'],
                            self.timetable['new_morning_train_targets_min'],a['reference_cap_unchanged'])
            for k,v in replay.items():
                self.assertEqual(v,case[k],(cid,k))

    def test_mapped_paths_and_one_minute_clock_shift(self):
        shape=json.loads((BASE/'local_counterflow.geojson').read_text(encoding='utf-8'))
        points=[f for f in shape['features'] if f['geometry']['type']=='Point']
        self.assertEqual(len(points),28)
        lines=[f for f in shape['features'] if f['geometry']['type']=='LineString']
        self.assertEqual(len(lines),44)
        for f in lines:
            pts=f['geometry']['coordinates']
            self.assertEqual(pts[0],pts[-1])
            self.assertNotIn(pts[0],pts[1:-1])
        fixed=self.data['full_correction_one_minute_retiming']
        full=next(c for c in self.data['cases'] if c['case_id']=='both')
        self.assertEqual(fixed['annual_service_km'],full['annual_service_km'])
        self.assertTrue(fixed['all_scenarios_same_morning_targets_retained'])
        self.assertTrue(fixed['all_scenarios_optimistic_h60'])
        self.assertEqual(len(fixed['trips']),36)


if __name__=='__main__':
    unittest.main()
