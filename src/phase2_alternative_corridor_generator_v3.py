"""Efficient bounded alternative-corridor generation on the frozen Gate-D graph.

This module does not select a network, passenger stops, topology, timetable or
winner. It preserves the certified Gate-D shortest path as the routing oracle
and generates a bounded set of deterministic alternatives by repeatedly
rerouting with edge penalties while enforcing the same turn restrictions.

Penalty, detour and overlap settings are technical exploration controls. They
must never be interpreted as policy weights or evidence that one route is
"better" overall.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import heapq
from math import inf
from typing import Iterable, Mapping, Sequence

from src.phase2_frozen_graph import restriction_aware_one_to_many, transition_allowed

EPS_MIN = 1e-12
EPS_M = 1e-9


@dataclass(frozen=True)
class CorridorPath:
    source: str
    target: str
    edge_ids: tuple[str, ...]
    node_ids: tuple[str, ...]
    running_minutes_model: float
    distance_m: float
    generation_penalized_cost: float
    provenance: str
    generation_round: int
    physical_node_loop: bool
    runtime_factor_vs_shortest: float
    max_shared_runtime_fraction: float
    admissible_for_corridor_pool: bool
    rejection_reason: str


def edge_lookup(adjacency) -> dict[str, tuple[str, str, float, float, str]]:
    """Return edge_id -> (u, v, length_m, minutes, osm_way_id)."""
    result: dict[str, tuple[str, str, float, float, str]] = {}
    for u_node, outgoing in adjacency.items():
        for v_node, length_m, minutes, osm_way_id, edge_id in outgoing:
            edge_id = str(edge_id)
            record = (
                str(u_node),
                str(v_node),
                float(length_m),
                float(minutes),
                str(osm_way_id),
            )
            previous = result.get(edge_id)
            if previous is not None and previous != record:
                raise ValueError(f"edge_id is not unique in adjacency: {edge_id}")
            result[edge_id] = record
    return result


def materialize_path(
    source: str,
    edge_ids: Sequence[str],
    lookup: Mapping[str, tuple[str, str, float, float, str]],
) -> tuple[tuple[str, ...], float, float]:
    """Rebuild ordered physical nodes, true runtime and distance from edge IDs."""
    nodes = [str(source)]
    runtime = 0.0
    distance = 0.0
    cursor = str(source)
    for raw_edge_id in edge_ids:
        edge_id = str(raw_edge_id)
        if edge_id not in lookup:
            raise KeyError(f"Unknown edge_id in path: {edge_id}")
        u_node, v_node, length_m, minutes, _ = lookup[edge_id]
        if u_node != cursor:
            raise ValueError(
                f"Non-contiguous path at edge {edge_id}: expected u={cursor}, got u={u_node}"
            )
        nodes.append(v_node)
        runtime += float(minutes)
        distance += float(length_m)
        cursor = v_node
    return tuple(nodes), runtime, distance


def has_physical_node_loop(node_ids: Sequence[str]) -> bool:
    return len(set(node_ids)) != len(node_ids)


def shared_runtime_fraction(
    candidate_edges: Sequence[str],
    reference_edges: Sequence[str],
    lookup: Mapping[str, tuple[str, str, float, float, str]],
) -> float:
    """Directed-edge shared runtime divided by the smaller path runtime.

    Edge multiplicity is respected even though corridor-admissible paths are
    normally physical-node-simple. The metric is diagnostic, not an objective.
    """
    candidate = Counter(str(edge_id) for edge_id in candidate_edges)
    reference = Counter(str(edge_id) for edge_id in reference_edges)
    shared = 0.0
    for edge_id in candidate.keys() & reference.keys():
        if edge_id not in lookup:
            raise KeyError(edge_id)
        minutes = float(lookup[edge_id][3])
        shared += min(candidate[edge_id], reference[edge_id]) * minutes
    candidate_runtime = sum(count * float(lookup[eid][3]) for eid, count in candidate.items())
    reference_runtime = sum(count * float(lookup[eid][3]) for eid, count in reference.items())
    denominator = min(candidate_runtime, reference_runtime)
    if denominator <= EPS_MIN:
        return 1.0 if tuple(candidate_edges) == tuple(reference_edges) else 0.0
    return shared / denominator


def max_shared_runtime_fraction(
    candidate_edges: Sequence[str],
    references: Iterable[Sequence[str]],
    lookup: Mapping[str, tuple[str, str, float, float, str]],
) -> float:
    values = [
        shared_runtime_fraction(candidate_edges, reference, lookup)
        for reference in references
    ]
    return max(values, default=0.0)


def restriction_aware_penalized_shortest_path(
    adjacency,
    rules,
    source: str,
    target: str,
    penalty_counts: Mapping[str, int],
    penalty_increment: float,
) -> dict | None:
    """Shortest legal path under deterministic edge penalties.

    The state is the same information Gate D needs for turn legality:
    `(node, previous_node, incoming_way)`. Penalties only influence exploration
    cost. True runtime and true distance are accumulated separately and returned
    untouched.
    """
    if penalty_increment < 0:
        raise ValueError("penalty_increment must be non-negative")
    source = str(source)
    target = str(target)
    if source == target:
        return {
            "running_minutes_model": 0.0,
            "distance_m": 0.0,
            "penalized_cost": 0.0,
            "edge_ids": [],
        }

    start_state = (source, None, None)
    best_penalized = {start_state: 0.0}
    best_true_min = {start_state: 0.0}
    best_distance = {start_state: 0.0}
    previous: dict[tuple, tuple[tuple, str]] = {}
    heap = [(0.0, 0.0, 0.0, source, "", "", start_state)]
    target_state = None

    while heap:
        penalized_cost, true_min, distance_m, _, _, _, state = heapq.heappop(heap)
        if abs(penalized_cost - best_penalized.get(state, inf)) > EPS_MIN:
            continue
        if abs(true_min - best_true_min.get(state, inf)) > EPS_MIN:
            continue
        if abs(distance_m - best_distance.get(state, inf)) > EPS_M:
            continue

        node, previous_node, incoming_way = state
        if node == target:
            target_state = state
            break

        for outgoing_node, length_m, minutes, outgoing_way, edge_id in adjacency.get(node, []):
            outgoing_node = str(outgoing_node)
            outgoing_way = str(outgoing_way)
            edge_id = str(edge_id)
            if not transition_allowed(
                rules,
                str(node),
                previous_node,
                incoming_way,
                outgoing_node,
                outgoing_way,
            ):
                continue

            length_m = float(length_m)
            minutes = float(minutes)
            penalty_count = int(penalty_counts.get(edge_id, 0))
            edge_penalized = minutes * (1.0 + penalty_increment * penalty_count)

            next_state = (outgoing_node, str(node), outgoing_way)
            next_penalized = penalized_cost + edge_penalized
            next_true_min = true_min + minutes
            next_distance = distance_m + length_m

            old_penalized = best_penalized.get(next_state)
            old_true_min = best_true_min.get(next_state, inf)
            old_distance = best_distance.get(next_state, inf)
            better = (
                old_penalized is None
                or next_penalized < old_penalized - EPS_MIN
                or (
                    abs(next_penalized - old_penalized) <= EPS_MIN
                    and next_true_min < old_true_min - EPS_MIN
                )
                or (
                    abs(next_penalized - old_penalized) <= EPS_MIN
                    and abs(next_true_min - old_true_min) <= EPS_MIN
                    and next_distance < old_distance - EPS_M
                )
            )
            if not better:
                continue

            best_penalized[next_state] = next_penalized
            best_true_min[next_state] = next_true_min
            best_distance[next_state] = next_distance
            previous[next_state] = (state, edge_id)
            heapq.heappush(
                heap,
                (
                    next_penalized,
                    next_true_min,
                    next_distance,
                    outgoing_node,
                    outgoing_way,
                    edge_id,
                    next_state,
                ),
            )

    if target_state is None:
        return None

    edges_rev: list[str] = []
    cursor = target_state
    while cursor != start_state:
        previous_state, edge_id = previous[cursor]
        edges_rev.append(edge_id)
        cursor = previous_state
    return {
        "running_minutes_model": best_true_min[target_state],
        "distance_m": best_distance[target_state],
        "penalized_cost": best_penalized[target_state],
        "edge_ids": list(reversed(edges_rev)),
    }


def generate_bounded_alternative_corridors(
    adjacency,
    rules,
    source: str,
    target: str,
    *,
    max_alternatives: int = 4,
    max_generation_rounds: int = 24,
    penalty_increment: float = 0.20,
    max_runtime_factor: float = 1.50,
    max_shared_runtime_fraction_allowed: float = 0.90,
) -> dict:
    """Generate a deterministic technical pool of legal alternative corridors.

    Returns baseline routing evidence, admitted loopless corridor paths and a
    full generation audit. The returned pool is explicitly *not* a network
    recommendation or a complete K-shortest enumeration.
    """
    if max_alternatives < 1:
        raise ValueError("max_alternatives must be >= 1")
    if max_generation_rounds < 0:
        raise ValueError("max_generation_rounds must be >= 0")
    if penalty_increment <= 0:
        raise ValueError("penalty_increment must be > 0")
    if max_runtime_factor < 1.0:
        raise ValueError("max_runtime_factor must be >= 1")
    if not 0.0 <= max_shared_runtime_fraction_allowed <= 1.0:
        raise ValueError("max_shared_runtime_fraction_allowed must be in [0, 1]")

    source = str(source)
    target = str(target)
    lookup = edge_lookup(adjacency)
    oracle = restriction_aware_one_to_many(adjacency, rules, source, {target}).get(target)
    if oracle is None:
        return {
            "status": "NO_GATE_D_ROUTE",
            "source": source,
            "target": target,
            "baseline": None,
            "corridors": [],
            "generation_audit": [],
            "contract": "ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION",
        }

    baseline_edges = tuple(str(edge_id) for edge_id in oracle["edge_ids"])
    baseline_nodes, baseline_runtime, baseline_distance = materialize_path(
        source, baseline_edges, lookup
    )
    if baseline_nodes[-1] != target:
        raise AssertionError("Gate-D baseline reconstruction does not end at target")
    if abs(baseline_runtime - float(oracle["running_minutes_model"])) > 1e-9:
        raise AssertionError("Gate-D baseline runtime changed during reconstruction")
    if abs(baseline_distance - float(oracle["distance_m"])) > 1e-6:
        raise AssertionError("Gate-D baseline distance changed during reconstruction")

    baseline_loop = has_physical_node_loop(baseline_nodes)
    baseline = CorridorPath(
        source=source,
        target=target,
        edge_ids=baseline_edges,
        node_ids=baseline_nodes,
        running_minutes_model=baseline_runtime,
        distance_m=baseline_distance,
        generation_penalized_cost=baseline_runtime,
        provenance="CERTIFIED_GATE_D_SHORTEST",
        generation_round=0,
        physical_node_loop=baseline_loop,
        runtime_factor_vs_shortest=1.0,
        max_shared_runtime_fraction=0.0,
        admissible_for_corridor_pool=not baseline_loop,
        rejection_reason="" if not baseline_loop else "PHYSICAL_NODE_LOOP",
    )

    admitted: list[CorridorPath] = []
    audit: list[CorridorPath] = [baseline]
    seen_paths = {baseline_edges}
    if baseline.admissible_for_corridor_pool:
        admitted.append(baseline)

    penalty_counts: Counter[str] = Counter(baseline_edges)

    for generation_round in range(1, max_generation_rounds + 1):
        if len(admitted) >= max_alternatives:
            break
        candidate_raw = restriction_aware_penalized_shortest_path(
            adjacency,
            rules,
            source,
            target,
            penalty_counts,
            penalty_increment,
        )
        if candidate_raw is None:
            break

        edges = tuple(str(edge_id) for edge_id in candidate_raw["edge_ids"])
        nodes, runtime, distance = materialize_path(source, edges, lookup)
        if nodes[-1] != target:
            raise AssertionError("Generated alternative does not end at target")
        loop = has_physical_node_loop(nodes)
        runtime_factor = runtime / baseline_runtime if baseline_runtime > EPS_MIN else 1.0

        reference_edges = [path.edge_ids for path in admitted]
        overlap = max_shared_runtime_fraction(edges, reference_edges, lookup)

        reasons: list[str] = []
        if edges in seen_paths:
            reasons.append("DUPLICATE_EDGE_SEQUENCE")
        if loop:
            reasons.append("PHYSICAL_NODE_LOOP")
        if runtime_factor > max_runtime_factor + 1e-12:
            reasons.append("ABOVE_TECHNICAL_RUNTIME_ENVELOPE")
        if admitted and overlap > max_shared_runtime_fraction_allowed + 1e-12:
            reasons.append("ABOVE_TECHNICAL_OVERLAP_ENVELOPE")

        candidate = CorridorPath(
            source=source,
            target=target,
            edge_ids=edges,
            node_ids=nodes,
            running_minutes_model=runtime,
            distance_m=distance,
            generation_penalized_cost=float(candidate_raw["penalized_cost"]),
            provenance="BOUNDED_PENALTY_ALTERNATIVE",
            generation_round=generation_round,
            physical_node_loop=loop,
            runtime_factor_vs_shortest=runtime_factor,
            max_shared_runtime_fraction=overlap,
            admissible_for_corridor_pool=not reasons,
            rejection_reason="|".join(reasons),
        )
        audit.append(candidate)
        seen_paths.add(edges)

        # Always penalize what the search just produced, including rejected or
        # duplicate candidates. Otherwise the generator can get stuck
        # returning the same path forever.
        penalty_counts.update(edges)
        if candidate.admissible_for_corridor_pool:
            admitted.append(candidate)

    admitted = sorted(
        admitted,
        key=lambda path: (
            path.running_minutes_model,
            path.distance_m,
            path.edge_ids,
            path.generation_round,
        ),
    )

    return {
        "status": "PASS_BOUNDED_ALTERNATIVE_GENERATION",
        "source": source,
        "target": target,
        "baseline": baseline,
        "corridors": admitted,
        "generation_audit": audit,
        "technical_parameters": {
            "max_alternatives": max_alternatives,
            "max_generation_rounds": max_generation_rounds,
            "penalty_increment": penalty_increment,
            "max_runtime_factor": max_runtime_factor,
            "max_shared_runtime_fraction_allowed": max_shared_runtime_fraction_allowed,
            "semantics": "TECHNICAL_EXPLORATION_PARAMETERS_NOT_POLICY_WEIGHTS_OR_THRESHOLDS",
        },
        "contract": "ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION",
        "completeness_claim": "NO_K_SHORTEST_COMPLETENESS_CLAIM",
    }


def path_to_record(path: CorridorPath) -> dict:
    return {
        "source_graph_node_id": path.source,
        "target_graph_node_id": path.target,
        "path_edge_ids": ";".join(path.edge_ids),
        "path_node_ids": ";".join(path.node_ids),
        "running_minutes_model": path.running_minutes_model,
        "distance_m": path.distance_m,
        "generation_penalized_cost": path.generation_penalized_cost,
        "provenance": path.provenance,
        "generation_round": path.generation_round,
        "physical_node_loop": path.physical_node_loop,
        "runtime_factor_vs_shortest": path.runtime_factor_vs_shortest,
        "max_shared_runtime_fraction": path.max_shared_runtime_fraction,
        "admissible_for_corridor_pool": path.admissible_for_corridor_pool,
        "rejection_reason": path.rejection_reason,
        "scope": "ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION",
    }
