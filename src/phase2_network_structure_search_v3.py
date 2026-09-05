"""Generic deterministic network-structure enumeration for Phase 2 V3.

This module operates only on an abstract undirected terminal-pair graph.
It does not know settlement names, stop names, road geometry, passenger stop
patterns, timetables, demand, accessibility, kilometres or route winners.

Topology is classified *after* connected subgraphs are generated. Topology
labels and shape flags are descriptive diagnostics, never generation priors or
policy scores.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Mapping, Sequence


CONTRACT = "ABSTRACT_NETWORK_STRUCTURES_NOT_TERRITORIAL_RECOMMENDATIONS"
CAP_STATUS = "BLOCKED_ENUMERATION_CAP_REACHED_FAIL_CLOSED"


@dataclass(frozen=True, order=True)
class AbstractLink:
    link_id: str
    u: str
    v: str


@dataclass(frozen=True)
class StructureRecord:
    link_ids: tuple[str, ...]
    vertex_ids: tuple[str, ...]
    topology_class: str
    shape_flags: tuple[str, ...]
    vertex_count: int
    edge_count: int
    cycle_rank: int
    max_degree: int
    leaf_count: int
    branch_vertex_count: int
    articulation_vertex_count: int
    articulation_vertex_ids: tuple[str, ...]


def _normalise_links(
    links: Iterable[AbstractLink | Mapping[str, str]],
) -> tuple[AbstractLink, ...]:
    normalised: list[AbstractLink] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()

    for raw in links:
        if isinstance(raw, AbstractLink):
            link = raw
        else:
            link = AbstractLink(
                link_id=str(raw["link_id"]),
                u=str(raw["u"]),
                v=str(raw["v"]),
            )
        link_id = str(link.link_id).strip()
        u = str(link.u).strip()
        v = str(link.v).strip()
        if not link_id or not u or not v:
            raise ValueError("link_id, u and v must be non-empty")
        if u == v:
            raise ValueError(f"self-loop is not allowed in abstract pair graph: {link_id}")
        if link_id in seen_ids:
            raise ValueError(f"duplicate link_id: {link_id}")
        pair = tuple(sorted((u, v)))
        if pair in seen_pairs:
            raise ValueError(
                "parallel terminal pair is not allowed in structural graph: "
                f"{pair[0]}--{pair[1]}"
            )
        seen_ids.add(link_id)
        seen_pairs.add(pair)
        normalised.append(AbstractLink(link_id=link_id, u=pair[0], v=pair[1]))

    return tuple(sorted(normalised, key=lambda item: (item.link_id, item.u, item.v)))


def _adjacency(links: Sequence[AbstractLink]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {}
    for link in links:
        adjacency.setdefault(link.u, set()).add(link.v)
        adjacency.setdefault(link.v, set()).add(link.u)
    return adjacency


def _is_connected(adjacency: Mapping[str, set[str]]) -> bool:
    if not adjacency:
        return False
    start = min(adjacency)
    stack = [start]
    seen: set[str] = set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(sorted(adjacency[node] - seen, reverse=True))
    return len(seen) == len(adjacency)


def articulation_vertices(adjacency: Mapping[str, set[str]]) -> tuple[str, ...]:
    """Return articulation vertices of a connected simple undirected graph."""
    if not adjacency:
        return ()

    time = 0
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    articulations: set[str] = set()

    def dfs(node: str) -> None:
        nonlocal time
        time += 1
        discovery[node] = time
        low[node] = time
        child_count = 0

        for neighbour in sorted(adjacency[node]):
            if neighbour not in discovery:
                parent[neighbour] = node
                child_count += 1
                dfs(neighbour)
                low[node] = min(low[node], low[neighbour])

                if parent.get(node) is None and child_count > 1:
                    articulations.add(node)
                if parent.get(node) is not None and low[neighbour] >= discovery[node]:
                    articulations.add(node)
            elif neighbour != parent.get(node):
                low[node] = min(low[node], discovery[neighbour])

    for root in sorted(adjacency):
        if root not in discovery:
            parent[root] = None
            dfs(root)
    return tuple(sorted(articulations))


def classify_connected_structure(
    links: Iterable[AbstractLink | Mapping[str, str]],
) -> StructureRecord:
    """Classify one connected abstract structure after it has been generated."""
    normalised = _normalise_links(links)
    if not normalised:
        raise ValueError("a candidate structure must contain at least one link")

    adjacency = _adjacency(normalised)
    if not _is_connected(adjacency):
        raise ValueError("candidate structure is disconnected")

    degrees = {node: len(neighbours) for node, neighbours in adjacency.items()}
    vertex_ids = tuple(sorted(adjacency))
    link_ids = tuple(link.link_id for link in normalised)
    vertex_count = len(vertex_ids)
    edge_count = len(normalised)
    cycle_rank = edge_count - vertex_count + 1
    max_degree = max(degrees.values())
    leaf_count = sum(degree == 1 for degree in degrees.values())
    branch_vertex_count = sum(degree >= 3 for degree in degrees.values())
    articulations = articulation_vertices(adjacency)

    flags: list[str] = []
    if cycle_rank == 0:
        topology_class = "PATH" if max_degree <= 2 else "TREE_BRANCHING"
    elif cycle_rank == 1:
        topology_class = (
            "CYCLE"
            if all(degree == 2 for degree in degrees.values())
            else "UNICYCLIC_BRANCHING"
        )
    elif cycle_rank == 2:
        topology_class = (
            "BICYCLIC_ARTICULATED" if articulations else "BICYCLIC_NONARTICULATED"
        )
        if (
            len(articulations) == 1
            and degrees[articulations[0]] == 4
            and all(
                degree == 2
                for node, degree in degrees.items()
                if node != articulations[0]
            )
        ):
            flags.append("FIGURE_EIGHT_LIKE")
    else:
        topology_class = "MULTICYCLIC"

    return StructureRecord(
        link_ids=link_ids,
        vertex_ids=vertex_ids,
        topology_class=topology_class,
        shape_flags=tuple(flags),
        vertex_count=vertex_count,
        edge_count=edge_count,
        cycle_rank=cycle_rank,
        max_degree=max_degree,
        leaf_count=leaf_count,
        branch_vertex_count=branch_vertex_count,
        articulation_vertex_count=len(articulations),
        articulation_vertex_ids=articulations,
    )


def _group_coverage_ok(
    vertices: set[str],
    required_policy_groups: Sequence[str],
    terminal_policy_groups: Mapping[str, Iterable[str]],
) -> bool:
    if not required_policy_groups:
        return True
    covered: set[str] = set()
    for terminal in vertices:
        covered.update(str(group) for group in terminal_policy_groups.get(terminal, ()))
    return set(required_policy_groups).issubset(covered)


def enumerate_connected_structures(
    links: Iterable[AbstractLink | Mapping[str, str]],
    *,
    required_terminal_ids: Iterable[str] = (),
    required_policy_groups: Iterable[str] = (),
    terminal_policy_groups: Mapping[str, Iterable[str]] | None = None,
    min_edges: int = 1,
    max_edges: int | None = None,
    max_subsets_scanned: int = 100_000,
    max_structures: int = 20_000,
) -> dict:
    """Enumerate connected edge-induced structures deterministically.

    Only generic hard requirements are applied during generation:
    connectivity, required terminal IDs, required policy-group coverage and
    explicit technical enumeration caps. No topology family is filtered in or
    out by this function.

    If either technical cap is reached, the function fails closed and does not
    return a partial candidate pool as usable evidence.
    """
    normalised = _normalise_links(links)
    if not normalised:
        raise ValueError("abstract pair graph must contain at least one link")
    if min_edges < 1:
        raise ValueError("min_edges must be >= 1")
    if max_subsets_scanned < 1 or max_structures < 1:
        raise ValueError("enumeration caps must be >= 1")

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

    scanned = 0
    accepted: list[StructureRecord] = []

    for edge_count in range(min_edges, upper + 1):
        for subset in combinations(normalised, edge_count):
            scanned += 1
            if scanned > max_subsets_scanned:
                return {
                    "status": CAP_STATUS,
                    "complete": False,
                    "structures": [],
                    "partial_structure_count": len(accepted),
                    "subsets_scanned": scanned - 1,
                    "cap_reached": "max_subsets_scanned",
                    "contract": CONTRACT,
                }

            adjacency = _adjacency(subset)
            if not _is_connected(adjacency):
                continue
            vertices = set(adjacency)
            if not set(required_terminals).issubset(vertices):
                continue
            if not _group_coverage_ok(vertices, groups, membership):
                continue

            accepted.append(classify_connected_structure(subset))
            if len(accepted) > max_structures:
                return {
                    "status": CAP_STATUS,
                    "complete": False,
                    "structures": [],
                    "partial_structure_count": len(accepted) - 1,
                    "subsets_scanned": scanned,
                    "cap_reached": "max_structures",
                    "contract": CONTRACT,
                }

    accepted.sort(
        key=lambda item: (
            item.edge_count,
            item.link_ids,
            item.vertex_ids,
        )
    )
    return {
        "status": "PASS_COMPLETE_ABSTRACT_STRUCTURE_ENUMERATION",
        "complete": True,
        "structures": accepted,
        "structure_count": len(accepted),
        "subsets_scanned": scanned,
        "required_terminal_ids": required_terminals,
        "required_policy_groups": groups,
        "technical_parameters": {
            "min_edges": min_edges,
            "max_edges": upper,
            "max_subsets_scanned": max_subsets_scanned,
            "max_structures": max_structures,
            "semantics": "TECHNICAL_ENUMERATION_CONTROLS_NOT_POLICY_WEIGHTS",
        },
        "contract": CONTRACT,
        "topology_semantics": "DESCRIPTIVE_POST_GENERATION_CLASSIFICATION",
    }


def structure_to_record(structure: StructureRecord) -> dict:
    return {
        "link_ids": ";".join(structure.link_ids),
        "vertex_ids": ";".join(structure.vertex_ids),
        "topology_class": structure.topology_class,
        "shape_flags": ";".join(structure.shape_flags),
        "vertex_count": structure.vertex_count,
        "edge_count": structure.edge_count,
        "cycle_rank": structure.cycle_rank,
        "max_degree": structure.max_degree,
        "leaf_count": structure.leaf_count,
        "branch_vertex_count": structure.branch_vertex_count,
        "articulation_vertex_count": structure.articulation_vertex_count,
        "articulation_vertex_ids": ";".join(structure.articulation_vertex_ids),
        "contract": CONTRACT,
    }
