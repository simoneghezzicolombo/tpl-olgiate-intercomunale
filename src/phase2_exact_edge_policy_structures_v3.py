"""Exact connected structural-layer enumeration for RT-024/RT-025 V3.

Generation is topology-neutral. The algorithm enumerates every connected simple
edge subset at one exact edge count by starting from all one-edge states and
adding only edges incident to the current vertex set. Deduplication uses an
integer edge bitmask whose bit positions follow the canonical normalized link
order. Topology is classified only after policy coverage is checked.

The bitmask representation is an execution optimization only: the generated
edge-set universe is identical to the earlier canonical link-tuple
representation and remains order invariant.
"""
from __future__ import annotations

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


def _iter_bit_indices(mask: int):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask -= bit


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
    vertex_index = {terminal: index for index, terminal in enumerate(all_vertices)}
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

    group_index = {group: index for index, group in enumerate(groups)}
    required_group_mask = (1 << len(groups)) - 1
    vertex_group_masks = [
        1 << group_index[group_by_terminal[terminal]] for terminal in all_vertices
    ]

    endpoints: list[tuple[int, int]] = []
    incident_edge_masks = [0 for _ in all_vertices]
    for edge_index, link in enumerate(normalised):
        u = vertex_index[link.u]
        v = vertex_index[link.v]
        endpoints.append((u, v))
        edge_bit = 1 << edge_index
        incident_edge_masks[u] |= edge_bit
        incident_edge_masks[v] |= edge_bit

    def vertex_mask(edge_mask: int) -> int:
        result = 0
        for edge_index in _iter_bit_indices(edge_mask):
            u, v = endpoints[edge_index]
            result |= (1 << u) | (1 << v)
        return result

    def incident_candidates(vertices_mask: int) -> int:
        result = 0
        for vertex in _iter_bit_indices(vertices_mask):
            result |= incident_edge_masks[vertex]
        return result

    states: set[int] = {1 << edge_index for edge_index in range(len(normalised))}
    state_counts = {1: len(states)}
    for edge_count in range(2, target + 1):
        next_states: set[int] = set()
        for state in states:
            vertices_mask = vertex_mask(state)
            candidates = incident_candidates(vertices_mask) & ~state
            while candidates:
                edge_bit = candidates & -candidates
                next_states.add(state | edge_bit)
                candidates -= edge_bit
        states = next_states
        state_counts[edge_count] = len(states)

    accepted: list[StructureRecord] = []
    for state in states:
        vertices_mask = vertex_mask(state)
        covered_group_mask = 0
        for vertex in _iter_bit_indices(vertices_mask):
            covered_group_mask |= vertex_group_masks[vertex]
        if covered_group_mask != required_group_mask:
            continue

        subset = [normalised[index] for index in _iter_bit_indices(state)]
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
            "ALL_SINGLE_EDGES_THEN_INCIDENT_EDGE_EXPANSION_WITH_CANONICAL_EDGE_BITMASK_DEDUPLICATION"
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
            "state_representation": "INTEGER_EDGE_BITMASK_EXECUTION_OPTIMIZATION",
            "semantics": "EXACT_LAYER_SCOPE_NOT_POLICY_WEIGHT_OR_TOPOLOGY_PRIOR",
        },
    }
