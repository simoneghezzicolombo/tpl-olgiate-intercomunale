import json
from pathlib import Path
import unittest
from itertools import permutations

from scripts.phase2_audit_rt031_south_road_probe_v3 import shortest
from scripts.phase2_audit_rt031_line8_free_partition_bound_v3 import two_cycles


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/phase2/rt031_line8_local_shortcuts_v3"


class Line8DistanceObjectiveTest(unittest.TestCase):
    def test_free_partition_dp_matches_brute_force_asymmetric_costs(self):
        cost = [[0, 8, 3, 7, 4], [6, 0, 4, 9, 2], [4, 7, 0, 2, 8],
                [7, 3, 5, 0, 6], [2, 8, 3, 4, 0]]
        def tour(vertices):
            return min(sum(cost[a][b] for a, b in zip((0,) + p, p + (0,)))
                       for p in permutations(vertices))
        brute = min(tour([i + 1 for i in range(4) if mask & (1 << i)])
                    + tour([i + 1 for i in range(4) if not mask & (1 << i)])
                    for mask in range(1, 15))
        value, first, second, _ = two_cycles(cost)
        self.assertEqual(value, brute)
        self.assertEqual(set(first[0][1:-1]) | set(second[0][1:-1]), {1, 2, 3, 4})
        self.assertFalse(set(first[0][1:-1]) & set(second[0][1:-1]))

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
        bypass = json.loads((BASE / "brivio_relaxation_probe.json").read_text(encoding="utf-8"))
        partition = json.loads((BASE / "free_partition_bound.json").read_text(encoding="utf-8"))
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
        self.assertEqual(bypass["bidirectional_pair_distance_m"], 42742.453)
        self.assertEqual(bypass["annual_10_pairs_260_days_km_before_extras"], 111130.378)
        self.assertFalse(bypass["brivio_centre_stop_encountered_both_directions"])
        self.assertGreater(bypass[
            "brivio_centre_inventory_stop_straight_line_to_road_m_by_direction"]["forward"],
            1400)
        self.assertEqual(walk[
            "brivio_waypoint_relaxation_potential_access_pp_change_vs_25_identity_baseline"]
            ["97010"]["10"], -46.690003)
        self.assertEqual(partition["all_nonempty_unlabelled_partitions_count"], 16383)
        self.assertEqual(partition["directed_shortest_leg_count"], 240)
        self.assertEqual(partition["free_partition_pair_distance_lower_bound_m"], 48613.013)
        self.assertEqual(partition["independent_orientation_relaxation"][
            "annual_20_traversals_260_days_lower_bound_km_before_extras"], 125316.755)
        self.assertFalse(partition["network_selected"])
        self.assertIsNone(partition["decision_budget_km"])
        self.assertFalse(audit["network_selected"])
        self.assertFalse(bound["network_selected"])
        self.assertFalse(audit["primary_selection_authorised"])
        self.assertFalse(bound["runner_up_selection_authorised"])
        self.assertIsNone(bound["decision_budget_km"])
        self.assertIsNone(bound["uncertainty_band_min"])


if __name__ == "__main__":
    unittest.main()
