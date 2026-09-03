"""Plan-level Phase 2 tournament helpers.

The V2 tournament deliberately avoids a weighted composite score.  A service
plan is a topology plus a declared headway/span/calendar/extension-share
policy. Recovery minutes remain a robustness sensitivity, not a different
passenger-facing plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable

CONTRACT = "PHASE2_SERVICE_PLAN_TOURNAMENT_V2"
STATUS = "PASS_SERVICE_PLAN_TOURNAMENT_V2_BUILD"


@dataclass(frozen=True)
class ServicePlanKey:
    scenario_id: str
    uniform_headway_min: int
    span_id: str
    calendar_id: str
    extension_share: float

    @property
    def plan_id(self) -> str:
        payload = {
            "scenario_id": self.scenario_id,
            "uniform_headway_min": self.uniform_headway_min,
            "span_id": self.span_id,
            "calendar_id": self.calendar_id,
            "extension_share": round(self.extension_share, 8),
        }
        token = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "P2PLAN_" + sha256(token.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class TournamentPoint:
    resident_coverage_share_10min: float
    worst_municipality_coverage_share_10min: float
    territorial_worker_od_mass_upper_bound: float
    s8_complete_match_route_share: float
    uniform_headway_min: int
    span_minutes: int
    annual_service_days: int
    annual_bus_km: float
    fleet_lower_bound_recovery15: int

    def validate(self) -> None:
        for value in (
            self.resident_coverage_share_10min,
            self.worst_municipality_coverage_share_10min,
            self.s8_complete_match_route_share,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("Share outside [0,1]")
        if self.territorial_worker_od_mass_upper_bound < 0:
            raise ValueError("Negative territorial OD mass")
        if self.uniform_headway_min <= 0 or self.span_minutes <= 0 or self.annual_service_days <= 0:
            raise ValueError("Invalid service intensity")
        if self.annual_bus_km <= 0 or self.fleet_lower_bound_recovery15 <= 0:
            raise ValueError("Invalid operating resource value")


def dominates(a: TournamentPoint, b: TournamentPoint) -> bool:
    """Return True when a weakly dominates b and improves at least one axis.

    Maximised axes: resident access, worst-municipality access, territorial OD
    addressability, S8 complete-match share, span and service days.
    Minimised axes: headway, annual bus-km and recovery-15 fleet lower bound.
    """
    a.validate()
    b.validate()
    max_a = (
        a.resident_coverage_share_10min,
        a.worst_municipality_coverage_share_10min,
        a.territorial_worker_od_mass_upper_bound,
        a.s8_complete_match_route_share,
        a.span_minutes,
        a.annual_service_days,
    )
    max_b = (
        b.resident_coverage_share_10min,
        b.worst_municipality_coverage_share_10min,
        b.territorial_worker_od_mass_upper_bound,
        b.s8_complete_match_route_share,
        b.span_minutes,
        b.annual_service_days,
    )
    min_a = (a.uniform_headway_min, a.annual_bus_km, a.fleet_lower_bound_recovery15)
    min_b = (b.uniform_headway_min, b.annual_bus_km, b.fleet_lower_bound_recovery15)
    weak = all(x >= y for x, y in zip(max_a, max_b)) and all(x <= y for x, y in zip(min_a, min_b))
    strict = any(x > y for x, y in zip(max_a, max_b)) or any(x < y for x, y in zip(min_a, min_b))
    return weak and strict


def nondominated_indices(points: Iterable[TournamentPoint]) -> tuple[int, ...]:
    """Exact Pareto classification for a deliberately pre-shortlisted set."""
    rows = tuple(points)
    keep: list[int] = []
    for i, point in enumerate(rows):
        if not any(j != i and dominates(other, point) for j, other in enumerate(rows)):
            keep.append(i)
    return tuple(keep)


def structural_s8_signature(point: TournamentPoint) -> tuple[float, float, float, float]:
    """Four maximised axes used for within-policy pre-shortlisting."""
    point.validate()
    return (
        point.resident_coverage_share_10min,
        point.worst_municipality_coverage_share_10min,
        point.territorial_worker_od_mass_upper_bound,
        point.s8_complete_match_route_share,
    )


def nondominated_max_signatures(rows: Iterable[tuple[float, ...]]) -> frozenset[tuple[float, ...]]:
    """Efficient-enough exact max-only Pareto filter for unique metric signatures."""
    unique = tuple(sorted(set(rows), reverse=True))
    frontier: list[tuple[float, ...]] = []
    for point in unique:
        dominated = False
        for other in unique:
            if other == point:
                continue
            if all(x >= y for x, y in zip(other, point)) and any(x > y for x, y in zip(other, point)):
                dominated = True
                break
        if not dominated:
            frontier.append(point)
    return frozenset(frontier)
