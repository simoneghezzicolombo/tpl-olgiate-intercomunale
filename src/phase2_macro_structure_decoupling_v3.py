from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd

CONTRACT = "RT031_MACRO_STRUCTURE_DECOUPLING_V3"


class RT031ContractError(ValueError):
    """Fail-closed RT-031 contract violation."""


def _text(value: object, label: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise RT031ContractError(f"{label} must be non-null")
    text = str(value).strip()
    if not text:
        raise RT031ContractError(f"{label} must be non-empty")
    return text


def _split_unique_ids(value: object, label: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in _text(value, label).split(";") if part.strip())
    if not values or len(values) != len(set(values)):
        raise RT031ContractError(f"{label} must contain unique non-empty semicolon-separated IDs")
    return values


def build_link_endpoint_map(realizations: pd.DataFrame) -> dict[str, tuple[str, str]]:
    required = {"structural_link_id", "source_stop_place_id", "target_stop_place_id"}
    missing = sorted(required - set(realizations.columns))
    if missing:
        raise RT031ContractError(f"RT-023 realizations missing columns: {missing}")
    endpoint_map: dict[str, tuple[str, str]] = {}
    for link_id, group in realizations.groupby("structural_link_id", sort=True):
        lid = _text(link_id, "structural_link_id")
        pairs = {
            tuple(sorted((_text(row.source_stop_place_id, f"{lid} source"), _text(row.target_stop_place_id, f"{lid} target"))))
            for row in group.itertuples(index=False)
        }
        if len(pairs) != 1:
            raise RT031ContractError(f"{lid} does not map to one frozen unordered endpoint pair")
        a, b = next(iter(pairs))
        if a == b:
            raise RT031ContractError(f"{lid} is a self-loop elementary link")
        endpoint_map[lid] = (a, b)
    if not endpoint_map:
        raise RT031ContractError("empty structural link endpoint map")
    return endpoint_map


def _adjacency(link_ids: Sequence[str], endpoint_map: Mapping[str, tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    adj: dict[str, list[tuple[str, str]]] = {}
    for link_id in link_ids:
        if link_id not in endpoint_map:
            raise RT031ContractError(f"structure references unknown link {link_id}")
        a, b = endpoint_map[link_id]
        adj.setdefault(a, []).append((link_id, b))
        adj.setdefault(b, []).append((link_id, a))
    for vertex in adj:
        adj[vertex].sort()
    return adj


def _assert_connected(adj: Mapping[str, Sequence[tuple[str, str]]]) -> None:
    if not adj:
        raise RT031ContractError("empty structure graph")
    start = min(adj)
    seen = {start}
    stack = [start]
    while stack:
        vertex = stack.pop()
        for _, neighbour in adj[vertex]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    if seen != set(adj):
        raise RT031ContractError("structure graph must be connected")


def _canonical_chain(vertices: Sequence[str], links: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    fv = tuple(vertices)
    fl = tuple(links)
    rv = tuple(reversed(fv))
    rl = tuple(reversed(fl))
    return (fv, fl) if (fv, fl) <= (rv, rl) else (rv, rl)


def _canonical_cycle(start: str, first_link: str, adj: Mapping[str, Sequence[tuple[str, str]]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    vertices = [start]
    links: list[str] = []
    current = start
    incoming: str | None = None
    next_link = first_link
    max_steps = sum(len(v) for v in adj.values()) // 2 + 1
    for _ in range(max_steps):
        options = {link_id: neighbour for link_id, neighbour in adj[current]}
        if next_link not in options:
            raise RT031ContractError("cycle traversal lost its next edge")
        neighbour = options[next_link]
        links.append(next_link)
        vertices.append(neighbour)
        incoming, current = next_link, neighbour
        if current == start:
            break
        candidates = [(link_id, n) for link_id, n in adj[current] if link_id != incoming]
        if len(candidates) != 1:
            raise RT031ContractError("pure cycle traversal encountered non-degree-2 vertex")
        next_link = candidates[0][0]
    else:
        raise RT031ContractError("pure cycle traversal failed to close")
    if vertices[-1] != start or len(set(links)) != len(links):
        raise RT031ContractError("invalid pure cycle traversal")
    return _canonical_chain(vertices, links)


@dataclass(frozen=True)
class MacroStructure:
    structure_id: str
    elementary_vertex_count: int
    elementary_edge_count: int
    cycle_rank: int
    degree_two_vertex_count: int
    macro_node_count: int
    macro_edge_count: int
    leaf_count: int
    branch_vertex_count: int
    branch_degree_sequence: tuple[int, ...]
    pure_cycle: bool
    macro_topology_class: str
    macro_edges: tuple[tuple[str, ...], ...]
    macro_edge_links: tuple[tuple[str, ...], ...]


def contract_structure(
    structure_id: str,
    link_ids: Sequence[str],
    vertex_ids: Sequence[str],
    endpoint_map: Mapping[str, tuple[str, str]],
) -> MacroStructure:
    if len(link_ids) != len(set(link_ids)) or not link_ids:
        raise RT031ContractError(f"{structure_id} link_ids must be unique and non-empty")
    if len(vertex_ids) != len(set(vertex_ids)) or not vertex_ids:
        raise RT031ContractError(f"{structure_id} vertex_ids must be unique and non-empty")
    adj = _adjacency(link_ids, endpoint_map)
    if set(adj) != set(vertex_ids):
        raise RT031ContractError(f"{structure_id} vertex_ids do not equal link endpoint universe")
    _assert_connected(adj)
    degree = {vertex: len(edges) for vertex, edges in adj.items()}
    edge_count = len(link_ids)
    vertex_count = len(vertex_ids)
    cycle_rank = edge_count - vertex_count + 1
    if cycle_rank < 0:
        raise RT031ContractError(f"{structure_id} has invalid connected-graph cycle rank")

    macro_nodes = tuple(sorted(vertex for vertex, deg in degree.items() if deg != 2))
    pure_cycle = len(macro_nodes) == 0
    visited: set[str] = set()
    chains: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    if pure_cycle:
        if any(deg != 2 for deg in degree.values()) or cycle_rank != 1:
            raise RT031ContractError(f"{structure_id} zero-macro-node graph is not a simple cycle")
        start = min(adj)
        first_link = min(link_id for link_id, _ in adj[start])
        chain = _canonical_cycle(start, first_link, adj)
        chains.append(chain)
        visited.update(chain[1])
    else:
        for start in macro_nodes:
            for first_link, first_neighbour in adj[start]:
                if first_link in visited:
                    continue
                vertices = [start, first_neighbour]
                links = [first_link]
                visited.add(first_link)
                previous_link = first_link
                current = first_neighbour
                max_steps = edge_count + 1
                for _ in range(max_steps):
                    if current in macro_nodes:
                        break
                    if degree[current] != 2:
                        raise RT031ContractError(f"{structure_id} traversal hit unexpected degree")
                    candidates = [(link_id, neighbour) for link_id, neighbour in adj[current] if link_id != previous_link]
                    if len(candidates) != 1:
                        raise RT031ContractError(f"{structure_id} degree-2 traversal is ambiguous")
                    next_link, next_neighbour = candidates[0]
                    if next_link in visited:
                        raise RT031ContractError(f"{structure_id} degree-2 chain reuses an elementary link")
                    visited.add(next_link)
                    links.append(next_link)
                    vertices.append(next_neighbour)
                    previous_link, current = next_link, next_neighbour
                else:
                    raise RT031ContractError(f"{structure_id} macro-chain traversal exceeded edge count")
                chains.append(_canonical_chain(vertices, links))

    if visited != set(link_ids):
        missing = sorted(set(link_ids) - visited)
        raise RT031ContractError(f"{structure_id} contraction did not cover every elementary link: {missing}")
    flattened = [link for _, links in chains for link in links]
    if len(flattened) != len(set(flattened)) or set(flattened) != set(link_ids):
        raise RT031ContractError(f"{structure_id} contraction is not a lossless edge partition")

    chains.sort(key=lambda item: (item[0], item[1]))
    leaf_count = sum(deg == 1 for deg in degree.values())
    branch_degrees = tuple(sorted(deg for deg in degree.values() if deg >= 3))
    branch_count = len(branch_degrees)
    if pure_cycle:
        macro_topology = "PURE_CYCLE_CORE"
    elif cycle_rank == 0 and branch_count == 0 and leaf_count == 2:
        macro_topology = "PATH_CORE"
    elif cycle_rank == 0:
        macro_topology = "TREE_BRANCHING_CORE"
    else:
        macro_topology = "CYCLIC_BRANCHING_CORE"

    return MacroStructure(
        structure_id=structure_id,
        elementary_vertex_count=vertex_count,
        elementary_edge_count=edge_count,
        cycle_rank=cycle_rank,
        degree_two_vertex_count=sum(deg == 2 for deg in degree.values()),
        macro_node_count=0 if pure_cycle else len(macro_nodes),
        macro_edge_count=len(chains),
        leaf_count=leaf_count,
        branch_vertex_count=branch_count,
        branch_degree_sequence=branch_degrees,
        pure_cycle=pure_cycle,
        macro_topology_class=macro_topology,
        macro_edges=tuple(vertices for vertices, _ in chains),
        macro_edge_links=tuple(links for _, links in chains),
    )


def compile_macro_structures(
    structures: pd.DataFrame,
    realizations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    required = {"structure_id", "link_ids", "vertex_ids", "edge_count", "vertex_count", "cycle_rank"}
    missing = sorted(required - set(structures.columns))
    if missing:
        raise RT031ContractError(f"structure universe missing columns: {missing}")
    if structures["structure_id"].astype(str).duplicated().any():
        raise RT031ContractError("duplicate structure_id")
    endpoint_map = build_link_endpoint_map(realizations)
    summary_rows: list[dict[str, object]] = []
    edge_rows: list[dict[str, object]] = []
    for row in structures.sort_values("structure_id", kind="mergesort").itertuples(index=False):
        sid = _text(row.structure_id, "structure_id")
        links = _split_unique_ids(row.link_ids, f"{sid} link_ids")
        vertices = _split_unique_ids(row.vertex_ids, f"{sid} vertex_ids")
        result = contract_structure(sid, links, vertices, endpoint_map)
        if result.elementary_edge_count != int(row.edge_count) or result.elementary_vertex_count != int(row.vertex_count):
            raise RT031ContractError(f"{sid} declared E/V counts disagree with frozen link graph")
        if result.cycle_rank != int(row.cycle_rank):
            raise RT031ContractError(f"{sid} declared cycle_rank disagrees with frozen link graph")
        summary_rows.append({
            "structure_id": sid,
            "elementary_vertex_count": result.elementary_vertex_count,
            "elementary_edge_count": result.elementary_edge_count,
            "cycle_rank": result.cycle_rank,
            "degree_two_vertex_count": result.degree_two_vertex_count,
            "macro_node_count": result.macro_node_count,
            "macro_edge_count": result.macro_edge_count,
            "leaf_count": result.leaf_count,
            "branch_vertex_count": result.branch_vertex_count,
            "branch_degree_sequence": ";".join(map(str, result.branch_degree_sequence)),
            "pure_cycle": result.pure_cycle,
            "macro_topology_class": result.macro_topology_class,
            "contract": CONTRACT,
        })
        for ordinal, (chain_vertices, chain_links) in enumerate(zip(result.macro_edges, result.macro_edge_links), start=1):
            edge_rows.append({
                "structure_id": sid,
                "macro_edge_ordinal": ordinal,
                "source_macro_vertex": chain_vertices[0] if not result.pure_cycle else "",
                "target_macro_vertex": chain_vertices[-1] if not result.pure_cycle else "",
                "ordered_passenger_vertex_ids": ";".join(chain_vertices),
                "ordered_elementary_link_ids": ";".join(chain_links),
                "elementary_link_count": len(chain_links),
                "intermediate_degree_two_vertex_count": max(0, len(chain_vertices) - 2),
                "is_cycle_macro_edge": chain_vertices[0] == chain_vertices[-1],
                "contract": CONTRACT,
            })
    summary = pd.DataFrame(summary_rows).sort_values("structure_id", kind="mergesort").reset_index(drop=True)
    macro_edges = pd.DataFrame(edge_rows).sort_values(["structure_id", "macro_edge_ordinal"], kind="mergesort").reset_index(drop=True)
    payload = summary.to_csv(index=False, lineterminator="\n").encode("utf-8")
    audit = {
        "contract": CONTRACT,
        "structure_count": int(len(summary)),
        "macro_edge_row_count": int(len(macro_edges)),
        "summary_sha256": hashlib.sha256(payload).hexdigest(),
        "lossless_elementary_link_partition": True,
        "service_terminal_status_inferred": False,
        "municipality_used_for_contraction": False,
        "topology_used_as_generation_filter": False,
        "passenger_vertices_deleted": False,
    }
    return summary, macro_edges, audit
