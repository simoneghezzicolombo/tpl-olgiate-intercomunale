"""Scenario-level, route-unweighted S8 feeder-envelope helpers.

This module deliberately does not create a scenario passenger score. Route-level
S8 transfer envelopes are aggregated only as counts, shares and ranges, split by
passenger-support semantics. The 1,882 ISTAT workers remain direction weights
inside each route transfer envelope and are never allocated to bus routes.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


SCENARIO_FEEDER_CONTRACT = "PHASE2_S8_SCENARIO_FEEDER_ENVELOPE_V2"
SCENARIO_FEEDER_STATUS = "PASS_S8_SCENARIO_FEEDER_ENVELOPE_V2_BUILD"


@dataclass(frozen=True, slots=True)
class RouteTimingGap:
    route_id: str
    roundtrip_passenger_supported: bool
    complete_match_phase_count: int
    best_complete_phase_weighted_mean_gap_min: float | None
    worst_complete_phase_weighted_mean_gap_min: float | None

    def validate(self) -> None:
        if not self.route_id:
            raise ValueError("Route timing gap requires a route_id")
        if self.complete_match_phase_count < 0:
            raise ValueError("complete_match_phase_count must be non-negative")
        if self.complete_match_phase_count == 0:
            if self.best_complete_phase_weighted_mean_gap_min is not None or self.worst_complete_phase_weighted_mean_gap_min is not None:
                raise ValueError("No-complete-match route cannot carry finite complete-match gaps")
            return
        if self.best_complete_phase_weighted_mean_gap_min is None or self.worst_complete_phase_weighted_mean_gap_min is None:
            raise ValueError("Complete-match route requires both best and worst gap")
        best = float(self.best_complete_phase_weighted_mean_gap_min)
        worst = float(self.worst_complete_phase_weighted_mean_gap_min)
        if not math.isfinite(best) or not math.isfinite(worst) or best < 0 or worst < 0:
            raise ValueError("Complete-match gaps must be finite and non-negative")
        if best > worst + 1e-9:
            raise ValueError("Best complete-match gap cannot exceed worst complete-match gap")


def _range(values: Sequence[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return min(values), max(values)


def _class_summary(rows: Sequence[RouteTimingGap], *, expected_roundtrip: bool) -> dict[str, object]:
    selected = [row for row in rows if row.roundtrip_passenger_supported is expected_roundtrip]
    for row in selected:
        row.validate()
    count = len(selected)
    complete = [row for row in selected if row.complete_match_phase_count > 0]
    complete_count = len(complete)
    best_values = [float(row.best_complete_phase_weighted_mean_gap_min) for row in complete]
    worst_values = [float(row.worst_complete_phase_weighted_mean_gap_min) for row in complete]
    best_min, best_max = _range(best_values)
    worst_min, worst_max = _range(worst_values)
    return {
        "route_count": count,
        "complete_match_route_count": complete_count,
        "no_complete_match_route_count": count - complete_count,
        "complete_match_route_share": (complete_count / count) if count else None,
        "all_routes_have_complete_match_phase": (complete_count == count) if count else None,
        "any_route_has_complete_match_phase": (complete_count > 0) if count else None,
        "best_complete_gap_min_min": best_min,
        "best_complete_gap_min_max": best_max,
        "worst_complete_gap_min_min": worst_min,
        "worst_complete_gap_min_max": worst_max,
    }


def summarise_role(route_ids: Sequence[str], gap_by_route: Mapping[str, RouteTimingGap]) -> dict[str, object]:
    """Summarise one scenario role without creating a route-weighted utility.

    The output keeps round-trip passenger service separate from routes that only
    support RAIL_TO_BUS from the Olgiate hub. Ranges are route-unweighted extrema,
    never means. No cross-route clock phase is selected or asserted feasible.
    """
    ids = tuple(str(route_id) for route_id in route_ids)
    if len(ids) != len(set(ids)):
        raise ValueError("Scenario role contains duplicate route IDs")
    rows: list[RouteTimingGap] = []
    for route_id in ids:
        try:
            row = gap_by_route[route_id]
        except KeyError as exc:
            raise ValueError(f"Scenario references missing route timing gap: {route_id}") from exc
        row.validate()
        rows.append(row)

    roundtrip = _class_summary(rows, expected_roundtrip=True)
    rail_to_bus_only = _class_summary(rows, expected_roundtrip=False)
    if int(roundtrip["route_count"]) + int(rail_to_bus_only["route_count"]) != len(rows):
        raise AssertionError("Passenger-support class partition is not exhaustive")
    total_complete = int(roundtrip["complete_match_route_count"]) + int(rail_to_bus_only["complete_match_route_count"])
    return {
        "route_count": len(rows),
        "complete_match_route_count": total_complete,
        "complete_match_route_share": (total_complete / len(rows)) if rows else None,
        "all_routes_have_some_complete_match_phase": (total_complete == len(rows)) if rows else None,
        "any_route_has_some_complete_match_phase": (total_complete > 0) if rows else None,
        "roundtrip": roundtrip,
        "rail_to_bus_only": rail_to_bus_only,
    }
