"""Restriction-aware K-shortest loopless corridor paths for Phase 2 V3.

This module does not choose a network, stop pattern, topology or winner. It
reuses the frozen Gate-D bus graph and preserves its turn semantics while
exposing deterministic alternative road paths.

Two contracts are deliberately separate:

1. **routing equivalence**: the historical Gate-D restriction-aware Dijkstra
   remains the authoritative shortest legal road path and must be exactly
   representable in the edge-state graph;
2. **corridor admissibility**: a future bus corridor must not revisit a physical
   road node. A legal shortest path that contains a manoeuvre loop therefore
   remains valid routing evidence but is not emitted as a loopless corridor.

Each directed Gate-D ``edge_id`` is a state vertex. A state transition ``e1 ->
e2`` exists only when the edges are contiguous and the existing Gate-D
``transition_allowed`` function permits that turn. NetworkX's tested
``shortest_simple_paths`` implementation can then enumerate Yen alternatives
without collapsing incoming-way state or parallel edge identity.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import networkx as nx
import pandas as pd

from src.phase2_frozen_graph import (
    build_adjacency,
    build_turn_rule_index,
    restriction_aware_one_to_many,
    transition_allowed,
)

TOL_MIN = 1e-12
TOL_M = 1e-9


@dataclass
class RestrictionAwareStateContext:
    """Reusable state-expanded representation of one frozen Gate-D graph."""

    graph: nx.DiGraph
    edge_lookup: dict[str, dict[str, Any]]
    outgoing_by_node: dict[str, list[str]]
    incoming_by_node: dict[str, list[str]]
    adjacency: dict
    rule_index: dict
    stats: dict[str, int]


def _edge_records(edges: pd.DataFrame) -> list[dict[str, Any]]:
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
    frame = edges.copy()
    frame["edge_id"] = frame["edge_id"].astype(str)
    if frame["edge_id"].duplicated().any():
        raise ValueError("Gate-D edge_id values must be unique")

    rows: list[dict[str, Any]] = []
    for row in frame.sort_values("edge_id", kind="mergesort").itertuples(index=False):
        minutes = float(row.running_minutes_model)
        length = float(row.length_m)
        if minutes <= 0 or length <= 0:
            raise ValueError(f"Non-positive Gate-D edge cost for {row.edge_id}")
        rows.append(
            {
                "edge_id": str(row.edge_id),
                "u": str(row.u_node_id),
                "v": str(row.v_node_id),
                "way": str(row.osm_way_id),
                "minutes": minutes,
                "length_m": length,
            }
        )
    return rows


def build_restriction_aware_state_context(
    edges: pd.DataFrame,
    rules: pd.DataFrame,
) -> RestrictionAwareStateContext:
    """Build an edge-state DiGraph localising exact Gate-D turn semantics."""
    records = _edge_records(edges)
    edge_lookup = {row["edge_id"]: row for row in records}
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    graph = nx.DiGraph()

    for row in records:
        edge_id = row["edge_id"]
        graph.add_node(edge_id)
        outgoing[row["u"]].append(edge_id)
        incoming[row["v"]].append(edge_id)
    for values in outgoing.values():
        values.sort()
    for values in incoming.values():
        values.sort()

    rule_index = build_turn_rule_index(rules)
    transition_count = 0
    turn_rejected = 0
    via_nodes = sorted(set(incoming) & set(outgoing))
    for via in via_nodes:
        for incoming_id in incoming[via]:
            inc = edge_lookup[incoming_id]
            for outgoing_id in outgoing[via]:
                out = edge_lookup[outgoing_id]
                if not transition_allowed(
                    rule_index,
                    via,
                    inc["u"],
                    inc["way"],
                    out["v"],
                    out["way"],
                ):
                    turn_rejected += 1
                    continue
                # Entering the next state means traversing the outgoing base
                # edge, so its running time is the transition cost.
                graph.add_edge(incoming_id, outgoing_id, weight=out["minutes"])
                transition_count += 1

    context = RestrictionAwareStateContext(
        graph=graph,
        edge_lookup=edge_lookup,
        outgoing_by_node=dict(outgoing),
        incoming_by_node=dict(incoming),
        adjacency=build_adjacency(edges),
        rule_index=rule_index,
        stats={
            "base_directed_edges": len(records),
            "state_vertices": graph.number_of_nodes(),
            "state_transitions": transition_count,
            "turn_transitions_rejected": turn_rejected,
            "physical_via_nodes_with_in_and_out": len(via_nodes),
        },
    )
    if context.stats["state_vertices"] != len(records):
        raise AssertionError("Edge-state graph lost Gate-D edge identity")
    return context


def physical_nodes_from_edge_ids(
    source_node: str,
    edge_ids: list[str],
    edge_lookup: dict[str, dict[str, Any]],
) -> list[str]:
    """Project an exact edge sequence to its physical road-node sequence."""
    current = str(source_node)
    nodes = [current]
    for edge_id in edge_ids:
        if edge_id not in edge_lookup:
            raise ValueError(f"Unknown Gate-D edge_id {edge_id}")
        edge = edge_lookup[edge_id]
        if edge["u"] != current:
            raise ValueError(
                f"Discontinuous Gate-D edge path at {edge_id}: expected u={current}, got {edge['u']}"
            )
        current = edge["v"]
        nodes.append(current)
    return nodes


def path_metrics(
    edge_ids: list[str],
    edge_lookup: dict[str, dict[str, Any]],
) -> tuple[float, float]:
    runtime = sum(float(edge_lookup[e]["minutes"]) for e in edge_ids)
    distance = sum(float(edge_lookup[e]["length_m"]) for e in edge_ids)
    return runtime, distance


def repeated_physical_nodes(nodes: list[str]) -> list[str]:
    counts = Counter(nodes)
    return sorted(node for node, count in counts.items() if count > 1)


def path_is_physical_loopless(nodes: list[str]) -> bool:
    return not repeated_physical_nodes(nodes)


def certified_state_path_representable(
    context: RestrictionAwareStateContext,
    source_node: str,
    target_node: str,
    edge_ids: list[str],
) -> tuple[bool, str]:
    """Verify an exact Gate-D edge sequence exists in the edge-state graph."""
    source = str(source_node)
    target = str(target_node)
    if not edge_ids:
        return False, "EMPTY_EDGE_SEQUENCE_FOR_DISTINCT_OD"
    nodes = physical_nodes_from_edge_ids(source, edge_ids, context.edge_lookup)
    if nodes[-1] != target:
        return False, "TARGET_MISMATCH"
    if edge_ids[0] not in context.outgoing_by_node.get(source, []):
        return False, "FIRST_EDGE_NOT_OUTGOING_FROM_SOURCE"
    if edge_ids[-1] not in context.incoming_by_node.get(target, []):
        return False, "LAST_EDGE_NOT_INCOMING_TO_TARGET"
    for first, second in zip(edge_ids, edge_ids[1:]):
        if not context.graph.has_edge(first, second):
            return False, f"MISSING_STATE_TRANSITION:{first}->{second}"
    return True, "REPRESENTABLE_EXACT_EDGE_SEQUENCE"


def _candidate(
    *,
    source_node: str,
    target_node: str,
    edge_ids: list[str],
    edge_lookup: dict[str, dict[str, Any]],
    provenance: str,
) -> dict[str, Any]:
    nodes = physical_nodes_from_edge_ids(source_node, edge_ids, edge_lookup)
    if not nodes or nodes[-1] != str(target_node):
        raise ValueError("Projected path does not terminate at requested target")
    runtime, distance = path_metrics(edge_ids, edge_lookup)
    repeated = repeated_physical_nodes(nodes)
    return {
        "source_node": str(source_node),
        "target_node": str(target_node),
        "edge_ids": list(edge_ids),
        "physical_nodes": nodes,
        "running_minutes_model": runtime,
        "distance_m": distance,
        "physical_loopless": not repeated,
        "repeated_physical_nodes": repeated,
        "provenance": provenance,
    }


def _cost_key(path: dict[str, Any]) -> tuple[Any, ...]:
    return (
        float(path["running_minutes_model"]),
        float(path["distance_m"]),
        tuple(path["edge_ids"]),
    )


def k_shortest_loopless_paths(
    context: RestrictionAwareStateContext,
    source_node: str,
    target_node: str,
    *,
    k: int = 5,
    max_raw_state_paths: int = 50_000,
) -> dict[str, Any]:
    """Return deterministic physically loopless legal alternatives for one OD.

    The certified Gate-D shortest path is audited separately and returned as
    metadata. If it is physically loopless it is forced to output rank 1. If it
    contains a legal manoeuvre loop, it remains certified routing evidence but
    is excluded from the corridor list and the first admissible loopless
    alternative becomes rank 1.
    """
    source = str(source_node)
    target = str(target_node)
    if source == target:
        raise ValueError("K-shortest corridor query requires distinct source and target")
    if k < 1:
        raise ValueError("k must be >= 1")
    if max_raw_state_paths < k:
        raise ValueError("max_raw_state_paths must be >= k")

    certified_routes = restriction_aware_one_to_many(
        context.adjacency,
        context.rule_index,
        source,
        {target},
    )
    certified_raw = certified_routes.get(target)
    if certified_raw is None:
        return {
            "paths": [],
            "raw_state_paths_examined": 0,
            "state_generator_exhausted": True,
            "tie_band_complete": True,
            "certified_shortest_present": False,
            "certified_path": None,
        }

    certified = _candidate(
        source_node=source,
        target_node=target,
        edge_ids=list(certified_raw["edge_ids"]),
        edge_lookup=context.edge_lookup,
        provenance="CERTIFIED_GATE_D_RESTRICTION_AWARE_DIJKSTRA",
    )
    representable, representable_reason = certified_state_path_representable(
        context,
        source,
        target,
        certified["edge_ids"],
    )
    if not representable:
        raise AssertionError(
            "Certified Gate-D path is not exactly representable in edge-state graph: "
            f"{representable_reason}"
        )

    virtual_source = ("__PHASE2_KSP_SOURCE__", source, target)
    virtual_target = ("__PHASE2_KSP_TARGET__", source, target)
    graph = context.graph
    if virtual_source in graph or virtual_target in graph:
        raise AssertionError("Temporary KSP query node collision")

    candidates: dict[tuple[str, ...], dict[str, Any]] = {}
    if certified["physical_loopless"]:
        candidates[tuple(certified["edge_ids"])] = certified

    raw_examined = 0
    generator_exhausted = False
    tie_band_complete = False
    first_state_candidate: dict[str, Any] | None = None
    first_loopless_state_candidate: dict[str, Any] | None = None

    try:
        graph.add_node(virtual_source)
        graph.add_node(virtual_target)
        for edge_id in context.outgoing_by_node.get(source, []):
            edge = context.edge_lookup[edge_id]
            graph.add_edge(virtual_source, edge_id, weight=edge["minutes"])
        for edge_id in context.incoming_by_node.get(target, []):
            graph.add_edge(edge_id, virtual_target, weight=0.0)

        if graph.out_degree(virtual_source) == 0 or graph.in_degree(virtual_target) == 0:
            raise AssertionError("State graph cannot represent certified reachable OD pair")

        generator = nx.shortest_simple_paths(
            graph,
            virtual_source,
            virtual_target,
            weight="weight",
        )
        cutoff_runtime: float | None = None
        for state_path in generator:
            raw_examined += 1
            if raw_examined > max_raw_state_paths:
                raise RuntimeError(
                    "KSP raw-state-path cap reached before deterministic tie-band completion"
                )
            edge_ids = [str(value) for value in state_path[1:-1]]
            state_candidate = _candidate(
                source_node=source,
                target_node=target,
                edge_ids=edge_ids,
                edge_lookup=context.edge_lookup,
                provenance="NETWORKX_YEN_EDGE_STATE_GRAPH",
            )
            runtime = float(state_candidate["running_minutes_model"])

            if first_state_candidate is None:
                first_state_candidate = state_candidate

            # shortest_simple_paths is non-decreasing in running-time weight.
            # Once it rises above the kth retained loopless runtime, every tie
            # at that runtime has already been observed and deterministic
            # distance/edge-ID tie-breaking can be applied safely.
            if cutoff_runtime is not None and runtime > cutoff_runtime + TOL_MIN:
                tie_band_complete = True
                break

            if not state_candidate["physical_loopless"]:
                continue
            if first_loopless_state_candidate is None:
                first_loopless_state_candidate = state_candidate
            candidates.setdefault(tuple(edge_ids), state_candidate)

            if len(candidates) >= k:
                ranked_now = sorted(candidates.values(), key=_cost_key)
                cutoff_runtime = float(ranked_now[k - 1]["running_minutes_model"])
        else:
            generator_exhausted = True
            tie_band_complete = True
    except nx.NetworkXNoPath as exc:
        raise AssertionError("State graph lost a Gate-D reachable path") from exc
    finally:
        if virtual_source in graph:
            graph.remove_node(virtual_source)
        if virtual_target in graph:
            graph.remove_node(virtual_target)

    if first_state_candidate is None:
        raise AssertionError("State graph produced no path for certified reachable OD pair")

    certified_runtime = float(certified["running_minutes_model"])
    certified_distance = float(certified["distance_m"])
    first_runtime = float(first_state_candidate["running_minutes_model"])
    first_distance = float(first_state_candidate["distance_m"])
    if first_runtime < certified_runtime - TOL_MIN:
        raise AssertionError("State-expanded graph found a path cheaper than certified Gate-D Dijkstra")
    if abs(first_runtime - certified_runtime) > TOL_MIN:
        raise AssertionError("State-expanded graph shortest runtime does not equal certified Gate-D Dijkstra")
    if first_distance < certified_distance - TOL_M:
        raise AssertionError(
            "State-expanded graph found equal-runtime but shorter-distance path than certified Gate-D Dijkstra"
        )

    ordered = sorted(candidates.values(), key=_cost_key)
    certified_key = tuple(certified["edge_ids"])
    if certified["physical_loopless"]:
        # Historical exact first-path identity is intentionally retained when
        # that path is an admissible corridor.
        ordered = [certified] + [
            path for path in ordered if tuple(path["edge_ids"]) != certified_key
        ]
    ordered = ordered[:k]
    for rank, path in enumerate(ordered, start=1):
        path["rank"] = rank

    if certified["physical_loopless"]:
        if not ordered or tuple(ordered[0]["edge_ids"]) != certified_key:
            raise AssertionError("Loopless certified Gate-D path was not retained at corridor rank 1")
        if abs(float(ordered[0]["running_minutes_model"]) - certified_runtime) > TOL_MIN:
            raise AssertionError("Loopless corridor rank 1 changed certified Gate-D runtime")

    loopless_penalty_min = None
    loopless_penalty_m = None
    if ordered:
        loopless_penalty_min = float(ordered[0]["running_minutes_model"]) - certified_runtime
        loopless_penalty_m = float(ordered[0]["distance_m"]) - certified_distance
        if loopless_penalty_min < -TOL_MIN:
            raise AssertionError("Loopless corridor unexpectedly beats certified Gate-D shortest runtime")

    return {
        "paths": ordered,
        "raw_state_paths_examined": raw_examined,
        "state_generator_exhausted": generator_exhausted,
        "tie_band_complete": tie_band_complete,
        "certified_shortest_present": True,
        "certified_path": certified,
        "certified_state_path_representable": representable,
        "certified_state_path_representable_reason": representable_reason,
        "certified_shortest_physical_loopless": bool(certified["physical_loopless"]),
        "certified_first_path_exact_edge_ids": bool(
            certified["physical_loopless"]
            and ordered
            and tuple(ordered[0]["edge_ids"]) == certified_key
        ),
        "first_state_path_runtime_delta_min": first_runtime - certified_runtime,
        "first_state_path_distance_delta_m": first_distance - certified_distance,
        "loopless_shortest_runtime_penalty_min": loopless_penalty_min,
        "loopless_shortest_distance_penalty_m": loopless_penalty_m,
        "first_loopless_state_path_present": first_loopless_state_candidate is not None,
    }
