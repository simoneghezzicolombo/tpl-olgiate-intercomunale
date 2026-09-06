from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

CONTRACT = "RT031_HAMILTONIAN_EXPRESSIVENESS_DIAGNOSTIC_V3"
STATUS = "PASS_HAMILTONIAN_EXPRESSIVENESS_DIAGNOSTIC_NOT_NETWORK_SEARCH_PASS"
EXPECTED_SCOPE = "RECIPROCAL_BIDIRECTIONAL_STRUCTURAL_LINK_INTERFACE_NOT_NETWORK_SELECTION"


class RT031HamiltonianContractError(ValueError):
    """Fail-closed RT-031 Hamiltonian diagnostic contract violation."""


@dataclass(frozen=True)
class FrozenStructuralGraph:
    vertices: tuple[str, ...]
    adjacency: Mapping[str, tuple[str, ...]]
    link_by_pair: Mapping[tuple[str, str], str]


@dataclass(frozen=True)
class HamiltonianWitness:
    feasible: bool
    ordered_vertices: tuple[str, ...]
    ordered_link_ids: tuple[str, ...]
    search_calls: int


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def validate_reciprocal_structural_graph(
    links: pd.DataFrame,
    *,
    expected_vertex_count: int | None = 35,
    expected_link_count: int | None = 110,
) -> FrozenStructuralGraph:
    required = {
        "structural_link_id", "terminal_a", "terminal_b", "eligibility_status",
        "eligible_for_bidirectional_undirected_structure", "scope",
    }
    missing = sorted(required - set(links.columns))
    if missing:
        raise RT031HamiltonianContractError(f"reciprocal structural-link table missing columns: {missing}")
    frame = links.copy()
    if expected_link_count is not None and len(frame) != int(expected_link_count):
        raise RT031HamiltonianContractError(f"expected {expected_link_count} structural links, got {len(frame)}")
    if frame["structural_link_id"].astype(str).duplicated().any():
        raise RT031HamiltonianContractError("duplicate structural_link_id")
    if not frame["eligible_for_bidirectional_undirected_structure"].astype(bool).all():
        raise RT031HamiltonianContractError("non-reciprocal link entered reciprocal graph")
    if not (frame["eligibility_status"].astype(str) == "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE").all():
        raise RT031HamiltonianContractError("unexpected reciprocal eligibility status")
    if not (frame["scope"].astype(str) == EXPECTED_SCOPE).all():
        raise RT031HamiltonianContractError("unexpected structural-link scope")

    adjacency: dict[str, set[str]] = defaultdict(set)
    link_by_pair: dict[tuple[str, str], str] = {}
    for row in frame.itertuples(index=False):
        link_id = str(row.structural_link_id).strip()
        a = str(row.terminal_a).strip()
        b = str(row.terminal_b).strip()
        if not link_id or not a or not b:
            raise RT031HamiltonianContractError("blank structural identity")
        if a == b:
            raise RT031HamiltonianContractError(f"self-loop in {link_id}")
        key = _pair(a, b)
        if key in link_by_pair:
            raise RT031HamiltonianContractError(f"parallel structural links for undirected pair {key}")
        link_by_pair[key] = link_id
        adjacency[a].add(b)
        adjacency[b].add(a)

    vertices = tuple(sorted(adjacency))
    if expected_vertex_count is not None and len(vertices) != int(expected_vertex_count):
        raise RT031HamiltonianContractError(f"expected {expected_vertex_count} structural vertices, got {len(vertices)}")
    return FrozenStructuralGraph(
        vertices=vertices,
        adjacency={v: tuple(sorted(adjacency[v])) for v in vertices},
        link_by_pair=dict(sorted(link_by_pair.items())),
    )


def _remaining_connected(adjacency: Mapping[str, Sequence[str]], allowed: set[str], seed: str) -> bool:
    stack = [seed]
    seen = {seed}
    while stack:
        current = stack.pop()
        for neighbor in adjacency[current]:
            if neighbor in allowed and neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return seen == allowed


def find_hamiltonian_path(graph: FrozenStructuralGraph) -> HamiltonianWitness:
    vertices, adjacency = graph.vertices, graph.adjacency
    n = len(vertices)
    if n == 0:
        return HamiltonianWitness(False, tuple(), tuple(), 0)
    calls = 0
    for start in sorted(vertices, key=lambda v: (len(adjacency[v]), v)):
        path = [start]
        used = {start}
        def dfs(current: str) -> bool:
            nonlocal calls
            calls += 1
            if len(path) == n:
                return True
            unvisited = set(vertices) - used
            allowed = unvisited | {current}
            if any(not any(w in allowed for w in adjacency[v]) for v in unvisited):
                return False
            if not _remaining_connected(adjacency, allowed, current):
                return False
            candidates = [v for v in adjacency[current] if v not in used]
            candidates.sort(key=lambda v: (sum(1 for w in adjacency[v] if w not in used), v))
            for nxt in candidates:
                used.add(nxt); path.append(nxt)
                if dfs(nxt):
                    return True
                path.pop(); used.remove(nxt)
            return False
        if dfs(start):
            forward, reverse = tuple(path), tuple(reversed(path))
            ordered = min(forward, reverse)
            link_ids = tuple(graph.link_by_pair[_pair(a, b)] for a, b in zip(ordered, ordered[1:]))
            return HamiltonianWitness(True, ordered, link_ids, calls)
    return HamiltonianWitness(False, tuple(), tuple(), calls)


def find_hamiltonian_cycle(graph: FrozenStructuralGraph) -> HamiltonianWitness:
    vertices, adjacency = graph.vertices, graph.adjacency
    n = len(vertices)
    if n < 3:
        return HamiltonianWitness(False, tuple(), tuple(), 0)
    start = vertices[0]
    path = [start]
    used = {start}
    calls = 0
    def dfs(current: str) -> bool:
        nonlocal calls
        calls += 1
        if len(path) == n:
            return start in adjacency[current]
        unvisited = set(vertices) - used
        allowed = unvisited | {current, start}
        if any(sum(1 for w in adjacency[v] if w in allowed) < 2 for v in unvisited):
            return False
        if not _remaining_connected(adjacency, allowed, current):
            return False
        candidates = [v for v in adjacency[current] if v not in used]
        candidates.sort(key=lambda v: (sum(1 for w in adjacency[v] if w not in used), v))
        for nxt in candidates:
            if len(path) == n - 1 and start not in adjacency[nxt]:
                continue
            used.add(nxt); path.append(nxt)
            if dfs(nxt):
                return True
            path.pop(); used.remove(nxt)
        return False
    if not dfs(start):
        return HamiltonianWitness(False, tuple(), tuple(), calls)
    forward = tuple(path)
    reverse = (forward[0],) + tuple(reversed(forward[1:]))
    ordered = min(forward, reverse)
    pairs = list(zip(ordered, ordered[1:])) + [(ordered[-1], ordered[0])]
    link_ids = tuple(graph.link_by_pair[_pair(a, b)] for a, b in pairs)
    return HamiltonianWitness(True, ordered, link_ids, calls)


def verify_witness(graph: FrozenStructuralGraph, witness: HamiltonianWitness, *, cycle: bool) -> None:
    if not witness.feasible:
        return
    ordered = witness.ordered_vertices
    if len(ordered) != len(graph.vertices) or len(set(ordered)) != len(ordered) or set(ordered) != set(graph.vertices):
        raise RT031HamiltonianContractError("Hamiltonian witness does not cover every vertex exactly once")
    pairs = list(zip(ordered, ordered[1:]))
    if cycle:
        pairs.append((ordered[-1], ordered[0]))
    expected = []
    for a, b in pairs:
        key = _pair(a, b)
        if key not in graph.link_by_pair:
            raise RT031HamiltonianContractError(f"witness uses absent structural edge {a} <-> {b}")
        expected.append(graph.link_by_pair[key])
    if tuple(expected) != witness.ordered_link_ids:
        raise RT031HamiltonianContractError("witness link sequence mismatch")


def witness_table(path: HamiltonianWitness, cycle: HamiltonianWitness) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for witness_type, witness, is_cycle in (("HAMILTONIAN_PATH", path, False), ("HAMILTONIAN_CYCLE", cycle, True)):
        if not witness.feasible:
            continue
        for ordinal, stop_id in enumerate(witness.ordered_vertices, start=1):
            outgoing = witness.ordered_link_ids[ordinal - 1] if (is_cycle or ordinal <= len(witness.ordered_link_ids)) else ""
            rows.append({
                "witness_type": witness_type,
                "stop_ordinal": ordinal,
                "stop_place_id": stop_id,
                "outgoing_structural_link_id": outgoing,
                "diagnostic_only_not_route_recommendation": True,
            })
    return pd.DataFrame(rows).sort_values(["witness_type", "stop_ordinal"], kind="mergesort").reset_index(drop=True)


def build_audit(graph: FrozenStructuralGraph, path: HamiltonianWitness, cycle: HamiltonianWitness, *, reciprocal_link_file_sha256: str) -> dict[str, object]:
    verify_witness(graph, path, cycle=False)
    verify_witness(graph, cycle, cycle=True)
    return {
        "contract": CONTRACT,
        "status": STATUS,
        "reciprocal_link_file_sha256": reciprocal_link_file_sha256,
        "structural_vertex_count": len(graph.vertices),
        "structural_link_count": len(graph.link_by_pair),
        "hamiltonian_path_feasible": path.feasible,
        "hamiltonian_path_vertex_count": len(path.ordered_vertices),
        "hamiltonian_path_link_count": len(path.ordered_link_ids),
        "hamiltonian_path_search_calls": path.search_calls,
        "hamiltonian_cycle_feasible": cycle.feasible,
        "hamiltonian_cycle_vertex_count": len(cycle.ordered_vertices),
        "hamiltonian_cycle_link_count": len(cycle.ordered_link_ids),
        "hamiltonian_cycle_search_calls": cycle.search_calls,
        "interpretation": "Structural-graph expressiveness witness only. It does not certify a timetable, preferred route, turn-continuous composed bus geometry, service frequency, or operational optimality.",
        "negative_assertions": {
            "selects_network_winner": False,
            "labels_witness_as_route_recommendation": False,
            "uses_manual_locality_forcing": False,
            "uses_random_search": False,
            "uses_synthetic_territorial_edges": False,
            "uses_elementary_edge_count_cap": False,
            "claims_hamiltonian_witness_is_operationally_optimal": False,
            "claims_rt031_search_pass": False,
        },
    }


def write_outputs(links: pd.DataFrame, *, reciprocal_link_file_sha256: str, outdir: str | Path) -> dict[str, object]:
    graph = validate_reciprocal_structural_graph(links)
    path = find_hamiltonian_path(graph)
    cycle = find_hamiltonian_cycle(graph)
    audit = build_audit(graph, path, cycle, reciprocal_link_file_sha256=reciprocal_link_file_sha256)
    destination = Path(outdir)
    destination.mkdir(parents=True, exist_ok=True)
    witness_table(path, cycle).to_csv(destination / "rt031_hamiltonian_structural_witnesses.csv", index=False, lineterminator="\n")
    (destination / "rt031_hamiltonian_expressiveness_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit
