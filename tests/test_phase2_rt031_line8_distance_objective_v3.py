import json
from pathlib import Path
import unittest

from scripts.phase2_audit_rt031_south_road_probe_v3 import shortest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/phase2/rt031_line8_local_shortcuts_v3"


class Line8DistanceObjectiveTest(unittest.TestCase):
    def test_time_shortest_is_not_necessarily_distance_shortest(self):
        edges = {
            "quick_1": {"edge_id": "quick_1", "u_node_id": "a", "v_node_id": "b",
                        "length_m": "100", "running_minutes_model": "1", "osm_way_id": "1"},
            "quick_2": {"edge_id": "quick_2", "u_node_id": "b", "v_node_id": "d",
                        "length_m": "100", "running_minutes_model": "1", "osm_way_id": "2"},
            "short_1": {"edge_id": "short_1", "u_node_id": "a", "v_node_id": "c",
                        "length_m": "50", "running_minutes_model": "2", "osm_way_id": "3"},
            "short_2": {"edge_id": "short_2", "u_node_id": "c", "v_node_id": "d",
                        "length_m": "50", "running_minutes_model": "2", "osm_way_id": "4"},
        }
        timed = shortest(edges, [], "a", "d")
        distanced = shortest(edges, [], "a", "d", objective="meters")
        self.assertEqual(timed["edge_ids"], ["quick_1", "quick_2"])
        self.assertEqual(distanced["edge_ids"], ["short_1", "short_2"])
        self.assertEqual((timed["distance_m"], distanced["distance_m"]), (200, 100))

    def test_pinned_fixed_waypoint_audit_is_not_decisional(self):
        audit = json.loads((BASE / "distance_objective_audit.json").read_text(encoding="utf-8"))
        bound = json.loads((BASE / "waypoint_lower_bound.json").read_text(encoding="utf-8"))
        shape = json.loads((BASE / "distance_option.geojson").read_text(encoding="utf-8"))
        walk = json.loads((BASE / "distance_option_walk.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["contract"],
                         "RT031_LINE8_FIXED_WAYPOINT_DISTANCE_OBJECTIVE_AUDIT_V3")
        self.assertEqual(audit["variants"]["baseline_order"]["minutes"]
                         ["bidirectional_pair_distance_m"], 52207.651)
        kept = audit["variants"]["full_retention_west_order"]
        self.assertEqual(kept["minutes"]["bidirectional_pair_distance_m"], 50918.67)
        self.assertEqual(kept["meters"]["bidirectional_pair_distance_m"], 49951.301)
        self.assertEqual(len(kept["meters"]
                             ["both_direction_encountered_stop_ids_not_boarding_guaranteed"]), 22)
        self.assertEqual(bound["contract"],
                         "RT031_LINE8_ALL_FIXED_WAYPOINT_ORDERS_KM_LOWER_BOUND_V3")
        self.assertGreater(bound["total_optimistic_bidirectional_pair_distance_m"],
                           bound["required_pair_distance_m_for_111419_km_at_10_pairs_260_days_before_extras"])
        self.assertEqual(bound["total_optimistic_bidirectional_pair_distance_m"], 48613.013)
        self.assertEqual(shape["name"],
                         "RT031_LINE8_FASTEST_VS_SHORTEST_KM_ROAD_DIAGNOSTIC_V3")
        self.assertEqual(sum(f["geometry"]["type"] == "LineString"
                             for f in shape["features"]), 4)
        self.assertEqual(sum(f["properties"].get("feature_type") == "UNAPPROVED_STOP_NEED"
                             for f in shape["features"]), 2)
        self.assertEqual(sum(f["properties"].get(
            "encountered_in_shorter_road_both_directions") is False
            for f in shape["features"]), 3)
        self.assertEqual(walk["contract"],
                         "RT031_LINE8_DISTANCE_OBJECTIVE_CONDITIONAL_WALK_ACCESS_V3")
        delta = walk["potential_access_percentage_point_change_vs_25_identity_baseline"]
        self.assertEqual(delta["TOTAL"]["10"], -2.440711)
        self.assertEqual(delta["97058"]["10"], -6.388113)
        self.assertEqual(delta["97010"]["10"], -3.552198)
        self.assertFalse(walk["network_selected"])
        self.assertFalse(audit["network_selected"])
        self.assertFalse(bound["network_selected"])
        self.assertFalse(audit["primary_selection_authorised"])
        self.assertFalse(bound["runner_up_selection_authorised"])
        self.assertIsNone(bound["decision_budget_km"])
        self.assertIsNone(bound["uncertainty_band_min"])


if __name__ == "__main__":
    unittest.main()
