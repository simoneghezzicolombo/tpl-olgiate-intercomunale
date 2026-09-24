"""Topology-neutral structural screening helpers for Phase 2.

The module evaluates only structural properties already present in a scenario
catalog and directed reduced path matrix. It does not rank topology families,
select stops, annualise service, choose headways, or infer passenger demand.

Population/accessibility data are deliberately abstracted as generic catchment
units so V1 cells and later V2 building-level origins can use the same union
machinery without changing the algorithm.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

from src.phase2_optimizer_core import ReducedPathMatrix


UNCERTAINTY_STATES = ("RESOLVED", "QUANTIFIED", "UNKNOWN")


@dataclass(frozen=True)
class AnchorMeta:
    anchor_id: str
    source_kind: str

    def __post_init__(self) -> None:
        if not self.anchor_id:
            raise ValueError("AnchorMeta requires a non-empty anchor_id")
        if not self.source_kind:
            raise ValueError("AnchorMeta requires a non-empty source_kind")


@dataclass(frozen=True)
class CatchmentRecord:
    """One anchor-to-analysis-unit membership with a reusable unit weight."""

    anchor_id: str
    unit_id: str
    weight: float

    def __post_init__(self) -> None:
        if not self.anchor_id or not self.unit_id:
            raise ValueError("CatchmentRecord requires non-empty IDs")
        if not math.isfinite(self.weight) or self.weight < 0:
            raise ValueError("CatchmentRecord weight must be finite and non-negative")


def _validate_tolerances(abs_tol_km: float, rel_tol: float) -> None:
    if not math.isfinite(abs_tol_km) or abs_tol_km < 0:
        raise ValueError("abs_tol_km must be finite and non-negative")
    if not math.isfinite(rel_tol) or rel_tol < 0:
        raise ValueError("rel_tol must be finite and non-negative")


def lies_on_directed_shortest_path(
    matrix: ReducedPathMatrix,
    *,
    origin: str,
    destination: str,
    candidate: str,
    abs_tol_km: float,
    rel_tol: float,
) -> bool:
    """Return whether candidate lies on the cached directed shortest path A→B.

    The test is purely metric:
        d(A,C) + d(C,B) == d(A,B)
    within caller-declared floating-point tolerances. No geographic-radius or
    topology preference is introduced.
    """
    _validate_tolerances(abs_tol_km, rel_tol)
    if candidate in {origin, destination}:
        return True
    if not matrix.has_leg(origin, candidate) or not matrix.has_leg(candidate, destination):
        return False
    direct = matrix.require_leg(origin, destination).distance_km
    via = (
        matrix.require_leg(origin, candidate).distance_km
        + matrix.require_leg(candidate, destination).distance_km
    )
    tolerance = max(abs_tol_km, rel_tol * direct)
    return abs(via - direct) <= tolerance


def intercepted_anchors_for_leg(
    matrix: ReducedPathMatrix,
    *,
    origin: str,
    destination: str,
    anchors: Iterable[str],
    abs_tol_km: float,
    rel_tol: float,
) -> frozenset[str]:
    """Find anchors lying on one directed shortest-path leg."""
    matrix.require_leg(origin, destination)
    return frozenset(
        anchor
        for anchor in anchors
        if lies_on_directed_shortest_path(
            matrix,
            origin=origin,
            destination=destination,
            candidate=anchor,
            abs_tol_km=abs_tol_km,
            rel_tol=rel_tol,
        )
    )


def route_legs(route: Sequence[str]) -> tuple[tuple[str, str], ...]:
    if len(route) < 2:
        raise ValueError("A structural route needs at least two anchors")
    if any(not anchor for anchor in route):
        raise ValueError("A structural route contains an empty anchor")
    if any(a == b for a, b in zip(route[:-1], route[1:])):
        raise ValueError("A structural route repeats an anchor consecutively")
    return tuple(zip(route[:-1], route[1:]))


def _pattern_metrics(
    matrix: ReducedPathMatrix,
    routes: Sequence[Sequence[str]],
) -> dict[str, float | int]:
    distance_km = 0.0
    runtime_min = 0.0
    counts = {state: 0 for state in UNCERTAINTY_STATES}
    distances = {state: 0.0 for state in UNCERTAINTY_STATES}
    leg_count = 0
    for route in routes:
        for origin, destination in route_legs(route):
            leg = matrix.require_leg(origin, destination)
            if leg.uncertainty not in counts:
                raise ValueError(f"Unsupported uncertainty state {leg.uncertainty!r}")
            distance_km += leg.distance_km
            runtime_min += leg.runtime_min
            counts[leg.uncertainty] += 1
            distances[leg.uncertainty] += leg.distance_km
            leg_count += 1
    return {
        "leg_count": leg_count,
        "distance_km": distance_km,
        "runtime_min": runtime_min,
        **{f"{state.lower()}_leg_count": counts[state] for state in UNCERTAINTY_STATES},
        **{f"{state.lower()}_distance_km": distances[state] for state in UNCERTAINTY_STATES},
    }


def _intercepted_for_routes(
    matrix: ReducedPathMatrix,
    routes: Sequence[Sequence[str]],
    *,
    anchor_ids: Sequence[str],
    abs_tol_km: float,
    rel_tol: float,
    leg_cache: dict[tuple[str, str], frozenset[str]] | None = None,
) -> frozenset[str]:
    cache = leg_cache if leg_cache is not None else {}
    intercepted: set[str] = set()
    for route in routes:
        for origin, destination in route_legs(route):
            key = (origin, destination)
            if key not in cache:
                cache[key] = intercepted_anchors_for_leg(
                    matrix,
                    origin=origin,
                    destination=destination,
                    anchors=anchor_ids,
                    abs_tol_km=abs_tol_km,
                    rel_tol=rel_tol,
                )
            intercepted.update(cache[key])
    return frozenset(intercepted)


def summarise_scenario_structure(
    matrix: ReducedPathMatrix,
    *,
    routes: Sequence[Sequence[str]],
    optional_extensions: Sequence[Sequence[str]],
    anchor_meta: Mapping[str, AnchorMeta],
    abs_tol_km: float,
    rel_tol: float,
    leg_cache: dict[tuple[str, str], frozenset[str]] | None = None,
) -> dict[str, float | int]:
    """Summarise route-skeleton geometry without operational assumptions."""
    _validate_tolerances(abs_tol_km, rel_tol)
    if not routes:
        raise ValueError("A scenario requires at least one public route")
    anchor_ids = tuple(sorted(anchor_meta))
    public_metrics = _pattern_metrics(matrix, routes)
    extension_metrics = _pattern_metrics(matrix, optional_extensions) if optional_extensions else {
        "leg_count": 0,
        "distance_km": 0.0,
        "runtime_min": 0.0,
        **{f"{state.lower()}_leg_count": 0 for state in UNCERTAINTY_STATES},
        **{f"{state.lower()}_distance_km": 0.0 for state in UNCERTAINTY_STATES},
    }
    public_intercepted = _intercepted_for_routes(
        matrix,
        routes,
        anchor_ids=anchor_ids,
        abs_tol_km=abs_tol_km,
        rel_tol=rel_tol,
        leg_cache=leg_cache,
    )
    extension_intercepted = _intercepted_for_routes(
        matrix,
        optional_extensions,
        anchor_ids=anchor_ids,
        abs_tol_km=abs_tol_km,
        rel_tol=rel_tol,
        leg_cache=leg_cache,
    ) if optional_extensions else frozenset()
    explicit_public = {anchor for route in routes for anchor in route}
    explicit_extensions = {anchor for route in optional_extensions for anchor in route}

    def kind_count(ids: Iterable[str], kind: str) -> int:
        return sum(1 for anchor in ids if anchor_meta[anchor].source_kind == kind)

    result: dict[str, float | int] = {
        "public_route_count": len(routes),
        "optional_extension_count": len(optional_extensions),
        "public_explicit_anchor_count": len(explicit_public),
        "extension_explicit_anchor_count": len(explicit_extensions),
        "public_intercepted_anchor_count": len(public_intercepted),
        "extension_intercepted_anchor_count": len(extension_intercepted),
        "public_intercepted_existing_stop_count": kind_count(public_intercepted, "EXISTING_PHYSICAL_STOP_CLUSTER"),
        "public_intercepted_proposed_stop_count": kind_count(public_intercepted, "PROPOSED_STOP"),
        "extension_intercepted_existing_stop_count": kind_count(extension_intercepted, "EXISTING_PHYSICAL_STOP_CLUSTER"),
        "extension_intercepted_proposed_stop_count": kind_count(extension_intercepted, "PROPOSED_STOP"),
    }
    for key, value in public_metrics.items():
        result[f"public_{key}"] = value
    for key, value in extension_metrics.items():
        result[f"extension_{key}"] = value
    return result


def build_catchment_index(
    records: Iterable[CatchmentRecord],
    *,
    weight_abs_tol: float = 1e-9,
) -> tuple[dict[str, frozenset[str]], dict[str, float]]:
    """Build an anchor→unit index while preserving one canonical unit weight.

    A unit can appear in many stop catchments, but its weight must be identical
    across those records. Conflicting weights fail closed to prevent silent
    double-counting or accidental joins across incompatible population layers.
    """
    if not math.isfinite(weight_abs_tol) or weight_abs_tol < 0:
        raise ValueError("weight_abs_tol must be finite and non-negative")
    by_anchor: dict[str, set[str]] = {}
    unit_weights: dict[str, float] = {}
    seen_any = False
    for record in records:
        seen_any = True
        by_anchor.setdefault(record.anchor_id, set()).add(record.unit_id)
        if record.unit_id in unit_weights:
            if not math.isclose(unit_weights[record.unit_id], record.weight, rel_tol=0.0, abs_tol=weight_abs_tol):
                raise ValueError(f"Conflicting weights for catchment unit {record.unit_id!r}")
        else:
            unit_weights[record.unit_id] = record.weight
    if not seen_any:
        raise ValueError("Catchment index cannot be built from zero records")
    return ({anchor: frozenset(units) for anchor, units in by_anchor.items()}, unit_weights)


def catchment_union(
    anchor_ids: Iterable[str],
    *,
    by_anchor: Mapping[str, frozenset[str]],
    unit_weights: Mapping[str, float],
) -> tuple[frozenset[str], float]:
    """Return unique analysis units and their once-only total weight."""
    units: set[str] = set()
    for anchor in set(anchor_ids):
        units.update(by_anchor.get(anchor, frozenset()))
    total = 0.0
    for unit in units:
        if unit not in unit_weights:
            raise ValueError(f"Missing weight for catchment unit {unit!r}")
        weight = unit_weights[unit]
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"Invalid weight for catchment unit {unit!r}")
        total += weight
    return frozenset(units), total
