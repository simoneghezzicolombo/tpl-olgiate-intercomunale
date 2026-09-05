"""Restriction-aware K-shortest loopless corridor paths for Phase 2 V3.

This module does not choose a network, a stop pattern, a topology or a winner.
It only generates alternative legal road paths on the already frozen Gate-D
bus graph.

Design contract
---------------
Gate D evaluates legal turns with state
``(current_node, previous_node, incoming_osm_way)``.  To reuse NetworkX's
well-tested Yen implementation without losing that state, every *directed
Gate-D edge* becomes a routing-state vertex.  Traversing state ``e1 -> e2``
means "after arriving on e1, take e2" and the transition exists only when
``phase2_frozen_graph.transition_allowed`` permits it.

A query adds temporary virtual source/target nodes.  NetworkX
``shortest_simple_paths`` then enumerates simple paths in the edge-state graph.
Because a state-simple path can still revisit the same physical road node via a
different incoming edge, projected paths with repeated physical nodes are
rejected.  Filtering a non-decreasing K-shortest state-path stream this way
preserves the order of the remaining physically loopless paths.

The existing Gate-D restriction-aware Dijkstra remains the authoritative
shortest-path oracle.  Every query checks that the state-expanded graph has no
path cheaper than that certified first path, then places the certified path at
rank 1.  This deliberately changes as little as possible of the already audited
routing stack.
"""
from __future__ import annotations

from collections import defaultdict
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
    """Build an edge-state DiGraph exactly localising Gate-D turn semantics.

    One state vertex corresponds to one exact directed ``edge_id``.  Therefore
    parallel edges remain distinct even when they share physical endpoints or an
    OSM way ID.
    """
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
                allowed = transition_allowed(
                    rule_index,
                    via,
                    inc["u"],
                    inc["way"],
                    out["v"],
                    out["way"],
                )
                if not allowed:
                    turn_rejected += 1
                    continue
                # The transition cost is the *new* base edge.  Query virtual
                # sources separately pay for the first base edge.
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


def path_metrics(edge_ids: list[str], edge_lookup: dict[str, dict[str, Any]]) -> tuple[float, float]:
    runtime = sum(float(edge_lookup[e]["minutes"]) for e in edge_ids)
    distance = sum(float(edge_lookup[e]["length_m"]) for e in edge_ids)
    return runtime, distance


def path_is_physical_loopless(nodes: list[str]) -> bool:
    return len(nodes) == len(set(nodes))


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
    return {
        "source_node": str(source_node),
        "target_node": str(target_node),
        "edge_ids": list(edge_ids),
        "physical_nodes": nodes,
        "running_minutes_model": runtime,
        "distance_m": distance,
        "physical_loopless": path_is_physical_loopless(nodes),
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
    """Return deterministic legal loopless alternatives for one OD node pair.

    Rank 1 is always the existing Gate-D Dijkstra path.  NetworkX/Yen is used
    to obtain alternatives and to audit that the state expansion admits no
    cheaper physically loopless path.
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
        }
    certified = _candidate(
        source_node=source,
        target_node=target,
        edge_ids=list(certified_raw["edge_ids"]),
        edge_lookup=context.edge_lookup,
        provenance="CERTIFIED_GATE_D_RESTRICTION_AWARE_DIJKSTRA",
    )
    if not certified["physical_loopless"]:
        raise ValueError(
            "Certified Gate-D shortest path repeats a physical road node; "
            "loopless first-path equivalence cannot be asserted"
        )

    virtual_source = ("__PHASE2_KSP_SOURCE__", source, target)
    virtual_target = ("__PHASE2_KSP_TARGET__", source, target)
    graph = context.graph
    if virtual_source in graph or virtual_target in graph:
        raise AssertionError("Temporary KSP query node collision")

    # Candidate map is seeded with the authoritative shortest path.  A state-
    # graph path with the same exact edges will simply deduplicate into it.
    candidates: dict[tuple[str, ...], dict[str, Any]] = {
        tuple(certified["edge_ids"]): certified
    }
    raw_examined = 0
    generator_exhausted = False
    tie_band_complete = False
    first_simple_state_candidate: dict[str, Any] | None = None

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

            # shortest_simple_paths is non-decreasing in the configured weight.
            # Once it moves above the kth retained runtime, all paths tied at
            # that runtime have already been seen, including physically cyclic
            # state paths that we intentionally discard.
            if cutoff_runtime is not None and runtime > cutoff_runtime + TOL_MIN:
                tie_band_complete = True
                break

            if not state_candidate["physical_loopless"]:
                continue
            if first_simple_state_candidate is None:
                first_simple_state_candidate = state_candidate
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

    if first_simple_state_candidate is None:
        raise AssertionError("State graph produced no physically loopless path for certified OD pair")

    # Strong equivalence guard.  The expanded state graph may tie differently,
    # but it may never beat the existing Gate-D shortest-path oracle.
    first_runtime = float(first_simple_state_candidate["running_minutes_model"])
    first_distance = float(first_simple_state_candidate["distance_m"])
    certified_runtime = float(certified["running_minutes_model"])
    certified_distance = float(certified["distance_m"])
    if first_runtime < certified_runtime - TOL_MIN:
        raise AssertionError("State-expanded graph found a path cheaper than certified Gate-D Dijkstra")
    if abs(first_runtime - certified_runtime) <= TOL_MIN and first_distance < certified_distance - TOL_M:
        raise AssertionError(
            "State-expanded graph found equal-runtime but shorter-distance path than certified Gate-D Dijkstra"
        )
    if abs(first_runtime - certified_runtime) > TOL_MIN:
        raise AssertionError("State-expanded graph shortest runtime does not equal certified Gate-D Dijkstra")

    ordered = sorted(candidates.values(), key=_cost_key)
    certified_key = tuple(certified["edge_ids"])
    ordered_without_certified = [p for p in ordered if tuple(p["edge_ids"]) != certified_key]
    ordered = [certified] + ordered_without_certified
    ordered = ordered[:k]
    for rank, path in enumerate(ordered, start=1):
        path["rank"] = rank

    return {
        "paths": ordered,
        "raw_state_paths_examined": raw_examined,
        "state_generator_exhausted": generator_exhausted,
        "tie_band_complete": tie_band_complete,
        "certified_shortest_present": True,
        "certified_first_path_exact_edge_ids": bool(
            ordered and tuple(ordered[0]["edge_ids"]) == certified_key
        ),
    }
