import unittest
import json

from scripts.phase2_probe_rt031_line8_manoeuvre_cycles_v3 import (
    OUTPUT, shortest_return_cycle, split_only_edges)


class Allowed:
    def __init__(self, forbidden=()):
        self.forbidden = set(forbidden)

    def decision(self, history, outgoing):
        return {'allowed': (history[-1], outgoing) not in self.forbidden}


def edge(u, v, distance=1):
    return {'u_node_id': u, 'v_node_id': v,
            'length_m': distance, 'running_minutes_model': distance/10}


class ReturnCycleTests(unittest.TestCase):
    def test_dead_end_cannot_hide_reversal_at_next_node(self):
        edges = {'in': edge('a', 'b'), 'out': edge('b', 'a'),
                 'bc': edge('b', 'c'), 'cb': edge('c', 'b')}
        self.assertFalse(shortest_return_cycle(edges, Allowed(), 'in', 'out', set())['reachable'])

    def test_cycle_must_have_legal_suffix_and_avoid_fs(self):
        edges = {'in': edge('a', 'b'), 'out': edge('b', 'a'),
                 'bc': edge('b', 'c'), 'cd': edge('c', 'd'), 'db': edge('d', 'b')}
        answer = shortest_return_cycle(edges, Allowed(), 'in', 'out', set())
        self.assertEqual(answer['cycle_edge_ids'], ['bc', 'cd', 'db'])
        self.assertEqual(answer['added_distance_m'], 3)
        self.assertFalse(shortest_return_cycle(edges, Allowed([('db', 'out')]),
                                               'in', 'out', set())['reachable'])
        self.assertFalse(shortest_return_cycle(edges, Allowed(), 'in', 'out', {'c'})['reachable'])

    def test_split_segment_replaces_overlapping_parent(self):
        edges = {'e': edge('a', 'b'), 'e::IN': edge('a', 'p'),
                 'e::OUT': edge('p', 'b'), 'other': edge('b', 'c')}
        self.assertEqual(set(split_only_edges(edges)), {'e::IN', 'e::OUT', 'other'})

    def test_published_cycles_do_not_certify_unresolved_service(self):
        result = json.loads(OUTPUT.read_text(encoding='utf-8'))
        self.assertEqual([c['id'] for c in result['cases'] if not c['reachable']], ['M5'])
        self.assertFalse(result['all_six_replacements_available_in_declared_domain'])
        self.assertFalse(result['network_selected'])
        self.assertFalse(result['physical_bus_operation_authorised'])
        comparison = result['available_five_cycles_comparison_not_adopted']
        self.assertGreater(comparison['annual_service_km_16_trips_260_days'], 126000)
        self.assertTrue(comparison['fixed_timetable_readiness_violations'])
        self.assertEqual(comparison['selected_real_train_binding_violations'], [])


if __name__ == '__main__':
    unittest.main()
