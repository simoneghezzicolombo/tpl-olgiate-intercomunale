import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "outputs/phase2/rt031_line8_peak_core_v3/probe.json"
GEOJSON = ROOT / "outputs/phase2/rt031_line8_peak_core_v3/road_options.geojson"


class PeakCoreProbeTest(unittest.TestCase):
    def test_conditional_core_math_and_fail_closed_flags(self):
        result = json.loads(PROBE.read_text(encoding="utf-8"))
        self.assertEqual(result["contract"], "RT031_LINE8_PEAK_SHORT_CORE_ROAD_PROBE_V3")
        self.assertEqual(result["loops"]["south_then_north"]["distance_m"], 4737.141)
        self.assertEqual(result["loops"]["south_then_north"][
            "existing_inventory_stop_ids_encountered_not_boarding_guaranteed"],
            ["FROZEN::L00407"])
        rows = {(row["variant_id"], row["full_forward_and_reverse_pairs_per_day"]): row
                for row in result["annual_examples"]}
        inclusive = "FIVE_QUATTRO_STRADE_THEN_CARIPLO"
        self.assertAlmostEqual(rows[(inclusive, 7)]["annual_model_km_before_all_extras"],
                               104871.1781)
        self.assertTrue(rows[(inclusive, 7)]["within_cap_before_all_extras"])
        self.assertFalse(rows[(inclusive, 8)]["within_cap_before_all_extras"])
        extensions = result["fixed_waypoint_short_core_extensions"]
        statale_calco = extensions["OLGIATE_STATALE_CALCO_VIRGILIO"]
        self.assertEqual(statale_calco["shortest_found_distance_m_for_fixed_waypoint_set"],
                         5988.218)
        self.assertEqual(len(statale_calco[
            "existing_inventory_stop_ids_encountered_not_boarding_guaranteed"]), 3)
        self.assertAlmostEqual(statale_calco[
            "annual_km_with_seven_inclusive_full_pairs_and_eight_short_loops_before_extras"],
            107473.41826)
        self.assertTrue(all(row["within_cap_before_extras"]
                            for row in extensions.values()))
        self.assertFalse(result["network_selected"])
        self.assertFalse(result["primary_selection_authorised"])
        self.assertFalse(result["runner_up_selection_authorised"])
        self.assertIsNone(result["decision_budget_km"])
        self.assertIsNone(result["uncertainty_band_min"])

    def test_short_core_geometry_is_explicit_and_non_decisional(self):
        probe = json.loads(PROBE.read_text(encoding="utf-8"))
        geojson = json.loads(GEOJSON.read_text(encoding="utf-8"))
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(geojson["properties"]["source_sha256"], probe["source_sha256"])
        lines = [feature for feature in geojson["features"]
                 if feature["geometry"]["type"] == "LineString"]
        self.assertEqual(len(lines), 6)
        expected = {**{key: row["distance_m"] for key, row in probe["loops"].items()},
                    **{key: row["shortest_found_distance_m_for_fixed_waypoint_set"]
                       for key, row in probe["fixed_waypoint_short_core_extensions"].items()}}
        self.assertEqual({row["properties"]["scenario"]: row["properties"]["distance_m"]
                          for row in lines}, expected)
        for feature in lines:
            coords = feature["geometry"]["coordinates"]
            self.assertEqual(coords[0], coords[-1])
            self.assertGreater(len(coords), 2)
        self.assertFalse(geojson["properties"]["network_selected"])


if __name__ == "__main__":
    unittest.main()
