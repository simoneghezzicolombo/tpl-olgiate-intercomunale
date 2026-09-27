import copy
import json
import unittest

from scripts.phase2_solve_rt031_line8_joint_evening_v3 import (
    BASE, LOCAL_SITES, document, events_by_site, family_inputs, occupied_sets,
    prepare, solve, verify,
)
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import EXPECTED, FLAGS, load_sources
from scripts.phase2_audit_rt031_line8_independent_wings_v3 import minimum_blocks
from scripts.phase2_export_rt031_line8_joint_evening_v3 import build as export_witness


class JointEveningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources()
        cls.families = {f['name']: f for f in family_inputs(cls.sources)}
        cls.result = json.loads((BASE / 'joint_evening_timetable.json').read_text(encoding='utf-8'))
        # Rebuild anchors and event times, not a second optimisation that could
        # pick a different tied optimum on another solver version.
        cls.problems = {(name, headway): prepare(family, headway, False)
                        for name, family in cls.families.items() for headway in (60, 90)}

    def test_complete_explicit_domain_and_nondecisional_sources(self):
        self.assertTrue(self.result['all_requested_comparisons_completed'])
        self.assertEqual(len(self.result['cases']), 8)
        self.assertEqual(self.result['source_sha256_normalized_newlines'], EXPECTED)
        self.assertEqual(len({(c['family_id'], c['offpeak_wait_comparison_min'], c['nominal_fleet_bound_comparison']) for c in self.result['cases']}), 8)
        self.assertFalse(document(self.result['cases'][:1])['all_requested_comparisons_completed'])
        for flag in (*FLAGS, 'actual_timetable_certified'):
            self.assertIs(self.result[flag], False)
        for field in ('decision_budget_km', 'uncertainty_band_min', 'total_operating_km', 'approved_uplift_percent'):
            self.assertIsNone(self.result[field])

    def test_all_witnesses_independently_recheck_frequencies_rail_fleet_and_cost(self):
        for case in self.result['cases']:
            if not case['witness_found']:
                self.assertFalse(case.get('continuous_grid_recheck_passed', False))
                continue
            problem = self.problems[case['family_id'], case['offpeak_wait_comparison_min']]
            grid = verify(problem, case['trips'], case['comparison_peak_windows'], case['nominal_fleet_bound_comparison'])
            self.assertEqual(grid, case['conditional_scenarios'])
            annual = sum(problem['family']['loops'][t['loop']]['distance_m'] for t in case['trips']) * .26
            self.assertAlmostEqual(annual, case['annual_service_km'], places=5)
            self.assertEqual(max(t['departure_min'] for t in case['trips']), 1240)
            self.assertEqual(len(grid), 27)
            if case['optimality_proven_in_this_domain']:
                self.assertEqual(case['solver_status'], 0)
                self.assertAlmostEqual(case['annual_service_km'], case['annual_service_km_lower_bound_in_domain'], places=3)
            if case['solver_status'] == 1:
                self.assertFalse(case['infeasibility_proven_in_this_domain'])
                self.assertFalse(case['optimality_proven_in_this_domain'])
            self.assertFalse(case['policy_adopted'])

    def test_occupation_exact_for_all_compatible_positive_duration_trips(self):
        loops = {'a': {'road_minutes': 20}, 'b': {'road_minutes': 30}}
        joins = {a + '>' + b: True for a in loops for b in loops}
        trips = [{'loop': 'a', 'departure_min': 0}, {'loop': 'b', 'departure_min': 0},
                 {'loop': 'a', 'departure_min': 25}, {'loop': 'a', 'departure_min': 35}]
        for recovery in (0, 5, 10, 15):
            bound = max(len(row) for row in occupied_sets(trips, loops, recovery))
            self.assertEqual(bound, minimum_blocks(trips, loops, joins, recovery)['minimum_vehicle_count_conditional'])
        bad = copy.deepcopy(self.families['original_priority_direction'])
        bad['joins']['west_A>east_B'] = False
        with self.assertRaisesRegex(ValueError, 'every represented FS join'):
            prepare(bad, 90, False)

    def test_local_frequency_does_not_use_early_long_ride_occurrence(self):
        sid = LOCAL_SITES[0]
        loops = {'west_A': {'events': [
            {'stop_place_id': sid, 'offset_from_wing_origin_min': 4},
            {'stop_place_id': sid, 'offset_from_wing_origin_min': 35}]}}
        opportunities = events_by_site([{'loop': 'west_A', 'departure_min': 400}], loops)
        self.assertEqual(opportunities[sid, 'to_fs'], [(0, 435)])
        self.assertEqual(opportunities[sid, 'from_fs'], [(0, 400)])
        case = next(c for c in self.result['cases'] if c['family_id'] == 'fast_local_both_directions'
                    and c['offpeak_wait_comparison_min'] == 90 and c['nominal_fleet_bound_comparison'] == 4)
        self.assertEqual(len(case['local_event_bindings_nominal']), 4)
        for binding in case['local_event_bindings_nominal']:
            self.assertLess(binding['to_fs_ride_min'], 4.4)
            self.assertLess(binding['from_fs_ride_min'], 4.4)
            self.assertNotEqual(binding['from_fs_alighting_occurrence_id'], binding['to_fs_boarding_occurrence_id'])
            self.assertFalse(binding['boarding_authorised'])

    def test_four_nominal_vehicle_witnesses_not_six_to_seven_necessity(self):
        for name, expected in (('original_priority_direction', 119084.270121), ('fast_local_both_directions', 129536.175164)):
            case = next(c for c in self.result['cases'] if c['family_id'] == name
                        and c['offpeak_wait_comparison_min'] == 90 and c['nominal_fleet_bound_comparison'] == 4)
            self.assertTrue(case['witness_found'])
            self.assertTrue(case['optimality_proven_in_this_domain'])
            self.assertAlmostEqual(case['annual_service_km'], expected, places=4)
            nominal = next(g for g in case['conditional_scenarios'] if (g['moving_multiplier'], g['dwell_min'], g['recovery_min']) == (1.1, .5, 10))
            self.assertLessEqual(nominal['minimum_vehicle_count_conditional'], 4)
            self.assertGreater(case['worst_grid_vehicle_count_conditional'], 4)

    def test_verifier_rejects_timetable_phase_and_uncompiled_solver_drift(self):
        case = next(c for c in self.result['cases'] if c['witness_found'])
        problem = self.problems[case['family_id'], case['offpeak_wait_comparison_min']]
        with self.assertRaises(ValueError):
            verify(problem, [], case['comparison_peak_windows'], case['nominal_fleet_bound_comparison'])
        phases = copy.deepcopy(case['comparison_peak_windows'])
        phases[0]['end_min'] -= 1
        with self.assertRaisesRegex(ValueError, 'phase outside declared domain'):
            verify(problem, case['trips'], phases, case['nominal_fleet_bound_comparison'])
        with self.assertRaisesRegex(ValueError, 'coverage constraints not compiled'):
            solve(problem, 4)
        bad = copy.deepcopy(self.sources)
        bad['wings']['network_selected'] = True
        with self.assertRaises(ValueError):
            family_inputs(bad)

    def test_exported_witness_ledger_and_exact_two_pattern_shape(self):
        shape = json.loads((BASE / 'local_counterflow.geojson').read_text(encoding='utf-8'))
        ledger, actual_shape = export_witness(self.result, self.sources, shape)
        committed = json.loads((BASE / 'joint_evening_witness.json').read_text(encoding='utf-8'))
        committed.pop('source_sha256_normalized_newlines')
        self.assertEqual(ledger, committed)
        self.assertEqual(actual_shape, json.loads((BASE / 'joint_evening_witness.geojson').read_text(encoding='utf-8')))
        self.assertEqual(len(ledger['trips']), 36)
        self.assertEqual(len(ledger['nonhub_sites']), 27)
        self.assertEqual(sum(s['site_status'] == 'NEW_SITE_NOT_APPROVED' for s in ledger['nonhub_sites']), 2)
        self.assertEqual({f['properties']['pattern'] for f in actual_shape['features'] if f['geometry']['type'] == 'LineString'}, {'west_B', 'east_A'})
        self.assertAlmostEqual(sum(t['service_km'] for t in ledger['trips']) * 260, ledger['annual_service_km'], places=5)
        self.assertTrue(all(not e['boarding_authorised'] and not e['passenger_continuity_certified'] for e in ledger['nominal_stop_occurrence_events']))


if __name__ == '__main__':
    unittest.main()
