"""Exact connected structural-layer enumeration for RT-024 V3.

Generation is topology-neutral. The algorithm enumerates every connected simple
edge subset at one exact edge count by starting from all one-edge states and
adding only edges incident to the current vertex set. Deduplication is by the
canonical link-id tuple. Topology is classified only after policy coverage is
checked.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    CONTRACT,
    StructureRecord,
    _normalise_links,
    classify_connected_structure,
)

EXACT_LAYER_CONTRACT = "EXACT_CONNECTED_EDGE_LAYER_WITH_POLICY_COVERAGE_NO_TOPOLOGY_PRIOR"
PASS_STATUS = "PASS_COMPLETE_EXACT_EDGE_POLICY_STRUCTURE_ENUMERATION"


def enumerate_exact_edge_policy_structures(
    links: Iterable[AbstractLink | Mapping[str, str]],
    *,
    exact_edge_count: int,
    required_policy_groups: Iterable[str],
    terminal_policy_groups: Mapping[str, Iterable[str]],
) -> dict:
    """Enumerate all connected structures at one exact edge count, uncapped."""
    normalised = _normalise_links(links)
    if not normalised:
        raise ValueError("abstract pair graph must contain at least one link")
    target = int(exact_edge_count)
    if target < 1:
        raise ValueError("exact_edge_count must be >= 1")
    if target > len(normalised):
        raise ValueError("exact_edge_count exceeds available structural links")

    groups = tuple(
        sorted({str(item).strip() for item in required_policy_groups if str(item).strip()})
    )
    if not groups:
        raise ValueError("at least one required policy group is required")
    group_set = set(groups)

    all_vertices = tuple(sorted({link.u for link in normalised} | {link.v for link in normalised}))
    group_by_terminal: dict[str, str] = {}
    present_groups: set[str] = set()
    for terminal in all_vertices:
        memberships = tuple(
            sorted(
                {
                    str(group).strip()
                    for group in terminal_policy_groups.get(terminal, ())
                    if str(group).strip() in group_set
                }
            )
        )
        if len(memberships) != 1:
            raise ValueError(
                "exact-edge policy search requires every graph terminal to belong "
                f"to exactly one required policy group: {terminal} -> {memberships}"
            )
        group_by_terminal[terminal] = memberships[0]
        present_groups.add(memberships[0])
    missing = sorted(group_set - present_groups)
    if missing:
        raise ValueError(f"required policy groups absent from pair graph: {missing}")

    edge_by_id = {link.link_id: link for link in normalised}
    incident: dict[str, tuple[str, ...]] = {}
    incident_lists: dict[str, list[str]] = defaultdict(list)
    for link in normalised:
        incident_lists[link.u].append(link.link_id)
        incident_lists[link.v].append(link.link_id)
    for terminal, edge_ids in incident_lists.items():
        incident[terminal] = tuple(sorted(edge_ids))

    states: set[tuple[str, ...]] = {(link.link_id,) for link in normalised}
    state_counts = {1: len(states)}
    for edge_count in range(2, target + 1):
        next_states: set[tuple[str, ...]] = set()
        for state in states:
            vertices: set[str] = set()
            for link_id in state:
                link = edge_by_id[link_id]
                vertices.add(link.u)
                vertices.add(link.v)
            candidates: set[str] = set()
            for vertex in vertices:
                candidates.update(incident[vertex])
            state_set = set(state)
            for link_id in sorted(candidates - state_set):
                next_states.add(tuple(sorted((*state, link_id))))
        states = next_states
        state_counts[edge_count] = len(states)

    accepted: list[StructureRecord] = []
    for state in sorted(states):
        subset = [edge_by_id[link_id] for link_id in state]
        vertices = {endpoint for link in subset for endpoint in (link.u, link.v)}
        covered = {group_by_terminal[terminal] for terminal in vertices}
        if not group_set.issubset(covered):
            continue
        record = classify_connected_structure(subset)
        if record.edge_count != target:
            raise AssertionError("exact-edge enumerator emitted wrong edge count")
        accepted.append(record)

    accepted.sort(key=lambda item: (item.link_ids, item.vertex_ids))
    if len({record.link_ids for record in accepted}) != len(accepted):
        raise AssertionError("duplicate exact-edge structure generated")

    return {
        "status": PASS_STATUS,
        "complete": True,
        "structures": accepted,
        "structure_count": len(accepted),
        "required_policy_groups": groups,
        "exact_edge_count": target,
        "connected_state_counts_by_edge_count": {
            str(key): int(value) for key, value in sorted(state_counts.items())
        },
        "connected_states_at_target": int(len(states)),
        "contract": CONTRACT,
        "frontier_contract": EXACT_LAYER_CONTRACT,
        "generation_semantics": (
            "ALL_SINGLE_EDGES_THEN_INCIDENT_EDGE_EXPANSION_WITH_CANONICAL_LINK_SET_DEDUPLICATION"
        ),
        "completeness_semantics": (
            "EVERY_CONNECTED_EDGE_SUBSET_HAS_AN_EDGE-DELETION_ORDER_TO_A_SINGLE_EDGE;"
            "REVERSING_THAT_ORDER_IS_GENERATED_BY_INCIDENT_EDGE_EXPANSION"
        ),
        "topology_semantics": "DESCRIPTIVE_POST_GENERATION_CLASSIFICATION",
        "technical_parameters": {
            "exact_edge_count": target,
            "enumeration_cap": None,
            "topology_filter": None,
            "semantics": "EXACT_LAYER_SCOPE_NOT_POLICY_WEIGHT_OR_TOPOLOGY_PRIOR",
        },
    }
