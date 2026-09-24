"""Exact Stage-D timetable/S8 optimizer for Phase 2.

The solver exhaustively evaluates every integer route-specific phase vector.
It uses the frozen explicit S8 events, the declared continuous transfer-quality
profiles, exact first/last public bus trips in the declared span, and exact
vehicle-cycle runtimes. No stochastic search, pruning, passenger weighting or
hidden composite score is used.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import heapq
import itertools
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DIRECTIONS = ("LECCO", "MILANO")
RECOVERIES = (5, 10, 15)
RUNTIME_STRESS_MIN = (0, 5, 10, 15)


@dataclass(frozen=True)
class TransferProfile:
    profile_id: str
    transfer_walk_min: float
    preferred_wait_min: float
    miss_transition_scale_min: float
    wait_decay_min: float

    def validate(self) -> None:
        values = (self.transfer_walk_min, self.preferred_wait_min, self.miss_transition_scale_min, self.wait_decay_min)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("transfer profile values must be finite")
        if self.transfer_walk_min < 0 or self.preferred_wait_min < 0:
            raise ValueError("transfer walk/preferred wait must be non-negative")
        if self.miss_transition_scale_min <= 0 or self.wait_decay_min <= 0:
            raise ValueError("transfer scales must be positive")


@dataclass(frozen=True)
class RouteInput:
    route_id: str
    public_runtime_min: float
    cycle_runtime_min: float
    public_service_starts_at_hub: bool
    public_service_returns_to_hub: bool
    vehicle_closure_added: bool
    rail_to_bus_passenger_event_supported: bool
    bus_to_rail_passenger_event_supported: bool

    def validate(self) -> None:
        if not self.route_id:
            raise ValueError("route_id is required")
        if not math.isfinite(self.public_runtime_min) or self.public_runtime_min <= 0:
            raise ValueError(f"invalid public runtime for {self.route_id}")
        if not math.isfinite(self.cycle_runtime_min) or self.cycle_runtime_min <= 0:
            raise ValueError(f"invalid cycle runtime for {self.route_id}")
        if not self.public_service_starts_at_hub or not self.rail_to_bus_passenger_event_supported:
            raise ValueError(f"Stage D route must support rail-to-bus at hub: {self.route_id}")
        if self.bus_to_rail_passenger_event_supported != self.public_service_returns_to_hub:
            raise ValueError(f"passenger return semantics changed for {self.route_id}")
        if self.vehicle_closure_added == self.public_service_returns_to_hub:
            raise ValueError(f"vehicle closure/public return semantics inconsistent for {self.route_id}")


@dataclass(frozen=True)
class PhaseEvaluation:
    phase_vector: tuple[int, ...]
    robust_min_transfer_quality: float
    robust_unweighted_mean_transfer_quality: float
    cell_values: tuple[float, ...]

    @property
    def objective_key(self) -> tuple[float, ...]:
        return (
            self.robust_min_transfer_quality,
            self.robust_unweighted_mean_transfer_quality,
            *(-phase for phase in self.phase_vector),
        )


def strict_bool(value: object) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"expected explicit boolean, got {value!r}")


def transfer_quality_from_slack(slack_after_walk_min: float, profile: TransferProfile) -> float:
    profile.validate()
    if not math.isfinite(slack_after_walk_min):
        raise ValueError("transfer slack must be finite")
    x = max(-60.0, min(60.0, slack_after_walk_min / profile.miss_transition_scale_min))
    catch_factor = 1.0 / (1.0 + math.exp(-x))
    nonnegative_wait = max(0.0, slack_after_walk_min)
    timing_factor = math.exp(-abs(nonnegative_wait - profile.preferred_wait_min) / profile.wait_decay_min)
    return catch_factor * timing_factor


def clockface_times(phase: int, headway: int, start: int, end: int) -> tuple[float, ...]:
    if headway <= 0 or not 0 <= phase < headway or not 0 <= start < end <= 1440:
        raise ValueError("invalid phase/headway/span")
    first = start + ((phase - start) % headway)
    return tuple(float(t) for t in range(first, end, headway))


def load_profiles(path: Path) -> tuple[TransferProfile, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != "PHASE2_S8_PHASING_SENSITIVITY_V2":
        raise ValueError("unexpected S8 sensitivity contract")
    if payload.get("delay_robustness_in_this_stage") is not False:
        raise ValueError("upstream delay-robustness contract changed")
    objective = payload.get("phase_objective", {})
    if objective.get("passenger_weighting") is not False or objective.get("topology_weighting") is not False:
        raise ValueError("S8 phase objective unexpectedly weighted")
    profiles = tuple(
        TransferProfile(
            profile_id=str(row["profile_id"]),
            transfer_walk_min=float(row["transfer_walk_min"]),
            preferred_wait_min=float(row["preferred_wait_min"]),
            miss_transition_scale_min=float(row["miss_transition_scale_min"]),
            wait_decay_min=float(row["wait_decay_min"]),
        )
        for row in payload["transfer_profiles"]
    )
    if not profiles or len({p.profile_id for p in profiles}) != len(profiles):
        raise ValueError("invalid transfer profile set")
    for profile in profiles:
        profile.validate()
    return profiles


def rail_event_index(events: Sequence[Mapping[str, object]]) -> dict[str, dict[str, tuple[float, ...]]]:
    result: dict[str, dict[str, tuple[float, ...]]] = {}
    for direction in DIRECTIONS:
        subset = [row for row in events if str(row["direction"]).upper() == direction]
        if not subset:
            raise ValueError(f"no S8 events for {direction}")
        result[direction] = {
            "arrivals": tuple(sorted(float(row["arrival_min"]) for row in subset)),
            "departures": tuple(sorted(float(row["departure_min"]) for row in subset)),
        }
    return result


def _next(values: Sequence[float], at_or_after: float) -> float | None:
    index = bisect_left(values, at_or_after)
    return None if index >= len(values) else float(values[index])


def route_phase_cell_values(
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
    cells: list[float] = []
    for profile in profiles:
        for direction in DIRECTIONS:
            arrivals = [t for t in rail_index[direction]["arrivals"] if span_start <= t < span_end]
            if not arrivals:
                raise ValueError(f"no in-span S8 arrivals for {direction}")
            qualities = []
            for rail_arrival in arrivals:
                bus_departure = _next(departures, rail_arrival)
                if bus_departure is None:
                    qualities.append(0.0)
                else:
                    qualities.append(transfer_quality_from_slack(bus_departure - rail_arrival - profile.transfer_walk_min, profile))
            cells.append(math.fsum(qualities) / len(qualities))

            if route.bus_to_rail_passenger_event_supported:
                public_returns = tuple(t + route.public_runtime_min for t in departures)
                qualities = []
                rail_departures = rail_index[direction]["departures"]
                for bus_arrival in public_returns:
                    rail_departure = _next(rail_departures, bus_arrival)
                    if rail_departure is None:
                        qualities.append(0.0)
                    else:
                        qualities.append(transfer_quality_from_slack(rail_departure - bus_arrival - profile.transfer_walk_min, profile))
                cells.append(math.fsum(qualities) / len(qualities))
    return tuple(cells)


def precompute_route_phase_cells(
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
            route_phase_cell_values(
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


def evaluate_phase_vector(phase_vector: Sequence[int], precomputed: Sequence[Sequence[Sequence[float]]]) -> PhaseEvaluation:
    if len(phase_vector) != len(precomputed):
        raise ValueError("phase vector length mismatch")
    cells: list[float] = []
    for route_index, phase in enumerate(phase_vector):
        if phase < 0 or phase >= len(precomputed[route_index]):
            raise ValueError("phase outside exact domain")
        cells.extend(precomputed[route_index][phase])
    if not cells:
        raise ValueError("phase vector produced no S8 quality cells")
    return PhaseEvaluation(
        phase_vector=tuple(int(v) for v in phase_vector),
        robust_min_transfer_quality=min(cells),
        robust_unweighted_mean_transfer_quality=math.fsum(cells) / len(cells),
        cell_values=tuple(cells),
    )


def choose_exact_phase_vector(headway: int, precomputed: Sequence[Sequence[Sequence[float]]]) -> tuple[PhaseEvaluation, int]:
    if headway <= 0 or not precomputed:
        raise ValueError("non-empty exact phase domain required")
    best: PhaseEvaluation | None = None
    count = 0
    for vector in itertools.product(range(headway), repeat=len(precomputed)):
        count += 1
        candidate = evaluate_phase_vector(vector, precomputed)
        if best is None or candidate.objective_key > best.objective_key:
            best = candidate
    if best is None or count != headway ** len(precomputed):
        raise AssertionError("exact phase enumeration incomplete")
    return best, count


def brute_force_oracle(headway: int, precomputed: Sequence[Sequence[Sequence[float]]]) -> tuple[PhaseEvaluation, int]:
    """Independent recursive enumerator used as an exact oracle."""
    best: PhaseEvaluation | None = None
    count = 0
    vector = [0] * len(precomputed)

    def visit(depth: int) -> None:
        nonlocal best, count
        if depth == len(vector):
            count += 1
            candidate = evaluate_phase_vector(tuple(vector), precomputed)
            if best is None or candidate.objective_key > best.objective_key:
                best = candidate
            return
        for phase in range(headway):
            vector[depth] = phase
            visit(depth + 1)

    visit(0)
    if best is None:
        raise AssertionError("oracle generated no phase vectors")
    return best, count


def exact_vehicle_blocks(
    routes: Sequence[RouteInput],
    phase_vector: Sequence[int],
    *,
    headway: int,
    span_start: int,
    span_end: int,
    recovery_min: int,
) -> tuple[int, dict[tuple[str, int], int]]:
    if recovery_min < 0:
        raise ValueError("recovery must be non-negative")
    tasks: list[tuple[float, float, str, int]] = []
    for route, phase in zip(routes, phase_vector):
        for ordinal, departure in enumerate(clockface_times(int(phase), headway, span_start, span_end)):
            tasks.append((departure, departure + route.cycle_runtime_min + recovery_min, route.route_id, ordinal))
    tasks.sort(key=lambda row: (row[0], row[2], row[3]))
    available: list[tuple[float, int]] = []
    assignment: dict[tuple[str, int], int] = {}
    next_vehicle = 0
    for departure, ready, route_id, ordinal in tasks:
        if available and available[0][0] <= departure + 1e-12:
            _, vehicle = heapq.heappop(available)
        else:
            vehicle = next_vehicle
            next_vehicle += 1
        assignment[(route_id, ordinal)] = vehicle
        heapq.heappush(available, (ready, vehicle))
    return next_vehicle, assignment


def bus_to_rail_miss_share_by_stress(
    routes: Sequence[RouteInput],
    phase_vector: Sequence[int],
    *,
    headway: int,
    span_start: int,
    span_end: int,
    rail_index: Mapping[str, Mapping[str, Sequence[float]]],
    profiles: Sequence[TransferProfile],
) -> dict[str, float | None]:
    """Transparent deterministic runtime-delay stress, not an empirical probability.

    Stress magnitudes reuse the declared 0/5/10/15-minute operational sensitivity
    scale. They are reported only and never enter phase selection.
    """
    result: dict[str, float | None] = {}
    for stress in RUNTIME_STRESS_MIN:
        misses = 0
        total = 0
        for route, phase in zip(routes, phase_vector):
            if not route.bus_to_rail_passenger_event_supported:
                continue
            departures = clockface_times(int(phase), headway, span_start, span_end)
            for bus_arrival_nominal in (t + route.public_runtime_min for t in departures):
                bus_arrival = bus_arrival_nominal + stress
                for profile in profiles:
                    for direction in DIRECTIONS:
                        rail_departure = _next(rail_index[direction]["departures"], bus_arrival)
                        total += 1
                        if rail_departure is None or rail_departure - bus_arrival - profile.transfer_walk_min < 0:
                            misses += 1
        result[str(stress)] = None if total == 0 else misses / total
    return result
