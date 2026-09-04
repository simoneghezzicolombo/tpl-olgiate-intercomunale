"""Contract-correct Stage-D S8 cell construction.

This adapter keeps the efficient exact phase engine but enforces the certified
START_INCLUSIVE_END_EXCLUSIVE hub-event span semantics for BUS_TO_RAIL public
returns. A trip may still return after the declared span for vehicle blocking,
but that out-of-span vehicle/public arrival is not scored as an in-span S8
passenger interchange event.
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence

from src.phase2_exact_timetable_optimizer_v2 import (
    DIRECTIONS,
    RouteInput,
    TransferProfile,
    best_continuous_quality_target,
    clockface_times,
)


def route_phase_cell_values_contract(
    route: RouteInput,
    *,
    phase: int,
    headway: int,
    span_start: int,
    span_end: int,
    rail_index: Mapping[str, Mapping[str, Sequence[float]]],
    profiles: Sequence[TransferProfile],
) -> tuple[float, ...]:
    route.validate()
    departures = clockface_times(phase, headway, span_start, span_end)
    if not departures:
        raise ValueError("explicit timetable generated no departures")

    public_returns = tuple(
        t + route.public_runtime_min
        for t in departures
        if span_start <= t + route.public_runtime_min < span_end
    )
    if route.bus_to_rail_passenger_event_supported and not public_returns:
        raise ValueError(f"closed route {route.route_id} has no in-span public return events")

    cells: list[float] = []
    for profile in profiles:
        for direction in DIRECTIONS:
            arrivals = tuple(
                t for t in rail_index[direction]["arrivals"]
                if span_start <= t < span_end
            )
            if not arrivals:
                raise ValueError(f"no in-span S8 arrivals for {direction}")
            r2b = []
            for rail_arrival in arrivals:
                matched = best_continuous_quality_target(departures, rail_arrival, profile)
                r2b.append(0.0 if matched is None else matched[1])
            cells.append(math.fsum(r2b) / len(r2b))

            if route.bus_to_rail_passenger_event_supported:
                rail_departures = rail_index[direction]["departures"]
                b2r = []
                for bus_arrival in public_returns:
                    matched = best_continuous_quality_target(rail_departures, bus_arrival, profile)
                    b2r.append(0.0 if matched is None else matched[1])
                cells.append(math.fsum(b2r) / len(b2r))
    return tuple(cells)


def precompute_route_phase_cells_contract(
    routes: Sequence[RouteInput],
    *,
    headway: int,
    span_start: int,
    span_end: int,
    rail_index: Mapping[str, Mapping[str, Sequence[float]]],
    profiles: Sequence[TransferProfile],
) -> tuple[tuple[tuple[float, ...], ...], ...]:
    return tuple(
        tuple(
            route_phase_cell_values_contract(
                route,
                phase=phase,
                headway=headway,
                span_start=span_start,
                span_end=span_end,
                rail_index=rail_index,
                profiles=profiles,
            )
            for phase in range(headway)
        )
        for route in routes
    )
