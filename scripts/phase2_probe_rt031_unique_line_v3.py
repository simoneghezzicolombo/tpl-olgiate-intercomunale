"""Conditional RT017 road screen for the caller's single Linea 8 brief.

This does not certify a stop, a composed route, vehicle suitability or timetable.
"""

import argparse
import csv
import gzip
import hashlib
import heapq
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.phase2_audit_rt031_south_road_probe_v3 import (
    EXPECTED, VIRTUAL, digest, projection, rows, shortest,
)
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


WEST = [
    ("FS", "FROZEN::L00407"),
    ("Monticello/Scarpone", "ASF::OLGIATE_MOLGORA_SCARPONE"),
    ("Rovagnate", "FROZEN::300879"),
    ("Perego", "ASF::PEREGO_VIA_STATALE_79"),
    ("Santa Maria Hoe", "FROZEN::300782"),
    ("Olgiate sud", VIRTUAL),
    ("FS", "FROZEN::L00407"),
]
EAST = [
    ("FS", "FROZEN::L00407"),
    ("Calco", "ASF::CALCO_VIA_GARIBALDI"),
    ("Arlate", "ASF::ARLATE_CANTINA_PIROVANO"),
    ("Brivio centro", "FROZEN::300063"),
    ("Beverate", "FROZEN::300398"),
    ("San Zeno/Via Cantu", "PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE"),
    ("FS", "FROZEN::L00407"),
]


def read_anchor(path):
    with path.open(encoding="utf-8", newline="") as stream:
        anchor = next(r for r in csv.DictReader(stream) if r["anchor_id"] == "SAN_ZENO")
    if anchor["epistemic_status"] != "ASSUMPTION":
        raise ValueError("San Zeno anchor semantics drift")
    return float(anchor["lat"]), float(anchor["lon"])


def build_graph(paths):
    for label in ("edges", "nodes", "rules", "attachments", "successor",
                  "candidates_normalized_newlines"):
        if digest(paths[label], label.endswith("normalized_newlines")) != EXPECTED[label]:
            raise ValueError(f"pinned input drift: {label}")
    edges = {r["edge_id"]: r for r in rows(paths["edges"])}
    nodes = {r["node_id"]: r for r in rows(paths["nodes"])}
    rules = rows(paths["rules"])
    attachments = {r["stop_place_id"]: r for r in rows(paths["attachments"])}
    candidate = next(r for r in rows(paths["candidates_normalized_newlines"])
                     if r["candidate_id"] == "P2V2S_0031")
    if candidate["physical_status"] != "FIELD_CHECK_PENDING" or candidate["osm_way_id"] != "40627763":
        raise ValueError("south candidate drift")
    point = float(candidate["x_utm32"]), float(candidate["y_utm32"])
    options = []
    for row in edges.values():
        if row["osm_way_id"] == candidate["osm_way_id"]:
            a, b = nodes[row["u_node_id"]], nodes[row["v_node_id"]]
            t, d = projection(point, (float(a["x"]), float(a["y"])),
                              (float(b["x"]), float(b["y"])))
            options.append((d, row["edge_id"], t))
    d, eid, _ = min(options)
    if d > 1:
        raise ValueError("south candidate off road segment")
    segment = edges[eid]
    endpoints = {segment["u_node_id"], segment["v_node_id"]}
    segment_edges = [r for r in edges.values() if r["osm_way_id"] == candidate["osm_way_id"]
                     and {r["u_node_id"], r["v_node_id"]} == endpoints]
    if len(segment_edges) != 2:
        raise ValueError("south segment is not bidirectional in model")
    for row in segment_edges:
        a, b = nodes[row["u_node_id"]], nodes[row["v_node_id"]]
        t, offset = projection(point, (float(a["x"]), float(a["y"])),
                               (float(b["x"]), float(b["y"])))
        if offset > 1 or not 0 < t < 1:
            raise ValueError("south segment projection ambiguous")
        for suffix, u, v, share in (("IN", row["u_node_id"], VIRTUAL, t),
                                    ("OUT", VIRTUAL, row["v_node_id"], 1 - t)):
            new_id = row["edge_id"] + "::" + suffix
            edges[new_id] = {**row, "edge_id": new_id, "u_node_id": u,
                             "v_node_id": v, "length_m": str(float(row["length_m"]) * share),
                             "running_minutes_model": str(float(row["running_minutes_model"]) * share)}
    return edges, nodes, rules, attachments


def screen_lobe(lobe, attachment_nodes, edges, rules):
    legs, path = [], []
    for (from_label, from_id), (to_label, to_id) in zip(lobe, lobe[1:]):
        leg = shortest(edges, rules, attachment_nodes[from_id], attachment_nodes[to_id])
        if leg is None:
            return {"reachable": False, "failed_leg": [from_label, to_label]}
        legs.append({"from": from_label, "to": to_label,
                     "distance_m": leg["distance_m"],
                     "running_minutes_model": leg["running_minutes_model"]})
        path.extend(leg["edge_ids"])
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                         unresolved_external_via_way_count=2)
    bad_turns = []
    for i in range(1, len(path)):
        if edges[path[i-1]]["v_node_id"] != edges[path[i]]["u_node_id"]:
            raise ValueError("disconnected leg seam")
        if adapter.decision((path[i-1],), path[i])["allowed"] is not True:
            bad_turns.append(i)
    return {"reachable": True, "ordered_waypoints": [label for label, _ in lobe],
            "legs": legs, "distance_m": round(sum(x["distance_m"] for x in legs), 3),
            "running_minutes_model": round(sum(x["running_minutes_model"] for x in legs), 6),
            "via_node_bad_turn_indices_at_leg_seams_or_within_legs": bad_turns,
            "path_edge_count": len(path),
            "path_edge_id_sha256": hashlib.sha256("\n".join(path).encode()).hexdigest(),
            "_path_edge_ids": path,
            "osm_way_ids": sorted({edges[e]["osm_way_id"] for e in path})}


def unconstrained_distance(edges, source, target):
    """Optimistic road distance; omits all turn and vehicle restrictions."""
    outgoing = defaultdict(list)
    for edge in edges.values():
        outgoing[edge["u_node_id"]].append((edge["v_node_id"], float(edge["length_m"])))
    heap, best = [(0.0, source)], {source: 0.0}
    while heap:
        distance, node = heapq.heappop(heap)
        if distance != best[node]:
            continue
        if node == target:
            return distance
        for next_node, length in outgoing[node]:
            new_distance = distance + length
            if new_distance < best.get(next_node, float("inf")):
                best[next_node] = new_distance
                heapq.heappush(heap, (new_distance, next_node))
    return None


def main(paths, output):
    edges, nodes, rules, attachments = build_graph(paths)
    anchor_lat, anchor_lon = read_anchor(paths["anchor"])
    via_cantu_nodes = {r["u_node_id"] for r in edges.values()
                       if r["osm_way_id"] == "581532442"}
    via_cantu_nodes |= {r["v_node_id"] for r in edges.values()
                        if r["osm_way_id"] == "581532442"}
    if not via_cantu_nodes:
        raise ValueError("Via Cantu missing from frozen graph")
    north_node = min(via_cantu_nodes, key=lambda n: (
        (float(nodes[n]["lat"]) - anchor_lat) ** 2
        + (float(nodes[n]["lon"]) - anchor_lon) ** 2, n))
    node_lat, node_lon = float(nodes[north_node]["lat"]), float(nodes[north_node]["lon"])
    lat_delta = math.radians(node_lat - anchor_lat)
    lon_delta = math.radians(node_lon - anchor_lon)
    haversine_term = (math.sin(lat_delta / 2) ** 2
                      + math.cos(math.radians(anchor_lat)) * math.cos(math.radians(node_lat))
                      * math.sin(lon_delta / 2) ** 2)
    north_proxy_air_distance_m = 2 * 6371000 * math.asin(min(1, math.sqrt(haversine_term)))
    selected = {stop for _, stop in WEST + EAST if stop.startswith(("FROZEN::", "ASF::"))}
    if any(attachments[s]["route_ready"] != "True" for s in selected):
        raise ValueError("representative stop attachment not route ready")
    attachment_nodes = {s: attachments[s]["graph_node_id"] for s in selected}
    attachment_nodes[VIRTUAL] = VIRTUAL
    attachment_nodes["PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE"] = north_node
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    via_ways = {way for r in successor["successor_via_way_relations"]
                for way in r["via_way_ids"]}
    screens = {}
    for label, itinerary in (("west_toward_south", WEST), ("west_reverse", list(reversed(WEST))),
                             ("east_toward_cantu", EAST), ("east_reverse", list(reversed(EAST)))):
        screen = screen_lobe(itinerary, attachment_nodes, edges, rules)
        if screen["reachable"]:
            bounds = [unconstrained_distance(edges, attachment_nodes[a[1]],
                                             attachment_nodes[b[1]])
                      for a, b in zip(itinerary, itinerary[1:])]
            if any(value is None for value in bounds):
                raise ValueError("unconstrained lower bound unreachable")
            screen["unconstrained_distance_lower_bound_m"] = round(sum(bounds), 3)
            screen["known_successor_via_way_overlap"] = sorted(
                via_ways & set(screen.pop("osm_way_ids")))
        screens[label] = screen
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                         unresolved_external_via_way_count=2)

    def joint(a, b):
        left, right = screens[a]["_path_edge_ids"], screens[b]["_path_edge_ids"]
        same_node = edges[left[-1]]["v_node_id"] == edges[right[0]]["u_node_id"]
        decision = adapter.decision((left[-1],), right[0]) if same_node else None
        return {"same_fs_graph_node": same_node,
                "represented_via_node_turn_allowed": decision is not None and decision["allowed"] is True,
                "incoming_edge_id": left[-1], "outgoing_edge_id": right[0]}

    fs_joins = {
        "west_to_east": joint("west_toward_south", "east_toward_cantu"),
        "east_reverse_to_west_reverse": joint("east_reverse", "west_reverse"),
        "forward_to_reverse_vehicle_continuation": joint("east_toward_cantu", "east_reverse"),
        "reverse_to_forward_vehicle_continuation": joint("west_reverse", "west_toward_south"),
    }
    west_core = WEST[:-2] + WEST[-1:]
    east_core = EAST[:-2] + EAST[-1:]
    south, north = WEST[-2], EAST[-2]
    allocations = {
        "SOUTH_WEST_NORTH_EAST": (WEST, EAST),
        "NORTH_WEST_SOUTH_EAST": (west_core[:-1] + [north] + west_core[-1:],
                                  east_core[:-1] + [south] + east_core[-1:]),
        "BOTH_WEST_SOUTH_NORTH": (west_core[:-1] + [south, north] + west_core[-1:],
                                  east_core),
        "BOTH_WEST_NORTH_SOUTH": (west_core[:-1] + [north, south] + west_core[-1:],
                                  east_core),
        "BOTH_EAST_SOUTH_NORTH": (west_core,
                                  east_core[:-1] + [south, north] + east_core[-1:]),
        "BOTH_EAST_NORTH_SOUTH": (west_core,
                                  east_core[:-1] + [north, south] + east_core[-1:]),
    }
    allocation_sensitivity = {}
    for name, (west_points, east_points) in allocations.items():
        outward = [screen_lobe(lobe, attachment_nodes, edges, rules)
                   for lobe in (west_points, east_points)]
        reverse = [screen_lobe(list(reversed(lobe)), attachment_nodes, edges, rules)
                   for lobe in (west_points, east_points)]
        directional = {}
        for label, lobes in (("outward", outward), ("reverse", reverse)):
            directional[label] = {
                "reachable": all(lobe["reachable"] for lobe in lobes),
                "distance_m": round(sum(lobe["distance_m"] for lobe in lobes), 3)
                if all(lobe["reachable"] for lobe in lobes) else None,
                "via_node_bad_turn_count": sum(len(lobe["via_node_bad_turn_indices_at_leg_seams_or_within_legs"])
                                                for lobe in lobes if lobe["reachable"]),
            }
        allocation_sensitivity[name] = directional
    forward_m = screens["west_toward_south"]["distance_m"] + screens["east_toward_cantu"]["distance_m"]
    reverse_m = screens["west_reverse"]["distance_m"] + screens["east_reverse"]["distance_m"]
    forward_bound_m = (screens["west_toward_south"]["unconstrained_distance_lower_bound_m"]
                       + screens["east_toward_cantu"]["unconstrained_distance_lower_bound_m"])
    reverse_bound_m = (screens["west_reverse"]["unconstrained_distance_lower_bound_m"]
                       + screens["east_reverse"]["unconstrained_distance_lower_bound_m"])
    payload = {
        "contract": "RT031_UNIQUE_LINE_ROAD_SCREEN_V3",
        "status": "CONDITIONAL_WAYPOINT_SHORTEST_PATH_DIAGNOSTIC",
        "source_sha256": {key: digest(paths[key], key in ("candidates_normalized_newlines", "anchor"))
                          for key in paths},
        "north_proxy": {"anchor_status": "ASSUMPTION", "road_way_id": "581532442",
                        "graph_node_id": north_node,
                        "straight_line_distance_from_anchor_m": round(north_proxy_air_distance_m, 3),
                        "boarding_stop_certified": False},
        "south_proxy": {"candidate_id": "P2V2S_0031", "physical_status": "FIELD_CHECK_PENDING",
                        "boarding_stop_certified": False},
        "representative_stop_ids_are_not_selected_stops": True,
        "leg_joint_global_path_optimality_certified": False,
        "full_history_via_way_composition_certified": False,
        "west_east_join_at_fs_legal_continuity_certified": False,
        "vehicle_suitability_certified": False,
        "timetable_certified": False,
        "screens": screens,
        "fs_joins": fs_joins,
        "allocation_sensitivity": allocation_sensitivity,
        "allocation_sensitivity_semantics": "fastest independent road legs at the same representative points; no stop, full-history, or timetable certification",
        "conditional_complete_cycle": {
            "west_then_east_distance_m": round(forward_m, 3),
            "opposite_direction_distance_m": round(reverse_m, 3),
            "west_then_east_unconstrained_lower_bound_m": round(forward_bound_m, 3),
            "opposite_direction_unconstrained_lower_bound_m": round(reverse_bound_m, 3),
            "unit": "one complete west and east traversal, not a bus departure or vehicle block",
        },
        "illustrative_production_arithmetic": {
            "service_days_assumption": 260,
            "policy_cap_bus_km_per_year": 111419,
            "policy_cap_source": "config/phase2_final_policy_contract_v3.json",
            "nominal_span_hours": 16,
            "nominal_peak_hours": 4,
            "nominal_base_hours": 12,
            "nominal_complete_traversals_per_direction_for_h30_peak_h60_base": 20,
            "nominal_complete_traversals_total_if_both_directions": 40,
            "annual_km_for_10_complete_traversals_per_direction": round(
                (forward_m + reverse_m) * 10 * 260 / 1000, 3),
            "annual_unconstrained_lower_bound_km_for_10_per_direction": round(
                (forward_bound_m + reverse_bound_m) * 10 * 260 / 1000, 3),
            "annual_km_for_nominal_20_complete_traversals_per_direction": round(
                (forward_m + reverse_m) * 20 * 260 / 1000, 3),
            "annual_unconstrained_lower_bound_km_for_nominal_20_per_direction": round(
                (forward_bound_m + reverse_bound_m) * 20 * 260 / 1000, 3),
            "meaning": "conditional arithmetic only; timetable events, exact boundary departures, vehicle blocks and passenger headways unverified",
        },
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
    }
    for screen in screens.values():
        screen.pop("_path_edge_ids", None)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "anchor"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "anchor")}, args.output)
