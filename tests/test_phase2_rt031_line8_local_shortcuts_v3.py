import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/phase2/rt031_line8_local_shortcuts_v3"


class Line8LocalShortcutsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.road = json.loads((BASE / "audit.json").read_text(encoding="utf-8"))
        cls.walk = json.loads((BASE / "walk.json").read_text(encoding="utf-8"))
        cls.shape = json.loads((BASE / "west_swap.geojson").read_text(encoding="utf-8"))
        cls.east = json.loads((BASE / "east_tail_orders.json").read_text(encoding="utf-8"))
        cls.via_como = json.loads((BASE / "via_como_proximity.json").read_text(encoding="utf-8"))
        cls.west_orders = json.loads((BASE / "west_group_orders.json").read_text(encoding="utf-8"))
        cls.full_retention_shape = json.loads((BASE / "west_full_retention.geojson").read_text(
            encoding="utf-8"))

    def test_bounded_road_search_does_not_select(self):
        self.assertEqual(self.road["contract"],
                         "RT031_LINE8_LOCAL_SHORTCUT_SINGLE_EDIT_AUDIT_V3")
        self.assertEqual(len(self.road["options"]), 24)
        self.assertEqual(self.road["baseline"]["bidirectional_pair_distance_m"], 52207.651)
        self.assertFalse(self.road["network_selected"])
        self.assertFalse(self.road["primary_selection_authorised"])
        self.assertFalse(self.road["runner_up_selection_authorised"])
        self.assertIsNone(self.road["decision_budget_km"])
        self.assertIsNone(self.road["uncertainty_band_min"])

    def test_west_swap_tradeoff_and_map(self):
        matches = [o for o in self.road["options"]
                   if o["edit"] == "SWAP_ADJACENT_EXISTING_WAYPOINTS"
                   and o["wing"] == "west"
                   and o["affected_waypoint_ids"] == [
                       "FROZEN::300879", "ASF::PEREGO_VIA_STATALE_79"]]
        self.assertEqual(len(matches), 1)
        option = matches[0]
        self.assertTrue(option["represented_road_feasible"])
        self.assertEqual(option["pair_km_saved_vs_baseline"], 1.562398)
        self.assertEqual(option["current_exact_stop_ids_encountered_count"], 11)
        self.assertEqual(option["existing_stop_ids_lost_both_directions"],
                         ["ASF::SANTA_MARIA_HOE_VIA_COMO"])
        self.assertTrue(option["retains_both_new_waypoint_needs"])
        access = next(o for o in self.walk["options"]
                      if o["option_index_in_road_audit"] == self.road["options"].index(option))
        self.assertEqual(access["potential_access_percentage_point_change_vs_baseline"]
                         ["TOTAL"]["10"], 0)
        self.assertLess(access["potential_access_percentage_point_change_vs_baseline"]
                        ["97074"]["5"], -2)
        lines = [f for f in self.shape["features"]
                 if f["geometry"]["type"] == "LineString"]
        self.assertEqual(len(lines), 2)
        self.assertEqual(round(sum(f["properties"]["distance_m"] for f in lines), 3),
                         option["bidirectional_pair_distance_m"])
        self.assertFalse(self.shape["properties"]["network_selected"])

    def test_east_tail_has_no_shorter_order_retaining_all_current_stops(self):
        self.assertEqual(self.east["contract"],
                         "RT031_LINE8_EAST_TAIL_FOUR_WAYPOINT_ORDER_AUDIT_V3")
        self.assertEqual(len(self.east["orders"]), 24)
        self.assertEqual(self.east["baseline"]["current_exact_stop_ids_encountered_count"], 11)
        shorter = [row for row in self.east["orders"]
                   if row["represented_road_feasible"]
                   and row["pair_km_saved_vs_baseline"] > 0]
        self.assertEqual(len(shorter), 1)
        self.assertEqual(shorter[0]["current_exact_stop_ids_encountered_count"], 10)
        self.assertFalse(self.east["network_selected"])

    def test_lost_via_como_stop_is_near_but_not_certified_on_new_road(self):
        self.assertEqual(self.via_como["contract"],
                         "RT031_VIA_COMO_STOP_TO_WEST_SWAP_ROAD_PROXIMITY_V3")
        self.assertEqual(self.via_como["stop_place_id"],
                         "ASF::SANTA_MARIA_HOE_VIA_COMO")
        old = self.via_como["comparisons"]["baseline"]
        new = self.via_como["comparisons"]["west_swap"]
        self.assertEqual({r["planar_straight_line_distance_m"] for r in old.values()},
                         {1.317})
        self.assertEqual({r["planar_straight_line_distance_m"] for r in new.values()},
                         {26.058})
        self.assertIn("safe boarding and bus stopping", self.via_como["does_not_establish"])
        self.assertFalse(self.via_como["network_selected"])

    def test_west_group_reorder_retains_all_encountered_identities_with_time_tradeoff(self):
        self.assertEqual(self.west_orders["contract"],
                         "RT031_LINE8_WEST_GROUP_WAYPOINT_ORDER_AUDIT_V3")
        self.assertEqual(len(self.west_orders["orders"]), 12)
        kept = [row for row in self.west_orders["orders"]
                if row["represented_road_feasible"]
                and row["pair_km_saved_vs_baseline"] > 0
                and not row["existing_stop_ids_lost_both_directions"]]
        self.assertEqual(len(kept), 1)
        option = kept[0]
        self.assertEqual(option["pair_km_saved_vs_baseline"], 1.288981)
        self.assertEqual(option["current_exact_stop_ids_encountered_count"], 11)
        self.assertEqual(option["both_direction_encountered_stop_ids_not_boarding_guaranteed"],
                         self.west_orders["baseline"][
                             "both_direction_encountered_stop_ids_not_boarding_guaranteed"])
        hoe = option["road_running_to_next_fs_delta_min_by_west_waypoint_excluding_dwell"][
            "FROZEN::300782"]
        self.assertGreater(hoe["forward"], 2.9)
        self.assertLess(hoe["reverse"], -3.6)
        lines = [f for f in self.full_retention_shape["features"]
                 if f["geometry"]["type"] == "LineString"]
        self.assertEqual(len(lines), 2)
        self.assertEqual(round(sum(f["properties"]["distance_m"] for f in lines), 3),
                         option["bidirectional_pair_distance_m"])
        self.assertFalse(self.full_retention_shape["properties"]["network_selected"])


if __name__ == "__main__":
    unittest.main()
