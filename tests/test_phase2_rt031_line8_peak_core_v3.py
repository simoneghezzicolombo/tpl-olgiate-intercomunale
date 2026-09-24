import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "outputs/phase2/rt031_line8_peak_core_v3/probe.json"


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
        self.assertFalse(result["network_selected"])
        self.assertFalse(result["primary_selection_authorised"])
        self.assertFalse(result["runner_up_selection_authorised"])
        self.assertIsNone(result["decision_budget_km"])
        self.assertIsNone(result["uncertainty_band_min"])


if __name__ == "__main__":
    unittest.main()
