import copy
from fractions import Fraction
import json
from types import SimpleNamespace
import unittest

import numpy as np

from scripts.phase2_audit_rt031_line8_stop_plan_v3 import (
    read_result,EXAMPLES,SHAPE,BASE,AUTH,TIMETABLE,FS,PATTERNS,FLAGS,
    add_site,bounded_walk,nondominated,timing_check,sources,digest,hub_boundaries,
    adjusted_loops,minimum_blocks)
from scripts.phase2_export_rt031_line8_stop_plan_v3 import study_examples,report,DOC,visualization
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import pedestrian_time


class StopPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=read_result();cls.p=sources()
        cls.tt=json.loads(TIMETABLE.read_text(encoding='utf-8'))
        cls.examples=json.loads(EXAMPLES.read_text(encoding='utf-8'))
        cls.shape=json.loads(SHAPE.read_text(encoding='utf-8'))

    def test_upstream_hashes_and_no_added_authority(self):
        h=self.r['source_sha256_normalized_newlines']
        for key,path in [('authority31',AUTH),('timetable',TIMETABLE),('counterflow',BASE/'local_counterflow.json')]:
            self.assertEqual(h[key],digest(path))
        self.assertEqual(self.examples['source_sha256_normalized_newlines'],h)
        self.assertEqual(self.r['annual_service_km'],self.tt['annual_service_km'])
        self.assertEqual(self.r['approved_stop_additions'],0)
        for k in (*FLAGS,'geometry_changed','platforms_certified','actual_timetable_certified','full_history_road_legality_certified'):
            self.assertFalse(self.r[k])
        for k in ('decision_budget_km','uncertainty_band_min'):self.assertIsNone(self.r[k])

    def test_register_sites_are_not_platforms(self):
        sites=self.r['register']
        self.assertEqual([s['number'] for s in sites],list(range(1,29)))
        self.assertEqual(len({s['site_id'] for s in sites}),28)
        self.assertEqual(sum(s['status']=='INVENTORY_SITE_PLATFORM_UNVERIFIED' for s in sites),26)
        for s in sites:
            self.assertFalse(s['boarding_authorised'])
            for k in ('platform_count','physical_platform_side','pedestrian_accessibility_on_field'):
                self.assertIsNone(s[k])
            for e in s['occurrences']:
                self.assertFalse(e['boarding_authorised'])
                self.assertIsNone(e['physical_platform_side'])
                loop=self.p['family']['loops'][e['pattern']]
                self.assertEqual(loop['edge_ids'][e['path_node_index']-1],e['incoming_edge'])
                self.assertEqual(loop['edge_ids'][e['path_node_index']],e['outgoing_edge'])

    def test_hub_boundaries_do_not_certify_through_service(self):
        hub=next(s for s in self.r['register'] if s['site_id']==FS)
        expected=hub_boundaries({pat:self.p['family']['loops'][pat] for pat in PATTERNS})
        self.assertEqual(hub['hub_boundary_events'],expected)
        self.assertEqual(len(expected),4)
        self.assertTrue(all(not e['cross_wing_passenger_continuity_certified'] for e in expected))

    def test_six_manoeuvres_are_ordered_but_not_bus_approved(self):
        self.assertEqual([m['id'] for m in self.r['manoeuvres']],['M1','M2','M3','M4','M5','M6'])
        for m in self.r['manoeuvres']:
            self.assertFalse(m['bus_manoeuvre_authorised'])
            loop=self.p['family']['loops'][m['pattern']]
            i=m['path_node_index']
            self.assertEqual(loop['edge_ids'][i-1:i+1],[m['incoming_edge'],m['outgoing_edge']])

    def test_complete_disclosed_finite_screen_and_failures_retained(self):
        singles=self.r['single_additions'];pairs=self.r['pair_comparisons']
        self.assertEqual(len(singles),self.r['candidate_node_count'])
        self.assertEqual(len(singles),1362)
        self.assertEqual(sum(c['timing']['fixed_31_timetable_pass'] for c in singles),1313)
        self.assertEqual(len(pairs),5253)
        self.assertEqual(sum(c['timing']['fixed_31_timetable_pass'] for c in pairs),4186)
        for c in singles+pairs:
            self.assertEqual(c['extra_service_km'],0)
            self.assertFalse(c['boarding_authorised'])
            self.assertEqual(c['timing']['fixed_31_timetable_pass'],not c['timing']['failure_counts'])
            self.assertFalse(c['timing']['physical_boarding_certified'])
        self.assertIn('not all continuous',self.r['scope'])

    def test_pareto_has_no_composite_score_and_keeps_equal_vectors(self):
        def case(key,gain,west=1,east=0,ok=True):
            return {'candidate_id':key,'gain_weight_vector':[gain]+[0]*14,
                    'added_event_counts':{'west_B':west,'east_A':east},
                    'timing':{'fixed_31_timetable_pass':ok}}
        cases=[case('a',2),case('b',1),case('equal',2),case('tradeoff',3,2),case('fail',9,ok=False)]
        self.assertEqual(nondominated(cases),['a','equal','tradeoff'])
        self.assertEqual(nondominated(self.r['single_additions']),self.r['single_addition_spatial_dwell_frontier_ids'])

    def test_pair_coverage_is_union_not_sum(self):
        lookup={c['candidate_id']:c for c in self.r['single_additions']}
        overlap_found=False
        for pair in self.r['pair_comparisons']:
            a,b=[lookup[k] for k in pair['candidate_ids']]
            for m in self.r['municipality_names']:
                for t in ('5','8','10'):
                    base=Fraction(self.r['baseline_potential_access_fraction'][m][t])
                    av=Fraction(a['potential_access_fraction'][m][t]);bv=Fraction(b['potential_access_fraction'][m][t])
                    combined=Fraction(pair['potential_access_fraction'][m][t])
                    self.assertGreaterEqual(combined,max(av,bv))
                    self.assertLessEqual(combined,min(Fraction(1),av+bv-base))
                    overlap_found |= combined<av+bv-base
        self.assertTrue(overlap_found)

    def test_examples_replay_fixed_departures_and_all_27_fleet_scenarios(self):
        self.assertEqual([c['candidate_id'] for c in study_examples(self.r)],['N0655','N1212'])
        for example in self.examples['examples']:
            loops=copy.deepcopy({pat:self.p['family']['loops'][pat] for pat in PATTERNS})
            for pat,added in example['added_events_by_pattern'].items():
                for event in added:
                    i=event['path_node_index']
                    self.assertEqual(loops[pat]['edge_ids'][i-1:i+1],[event['incoming_edge'],event['outgoing_edge']])
                loops[pat]['events']+=added
                loops[pat]['events'].sort(key=lambda e:(e['path_node_index'],e['stop_place_id']))
            self.assertEqual(timing_check(loops,self.p,self.tt),example['timing'])
            self.assertTrue(example['timing']['fixed_31_timetable_pass'])
            self.assertEqual(len(example['conditional_scenarios']),27)
            for scenario in example['conditional_scenarios']:
                adjusted=adjusted_loops(loops,scenario['moving_multiplier'],scenario['dwell_min'])
                rebuilt=minimum_blocks(self.tt['trips'],adjusted,self.p['family']['joins'],scenario['recovery_min'])
                for k,v in rebuilt.items():self.assertEqual(scenario[k],v)
            self.assertEqual(max(s['minimum_vehicle_count_conditional'] for s in example['conditional_scenarios']),6)
        pair=self.examples['examples'][-1]
        self.assertEqual(pair['timing']['per_site_rail_check_count'],319)
        self.assertAlmostEqual(pair['timing']['smallest_AM_residual_min_after_3min_transfer'],.8406259410437684)

    def test_directional_occurrences_are_distinct_for_repeated_local_stop(self):
        west=self.examples['examples'][0]
        ride=west['timing']['new_site_nominal_rides'][0]
        self.assertNotEqual(ride['from_fs_alighting_occurrence_id'],ride['to_fs_boarding_occurrence_id'])
        self.assertLess(ride['from_fs_min'],3)
        self.assertLess(ride['to_fs_min'],3)
        self.assertEqual(west['timing']['extra_nominal_running_and_dwell_min']['west_B'],1)
        self.assertEqual(west['timing']['extra_stress_running_and_dwell_min']['west_B'],2)

    def test_increased_dwell_cannot_reuse_old_rail_eligibility(self):
        loops=copy.deepcopy({pat:self.p['family']['loops'][pat] for pat in PATTERNS})
        loops['east_A']['road_minutes']+=20
        result=timing_check(loops,self.p,self.tt)
        self.assertFalse(result['fixed_31_timetable_pass'])
        self.assertTrue(result['failed_rail_targets'])

    def test_additions_preserve_edges_charge_both_occurrences_and_fail_if_off_path(self):
        edges={f'e{i}':{'u_node_id':u,'v_node_id':v,'running_minutes_model':1}
               for i,(u,v) in enumerate([('F','A'),('A','B'),('B','A'),('A','F')])}
        loops={'west_B':{'edge_ids':list(edges),'events':[],'road_km':4,'road_minutes':4}}
        modified=add_site(loops,'A',edges)
        self.assertEqual(loops['west_B']['events'],[])
        self.assertEqual(modified['west_B']['edge_ids'],loops['west_B']['edge_ids'])
        self.assertEqual([e['path_node_index'] for e in modified['west_B']['events']],[1,3])
        self.assertEqual(modified['west_B']['road_km'],4)
        with self.assertRaisesRegex(ValueError,'already'):add_site(modified,'A',edges)
        with self.assertRaisesRegex(ValueError,'not on'):add_site(loops,'OFF',edges)

    def test_bounded_pedestrian_screen_equals_full_dijkstra_at_all_thresholds(self):
        graph=SimpleNamespace(reverse_adjacency={'s':[('a',300),('b',800),('c',801)],'a':[('d',100)]},
            snap=lambda lat,lon:SimpleNamespace(status='REACHABLE',node_id='s',connector_distance_m=0))
        units=['s','a','b','c','d','unreachable']
        snap_map={n:{'population_snap_node_id':n,'population_connector_distance_m':0} for n in units}
        snap_map['d']['population_connector_distance_m']=1
        context={'graph':graph,'snap_map':snap_map,'units':units}
        bounded,_=bounded_walk(context,0,0)
        full,_=pedestrian_time(graph,snap_map,units,0,0)
        for t in (5,8,10):np.testing.assert_array_equal(bounded<=t,full<=t)
        self.assertEqual(bounded[2],10)
        self.assertTrue(np.isinf(bounded[3]))
        snap_map['a']['population_connector_distance_m']=-1
        with self.assertRaisesRegex(ValueError,'negative connector'):bounded_walk(context,0,0)

    def test_report_reproducible_and_visual_bounded(self):
        self.assertEqual(DOC.read_text(encoding='utf-8'),report(self.r))
        fragment=visualization(self.r,self.shape)
        self.assertLess(len(fragment.encode()),1_000_000)
        self.assertNotIn('__DATA__',fragment)
        self.assertIn('N0655',fragment)
        self.assertIn('N1212',fragment)


if __name__=='__main__':unittest.main()
