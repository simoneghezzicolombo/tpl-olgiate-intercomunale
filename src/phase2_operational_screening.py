"""Assumption-free operational lower-bound helpers for Phase 2.

The functions in this module do not choose headways, calendars, recovery,
fleet or service policy. They only turn a structural public route into the
minimum closed vehicle cycle implied by the validated directed path matrix:

- a route already ending where it starts needs no added closure;
- an open route needs the validated shortest matrix leg from its endpoint back
  to its start;
- if that return leg does not exist, the route is not cyclically closable under
  the current frozen graph and remains ineligible for service-policy search.

These are lower bounds, not timetables or operating plans.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from src.phase2_optimizer_core import ReducedPathMatrix


UNCERTAINTY_STATES = ("RESOLVED", "QUANTIFIED", "UNKNOWN")


@dataclass(frozen=True)
class RouteOperationalLowerBound:
    route_start: str
    route_end: str
    public_distance_km: float
    public_runtime_min: float
    public_leg_count: int
    is_structurally_closed: bool
    return_closable: bool
    return_distance_km: float | None
    return_runtime_min: float | None
    return_uncertainty: str | None
    operational_cycle_distance_km: float | None
    operational_cycle_runtime_min: float | None
    operational_resolved_distance_km: float | None
    operational_quantified_distance_km: float | None
    operational_unknown_distance_km: float | None

    @property
    def closure_added(self) -> bool:
        return not self.is_structurally_closed and self.return_closable


def route_operational_lower_bound(
    matrix: ReducedPathMatrix,
    anchors: Sequence[str],
) -> RouteOperationalLowerBound:
    if len(anchors) < 2:
        raise ValueError("Operational screening route requires at least two anchors")
    if any(not anchor for anchor in anchors):
        raise ValueError("Operational screening route contains an empty anchor")

    public_distance = 0.0
    public_runtime = 0.0
    uncertainty_distance = {state: 0.0 for state in UNCERTAINTY_STATES}
    for origin, destination in zip(anchors[:-1], anchors[1:]):
        leg = matrix.require_leg(origin, destination)
        public_distance += leg.distance_km
        public_runtime += leg.runtime_min
        uncertainty_distance[leg.uncertainty] += leg.distance_km

    start = anchors[0]
    end = anchors[-1]
    closed = start == end
    if closed:
        return RouteOperationalLowerBound(
            route_start=start,
            route_end=end,
            public_distance_km=public_distance,
            public_runtime_min=public_runtime,
            public_leg_count=len(anchors) - 1,
            is_structurally_closed=True,
            return_closable=True,
            return_distance_km=0.0,
            return_runtime_min=0.0,
            return_uncertainty=None,
            operational_cycle_distance_km=public_distance,
            operational_cycle_runtime_min=public_runtime,
            operational_resolved_distance_km=uncertainty_distance["RESOLVED"],
            operational_quantified_distance_km=uncertainty_distance["QUANTIFIED"],
            operational_unknown_distance_km=uncertainty_distance["UNKNOWN"],
        )

    if not matrix.has_leg(end, start):
        return RouteOperationalLowerBound(
            route_start=start,
            route_end=end,
            public_distance_km=public_distance,
            public_runtime_min=public_runtime,
            public_leg_count=len(anchors) - 1,
            is_structurally_closed=False,
            return_closable=False,
            return_distance_km=None,
            return_runtime_min=None,
            return_uncertainty=None,
            operational_cycle_distance_km=None,
            operational_cycle_runtime_min=None,
            operational_resolved_distance_km=None,
            operational_quantified_distance_km=None,
            operational_unknown_distance_km=None,
        )

    return_leg = matrix.require_leg(end, start)
    uncertainty_distance[return_leg.uncertainty] += return_leg.distance_km
    return RouteOperationalLowerBound(
        route_start=start,
        route_end=end,
        public_distance_km=public_distance,
        public_runtime_min=public_runtime,
        public_leg_count=len(anchors) - 1,
        is_structurally_closed=False,
        return_closable=True,
        return_distance_km=return_leg.distance_km,
        return_runtime_min=return_leg.runtime_min,
        return_uncertainty=return_leg.uncertainty,
        operational_cycle_distance_km=public_distance + return_leg.distance_km,
        operational_cycle_runtime_min=public_runtime + return_leg.runtime_min,
        operational_resolved_distance_km=uncertainty_distance["RESOLVED"],
        operational_quantified_distance_km=uncertainty_distance["QUANTIFIED"],
        operational_unknown_distance_km=uncertainty_distance["UNKNOWN"],
    )


def aggregate_route_lower_bounds(
    rows: Sequence[RouteOperationalLowerBound],
) -> dict[str, float | int | bool | None]:
    if not rows:
        raise ValueError("Cannot aggregate zero route lower bounds")
    all_closable = all(row.return_closable for row in rows)
    result: dict[str, float | int | bool | None] = {
        "route_count": len(rows),
        "open_route_count": sum(not row.is_structurally_closed for row in rows),
        "closure_added_route_count": sum(row.closure_added for row in rows),
        "all_return_closable": all_closable,
        "public_distance_km": sum(row.public_distance_km for row in rows),
        "public_runtime_min": sum(row.public_runtime_min for row in rows),
        "return_closure_distance_km": None,
        "return_closure_runtime_min": None,
        "equal_pattern_set_cycle_distance_km_lower_bound": None,
        "equal_pattern_set_cycle_runtime_min_lower_bound": None,
        "max_single_route_cycle_runtime_min_lower_bound": None,
        "operational_resolved_distance_km_lower_bound": None,
        "operational_quantified_distance_km_lower_bound": None,
        "operational_unknown_distance_km_lower_bound": None,
        "operational_unknown_distance_share_lower_bound": None,
    }
    if not all_closable:
        return result

    return_distance = sum(float(row.return_distance_km or 0.0) for row in rows)
    return_runtime = sum(float(row.return_runtime_min or 0.0) for row in rows)
    cycle_distance = sum(float(row.operational_cycle_distance_km) for row in rows)
    cycle_runtime = sum(float(row.operational_cycle_runtime_min) for row in rows)
    max_cycle_runtime = max(float(row.operational_cycle_runtime_min) for row in rows)
    resolved = sum(float(row.operational_resolved_distance_km) for row in rows)
    quantified = sum(float(row.operational_quantified_distance_km) for row in rows)
    unknown = sum(float(row.operational_unknown_distance_km) for row in rows)
    if not math.isclose(resolved + quantified + unknown, cycle_distance, rel_tol=0.0, abs_tol=1e-8):
        raise AssertionError("Operational uncertainty distances do not conserve cycle distance")
    result.update({
        "return_closure_distance_km": return_distance,
        "return_closure_runtime_min": return_runtime,
        "equal_pattern_set_cycle_distance_km_lower_bound": cycle_distance,
        "equal_pattern_set_cycle_runtime_min_lower_bound": cycle_runtime,
        "max_single_route_cycle_runtime_min_lower_bound": max_cycle_runtime,
        "operational_resolved_distance_km_lower_bound": resolved,
        "operational_quantified_distance_km_lower_bound": quantified,
        "operational_unknown_distance_km_lower_bound": unknown,
        "operational_unknown_distance_share_lower_bound": unknown / cycle_distance if cycle_distance else 0.0,
    })
    return result


def maximum_equal_pattern_sets_per_year(
    annual_bus_km_cap: float,
    equal_pattern_set_cycle_distance_km: float,
) -> int:
    """Resource-capacity upper bound, not a service frequency or calendar.

    One equal pattern set means one minimum closed cycle of every public route in
    the scenario. The function intentionally knows nothing about service days,
    headways, recovery or fleet.
    """
    if not math.isfinite(annual_bus_km_cap) or annual_bus_km_cap <= 0:
        raise ValueError("annual_bus_km_cap must be finite and positive")
    if not math.isfinite(equal_pattern_set_cycle_distance_km) or equal_pattern_set_cycle_distance_km <= 0:
        raise ValueError("equal pattern-set distance must be finite and positive")
    return int(math.floor(annual_bus_km_cap / equal_pattern_set_cycle_distance_km))
