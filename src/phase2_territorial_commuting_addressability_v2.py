"""Pure helpers for Phase 2 Territorial Commuting Addressability V2.

This module measures *structural municipal OD addressability*.  It does not
estimate ridership, mode share, passenger assignment, stop-level origins or
workplace locations.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import unicodedata

CONTRACT = "PHASE2_STRUCTURALLY_ADDRESSABLE_MUNICIPAL_OD_WORKER_MASS_UPPER_BOUND_V2"
STATUS = "PASS_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2_BUILD"
EVALUATED_CATEGORIES = frozenset({"OTHER_CORE", "OTHER_EXTERNAL"})
EXCLUDED_CATEGORIES = frozenset({"SELF", "S8_DIRECT"})


def canonical_place(value: str) -> str:
    """Canonical comparison key without inventing geographic equivalences."""
    return " ".join(unicodedata.normalize("NFKC", value).strip().casefold().split())


@dataclass(frozen=True)
class ODRelation:
    origin_name: str
    destination_name: str
    origin_key: str
    destination_key: str
    workers: int
    category: str


@dataclass(frozen=True)
class ScenarioAddressability:
    addressable_relation_count: int
    addressable_worker_mass: int
    other_core_addressable_relation_count: int
    other_core_addressable_worker_mass: int
    other_external_addressable_relation_count: int
    other_external_addressable_worker_mass: int


def directed_edges(anchor_ids: tuple[str, ...]) -> set[tuple[str, str]]:
    """Successive public anchors only. Repeated anchors are valid."""
    if not anchor_ids:
        raise ValueError("route has no public anchors")
    if any(not anchor for anchor in anchor_ids):
        raise ValueError("route has blank public anchor")
    return set(zip(anchor_ids, anchor_ids[1:]))


def reachable_from(starts: set[str], edges: set[tuple[str, str]]) -> set[str]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for left, right in edges:
        adjacency[left].add(right)
    seen = set(starts)
    queue = deque(sorted(starts))
    while queue:
        node = queue.popleft()
        for nxt in sorted(adjacency.get(node, ())):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def evaluate_scenario(
    *,
    public_route_anchor_sequences: list[tuple[str, ...]],
    anchor_municipalities: dict[str, frozenset[str]],
    relations: tuple[ODRelation, ...],
) -> ScenarioAddressability:
    """Evaluate directed municipal OD reachability over the union public graph.

    Inter-route transfer is permitted only through the same routing anchor.  No
    technical-return sequence is accepted by this interface.
    """
    edges: set[tuple[str, str]] = set()
    scenario_anchors: set[str] = set()
    for sequence in public_route_anchor_sequences:
        edges.update(directed_edges(sequence))
        scenario_anchors.update(sequence)
    unknown = scenario_anchors - set(anchor_municipalities)
    if unknown:
        raise ValueError(f"route references unknown routing anchors: {sorted(unknown)[:5]}")

    by_municipality: dict[str, set[str]] = defaultdict(set)
    for anchor in scenario_anchors:
        for municipality in anchor_municipalities[anchor]:
            by_municipality[municipality].add(anchor)

    reachability: dict[str, set[str]] = {}
    for relation in relations:
        if relation.origin_key not in reachability:
            reachability[relation.origin_key] = reachable_from(
                by_municipality.get(relation.origin_key, set()), edges
            )

    relation_count = worker_mass = 0
    core_count = core_mass = 0
    external_count = external_mass = 0
    for relation in relations:
        reachable = reachability[relation.origin_key]
        destination_anchors = by_municipality.get(relation.destination_key, set())
        if not (reachable & destination_anchors):
            continue
        relation_count += 1
        worker_mass += relation.workers
        if relation.category == "OTHER_CORE":
            core_count += 1
            core_mass += relation.workers
        elif relation.category == "OTHER_EXTERNAL":
            external_count += 1
            external_mass += relation.workers
        else:  # fail closed if caller violates the contract
            raise ValueError(f"unexpected evaluated OD category {relation.category}")

    return ScenarioAddressability(
        addressable_relation_count=relation_count,
        addressable_worker_mass=worker_mass,
        other_core_addressable_relation_count=core_count,
        other_core_addressable_worker_mass=core_mass,
        other_external_addressable_relation_count=external_count,
        other_external_addressable_worker_mass=external_mass,
    )
