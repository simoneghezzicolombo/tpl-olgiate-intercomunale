"""Robust clockface S8 phase search for Phase 2 V2.

This module chooses only a hub clockface phase within an already declared
headway design. It does not select a topology, service policy, calendar, stop
set or passenger-demand weighting.

Public routes are known to begin at the rail hub in the certified structural
catalog. Their return-to-hub offsets are derived from the certified directed
path matrix, including an explicit shortest-path closure when a structural
route is open. Scheduled extensions use explicit repeating extension patterns;
an average fictitious runtime is never created.
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


def cyclic_transfer_quality(
    bus_offset_min: float,
    *,
    rail_offsets_min: Sequence[float],
    connection_type: str,
    profile: TransferQualityProfile,
) -> float:
    """Best steady-state transfer quality on a 60-minute clockface.

    Neighbouring hours are included so an event near :00 can connect to a rail
    event in the preceding/following hour. This is a repeating-clockface metric,
    not an exact first/last-service-day event claim.
    """
    if connection_type not in CONNECTION_TYPES:
        raise ValueError(f"Unsupported connection type {connection_type!r}")
    if not rail_offsets_min:
        raise ValueError("At least one rail minute offset is required")
    bus = float(bus_offset_min) % 60.0
    candidates: list[float] = []
    for raw in rail_offsets_min:
        base = float(raw) % 60.0
        candidates.extend((base - 60.0, base, base + 60.0, base + 120.0))
    best = -1.0
    for rail in candidates:
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
    """Return a lossless repeating extension/base pattern over clockface pulses."""
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
    pulses_per_hour = 60 // headway_min
    period_departures = math.lcm(pulses_per_hour, denominator)
    flags = tuple(
        ((ordinal - rotation) % denominator) < numerator if numerator else False
        for ordinal in range(period_departures)
    )
    if flags:
        realised = sum(flags) / len(flags)
        if not math.isclose(realised, extension_share, rel_tol=0.0, abs_tol=1e-12):
            raise AssertionError("Extension pattern does not conserve declared share")
    return flags, period_departures


def route_cycle_runtime(
    route: Sequence[str],
    runtime_lookup: Mapping[tuple[str, str], float],
) -> float:
    """Minimum closed runtime from a certified route sequence and matrix."""
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
) -> dict[tuple[str, str], tuple[float, ...]]:
    result: dict[tuple[str, str], tuple[float, ...]] = {}
    for connection_type in CONNECTION_TYPES:
        source_field = "departure_min" if connection_type == "BUS_TO_RAIL" else "arrival_min"
        for direction in RAIL_DIRECTIONS:
            values = sorted({
                round(float(row[source_field]) % 60.0, 9)
                for row in rail_events
                if str(row.get("direction", "")).upper() == direction
            })
            if not values:
                raise ValueError(f"No rail offsets for {connection_type}/{direction}")
            result[(connection_type, direction)] = tuple(values)
    return result


def _rotation_values(extension_share: float) -> range:
    if extension_share == 0.25:
        return range(4)
    if extension_share == 0.5:
        return range(2)
    return range(1)


def choose_robust_phase(
    *,
    headway_min: int,
    public_route_runtimes_min: Sequence[float],
    extension_share: float,
    extension_runtime_min: float | None,
    rail_events: Sequence[Mapping[str, object]],
    profiles: Sequence[PhasingProfile],
) -> dict[str, object]:
    """Choose one robust-balanced phase without passenger or topology weights.

    Primary objective is maximin across every transfer-profile x connection-type
    x rail-direction cell. Secondary objective is the unweighted mean across
    those same cells. Remaining ties use lower phase then lower extension
    rotation solely for deterministic reproducibility.
    """
    if headway_min <= 0 or 60 % headway_min != 0:
        raise ValueError("headway_min must be a positive divisor of 60")
    runtimes = tuple(float(value) for value in public_route_runtimes_min)
    if not runtimes or any((not math.isfinite(v) or v <= 0) for v in runtimes):
        raise ValueError("At least one positive finite public route runtime is required")
    if not profiles:
        raise ValueError("At least one phasing sensitivity profile is required")
    if extension_share not in SUPPORTED_EXTENSION_SHARES:
        raise ValueError("Unsupported extension_share")
    if extension_share > 0 and extension_runtime_min is None:
        raise ValueError("Positive extension_share requires an extension runtime")
    if extension_runtime_min is not None and (
        not math.isfinite(float(extension_runtime_min)) or float(extension_runtime_min) <= 0
    ):
        raise ValueError("extension runtime must be finite and positive")

    offsets = rail_clockface_offsets(rail_events)
    converted = [(profile.profile_id, profile.as_transfer_profile()) for profile in profiles]

    departure_q: dict[tuple[str, str, int], float] = {}
    arrival_q: dict[tuple[str, str, float, int], float] = {}
    for profile_id, profile in converted:
        for direction in RAIL_DIRECTIONS:
            for minute in range(60):
                departure_q[(profile_id, direction, minute)] = cyclic_transfer_quality(
                    minute,
                    rail_offsets_min=offsets[("RAIL_TO_BUS", direction)],
                    connection_type="RAIL_TO_BUS",
                    profile=profile,
                )
            unique_runtimes = set(runtimes)
            if extension_runtime_min is not None:
                unique_runtimes.add(float(extension_runtime_min))
            for runtime in unique_runtimes:
                for minute in range(60):
                    arrival_q[(profile_id, direction, runtime, minute)] = cyclic_transfer_quality(
                        (minute + runtime) % 60.0,
                        rail_offsets_min=offsets[("BUS_TO_RAIL", direction)],
                        connection_type="BUS_TO_RAIL",
                        profile=profile,
                    )

    best_key: tuple[float, float, int, int] | None = None
    best_payload: dict[str, object] | None = None

    for phase in range(headway_min):
        for rotation in _rotation_values(extension_share):
            flags, period_departures = extension_pattern(
                headway_min=headway_min,
                extension_share=extension_share,
                rotation=rotation,
            )
            departure_minutes = tuple(
                int((phase + ordinal * headway_min) % 60)
                for ordinal in range(period_departures)
            )
            cell_values: dict[str, float] = {}
            all_values: list[float] = []

            for profile_id, _profile in converted:
                for direction in RAIL_DIRECTIONS:
                    r2b = mean(
                        departure_q[(profile_id, direction, minute)]
                        for minute in departure_minutes
                    )
                    key = f"{profile_id}|RAIL_TO_BUS|{direction}"
                    cell_values[key] = r2b
                    all_values.append(r2b)

                    arrival_values: list[float] = []
                    if extension_share > 0:
                        if len(runtimes) != 1:
                            raise ValueError("Scheduled extension phasing expects exactly one public base route")
                        base_runtime = runtimes[0]
                        ext_runtime = float(extension_runtime_min)
                        for ordinal, minute in enumerate(departure_minutes):
                            runtime = ext_runtime if flags[ordinal] else base_runtime
                            arrival_values.append(arrival_q[(profile_id, direction, runtime, minute)])
                    else:
                        for minute in departure_minutes:
                            for runtime in runtimes:
                                arrival_values.append(arrival_q[(profile_id, direction, runtime, minute)])
                    b2r = mean(arrival_values)
                    key = f"{profile_id}|BUS_TO_RAIL|{direction}"
                    cell_values[key] = b2r
                    all_values.append(b2r)

            robust_min = min(all_values)
            robust_mean = mean(all_values)
            candidate_key = (robust_min, robust_mean, -phase, -rotation)
            if best_key is None or candidate_key > best_key:
                worst_cells: dict[str, float] = {}
                for connection_type in CONNECTION_TYPES:
                    for direction in RAIL_DIRECTIONS:
                        suffix = f"|{connection_type}|{direction}"
                        values = [value for key, value in cell_values.items() if key.endswith(suffix)]
                        worst_cells[f"worst_profile_{connection_type.lower()}_{direction.lower()}"] = min(values)
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
