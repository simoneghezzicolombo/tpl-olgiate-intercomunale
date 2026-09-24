"""Raw S8 clock-phase opportunity helpers for Phase 2 V2.

No transfer-walk assumption, waiting utility, delay case, passenger weight or
phase selection is applied. Hub departures are public-service events. Hub
returns generated from a closed vehicle-cycle runtime are operational events,
not automatically passenger-service arrivals: downstream code must use the
route-level support flags materialised by the V2 builder before interpreting a
vehicle return as BUS_TO_RAIL passenger service.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json
import math
from statistics import median
from typing import Iterable, Sequence


D = Decimal


@dataclass(frozen=True)
class Span:
    span_id: str
    start_min: int
    end_min: int

    def validate(self) -> None:
        if not self.span_id or not 0 <= self.start_min < self.end_min <= 1440:
            raise ValueError(f"Invalid span {self}")


@dataclass(frozen=True)
class RailEvent:
    trip_id: str
    direction: str
    arrival_min: Decimal
    departure_min: Decimal

    def validate(self) -> None:
        if not self.trip_id:
            raise ValueError("RailEvent requires trip_id")
        if self.direction not in {"MILANO", "LECCO"}:
            raise ValueError(f"Unsupported rail direction {self.direction}")
        if self.arrival_min < 0 or self.departure_min < self.arrival_min:
            raise ValueError(f"Invalid rail event times {self}")


def stable_route_id(anchors: Sequence[str]) -> str:
    if len(anchors) < 2 or any(not a for a in anchors):
        raise ValueError("Route ID requires at least two non-empty anchors")
    payload = json.dumps(list(anchors), ensure_ascii=False, separators=(",", ":"))
    return f"R2_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def runtime_archetype_id(cycle_runtime_min: Decimal) -> str:
    if cycle_runtime_min <= 0:
        raise ValueError("Cycle runtime must be positive")
    text = format(cycle_runtime_min, "f")
    return f"RT2_{sha256(text.encode('utf-8')).hexdigest()[:20]}"


def clockface_times(*, phase_min: int, headway_min: int, span: Span) -> tuple[Decimal, ...]:
    """Integer-minute clockface public departures inside [start,end)."""
    span.validate()
    if headway_min <= 0 or 60 % headway_min != 0:
        raise ValueError("headway must be a positive divisor of 60")
    if not 0 <= phase_min < headway_min:
        raise ValueError("phase must be in [0, headway)")
    start = span.start_min
    first = start + ((phase_min - start) % headway_min)
    return tuple(D(t) for t in range(first, span.end_min, headway_min))


def steady_state_arrival_times(
    *,
    phase_min: int,
    headway_min: int,
    cycle_runtime_min: Decimal,
    span: Span,
) -> tuple[Decimal, ...]:
    """Vehicle-cycle hub-return events in [start,end), not passenger assertions."""
    span.validate()
    if cycle_runtime_min <= 0:
        raise ValueError("cycle runtime must be positive")
    if headway_min <= 0 or 60 % headway_min != 0:
        raise ValueError("headway must be a positive divisor of 60")
    if not 0 <= phase_min < headway_min:
        raise ValueError("phase must be in [0, headway)")
    base = D(phase_min) + cycle_runtime_min
    h = D(headway_min)
    start = D(span.start_min)
    end = D(span.end_min)
    k = ((start - base) / h).to_integral_value(rounding=ROUND_CEILING)
    t = base + k * h
    rows: list[Decimal] = []
    while t < end:
        if t >= start:
            rows.append(t)
        t += h
    return tuple(rows)


def _next_gap(event_time: Decimal, targets: Sequence[Decimal]) -> Decimal | None:
    idx = bisect_left(targets, event_time)
    if idx >= len(targets):
        return None
    return targets[idx] - event_time


def gap_distribution_to_next(
    source_times: Sequence[Decimal],
    target_times: Sequence[Decimal],
) -> tuple[Decimal | None, ...]:
    targets = tuple(sorted(target_times))
    return tuple(_next_gap(t, targets) for t in source_times)


def summarize_gaps(gaps: Iterable[Decimal | None]) -> dict[str, object]:
    rows = list(gaps)
    matched = sorted(float(v) for v in rows if v is not None)
    unmatched = len(rows) - len(matched)
    if not rows:
        return {
            "source_event_count": 0,
            "matched_count": 0,
            "unmatched_count": 0,
            "mean_gap_min": None,
            "median_gap_min": None,
            "p90_gap_min": None,
            "max_gap_min": None,
        }
    if not matched:
        return {
            "source_event_count": len(rows),
            "matched_count": 0,
            "unmatched_count": unmatched,
            "mean_gap_min": None,
            "median_gap_min": None,
            "p90_gap_min": None,
            "max_gap_min": None,
        }
    p90_index = max(0, math.ceil(0.90 * len(matched)) - 1)
    return {
        "source_event_count": len(rows),
        "matched_count": len(matched),
        "unmatched_count": unmatched,
        "mean_gap_min": sum(matched) / len(matched),
        "median_gap_min": median(matched),
        "p90_gap_min": matched[p90_index],
        "max_gap_min": matched[-1],
    }


def phase_raw_gap_metrics(
    *,
    rail_events: Sequence[RailEvent],
    cycle_runtime_min: Decimal,
    headway_min: int,
    span: Span,
    phase_min: int,
) -> dict[str, object]:
    """Return raw operational gaps without asserting passenger return service."""
    for event in rail_events:
        event.validate()
    departures = clockface_times(phase_min=phase_min, headway_min=headway_min, span=span)
    vehicle_returns = steady_state_arrival_times(
        phase_min=phase_min,
        headway_min=headway_min,
        cycle_runtime_min=cycle_runtime_min,
        span=span,
    )
    out: dict[str, object] = {
        "phase_min": phase_min,
        "bus_departure_count": len(departures),
        "vehicle_cycle_return_count": len(vehicle_returns),
    }
    for direction in ("MILANO", "LECCO"):
        direction_events = [e for e in rail_events if e.direction == direction]
        rail_departures = tuple(sorted(e.departure_min for e in direction_events))
        rail_arrivals_in_span = tuple(
            sorted(
                e.arrival_min
                for e in direction_events
                if D(span.start_min) <= e.arrival_min < D(span.end_min)
            )
        )
        cycle_to_rail = summarize_gaps(gap_distribution_to_next(vehicle_returns, rail_departures))
        rail_to_bus = summarize_gaps(gap_distribution_to_next(rail_arrivals_in_span, departures))
        for prefix, metrics in (("vehicle_cycle_to_rail", cycle_to_rail), ("rail_to_bus", rail_to_bus)):
            for key, value in metrics.items():
                out[f"{prefix}_{direction.lower()}_{key}"] = value
    return out
