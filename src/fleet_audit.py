"""Scheduled fleet concurrency audit for Gate E.

Computes theoretical in-service fleet from actual cycle-origin departures and
validated cycle durations. It does not include depot deadhead, driver reliefs,
maintenance or spare ratio.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from src.service_math import ServiceMathError, parse_gtfs_time_to_minutes


def minimum_fleet_from_intervals(intervals: Iterable[tuple[float, float]]) -> int:
    events: list[tuple[float, int]] = []
    count = 0
    for start, end in intervals:
        start = float(start); end = float(end)
        if end <= start:
            raise ServiceMathError(f"cycle interval end must be after start: {start}, {end}")
        # Half-open [start, end): an ending vehicle may operate a departure at the same instant.
        events.append((start, +1)); events.append((end, -1)); count += 1
    if count == 0:
        return 0
    events.sort(key=lambda item: (item[0], item[1]))  # end (-1) before start (+1)
    active = peak = 0
    for _, delta in events:
        active += delta
        if active < 0:
            raise ServiceMathError("invalid fleet event ordering")
        peak = max(peak, active)
    return peak


def cycle_intervals(departure_times: Sequence[str], cycle_minutes: float) -> list[tuple[float, float]]:
    if cycle_minutes <= 0:
        raise ServiceMathError("cycle_minutes must be > 0")
    starts = [parse_gtfs_time_to_minutes(value) for value in departure_times]
    return [(start, start + float(cycle_minutes)) for start in starts]


def scheduled_fleet_from_directional_cycles(
    cw_departures: Sequence[str],
    cw_cycle_minutes: float,
    ccw_departures: Sequence[str],
    ccw_cycle_minutes: float,
) -> dict[str, object]:
    cw_intervals = cycle_intervals(cw_departures, cw_cycle_minutes)
    ccw_intervals = cycle_intervals(ccw_departures, ccw_cycle_minutes)
    cw = minimum_fleet_from_intervals(cw_intervals)
    ccw = minimum_fleet_from_intervals(ccw_intervals)
    interlined = minimum_fleet_from_intervals(cw_intervals + ccw_intervals)
    return {
        "minimum_scheduled_vehicles_CW_direction_locked": cw,
        "minimum_scheduled_vehicles_CCW_direction_locked": ccw,
        "minimum_scheduled_vehicles_direction_locked_total": cw + ccw,
        "minimum_scheduled_vehicles_hub_interlining_allowed": interlined,
        "potential_interlining_saving_vs_direction_locked": cw + ccw - interlined,
        "fleet_scope": "THEORETICAL_IN_SERVICE_FROM_ACTUAL_DEPARTURES",
        "excluded_from_fleet_scope": "DEPOT_DEADHEAD;DRIVER_RELIEFS;MAINTENANCE;SPARES",
    }
