import json
import math
import unittest

from scripts.phase2_audit_rt031_line8_robustness_cost_v3 import (
    BASE, EXPECTED, FLAGS, PROFILES, SPAN_IDS, SPANS, accounting, digest, stress_audit,
)
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import GRID, family_inputs, prepare, verify
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import load_sources


class RobustnessCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
        cls.result = json.loads((BASE / 'robustness_cost_diagnostic.json').read_text(encoding='utf-8'))

    def test_sources_completeness_and_no_decision(self):
        self.assertEqual(self.result['source_sha256_normalized_newlines'], {
            **EXPECTED, 'shorter_span': digest(BASE / 'shorter_span_comparison.json')})
        self.assertTrue(self.result['all_comparisons_completed'])
        self.assertEqual(len(self.result['cases']), 6)
        self.assertEqual({(c['profile_id'], c['span_comparison_id']) for c in self.result['cases']},
                         {(p, s) for p in PROFILES for s in SPAN_IDS})
        for key in (*FLAGS, 'actual_timetable_certified'):
            self.assertIs(self.result[key], False)
        for key in ('decision_budget_km', 'uncertainty_band_min', 'approved_uplift_percent', 'total_operating_km'):
            self.assertIsNone(self.result[key])

    def test_default_grid_unchanged_and_invalid_subsets_rejected(self):
        self.assertEqual(prepare(self.family, 60, False)['timing_grid'], GRID)
        for grid in ([], [(1., .5)], [(1.1, .5)] * 2, [(1.1, .5), (1.2, .5)]):
            with self.assertRaisesRegex(ValueError, 'invalid timing comparison grid'):
                prepare(self.family, 60, False, timing_grid=grid)
        with self.assertRaisesRegex(ValueError, 'explicit unchanged AM'):
            prepare(self.family, 60, False, timing_grid=PROFILES['nominal_only'])

    def test_all_witnesses_recheck_with_frozen_ceiling_and_original_stress(self):
        for case in self.result['cases']:
            spec = SPANS[case['span_comparison_id']]
            kwargs = dict(ready_span=(390, spec['end_min']), pm_arrivals=spec['pm_arrivals'])
            full = prepare(self.family, 60, False, **kwargs)
            problem = prepare(self.family, 60, False, **kwargs,
                              timing_grid=PROFILES[case['profile_id']],
                              am_wait_ceiling_comparison_min=full['wait_ceiling'])
            self.assertEqual(case['timing_grid_comparison'], [list(p) for p in PROFILES[case['profile_id']]])
            self.assertAlmostEqual(case['am_residual_wait_ceiling_inherited_comparison_min'], full['wait_ceiling'])
            self.assertFalse(case['policy_adopted'])
            if not case['witness_found']:
                self.assertFalse(case['optimality_proven_in_this_domain'])
                continue
            verify(problem, case['trips'], case['comparison_peak_windows'], 4)
            self.assertEqual(stress_audit(full, case), case['full_grid_frequency_and_rail_audit'])
            if case['passes_full_reference_contract']:
                verify(full, case['trips'], case['comparison_peak_windows'], 4)
            else:
                with self.assertRaises(ValueError):
                    verify(full, case['trips'], case['comparison_peak_windows'], 4)
            if case['profile_id'] == 'full_grid':
                self.assertTrue(case['passes_full_reference_contract'])
            daily = sum(self.family['loops'][t['loop']]['distance_m'] / 1000 for t in case['trips'])
            self.assertEqual(accounting(daily), case['service_day_accounting'])
            self.assertAlmostEqual(daily * 260, case['annual_service_km'], places=5)
            if case['optimality_proven_in_this_domain']:
                self.assertAlmostEqual(case['annual_service_km'], case['annual_service_km_lower_bound_in_domain'], places=3)

    def test_calendar_is_arithmetic_not_an_approved_weekend_cut(self):
        for daily in (400, 500, 600):
            result = accounting(daily)
            days = result['maximum_whole_identical_service_days_within_reference']
            self.assertLessEqual(days * daily, 111419)
            self.assertGreater((days + 1) * daily, 111419)
            self.assertFalse(result['calendar_adopted'])
            self.assertIsNone(result['actual_weekend_days_in_calendar'])
        for daily in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                accounting(daily)


if __name__ == '__main__':
    unittest.main()
