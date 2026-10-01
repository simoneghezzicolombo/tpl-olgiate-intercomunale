import itertools
import json
import math
import unittest
import numpy as np

from scripts.phase2_probe_rt031_line8_multistop_recovery_v3 import OUTPUT, seeded_distances, minimum_cover
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import RETENTION
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import FLAGS
from scripts.phase2_check_rt031_line8_multistop_recovery_v3 import OUTPUT as TIMETABLE, build_problem
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import verify
from scripts.phase2_probe_rt031_line8_stop_relocation_v3 import digest


class MultistopRecoveryTests(unittest.TestCase):
    def test_multisource_includes_connectors_and_direction(self):
        reverse = {'stop_a': [('p', 8)], 'stop_b': [('q', 1)], 'q': [('p', 1)], 'p': []}
        together = seeded_distances(reverse, [('stop_a', 0), ('stop_b', 10)])
        a, b = (seeded_distances(reverse, [(s, c)]) for s, c in [('stop_a', 0), ('stop_b', 10)])
        for node in set(a) | set(b):
            self.assertEqual(together[node], min(a.get(node, math.inf), b.get(node, math.inf)))
        self.assertEqual(together['p'], 8)
        self.assertNotIn('stop_a', seeded_distances(reverse, [('p', 0)]))

    def test_invalid_distance_fails_closed(self):
        for cost in (-1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                seeded_distances({}, [('a', cost)])
        with self.assertRaises(ValueError):
            seeded_distances({'a': [('b', -1)]}, [('a', 0)])

    def test_cover_matches_exhaustive_subsets(self):
        rng = np.random.default_rng(12)
        for _ in range(15):
            matrix = rng.random((5, 7)) > .55
            matrix[:, 0] |= ~matrix.any(axis=1)
            best = min(len(indices) for n in range(8) for indices in itertools.combinations(range(7), n)
                       if n and matrix[:, list(indices)].any(axis=1).all())
            selected, proven, lower = minimum_cover(matrix)
            self.assertTrue(proven)
            self.assertEqual(len(selected), best)
            self.assertAlmostEqual(lower, best)
            self.assertTrue(matrix[:, selected].any(axis=1).all())

    def test_unrecoverable_requirements_cannot_be_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, 'uncoverable'):
            minimum_cover(np.array([[True, False], [False, False]]))
        self.assertEqual(minimum_cover(np.empty((0, 4), dtype=bool)), ([], True, 0.))

    def test_witness_paths_unchanged_and_stops_on_both_directions(self):
        r = json.loads(OUTPUT.read_text(encoding='utf-8'))
        old = json.loads(RETENTION.read_text(encoding='utf-8'))
        variants = {v['variant_id']: v for values in old['variants'].values() for v in values}
        for wing in ('west', 'east'):
            vid = r['diagnostic_reference_case'][wing + '_choice_id'].split('__')[0]
            for pattern, loop in variants[vid]['loops'].items():
                self.assertEqual(r['loops'][pattern]['edge_ids'], loop['edge_ids'])
                self.assertEqual(r['loops'][pattern]['distance_m'], loop['distance_m'])
                for node in r['added_road_nodes']:
                    if node in r['candidate_nodes_by_wing'][wing]:
                        events = [e for e in r['loops'][pattern]['events'] if e['stop_place_id'] == 'PROXY::RELOCATION_NODE_' + node]
                        self.assertTrue(events)
                        self.assertTrue(all(e['boarding_authorised'] is False for e in events))
        self.assertEqual(len(r['added_road_nodes']), r['added_stop_count'])
        self.assertIsNone(r['annual_service_km'])
        self.assertFalse(r['timetable_validated'])
        for flag in FLAGS:
            self.assertFalse(r[flag])

    def test_witness_recovers_every_recoverable_baseline_target(self):
        r = json.loads(OUTPUT.read_text(encoding='utf-8'))
        self.assertEqual(r['witness_previously_covered_population_fraction_lost'],
                         r['all_candidate_stops_irrecoverable_loss_fraction'])
        self.assertTrue(r['minimum_added_stop_count_proven_for_recoverable_target'])
        self.assertEqual(r['added_stop_count'], r['added_stop_count_lower_bound'])
        self.assertFalse(r['no_loss_possible_in_finite_node_domain'])

    def test_timetable_recomputed_with_added_dwell(self):
        r = json.loads(OUTPUT.read_text(encoding='utf-8'))
        checked = json.loads(TIMETABLE.read_text(encoding='utf-8'))
        self.assertEqual(checked['source_sha256_normalized_newlines'], digest(OUTPUT, True))
        p = build_problem(r)
        c = checked['case']
        self.assertEqual(c['conditional_scenarios'], verify(p, c['trips'], c['comparison_peak_windows'], 4))
        self.assertGreater(c['annual_service_km'], r['diagnostic_reference_case']['annual_service_km'])
        self.assertAlmostEqual(sum(r['loops'][t['loop']]['distance_m']*.26 for t in c['trips']), c['annual_service_km'], places=5)
        self.assertTrue(all(not checked[k] for k in FLAGS))
        self.assertFalse(checked['actual_timetable_certified'])


if __name__ == '__main__':
    unittest.main()
