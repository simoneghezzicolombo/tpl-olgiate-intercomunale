import copy
import hashlib
import json
import unittest

from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS, document, validate_rail
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import BASE, FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, verify
from scripts.phase2_export_rt031_line8_joint_evening_v3 import build as export_witness


class ShorterSpanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources()
        cls.family = next(f for f in family_inputs(cls.sources) if f['name'] == 'fast_local_both_directions')
        cls.result = json.loads((BASE / 'shorter_span_comparison.json').read_text(encoding='utf-8'))

    def test_all_nine_comparisons_and_source_provenance(self):
        self.assertTrue(self.result['all_comparisons_completed'])
        self.assertEqual(len(self.result['cases']), 9)
        self.assertFalse(document(self.result['cases'][:1], 'test')['all_comparisons_completed'])
        source_hash = hashlib.sha256((BASE / 'joint_evening_timetable.json').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        self.assertEqual(source_hash, self.result['source_sha256_normalized_newlines']['joint_reference'])
        validate_rail(self.sources)
        bad = copy.deepcopy(self.sources)
        bad['rail'] = [r for r in bad['rail'] if not (r['direction'] == 'LECCO' and float(r['arrival_min']) == 1202)]
        with self.assertRaisesRegex(ValueError, 'absent from frozen rail'):
            validate_rail(bad)

    def test_independent_event_rail_and_fleet_recheck_all_cases(self):
        for case in self.result['cases']:
            self.assertEqual(case['h120_boundary_relaxation_only'], case['offpeak_wait_comparison_min'] == 120)
            self.assertFalse(case['user_approval_recorded'])
            spec = SPANS[case['span_comparison_id']]
            problem = prepare(self.family, case['offpeak_wait_comparison_min'], False,
                              ready_span=(390, spec['end_min']), pm_arrivals=spec['pm_arrivals'])
            grid = verify(problem, case['trips'], case['comparison_peak_windows'], 4)
            self.assertEqual(grid, case['conditional_scenarios'])
            self.assertEqual(case['last_actual_fs_departure_min'], spec['end_min'])
            self.assertEqual(case['ready_span_comparison_min'], [390, spec['end_min']])
            self.assertEqual(case['declared_pm_rail_arrival_targets_min'], list(spec['pm_arrivals']))
            self.assertEqual(len({e['stop_place_id'] for loop in problem['family']['loops'].values() for e in loop['events']}), 27)
            self.assertTrue(case['morning_targets_unchanged'])
            self.assertTrue(case['geography_unchanged'])
            self.assertTrue(case['optimality_proven_in_this_domain'])
            self.assertAlmostEqual(case['annual_service_km'], case['annual_service_km_lower_bound_in_domain'], places=3)

    def test_shorter_span_cannot_silently_drop_the_late_train(self):
        with self.assertRaisesRegex(ValueError, 'empty rail anchor domain'):
            prepare(self.family, 90, False, ready_span=(390, 1180))
        for case in self.result['cases']:
            sid = case['span_comparison_id']
            self.assertEqual(case['reference_pm_targets_not_retained_min'], [] if sid.endswith('reference') else [1232])
            self.assertEqual(case['replacement_pm_targets_min'], [1202] if sid == 'last_fs_2010' else [])

    def test_half_hour_less_does_not_manufacture_km_saving(self):
        cases = {(c['span_comparison_id'], c['offpeak_wait_comparison_min']): c for c in self.result['cases']}
        full = cases['last_fs_2040_reference', 90]
        half = cases['last_fs_2010', 90]
        short = cases['last_fs_1940', 90]
        self.assertEqual(full['annual_service_km'], half['annual_service_km'])
        self.assertEqual(full['daily_trip_count'], 36)
        self.assertEqual(short['daily_trip_count'], 34)
        self.assertAlmostEqual(short['annual_service_km'], 122339.720989, places=5)
        pair_cost = sum(self.family['loops'][p]['distance_m'] for p in ('west_B', 'east_A')) * .26
        self.assertAlmostEqual(full['annual_service_km'] - short['annual_service_km'], pair_cost, places=5)
        self.assertEqual(short['worst_grid_vehicle_count_conditional'], 5)
        self.assertTrue(all(c['annual_service_km'] > 111419 for c in cases.values()
                            if c['offpeak_wait_comparison_min'] in (60, 90)))

    def test_labelled_short_witness_has_exact_34_trip_ledger_and_same_shape(self):
        shape = json.loads((BASE / 'local_counterflow.geojson').read_text(encoding='utf-8'))
        ledger, derived_shape = export_witness(self.result, self.sources, shape, 'last_fs_1940')
        committed = json.loads((BASE / 'shorter_span_1940_witness.json').read_text(encoding='utf-8'))
        source_hash = hashlib.sha256((BASE / 'shorter_span_comparison.json').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        self.assertEqual(committed['source_sha256_normalized_newlines']['joint_search'], source_hash)
        committed.pop('source_sha256_normalized_newlines')
        self.assertEqual(ledger, committed)
        self.assertEqual(len(ledger['trips']), 34)
        self.assertAlmostEqual(sum(t['service_km'] for t in ledger['trips']) * 260, 122339.720989, places=5)
        self.assertEqual(derived_shape, json.loads((BASE / 'joint_evening_witness.geojson').read_text(encoding='utf-8')))
        self.assertEqual(ledger['reference_pm_targets_not_retained_min'], [1232])

    def test_h120_boundary_does_not_gain_by_shifting_the_comparison_peaks(self):
        h90 = next(c for c in self.result['cases'] if c['span_comparison_id'] == 'last_fs_1940' and c['offpeak_wait_comparison_min'] == 90)
        h120 = next(c for c in self.result['cases'] if c['span_comparison_id'] == 'last_fs_1940' and c['offpeak_wait_comparison_min'] == 120)
        self.assertEqual(h120['comparison_peak_windows'], h90['comparison_peak_windows'])
        self.assertTrue(h120['also_optimal_in_unrestricted_phase_domain'])
        self.assertEqual(h120['annual_service_km'], h120['unrestricted_phase_lower_bound_km'])
        self.assertAlmostEqual(h120['annual_service_km'], 115143.266813, places=5)
        self.assertEqual(h120['daily_trip_count'], 32)
        self.assertEqual(h120['first_actual_fs_departure_min'], 390)
        self.assertEqual(h120['worst_grid_vehicle_count_conditional'], 6)
        self.assertGreater(h120['annual_service_km'], 111419)

    def test_decision_contract_unchanged(self):
        for flag in (*FLAGS, 'actual_timetable_certified'):
            self.assertIs(self.result[flag], False)
        for field in ('decision_budget_km', 'uncertainty_band_min', 'approved_uplift_percent', 'total_operating_km'):
            self.assertIsNone(self.result[field])
        self.assertEqual(self.result['reference_cap_unchanged'], 111419)
        self.assertEqual(self.result['annual_service_days_assumption'], 260)


if __name__ == '__main__':
    unittest.main()
