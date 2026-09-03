"""Municipal-OD structural addressability helpers for Phase 2.

The helpers answer only whether a directed public-service graph contains a
structural path between municipalities. They do not allocate municipal workers
to stops or routes and do not convert OD weights into observed bus ridership.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


CONTRACT = "PHASE2_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2"
STATUS = "PASS_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2_BUILD"


@dataclass(frozen=True, slots=True)
class WorkOD:
    origin_code: str
    origin_name: str
    destination_code: str
    destination_name: str
    workers: float
    category: str

    def validate(self) -> None:
        if not self.origin_code or not self.destination_code:
            raise ValueError("OD row requires origin and destination codes")
        if not self.origin_name or not self.destination_name:
            raise ValueError("OD row requires municipality names")
        if self.workers <= 0:
            raise ValueError("OD worker weight must be positive")
        if self.category not in {"SELF", "OTHER_CORE", "S8_DIRECT", "OTHER_EXTERNAL"}:
            raise ValueError(f"Unexpected OD category {self.category}")


@dataclass(frozen=True, slots=True)
class RouteGeometry:
    route_id: str
    anchors: tuple[str, ...]

    def validate(self) -> None:
        if not self.route_id:
            raise ValueError("Route requires route_id")
        if len(self.anchors) < 2:
            raise ValueError("Route requires at least two public anchors")
        if any(not anchor for anchor in self.anchors):
            raise ValueError("Route contains an empty anchor")


def directed_edges(routes: Iterable[RouteGeometry]) -> tuple[set[str], dict[str, set[str]]]:
    """Union public-service consecutive edges, preserving route direction."""
    nodes: set[str] = set()
    graph: dict[str, set[str]] = defaultdict(set)
    for route in routes:
        route.validate()
        nodes.update(route.anchors)
        for a, b in zip(route.anchors[:-1], route.anchors[1:]):
            if a == b:
                raise ValueError(f"Route {route.route_id} contains a zero-length anchor step")
            graph[a].add(b)
    return nodes, dict(graph)


def reachable_municipalities(
    routes: Iterable[RouteGeometry],
    anchor_municipalities: Mapping[str, frozenset[str]],
    origin_municipality: str,
) -> frozenset[str]:
    """Return municipalities reachable from any scenario anchor in the origin.

    Zero-edge reachability is intentionally retained for graph mechanics, but
    SELF OD rows are excluded by the caller because municipal OD cannot resolve
    within-municipality trip endpoints.
    """
    nodes, graph = directed_edges(routes)
    for node in nodes:
        if node not in anchor_municipalities:
            raise ValueError(f"Missing municipality lineage for anchor {node}")
    starts = {node for node in nodes if origin_municipality in anchor_municipalities[node]}
    if not starts:
        return frozenset()
    seen = set(starts)
    queue = deque(starts)
    while queue:
        node = queue.popleft()
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    result: set[str] = set()
    for node in seen:
        result.update(anchor_municipalities[node])
    return frozenset(result)


def summarise_addressability(
    ods: Sequence[WorkOD],
    routes: Sequence[RouteGeometry],
    anchor_municipalities: Mapping[str, frozenset[str]],
) -> dict[str, object]:
    """Summarise municipal OD structural opportunity without passenger assignment."""
    for od in ods:
        od.validate()
    by_origin: dict[str, frozenset[str]] = {}
    for origin in sorted({od.origin_name for od in ods if od.category != "SELF"}):
        by_origin[origin] = reachable_municipalities(routes, anchor_municipalities, origin)

    addressable = [
        od for od in ods
        if od.category != "SELF" and od.destination_name in by_origin.get(od.origin_name, frozenset())
    ]
    self_rows = [od for od in ods if od.category == "SELF"]
    categories = ("OTHER_CORE", "S8_DIRECT", "OTHER_EXTERNAL")
    result: dict[str, object] = {
        "intermunicipal_od_relation_count": sum(od.category != "SELF" for od in ods),
        "intermunicipal_worker_od_mass": sum(od.workers for od in ods if od.category != "SELF"),
        "structurally_addressable_od_relation_count": len(addressable),
        "structurally_addressable_worker_od_mass_upper_bound": sum(od.workers for od in addressable),
        "self_od_relation_count_unresolved": len(self_rows),
        "self_worker_od_mass_unresolved": sum(od.workers for od in self_rows),
    }
    inter_count = int(result["intermunicipal_od_relation_count"])
    inter_mass = float(result["intermunicipal_worker_od_mass"])
    result["structurally_addressable_od_relation_share"] = (len(addressable) / inter_count) if inter_count else None
    result["structurally_addressable_worker_od_mass_share"] = (
        float(result["structurally_addressable_worker_od_mass_upper_bound"]) / inter_mass if inter_mass else None
    )
    for category in categories:
        universe = [od for od in ods if od.category == category]
        hit = [od for od in addressable if od.category == category]
        result[f"{category.lower()}_relation_count"] = len(universe)
        result[f"{category.lower()}_worker_od_mass"] = sum(od.workers for od in universe)
        result[f"{category.lower()}_addressable_relation_count"] = len(hit)
        result[f"{category.lower()}_addressable_worker_od_mass_upper_bound"] = sum(od.workers for od in hit)
    return result
