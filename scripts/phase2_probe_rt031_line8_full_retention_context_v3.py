"""Optimize both wings' inventory-node orders then compose with via-node memory.

Fixed-order contextual witness, not a global physical optimum or service plan.
"""
import argparse
import json
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, digest, rows
from scripts.phase2_export_rt031_line8_inclusive_shape_v3 import NORTH, itinerary
from scripts.phase2_audit_rt031_line8_waypoint_lower_bound_v3 import minimum_pair_cycle
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph, screen_lobe
from scripts.phase2_probe_rt031_current_stop_repair_v3 import path_stops
from scripts.phase2_rt031_ordered_via_node_path_v3 import ordered_path


def build(paths):
    road = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    prior = json.loads(paths["distance_audit"].read_text(encoding="utf-8"))
    if (road["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3"
            or prior["contract"] != "RT031_LINE8_FIXED_WAYPOINT_DISTANCE_OBJECTIVE_AUDIT_V3"
            or prior["source_sha256"]["road_screen"] != digest(paths["road_screen"], True)):
        raise ValueError("source contract drift")
    reference = prior["variants"]["full_retention_west_order"]["minutes"]
    required = set(reference["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    edges, graph_nodes, rules, attachments = build_graph(paths)
    nodes = {sid: row["graph_node_id"] for sid, row in attachments.items() if row["route_ready"] == "True"}
    nodes[VIRTUAL], nodes[NORTH] = VIRTUAL, road["north_proxy"]["graph_node_id"]
    eligible = {sid: row["graph_node_id"] for sid, row in attachments.items()
                if row["route_ready"] == "True" and row["service_class"] == "CONVENTIONAL_TPL"}
    west, _ = itinerary()
    west = west[:2] + list(reversed(west[2:4])) + list(reversed(west[4:6])) + west[6:]
    wf, wr = (screen_lobe(seq, nodes, edges, rules) for seq in (west, list(reversed(west))))
    western = required & path_stops(wf, edges, eligible) & path_stops(wr, edges, eligible)
    fs = west[0]
    sets = ((western - {fs[1]}, ("Olgiate sud", VIRTUAL)),
            (required - western - {fs[1]}, ("San Zeno/Via Cantu", NORTH)))
    sequences, bounds, cache = [], [], {}
    for ids, extra in sets:
        points = [fs] + [(attachments[sid]["stop_name"], sid) for sid in sorted(ids)] + [extra, fs]
        bound = minimum_pair_cycle(points, nodes, edges, rules, cache=cache)
        lookup = {sid: (label, sid) for label, sid in points}
        sequences.append([lookup[sid] for sid in bound["ordered_waypoint_ids_at_optimistic_minimum"]])
        bounds.append(bound)
    complete = sequences[0] + sequences[1][1:]
    forward = ordered_path(edges, rules, [nodes[sid] for _, sid in complete])
    reverse = ordered_path(edges, rules, [nodes[sid] for _, sid in reversed(complete)])
    if not forward["reachable"] or not reverse["reachable"]:
        raise ValueError("contextual all-inventory path unreachable")
    both = path_stops(forward, edges, eligible) & path_stops(reverse, edges, eligible)
    if not required <= both:
        raise ValueError("all-reference identity guarantee lost")
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for row in successor["successor_via_way_relations"] for way in row["via_way_ids"]}
    overlap = sorted(via_ways & (set(forward["osm_way_ids"]) | set(reverse["osm_way_ids"])))
    pair_m = forward["distance_m"] + reverse["distance_m"]
    policy = json.loads(paths["policy"].read_text(encoding="utf-8"))
    cap = policy["human_policy_decisions"]["annual_bus_km_cap"]
    scenarios = []
    for span in (13, 14, 16):
        count = 4 * 2 + (span - 4)
        km = pair_m / 2000 * count * 260
        scenarios.append({"span_hours": span, "h30_peak_hours": 4,
                          "h60_other_hours": span - 4, "total_traversals_per_day_assumption": count,
                          "annual_model_km_before_extras": round(km, 3),
                          "residual_to_approved_cap_km_before_extras": round(cap - km, 3),
                          "annual_direction_allocation": "equal totals across 260 days; odd daily count requires alternating directional allocation, not a certified timetable"})
    candidate = next(r for r in rows(paths["candidates_normalized_newlines"]) if r["candidate_id"] == "P2V2S_0031")
    coords = {nid: [float(row["lon"]), float(row["lat"])] for nid, row in graph_nodes.items()}
    coords[VIRTUAL] = [float(candidate["lon"]), float(candidate["lat"])]
    lines = []
    for name, part in (("forward", forward), ("reverse", reverse)):
        vertex_ids = [edges[part["_path_edge_ids"][0]]["u_node_id"]]
        for eid in part["_path_edge_ids"]:
            if edges[eid]["u_node_id"] != vertex_ids[-1]:
                raise ValueError("discontinuous contextual geometry")
            vertex_ids.append(edges[eid]["v_node_id"])
        lines.append({"type": "Feature", "properties": {"direction": name,
                       "distance_m": part["distance_m"], "status": "MODELED_PATH_NOT_APPROVED_TPL"},
                      "geometry": {"type": "LineString", "coordinates": [coords[n] for n in vertex_ids]}})
    points = [{"type": "Feature", "properties": {"stop_place_id": sid,
               "name": attachments[sid]["stop_name"], "status": "INVENTORY_ENCOUNTER_NOT_BOARDING_EVENT"},
               "geometry": {"type": "Point", "coordinates": [float(attachments[sid]["lon"]),
                                                                float(attachments[sid]["lat"])]}}
              for sid in sorted(both)]
    for label, sid in (("Olgiate sud", VIRTUAL), ("San Zeno/Via Cantu", NORTH)):
        points.append({"type": "Feature", "properties": {"stop_place_id": sid,
                       "name": label, "status": "NEW_STOP_NEED_NOT_APPROVED"},
                       "geometry": {"type": "Point", "coordinates": coords[nodes[sid]]}})
    flags = {"network_selected": False, "primary_selection_authorised": False,
             "runner_up_selection_authorised": False, "decision_budget_km": None,
             "uncertainty_band_min": None}
    result = {"contract": "RT031_LINE8_ALL_REFERENCE_CONTEXTUAL_ROAD_WITNESS_V3",
              "status": "NON_DECISIONAL_FIXED_ORDER_WITNESS",
              "source_sha256": {key: digest(path, key in (
                  "road_screen", "distance_audit", "policy", "candidates_normalized_newlines"))
                                for key, path in paths.items()},
              "ordered_wings": [[sid for _, sid in seq] for seq in sequences],
              "independent_leg_order_bounds": bounds,
              "pair_distance_m": round(pair_m, 3),
              "directions": {name: {"distance_m": p["distance_m"],
                              "running_minutes_excluding_dwell": p["running_minutes_model"],
                              "edge_ids": p["_path_edge_ids"]} for name, p in (("forward", forward), ("reverse", reverse))},
              "both_direction_encountered_stop_ids_not_boarding_guaranteed": sorted(both),
              "lost_reference_inventory_ids": sorted(required - both),
              "gained_reference_inventory_ids": sorted(both - required),
              "known_successor_via_way_overlap": overlap,
              "represented_via_node_path_verified": True,
              "scenarios": scenarios,
              "not_certified": ["global optimum", "full-history restrictions", "bus suitability",
                                "boarding events", "H30/H60 timetable", "fleet", "depot kilometres"],
              "span_count_semantics": "Frequency-volume scenario only; half-open service window, boundary departures and useful directional headways unverified.",
              **flags}
    shape = {"type": "FeatureCollection", "name": "RT031_LINE8_ALL_REFERENCE_CONTEXTUAL_WITNESS_V3",
             "properties": flags, "features": lines + points}
    return result, shape


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "road_screen", "distance_audit", "policy"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--geojson", required=True, type=Path)
    args = parser.parse_args()
    result, shape = build({key: getattr(args, key) for key in (*EXPECTED, "road_screen", "distance_audit", "policy")})
    for path, value in ((args.output, result), (args.geojson, shape)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n", encoding="utf-8")
