"""Exact non-decisional hub-phase surface for the corrected RT-031 candidate.

The calculation is cyclic clock geometry.  It does not construct a daily
timetable, select a service span, or turn deterministic transfer quality into
an empirical probability.
"""
from __future__ import annotations

from dataclasses import asdict
from itertools import product
from typing import Mapping, Sequence

from src.phase2_exact_timetable_optimizer_v2 import (
    DIRECTIONS,
    TransferProfile,
    transfer_quality_from_slack,
)


def next_cyclic_wait(origin_minute: float, target_phases: Sequence[float], period: int = 60) -> float:
    if period <= 0 or not target_phases:
        raise ValueError("positive period and nonempty target phases required")
    waits = [((float(target) - float(origin_minute)) % period) for target in target_phases]
    return min(waits)


def circular_max_gap(phases: Sequence[int], period: int = 60) -> int:
    values = sorted(set(int(value) for value in phases))
    if not values or any(value < 0 or value >= period for value in values):
        raise ValueError("phases outside cyclic domain")
    if len(values) == 1:
        return period
    gaps = [right - left for left, right in zip(values, values[1:])]
    gaps.append(period - values[-1] + values[0])
    return max(gaps)


def phase_metrics(
    phase_vector: Sequence[int],
    *,
    rail_events: Sequence[Mapping[str, object]],
    profiles: Sequence[TransferProfile],
    period: int = 60,
) -> dict[str, float | int]:
    if len(phase_vector) != 2 or any(type(value) is not int for value in phase_vector):
        raise ValueError("exactly two integer route phases required")
    if any(value < 0 or value >= period for value in phase_vector):
        raise ValueError("route phase outside domain")
    if not profiles:
        raise ValueError("transfer profiles required")
    result: dict[str, float | int] = {
        "route_1_hub_phase_min": phase_vector[0],
        "route_2_hub_phase_min": phase_vector[1],
        "combined_hub_max_gap_min": circular_max_gap(phase_vector, period),
    }
    for profile in profiles:
        profile.validate()
        for direction in DIRECTIONS:
            rows = [row for row in rail_events if str(row["direction"]).upper() == direction]
            if not rows:
                raise ValueError(f"missing rail direction {direction}")
            rail_arrivals = [float(row["arrival_min"]) % period for row in rows]
            rail_departures = [float(row["departure_min"]) % period for row in rows]

            rail_to_bus = [
                transfer_quality_from_slack(
                    next_cyclic_wait(arrival, phase_vector, period) - profile.transfer_walk_min,
                    profile,
                )
                for arrival in rail_arrivals
            ]
            bus_to_rail = [
                transfer_quality_from_slack(
                    next_cyclic_wait(phase, rail_departures, period) - profile.transfer_walk_min,
                    profile,
                )
                for phase in phase_vector
            ]
            stem = f"{profile.profile_id.lower()}__{direction.lower()}"
            result[f"{stem}__rail_to_bus_mean_quality"] = sum(rail_to_bus) / len(rail_to_bus)
            result[f"{stem}__bus_to_rail_mean_quality"] = sum(bus_to_rail) / len(bus_to_rail)
    return result


def pareto_frontier(rows: Sequence[Mapping[str, float | int]]) -> list[dict[str, float | int]]:
    if not rows:
        raise ValueError("nonempty phase surface required")
    identity = {"route_1_hub_phase_min", "route_2_hub_phase_min"}
    dimensions = [key for key in rows[0] if key not in identity]
    if "combined_hub_max_gap_min" not in dimensions:
        raise ValueError("headway regularity dimension missing")

    def no_worse(left, right):
        for key in dimensions:
            if key == "combined_hub_max_gap_min":
                if float(left[key]) > float(right[key]):
                    return False
            elif float(left[key]) < float(right[key]):
                return False
        return True

    def strict(left, right):
        return any(
            (float(left[key]) < float(right[key]))
            if key == "combined_hub_max_gap_min"
            else (float(left[key]) > float(right[key]))
            for key in dimensions
        )

    frontier = []
    for index, row in enumerate(rows):
        if not any(
            other_index != index and no_worse(other, row) and strict(other, row)
            for other_index, other in enumerate(rows)
        ):
            frontier.append(dict(row))
    return frontier


def exact_surface(rail_events, profiles, period: int = 60):
    rows = [
        phase_metrics(vector, rail_events=rail_events, profiles=profiles, period=period)
        for vector in product(range(period), repeat=2)
    ]
    return {
        "phase_vectors": rows,
        "frontier": pareto_frontier(rows),
        "evaluated_phase_vector_count": len(rows),
        "profiles": [asdict(profile) for profile in profiles],
    }


def repeating_phase_metrics(
    phase_vector: Sequence[int], *, route_headway_min: int,
    rail_events: Sequence[Mapping[str, object]],
    profiles: Sequence[TransferProfile], period: int = 60,
) -> dict[str, float | int]:
    """Metrics for two routes repeating more frequently than the clock period."""
    if (len(phase_vector) != 2 or any(type(value) is not int for value in phase_vector)
            or route_headway_min <= 0 or period % route_headway_min):
        raise ValueError("two phases and a period-dividing headway required")
    if any(value < 0 or value >= route_headway_min for value in phase_vector):
        raise ValueError("base route phase outside headway domain")
    if not profiles:
        raise ValueError("transfer profiles required")
    repeats = period // route_headway_min
    route_departures = [
        tuple(phase + repeat * route_headway_min for repeat in range(repeats))
        for phase in phase_vector
    ]
    combined = tuple(value for route in route_departures for value in route)
    result: dict[str, float | int] = {
        "route_1_hub_phase_min": phase_vector[0],
        "route_2_hub_phase_min": phase_vector[1],
        "combined_hub_max_gap_min": circular_max_gap(combined, period),
    }
    for profile in profiles:
        profile.validate()
        for direction in DIRECTIONS:
            rows = [row for row in rail_events
                    if str(row["direction"]).upper() == direction]
            if not rows:
                raise ValueError(f"missing rail direction {direction}")
            rail_arrivals = [float(row["arrival_min"]) % period for row in rows]
            rail_departures = [float(row["departure_min"]) % period for row in rows]
            rail_to_bus = [
                transfer_quality_from_slack(
                    next_cyclic_wait(arrival, combined, period)
                    - profile.transfer_walk_min, profile)
                for arrival in rail_arrivals
            ]
            bus_to_rail = [
                transfer_quality_from_slack(
                    next_cyclic_wait(departure, rail_departures, period)
                    - profile.transfer_walk_min, profile)
                for departure in combined
            ]
            stem = f"{profile.profile_id.lower()}__{direction.lower()}"
            result[f"{stem}__rail_to_bus_mean_quality"] = (
                sum(rail_to_bus) / len(rail_to_bus))
            result[f"{stem}__bus_to_rail_mean_quality"] = (
                sum(bus_to_rail) / len(bus_to_rail))
    return result


def exact_repeating_surface(
        rail_events, profiles, *, route_headway_min: int, period: int = 60):
    rows = [
        repeating_phase_metrics(
            vector, route_headway_min=route_headway_min,
            rail_events=rail_events, profiles=profiles, period=period)
        for vector in product(range(route_headway_min), repeat=2)
    ]
    return {
        "phase_vectors": rows,
        "frontier": pareto_frontier(rows),
        "evaluated_phase_vector_count": len(rows),
        "route_headway_min": route_headway_min,
        "profiles": [asdict(profile) for profile in profiles],
    }
