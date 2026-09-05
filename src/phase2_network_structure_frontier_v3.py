"""Connected-only topology-neutral structure enumeration for Phase 2 V3.

RT-007 provides an exhaustive subset oracle. This module reduces wasted work by
expanding only edge sets that are connected by construction. It does not use
network topology classes as generation or pruning rules.

All territorial meaning remains upstream/downstream. Inputs are generic
terminal-pair links and generic hard guards only.
"""
from __future__ import annotations

from collections import defaultdict
from heapq import heappop, heappush
from typing import Iterable, Mapping

from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    CAP_STATUS,
    CONTRACT,
    StructureRecord,
    _group_coverage_ok,
    _normalise_links,
    classify_connected_structure,
)


FRONTIER_CONTRACT = "CONNECTED_ONLY_SEARCH_SAME_RT007_TOPOLOGY_NEUTRAL_CONTRACT"


def enumerate_connected_structures_frontier(
    links: Iterable[AbstractLink | Mapping[str, str]],
    *,
    required_terminal_ids: Iterable[str] = (),
    required_policy_groups: Iterable[str] = (),
    terminal_policy_groups: Mapping[str, Iterable[str]] | None = None,
    min_edges: int = 1,
    max_edges: int | None = None,
    max_states: int = 100_000,
    max_structures: int = 20_000,
) -> dict:
    """Enumerate connected structures by deterministic frontier expansion.

    Every discovered state is connected by construction. No topology label is
    consulted while deciding which state to expand. Generic required terminals
    and policy groups are acceptance guards only and therefore do not alter the
    topology-neutral expansion rule.

    If either state or output caps are reached, the function fails closed and
    returns no partial structure pool as usable evidence.
    """
    normalised = _normalise_links(links)
    if not normalised:
        raise ValueError("abstract pair graph must contain at least one link")
    if min_edges < 1:
        raise ValueError("min_edges must be >= 1")
    if max_states < 1 or max_structures < 1:
        raise ValueError("frontier caps must be >= 1")

    all_vertices = {link.u for link in normalised} | {link.v for link in normalised}
    required_terminals = tuple(sorted({str(item) for item in required_terminal_ids}))
    missing_terminals = sorted(set(required_terminals) - all_vertices)
    if missing_terminals:
        raise ValueError(
            f"required terminal IDs absent from pair graph: {missing_terminals}"
        )

    groups = tuple(sorted({str(item) for item in required_policy_groups}))
    membership = terminal_policy_groups or {}
    if groups:
        universe_groups: set[str] = set()
        for terminal in all_vertices:
            universe_groups.update(str(group) for group in membership.get(terminal, ()))
        missing_groups = sorted(set(groups) - universe_groups)
        if missing_groups:
            raise ValueError(
                f"required policy groups absent from pair graph: {missing_groups}"
            )

    upper = len(normalised) if max_edges is None else min(int(max_edges), len(normalised))
    if upper < min_edges:
        raise ValueError("max_edges must be >= min_edges")

    by_id = {link.link_id: link for link in normalised}
    incident: dict[str, set[str]] = defaultdict(set)
    for link in normalised:
        incident[link.u].add(link.link_id)
        incident[link.v].add(link.link_id)

    heap: list[tuple[int, tuple[str, ...]]] = []
    seen: set[frozenset[str]] = set()
    for link in normalised:
        key = (link.link_id,)
        heappush(heap, (1, key))
        seen.add(frozenset(key))

    if len(seen) > max_states:
        return {
            "status": CAP_STATUS,
            "complete": False,
            "structures": [],
            "partial_structure_count": 0,
            "states_expanded": 0,
            "states_discovered": max_states,
            "cap_reached": "max_states_discovered",
            "contract": CONTRACT,
            "frontier_contract": FRONTIER_CONTRACT,
        }

    accepted: list[StructureRecord] = []
    states_expanded = 0
    frontier_expansion_attempts = 0
    duplicate_expansion_attempts = 0

    while heap:
        edge_count, key = heappop(heap)
        states_expanded += 1
        if states_expanded > max_states:
            return {
                "status": CAP_STATUS,
                "complete": False,
                "structures": [],
                "partial_structure_count": len(accepted),
                "states_expanded": states_expanded - 1,
                "states_discovered": len(seen),
                "cap_reached": "max_states_expanded",
                "contract": CONTRACT,
                "frontier_contract": FRONTIER_CONTRACT,
            }

        subset = tuple(by_id[link_id] for link_id in key)
        vertices: set[str] = set()
        for link in subset:
            vertices.add(link.u)
            vertices.add(link.v)

        if (
            edge_count >= min_edges
            and set(required_terminals).issubset(vertices)
            and _group_coverage_ok(vertices, groups, membership)
        ):
            accepted.append(classify_connected_structure(subset))
            if len(accepted) > max_structures:
                return {
                    "status": CAP_STATUS,
                    "complete": False,
                    "structures": [],
                    "partial_structure_count": len(accepted) - 1,
                    "states_expanded": states_expanded,
                    "states_discovered": len(seen),
                    "cap_reached": "max_structures",
                    "contract": CONTRACT,
                    "frontier_contract": FRONTIER_CONTRACT,
                }

        if edge_count >= upper:
            continue

        frontier: set[str] = set()
        for vertex in vertices:
            frontier.update(incident[vertex])
        frontier.difference_update(key)

        for link_id in sorted(frontier):
            frontier_expansion_attempts += 1
            new_state = frozenset((*key, link_id))
            if new_state in seen:
                duplicate_expansion_attempts += 1
                continue
            if len(seen) >= max_states:
                return {
                    "status": CAP_STATUS,
                    "complete": False,
                    "structures": [],
                    "partial_structure_count": len(accepted),
                    "states_expanded": states_expanded,
                    "states_discovered": len(seen),
                    "cap_reached": "max_states_discovered",
                    "contract": CONTRACT,
                    "frontier_contract": FRONTIER_CONTRACT,
                }
            seen.add(new_state)
            new_key = tuple(sorted(new_state))
            heappush(heap, (len(new_key), new_key))

    accepted.sort(
        key=lambda item: (
            item.edge_count,
            item.link_ids,
            item.vertex_ids,
        )
    )
    return {
        "status": "PASS_COMPLETE_CONNECTED_ONLY_STRUCTURE_ENUMERATION",
        "complete": True,
        "structures": accepted,
        "structure_count": len(accepted),
        "states_expanded": states_expanded,
        "states_discovered": len(seen),
        "frontier_expansion_attempts": frontier_expansion_attempts,
        "duplicate_expansion_attempts": duplicate_expansion_attempts,
        "required_terminal_ids": required_terminals,
        "required_policy_groups": groups,
        "technical_parameters": {
            "min_edges": min_edges,
            "max_edges": upper,
            "max_states": max_states,
            "max_structures": max_structures,
            "semantics": "TECHNICAL_ENUMERATION_CONTROLS_NOT_POLICY_WEIGHTS",
        },
        "contract": CONTRACT,
        "frontier_contract": FRONTIER_CONTRACT,
        "topology_semantics": "DESCRIPTIVE_POST_GENERATION_CLASSIFICATION",
        "generation_semantics": "CONNECTED_FRONTIER_EXPANSION_WITHOUT_TOPOLOGY_FILTERING",
    }
