"""Exact seven-edge bicyclic feasibility diagnostic for RT-026 V3.

This module does NOT enumerate the full edge_count=7 topology-neutral universe.
It enumerates only the mathematically complete bicyclic slice.

For a connected graph, cycle_rank = E - V + 1. Therefore E=7 and
cycle_rank=2 implies V=6. With five required policy groups and exactly one
policy-group membership per terminal, a six-terminal policy-covering vertex set
contains exactly one duplicated group. Exhaustively enumerating those vertex
sets and every seven-edge connected subset of their induced structural graph is
therefore complete for the seven-edge bicyclic class.
"""
from __future__ import annotations

from itertools import combinations, product
from typing import Iterable, Mapping

from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    StructureRecord,
    _normalise_links,
    classify_connected_structure,
)

CONTRACT = "EXACT_SEVEN_EDGE_BICYCLIC_FEASIBILITY_DIAGNOSTIC_NOT_FULL_EDGE7_UNIVERSE"
PASS_STATUS = "PASS_COMPLETE_EXACT_SEVEN_EDGE_BICYCLIC_DIAGNOSTIC"


def enumerate_exact_seven_edge_bicyclic_policy_structures(
    links: Iterable[AbstractLink | Mapping[str, str]],
    *,
    required_policy_groups: Iterable[str],
    terminal_policy_groups: Mapping[str, Iterable[str]],
) -> dict[str, object]:
    normalised = _normalise_links(links)
    if not normalised:
        raise ValueError("abstract structural graph must contain links")

    groups = tuple(sorted({str(g).strip() for g in required_policy_groups if str(g).strip()}))
    if len(groups) != 5:
        raise ValueError("RT-026 proof requires exactly five required policy groups")
    group_set = set(groups)

    vertices = tuple(sorted({link.u for link in normalised} | {link.v for link in normalised}))
    group_by_terminal: dict[str, str] = {}
    terminals_by_group: dict[str, list[str]] = {group: [] for group in groups}
    for terminal in vertices:
        memberships = tuple(sorted({
            str(group).strip()
            for group in terminal_policy_groups.get(terminal, ())
            if str(group).strip() in group_set
        }))
        if len(memberships) != 1:
            raise ValueError(
                "every structural terminal must belong to exactly one required policy group: "
                f"{terminal} -> {memberships}"
            )
        group = memberships[0]
        group_by_terminal[terminal] = group
        terminals_by_group[group].append(terminal)

    missing = [group for group in groups if not terminals_by_group[group]]
    if missing:
        raise ValueError(f"required policy groups absent from structural graph: {missing}")
    for group in groups:
        terminals_by_group[group].sort()

    pair_lookup = {(link.u, link.v): link for link in normalised}
    accepted: list[StructureRecord] = []
    accepted_duplicate_groups: list[str] = []
    vertex_sets_scanned = 0
    vertex_sets_with_at_least_seven_induced_links = 0
    seven_edge_subsets_scanned = 0
    seven_edge_subsets_using_all_six_terminals = 0
    seen: set[tuple[str, ...]] = set()

    for duplicate_group in groups:
        other_groups = tuple(group for group in groups if group != duplicate_group)
        for duplicate_pair in combinations(terminals_by_group[duplicate_group], 2):
            for singles in product(*(terminals_by_group[group] for group in other_groups)):
                chosen = tuple(sorted((*duplicate_pair, *singles)))
                if len(set(chosen)) != 6:
                    raise AssertionError("six-terminal policy construction produced duplicate identity")
                chosen_set = set(chosen)
                vertex_sets_scanned += 1

                induced: list[AbstractLink] = []
                for u, v in combinations(chosen, 2):
                    link = pair_lookup.get((u, v))
                    if link is not None:
                        induced.append(link)
                if len(induced) < 7:
                    continue
                vertex_sets_with_at_least_seven_induced_links += 1

                for subset in combinations(induced, 7):
                    seven_edge_subsets_scanned += 1
                    subset_vertices = {
                        endpoint
                        for link in subset
                        for endpoint in (link.u, link.v)
                    }
                    # The bicyclic proof is for V=6. A seven-edge subset can be
                    # connected on only five of the six selected terminals when
                    # the induced graph is dense. Such a subset is outside the
                    # exact E=7,V=6 slice and must be skipped, not reinterpreted.
                    if subset_vertices != chosen_set:
                        continue
                    seven_edge_subsets_using_all_six_terminals += 1
                    try:
                        record = classify_connected_structure(subset)
                    except ValueError as exc:
                        if "disconnected" in str(exc):
                            continue
                        raise
                    if record.edge_count != 7 or record.vertex_count != 6 or record.cycle_rank != 2:
                        raise AssertionError("accepted RT-026 structure violates seven-edge bicyclic identity")
                    if record.link_ids in seen:
                        raise AssertionError(f"duplicate RT-026 structure: {record.link_ids}")
                    seen.add(record.link_ids)
                    accepted.append(record)
                    accepted_duplicate_groups.append(duplicate_group)

    combined = sorted(
        zip(accepted, accepted_duplicate_groups),
        key=lambda item: (item[0].link_ids, item[0].vertex_ids, item[1]),
    )
    return {
        "status": PASS_STATUS,
        "complete": True,
        "structures": [item[0] for item in combined],
        "duplicated_policy_groups": [item[1] for item in combined],
        "structure_count": len(combined),
        "vertex_sets_scanned": vertex_sets_scanned,
        "vertex_sets_with_at_least_seven_induced_links": vertex_sets_with_at_least_seven_induced_links,
        "seven_edge_subsets_scanned": seven_edge_subsets_scanned,
        "seven_edge_subsets_using_all_six_terminals": seven_edge_subsets_using_all_six_terminals,
        "required_policy_groups": groups,
        "contract": CONTRACT,
        "proof_semantics": (
            "CONNECTED_CYCLE_RANK_2_WITH_E7_IMPLIES_V6;"
            "V6_COVERING_FIVE_SINGLE_MEMBERSHIP_POLICY_GROUPS_IMPLIES_EXACTLY_ONE_DUPLICATED_GROUP"
        ),
        "generation_semantics": (
            "ENUMERATE_ALL_SIX_TERMINAL_POLICY_COVERING_VERTEX_SETS_THEN_ALL_SEVEN_EDGE_"
            "SUBSETS_OF_THEIR_INDUCED_STRUCTURAL_GRAPH;REQUIRE_ALL_SIX_SELECTED_TERMINALS;KEEP_CONNECTED_ONLY"
        ),
        "interpretation_boundary": (
            "BICYCLIC_FEASIBILITY_DIAGNOSTIC_ONLY_NOT_FULL_EDGE7_TOPOLOGY_NEUTRAL_CANDIDATE_UNIVERSE"
        ),
    }
