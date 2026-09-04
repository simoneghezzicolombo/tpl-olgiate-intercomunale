#!/usr/bin/env python3
"""Run exact GJT set-bounds builder with the certified V3 in-span contract.

Stage D persists physical public trips even when their eventual public return is
outside the declared service span because those movements remain relevant to
vehicle blocking. Passenger BUS_TO_RAIL evidence, however, is valid only when
the *next explicit public hub occurrence* lies in [span_start, span_end). This
adapter injects that already-certified Stage-D V3 rule into the fine-origin set
bounds without changing any other builder semantics.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import scripts.phase2_build_gjt_set_bounds_exact_v3 as target
from src.phase2_gjt_set_bounds_exact_v3 import (
    RailDeparture,
    SensitivityCase,
    bus_generalized_cost,
    first_feasible_rail_departure,
)

_SPANS: dict[str, tuple[int, int]] = {}


class SpanAwareRouteDepartures(dict):
    def __init__(self, *args, span_start: int, span_end: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.span_start = int(span_start)
        self.span_end = int(span_end)


_original_load_timetables = target.load_timetables
_original_load_trip_departures = target.load_trip_departures


def load_timetables_with_spans(path, expected_count):
    rows = _original_load_timetables(path, expected_count)
    _SPANS.clear()
    for row in rows:
        _SPANS[str(row["selected_timetable_id"])] = (
            int(row["span_start_min"]), int(row["span_end_min"])
        )
    return rows


def load_trip_departures_with_spans(path, wanted_timetables, expected_count):
    rows = _original_load_trip_departures(path, wanted_timetables, expected_count)
    if set(rows) != set(_SPANS):
        raise ValueError("Span metadata and exact-trip timetable identities differ")
    return {
        tid: SpanAwareRouteDepartures(
            by_route,
            span_start=_SPANS[tid][0],
            span_end=_SPANS[tid][1],
        )
        for tid, by_route in rows.items()
    }


def build_anchor_components_in_span(
    *,
    timetable_route_departures: Mapping[str, Sequence[float]],
    route_occurrences: Mapping[str, Sequence],
    rail_departures: Mapping[str, Sequence[RailDeparture]],
    case: SensitivityCase,
    direction: str,
):
    if not isinstance(timetable_route_departures, SpanAwareRouteDepartures):
        raise TypeError("Expected span-aware exact timetable route departures")
    span_start = timetable_route_departures.span_start
    span_end = timetable_route_departures.span_end
    best: dict[str, dict[str, object]] = {}
    for rid, departures in timetable_route_departures.items():
        for occ in route_occurrences.get(rid, ()):
            for trip_departure in departures:
                bus_hub_arrival = float(trip_departure) + occ.next_public_hub_cumulative_min
                if not (span_start <= bus_hub_arrival < span_end):
                    continue
                rail = first_feasible_rail_departure(
                    rail_departures[direction],
                    bus_hub_arrival_min=bus_hub_arrival,
                    station_transfer_walk_min=case.station_transfer_walk_min,
                )
                if rail is None:
                    continue
                component_cost, wait = bus_generalized_cost(
                    access_walk_min=0.0,
                    bus_ivt_min=occ.bus_ivt_to_hub_min,
                    bus_hub_arrival_min=bus_hub_arrival,
                    rail_departure_min=rail.departure_min,
                    case=case,
                )
                candidate = {
                    "base_cost": component_cost,
                    "route_id": rid,
                    "trip_departure_min": float(trip_departure),
                    "bus_hub_arrival_min": bus_hub_arrival,
                    "rail_event_id": rail.event_id,
                    "rail_departure_min": rail.departure_min,
                    "bus_ivt_min": occ.bus_ivt_to_hub_min,
                    "exact_transfer_wait_min": wait,
                }
                key = (
                    component_cost,
                    rid,
                    float(trip_departure),
                    rail.departure_min,
                    rail.event_id,
                )
                previous = best.get(occ.anchor_id)
                if previous is None or key < previous["key"]:
                    candidate["key"] = key
                    best[occ.anchor_id] = candidate
    return best


target.load_timetables = load_timetables_with_spans
target.load_trip_departures = load_trip_departures_with_spans
target.build_anchor_components = build_anchor_components_in_span


if __name__ == "__main__":
    raise SystemExit(target.main())
