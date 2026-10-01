import gzip
import json
import unittest

from scripts.phase2_probe_rt031_line8_calco_through_path_v3 import OUTPUT, through_path
from scripts.phase2_probe_rt031_line8_free_orders_v3 import reversal_indices
from tests.test_phase2_rt031_line8_manoeuvre_cycles_v3 import Allowed, edge


class CalcoThroughTests(unittest.TestCase):
    def test_through_path_does_not_move_a_reversal_to_another_node(self):
        edges = {'in': edge('a', 'b'), 'bc': edge('b', 'c'), 'cb': edge('c', 'b'),
                 'out': edge('b', 'd')}
        self.assertFalse(through_path(edges, Allowed(), 'in', 'out', 'c', set())['reachable'])

    def test_service_checkpoint_requires_its_declared_incoming_edge(self):
        edges = {'in': edge('a', 'b'), 'bc': edge('b', 'c'), 'cd': edge('c', 'd'),
                 'dx': edge('d', 'x'), 'xc': edge('x', 'c'), 'cf': edge('c', 'f'),
                 'out': edge('f', 'g')}
        answer = through_path(edges, Allowed(), 'in', 'out', [('c', 'xc')], set())
        self.assertEqual(answer['edge_ids'], ['bc', 'cd', 'dx', 'xc', 'cf'])
        self.assertEqual(reversal_indices(['in', *answer['edge_ids'], 'out'], edges), [])

    def test_ordered_service_event_progress_is_part_of_state(self):
        edges = {'in': edge('a', 'b'), 'bc': edge('b', 'c'), 'cd': edge('c', 'd'),
                 'db': edge('d', 'b'), 'bf': edge('b', 'f'), 'out': edge('f', 'g')}
        answer = through_path(edges, Allowed(), 'in', 'out', [('c', None), ('b', None)], set())
        self.assertEqual(answer['edge_ids'], ['bc', 'cd', 'db', 'bf'])

    def test_proposal_keeps_uncertified_relocation_and_budget_visible(self):
        result = json.loads(gzip.decompress(OUTPUT.read_bytes()))
        old = [c for c in result['cases'] if c['original_calco_service_point_retained']]
        self.assertTrue(all(not c['reachable'] for c in old))
        candidate = next(c for c in result['cases'] if c['reachable'])
        self.assertLess(candidate['graph_service_point_displacement_m'], 20)
        self.assertFalse(candidate['pedestrian_coverage_preservation_certified'])
        whole = candidate['whole_wing_fixed_order_without_reversals']
        self.assertTrue(whole['reachable'])
        self.assertGreater(whole['annual_service_km_16_trips_260_days'], 123000)
        self.assertLess(whole['annual_service_km_16_trips_260_days'], 126611)
        self.assertEqual(len({e['stop_place_id'] for l in whole['loops'].values()
                              for e in l['events']}), 28)  # FS is the 29th identity.
        for local in whole['local_fast_passages_nominal'].values():
            self.assertEqual(local['served_occurrence_count'], 2)
            self.assertLess(local['inbound_min_nominal'], 5)
            self.assertLess(local['outbound_min_nominal'], 5)
        for l in whole['loops'].values():
            self.assertTrue(all(e['next_fs_node_index']==len(l['edge_ids']) for e in l['events']))
        self.assertTrue(whole['timetable_comparison']['witness_found'])
        self.assertEqual([c['shoulder_headway_cap_min'] for c in
                          whole['reduced_trip_count_comparisons_not_adopted']], [70, 75, 80])
        self.assertTrue(all(c['infeasibility_proven'] and c['comparison_trip_count_not_adopted']
                            for c in whole['reduced_trip_count_comparisons_not_adopted']))
        self.assertFalse(result['network_selected'])
        self.assertFalse(result['fs_terminal_manoeuvre_certified'])


if __name__ == '__main__':
    unittest.main()
