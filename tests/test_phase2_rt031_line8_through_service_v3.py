import copy
import itertools
import unittest

from scripts.phase2_audit_rt031_line8_through_service_v3 import (
    inputs,read_result_file,successor_edges,solve_links,through_frontier,plan_blocks,
    passenger_ledger,through_permission,journeys,middle_schedules,middle_retiming_comparison,
    adjusted_loops,minimum_blocks,AUTH,TIMETABLE,EXAMPLES,BASE,digest,report,DOC,joint_retiming_comparison)


class ThroughServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authority,cls.p,cls.stops,cls.tt,cls.loops=inputs()
        cls.r=read_result_file();cls.trips=cls.r['trips']
        cls.grid={key:adjusted_loops(cls.loops,*key) for key in cls.p['adjusted']}

    def test_caller_choices_not_operating_approval(self):
        self.assertEqual(self.authority['accepted_design_addition_ids'],['N1212'])
        self.assertEqual(self.authority['rejected_design_addition_ids'],['N0655'])
        self.assertFalse(self.authority['nearby_replacement_automatically_authorised'])
        sites={e['stop_place_id'] for loop in self.loops.values() for e in loop['events']}
        self.assertEqual(len(sites),28)  # Plus FS = 29 design sites.
        self.assertIn('PROXY::RT031_ADDITIONAL::n:534398.29:5063851.64',sites)
        self.assertNotIn('PROXY::RT031_ADDITIONAL::n:531392.69:5063340.44',sites)
        self.assertIn('RT031::P2V2S_0031_PROJECTED_ROAD_POINT',sites)
        self.assertIn('PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE',sites)
        self.assertEqual(self.trips,self.tt['trips'])
        self.assertEqual(self.r['annual_service_km'],self.tt['annual_service_km'])
        for k in ('geometry_changed','departures_changed','new_site_boarding_authorised',
                  'physical_passenger_continuity_certified','operating_plan_adopted',
                  'new_fleet_increase_accepted','network_selected','primary_selection_authorised','runner_up_selection_authorised'):
            self.assertFalse(self.r[k])
        for k in ('operator_route_id','decision_budget_km','uncertainty_band_min'):
            self.assertIsNone(self.r[k])

    def test_source_hashes_and_added_stop_frequency_rail_check(self):
        h=self.r['source_sha256_normalized_newlines']
        for key,path in [('authority',AUTH),('timetable',TIMETABLE),('addition_examples',EXAMPLES),('counterflow',BASE/'local_counterflow.json')]:
            self.assertEqual(h[key],digest(path))
        check=self.r['accepted_addition_timing_check']
        self.assertTrue(check['fixed_31_timetable_pass'])
        self.assertEqual(check['per_site_rail_check_count'],308)
        self.assertEqual(check['nominal_vehicle_count'],4)

    def test_current_register_and_coverage_do_not_keep_rejected_stop_gain(self):
        arlate=next(c for c in self.stops['single_additions'] if c['candidate_id']=='N1212')
        self.assertEqual(self.r['current_potential_access_fraction'],arlate['potential_access_fraction'])
        self.assertEqual(self.r['current_potential_access_fraction']['97058'],self.r['baseline_potential_access_fraction']['97058'])
        self.assertEqual(len(self.r['current_design_stop_register']),29)
        self.assertEqual(self.r['current_design_stop_register'][-1]['source_candidate_id'],'N1212')
        for row,t in zip(self.r['current_design_trip_ledger'],self.trips):
            self.assertEqual(row['departure_min'],t['departure_min'])
            loop=self.grid[1.1,.5][t['loop']]
            self.assertEqual(row['fs_return_nominal_min'],t['departure_min']+loop['road_minutes'])
            for actual,event in zip(row['events_nominal'],loop['events']):
                self.assertEqual(actual['departure_min'],t['departure_min']+event['offset_from_wing_origin_min'])

    def test_pure_alternation_all_27_counts_independently(self):
        joins={a+'>'+b:a!=b and self.p['family']['joins'][a+'>'+b] for a in self.loops for b in self.loops}
        for case in self.r['pure_alternation_27_separate_scenario_minima']:
            rebuilt=minimum_blocks(self.trips,self.grid[case['moving_multiplier'],case['dwell_min']],joins,case['recovery_min'])
            for k,v in rebuilt.items():self.assertEqual(case[k],v)
        nominal=next(c for c in self.r['pure_alternation_27_separate_scenario_minima'] if (c['moving_multiplier'],c['dwell_min'],c['recovery_min'])==(1.1,.5,10))
        self.assertEqual(nominal['minimum_vehicle_count_conditional'],5)
        self.assertEqual(max(c['minimum_vehicle_count_conditional'] for c in self.r['pure_alternation_27_separate_scenario_minima']),7)

    def test_frontier_exact_objectives_not_solver_specific_vehicle_labels(self):
        for case in self.r['cases']:
            grid={tuple(k):self.grid[tuple(k)] for k in case['timing_scenarios']}
            edges=successor_edges(self.trips,grid,self.p['family']['joins'],case['recovery_min'])
            rebuilt=through_frontier(self.trips,edges,case['vehicle_count_comparison'])
            self.assertEqual([(c['cross_wing_count'],c['max_cross_wing_fs_wait_min']) for c in rebuilt],
                             [(c['cross_wing_count'],c['max_cross_wing_fs_wait_min']) for c in case['frontier']])
            self.assertIsNone(solve_links(31,edges,case['vehicle_count_comparison'],cross_only=True))
        self.assertEqual([p['cross_wing_count'] for p in self.r['cases'][0]['frontier']],[0,10,18,20,22,24,26])

    def test_every_stored_link_valid_across_declared_scenarios(self):
        for case in self.r['cases']:
            grid={tuple(k):self.grid[tuple(k)] for k in case['timing_scenarios']}
            for point in case['frontier']:
                blocks=plan_blocks(self.trips,point['links'])
                self.assertEqual(len(blocks),case['vehicle_count_comparison'])
                self.assertEqual(sum(len(b) for b in blocks),31)
                for e in point['links']:
                    a=self.trips[e['from_trip_index']];b=self.trips[e['to_trip_index']]
                    waits=[b['departure_min']-a['departure_min']-g[a['loop']]['road_minutes'] for g in grid.values()]
                    self.assertGreaterEqual(min(waits)+1e-8,case['recovery_min'])
                    self.assertEqual(e['scenario_fs_wait_max'],max(waits))
                    self.assertEqual(e['cross_wing'],a['loop']!=b['loop'])

    def test_common_fixed_block_compatibility_not_27_changing_assignments(self):
        # The severe case uses one actual successor set valid in all nine grids.
        case=self.r['cases'][1];self.assertEqual(len(case['timing_scenarios']),9)
        self.assertEqual(case['recovery_min'],15)
        self.assertEqual(case['vehicle_count_comparison'],6)
        for link in case['maximum_continuation_example']['links']:
            self.assertGreaterEqual(link['scenario_fs_wait_min']+1e-8,15)

    def test_same_vehicle_without_explicit_passenger_permission_is_not_through(self):
        example=self.r['cases'][0]['illustrative_20_link_plan']
        link=copy.deepcopy(next(e for e in example['ordered_continuation_ledger'] if e['cross_wing']))
        self.assertTrue(through_permission(link))
        for key,value in [('passenger_continuation_planned',False),('remain_onboard_planned',False),
                          ('to_vehicle_block_id','DIFFERENT'),('to_design_route_id','OTHER_SERVICE'),
                          ('requires_vehicle_change_in_plan',True),('cross_wing',False)]:
            bad={**link,key:value};self.assertFalse(through_permission(bad))

    def test_20_links_are_not_31_guarantees_or_20_percent_passengers(self):
        example=self.r['cases'][0]['illustrative_20_link_plan']
        ledger=example['ordered_continuation_ledger']
        self.assertEqual(sum(through_permission(e) for e in ledger),20)
        self.assertEqual(sum(not e['cross_wing'] for e in ledger),7)
        self.assertEqual(len(plan_blocks(self.trips,example['links'])),4)
        self.assertAlmostEqual(example['max_cross_wing_fs_wait_min'],24.84062594104377)
        self.assertFalse(example['operating_plan_adopted'])

    def test_ordered_journeys_include_fs_wait_and_do_not_teleport(self):
        example=self.r['cases'][0]['illustrative_20_link_plan'];g=self.grid[1.1,.5]
        rebuilt=journeys(self.trips,{(1.1,.5):g},example['ordered_continuation_ledger'])
        self.assertEqual(rebuilt,example['journeys'])
        for row in rebuilt:
            a=self.trips[row['from_trip_index']];b=self.trips[row['to_trip_index']]
            src=max((e for e in g[a['loop']]['events'] if e['stop_place_id']==row['origin_site_id']),key=lambda e:e['path_node_index'])
            dst=min((e for e in g[b['loop']]['events'] if e['stop_place_id']==row['destination_site_id']),key=lambda e:e['path_node_index'])
            self.assertEqual(src['occurrence_id'],row['boarding_occurrence_id'])
            self.assertEqual(dst['occurrence_id'],row['alighting_occurrence_id'])
            self.assertAlmostEqual(row['nominal_elapsed_min'],row['nominal_alighting_min']-row['nominal_boarding_min'])
            self.assertGreater(row['nominal_elapsed_min'],row['nominal_onboard_fs_wait_min'])
            self.assertFalse(row['physical_journey_certified'])

    def test_impermitted_same_carrier_produces_no_journeys(self):
        example=self.r['cases'][0]['illustrative_20_link_plan']
        denied=[{**e,'passenger_continuation_planned':False} for e in example['ordered_continuation_ledger']]
        self.assertEqual(journeys(self.trips,{(1.1,.5):self.grid[1.1,.5]},denied),[])

    def test_middle_enumeration_equals_brute_force_toy(self):
        brute=[list(c) for c in itertools.combinations(range(5,40,5),2) if max(b-a for a,b in zip([0,*c],[*c,40]))<=15]
        self.assertEqual(middle_schedules(0,40,2,15),brute)
        self.assertEqual(len(middle_schedules(540,995,2,155)),6)
        self.assertEqual(len(middle_schedules(545,995,3,120)),84)

    def test_504_middle_comparisons_preserve_peaks_counts_km_and_prove_bounded_floor(self):
        r=middle_retiming_comparison();self.assertEqual(r,self.r['central_retiming_comparison'])
        self.assertEqual(len(r['cases']),504)
        self.assertEqual(r['minimum_pure_alternating_nominal_vehicles'],5)
        self.assertEqual(r['minimum_pure_alternating_severe_vehicles'],7)
        for c in r['cases']:
            self.assertEqual(len(c['trips']),31)
            for pattern in self.loops:
                baseline=[t for t in self.trips if t['loop']==pattern]
                proposed=[t for t in c['trips'] if t['loop']==pattern]
                self.assertEqual(len(proposed),len(baseline))
                self.assertEqual([t for t in proposed if t['departure_min']<=545 or t['departure_min']>=995],
                                 [t for t in baseline if t['departure_min']<=545 or t['departure_min']>=995])
        self.assertFalse(r['retiming_adopted'])

    def test_tiny_matching_proves_cannot_reuse_one_vehicle_twice(self):
        trips=[{'loop':'a','departure_min':0},{'loop':'b','departure_min':10},{'loop':'b','departure_min':10}]
        grid={(1.1,.5):{'a':{'road_minutes':5},'b':{'road_minutes':5}}}
        joins={a+'>'+b:True for a in ('a','b') for b in ('a','b')}
        edges=successor_edges(trips,grid,joins,5)
        self.assertIsNone(solve_links(3,edges,1))
        self.assertEqual(solve_links(3,edges,2)['cross_wing_count'],1)
        self.assertEqual(through_frontier(trips,edges,2)[0]['max_cross_wing_fs_wait_min'],5)

    def test_joint_four_vehicle_infeasibility_recompiled_after_arlate(self):
        rebuilt=joint_retiming_comparison()
        self.assertTrue(rebuilt['infeasible_in_declared_domain'])
        self.assertEqual(rebuilt['departure_candidate_count'],317)
        self.assertEqual(rebuilt['vehicle_successor_candidate_count'],21904)
        self.assertEqual(rebuilt['solver_status'],self.r['joint_retiming_comparison']['solver_status'])
        self.assertFalse(rebuilt['retiming_adopted'])

    def test_fifth_vehicle_lower_bound_and_constructive_integral_witness(self):
        five=self.r['five_vehicle_wait_comparison']
        self.assertTrue(five['minimum_proven']);self.assertFalse(five['fleet_increase_adopted'])
        optimum=five['minimum_maximum_nominal_fs_wait_min']
        below=max(c['nominal_fs_wait_ceiling_comparison'] for c in five['checks'] if c['infeasible_in_declared_domain'])
        self.assertTrue(joint_retiming_comparison(vehicle_count=5,fs_wait_limit=below)['infeasible_in_declared_domain'])
        rebuilt=joint_retiming_comparison(vehicle_count=5,fs_wait_limit=optimum)
        self.assertTrue(rebuilt['witness_found'])
        self.assertLessEqual(rebuilt['achieved_max_nominal_fs_wait_min'],optimum+1e-8)
        self.assertEqual(len(rebuilt['alternating_blocks']),5)
        self.assertTrue(all(through_permission(e) for e in rebuilt['links']))

    def test_report_reproduces_with_unresolved_operating_limits(self):
        self.assertEqual(report(self.r),DOC.read_text(encoding='utf-8'))
        self.assertIn('non accorcia automaticamente',report(self.r))


if __name__=='__main__':unittest.main()
