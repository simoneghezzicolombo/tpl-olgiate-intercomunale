import json
from pathlib import Path
import unittest
from fractions import Fraction

from scripts.phase2_rt031_ordered_via_node_path_v3 import ordered_path


BASE = Path(__file__).resolve().parents[1] / "outputs/phase2/rt031_line8_local_shortcuts_v3"


class ExistingSitesTest(unittest.TestCase):
    def test_contextual_witness_preserves_reference_and_span_is_only_volume(self):
        road = json.loads((BASE / 'full_retention_context.json').read_text(encoding='utf-8'))
        self.assertEqual(road['lost_reference_inventory_ids'], [])
        self.assertEqual(len(road['both_direction_encountered_stop_ids_not_boarding_guaranteed']), 26)
        self.assertEqual(road['known_successor_via_way_overlap'], [])
        self.assertTrue(road['represented_via_node_path_verified'])
        self.assertIn('H30/H60 timetable', road['not_certified'])
        self.assertIn('full-history restrictions', road['not_certified'])
        self.assertFalse(road['network_selected'])
        self.assertFalse(road['primary_selection_authorised'])
        self.assertFalse(road['runner_up_selection_authorised'])
        self.assertIsNone(road['decision_budget_km'])
        self.assertIsNone(road['uncertainty_band_min'])
        self.assertEqual([s['span_hours'] for s in road['scenarios']], [13, 14, 16])
        for s in road['scenarios']:
            expected = road['pair_distance_m'] / 2000 * (s['span_hours'] + 4) * 260
            self.assertAlmostEqual(s['annual_model_km_before_extras'], expected, places=3)
        shape = json.loads((BASE / 'full_retention_context.geojson').read_text(encoding='utf-8'))
        lines = [f for f in shape['features'] if f['geometry']['type'] == 'LineString']
        self.assertEqual(len(lines), 2)
        for f in lines:
            self.assertEqual(f['geometry']['coordinates'][0], f['geometry']['coordinates'][-1])
            self.assertEqual(f['properties']['distance_m'], road['directions'][f['properties']['direction']]['distance_m'])

    def test_conditional_access_has_no_municipal_loss(self):
        walk = json.loads((BASE / 'brivio_existing_sites_walk.json').read_text(encoding='utf-8'))
        for thresholds in walk['all_reference_contextual_access_pp_change_vs_reference'].values():
            self.assertTrue(all(delta >= 0 for delta in thresholds.values()))
        self.assertEqual(len(walk['existing_site_options']), 31)
        for value in walk['all_reference_contextual_potential_access'].values():
            self.assertTrue(all(0 <= Fraction(f) <= 1 for f in value['potential_walking_access_fraction'].values()))

    def test_waypoint_does_not_reset_incoming_turn_memory(self):
        edges = {}
        for eid, u, v, length in (("ab", "a", "b", 1), ("bc", "b", "c", 1),
                                   ("ax", "a", "x", 1), ("xb", "x", "b", 2)):
            edges[eid] = {"edge_id": eid, "u_node_id": u, "v_node_id": v,
                          "osm_way_id": eid, "length_m": str(length),
                          "running_minutes_model": str(length)}
        rules = [{"relation_id": "r", "restriction": "no_right_turn", "via_node_id": "b",
                  "from_osm_way_id": "ab", "to_osm_way_id": "bc", "via_node_in_graph": "True"}]
        answer = ordered_path(edges, rules, ["a", "b", "c"])
        self.assertTrue(answer["reachable"])
        self.assertEqual(answer["_path_edge_ids"], ["ax", "xb", "bc"])
        self.assertEqual(answer["distance_m"], 4)
        self.assertFalse(answer["full_history_via_way_legality_certified"])

    def test_inventory_domain_is_explicit_and_not_a_selected_centre_stop(self):
        road = json.loads((BASE / "brivio_existing_sites.json").read_text(encoding="utf-8"))
        self.assertEqual(road["contract"], "RT031_LINE8_BRIVIO_EXISTING_SITE_REPLACEMENT_PROBE_V3")
        self.assertEqual(len(road["inventory_candidate_ids"]), 10)
        self.assertEqual(len(road["options"]), 32)
        self.assertFalse(road["centre_service_equivalence_certified"])
        self.assertFalse(road["network_selected"])
        rejected = next(r for r in road["options"] if r["mode"] == "ALL_REFERENCE_IDS_REQUIRED_SHORTEST_KM")
        self.assertFalse(rejected["represented_road_feasible"])
        self.assertGreater(rejected["represented_via_node_bad_turn_count"], 0)


if __name__ == "__main__":
    unittest.main()
