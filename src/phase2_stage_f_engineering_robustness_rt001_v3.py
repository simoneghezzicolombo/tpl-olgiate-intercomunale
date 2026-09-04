"""Pure Stage-F engineering-sensitivity helpers for the RT-001 V3 lineage.

This module deliberately does not estimate probabilities or passenger demand.
It preserves the nominal planned S8 target identity from Stage E and tests that
same target under deterministic runtime, dwell and rail-clock perturbations.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import heapq
import math
from typing import Iterable, Mapping, Sequence

from src.phase2_final_operational_robustness_v2 import ConnectionCandidate, ExactTrip

EPS = 1e-9
HUB_ID = "rail:S01514"


@dataclass(frozen=True)
class RouteStressMeta:
    route_id: str
    public_runtime_min: float
    cycle_runtime_min: float
    nonhub_public_stop_occurrences: int
    bus_to_rail_passenger_event_supported: bool

    def validate(self) -> None:
        if not self.route_id:
            raise ValueError("route_id is required")
        if not math.isfinite(self.public_runtime_min) or self.public_runtime_min <= 0:
            raise ValueError("public_runtime_min must be finite and positive")
        if not math.isfinite(self.cycle_runtime_min) or self.cycle_runtime_min <= 0:
            raise ValueError("cycle_runtime_min must be finite and positive")
        if self.cycle_runtime_min + EPS < self.public_runtime_min:
            raise ValueError("cycle runtime cannot be shorter than public runtime")
        if self.nonhub_public_stop_occurrences < 0:
            raise ValueError("nonhub stop count cannot be negative")

    def public_runtime_stressed(self, multiplier: float, dwell_per_stop_min: float) -> float:
        _validate_stress(multiplier, dwell_per_stop_min)
        return self.public_runtime_min * multiplier + dwell_per_stop_min * self.nonhub_public_stop_occurrences

    def cycle_runtime_stressed(self, multiplier: float, dwell_per_stop_min: float) -> float:
        _validate_stress(multiplier, dwell_per_stop_min)
        return self.cycle_runtime_min * multiplier + dwell_per_stop_min * self.nonhub_public_stop_occurrences

    def public_runtime_delta(self, multiplier: float, dwell_per_stop_min: float) -> float:
        return self.public_runtime_stressed(multiplier, dwell_per_stop_min) - self.public_runtime_min


def _validate_stress(multiplier: float, dwell: float) -> None:
    if not math.isfinite(multiplier) or multiplier <= 0:
        raise ValueError("runtime multiplier must be finite and positive")
    if not math.isfinite(dwell) or dwell < 0:
        raise ValueError("dwell must be finite and non-negative")


def fixed_target_retained(
    candidate: ConnectionCandidate,
    *,
    route_meta: RouteStressMeta,
    runtime_multiplier: float,
    dwell_per_stop_min: float,
    rail_clock_shift_min: float,
) -> bool | None:
    """Test retention of the already-planned target without target rebinding."""
    if not math.isfinite(rail_clock_shift_min):
        raise ValueError("rail clock shift must be finite")
    if not candidate.planned_connection_exists:
        return None
    if candidate.nominal_slack_min is None:
        raise ValueError("planned connection lacks nominal slack")
    if candidate.connection_type == "BUS_TO_RAIL":
        delta = route_meta.public_runtime_delta(runtime_multiplier, dwell_per_stop_min)
        # The same frozen rail target is shifted by the engineering rail clock case.
        return candidate.nominal_slack_min - delta + rail_clock_shift_min >= -EPS
    if candidate.connection_type == "RAIL_TO_BUS":
        # Clockface bus departure stays fixed; only the frozen rail source event shifts.
        return candidate.nominal_slack_min - rail_clock_shift_min >= -EPS
    raise ValueError(f"unsupported connection type {candidate.connection_type!r}")


def retained_count_from_sorted_slacks(slacks: Sequence[float], required_slack: float) -> int:
    """Exact count for condition slack >= required_slack."""
    if not math.isfinite(required_slack):
        raise ValueError("required slack must be finite")
    if any(not math.isfinite(v) for v in slacks):
        raise ValueError("slacks must be finite")
    if any(a > b for a, b in zip(slacks, slacks[1:])):
        raise ValueError("slacks must be sorted")
    return len(slacks) - bisect_left(slacks, required_slack - EPS)


def aggregate_fixed_target_retention(
    candidates: Sequence[ConnectionCandidate],
    route_meta: Mapping[str, RouteStressMeta],
    *,
    runtime_multiplier: float,
    dwell_per_stop_min: float,
    rail_clock_shift_min: float,
) -> dict[tuple[str, str, str], tuple[int, int, int]]:
    """Return source/planned/retained counts by profile, type and direction."""
    grouped: dict[tuple[str, str, str], list[ConnectionCandidate]] = {}
    for candidate in candidates:
        candidate.validate()
        grouped.setdefault((candidate.profile_id, candidate.connection_type, candidate.direction), []).append(candidate)
    out: dict[tuple[str, str, str], tuple[int, int, int]] = {}
    for key, rows in grouped.items():
        retained = 0
        planned = 0
        for candidate in rows:
            if candidate.planned_connection_exists:
                planned += 1
                meta = route_meta[candidate.route_id]
                if fixed_target_retained(
                    candidate,
                    route_meta=meta,
                    runtime_multiplier=runtime_multiplier,
                    dwell_per_stop_min=dwell_per_stop_min,
                    rail_clock_shift_min=rail_clock_shift_min,
                ):
                    retained += 1
        out[key] = (len(rows), planned, retained)
    return out


def stressed_vehicle_return_min(
    trip: ExactTrip,
    route_meta: RouteStressMeta,
    *,
    runtime_multiplier: float,
    dwell_per_stop_min: float,
) -> float:
    return trip.hub_departure_min + route_meta.cycle_runtime_stressed(runtime_multiplier, dwell_per_stop_min)


def minimum_vehicle_requirement(intervals: Sequence[tuple[float, float]]) -> int:
    """Exact interval-graph colouring number for common-hub vehicle blocks."""
    heap: list[float] = []
    peak = 0
    for start, end in sorted(intervals):
        if not (math.isfinite(start) and math.isfinite(end)) or end + EPS < start:
            raise ValueError("invalid vehicle interval")
        while heap and heap[0] <= start + EPS:
            heapq.heappop(heap)
        heapq.heappush(heap, end)
        peak = max(peak, len(heap))
    return peak


def audit_stressed_blocks(
    trips: Sequence[ExactTrip],
    route_meta: Mapping[str, RouteStressMeta],
    *,
    runtime_multiplier: float,
    dwell_per_stop_min: float,
    recovery_min: int,
) -> dict[str, float | int | bool | None]:
    if recovery_min < 0:
        raise ValueError("recovery must be non-negative")
    stressed: list[tuple[ExactTrip, float]] = []
    for trip in trips:
        trip.validate()
        end = stressed_vehicle_return_min(
            trip, route_meta[trip.route_id],
            runtime_multiplier=runtime_multiplier,
            dwell_per_stop_min=dwell_per_stop_min,
        ) + recovery_min
        stressed.append((trip, end))
    minimum = minimum_vehicle_requirement([(t.hub_departure_min, end) for t, end in stressed])
    nominal_ids = {int(t.block_by_recovery[recovery_min]) for t, _ in stressed}
    nominal_fleet = len(nominal_ids)
    conflicts = 0
    slacks: list[float] = []
    by_block: dict[int, list[tuple[ExactTrip, float]]] = {}
    for item in stressed:
        by_block.setdefault(int(item[0].block_by_recovery[recovery_min]), []).append(item)
    for rows in by_block.values():
        rows.sort(key=lambda x: (x[0].hub_departure_min, x[0].route_id, x[0].trip_ordinal))
        for (_, previous_end), (next_trip, _) in zip(rows, rows[1:]):
            slack = next_trip.hub_departure_min - previous_end
            slacks.append(slack)
            if slack < -EPS:
                conflicts += 1
    return {
        "nominal_stage_d_fleet": nominal_fleet,
        "minimum_vehicle_requirement": minimum,
        "minimum_additional_vehicle_requirement": max(0, minimum - nominal_fleet),
        "vehicle_conflict_count_on_nominal_blocks": conflicts,
        "nominal_block_assignment_infeasible_under_case": conflicts > 0,
        "minimum_block_slack_min": None if not slacks else min(slacks),
        "median_block_slack_min": None if not slacks else _median(slacks),
        "maximum_block_slack_min": None if not slacks else max(slacks),
    }


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
