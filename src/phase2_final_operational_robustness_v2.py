"""Pure helpers for Phase 2 Stage E Final Operational Robustness V2.

The module preserves nominal connection identity under perturbation. A missed
planned connection never becomes a success merely because a later train or bus
is reachable. Later alternatives are reported separately.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import heapq
import math
import statistics
from typing import Iterable, Mapping, Sequence

DIRECTIONS = ("LECCO", "MILANO")
CONNECTION_TYPES = ("BUS_TO_RAIL", "RAIL_TO_BUS")
EPS = 1e-9


@dataclass(frozen=True)
class TransferProfile:
    profile_id: str
    transfer_walk_min: float
    preferred_wait_min: float
    miss_transition_scale_min: float
    wait_decay_min: float

    def validate(self) -> None:
        values = (
            self.transfer_walk_min,
            self.preferred_wait_min,
            self.miss_transition_scale_min,
            self.wait_decay_min,
        )
        if not all(math.isfinite(v) for v in values):
            raise ValueError("transfer profile values must be finite")
        if self.transfer_walk_min < 0 or self.preferred_wait_min < 0:
            raise ValueError("transfer walk/preferred wait must be non-negative")
        if self.miss_transition_scale_min <= 0 or self.wait_decay_min <= 0:
            raise ValueError("transfer scales must be positive")


@dataclass(frozen=True)
class RailEvent:
    trip_id: str
    direction: str
    arrival_min: float
    departure_min: float

    def validate(self) -> None:
        if not self.trip_id:
            raise ValueError("rail trip_id is required")
        if self.direction not in DIRECTIONS:
            raise ValueError(f"unsupported rail direction {self.direction!r}")
        if not all(math.isfinite(v) for v in (self.arrival_min, self.departure_min)):
            raise ValueError("rail event minutes must be finite")
        if self.departure_min + EPS < self.arrival_min:
            raise ValueError("rail departure cannot precede arrival")


@dataclass(frozen=True)
class ExactTrip:
    stage_d_input_id: str
    scenario_id: str
    route_id: str
    trip_ordinal: int
    hub_departure_min: float
    public_hub_return_min: float | None
    vehicle_hub_return_min: float
    block_by_recovery: Mapping[int, int]

    def validate(self) -> None:
        if not self.stage_d_input_id or not self.route_id:
            raise ValueError("exact trip identity is incomplete")
        if self.trip_ordinal < 0:
            raise ValueError("trip ordinal must be non-negative")
        if not math.isfinite(self.hub_departure_min) or not math.isfinite(self.vehicle_hub_return_min):
            raise ValueError("exact trip times must be finite")
        if self.vehicle_hub_return_min + EPS < self.hub_departure_min:
            raise ValueError("vehicle return cannot precede departure")
        if self.public_hub_return_min is not None:
            if not math.isfinite(self.public_hub_return_min):
                raise ValueError("public return must be finite when present")
            if self.public_hub_return_min + EPS < self.hub_departure_min:
                raise ValueError("public return cannot precede departure")
        if any(r < 0 or int(v) < 0 for r, v in self.block_by_recovery.items()):
            raise ValueError("recovery/block identifiers must be non-negative")

    @property
    def passenger_returns_to_hub(self) -> bool:
        return self.public_hub_return_min is not None


@dataclass(frozen=True)
class RailDepartureIndex:
    events_by_direction: Mapping[str, tuple[RailEvent, ...]]
    times_by_direction: Mapping[str, tuple[float, ...]]


@dataclass(frozen=True)
class BusDepartureIndex:
    trips_by_route: Mapping[str, tuple[ExactTrip, ...]]
    times_by_route: Mapping[str, tuple[float, ...]]


@dataclass(frozen=True)
class ConnectionCandidate:
    connection_id: str
    stage_d_input_id: str
    scenario_id: str
    route_id: str
    connection_type: str
    direction: str
    profile_id: str
    transfer_walk_min: float
    source_event_id: str
    source_time_min: float
    planned_target_event_id: str | None
    planned_target_time_min: float | None
    nominal_slack_min: float | None

    def validate(self) -> None:
        if self.connection_type not in CONNECTION_TYPES:
            raise ValueError(f"invalid connection type {self.connection_type!r}")
        if self.direction not in DIRECTIONS:
            raise ValueError(f"invalid direction {self.direction!r}")
        if self.transfer_walk_min < 0 or not math.isfinite(self.transfer_walk_min):
            raise ValueError("transfer walk must be finite and non-negative")
        if not math.isfinite(self.source_time_min):
            raise ValueError("source time must be finite")
        target_present = self.planned_target_event_id is not None
        if target_present != (self.planned_target_time_min is not None):
            raise ValueError("planned target identity/time must be jointly present or absent")
        if target_present != (self.nominal_slack_min is not None):
            raise ValueError("nominal slack presence must follow planned target")
        if self.nominal_slack_min is not None and self.nominal_slack_min < -EPS:
            raise ValueError("planned connections must be nominally reachable after transfer walk")

    @property
    def planned_connection_exists(self) -> bool:
        return self.planned_target_event_id is not None


@dataclass(frozen=True)
class ConnectionEvaluation:
    connection_id: str
    perturbation_dimension: str
    perturbation_min: float
    planned_connection_exists: bool
    planned_connection_retained: bool | None
    perturbed_ready_min: float
    next_alternative_event_id: str | None
    next_alternative_time_min: float | None
    next_alternative_wait_min: float | None
    additional_wait_vs_planned_target_min: float | None


def strict_bool(value: object) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"expected explicit true/false, got {value!r}")


def finite_float(value: object, *, field: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if not math.isfinite(out):
        raise ValueError(f"non-finite {field}: {out}")
    return out


def optional_float(value: object, *, field: str) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    return finite_float(text, field=field)


def _first_at_or_after(times: Sequence[float], ready_min: float) -> int | None:
    index = bisect_left(times, ready_min - EPS)
    return None if index >= len(times) else index


def build_rail_departure_index(events: Sequence[RailEvent]) -> RailDepartureIndex:
    by_direction: dict[str, tuple[RailEvent, ...]] = {}
    times: dict[str, tuple[float, ...]] = {}
    for direction in DIRECTIONS:
        rows = [event for event in events if event.direction == direction]
        rows.sort(key=lambda e: (e.departure_min, e.trip_id))
        if not rows:
            raise ValueError(f"no rail events for {direction}")
        for event in rows:
            event.validate()
        by_direction[direction] = tuple(rows)
        times[direction] = tuple(e.departure_min for e in rows)
    return RailDepartureIndex(by_direction, times)


def build_bus_departure_index(trips: Sequence[ExactTrip]) -> BusDepartureIndex:
    grouped: dict[str, list[ExactTrip]] = {}
    for trip in trips:
        trip.validate()
        grouped.setdefault(trip.route_id, []).append(trip)
    trips_by_route: dict[str, tuple[ExactTrip, ...]] = {}
    times_by_route: dict[str, tuple[float, ...]] = {}
    for route_id in sorted(grouped):
        rows = sorted(grouped[route_id], key=lambda t: (t.hub_departure_min, t.trip_ordinal))
        trips_by_route[route_id] = tuple(rows)
        times_by_route[route_id] = tuple(t.hub_departure_min for t in rows)
    return BusDepartureIndex(trips_by_route, times_by_route)


def plan_bus_to_rail_connections(
    trips: Sequence[ExactTrip],
    rail_events: Sequence[RailEvent],
    profiles: Sequence[TransferProfile],
) -> list[ConnectionCandidate]:
    """Plan nominal BUS_TO_RAIL connections for passenger-returning trips only."""
    rail_index = build_rail_departure_index(rail_events)
    output: list[ConnectionCandidate] = []
    for trip in sorted(trips, key=lambda t: (t.route_id, t.trip_ordinal)):
        trip.validate()
        if not trip.passenger_returns_to_hub:
            continue
        assert trip.public_hub_return_min is not None
        for profile in profiles:
            profile.validate()
            for direction in DIRECTIONS:
                events = rail_index.events_by_direction[direction]
                times = rail_index.times_by_direction[direction]
                ready = trip.public_hub_return_min + profile.transfer_walk_min
                index = _first_at_or_after(times, ready)
                target = None if index is None else events[index]
                target_time = None if target is None else target.departure_min
                slack = None if target_time is None else target_time - ready
                candidate = ConnectionCandidate(
                    connection_id=(
                        f"B2R|{trip.stage_d_input_id}|{trip.route_id}|{trip.trip_ordinal}|"
                        f"{profile.profile_id}|{direction}"
                    ),
                    stage_d_input_id=trip.stage_d_input_id,
                    scenario_id=trip.scenario_id,
                    route_id=trip.route_id,
                    connection_type="BUS_TO_RAIL",
                    direction=direction,
                    profile_id=profile.profile_id,
                    transfer_walk_min=profile.transfer_walk_min,
                    source_event_id=f"{trip.route_id}:{trip.trip_ordinal}",
                    source_time_min=trip.public_hub_return_min,
                    planned_target_event_id=None if target is None else target.trip_id,
                    planned_target_time_min=target_time,
                    nominal_slack_min=slack,
                )
                candidate.validate()
                output.append(candidate)
    return output


def plan_rail_to_bus_connections(
    trips: Sequence[ExactTrip],
    rail_events: Sequence[RailEvent],
    profiles: Sequence[TransferProfile],
    *,
    span_start_min: float,
    span_end_min: float,
) -> list[ConnectionCandidate]:
    """Plan nominal RAIL_TO_BUS connections route-by-route from frozen S8 arrivals."""
    bus_index = build_bus_departure_index(trips)
    output: list[ConnectionCandidate] = []
    source_events = sorted(
        (e for e in rail_events if span_start_min <= e.arrival_min < span_end_min),
        key=lambda e: (e.arrival_min, e.direction, e.trip_id),
    )
    for route_id in sorted(bus_index.trips_by_route):
        route_trips = bus_index.trips_by_route[route_id]
        departures = bus_index.times_by_route[route_id]
        for event in source_events:
            event.validate()
            for profile in profiles:
                profile.validate()
                ready = event.arrival_min + profile.transfer_walk_min
                index = _first_at_or_after(departures, ready)
                target = None if index is None else route_trips[index]
                target_time = None if target is None else target.hub_departure_min
                slack = None if target_time is None else target_time - ready
                candidate = ConnectionCandidate(
                    connection_id=(
                        f"R2B|{route_trips[0].stage_d_input_id}|{route_id}|{event.trip_id}|"
                        f"{profile.profile_id}"
                    ),
                    stage_d_input_id=route_trips[0].stage_d_input_id,
                    scenario_id=route_trips[0].scenario_id,
                    route_id=route_id,
                    connection_type="RAIL_TO_BUS",
                    direction=event.direction,
                    profile_id=profile.profile_id,
                    transfer_walk_min=profile.transfer_walk_min,
                    source_event_id=event.trip_id,
                    source_time_min=event.arrival_min,
                    planned_target_event_id=(
                        None if target is None else f"{target.route_id}:{target.trip_ordinal}"
                    ),
                    planned_target_time_min=target_time,
                    nominal_slack_min=slack,
                )
                candidate.validate()
                output.append(candidate)
    return output


def evaluate_bus_to_rail_connection(
    candidate: ConnectionCandidate,
    *,
    bus_runtime_delay_min: float,
    rail_index: RailDepartureIndex,
) -> ConnectionEvaluation:
    if candidate.connection_type != "BUS_TO_RAIL":
        raise ValueError("BUS_TO_RAIL candidate required")
    delay = finite_float(bus_runtime_delay_min, field="bus_runtime_delay_min")
    if delay < 0:
        raise ValueError("negative runtime delay is not authorised by this engine contract")
    rows = rail_index.events_by_direction[candidate.direction]
    times = rail_index.times_by_direction[candidate.direction]
    ready = candidate.source_time_min + delay + candidate.transfer_walk_min
    if not candidate.planned_connection_exists:
        return ConnectionEvaluation(
            candidate.connection_id, "BUS_RUNTIME_DELAY", delay, False, None, ready,
            None, None, None, None,
        )
    assert candidate.planned_target_time_min is not None
    retained = ready <= candidate.planned_target_time_min + EPS
    if retained:
        return ConnectionEvaluation(
            candidate.connection_id, "BUS_RUNTIME_DELAY", delay, True, True, ready,
            None, None, None, None,
        )
    index = _first_at_or_after(times, ready)
    alt = None if index is None else rows[index]
    alt_time = None if alt is None else alt.departure_min
    alt_wait = None if alt_time is None else alt_time - ready
    extra = None if alt_time is None else alt_time - candidate.planned_target_time_min
    return ConnectionEvaluation(
        candidate.connection_id, "BUS_RUNTIME_DELAY", delay, True, False, ready,
        None if alt is None else alt.trip_id, alt_time, alt_wait, extra,
    )


def evaluate_rail_to_bus_connection(
    candidate: ConnectionCandidate,
    *,
    rail_arrival_delay_min: float,
    bus_index: BusDepartureIndex,
) -> ConnectionEvaluation:
    if candidate.connection_type != "RAIL_TO_BUS":
        raise ValueError("RAIL_TO_BUS candidate required")
    delay = finite_float(rail_arrival_delay_min, field="rail_arrival_delay_min")
    if delay < 0:
        raise ValueError("negative rail delay is not authorised by this engine contract")
    rows = bus_index.trips_by_route[candidate.route_id]
    times = bus_index.times_by_route[candidate.route_id]
    ready = candidate.source_time_min + delay + candidate.transfer_walk_min
    if not candidate.planned_connection_exists:
        return ConnectionEvaluation(
            candidate.connection_id, "RAIL_ARRIVAL_DELAY", delay, False, None, ready,
            None, None, None, None,
        )
    assert candidate.planned_target_time_min is not None
    retained = ready <= candidate.planned_target_time_min + EPS
    if retained:
        return ConnectionEvaluation(
            candidate.connection_id, "RAIL_ARRIVAL_DELAY", delay, True, True, ready,
            None, None, None, None,
        )
    index = _first_at_or_after(times, ready)
    alt = None if index is None else rows[index]
    alt_time = None if alt is None else alt.hub_departure_min
    alt_wait = None if alt_time is None else alt_time - ready
    extra = None if alt_time is None else alt_time - candidate.planned_target_time_min
    return ConnectionEvaluation(
        candidate.connection_id, "RAIL_ARRIVAL_DELAY", delay, True, False, ready,
        None if alt is None else f"{alt.route_id}:{alt.trip_ordinal}", alt_time, alt_wait, extra,
    )


def maximum_gap(values: Iterable[float]) -> float | None:
    ordered = sorted(float(v) for v in values)
    if len(ordered) < 2:
        return None
    return max(b - a for a, b in zip(ordered, ordered[1:]))


def mean_or_none(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    return None if not clean else math.fsum(clean) / len(clean)


def median_or_none(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    return None if not clean else float(statistics.median(clean))


def minimum_vehicle_requirement(
    trips: Sequence[ExactTrip],
    *,
    recovery_min: int,
    runtime_stress_min: float,
) -> int:
    if recovery_min < 0:
        raise ValueError("recovery must be non-negative")
    stress = finite_float(runtime_stress_min, field="runtime_stress_min")
    if stress < 0:
        raise ValueError("runtime stress must be non-negative")
    tasks = sorted(
        (
            trip.hub_departure_min,
            trip.vehicle_hub_return_min + recovery_min + stress,
            trip.route_id,
            trip.trip_ordinal,
        )
        for trip in trips
    )
    available: list[tuple[float, int]] = []
    next_vehicle = 0
    for departure, ready, _route_id, _ordinal in tasks:
        if available and available[0][0] <= departure + EPS:
            _, vehicle = heapq.heappop(available)
        else:
            vehicle = next_vehicle
            next_vehicle += 1
        heapq.heappush(available, (ready, vehicle))
    return next_vehicle


def audit_nominal_block_assignment(
    trips: Sequence[ExactTrip],
    *,
    recovery_min: int,
    runtime_stress_min: float,
) -> dict[str, float | int | bool | None]:
    if recovery_min < 0:
        raise ValueError("recovery must be non-negative")
    stress = finite_float(runtime_stress_min, field="runtime_stress_min")
    by_block: dict[int, list[ExactTrip]] = {}
    for trip in trips:
        trip.validate()
        if recovery_min not in trip.block_by_recovery:
            raise ValueError(f"trip lacks nominal block for recovery {recovery_min}")
        by_block.setdefault(int(trip.block_by_recovery[recovery_min]), []).append(trip)
    slacks: list[float] = []
    raw_turnarounds: list[float] = []
    conflicts = 0
    for block_id in sorted(by_block):
        ordered = sorted(by_block[block_id], key=lambda t: (t.hub_departure_min, t.route_id, t.trip_ordinal))
        for previous, nxt in zip(ordered, ordered[1:]):
            raw = nxt.hub_departure_min - (previous.vehicle_hub_return_min + stress)
            slack = raw - recovery_min
            raw_turnarounds.append(raw)
            slacks.append(slack)
            conflicts += int(slack < -EPS)
    nominal_fleet = len(by_block)
    minimum_fleet = minimum_vehicle_requirement(
        trips, recovery_min=recovery_min, runtime_stress_min=stress
    )
    return {
        "nominal_stage_d_fleet": nominal_fleet,
        "minimum_vehicle_requirement": minimum_fleet,
        "maximum_simultaneous_vehicle_requirement": minimum_fleet,
        "minimum_additional_vehicle_requirement": max(0, minimum_fleet - nominal_fleet),
        "vehicle_conflict_count_on_nominal_blocks": conflicts,
        "turnaround_violation_count": conflicts,
        "nominal_block_assignment_infeasible_under_case": conflicts > 0,
        "minimum_hub_turnaround_min": None if not raw_turnarounds else min(raw_turnarounds),
        "minimum_block_slack_min": None if not slacks else min(slacks),
        "median_block_slack_min": None if not slacks else float(statistics.median(slacks)),
        "maximum_block_slack_min": None if not slacks else max(slacks),
    }
