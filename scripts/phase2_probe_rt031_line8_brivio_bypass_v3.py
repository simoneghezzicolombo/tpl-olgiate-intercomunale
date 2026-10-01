"""Check the most optimistic one-waypoint relaxation, without selecting it."""

import argparse
import json
import math
from pathlib import Path

from pyproj import Transformer

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_probe_rt031_current_stop_repair_v3 import path_stops
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def point_segment_m(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy)
                     / (dx * dx + dy * dy)))
    return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def build(paths):
    bound = json.loads(paths["bound"].read_text(encoding="utf-8"))
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if (bound["contract"] != "RT031_LINE8_ALL_FIXED_WAYPOINT_ORDERS_KM_LOWER_BOUND_V3"
            or road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or bound["source_sha256"]["road_screen"] != digest(paths["road_screen"], True)):
        raise ValueError("bound or road source drift")
    drops = [row for row in bound["single_existing_waypoint_drop_sensitivity_optimistic_not_stop_loss"]
             if row["dropped_waypoint_id"] == "FROZEN::300063"]
    if len(drops) != 1 or drops[0]["wing"] != "east":
        raise ValueError("Brivio centre relaxation drift")
    edges, graph_nodes, rules, attachments = build_graph(paths)
    nodes = {sid: row["graph_node_id"] for sid, row in attachments.items()
             if row["route_ready"] == "True"}
    nodes[VIRTUAL] = VIRTUAL
    nodes[NORTH] = road["north_proxy"]["graph_node_id"]
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True"
                and row["service_class"] == "CONVENTIONAL_TPL"}
    west, east = itinerary()
    by_id = {sid: (label, sid) for label, sid in west + east}
    w = [by_id[sid] for sid in bound["wings"]["west"]
         ["ordered_waypoint_ids_at_optimistic_minimum"]]
    e = [by_id[sid] for sid in drops[0]["optimistic_order_after_drop"]]
    if "FROZEN::300063" in [sid for _, sid in e]:
        raise ValueError("Brivio centre waypoint unexpectedly retained")
    parts = {key: screen_lobe(seq, nodes, edges, rules, objective="meters")
             for key, seq in (("wf", w), ("ef", e),
                              ("er", list(reversed(e))), ("wr", list(reversed(w))))}
    if not all(p["reachable"] for p in parts.values()):
        raise ValueError("optimistic order not reachable on represented graph")
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                         unresolved_external_via_way_count=2)
    def join(a, b):
        left, right = parts[a]["_path_edge_ids"][-1], parts[b]["_path_edge_ids"][0]
        return (edges[left]["v_node_id"] == edges[right]["u_node_id"]
                and adapter.decision((left,), right)["allowed"] is True)
    bad = sum(len(p["via_node_bad_turn_indices_at_leg_seams_or_within_legs"])
              for p in parts.values())
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for relation in successor["successor_via_way_relations"]
                for way in relation["via_way_ids"]}
    overlap = sorted(via_ways & set().union(*(set(p["osm_way_ids"]) for p in parts.values())))
    pair_m = sum(p["distance_m"] for p in parts.values())
    if abs(pair_m - drops[0]["optimistic_pair_distance_m"]) > .01:
        raise ValueError("relaxed order differs from optimistic distance bound")
    forward = parts["wf"]["_path_edge_ids"] + parts["ef"]["_path_edge_ids"]
    reverse = parts["er"]["_path_edge_ids"] + parts["wr"]["_path_edge_ids"]
    f_stops = path_stops(parts["wf"], edges, eligible) | path_stops(parts["ef"], edges, eligible)
    r_stops = path_stops(parts["er"], edges, eligible) | path_stops(parts["wr"], edges, eligible)
    both = sorted(f_stops & r_stops)
    brivio = attachments["FROZEN::300063"]
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    point = transformer.transform(float(brivio["lon"]), float(brivio["lat"]))
    nearest = {}
    for direction, path in (("forward", forward), ("reverse", reverse)):
        nearest[direction] = round(min(point_segment_m(
            point,
            (float(graph_nodes[edges[eid]["u_node_id"]]["x"]),
             float(graph_nodes[edges[eid]["u_node_id"]]["y"])),
            (float(graph_nodes[edges[eid]["v_node_id"]]["x"]),
             float(graph_nodes[edges[eid]["v_node_id"]]["y"])))
            for eid in path if edges[eid]["u_node_id"] in graph_nodes
            and edges[eid]["v_node_id"] in graph_nodes), 3)
    return {
        "contract": "RT031_LINE8_BRIVIO_WAYPOINT_RELAXATION_ROAD_PROBE_V3",
        "status": "NON_DECISIONAL_OPTIMISTIC_ROAD_WITNESS_NOT_SERVICE",
        "source_sha256": {key: digest(paths[key], key in (
            "candidates_normalized_newlines", "road_screen", "bound"))
                          for key in paths},
        "west_ordered_waypoint_ids": [sid for _, sid in w],
        "east_ordered_waypoint_ids": [sid for _, sid in e],
        "represented_via_node_bad_turn_count": bad,
        "represented_fs_joins_allowed": join("wf", "ef") and join("er", "wr"),
        "known_successor_via_way_overlap": overlap,
        "bidirectional_pair_distance_m": round(pair_m, 3),
        "annual_10_pairs_260_days_km_before_extras": round(pair_m * 10 * 260 / 1000, 3),
        "both_direction_encountered_stop_ids_not_boarding_guaranteed": both,
        "brivio_centre_inventory_stop_straight_line_to_road_m_by_direction": nearest,
        "brivio_centre_stop_encountered_both_directions": "FROZEN::300063" in both,
        "not_certified": ["full-history via-way legality", "vehicle suitability",
                          "safe relocated Brivio stop", "walking access",
                          "directional boarding", "timetable", "depot kilometres"],
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
    }


def main(paths, output):
    result = build(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "road_screen", "bound"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "road_screen", "bound")},
         args.output)
