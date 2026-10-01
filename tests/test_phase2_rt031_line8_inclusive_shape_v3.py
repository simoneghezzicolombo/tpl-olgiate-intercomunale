import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHAPE = ROOT / "outputs/phase2/rt031_line8_inclusive_shape_v3/line8_inclusive_model.geojson"
REPAIR = ROOT / "outputs/phase2/rt031_current_stop_repair_v3/road_options.json"


class InclusiveShapeTest(unittest.TestCase):
    def test_shape_materialises_both_frozen_directions_and_encountered_points(self):
        shape = json.loads(SHAPE.read_text(encoding="utf-8"))
        repair = json.loads(REPAIR.read_text(encoding="utf-8"))
        reference = repair["combined_repair_order_options"]["FIVE_QUATTRO_STRADE_THEN_CARIPLO"]
        self.assertEqual(shape["type"], "FeatureCollection")
        self.assertEqual(len(shape["features"]), 29)
        paths = shape["features"][:2]
        self.assertEqual([f["geometry"]["type"] for f in paths], ["LineString", "LineString"])
        self.assertEqual(paths[0]["properties"]["distance_m"],
                         reference["forward_complete_cycle_distance_m"])
        self.assertEqual(paths[1]["properties"]["distance_m"],
                         reference["reverse_complete_cycle_distance_m"])
        self.assertTrue(all(f["geometry"]["coordinates"][0] ==
                            f["geometry"]["coordinates"][-1] for f in paths))
        stops = shape["features"][2:]
        self.assertEqual(len([f for f in stops if f["properties"]["feature_type"] ==
                              "EXISTING_INVENTORY_STOP_ENCOUNTERED_NOT_BOARDING_CERTIFIED"]), 25)
        self.assertEqual(len([f for f in stops if f["properties"]["feature_type"] ==
                              "NEW_STOP_NEED_NOT_APPROVED_STOP"]), 2)
        props = shape["properties"]
        self.assertFalse(props["network_selected"])
        self.assertFalse(props["primary_selection_authorised"])
        self.assertFalse(props["runner_up_selection_authorised"])
        self.assertIsNone(props["decision_budget_km"])
        self.assertIsNone(props["uncertainty_band_min"])


if __name__ == "__main__":
    unittest.main()
