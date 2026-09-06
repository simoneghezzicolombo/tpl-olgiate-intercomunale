"""Exact minimum-edge policy-backbone enumeration for RT-022 V3.

This enumerator is topology-neutral. It derives the minimum edge count only from
the frozen policy contract that every routing terminal belongs to exactly one of
the required policy groups. With G required groups, any connected structure
covering all groups needs at least G-1 edges. At that exact edge count it must
contain exactly one terminal from each group.

Topology labels are computed only after a candidate has been generated.
"""
from __future__ import annotations

from itertools import combinations, product
from typing import Iterable, Mapping

from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    CONTRACT,
    StructureRecord,
    _normalise_links,
    classify_connected_structure,
)

MINIMUM_BACKBONE_CONTRACT = (
    "EXACT_MINIMUM_EDGE_POLICY_COVERAGE_WITHOUT_TOPOLOGY_GENERATION_PRIOR"
)
PASS_STATUS = "PASS_COMPLETE_EXACT_MINIMUM_POLICY_BACKBONE_ENUMERATION"


def enumerate_exact_minimum_policy_backbones(
    links: Iterable[AbstractLink | Mapping[str, str]],
    *,
    required_policy_groups: Iterable[str],
    terminal_policy_groups: Mapping[str, Iterable[str]],
) -> dict:
    """Enumerate every connected minimum-edge structure satisfying all groups."""
    normalised = _normalise_links(links)
    if not normalised:
        raise ValueError("abstract pair graph must contain at least one link")

    groups = tuple(sorted({str(item).strip() for item in required_policy_groups if str(item).strip()}))
    if len(groups) < 2:
        raise ValueError("exact minimum-policy search requires at least two policy groups")

    all_vertices = tuple(sorted({link.u for link in normalised} | {link.v for link in normalised}))
    group_set = set(groups)
    group_by_terminal: dict[str, str] = {}
    terminals_by_group: dict[str, list[str]] = {group: [] for group in groups}

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
                "minimum-edge derivation requires every graph terminal to belong "
                f"to exactly one required policy group: {terminal} -> {memberships}"
            )
        group = memberships[0]
        group_by_terminal[terminal] = group
        terminals_by_group[group].append(terminal)

    missing_groups = [group for group in groups if not terminals_by_group[group]]
    if missing_groups:
        raise ValueError(f"required policy groups absent from pair graph: {missing_groups}")
    for group in groups:
        terminals_by_group[group].sort()

    minimum_edge_count = len(groups) - 1
    pair_lookup = {(link.u, link.v): link for link in normalised}
    accepted: list[StructureRecord] = []
    seen_link_sets: set[tuple[str, ...]] = set()
    terminal_tuples_scanned = 0
    induced_edge_combinations_scanned = 0
    terminal_tuples_with_enough_links = 0

    for chosen in product(*(terminals_by_group[group] for group in groups)):
        terminal_tuples_scanned += 1
        chosen_vertices = frozenset(chosen)
        if len(chosen_vertices) != len(groups):
            raise AssertionError("one-terminal-per-group product produced duplicate terminal identity")

        induced: list[AbstractLink] = []
        for u, v in combinations(sorted(chosen_vertices), 2):
            link = pair_lookup.get((u, v))
            if link is not None:
                induced.append(link)
        if len(induced) < minimum_edge_count:
            continue
        terminal_tuples_with_enough_links += 1

        for subset in combinations(induced, minimum_edge_count):
            induced_edge_combinations_scanned += 1
            vertices = {endpoint for link in subset for endpoint in (link.u, link.v)}
            if vertices != set(chosen_vertices):
                continue
            try:
                record = classify_connected_structure(subset)
            except ValueError as exc:
                if "disconnected" in str(exc):
                    continue
                raise
            if record.edge_count != minimum_edge_count or record.vertex_count != len(groups):
                raise AssertionError("accepted minimum backbone violates derived size identity")
            link_key = record.link_ids
            if link_key in seen_link_sets:
                raise AssertionError(f"duplicate minimum backbone generated: {link_key}")
            seen_link_sets.add(link_key)
            accepted.append(record)

    accepted.sort(key=lambda item: (item.link_ids, item.vertex_ids))
    return {
        "status": PASS_STATUS,
        "complete": True,
        "structures": accepted,
        "structure_count": len(accepted),
        "required_policy_groups": groups,
        "derived_minimum_edge_count": minimum_edge_count,
        "terminal_tuple_count": terminal_tuples_scanned,
        "terminal_tuples_with_enough_induced_links": terminal_tuples_with_enough_links,
        "induced_edge_combinations_scanned": induced_edge_combinations_scanned,
        "contract": CONTRACT,
        "frontier_contract": MINIMUM_BACKBONE_CONTRACT,
        "topology_semantics": "DESCRIPTIVE_POST_GENERATION_CLASSIFICATION",
        "generation_semantics": (
            "ONE_TERMINAL_PER_REQUIRED_GROUP_THEN_EXACT_CONNECTED_G_MINUS_1_EDGE_ENUMERATION"
        ),
        "proof_semantics": (
            "WITH_EXACTLY_ONE_REQUIRED_GROUP_PER_TERMINAL_A_CONNECTED_STRUCTURE_COVERING_G_GROUPS_"
            "NEEDS_AT_LEAST_G_MINUS_1_EDGES;AT_EQUALITY_IT_HAS_EXACTLY_G_VERTICES"
        ),
        "technical_parameters": {
            "search_scope": "EXACT_MINIMUM_POLICY_BACKBONES_ONLY",
            "minimum_edge_count": minimum_edge_count,
            "enumeration_cap": None,
            "semantics": "LOGICALLY_DERIVED_MINIMUM_NOT_POLICY_WEIGHT_OR_TOPOLOGY_PRIOR",
        },
    }
