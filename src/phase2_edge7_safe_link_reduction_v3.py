"""Exact safe-link feasibility reduction for a future edge_count=7 search.

For every structural link, compute the minimum number of original edges in any
connected subgraph that contains that link and covers all required policy
groups. The required link is contracted, a synthetic mandatory-root group is
assigned only to the contracted node, and an exact unweighted group-Steiner
subset DP is solved on the contracted graph. One is added back for the required
edge.

This module is a necessary-condition reduction only. It does not rank links,
select topology, or prove that a retained link occurs in an exact seven-edge
candidate.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from heapq import heappop, heappush
from math import inf
from typing import Iterable, Mapping


CONTRACT = "EXACT_MANDATORY_EDGE_POLICY_COVERAGE_MINIMUM_NOT_NETWORK_SELECTION"
PASS_STATUS = "PASS_EXACT_EDGE7_SAFE_LINK_FEASIBILITY_REDUCTION_V3"


@dataclass(frozen=True, order=True)
class StructuralLink:
    link_id: str
    u: str
    v: str


@dataclass(frozen=True)
class EdgeFeasibility:
    link_id: str
    u: str
    v: str
    minimum_policy_covering_edges_including_link: int | None
    retained_for_edge7_safe_superset: bool
    safely_excludable_from_edge7: bool


def _normalise_links(links: Iterable[StructuralLink | Mapping[str, str]]) -> tuple[StructuralLink, ...]:
    out: list[StructuralLink] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for raw in links:
        if isinstance(raw, StructuralLink):
            link = raw
        else:
            link_id = str(raw.get("link_id", raw.get("structural_link_id", ""))).strip()
            u = str(raw.get("u", raw.get("terminal_a", ""))).strip()
            v = str(raw.get("v", raw.get("terminal_b", ""))).strip()
            link = StructuralLink(link_id, u, v)
        if not link.link_id or not link.u or not link.v:
            raise ValueError("every structural link requires non-empty id/u/v")
        if link.u == link.v:
            raise ValueError(f"self-loop is not allowed: {link.link_id}")
        u, v = sorted((link.u, link.v))
        link = StructuralLink(link.link_id, u, v)
        pair = (u, v)
        if link.link_id in seen_ids:
            raise ValueError(f"duplicate structural link id: {link.link_id}")
        if pair in seen_pairs:
            raise ValueError(f"parallel/duplicate structural pair: {pair}")
        seen_ids.add(link.link_id)
        seen_pairs.add(pair)
        out.append(link)
    if not out:
        raise ValueError("structural graph must contain at least one link")
    return tuple(sorted(out))


def _single_policy_membership(
    vertices: Iterable[str],
    required_policy_groups: Iterable[str],
    terminal_policy_groups: Mapping[str, Iterable[str]],
) -> tuple[tuple[str, ...], dict[str, str]]:
    groups = tuple(sorted({str(g).strip() for g in required_policy_groups if str(g).strip()}))
    if not groups:
        raise ValueError("at least one required policy group is required")
    allowed = set(groups)
    by_terminal: dict[str, str] = {}
    present: set[str] = set()
    for terminal in sorted(set(vertices)):
        memberships = tuple(sorted({
            str(g).strip()
            for g in terminal_policy_groups.get(terminal, ())
            if str(g).strip() in allowed
        }))
        if len(memberships) != 1:
            raise ValueError(
                "every graph terminal must belong to exactly one required policy group: "
                f"{terminal} -> {memberships}"
            )
        by_terminal[terminal] = memberships[0]
        present.add(memberships[0])
    missing = sorted(allowed - present)
    if missing:
        raise ValueError(f"required policy groups absent from structural graph: {missing}")
    return groups, by_terminal


def _contract_required_edge(
    links: tuple[StructuralLink, ...],
    required_link: StructuralLink,
    group_by_terminal: Mapping[str, str],
    group_to_bit: Mapping[str, int],
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]], dict[str, int], str]:
    root = f"__REQ__::{required_link.link_id}"

    def map_vertex(vertex: str) -> str:
        if vertex == required_link.u or vertex == required_link.v:
            return root
        return vertex

    adjacency_sets: dict[str, set[str]] = defaultdict(set)
    contracted_vertices: set[str] = {root}
    for link in links:
        if link.link_id == required_link.link_id:
            continue
        a = map_vertex(link.u)
        b = map_vertex(link.v)
        if a == b:
            continue
        contracted_vertices.update((a, b))
        adjacency_sets[a].add(b)
        adjacency_sets[b].add(a)

    adjacency = {
        vertex: tuple(sorted(adjacency_sets.get(vertex, set())))
        for vertex in sorted(contracted_vertices)
    }

    node_group_mask: dict[str, int] = {vertex: 0 for vertex in contracted_vertices}
    for original, group in group_by_terminal.items():
        contracted = map_vertex(original)
        node_group_mask[contracted] |= 1 << group_to_bit[group]
    mandatory_bit = len(group_to_bit)
    node_group_mask[root] |= 1 << mandatory_bit
    return tuple(sorted(contracted_vertices)), adjacency, node_group_mask, root


def _group_steiner_min_edges(
    vertices: tuple[str, ...],
    adjacency: Mapping[str, tuple[str, ...]],
    node_group_mask: Mapping[str, int],
    group_count: int,
) -> int | None:
    """Exact unweighted group-Steiner minimum using subset DP + graph closure."""
    if group_count < 1:
        raise ValueError("group_count must be positive")
    index = {vertex: i for i, vertex in enumerate(vertices)}
    n = len(vertices)
    full_mask = (1 << group_count) - 1
    dp = [[inf] * n for _ in range(full_mask + 1)]

    for vertex, i in index.items():
        mask = int(node_group_mask.get(vertex, 0))
        bit = 0
        while mask:
            if mask & 1:
                dp[1 << bit][i] = 0
            mask >>= 1
            bit += 1

    for mask in range(1, full_mask + 1):
        # Merge two already-connected Steiner trees at the same root vertex.
        sub = (mask - 1) & mask
        while sub:
            other = mask ^ sub
            if other and sub < other:
                left = dp[sub]
                right = dp[other]
                current = dp[mask]
                for i in range(n):
                    candidate = left[i] + right[i]
                    if candidate < current[i]:
                        current[i] = candidate
            sub = (sub - 1) & mask

        # Multi-source Dijkstra closure on unit-weight graph.
        heap: list[tuple[int, int]] = []
        current = dp[mask]
        for i, value in enumerate(current):
            if value < inf:
                heappush(heap, (int(value), i))
        while heap:
            distance, i = heappop(heap)
            if distance != current[i]:
                continue
            vertex = vertices[i]
            for neighbor in adjacency.get(vertex, ()):
                j = index[neighbor]
                candidate = distance + 1
                if candidate < current[j]:
                    current[j] = candidate
                    heappush(heap, (candidate, j))

    answer = min(dp[full_mask])
    return None if answer == inf else int(answer)


def minimum_policy_covering_edges_including_link(
    links: Iterable[StructuralLink | Mapping[str, str]],
    *,
    required_link_id: str,
    required_policy_groups: Iterable[str],
    terminal_policy_groups: Mapping[str, Iterable[str]],
) -> int | None:
    normalised = _normalise_links(links)
    edge_by_id = {link.link_id: link for link in normalised}
    if required_link_id not in edge_by_id:
        raise ValueError(f"unknown required structural link: {required_link_id}")
    vertices = {endpoint for link in normalised for endpoint in (link.u, link.v)}
    groups, group_by_terminal = _single_policy_membership(
        vertices, required_policy_groups, terminal_policy_groups
    )
    group_to_bit = {group: i for i, group in enumerate(groups)}
    contracted_vertices, adjacency, node_group_mask, _root = _contract_required_edge(
        normalised, edge_by_id[required_link_id], group_by_terminal, group_to_bit
    )
    contracted_min = _group_steiner_min_edges(
        contracted_vertices,
        adjacency,
        node_group_mask,
        group_count=len(groups) + 1,
    )
    return None if contracted_min is None else contracted_min + 1


def build_edge7_safe_link_reduction(
    links: Iterable[StructuralLink | Mapping[str, str]],
    *,
    required_policy_groups: Iterable[str],
    terminal_policy_groups: Mapping[str, Iterable[str]],
    target_edge_count: int = 7,
) -> dict[str, object]:
    normalised = _normalise_links(links)
    vertices = {endpoint for link in normalised for endpoint in (link.u, link.v)}
    groups, _ = _single_policy_membership(vertices, required_policy_groups, terminal_policy_groups)
    if target_edge_count < 1:
        raise ValueError("target_edge_count must be positive")

    records: list[EdgeFeasibility] = []
    distribution: dict[str, int] = defaultdict(int)
    for link in normalised:
        minimum = minimum_policy_covering_edges_including_link(
            normalised,
            required_link_id=link.link_id,
            required_policy_groups=groups,
            terminal_policy_groups=terminal_policy_groups,
        )
        key = "UNREACHABLE" if minimum is None else str(minimum)
        distribution[key] += 1
        retained = minimum is not None and minimum <= target_edge_count
        records.append(
            EdgeFeasibility(
                link_id=link.link_id,
                u=link.u,
                v=link.v,
                minimum_policy_covering_edges_including_link=minimum,
                retained_for_edge7_safe_superset=retained,
                safely_excludable_from_edge7=not retained,
            )
        )

    retained_count = sum(record.retained_for_edge7_safe_superset for record in records)
    excluded_count = len(records) - retained_count
    return {
        "status": PASS_STATUS,
        "complete": True,
        "contract": CONTRACT,
        "target_edge_count": int(target_edge_count),
        "required_policy_groups": groups,
        "records": tuple(records),
        "counts": {
            "structural_links": len(records),
            "retained_safe_superset_links": retained_count,
            "safely_excludable_links": excluded_count,
        },
        "minimum_edge_distribution": dict(sorted(distribution.items(), key=lambda item: item[0])),
        "proof_semantics": (
            "CONTRACT_REQUIRED_EDGE;ADD_SYNTHETIC_ROOT_GROUP;EXACT_GROUP_STEINER_DP;ADD_REQUIRED_EDGE_BACK"
        ),
        "interpretation_boundary": (
            "MINIMUM_GT_TARGET_IS_SAFE_EXCLUSION;MINIMUM_LE_TARGET_IS_RETENTION_ONLY_NOT_EXACT_TARGET_OCCURRENCE_PROOF"
        ),
        "guards": {
            "ranking_performed": False,
            "topology_preference_used": False,
            "service_terminal_selected": False,
            "retained_link_exact_edge7_occurrence_claimed": False,
            "municipality_used_as_routing_fence": False,
        },
    }
