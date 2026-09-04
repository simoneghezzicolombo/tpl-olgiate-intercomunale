"""Exact clockface timetable and common-hub vehicle-block helpers for Phase 2.

This module contains no topology or service-policy selection.  It only turns a
fixed plan plus route phases into explicit trips and verifies how many vehicles
are simultaneously required when every vehicle cycle returns to the common FS
hub.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import heapq
from bisect import bisect_left
from typing import Iterable, Sequence

D = Decimal


@dataclass(frozen=True)
class RouteCycle:
    route_id: str
    public_runtime_min: Decimal
    cycle_runtime_min: Decimal
    cycle_distance_km: Decimal
    public_returns_to_hub: bool

    def validate(self) -> None:
        if not self.route_id or self.public_runtime_min <= 0 or self.cycle_runtime_min <= 0 or self.cycle_distance_km <= 0:
            raise ValueError("Invalid route-cycle evidence")
        if self.public_runtime_min > self.cycle_runtime_min:
            raise ValueError("Public runtime cannot exceed closed vehicle-cycle runtime")
        if self.public_returns_to_hub and self.public_runtime_min != self.cycle_runtime_min:
            raise ValueError("A public-return route must close its passenger and vehicle cycles together")


@dataclass(frozen=True)
class Trip:
    route_id: str
    phase_min: int
    departure_min: Decimal
    public_service_end_min: Decimal
    vehicle_return_hub_min: Decimal

    def validate(self) -> None:
        if not self.route_id or self.phase_min < 0 or self.departure_min < 0:
            raise ValueError("Invalid trip identity/time")
        if self.public_service_end_min <= self.departure_min:
            raise ValueError("Public trip must end after departure")
        if self.vehicle_return_hub_min < self.public_service_end_min:
            raise ValueError("Vehicle return cannot precede public-service end")


@dataclass(frozen=True)
class BlockedTrip:
    vehicle_index: int
    trip: Trip
    ready_min: Decimal


@dataclass(frozen=True)
class CellGapSummary:
    source_count: int
    matched_count: int
    unmatched_count: int
    mean_gap_min: float | None


def clockface_departures(*, phase_min: int, headway_min: int, span_start_min: int, span_end_min: int) -> tuple[Decimal, ...]:
    if headway_min <= 0 or 60 % headway_min != 0:
        raise ValueError("headway must be a positive divisor of 60")
    if not 0 <= phase_min < headway_min:
        raise ValueError("phase outside headway domain")
    if not 0 <= span_start_min < span_end_min <= 1440:
        raise ValueError("invalid service span")
    first = span_start_min + ((phase_min - span_start_min) % headway_min)
    return tuple(D(value) for value in range(first, span_end_min, headway_min))


def materialise_route_trips(
    route: RouteCycle,
    *,
    phase_min: int,
    headway_min: int,
    span_start_min: int,
    span_end_min: int,
) -> tuple[Trip, ...]:
    route.validate()
    return tuple(
        Trip(
            route_id=route.route_id,
            phase_min=phase_min,
            departure_min=departure,
            public_service_end_min=departure + route.public_runtime_min,
            vehicle_return_hub_min=departure + route.cycle_runtime_min,
        )
        for departure in clockface_departures(
            phase_min=phase_min,
            headway_min=headway_min,
            span_start_min=span_start_min,
            span_end_min=span_end_min,
        )
    )


def minimum_common_hub_blocks(trips: Iterable[Trip], *, recovery_min: int) -> tuple[int, tuple[BlockedTrip, ...]]:
    """Greedy interval colouring, exact for common-hub closed vehicle cycles.

    A vehicle is occupied from public departure until cycle return plus the
    declared recovery.  Since every cycle ends at the same hub where every next
    trip starts, sorting by departure and reusing the earliest available vehicle
    yields the minimum fleet for the fixed timetable.
    """
    if recovery_min < 0:
        raise ValueError("recovery must be non-negative")
    rows = sorted(trips, key=lambda trip: (trip.departure_min, trip.route_id, trip.phase_min))
    for trip in rows:
        trip.validate()
    available: list[tuple[Decimal, int]] = []
    next_vehicle = 0
    blocked: list[BlockedTrip] = []
    for trip in rows:
        if available and available[0][0] <= trip.departure_min:
            _, vehicle = heapq.heappop(available)
        else:
            vehicle = next_vehicle
            next_vehicle += 1
        ready = trip.vehicle_return_hub_min + D(recovery_min)
        heapq.heappush(available, (ready, vehicle))
        blocked.append(BlockedTrip(vehicle, trip, ready))
    return next_vehicle, tuple(blocked)


def next_gap_with_minimum_margin(source_min: Decimal, targets_min: Sequence[Decimal], margin_min: int) -> Decimal | None:
    """Gap to first target at least `margin_min` after the source event."""
    if margin_min < 0:
        raise ValueError("minimum margin must be non-negative")
    targets = tuple(sorted(targets_min))
    idx = bisect_left(targets, source_min + D(margin_min))
    if idx >= len(targets):
        return None
    return targets[idx] - source_min


def summarise_margin_gaps(
    sources_min: Sequence[Decimal],
    targets_min: Sequence[Decimal],
    *,
    margin_min: int,
) -> CellGapSummary:
    gaps = [next_gap_with_minimum_margin(source, targets_min, margin_min) for source in sources_min]
    matched = [float(value) for value in gaps if value is not None]
    return CellGapSummary(
        source_count=len(gaps),
        matched_count=len(matched),
        unmatched_count=len(gaps) - len(matched),
        mean_gap_min=(sum(matched) / len(matched)) if matched else None,
    )
