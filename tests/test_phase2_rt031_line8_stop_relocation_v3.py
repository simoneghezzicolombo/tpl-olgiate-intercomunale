import copy
from fractions import Fraction
import json
import unittest

import numpy as np

from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import (
    BASE, OUTPUT as SCREEN, RETENTION, bypass_nodes, add_stop, shortlist, ratios, lost_ratios, validate_paths,
)
from scripts.phase2_check_rt031_line8_relocation_timetable_v3 import OUTPUT as TIMETABLE, materialize, sha, PEAKS
from scripts.phase2_export_rt031_line8_stop_relocation_v3 import DOC, frontier, report
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, load_sources
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs, prepare, verify
from scripts.phase2_compare_rt031_line8_shorter_span_v3 import SPANS


class RelocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.screen = json.loads(SCREEN.read_text(encoding='utf-8'))
        cls.retention = json.loads(RETENTION.read_text(encoding='utf-8'))
        cls.timetable = json.loads(TIMETABLE.read_text(encoding='utf-8'))
        cls.reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')

    def test_complete_bounded_domain_and_no_duplicate_new_inventory_site(self):
        screen = self.screen
        self.assertEqual(screen['source_sha256_normalized_retention'], sha(RETENTION))
        self.assertEqual(screen['case_count'], 709)
        self.assertEqual(screen['candidate_node_count'], 281)
        expected = set()
        for wing, variants in screen['candidate_nodes_by_variant'].items():
            for vid, nodes in variants.items():
                expected.add(vid + '__no_new_stop')
                expected.update(vid + '__node_' + n for n in nodes)
        self.assertEqual(expected, {c['case_id'] for c in screen['cases']})
        self.assertEqual(len(expected), len(screen['cases']))
        self.assertEqual(screen['diagnostic_summary'], shortlist(screen['cases']))
        self.assertTrue(all(not screen[k] for k in FLAGS))
        self.assertTrue(all(c['annual_service_km'] is None and not c['timetable_validated'] for c in screen['cases']))

    def test_stored_coverage_flags_and_gross_losses_are_consistent(self):
        baseline = self.screen['baseline_potential_access_fraction']
        for c in self.screen['cases']:
            good = all(Fraction(c['potential_access_fraction'][m][t]) >= Fraction(baseline[m][t])
                       for m in self.screen['municipality_names'] for t in ('5', '8', '10'))
            self.assertEqual(good, c['all_15_municipal_access_metrics_nonworse'])
            if c['no_previously_covered_units_lost']:
                self.assertTrue(good)
                self.assertTrue(all(Fraction(v) == 0 for row in c['previously_covered_population_fraction_lost'].values() for v in row.values()))
            for m, row in c['potential_access_fraction'].items():
                for t, value in row.items():
                    self.assertAlmostEqual(c['potential_access_change_pp'][m][t], 100 * float(Fraction(value) - Fraction(baseline[m][t])))

    def test_equal_aggregate_access_cannot_hide_changed_people(self):
        codes = list(self.screen['municipality_names'])
        ctx = {'codes': np.array([code for code in codes for _ in (0, 1)]),
               'core': np.ones(10, dtype=bool), 'weights': [1] * 10}
        before, after = np.array([4., 12.] * 5), np.array([12., 4.] * 5)
        self.assertEqual(ratios(before, ctx), ratios(after, ctx))
        lost = lost_ratios(before, after, ctx)
        self.assertEqual(Fraction(lost['TOTAL']['10']), Fraction(1, 2))

    def test_new_stop_is_an_actual_ordered_event_not_a_synthetic_shortcut(self):
        edges = {'a': {'v_node_id': 'new', 'running_minutes_model': '2'},
                 'b': {'v_node_id': 'fs', 'running_minutes_model': '3'}}
        loop = {'edge_ids': ['a', 'b'], 'events': [], 'distance_m': 100., 'road_minutes': 5.}
        changed = add_stop({'west_A': loop, 'west_B': loop}, 'new', edges)
        self.assertEqual(loop['events'], [])
        for p, item in changed.items():
            self.assertEqual(item['edge_ids'], loop['edge_ids'])
            self.assertEqual(item['distance_m'], loop['distance_m'])
            self.assertEqual(item['events'][0]['offset_from_wing_origin_min'], 2.)
            self.assertEqual(item['events'][0]['occurrence_id'], f'{p}:1:PROXY::RELOCATION_NODE_new')
            self.assertFalse(item['events'][0]['boarding_authorised'])
        with self.assertRaises(ValueError):
            add_stop({'west_A': loop}, 'absent', edges)

    def test_already_served_bypass_node_not_in_new_stop_pool(self):
        edges = {e: {'v_node_id': e} for e in ('fs', 'old', 'new', 'inventory')}
        base = {'edge_ids': ['old', 'fs'], 'events': []}
        alternate = {'edge_ids': ['new', 'inventory', 'fs'], 'events': [{'incoming_edge': 'inventory'}]}
        variants = [{'variant_id': 'base', 'loops': {'A': base, 'B': base}},
                    {'variant_id': 'alt', 'loops': {'A': alternate, 'B': alternate}}]
        self.assertEqual(bypass_nodes(variants, edges), {'alt': ['new']})

    def test_inherited_paths_rechecked_before_new_access_claims(self):
        from types import SimpleNamespace
        edges = {'a': {'u_node_id': 'fs', 'v_node_id': 's', 'length_m': '30', 'running_minutes_model': '2'},
                 'b': {'u_node_id': 's', 'v_node_id': 'fs', 'length_m': '40', 'running_minutes_model': '3'}}
        variants = {'west': [{'loops': {'west_A': {'edge_ids': ['a', 'b'], 'distance_m': 70., 'road_minutes': 5.,
            'events': [{'incoming_edge': 'a', 'path_node_index': 1, 'offset_from_wing_origin_min': 2.}]}}}]}
        adapter = SimpleNamespace(decision=lambda a, b: {'allowed': True})
        validate_paths(variants, edges, adapter, 'fs')
        broken = copy.deepcopy(variants)
        broken['west'][0]['loops']['west_A']['distance_m'] = 65.
        with self.assertRaisesRegex(ValueError, 'distance mismatch'):
            validate_paths(broken, edges, adapter, 'fs')
        with self.assertRaisesRegex(ValueError, 'forbidden represented turn'):
            validate_paths(variants, edges, SimpleNamespace(decision=lambda a, b: {'allowed': False}), 'fs')

    def test_all_six_timetables_with_frozen_reference_wait_and_real_occurrences(self):
        self.assertEqual(self.timetable['source_sha256_normalized_newlines'], {'screen': sha(SCREEN), 'retention': sha(RETENTION)})
        source_cases = {c['case_id']: c for c in self.screen['cases']}
        zero_loss = {c['case_id'] for c in self.screen['cases'] if c['direction_pair_m_saved'] > 1e-6 and c['no_previously_covered_units_lost']}
        self.assertEqual(set(self.timetable['diagnostic_case_ids']), zero_loss)
        self.assertEqual(len(self.timetable['cases']), 6)
        base = prepare(self.reference, 60, False, ready_span=(390, 1180), pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'])
        ceiling = base['wait_ceiling']
        self.assertEqual(ceiling, self.timetable['frozen_reference_am_wait_ceiling_comparison_min'])
        for c in self.timetable['cases']:
            family = materialize(self.reference, self.retention, source_cases[c['relocation_case_id']])
            p = prepare(family, c['offpeak_wait_comparison_min'], False, ready_span=(390, 1180),
                        pm_arrivals=SPANS['last_fs_1940']['pm_arrivals'], am_wait_ceiling_comparison_min=ceiling)
            self.assertEqual(verify(p, c['trips'], c['comparison_peak_windows'], 4), c['conditional_scenarios'])
            self.assertEqual({phase['peak']: phase['start_min'] for phase in c['comparison_peak_windows']}, PEAKS)
            self.assertEqual(c['am_residual_wait_ceiling_inherited_comparison_min'], ceiling)
            cost = sum(family['loops'][t['loop']]['distance_m'] for t in c['trips']) * .26
            self.assertAlmostEqual(cost, c['annual_service_km'], places=5)
            self.assertAlmostEqual(cost, c['annual_service_km_lower_bound_in_domain'], places=5)
            self.assertGreater(cost, 111419)
            self.assertTrue(c['optimality_proven_in_this_domain'])
        with self.assertRaises(ValueError):
            prepare(self.reference, 60, False, am_wait_ceiling_comparison_min=-1)

    def test_boundary_drift_fails_closed(self):
        reference = copy.deepcopy(self.reference)
        reference['loops']['west_A']['edge_ids'][0] = 'wrong'
        case = next(c for c in self.screen['cases'] if c['case_id'] == self.timetable['diagnostic_case_ids'][0])
        with self.assertRaisesRegex(ValueError, 'FS boundary changed'):
            materialize(reference, self.retention, case)

    def test_frontier_report_and_geometry_exports(self):
        front = frontier(self.screen, self.retention)
        self.assertEqual(front, json.loads((BASE / 'stop_relocation_frontier.json').read_text(encoding='utf-8')))
        self.assertEqual(len(front['frontier_case_ids']), 165)
        self.assertEqual(report(self.screen, self.timetable, front), DOC.read_text(encoding='utf-8'))
        shape = json.loads((BASE / 'stop_relocation_diagnostic.geojson').read_text(encoding='utf-8'))
        self.assertEqual(len([f for f in shape['features'] if f['geometry']['type'] == 'LineString']), 8)
        points = [f for f in shape['features'] if f['geometry']['type'] == 'Point']
        self.assertEqual(len(points), 4)
        self.assertTrue(all(not f['properties']['boarding_authorised'] for f in points))


if __name__ == '__main__':
    unittest.main()
