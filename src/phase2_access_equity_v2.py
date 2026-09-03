"""Source-closed accessibility and municipal-equity helpers for Phase 2 V2.

This module evaluates only whether validated building-section population units
fall inside stop catchments for the explicit stops of a structural scenario.
It does not infer passenger demand, rank topology families, choose service
policies or declare a recommendation.

The 12-minute candidate-stop layer is intentionally treated as a conservative
lower bound when only the certified 10-minute proposed-stop membership table is
available. Existing-stop memberships can still contribute through 12 minutes.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping


EXACT_THRESHOLDS_MIN = (5, 8, 10)
LOWER_BOUND_THRESHOLD_MIN = 12


@dataclass(frozen=True)
class CoverageSummary:
    covered_population: float
    coverage_share: float
    municipality_covered_population: dict[str, float]
    municipality_coverage_share: dict[str, float]
    worst_municipality: str
    worst_municipality_coverage_share: float

    def __post_init__(self) -> None:
        values = (
            self.covered_population,
            self.coverage_share,
            self.worst_municipality_coverage_share,
            *self.municipality_covered_population.values(),
            *self.municipality_coverage_share.values(),
        )
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("CoverageSummary requires finite numeric values")
        if self.covered_population < 0:
            raise ValueError("covered_population must be non-negative")
        if not 0.0 <= self.coverage_share <= 1.0 + 1e-12:
            raise ValueError("coverage_share must lie in [0,1]")
        if not 0.0 <= self.worst_municipality_coverage_share <= 1.0 + 1e-12:
            raise ValueError("worst municipality share must lie in [0,1]")


def union_catchment_units(
    anchor_ids: Iterable[str],
    *,
    by_anchor: Mapping[str, frozenset[str]],
) -> frozenset[str]:
    """Union catchment units once, even when several stops cover the same unit."""
    units: set[str] = set()
    for anchor_id in set(anchor_ids):
        units.update(by_anchor.get(anchor_id, frozenset()))
    return frozenset(units)


def summarise_coverage(
    anchor_ids: Iterable[str],
    *,
    by_anchor: Mapping[str, frozenset[str]],
    unit_weights: Mapping[str, float],
    unit_municipality: Mapping[str, str],
    municipality_totals: Mapping[str, float],
) -> CoverageSummary:
    """Summarise one stop-set catchment without double-counting population."""
    if not municipality_totals:
        raise ValueError("municipality_totals cannot be empty")
    for municipality, total in municipality_totals.items():
        if not municipality or not math.isfinite(float(total)) or float(total) <= 0:
            raise ValueError("municipality totals must be finite and positive")

    units = union_catchment_units(anchor_ids, by_anchor=by_anchor)
    by_municipality = {municipality: 0.0 for municipality in municipality_totals}
    covered_population = 0.0
    for unit_id in sorted(units):
        if unit_id not in unit_weights:
            raise ValueError(f"Missing weight for population unit {unit_id!r}")
        if unit_id not in unit_municipality:
            raise ValueError(f"Missing municipality for population unit {unit_id!r}")
        municipality = unit_municipality[unit_id]
        if municipality not in municipality_totals:
            raise ValueError(f"Unknown municipality {municipality!r} for unit {unit_id!r}")
        weight = float(unit_weights[unit_id])
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"Invalid population weight for {unit_id!r}")
        covered_population += weight
        by_municipality[municipality] += weight

    total_population = sum(float(value) for value in municipality_totals.values())
    municipal_shares = {
        municipality: by_municipality[municipality] / float(municipality_totals[municipality])
        for municipality in municipality_totals
    }
    worst_municipality, worst_share = min(
        municipal_shares.items(),
        key=lambda item: (item[1], item[0]),
    )
    return CoverageSummary(
        covered_population=covered_population,
        coverage_share=covered_population / total_population,
        municipality_covered_population=by_municipality,
        municipality_coverage_share=municipal_shares,
        worst_municipality=worst_municipality,
        worst_municipality_coverage_share=worst_share,
    )


def merge_anchor_sets(public_anchors: Iterable[str], extension_anchors: Iterable[str]) -> frozenset[str]:
    """Return the explicit stop set when optional extensions are actually operated."""
    return frozenset(set(public_anchors) | set(extension_anchors))


def summarise_walk_coverage_thresholds(
    anchor_ids: Iterable[str],
    *,
    walk_by_anchor: Mapping[str, Mapping[str, float]],
    unit_weights: Mapping[str, float],
    unit_municipality: Mapping[str, str],
    municipality_totals: Mapping[str, float],
    thresholds: tuple[int, ...] = (5, 8, 10, 12),
) -> dict[int, CoverageSummary]:
    """Summarise nested thresholds in one pass over each stop-set's min walks.

    `walk_by_anchor` may itself be truncated for some anchor classes. Therefore
    a threshold is exact only to the extent certified by the caller's input
    layer. Phase 2 V2 uses this with proposed stops through 10 minutes and
    existing stops through 12 minutes, making the 12-minute result a
    conservative lower bound.
    """
    if tuple(sorted(thresholds)) != thresholds or not thresholds:
        raise ValueError("thresholds must be a non-empty increasing tuple")
    min_walk: dict[str, float] = {}
    for anchor_id in sorted(set(anchor_ids)):
        for unit_id, walk_min in walk_by_anchor.get(anchor_id, {}).items():
            if not math.isfinite(float(walk_min)) or float(walk_min) < 0:
                raise ValueError(f"Invalid walk time for {anchor_id!r}/{unit_id!r}")
            previous = min_walk.get(unit_id)
            if previous is None or float(walk_min) < previous:
                min_walk[unit_id] = float(walk_min)

    by_threshold_pop = {threshold: 0.0 for threshold in thresholds}
    by_threshold_municipality = {
        threshold: {municipality: 0.0 for municipality in municipality_totals}
        for threshold in thresholds
    }
    for unit_id, walk_min in min_walk.items():
        if unit_id not in unit_weights or unit_id not in unit_municipality:
            raise ValueError(f"Unknown population unit {unit_id!r} in walk catchment")
        municipality = unit_municipality[unit_id]
        if municipality not in municipality_totals:
            raise ValueError(f"Unknown municipality {municipality!r}")
        weight = float(unit_weights[unit_id])
        for threshold in thresholds:
            if walk_min <= threshold + 1e-9:
                by_threshold_pop[threshold] += weight
                by_threshold_municipality[threshold][municipality] += weight

    total_population = sum(float(value) for value in municipality_totals.values())
    result: dict[int, CoverageSummary] = {}
    for threshold in thresholds:
        municipal_pop = by_threshold_municipality[threshold]
        municipal_share = {
            municipality: municipal_pop[municipality] / float(municipality_totals[municipality])
            for municipality in municipality_totals
        }
        worst_municipality, worst_share = min(
            municipal_share.items(),
            key=lambda item: (item[1], item[0]),
        )
        result[threshold] = CoverageSummary(
            covered_population=by_threshold_pop[threshold],
            coverage_share=by_threshold_pop[threshold] / total_population,
            municipality_covered_population=municipal_pop,
            municipality_coverage_share=municipal_share,
            worst_municipality=worst_municipality,
            worst_municipality_coverage_share=worst_share,
        )
    return result
