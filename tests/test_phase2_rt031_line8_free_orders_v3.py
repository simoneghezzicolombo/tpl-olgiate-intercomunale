import heapq
import json
import math
import unittest

from scripts.phase2_probe_rt031_line8_free_orders_v3 import EdgeStateClosure, terminal_tour, OUTPUT
from scripts.phase2_compare_rt031_line8_evening_reallocation_v3 import FLAGS, load_sources, EXPECTED
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import family_inputs


class Rules:
    def __init__(self, banned=()):
        self.banned = set(banned)

    def decision(self, history, nxt):
        return {'allowed': (history[-1], nxt) not in self.banned}


def graph():
    # Two ways to approach A: cheapest arrival cannot continue directly to B.
    rows = [('start', 'FS', 'L', 1), ('la', 'L', 'A', 1),
            ('lx', 'L', 'X', 2), ('xa', 'X', 'A', 1),
            ('ab', 'A', 'B', 1), ('ba', 'B', 'A', 1),
            ('al', 'A', 'L', 6), ('bl', 'B', 'L', 1),
            ('suffix', 'L', 'FS', 1)]
    return {e: {'u_node_id': u, 'v_node_id': v, 'length_m': d,
                'running_minutes_model': d / 2} for e, u, v, d in rows}


def product_graph_oracle(edges, rules, required):
    """Independent edge-by-edge exhaustive state search, not terminal closure."""
    bits = {n: 1 << i for i, n in enumerate(sorted(set(required)))}
    full = (1 << len(bits)) - 1
    best = {(0, 'start'): (0., 0.)}
    queue = [(0., 0., 0, 'start')]
    while queue:
        distance, runtime, mask, last = heapq.heappop(queue)
        if (distance, runtime) != best[mask, last]:
            continue
        node = edges[last]['v_node_id']
        if mask == full and node == 'L' and rules.decision((last,), 'suffix')['allowed']:
            return distance, runtime
        for nxt, e in edges.items():
            if e['u_node_id'] != node or e['v_node_id'] == 'FS' or not rules.decision((last,), nxt)['allowed']:
                continue
            state = (mask | bits.get(e['v_node_id'], 0), nxt)
            cost = (distance + e['length_m'], runtime + e['running_minutes_model'])
            if cost < best.get(state, (math.inf, math.inf)):
                best[state] = cost
                heapq.heappush(queue, (*cost, *state))
    return math.inf, math.inf


class FreeOrdersTests(unittest.TestCase):
    def compare(self, banned=(), required=('A', 'B')):
        edges, rules = graph(), Rules(banned)
        closure = EdgeStateClosure(edges, rules, {'FS'})
        result = terminal_tour(closure, required, 'start', 'L', 'suffix', rules)
        oracle = product_graph_oracle(edges, rules, required)
        self.assertEqual((result['interior_distance_m'], result['interior_road_minutes']), oracle)
        path = ['start', *result['interior_edge_ids'], 'suffix']
        for a, b in zip(path, path[1:]):
            self.assertEqual(edges[a]['v_node_id'], edges[b]['u_node_id'])
            self.assertTrue(rules.decision((a,), b)['allowed'])
        self.assertNotIn('FS', [edges[e]['v_node_id'] for e in path[:-1]])
        self.assertTrue(set(required) <= {edges[e]['v_node_id'] for e in path})
        self.assertEqual(sum(edges[e]['length_m'] for e in path[1:-1]), oracle[0])
        return result

    def test_incoming_state_not_reset_at_terminal(self):
        r = self.compare([('la', 'ab')])
        self.assertEqual(r['interior_distance_m'], 5)
        self.assertEqual(r['interior_edge_ids'], ['lx', 'xa', 'ab', 'bl'])

    def test_suffix_seam_changes_valid_optimum(self):
        r = self.compare([('bl', 'suffix')])
        self.assertGreater(r['interior_distance_m'], 3)
        self.assertEqual(r['interior_edge_ids'][-1], 'al')

    def test_prefix_seam_and_incidental_terminal_visits(self):
        self.compare([('start', 'la')])
        self.compare(required=('B',))  # A is passed without becoming a DP terminal.
        self.compare(required=('A', 'B', 'A'))

    def test_many_rules_against_independent_product_graph(self):
        candidates = [('start', 'la'), ('la', 'ab'), ('xa', 'ab'), ('bl', 'suffix')]
        for mask in range(16):
            banned = [pair for i, pair in enumerate(candidates) if mask & (1 << i)]
            rules, edges = Rules(banned), graph()
            if math.isfinite(product_graph_oracle(edges, rules, ('A', 'B'))[0]):
                self.compare(banned)
            else:
                with self.assertRaisesRegex(ValueError, 'unreachable'):
                    terminal_tour(EdgeStateClosure(edges, rules, {'FS'}), ('A', 'B'), 'start', 'L', 'suffix', rules)

    def test_invalid_costs_fail_closed(self):
        for field in ('length_m', 'running_minutes_model'):
            for value in (-1, math.nan, math.inf):
                edges = graph()
                edges['ab'][field] = value
                with self.assertRaisesRegex(ValueError, 'nonnegative'):
                    EdgeStateClosure(edges, Rules(), {'FS'})

    def test_saved_result_matches_existing_full_wings(self):
        r = json.loads(OUTPUT.read_text(encoding='utf-8'))
        reference = next(f for f in family_inputs(load_sources()) if f['name'] == 'fast_local_both_directions')
        self.assertEqual(r['source_sha256_normalized_newlines'], EXPECTED)
        self.assertEqual(len(r['reference_site_ids']), 28)
        for audit in r['audits']:
            name = audit['pattern']
            target = 'west_B' if name.startswith('west') else 'east_A'
            self.assertEqual(audit['identical_reference_patterns'], [target])
            self.assertEqual(r['loops'][name]['edge_ids'], reference['loops'][target]['edge_ids'])
            self.assertEqual(len(audit['new_immediate_reversal_indices']), 3)
            self.assertTrue(audit['minimum_distance_proven_in_represented_fixed_boundary_domain'])
            old_ids = {e['stop_place_id'] for e in reference['loops'][target]['events']}
            self.assertTrue(old_ids <= {e['stop_place_id'] for e in r['loops'][name]['events']})
        for key in FLAGS:
            self.assertFalse(r[key])
        self.assertFalse(r['actual_timetable_certified'])
        self.assertIsNone(r['decision_budget_km'])
        self.assertIsNone(r['uncertainty_band_min'])


if __name__ == '__main__':
    unittest.main()
