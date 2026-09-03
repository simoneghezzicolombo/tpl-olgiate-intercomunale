"""Phase 2 topology-level pre-tournament Pareto helpers.

This module identifies non-dominated metric triplets without assigning a scalar
score or ranking scenarios. It is deliberately upstream of plan-level passenger
utility, S8 phase selection and the final candidate tournament.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

CONTRACT = "PHASE2_PRETOURNAMENT_STRUCTURAL_FRONTIER_V2"
STATUS = "PASS_PRETOURNAMENT_STRUCTURAL_FRONTIER_V2_BUILD"


@dataclass(frozen=True, order=True)
class MetricPoint:
    population_coverage_share_10min: Decimal
    worst_municipality_coverage_share_10min: Decimal
    territorial_worker_od_mass_upper_bound: Decimal

    @classmethod
    def from_values(cls, population: object, worst: object, territorial: object) -> "MetricPoint":
        point = cls(Decimal(str(population)), Decimal(str(worst)), Decimal(str(territorial)))
        if point.population_coverage_share_10min < 0 or point.population_coverage_share_10min > 1:
            raise ValueError("Population coverage share must be in [0, 1]")
        if point.worst_municipality_coverage_share_10min < 0 or point.worst_municipality_coverage_share_10min > 1:
            raise ValueError("Worst-municipality coverage share must be in [0, 1]")
        if point.territorial_worker_od_mass_upper_bound < 0:
            raise ValueError("Territorial worker OD mass must be non-negative")
        return point


def dominates(a: MetricPoint, b: MetricPoint) -> bool:
    """Return True when a weakly improves every dimension and strictly improves one."""
    weak = (
        a.population_coverage_share_10min >= b.population_coverage_share_10min
        and a.worst_municipality_coverage_share_10min >= b.worst_municipality_coverage_share_10min
        and a.territorial_worker_od_mass_upper_bound >= b.territorial_worker_od_mass_upper_bound
    )
    strict = a != b
    return weak and strict


class _FenwickMax:
    def __init__(self, size: int) -> None:
        self.values: list[Decimal | None] = [None] * (size + 1)

    def update(self, index: int, value: Decimal) -> None:
        while index < len(self.values):
            current = self.values[index]
            if current is None or value > current:
                self.values[index] = value
            index += index & -index

    def query(self, index: int) -> Decimal | None:
        best: Decimal | None = None
        while index > 0:
            current = self.values[index]
            if current is not None and (best is None or current > best):
                best = current
            index -= index & -index
        return best


def nondominated_metric_points(points: Iterable[MetricPoint]) -> frozenset[MetricPoint]:
    """Return unique non-dominated points for three maximisation objectives.

    Exact duplicate metric triplets are treated as equivalent, not as mutually
    dominating. Complexity is O(n log n) using a Fenwick prefix maximum over the
    second dimension after sorting the first dimension descending.
    """
    unique = set(points)
    if not unique:
        return frozenset()

    y_values = sorted(
        {p.worst_municipality_coverage_share_10min for p in unique},
        reverse=True,
    )
    y_rank = {value: index + 1 for index, value in enumerate(y_values)}
    tree = _FenwickMax(len(y_values))

    ordered = sorted(
        unique,
        key=lambda p: (
            p.population_coverage_share_10min,
            p.worst_municipality_coverage_share_10min,
            p.territorial_worker_od_mass_upper_bound,
        ),
        reverse=True,
    )

    frontier: set[MetricPoint] = set()
    for point in ordered:
        rank = y_rank[point.worst_municipality_coverage_share_10min]
        prior_max_z = tree.query(rank)
        if prior_max_z is None or prior_max_z < point.territorial_worker_od_mass_upper_bound:
            frontier.add(point)
        tree.update(rank, point.territorial_worker_od_mass_upper_bound)
    return frozenset(frontier)
