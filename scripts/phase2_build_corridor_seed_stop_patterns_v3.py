#!/usr/bin/env python3
"""Build two non-decision V3 corridor seeds with full passenger stop patterns.

This is the first RT-005 regression test that proves structural waypoints and
passenger stops are separate objects.

The human-defined seed specifies only service areas. Each service area is
resolved to an existing official, route-ready physical stop using transparent
identity/proximity evidence. All permutations of those area waypoints are then
materialised and the minimum frozen-graph running-time loop is selected as a
*seed ordering heuristic*, not as a network ranking. The exact frozen Gate-D
path is rebuilt and every existing official stop cluster whose snapped graph
node lies exactly on that path is inserted into the passenger stop pattern.

No proposed FIELD_CHECK_PENDING stop is allowed in this first seed. No topology,
headway, winner, PRIMARY or RUNNER-UP is selected.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd

from src.phase2_frozen_graph import (
    build_adjacency,
    build_turn_rule_index,
    restriction_aware_one_to_many,
)
from src.phase2_reduced_path_matrix import load_frozen_graph_inputs

HUB = "rail:S01514"
STUDY_MUNICIPALITIES = {
    "Olgiate Molgora", "Calco", "Brivio", "Santa Maria Hoè", "La Valletta Brianza"
}
ORDERING_SEMANTICS = "MIN_FROZEN_GRAPH_RUNNING_TIME_WITHIN_HUMAN_DEFINED_SERVICE_AREA_SET_NOT_NETWORK_RANKING"
INTERPOLATION_SEMANTICS = "EXISTING_OFFICIAL_STOPS_ON_EXACT_FROZEN_GRAPH_PATH_NODE_ONLY"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def truth(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(a))


def percentile(values: list[float], q: float) -> float:
    xs = sorted(values)
    if not xs:
        raise ValueError("percentile requires values")
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    f = pos - lo
    return xs[lo] * (1 - f) + xs[hi] * f


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if not rows:
        raise ValueError(f"Refusing empty output {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def select_existing_waypoint_options(seed_rows, options_rows, membership_rows):
    membership = {
        row["source_anchor_id"]: row
        for row in membership_rows
        if row.get("source_anchor_id")
    }
    selected = []
    for seed in seed_rows:
        area = seed["area_id"]
        candidates = []
        seen = set()
        for row in options_rows:
            if row.get("area_id") != area or row.get("option_class") != "EXISTING_OFFICIAL":
                continue
            stop_id = row.get("stop_or_candidate_id", "")
            if not stop_id or stop_id in seen:
                continue
            seen.add(stop_id)
            source_anchor = f"existing:{stop_id}"
            member = membership.get(source_anchor)
            if not member or not truth(member.get("route_ready", "")) or not member.get("routing_anchor_id"):
                continue
            same_municipality = row.get("option_municipality") == row.get("area_municipality")
            candidates.append({
                **row,
                "source_anchor_id": source_anchor,
                "routing_anchor_id": member["routing_anchor_id"],
                "graph_node_id": member["graph_node_id"],
                "same_municipality": same_municipality,
            })
        if not candidates:
            raise AssertionError(f"No route-ready existing official stop option for {area}")
        candidates.sort(key=lambda r: (
            0 if r["same_municipality"] else 1,
            -int(r.get("name_match_strength") or 0),
            float(r.get("distance_to_area_anchor_m_geodesic") or 1e12),
            r["stop_or_candidate_id"],
        ))
        chosen = candidates[0]
        selected.append({
            "seed_id": seed["seed_id"],
            "seed_label": seed["seed_label"],
            "area_id": area,
            "area_name": chosen["area_name"],
            "area_municipality": chosen["area_municipality"],
            "selected_physical_cluster_id": chosen["stop_or_candidate_id"],
            "selected_source_anchor_id": chosen["source_anchor_id"],
            "selected_routing_anchor_id": chosen["routing_anchor_id"],
            "selected_graph_node_id": chosen["graph_node_id"],
            "selected_human_label": chosen["human_label"],
            "selected_option_municipality": chosen["option_municipality"],
            "name_match_strength": chosen["name_match_strength"],
            "name_match_kind": chosen["name_match_kind"],
            "distance_to_area_anchor_m_geodesic": chosen["distance_to_area_anchor_m_geodesic"],
            "official_routes_reference_gtfs": chosen["official_routes_reference_gtfs"],
            "selection_semantics": "EXISTING_OFFICIAL_ROUTE_READY_SAME_MUNICIPALITY_THEN_NAME_MATCH_THEN_PROXIMITY_SEED_HEURISTIC",
            "automatic_network_recommendation": "false",
        })
    return selected


def build_matrix_lookup(matrix_path: Path):
    lookup = {}
    with matrix_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            lookup[(row["origin"], row["destination"])] = {
                "runtime_min": float(row["runtime_min"]),
                "distance_km": float(row["distance_km"]),
                "uncertainty": row["uncertainty"],
                "unknown_access_edge_count": int(row["unknown_access_edge_count"]),
                "service_road_edge_count": int(row["service_road_edge_count"]),
            }
    return lookup


def enumerate_orders(seed_id: str, waypoints, matrix):
    rows = []
    for perm in itertools.permutations(waypoints):
        anchors = [HUB] + [row["selected_routing_anchor_id"] for row in perm] + [HUB]
        total_runtime = total_distance = 0.0
        max_unknown = 0
        service_edges = 0
        valid = True
        uncertainties = []
        for a, b in zip(anchors[:-1], anchors[1:]):
            leg = matrix.get((a, b))
            if not leg:
                valid = False
                break
            total_runtime += leg["runtime_min"]
            total_distance += leg["distance_km"]
            max_unknown = max(max_unknown, leg["unknown_access_edge_count"])
            service_edges += leg["service_road_edge_count"]
            uncertainties.append(leg["uncertainty"])
        rows.append({
            "seed_id": seed_id,
            "waypoint_area_order": "|".join(row["area_id"] for row in perm),
            "waypoint_routing_anchor_order": "|".join(anchors),
            "valid_all_legs": str(valid).lower(),
            "total_running_min": f"{total_runtime:.9f}" if valid else "",
            "total_distance_km": f"{total_distance:.9f}" if valid else "",
            "max_unknown_access_edge_count_on_leg": max_unknown if valid else "",
            "service_road_edge_count_sum_by_leg": service_edges if valid else "",
            "leg_uncertainty_values": "|".join(uncertainties) if valid else "",
            "ordering_semantics": ORDERING_SEMANTICS,
            "selected_seed_order": "false",
        })
    valid_rows = [r for r in rows if r["valid_all_legs"] == "true"]
    if not valid_rows:
        raise AssertionError(f"No valid complete permutation for seed {seed_id}")
    valid_rows.sort(key=lambda r: (
        float(r["total_running_min"]), float(r["total_distance_km"]), r["waypoint_area_order"]
    ))
    chosen_order = valid_rows[0]["waypoint_area_order"]
    for row in rows:
        if row["waypoint_area_order"] == chosen_order and row["valid_all_legs"] == "true":
            row["selected_seed_order"] = "true"
            break
    chosen_waypoints = next(
        perm for perm in itertools.permutations(waypoints)
        if "|".join(row["area_id"] for row in perm) == chosen_order
    )
    return rows, list(chosen_waypoints)


def exact_leg_path(origin_anchor, destination_anchor, routing_nodes, adjacency, rule_index, edge_lookup):
    origin_node = routing_nodes[origin_anchor]
    destination_node = routing_nodes[destination_anchor]
    result = restriction_aware_one_to_many(adjacency, rule_index, origin_node, {destination_node}).get(destination_node)
    if result is None:
        raise AssertionError(f"Frozen graph cannot route {origin_anchor} -> {destination_anchor}")
    nodes = [origin_node]
    current = origin_node
    for edge_id in result["edge_ids"]:
        edge = edge_lookup[edge_id]
        if str(edge.u_node_id) != current:
            raise AssertionError(f"Broken directed edge ordering at {edge_id}: {current} -> {edge.u_node_id}")
        current = str(edge.v_node_id)
        nodes.append(current)
    if current != destination_node:
        raise AssertionError("Exact path failed to reach destination node")
    return result, nodes


def build_existing_stop_index(foundation_rows, membership_rows):
    foundation = {row["stop_foundation_id"]: row for row in foundation_rows}
    by_node: dict[str, list[dict[str, str]]] = {}
    for member in membership_rows:
        source = member.get("source_anchor_id", "")
        if not source.startswith("existing:") or not truth(member.get("route_ready", "")):
            continue
        f = foundation.get(source)
        if not f or f.get("stop_class") != "EXISTING_OFFICIAL":
            continue
        enriched = {**f, "graph_node_id": member["graph_node_id"], "routing_anchor_id": member["routing_anchor_id"]}
        by_node.setdefault(member["graph_node_id"], []).append(enriched)
    for node in by_node:
        by_node[node].sort(key=lambda r: (r["physical_cluster_id"], r["source_stop_id"]))
    return by_node


def build_corridor(seed_id, ordered_waypoints, routing_nodes, adjacency, rules, edge_lookup, existing_by_node, hub_member, matrix):
    routing_order = [HUB] + [row["selected_routing_anchor_id"] for row in ordered_waypoints] + [HUB]
    area_by_routing = {row["selected_routing_anchor_id"]: row["area_id"] for row in ordered_waypoints}
    leg_rows = []
    full_nodes = []
    all_edge_ids = []
    total_runtime = total_distance_m = 0.0
    for leg_index, (origin, destination) in enumerate(zip(routing_order[:-1], routing_order[1:]), start=1):
        path, nodes = exact_leg_path(origin, destination, routing_nodes, adjacency, rules, edge_lookup)
        matrix_leg = matrix[(origin, destination)]
        if abs(path["running_minutes_model"] - matrix_leg["runtime_min"]) > 1e-6:
            raise AssertionError(f"Runtime mismatch rebuilding {origin}->{destination}")
        if abs(path["distance_m"] / 1000.0 - matrix_leg["distance_km"]) > 1e-6:
            raise AssertionError(f"Distance mismatch rebuilding {origin}->{destination}")
        if full_nodes and nodes[0] == full_nodes[-1]:
            full_nodes.extend(nodes[1:])
        else:
            full_nodes.extend(nodes)
        all_edge_ids.extend(path["edge_ids"])
        total_runtime += path["running_minutes_model"]
        total_distance_m += path["distance_m"]
        leg_rows.append({
            "seed_id": seed_id,
            "leg_sequence": leg_index,
            "origin_routing_anchor_id": origin,
            "destination_routing_anchor_id": destination,
            "origin_area_id": "HUB" if origin == HUB else area_by_routing.get(origin, ""),
            "destination_area_id": "HUB" if destination == HUB else area_by_routing.get(destination, ""),
            "distance_km": f"{path['distance_m']/1000.0:.9f}",
            "running_min": f"{path['running_minutes_model']:.9f}",
            "edge_count": len(path["edge_ids"]),
            "path_node_count": len(nodes),
            "path_edge_ids": ";".join(path["edge_ids"]),
            "path_semantics": "EXACT_RESTRICTION_AWARE_SHORTEST_RUNNING_TIME_PATH_ON_FROZEN_GATE_D_GRAPH",
        })

    stop_occurrences = []
    # Hub is explicit start and end. Intermediate path-node encounters with the hub are flagged, not silently inserted.
    hub_node = routing_nodes[HUB]
    intermediate_hub_node_positions = [i for i, node in enumerate(full_nodes[1:-1], start=1) if node == hub_node]
    occurrence = 0

    def add_stop(stop_id, label, municipality, lat, lon, graph_node, node_position, stop_class, selected_area_id=""):
        nonlocal occurrence
        occurrence += 1
        stop_occurrences.append({
            "seed_id": seed_id,
            "stop_sequence": occurrence,
            "stop_foundation_id": stop_id,
            "human_label": label,
            "municipality": municipality,
            "lat": lat,
            "lon": lon,
            "graph_node_id": graph_node,
            "path_node_position": node_position,
            "stop_class": stop_class,
            "selected_service_area_id": selected_area_id,
            "interpolation_semantics": INTERPOLATION_SEMANTICS,
        })

    add_stop(HUB, hub_member.get("source_name", "Olgiate-Calco-Brivio"), "Olgiate Molgora", hub_member.get("lat", ""), hub_member.get("lon", ""), hub_node, 0, "HUB_RAIL")
    seen_occurrence_keys = set()
    selected_source_to_area = {row["selected_source_anchor_id"]: row["area_id"] for row in ordered_waypoints}
    for node_position, node in enumerate(full_nodes[1:-1], start=1):
        for stop in existing_by_node.get(node, []):
            key = (node_position, stop["stop_foundation_id"])
            if key in seen_occurrence_keys:
                continue
            seen_occurrence_keys.add(key)
            add_stop(
                stop["stop_foundation_id"], stop["human_label"], stop["municipality"],
                stop["lat"], stop["lon"], node, node_position, "EXISTING_OFFICIAL",
                selected_source_to_area.get(stop["stop_foundation_id"], ""),
            )
    add_stop(HUB, hub_member.get("source_name", "Olgiate-Calco-Brivio"), "Olgiate Molgora", hub_member.get("lat", ""), hub_member.get("lon", ""), hub_node, len(full_nodes)-1, "HUB_RAIL")

    selected_sources = {row["selected_source_anchor_id"] for row in ordered_waypoints}
    appeared = {row["stop_foundation_id"] for row in stop_occurrences}
    missing_selected = sorted(selected_sources - appeared)
    if missing_selected:
        raise AssertionError(f"Selected service-area waypoints did not appear as passenger stops: {missing_selected}")

    geodesic_gaps = []
    for left, right in zip(stop_occurrences[:-1], stop_occurrences[1:]):
        if not all(str(x).strip() for x in (left["lat"], left["lon"], right["lat"], right["lon"])):
            continue
        geodesic_gaps.append(haversine_m(float(left["lat"]), float(left["lon"]), float(right["lat"]), float(right["lon"])))

    summary = {
        "seed_id": seed_id,
        "service_area_waypoint_order": "|".join(row["area_id"] for row in ordered_waypoints),
        "routing_anchor_order": "|".join(routing_order),
        "structural_nonhub_waypoint_count": len(ordered_waypoints),
        "passenger_stop_occurrence_count_including_closing_hub": len(stop_occurrences),
        "comparable_stop_position_count_excluding_closing_hub": len(stop_occurrences) - 1,
        "unique_nonhub_passenger_stop_count": len({r["stop_foundation_id"] for r in stop_occurrences if r["stop_class"] != "HUB_RAIL"}),
        "total_distance_km": f"{total_distance_m/1000.0:.9f}",
        "running_min_without_added_stop_dwell": f"{total_runtime:.9f}",
        "intermediate_hub_reentry_count": len(intermediate_hub_node_positions),
        "intermediate_hub_path_positions": "|".join(map(str, intermediate_hub_node_positions)),
        "median_consecutive_stop_geodesic_m": f"{percentile(geodesic_gaps,.5):.3f}" if geodesic_gaps else "",
        "p90_consecutive_stop_geodesic_m": f"{percentile(geodesic_gaps,.9):.3f}" if geodesic_gaps else "",
        "max_consecutive_stop_geodesic_m": f"{max(geodesic_gaps):.3f}" if geodesic_gaps else "",
        "municipalities_with_explicit_passenger_stop": "|".join(sorted({r["municipality"].replace("HoÃ¨","Hoè") for r in stop_occurrences if r["municipality"]})),
        "ordering_semantics": ORDERING_SEMANTICS,
        "interpolation_semantics": INTERPOLATION_SEMANTICS,
        "seed_is_network_recommendation": "false",
    }
    return leg_rows, stop_occurrences, summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed-config", type=Path, required=True)
    p.add_argument("--service-options", type=Path, required=True)
    p.add_argument("--membership", type=Path, required=True)
    p.add_argument("--routing-anchors", type=Path, required=True)
    p.add_argument("--foundation", type=Path, required=True)
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--frozen-dir", type=Path, required=True)
    p.add_argument("--spacing-benchmark", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    seed_config = read_csv(args.seed_config)
    options = read_csv(args.service_options)
    membership = read_csv(args.membership)
    foundation = read_csv(args.foundation)
    spacing = json.loads(args.spacing_benchmark.read_text(encoding="utf-8"))
    if spacing["status"] != "PASS_CURRENT_STOP_SPACING_BENCHMARK_V3":
        raise AssertionError("Spacing benchmark is not PASS")

    seed_ids = sorted({row["seed_id"] for row in seed_config})
    if seed_ids != ["EAST_BASE", "WEST_BASE"]:
        raise AssertionError(f"Unexpected seed set {seed_ids}")

    selected_waypoints = []
    for seed_id in seed_ids:
        seed_rows = [row for row in seed_config if row["seed_id"] == seed_id]
        selected_waypoints.extend(select_existing_waypoint_options(seed_rows, options, membership))

    matrix = build_matrix_lookup(args.matrix)
    order_rows = []
    selected_order_by_seed = {}
    for seed_id in seed_ids:
        wps = [row for row in selected_waypoints if row["seed_id"] == seed_id]
        candidates, chosen = enumerate_orders(seed_id, wps, matrix)
        order_rows.extend(candidates)
        selected_order_by_seed[seed_id] = chosen

    nodes, edges, rules, _ = load_frozen_graph_inputs(args.frozen_dir)
    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    edge_lookup = {str(row.edge_id): row for row in edges.itertuples(index=False)}
    routing_rows = read_csv(args.routing_anchors)
    routing_nodes = {row["anchor_id"]: row["graph_node_id"] for row in routing_rows}
    if HUB not in routing_nodes:
        raise AssertionError("Hub missing from routing anchor universe")
    membership_by_source = {row["source_anchor_id"]: row for row in membership}
    hub_member = membership_by_source.get(HUB)
    if not hub_member:
        raise AssertionError("Hub missing from routing membership")
    existing_by_node = build_existing_stop_index(foundation, membership)

    leg_rows = []
    passenger_rows = []
    summaries = []
    for seed_id in seed_ids:
        legs, passengers, summary = build_corridor(
            seed_id, selected_order_by_seed[seed_id], routing_nodes,
            adjacency, rule_index, edge_lookup, existing_by_node, hub_member, matrix
        )
        leg_rows.extend(legs); passenger_rows.extend(passengers); summaries.append(summary)

    # Pair-level territorial guard: these two seeds are a regression fixture for five-municipality explicit service.
    municipalities = set()
    for row in passenger_rows:
        name = row["municipality"].replace("HoÃ¨", "Hoè")
        if name:
            municipalities.add(name)
    missing_municipalities = sorted(STUDY_MUNICIPALITIES - municipalities)

    current_median_stops = float(spacing["pattern_stop_count"]["median_trip_weighted"])
    current_p90_gap = float(spacing["segment_geodesic_distance_m"]["p90_trip_weighted"])
    for summary in summaries:
        stop_positions = int(summary["comparable_stop_position_count_excluding_closing_hub"])
        p90 = float(summary["p90_consecutive_stop_geodesic_m"]) if summary["p90_consecutive_stop_geodesic_m"] else 0.0
        summary["below_current_trip_weighted_median_stop_count"] = str(stop_positions < current_median_stops).lower()
        summary["p90_gap_above_current_trip_weighted_p90"] = str(p90 > current_p90_gap).lower()
        summary["benchmark_semantics"] = "DESCRIPTIVE_ANOMALY_FLAGS_ONLY_NOT_REJECTION_THRESHOLDS"

    out = args.output_dir
    write_csv(out / "corridor_seed_waypoints_v3.csv", selected_waypoints)
    write_csv(out / "corridor_seed_order_candidates_v3.csv", order_rows)
    write_csv(out / "corridor_seed_paths_v3.csv", leg_rows)
    write_csv(out / "corridor_seed_passenger_stops_v3.csv", passenger_rows)
    write_csv(out / "corridor_seed_summary_v3.csv", summaries)

    validation = {
        "status": "PASS_CORRIDOR_SEED_FULL_STOP_PATTERN_V3" if not missing_municipalities else "FAIL_TERRITORIAL_GUARD",
        "contract": "NON_DECISION_CORRIDOR_SEED_WITH_SEPARATE_FULL_PASSENGER_STOP_PATTERN",
        "seed_corridor_count": len(seed_ids),
        "seed_ids": seed_ids,
        "route_generation_scope": "REGRESSION_AND_METHOD_VALIDATION_ONLY",
        "topology_ranked": False,
        "headway_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "winner_implied": False,
        "proposed_stops_used": False,
        "structural_waypoints_equated_to_passenger_stops": False,
        "ordering_semantics": ORDERING_SEMANTICS,
        "interpolation_semantics": INTERPOLATION_SEMANTICS,
        "study_municipalities_with_explicit_passenger_stop_across_pair": sorted(municipalities & STUDY_MUNICIPALITIES),
        "study_municipalities_missing_explicit_stop_across_pair": missing_municipalities,
        "all_five_study_municipalities_explicitly_served_across_pair": not missing_municipalities,
        "at_least_one_corridor_has_more_passenger_stops_than_structural_waypoints": any(
            int(r["unique_nonhub_passenger_stop_count"]) > int(r["structural_nonhub_waypoint_count"]) for r in summaries
        ),
        "current_spacing_benchmark_used_as_rejection_threshold": False,
        "summary": summaries,
        "lineage": {
            "seed_config_sha256": sha256_path(args.seed_config),
            "service_options_sha256": sha256_path(args.service_options),
            "membership_sha256": sha256_path(args.membership),
            "routing_anchors_sha256": sha256_path(args.routing_anchors),
            "foundation_sha256": sha256_path(args.foundation),
            "matrix_sha256": sha256_path(args.matrix),
            "spacing_benchmark_sha256": sha256_path(args.spacing_benchmark),
        },
    }
    (out / "corridor_seed_v3_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if validation["status"] != "PASS_CORRIDOR_SEED_FULL_STOP_PATTERN_V3":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
