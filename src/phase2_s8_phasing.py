"""Robust clockface S8 phase search for Phase 2 V2.

The search chooses only a hub clockface phase inside an already declared
uniform-headway design. It never selects a topology, annual calendar, stop set
or passenger-demand weighting.

The certified 2026-09-03 S8 reference day is exactly half-hourly in both
directions. This module therefore evaluates the repeating 30-minute clockface
and leaves first/last-trip and delay robustness to later exact timetable stages.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean
from typing import Mapping, Sequence

from src.phase2_s8_interchange import TransferQualityProfile, transfer_quality_from_slack


CONNECTION_TYPES = ("BUS_TO_RAIL", "RAIL_TO_BUS")
RAIL_DIRECTIONS = ("LECCO", "MILANO")
SUPPORTED_EXTENSION_SHARES = (0.0, 0.25, 0.5, 1.0)


@dataclass(frozen=True)
class PhasingProfile:
    profile_id: str
    transfer_walk_min: float
    preferred_wait_min: float
    miss_transition_scale_min: float
    wait_decay_min: float

    def as_transfer_profile(self) -> TransferQualityProfile:
        profile = TransferQualityProfile(
            transfer_walk_min=self.transfer_walk_min,
            preferred_wait_min=self.preferred_wait_min,
            miss_transition_scale_min=self.miss_transition_scale_min,
            wait_decay_min=self.wait_decay_min,
        )
        profile.validate()
        return profile


def route_cycle_runtime(
    route: Sequence[str],
    runtime_lookup: Mapping[tuple[str, str], float],
) -> float:
    """Minimum closed runtime from a certified route sequence and path matrix."""
    if len(route) < 2:
        raise ValueError("Route requires at least two anchors")
    total = 0.0
    for origin, destination in zip(route[:-1], route[1:]):
        try:
            total += float(runtime_lookup[(origin, destination)])
        except KeyError as exc:
            raise ValueError(f"Missing directed route leg {origin!r}->{destination!r}") from exc
    if route[-1] != route[0]:
        try:
            total += float(runtime_lookup[(route[-1], route[0])])
        except KeyError as exc:
            raise ValueError(f"Open route lacks certified return leg {route[-1]!r}->{route[0]!r}") from exc
    if not math.isfinite(total) or total <= 0:
        raise ValueError("Closed route runtime must be finite and positive")
    return total


def rail_clockface_offsets(
    rail_events: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], tuple[float, float]]:
    """Extract the certified half-hourly S8 minute offsets.

    Phase Search V2 intentionally fails closed if the factual reference day is
    not a strict two-pulse-per-hour clockface. A future non-clockface S8 day
    requires exact event scoring rather than silently using this shortcut.
    """
    result: dict[tuple[str, str], tuple[float, float]] = {}
    for connection_type in CONNECTION_TYPES:
        field = "departure_min" if connection_type == "BUS_TO_RAIL" else "arrival_min"
        for direction in RAIL_DIRECTIONS:
            values = sorted({
                round(float(row[field]) % 60.0, 9)
                for row in rail_events
                if str(row.get("direction", "")).upper() == direction
            })
            if len(values) != 2 or not math.isclose(
                values[1] - values[0], 30.0, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError(
                    f"S8 Phase V2 requires exact half-hour clockface offsets for "
                    f"{connection_type}/{direction}; got {values}"
                )
            result[(connection_type, direction)] = (values[0], values[1])
    return result


def clockface_transfer_quality(
    bus_offset_min: float,
    *,
    first_rail_offset_min: float,
    connection_type: str,
    profile: TransferQualityProfile,
) -> float:
    """Best transfer quality against an infinite 30-minute rail pulse lattice."""
    if connection_type not in CONNECTION_TYPES:
        raise ValueError(f"Unsupported connection type {connection_type!r}")
    bus = float(bus_offset_min)
    base = float(first_rail_offset_min)
    if connection_type == "BUS_TO_RAIL":
        target = bus + profile.transfer_walk_min + profile.preferred_wait_min
    else:
        target = bus - profile.transfer_walk_min - profile.preferred_wait_min
    k0 = math.floor((target - base) / 30.0)
    best = -1.0
    for k in range(k0 - 1, k0 + 3):
        rail = base + 30.0 * k
        if connection_type == "BUS_TO_RAIL":
            slack = rail - bus - profile.transfer_walk_min
        else:
            slack = bus - rail - profile.transfer_walk_min
        best = max(best, transfer_quality_from_slack(slack, profile))
    return best


def extension_pattern(
    *,
    headway_min: int,
    extension_share: float,
    rotation: int,
) -> tuple[tuple[bool, ...], int]:
    """Lossless repeating base/extension sequence over clockface departures."""
    if headway_min <= 0 or 60 % headway_min != 0:
        raise ValueError("headway_min must be a positive divisor of 60")
    if extension_share not in SUPPORTED_EXTENSION_SHARES:
        raise ValueError(f"Unsupported extension share {extension_share}")
    if extension_share == 0.0:
        denominator, numerator = 1, 0
    elif extension_share == 0.25:
        denominator, numerator = 4, 1
    elif extension_share == 0.5:
        denominator, numerator = 2, 1
    else:
        denominator, numerator = 1, 1
    if not 0 <= rotation < denominator:
        raise ValueError("rotation outside extension pattern denominator")
    period_departures = math.lcm(60 // headway_min, denominator)
    flags = tuple(
        ((ordinal - rotation) % denominator) < numerator if numerator else False
        for ordinal in range(period_departures)
    )
    realised = sum(flags) / len(flags)
    if not math.isclose(realised, extension_share, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError("Extension pattern does not conserve declared share")
    return flags, period_departures


def _rotation_values(extension_share: float) -> range:
    if extension_share == 0.25:
        return range(4)
    if extension_share == 0.5:
        return range(2)
    return range(1)


def _quality_tables(
    *,
    public_route_runtimes_min: Sequence[float],
    extension_runtime_min: float | None,
    rail_events: Sequence[Mapping[str, object]],
    profiles: Sequence[PhasingProfile],
) -> tuple[
    dict[tuple[str, str, int], float],
    dict[tuple[str, str, float, int], float],
]:
    offsets = rail_clockface_offsets(rail_events)
    runtimes = {float(value) for value in public_route_runtimes_min}
    if extension_runtime_min is not None:
        runtimes.add(float(extension_runtime_min))

    departure_q: dict[tuple[str, str, int], float] = {}
    arrival_q: dict[tuple[str, str, float, int], float] = {}
    for raw_profile in profiles:
        profile = raw_profile.as_transfer_profile()
        pid = raw_profile.profile_id
        for direction in RAIL_DIRECTIONS:
            r2b_base = offsets[("RAIL_TO_BUS", direction)][0]
            b2r_base = offsets[("BUS_TO_RAIL", direction)][0]
            for minute in range(30):
                departure_q[(pid, direction, minute)] = clockface_transfer_quality(
                    minute,
                    first_rail_offset_min=r2b_base,
                    connection_type="RAIL_TO_BUS",
                    profile=profile,
                )
            for runtime in runtimes:
                for minute in range(30):
                    arrival_q[(pid, direction, runtime, minute)] = clockface_transfer_quality(
                        minute + runtime,
                        first_rail_offset_min=b2r_base,
                        connection_type="BUS_TO_RAIL",
                        profile=profile,
                    )
    return departure_q, arrival_q


def _choose_with_tables(
    *,
    headway_min: int,
    runtimes: tuple[float, ...],
    extension_share: float,
    extension_runtime_min: float | None,
    profiles: Sequence[PhasingProfile],
    departure_q: Mapping[tuple[str, str, int], float],
    arrival_q: Mapping[tuple[str, str, float, int], float],
) -> dict[str, object]:
    best_key: tuple[float, float, int, int] | None = None
    best_payload: dict[str, object] | None = None

    for phase in range(headway_min):
        for rotation in _rotation_values(extension_share):
            flags, period_departures = extension_pattern(
                headway_min=headway_min,
                extension_share=extension_share,
                rotation=rotation,
            )
            pulse_minutes = tuple(
                int((phase + ordinal * headway_min) % 30)
                for ordinal in range(period_departures)
            )
            cell_values: dict[str, float] = {}
            all_values: list[float] = []
            for raw_profile in profiles:
                pid = raw_profile.profile_id
                for direction in RAIL_DIRECTIONS:
                    r2b = mean(
                        departure_q[(pid, direction, minute)]
                        for minute in pulse_minutes
                    )
                    r2b_key = f"{pid}|RAIL_TO_BUS|{direction}"
                    cell_values[r2b_key] = r2b
                    all_values.append(r2b)

                    arrivals: list[float] = []
                    if extension_share > 0:
                        if len(runtimes) != 1 or extension_runtime_min is None:
                            raise ValueError(
                                "Positive scheduled-extension share requires one public base route "
                                "and one explicit extension runtime"
                            )
                        base_runtime = runtimes[0]
                        ext_runtime = float(extension_runtime_min)
                        for ordinal, minute in enumerate(pulse_minutes):
                            runtime = ext_runtime if flags[ordinal] else base_runtime
                            arrivals.append(arrival_q[(pid, direction, runtime, minute)])
                    else:
                        for minute in pulse_minutes:
                            for runtime in runtimes:
                                arrivals.append(arrival_q[(pid, direction, runtime, minute)])
                    b2r = mean(arrivals)
                    b2r_key = f"{pid}|BUS_TO_RAIL|{direction}"
                    cell_values[b2r_key] = b2r
                    all_values.append(b2r)

            robust_min = min(all_values)
            robust_mean = mean(all_values)
            candidate_key = (robust_min, robust_mean, -phase, -rotation)
            if best_key is None or candidate_key > best_key:
                worst_cells: dict[str, float] = {}
                for connection_type in CONNECTION_TYPES:
                    for direction in RAIL_DIRECTIONS:
                        suffix = f"|{connection_type}|{direction}"
                        values = [
                            value for key, value in cell_values.items()
                            if key.endswith(suffix)
                        ]
                        worst_cells[
                            f"worst_profile_{connection_type.lower()}_{direction.lower()}"
                        ] = min(values)
                best_key = candidate_key
                best_payload = {
                    "phase_offset_min": phase,
                    "extension_rotation_index": rotation,
                    "extension_pattern_period_departures": period_departures,
                    "robust_min_transfer_quality": robust_min,
                    "robust_unweighted_mean_transfer_quality": robust_mean,
                    **worst_cells,
                    "profile_cell_quality": dict(sorted(cell_values.items())),
                }
    if best_payload is None:
        raise AssertionError("Phase search generated no candidate")
    return best_payload


def choose_robust_phase_grid(
    *,
    headways_min: Sequence[int],
    public_route_runtimes_min: Sequence[float],
    extension_shares: Sequence[float],
    extension_runtime_min: float | None,
    rail_events: Sequence[Mapping[str, object]],
    profiles: Sequence[PhasingProfile],
) -> dict[tuple[int, float], dict[str, object]]:
    """Evaluate multiple headways/shares while computing transfer curves once."""
    runtimes = tuple(float(value) for value in public_route_runtimes_min)
    if not runtimes or any((not math.isfinite(v) or v <= 0) for v in runtimes):
        raise ValueError("At least one positive finite public route runtime is required")
    if not profiles:
        raise ValueError("At least one phasing sensitivity profile is required")
    headways = tuple(sorted({int(v) for v in headways_min}))
    if any(h <= 0 or 60 % h != 0 for h in headways):
        raise ValueError("All headways must be positive divisors of 60")
    shares = tuple(sorted({float(v) for v in extension_shares}))
    if any(v not in SUPPORTED_EXTENSION_SHARES for v in shares):
        raise ValueError("Unsupported extension share")
    if any(v > 0 for v in shares) and extension_runtime_min is None:
        raise ValueError("Extension shares above zero require extension_runtime_min")

    departure_q, arrival_q = _quality_tables(
        public_route_runtimes_min=runtimes,
        extension_runtime_min=extension_runtime_min,
        rail_events=rail_events,
        profiles=profiles,
    )
    return {
        (headway, share): _choose_with_tables(
            headway_min=headway,
            runtimes=runtimes,
            extension_share=share,
            extension_runtime_min=extension_runtime_min,
            profiles=profiles,
            departure_q=departure_q,
            arrival_q=arrival_q,
        )
        for share in shares
        for headway in headways
    }


def choose_robust_phase(
    *,
    headway_min: int,
    public_route_runtimes_min: Sequence[float],
    extension_share: float,
    extension_runtime_min: float | None,
    rail_events: Sequence[Mapping[str, object]],
    profiles: Sequence[PhasingProfile],
) -> dict[str, object]:
    return choose_robust_phase_grid(
        headways_min=[headway_min],
        public_route_runtimes_min=public_route_runtimes_min,
        extension_shares=[extension_share],
        extension_runtime_min=extension_runtime_min,
        rail_events=rail_events,
        profiles=profiles,
    )[(headway_min, extension_share)]
