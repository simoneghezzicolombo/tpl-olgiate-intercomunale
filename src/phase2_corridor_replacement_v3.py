"""Scalable deterministic corridor alternatives on the frozen Gate-D graph.

This is intentionally *not* an exhaustive K-shortest-path implementation.
For one OD pair it preserves the certified Gate-D shortest path, then performs
one exact restriction-aware reroute for every distinct OSM way used by that
baseline. Each reroute forbids that baseline way and therefore exposes a
meaningfully different replacement corridor rather than thousands of tiny Yen
spur variants.

The primitive selects no settlement, passenger stop, topology, timetable or
winner. Its design role is corridor diversification after an OD/leg has been
chosen independently.
"""
from __future__ import annotations

from collections import Counter
import heapq
from typing import Any

import pandas as pd

from src.phase2_frozen_graph import (
    build_adjacency,
    build_turn_rule_index,
    restriction_aware_one_to_many,
    transition_allowed,
)

TOL_MIN = 1e-12
TOL_M = 1e-9


def edge_lookup(edges: pd.DataFrame) -> dict[str, dict[str, Any]]:
    required = {
        "edge_id",
        "u_node_id",
        "v_node_id",
        "osm_way_id",
        "length_m",
        "running_minutes_model",
    }
    missing = sorted(required - set(edges.columns))
    if missing:
        raise ValueError(f"Gate-D edge input missing columns: {missing}")
    if edges["edge_id"].astype(str).duplicated().any():
        raise ValueError("Gate-D edge_id values must be unique")
    return {
        str(row.edge_id): {
            "u": str(row.u_node_id),
            "v": str(row.v_node_id),
            "way": str(row.osm_way_id),
            "length_m": float(row.length_m),
            "minutes": float(row.running_minutes_model),
        }
        for row in edges.itertuples(index=False)
    }


def project_path(source: str, edge_ids: list[str], lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    current = str(source)
    nodes = [current]
    ways: list[str] = []
    runtime = 0.0
    distance = 0.0
    for eid in edge_ids:
        edge = lookup[str(eid)]
        if edge["u"] != current:
            raise ValueError(f"Discontinuous path at {eid}: {edge['u']} != {current}")
        current = edge["v"]
        nodes.append(current)
        ways.append(edge["way"])
        runtime += float(edge["minutes"])
        distance += float(edge["length_m"])
    counts = Counter(nodes)
    repeated = sorted(node for node, count in counts.items() if count > 1)
    return {
        "edge_ids": [str(value) for value in edge_ids],
        "physical_nodes": nodes,
        "osm_way_ids": ways,
        "running_minutes_model": runtime,
        "distance_m": distance,
        "physical_loopless": not repeated,
        "repeated_physical_nodes": repeated,
    }


def restriction_aware_route_excluding_ways(
    adjacency: dict,
    rules: dict,
    source: str,
    target: str,
    excluded_osm_way_ids: set[str] | frozenset[str],
) -> dict[str, Any] | None:
    """Exact Gate-D stateful Dijkstra with a deterministic OSM-way exclusion.

    With an empty exclusion set this is required by tests to reproduce
    ``restriction_aware_one_to_many`` exactly.
    """
    source = str(source)
    target = str(target)
    excluded = {str(value) for value in excluded_osm_way_ids}
    if source == target:
        return {"running_minutes_model": 0.0, "distance_m": 0.0, "edge_ids": []}

    start_state = (source, None, None)
    dist = {start_state: 0.0}
    dist_m = {start_state: 0.0}
    previous: dict = {}
    heap = [(0.0, 0.0, source, "", "", start_state)]
    settled = None

    while heap:
        current_min, current_m, _, _, _, state = heapq.heappop(heap)
        if current_min != dist.get(state):
            continue
        node, previous_node, incoming_way = state
        if node == target:
            settled = state
            break
        for outgoing_node, length_m, minutes, outgoing_way, eid in adjacency.get(node, []):
            outgoing_way = str(outgoing_way)
            if outgoing_way in excluded:
                continue
            if not transition_allowed(
                rules,
                node,
                previous_node,
                incoming_way,
                outgoing_node,
                outgoing_way,
            ):
                continue
            next_state = (outgoing_node, node, outgoing_way)
            next_min = current_min + float(minutes)
            next_m = current_m + float(length_m)
            old = dist.get(next_state)
            if old is None or next_min < old - TOL_MIN or (
                abs(next_min - old) <= TOL_MIN and next_m < dist_m[next_state] - TOL_M
            ):
                dist[next_state] = next_min
                dist_m[next_state] = next_m
                previous[next_state] = (state, str(eid))
                heapq.heappush(
                    heap,
                    (next_min, next_m, str(outgoing_node), outgoing_way, str(eid), next_state),
                )

    if settled is None:
        return None
    edges_rev: list[str] = []
    cursor = settled
    while cursor != start_state:
        prev_state, eid = previous[cursor]
        edges_rev.append(eid)
        cursor = prev_state
    return {
        "running_minutes_model": dist[settled],
        "distance_m": dist_m[settled],
        "edge_ids": list(reversed(edges_rev)),
    }


def _path_key(path: dict[str, Any]) -> tuple[Any, ...]:
    return (
        float(path["running_minutes_model"]),
        float(path["distance_m"]),
        tuple(path["edge_ids"]),
    )


def generate_way_replacement_corridors(
    edges: pd.DataFrame,
    rules: pd.DataFrame,
    source_node: str,
    target_node: str,
) -> dict[str, Any]:
    """Enumerate the complete single-baseline-way replacement set for one OD."""
    source = str(source_node)
    target = str(target_node)
    if source == target:
        raise ValueError("Corridor replacement query requires distinct source and target")

    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    lookup = edge_lookup(edges)
    baseline_raw = restriction_aware_one_to_many(adjacency, rule_index, source, {target}).get(target)
    if baseline_raw is None:
        return {
            "certified_baseline_present": False,
            "certified_baseline": None,
            "replacement_corridors": [],
            "baseline_distinct_way_count": 0,
            "replacement_queries_run": 0,
            "replacement_queries_unreachable": 0,
            "replacement_queries_physically_cyclic": 0,
        }

    baseline = project_path(source, list(baseline_raw["edge_ids"]), lookup)
    if baseline["physical_nodes"][-1] != target:
        raise AssertionError("Certified baseline does not terminate at requested target")
    if abs(float(baseline_raw["running_minutes_model"]) - baseline["running_minutes_model"]) > TOL_MIN:
        raise AssertionError("Projected baseline runtime changed Gate-D certified runtime")
    if abs(float(baseline_raw["distance_m"]) - baseline["distance_m"]) > 1e-6:
        raise AssertionError("Projected baseline distance changed Gate-D certified distance")
    baseline["provenance"] = "CERTIFIED_GATE_D_RESTRICTION_AWARE_DIJKSTRA"

    distinct_ways = list(dict.fromkeys(baseline["osm_way_ids"]))
    replacements: dict[tuple[str, ...], dict[str, Any]] = {}
    unreachable = 0
    cyclic = 0
    for banned_way in distinct_ways:
        reroute = restriction_aware_route_excluding_ways(
            adjacency,
            rule_index,
            source,
            target,
            {banned_way},
        )
        if reroute is None:
            unreachable += 1
            continue
        candidate = project_path(source, list(reroute["edge_ids"]), lookup)
        if banned_way in candidate["osm_way_ids"]:
            raise AssertionError(f"Replacement corridor still uses excluded way {banned_way}")
        if candidate["running_minutes_model"] < baseline["running_minutes_model"] - TOL_MIN:
            raise AssertionError("Excluded-way reroute beats certified Gate-D baseline runtime")
        if not candidate["physical_loopless"]:
            cyclic += 1
            continue
        key = tuple(candidate["edge_ids"])
        if key not in replacements:
            candidate["excluded_baseline_osm_way_ids"] = [banned_way]
            candidate["provenance"] = "GATE_D_SINGLE_BASELINE_WAY_REPLACEMENT"
            replacements[key] = candidate
        else:
            replacements[key]["excluded_baseline_osm_way_ids"].append(banned_way)

    ordered = sorted(replacements.values(), key=_path_key)
    for rank, path in enumerate(ordered, start=1):
        path["replacement_rank"] = rank
        path["excluded_baseline_osm_way_ids"] = sorted(path["excluded_baseline_osm_way_ids"])
        path["runtime_penalty_min"] = (
            float(path["running_minutes_model"]) - float(baseline["running_minutes_model"])
        )
        path["distance_penalty_m"] = float(path["distance_m"]) - float(baseline["distance_m"])

    return {
        "certified_baseline_present": True,
        "certified_baseline": baseline,
        "replacement_corridors": ordered,
        "baseline_distinct_way_count": len(distinct_ways),
        "replacement_queries_run": len(distinct_ways),
        "replacement_queries_unreachable": unreachable,
        "replacement_queries_physically_cyclic": cyclic,
        "method_contract": "COMPLETE_SINGLE_BASELINE_OSM_WAY_REPLACEMENT_SET_NOT_K_SHORTEST_NOT_NETWORK_SELECTION",
    }
