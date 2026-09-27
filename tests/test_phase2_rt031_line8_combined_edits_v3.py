import copy
from fractions import Fraction
import json
import unittest
from types import SimpleNamespace

import numpy as np

from scripts.phase2_bound_rt031_line8_combined_edits_v3 import (
    OUTPUT as WEAK, relaxed_problem, verify_relaxed, solve_bound, summarize,
)
from scripts.phase2_bound_rt031_line8_combined_timing_v3 import (
    OUTPUT as BOUNDS, BASE, SCREEN, RETENTION, choices, groups, signature, document, GRID,
)
from scripts.phase2_check_rt031_line8_combined_edits_v3 import (
    OUTPUT as JOINT, diagnostic_pairs, combine_family, combined_access,
)
from scripts.phase2_export_rt031_line8_combined_edits_v3 import close, report, DOC
from scripts.phase2_check_rt031_line8_relocation_timetable_v3 import sha, PEAKS
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, verify
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS


class CombinedEditsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.screen = json.loads(SCREEN.read_text(encoding='utf-8'))
        cls.retention = json.loads(RETENTION.read_text(encoding='utf-8'))
        cls.weak = json.loads(WEAK.read_text(encoding='utf-8'))
        cls.bounds = json.loads(BOUNDS.read_text(encoding='utf-8'))
        cls.joint = json.loads(JOINT.read_text(encoding='utf-8'))
        cls.pool = choices(cls.screen, cls.retention)
        cls.groups = groups(cls.pool)
        cls.lookup = {c['choice_id']: c for cs in cls.pool.values() for c in cs}
        cls.reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
        cls.ceiling = cls.bounds['frozen_reference_am_wait_ceiling_comparison_min']

    def test_full_choice_domain_and_exact_timing_equivalence_not_spatial_merging(self):
        self.assertEqual({w: len(c) for w, c in self.pool.items()}, {'west': 285, 'east': 426})
        self.assertEqual(self.bounds['combination_count'], 121410)
        self.assertEqual(len(self.groups), 41)
        members = [cid for g in self.bounds['groups'] for cid in g['choice_ids']]
        self.assertEqual(len(members), len(set(members)))
        self.assertEqual(set(members), set(self.lookup))
        for g in self.bounds['groups']:
            self.assertEqual(g['choice_ids'], self.groups[g['group_id']]['choice_ids'])
            for cid in g['choice_ids']:
                self.assertEqual(signature(self.lookup[cid], g['wing']), g['group_id'])
        self.assertEqual(self.bounds, document(self.bounds['groups'], self.screen, self.retention, self.ceiling))

    def test_all_41_bounds_reproduced_by_integer_optimisation(self):
        for g in self.bounds['groups']:
            choice = self.lookup[g['representative_choice_id']]
            p = relaxed_problem(choice, g['wing'], self.ceiling, GRID)
            verify_relaxed(p, g['relaxed_dispatches_not_timetable'])
            recalculated = solve_bound(choice, g['wing'], self.ceiling, GRID)
            with self.subTest(group=g['group_id']):
                self.assertTrue(recalculated['optimality_proven_in_relaxed_domain'])
                self.assertAlmostEqual(recalculated['annual_service_km_lower_bound'], g['annual_service_km_lower_bound'], places=4)
        self.assertTrue(self.bounds['all_reference_cap_excluded'])
        self.assertAlmostEqual(self.bounds['minimum_annual_service_km_lower_bound'], 121340.751423, places=5)

    def test_weaker_bound_covers_every_road_pair_and_is_never_stronger(self):
        self.assertEqual(self.weak, summarize(self.weak['wing_relaxations'], self.retention, self.screen, self.ceiling))
        self.assertEqual(self.weak['road_variant_pair_count'], 616)
        self.assertEqual(self.weak['relocation_choice_pair_count'], 121410)
        self.assertAlmostEqual(self.weak['minimum_lower_bound'], 111852.616046, places=5)
        weak_by_variant = {r['variant_id']: r for r in self.weak['wing_relaxations']}
        for g in self.bounds['groups']:
            variant_id = self.lookup[g['representative_choice_id']]['variant_id']
            self.assertLessEqual(weak_by_variant[variant_id]['annual_service_km_lower_bound'], g['annual_service_km_lower_bound'] + 1e-5)

    def test_all_four_full_witnesses_match_lower_bound_and_declared_site_sets(self):
        expected = set(diagnostic_pairs(self.bounds, self.pool))
        self.assertEqual(expected, {(c['west_choice_id'], c['east_choice_id']) for c in self.joint['cases']})
        self.assertEqual(len(expected), 4)
        for c in self.joint['cases']:
            family = combine_family(self.reference, self.lookup[c['west_choice_id']], self.lookup[c['east_choice_id']])
            self.assertEqual(c['served_nonhub_site_ids'], family['comparison_nonhub_site_ids'])
            p = prepare(family, 60, False, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'],
                        am_wait_ceiling_comparison_min=self.ceiling)
            self.assertEqual(verify(p, c['trips'], c['comparison_peak_windows'], 4), c['conditional_scenarios'])
            self.assertAlmostEqual(c['annual_service_km'], self.bounds['minimum_annual_service_km_lower_bound'], places=5)
            self.assertEqual(len(c['trips']), 39)
            self.assertEqual(c['worst_grid_vehicle_count_conditional'], 5)
            for wing in ('west', 'east'):
                variant = self.lookup[c[wing + '_choice_id']]
                relaxed = relaxed_problem(variant, wing, self.ceiling, GRID)
                verify_relaxed(relaxed, [t for t in c['trips'] if t['loop'].startswith(wing)])

    def test_explicit_footprint_and_missing_trips_fail_closed(self):
        c = self.joint['cases'][0]
        family = combine_family(self.reference, self.lookup[c['west_choice_id']], self.lookup[c['east_choice_id']])
        bad = copy.deepcopy(family)
        bad['comparison_nonhub_site_ids'] = bad['comparison_nonhub_site_ids'][:-1]
        with self.assertRaisesRegex(ValueError, 'declared comparison site domain drift'):
            prepare(bad, 60, False)
        bad = copy.deepcopy(family)
        bad.pop('comparison_nonhub_site_ids')
        with self.assertRaisesRegex(ValueError, 'site domain drift'):
            prepare(bad, 60, False)

    def test_joint_access_is_vector_union_not_added_percentages(self):
        from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import FS, MUNICIPALITY_NAMES, ratios
        codes = list(MUNICIPALITY_NAMES)
        n = 2 * len(codes)
        matrix = np.array([[np.inf, 4. if i % 2 == 0 else 12., 12. if i % 2 == 0 else 4.] for i in range(n)])
        ctx = {'substrate': SimpleNamespace(stop_index={FS: 0, 'west': 1, 'east': 2}, walk_time_matrix=matrix),
               'local': np.full(n, np.inf), 'weights': [1] * n, 'core': np.ones(n, dtype=bool),
               'codes': np.array([code for code in codes for _ in (0, 1)])}
        family = {'loops': {'w': {'events': [{'stop_place_id': 'west'}]}, 'e': {'events': [{'stop_place_id': 'east'}]}}}
        actual = combined_access(family, ctx, {}, np.full(n, 4.))
        self.assertEqual(Fraction(actual['potential_access_fraction']['TOTAL']['5']), 1)
        self.assertTrue(actual['no_previously_covered_units_lost'])
        self.assertEqual(Fraction(actual['previously_covered_population_fraction_lost']['TOTAL']['5']), 0)
        # Separate removal of either wing loses half; removing both loses all.
        # Overlap/union must be resolved on population units before aggregation.
        overlap = {'loops': {'w': {'events': [{'stop_place_id': 'west'}]}, 'e': {'events': [{'stop_place_id': 'west'}]}}}
        actual = combined_access(overlap, ctx, {}, np.full(n, 4.))
        self.assertEqual(Fraction(actual['potential_access_fraction']['TOTAL']['5']), Fraction(1, 2))

    def test_finite_closure_report_no_authorisation_and_shapes(self):
        closure = close(self.bounds, self.joint, self.pool, self.reference)
        self.assertEqual(closure, json.loads((BASE / 'combined_edits_closure.json').read_text(encoding='utf-8')))
        self.assertEqual(report(closure, self.joint), DOC.read_text(encoding='utf-8'))
        self.assertTrue(closure['finite_domain_minimum_proven'])
        self.assertFalse(closure['all_territorial_requirements_met'])
        self.assertTrue(all(not closure[k] for k in FLAGS))
        self.assertIsNone(closure['decision_budget_km'])
        bad = copy.deepcopy(self.bounds)
        bad['minimum_annual_service_km_lower_bound'] -= 100
        with self.assertRaisesRegex(ValueError, 'lower bound not attained'):
            close(bad, self.joint, self.pool, self.reference)
        shape = json.loads((BASE / 'combined_edits_diagnostic.geojson').read_text(encoding='utf-8'))
        self.assertEqual({f['properties']['pattern'] for f in shape['features'] if f['geometry']['type'] == 'LineString'}, {'west_B', 'east_A'})
        self.assertEqual(sum(f['geometry']['type'] == 'Point' and f['properties']['lost'] for f in shape['features']), 4)


if __name__ == '__main__':
    unittest.main()
