import copy
import json
import unittest

from scripts.phase2_close_rt031_line8_16_full_trips_v3 import (
    AUTH, DOC, BASE, authority, read_result, inputs, source_fingerprints,
    digest, solve_case, verify, report, timing_offsets, staggered_rail_inputs)


class SixteenFullTripsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = read_result()
        _, cls.p, _, _, cls.loops = inputs()
        cls.examples = [c for c in cls.r['cases'] if c['offpeak_comparison'] == 215 and c['witness_found']]

    def test_scoped_authority_and_sources(self):
        a = authority()
        self.assertEqual(a['full_commercial_trips_per_day_adopted'], 16)
        self.assertEqual(self.r['authority_sha256'], digest(AUTH))
        self.assertEqual(self.r['parent_sources'], source_fingerprints(self.p, self.loops))
        self.assertEqual(self.r['accepted_addition_ids'], ['N1212'])
        self.assertEqual(self.r['rejected_addition_ids'], ['N0655'])
        self.assertEqual(self.r['current_design_site_count'], 29)
        self.assertFalse(a['exact_peak_phases_or_connection_wait_changes_adopted'])

    def test_exact_production_is_16_complete_eights_not_16_wings(self):
        km = 16*260*sum(l['distance_m'] for l in self.loops.values())/1000
        self.assertAlmostEqual(self.r['annual_service_km'], km)
        self.assertAlmostEqual(km, 115143.26681282124)
        for c in self.examples:
            self.assertEqual(c['full_trip_count'], 16)
            self.assertEqual(len(c['full_trip_departures_min']), 16)
            self.assertAlmostEqual(c['annual_service_km'], km)
        self.assertTrue(self.r['all_trips_same_complete_path_within_each_comparison'])
        self.assertFalse(self.r['comparisons_mix_different_roots_in_one_timetable'])

    def test_all_cases_replay_and_no_rail_target_disappears(self):
        self.assertEqual(len(self.r['cases']), 42)
        self.assertEqual(self.r['unique_train_wing_targets'], 22)
        for c in self.r['cases']:
            if c['witness_found']:
                self.assertEqual(c['verification'], verify(self.p, self.loops, c))
                self.assertEqual(len(c['verification']['rail_bindings']), 308)
                self.assertEqual(len(c['verification']['all_27_resource_cases']), 27)
                self.assertEqual(c['am_residual_wait_ceiling_min'], self.p['wait_ceiling'])
                self.assertEqual(c['pm_train_to_bus_ceiling_min'], 8)

    def test_true_h30_at_each_fixed_event_not_common_clock_claim(self):
        for c in self.examples:
            grid = timing_offsets(self.loops, c['first_wing'], c['midpoint_departure_offset_min'])
            for g in grid.values():
                for row in g['sites'].values():
                    for direction in ('to_fs', 'from_fs'):
                        for bank in c['peak_banks']:
                            times = [t+row[direction] for t in bank['departures_min']]
                            self.assertTrue(all(abs(b-a-30) < 1e-8 for a,b in zip(times,times[1:])))
            self.assertFalse(c['verification']['all_site_common_clock_legacy_peak_windows_certified'])
            self.assertFalse(c['verification']['independent_trip_delays_certified'])

    def test_215_gap_is_exposed_not_mislabelled_h120(self):
        self.assertTrue(self.examples)
        for c in self.examples:
            self.assertEqual(c['verification']['maximum_consecutive_opportunity_gap_min'], 215)
            tightened = copy.deepcopy(c)
            tightened['offpeak_comparison'] = 'inherited'
            with self.assertRaisesRegex(ValueError, 'gap'):
                verify(self.p, self.loops, tightened)
        self.assertFalse(self.r['offpeak_215_minutes_adopted'])

    def test_both_symmetric_120_minute_diagnostics_and_exact_rail_substitutions(self):
        cases = self.r['staggered_120_minute_diagnostics']
        self.assertEqual(len(cases), 2)
        self.assertEqual({c['first_wing'] for c in cases}, {'west_B', 'east_A'})
        for c in cases:
            delayed = 'east' if c['first_wing'] == 'west_B' else 'west'
            q, substitutions = staggered_rail_inputs(self.p, delayed)
            self.assertEqual(c['rail_target_substitutions_not_adopted'], substitutions)
            self.assertEqual(c['verification'], verify(q, self.loops, c))
            self.assertEqual(len(c['verification']['rail_bindings']), 308)
            self.assertEqual(c['verification']['maximum_consecutive_opportunity_gap_min'], 120)
            self.assertEqual(c['full_trip_count'], 16)
            self.assertEqual(len(c['full_trip_stop_event_ledger_nominal']), 16)
            for trip in c['full_trip_stop_event_ledger_nominal']:
                roles = [e['role'] for e in trip['events']]
                self.assertEqual(roles[0], 'FULL_TRIP_START_AT_FS')
                self.assertEqual(roles[-1], 'FULL_TRIP_END_AT_FS')
                self.assertEqual(roles.count('INTERMEDIATE_FS_PUBLIC_STOP_STAY_ONBOARD_DESIGN'), 1)
                self.assertEqual(len({e['site_id'] for e in trip['events'] if
                                      e['role'] == 'DESIGN_STOP_OCCURRENCE'}), 28)
                self.assertFalse(any(e.get('boarding_authorised') for e in trip['events']))
            self.assertEqual(len(c['rail_assignments']), 22)
            self.assertFalse(c['original_22_train_targets_all_retained'])
            self.assertTrue(c['new_22_train_target_bindings_verified'])
            self.assertEqual(c['ready_service_start_min_not_adopted'], 420)
            self.assertTrue(c['verification']['actual_five_core_train_bound_trips_h30_each_wing_am_and_pm'])
            with self.assertRaisesRegex(ValueError, 'target dropped'):
                verify(self.p, self.loops, c)
        self.assertFalse(self.r['staggered_comparisons_adopted'])
        self.assertFalse(self.r['staggered_ready_start_07_accepted'])

    def test_refined_115_minute_examples_and_finite_lower_bounds(self):
        cases = self.r['refined_115_minute_diagnostics']
        self.assertEqual(len(cases), 2)
        self.assertEqual(len(self.r['shifted_start_0630_cap120_all_14_offsets_infeasible']), 14)
        self.assertEqual(len(self.r['shifted_cap110_all_14_offsets_infeasible']), 14)
        self.assertTrue(all(c['infeasibility_proven'] for c in
                            self.r['shifted_start_0630_cap120_all_14_offsets_infeasible'] +
                            self.r['shifted_cap110_all_14_offsets_infeasible']))
        self.assertEqual({c['first_wing']: c['ready_service_start_min_not_adopted'] for c in cases},
                         {'west_B': 405, 'east_A': 410})
        for c in cases:
            delayed = 'east' if c['first_wing'] == 'west_B' else 'west'
            q, replacements = staggered_rail_inputs(self.p, delayed)
            self.assertEqual(c['rail_target_substitutions_not_adopted'], replacements)
            self.assertEqual(c['verification'], verify(q, self.loops, c))
            self.assertEqual(c['verification']['maximum_consecutive_opportunity_gap_min'], 115)
            self.assertEqual(len(c['verification']['rail_bindings']), 308)
            self.assertEqual(c['full_trip_count'], 16)
            self.assertEqual(len(c['full_trip_stop_event_ledger_nominal']), 16)
            self.assertFalse(c['original_22_train_targets_all_retained'])
            self.assertEqual(c['annual_service_km'], self.r['annual_service_km'])
        self.assertFalse(self.r['refined_diagnostics_adopted'])

    def test_both_roots_210_infeasible_215_constructive_independent_rerun(self):
        for first, midpoint in [('west_B', 60), ('east_A', 55)]:
            no = solve_case(self.p, self.loops, first, midpoint, self.p['wait_ceiling'], 8, 210, 16)
            yes = solve_case(self.p, self.loops, first, midpoint, self.p['wait_ceiling'], 8, 215, 16)
            self.assertTrue(no['infeasibility_proven'])
            self.assertTrue(yes['witness_found'])
        self.assertTrue(self.r['all_examined_16_trip_210_minute_cases_infeasible'])
        self.assertTrue(self.r['all_inherited_offpeak_minima_proven'])
        self.assertEqual(self.r['minimum_full_count_with_h30_banks_and_inherited_offpeak'], 18)

    def test_deleting_trip_or_train_fails_closed(self):
        original = self.examples[0]
        c = copy.deepcopy(original)
        c['full_trip_departures_min'].pop()
        with self.assertRaises(ValueError):
            verify(self.p, self.loops, c)
        c = copy.deepcopy(original)
        c['full_trip_stop_event_ledger_nominal'][0]['events'].pop(1)
        with self.assertRaisesRegex(ValueError, 'ledger drift'):
            verify(self.p, self.loops, c)
        c = copy.deepcopy(original)
        c['rail_assignments'].pop()
        with self.assertRaisesRegex(ValueError, 'target dropped'):
            verify(self.p, self.loops, c)
        c = copy.deepcopy(original)
        c['rail_assignments'].append(copy.deepcopy(c['rail_assignments'][0]))
        with self.assertRaises(ValueError):
            verify(self.p, self.loops, c)

    def test_boundary_and_midpoint_do_not_disappear(self):
        for c in self.examples:
            v = c['verification']
            self.assertGreater(v['last_full_arrival_nominal_min'], v['last_full_departure_min'])
            self.assertGreater(v['nominal_intermediate_fs_wait_min'], 0)
            self.assertFalse(v['operating_authorised'])

    def test_no_automatic_operating_or_preference_selection(self):
        for key in ('annual_calendar_adopted', 'geometry_changed', 'detailed_timetable_adopted',
                    'h30_phase_changes_adopted', 'new_fleet_increase_accepted',
                    'staggered_comparisons_adopted', 'staggered_ready_start_07_accepted',
                    'refined_diagnostics_adopted',
                    'physical_passenger_continuity_certified', 'operating_plan_adopted',
                    'network_selected', 'primary_selection_authorised', 'runner_up_selection_authorised'):
            self.assertFalse(self.r[key], key)
        for key in ('decision_budget_km', 'uncertainty_band_min'):
            self.assertIsNone(self.r[key])

    def test_current_readiness_and_generated_report(self):
        status = json.loads((BASE/'proposal_readiness.json').read_text(encoding='utf-8'))
        self.assertEqual(status['current_caller_service_authority'], 'config/rt031_16_full_trips_authority_v3.json')
        self.assertIsNone(status['current_design_proposal'])
        self.assertEqual(DOC.read_text(encoding='utf-8'), report(self.r))
        self.assertIn('non è stato accettato', report(self.r))


if __name__ == '__main__':
    unittest.main()
