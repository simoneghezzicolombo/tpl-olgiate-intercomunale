import copy
import json
import unittest

from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import (
    AUTH,OUTPUT,DOC,read_result,inputs,timing_offsets,verify,solve_case,report,digest,source_fingerprints,BASE)


class UniformCompleteLineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=read_result();_,cls.p,_,_,cls.loops=inputs()

    def test_caller_contract_requires_every_commercial_trip_to_operate_whole_route(self):
        a=json.loads(AUTH.read_text(encoding='utf-8'))
        self.assertTrue(a['all_commercial_trips_same_complete_path'])
        self.assertTrue(a['both_wings_required_in_every_commercial_trip'])
        self.assertFalse(a['short_turn_public_trips_allowed'])
        self.assertFalse(a['mixing_wing_only_public_services_allowed'])
        self.assertIsNone(a['full_circuit_daily_count_adopted'])
        self.assertEqual(self.r['authority_sha256'],digest(AUTH))
        for key,value in source_fingerprints(self.p,self.loops).items():
            self.assertEqual(self.r[key],value)
        self.assertFalse(self.r['earlier_31_wing_trip_plan_is_final_proposal'])
        readiness=json.loads((BASE/'proposal_readiness.json').read_text(encoding='utf-8'))
        self.assertIsNone(readiness['current_design_proposal'])
        self.assertEqual(readiness['current_caller_service_authority'],
                         'config/rt031_uniform_complete_line_authority_v3.json')
        self.assertEqual(readiness['current_uniform_route_comparison'],OUTPUT.name)

    def test_full_path_is_exact_concatenation_not_a_renamed_single_wing(self):
        expected=sum(l['distance_m'] for l in self.loops.values())/1000
        self.assertAlmostEqual(self.r['full_circuit_distance_km'],expected)
        for key,p in self.r['full_route_patterns'].items():
            a,b=key.split('>')
            self.assertEqual(p['edge_ids'],self.loops[a]['edge_ids']+self.loops[b]['edge_ids'])
            self.assertEqual(p['intermediate_fs_path_index'],len(self.loops[a]['edge_ids']))
            self.assertFalse(p['full_history_legality_certified'])

    def test_31_wings_cannot_be_relabelled_as_31_full_circuits(self):
        values={c['full_trips_per_day']:c for c in self.r['production_comparisons']}
        self.assertAlmostEqual(values[15]['annual_service_km'],107946.8126370199)
        self.assertAlmostEqual(values[16]['annual_service_km'],115143.26681282124)
        self.assertAlmostEqual(values[31]['annual_service_km'],223090.07944984114)
        self.assertLess(values[15]['annual_service_km'],111419)
        self.assertGreater(values[16]['annual_service_km'],111419)

    def test_intermediate_fs_holding_and_terminal_recovery_are_distinct(self):
        for c in self.r['cases']:
            grid=timing_offsets(self.loops,c['first_wing'],c['intermediate_fs_departure_offset_min'])
            for (moving,dwell),g in grid.items():
                self.assertGreaterEqual(g['intermediate_fs_holding_excluding_dwell_min'],-1e-8)
                self.assertAlmostEqual(g['midpoint_departure']-g['midpoint_arrival'],
                    g['intermediate_fs_holding_excluding_dwell_min']+dwell)
            for s in c['conditional_scenarios']:
                self.assertTrue(s['midpoint_holding_excludes_terminal_recovery'])
                self.assertEqual(s['allowance_per_wing_trip_min'],s['terminal_recovery_once_per_full_trip_min'])
        with self.assertRaisesRegex(ValueError,'precedes'):timing_offsets(self.loops,'west_B',30)

    def test_all_cases_replay_all_site_frequency_and_dated_trains(self):
        self.assertEqual(len(self.r['cases']),14)
        for c in self.r['cases']:
            grid=timing_offsets(self.loops,c['first_wing'],c['intermediate_fs_departure_offset_min'])
            rail,scenarios=verify(grid,c['full_trip_departures_min'],self.p,self.loops)
            self.assertEqual(rail,c['rail_target_bindings'])
            self.assertEqual(len(rail),308)
            self.assertEqual(scenarios,c['conditional_scenarios'])
            self.assertEqual(len(scenarios),27)
            self.assertTrue(c['every_trip_operates_both_wings'])
            self.assertFalse(c['short_turns_present'])
            self.assertEqual(c['full_trip_count'],len(c['full_trip_departures_min']))
            self.assertEqual({t['full_pattern_id'] for t in c['full_trip_ledger']},{c['first_wing']+'>'+c['second_wing']})

    def test_removing_full_trip_cannot_keep_all_guarantees_by_reusing_wing_results(self):
        c=next(c for c in self.r['cases'] if c.get('full_trip_count')==20)
        grid=timing_offsets(self.loops,c['first_wing'],c['intermediate_fs_departure_offset_min'])
        with self.assertRaises(ValueError):verify(grid,c['full_trip_departures_min'][1:],self.p,self.loops)

    def test_independently_reproduce_both_roots_minimum_not_overall_selected_winner(self):
        for first,offset in [('west_B',60),('east_A',55)]:
            rebuilt=solve_case(self.p,self.loops,first,offset)
            self.assertTrue(rebuilt['minimum_full_trip_count_proven'])
            self.assertEqual(rebuilt['full_trip_count'],20)
            self.assertFalse(rebuilt['operating_plan_adopted'])
        self.assertTrue(self.r['all_examined_case_minima_proven'])
        self.assertEqual(self.r['minimum_full_trip_count_in_examined_domain'],20)
        self.assertAlmostEqual(self.r['minimum_service_km_in_examined_domain'],143929.08351602656)

    def test_stop_choices_and_no_extra_budget_or_operating_claim(self):
        self.assertEqual(self.r['current_design_site_count_including_fs'],29)
        self.assertEqual(self.r['accepted_addition_ids'],['N1212'])
        self.assertEqual(self.r['rejected_addition_ids'],['N0655'])
        for k in ('annual_calendar_adopted','operating_plan_adopted','physical_passenger_continuity_certified',
                  'cross_terminal_passenger_continuation_certified','network_selected',
                  'primary_selection_authorised','runner_up_selection_authorised'):
            self.assertFalse(self.r[k])
        for k in ('decision_budget_km','uncertainty_band_min'):self.assertIsNone(self.r[k])

    def test_report_reproducible_and_old_count_explicitly_superseded(self):
        self.assertEqual(report(self.r),DOC.read_text(encoding='utf-8'))
        self.assertIn('non viene più presentata come soluzione finale',report(self.r))


if __name__=='__main__':unittest.main()
