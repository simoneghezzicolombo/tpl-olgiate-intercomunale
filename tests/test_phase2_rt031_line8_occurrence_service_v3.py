import json
from pathlib import Path
import unittest
from scripts.phase2_audit_rt031_line8_occurrence_service_v3 import occurrences


BASE = Path(__file__).resolve().parents[1] / 'outputs/phase2/rt031_line8_local_shortcuts_v3'


class OccurrenceServiceTests(unittest.TestCase):
    def test_repeated_identity_keeps_distinct_downstream_fs(self):
        edges = {str(i): {'u_node_id': a, 'v_node_id': b, 'running_minutes_model': t}
                 for i,(a,b,t) in enumerate([('fs','s',2),('s','fs',3),('fs','s',7),('s','fs',11)])}
        events = occurrences(list(edges), edges, {'stop': {'node':'s','name':'Stop','status':'UNVERIFIED'}}, 'fs', 'A')
        self.assertEqual([r['road_minutes_to_next_fs'] for r in events], [3,11])
        self.assertNotEqual(events[0]['occurrence_id'], events[1]['occurrence_id'])
        self.assertTrue(all(not r['boarding_authorised'] for r in events))

    def test_discontinuous_path_fails_closed(self):
        edges = {'a': {'u_node_id':'fs','v_node_id':'s','running_minutes_model':1},
                 'b': {'u_node_id':'x','v_node_id':'fs','running_minutes_model':1}}
        with self.assertRaises(ValueError):
            occurrences(['a','b'], edges, {}, 'fs', 'A')

    def test_artifact_does_not_promote_aggregate_frequency_or_coverage(self):
        a = json.loads((BASE/'occurrence_service.json').read_text(encoding='utf-8'))
        self.assertEqual(a['alternating_directions']['same_direction_same_occurrence_peak_headway_min'], 60)
        self.assertEqual(a['alternating_directions']['same_direction_same_occurrence_offpeak_headway_min'], 120)
        self.assertFalse(a['network_selected'])
        self.assertFalse(a['primary_selection_authorised'])
        self.assertFalse(a['runner_up_selection_authorised'])
        self.assertIsNone(a['decision_budget_km'])
        self.assertIsNone(a['uncertainty_band_min'])
        self.assertEqual(len(a['road_patterns']), 4)
        reference = json.loads((BASE/'full_retention_context.json').read_text(encoding='utf-8'))
        for pattern in a['road_patterns']:
            seen = {e['stop_place_id'] for e in a['events'] if e['direction'] == pattern}
            self.assertTrue(set(reference['both_direction_encountered_stop_ids_not_boarding_guaranteed']) <= seen)
        for s in a['repeat_direction_scenarios']:
            distance = a['road_patterns'][s['pattern'].removeprefix('REPEAT_')]['distance_m']
            self.assertAlmostEqual(s['annual_km_before_extras'], distance/1000*(s['span_hours']+4)*260, places=3)


if __name__ == '__main__':
    unittest.main()
