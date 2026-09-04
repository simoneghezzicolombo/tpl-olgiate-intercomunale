"""Exact Stage-D clockface/timetable reference primitives.

This module is intentionally exhaustive over the certified integer-minute phase
space. The only inner-loop acceleration localises the best transfer target using
the proven unimodality of the current transfer-quality profiles; a fail-closed
fallback keeps arbitrary future profiles exact as well.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from decimal import Decimal
import heapq
import math
from statistics import mean
from typing import Iterable, Sequence

from src.phase2_s8_interchange import TransferQualityProfile, transfer_quality_from_slack

D = Decimal
DIRECTIONS = ("LECCO", "MILANO")


@dataclass(frozen=True)
class ExactRoute:
    route_id: str
    public_runtime_min: Decimal
    cycle_runtime_min: Decimal
    cycle_distance_km: Decimal
    public_returns_to_hub: bool

    def validate(self) -> None:
        if not self.route_id:
            raise ValueError("route_id is required")
        if self.public_runtime_min <= 0 or self.cycle_runtime_min <= 0 or self.cycle_distance_km <= 0:
            raise ValueError("route runtime/distance must be positive")
        if self.public_runtime_min > self.cycle_runtime_min:
            raise ValueError("public runtime exceeds vehicle-cycle runtime")
        if self.public_returns_to_hub and self.public_runtime_min != self.cycle_runtime_min:
            raise ValueError("public-return route must close public and vehicle cycles together")


@dataclass(frozen=True)
class ExactTrip:
    route_id: str
    phase_min: int
    departure_min: Decimal
    public_service_end_min: Decimal
    vehicle_return_hub_min: Decimal


@dataclass(frozen=True)
class ExactBlockedTrip:
    vehicle_index: int
    trip: ExactTrip
    ready_min: Decimal


@dataclass(frozen=True)
class TransferProfile:
    profile_id: str
    transfer_walk_min: float
    preferred_wait_min: float
    miss_transition_scale_min: float
    wait_decay_min: float

    def as_model_profile(self) -> TransferQualityProfile:
        profile = TransferQualityProfile(
            transfer_walk_min=self.transfer_walk_min,
            preferred_wait_min=self.preferred_wait_min,
            miss_transition_scale_min=self.miss_transition_scale_min,
            wait_decay_min=self.wait_decay_min,
        )
        profile.validate()
        return profile


@dataclass(frozen=True)
class ExactRailEvent:
    trip_id: str
    direction: str
    arrival_min: Decimal
    departure_min: Decimal

    def validate(self) -> None:
        if not self.trip_id or self.direction not in DIRECTIONS:
            raise ValueError("invalid rail event identity")
        if self.arrival_min < 0 or self.departure_min < self.arrival_min:
            raise ValueError("invalid rail event time")


@dataclass(frozen=True)
class RoutePhaseEvidence:
    route_id: str
    phase_min: int
    departure_count: int
    exact_daily_bus_km: Decimal
    cell_mean_quality: tuple[float, ...]
    cell_hard_miss_share: tuple[float, ...]
    cell_labels: tuple[str, ...]

    @property
    def robust_min_quality(self) -> float:
        return min(self.cell_mean_quality)

    @property
    def unweighted_mean_quality(self) -> float:
        return mean(self.cell_mean_quality)


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
    route: ExactRoute,
    *,
    phase_min: int,
    headway_min: int,
    span_start_min: int,
    span_end_min: int,
) -> tuple[ExactTrip, ...]:
    route.validate()
    return tuple(
        ExactTrip(
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


def minimum_common_hub_blocks(trips: Iterable[ExactTrip], *, recovery_min: int) -> tuple[int, tuple[ExactBlockedTrip, ...]]:
    """Exact interval colouring for fixed common-hub closed cycles."""
    if recovery_min < 0:
        raise ValueError("recovery must be non-negative")
    rows = sorted(trips, key=lambda t: (t.departure_min, t.route_id, t.phase_min))
    available: list[tuple[Decimal, int]] = []
    next_vehicle = 0
    blocked: list[ExactBlockedTrip] = []
    for trip in rows:
        if available and available[0][0] <= trip.departure_min:
            _, vehicle = heapq.heappop(available)
        else:
            vehicle = next_vehicle
            next_vehicle += 1
        ready = trip.vehicle_return_hub_min + D(recovery_min)
        heapq.heappush(available, (ready, vehicle))
        blocked.append(ExactBlockedTrip(vehicle, trip, ready))
    return next_vehicle, tuple(blocked)


def _best_quality_and_slack_exhaustive(slacks: Sequence[float], profile: TransferQualityProfile) -> tuple[float, float]:
    if not slacks:
        raise ValueError("connection has no target events")
    scored = [(transfer_quality_from_slack(slack, profile), slack) for slack in slacks]
    return max(scored, key=lambda item: (item[0], -abs(item[1])))


def _quality_peak_is_preferred_wait(profile: TransferQualityProfile) -> bool:
    """Prove the current quality curve peaks at preferred_wait_min.

    For negative slack and for 0..preferred_wait both multiplicative factors are
    strictly increasing. For slack above preferred_wait, d(log q)/ds equals
    (1-logistic(s/scale))/scale - 1/decay and decreases with s. It is therefore
    enough to verify that this derivative is non-positive immediately to the
    right of preferred_wait.
    """
    profile.validate()
    p = profile.preferred_wait_min
    scale = profile.miss_transition_scale_min
    decay = profile.wait_decay_min
    logistic = 1.0 / (1.0 + math.exp(-p / scale))
    right_derivative = (1.0 - logistic) / scale - 1.0 / decay
    return right_derivative <= 1e-15


def _best_target_quality_and_slack(
    source_min: Decimal,
    target_times_min: Sequence[Decimal],
    profile: TransferQualityProfile,
) -> tuple[float, float]:
    if not target_times_min:
        raise ValueError("connection has no target events")
    targets = tuple(sorted(float(x) for x in target_times_min))
    if not _quality_peak_is_preferred_wait(profile):
        slacks = [target - float(source_min) - profile.transfer_walk_min for target in targets]
        return _best_quality_and_slack_exhaustive(slacks, profile)

    ideal_target = float(source_min) + profile.transfer_walk_min + profile.preferred_wait_min
    idx = bisect_left(targets, ideal_target)
    candidate_indexes = {max(0, min(len(targets) - 1, idx - 1)), max(0, min(len(targets) - 1, idx))}
    candidates = []
    for i in sorted(candidate_indexes):
        slack = targets[i] - float(source_min) - profile.transfer_walk_min
        candidates.append((transfer_quality_from_slack(slack, profile), slack))
    return max(candidates, key=lambda item: (item[0], -abs(item[1])))


def source_centric_cell(
    *,
    source_times_min: Sequence[Decimal],
    target_times_min: Sequence[Decimal],
    connection_type: str,
    profile: TransferQualityProfile,
) -> tuple[float, float]:
    """Mean continuous quality and hard-miss share, one best target per source."""
    if connection_type not in {"BUS_TO_RAIL", "RAIL_TO_BUS"}:
        raise ValueError(f"unsupported connection type {connection_type}")
    if not source_times_min or not target_times_min:
        raise ValueError("source-centric transfer cell must contain source and target events")
    qualities: list[float] = []
    misses = 0
    for source in source_times_min:
        quality, slack = _best_target_quality_and_slack(source, target_times_min, profile)
        qualities.append(quality)
        misses += slack < 0
    return mean(qualities), misses / len(qualities)


def route_phase_evidence(
    route: ExactRoute,
    *,
    phase_min: int,
    headway_min: int,
    span_start_min: int,
    span_end_min: int,
    rail_events: Sequence[ExactRailEvent],
    profiles: Sequence[TransferProfile],
) -> RoutePhaseEvidence:
    route.validate()
    for event in rail_events:
        event.validate()
    if not profiles:
        raise ValueError("at least one transfer profile is required")
    trips = materialise_route_trips(
        route,
        phase_min=phase_min,
        headway_min=headway_min,
        span_start_min=span_start_min,
        span_end_min=span_end_min,
    )
    departures = tuple(t.departure_min for t in trips)
    public_returns = tuple(
        t.public_service_end_min
        for t in trips
        if route.public_returns_to_hub and D(span_start_min) <= t.public_service_end_min < D(span_end_min)
    )
    labels: list[str] = []
    qualities: list[float] = []
    misses: list[float] = []
    for raw_profile in profiles:
        profile = raw_profile.as_model_profile()
        for direction in DIRECTIONS:
            direction_events = [e for e in rail_events if e.direction == direction]
            rail_arrivals = tuple(
                e.arrival_min for e in direction_events if D(span_start_min) <= e.arrival_min < D(span_end_min)
            )
            rail_departures = tuple(e.departure_min for e in direction_events)
            if not rail_arrivals or not rail_departures:
                raise ValueError(f"no rail events for {direction} in exact timetable span")

            r2b_q, r2b_miss = source_centric_cell(
                source_times_min=rail_arrivals,
                target_times_min=departures,
                connection_type="RAIL_TO_BUS",
                profile=profile,
            )
            labels.append(f"{raw_profile.profile_id}|RAIL_TO_BUS|{direction}")
            qualities.append(r2b_q)
            misses.append(r2b_miss)

            if route.public_returns_to_hub:
                if not public_returns:
                    raise ValueError(f"closed route {route.route_id} has no public return events in span")
                b2r_q, b2r_miss = source_centric_cell(
                    source_times_min=public_returns,
                    target_times_min=rail_departures,
                    connection_type="BUS_TO_RAIL",
                    profile=profile,
                )
                labels.append(f"{raw_profile.profile_id}|BUS_TO_RAIL|{direction}")
                qualities.append(b2r_q)
                misses.append(b2r_miss)

    if not qualities or any(not math.isfinite(x) for x in qualities):
        raise ValueError("route phase produced invalid transfer quality")
    return RoutePhaseEvidence(
        route_id=route.route_id,
        phase_min=phase_min,
        departure_count=len(trips),
        exact_daily_bus_km=route.cycle_distance_km * len(trips),
        cell_mean_quality=tuple(qualities),
        cell_hard_miss_share=tuple(misses),
        cell_labels=tuple(labels),
    )


def phase_vector_objective(rows: Sequence[RoutePhaseEvidence]) -> tuple[float, float]:
    """Current normative robust phase objective, extended route-unweighted."""
    if not rows:
        raise ValueError("phase vector is empty")
    values = [value for row in rows for value in row.cell_mean_quality]
    if not values:
        raise ValueError("phase vector has no S8 quality cells")
    return min(values), mean(values)


def aggregate_hard_miss(rows: Sequence[RoutePhaseEvidence]) -> tuple[float, float]:
    values = [value for row in rows for value in row.cell_hard_miss_share]
    if not values:
        raise ValueError("phase vector has no hard-miss cells")
    return max(values), mean(values)
