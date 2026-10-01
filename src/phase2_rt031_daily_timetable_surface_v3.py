"""Non-decisional daily timetable and vehicle-block surface for RT031.

The layer evaluates every H30-aligned 12-hour span contained in the frozen S8
design window, every regular combined-H15 phase pair, and every inherited
runtime/dwell/recovery case.  It deliberately returns a surface rather than a
selected timetable.
"""
from __future__ import annotations

from fractions import Fraction
from math import fsum

from src.phase2_exact_timetable_optimizer_v2 import (
    RouteInput,
    bus_to_rail_miss_share_by_stress,
    exact_vehicle_blocks,
    route_phase_cell_values,
)


HEADWAY_MIN = 30
SPAN_MINUTES = 720
S8_DESIGN_WINDOW_START_MIN = 330
S8_DESIGN_WINDOW_END_MIN = 1440


def aligned_span_starts(*, window_start: int = S8_DESIGN_WINDOW_START_MIN,
                        window_end: int = S8_DESIGN_WINDOW_END_MIN,
                        span_minutes: int = SPAN_MINUTES,
                        alignment_min: int = HEADWAY_MIN) -> tuple[int, ...]:
    if alignment_min <= 0 or span_minutes <= 0 or window_end <= window_start:
        raise ValueError("invalid span surface")
    first = window_start + (-window_start % alignment_min)
    result = tuple(range(first, window_end - span_minutes + 1, alignment_min))
    if not result:
        raise ValueError("no aligned span fits the evidence window")
    return result


def regular_h15_phase_vectors(headway_min: int = HEADWAY_MIN) -> tuple[tuple[int, int], ...]:
    if headway_min != 30:
        raise ValueError("this certified diagnostic subspace requires H30")
    return tuple((phase, (phase + 15) % 30) for phase in range(30))


def routes_for_engineering_case(case) -> tuple[RouteInput, ...]:
    recovery = float(case["recovery_minutes"])
    routes = []
    for component in case["components"]:
        public_runtime = float(component["cycle_minutes_source_model_sensitivity"]) - recovery
        if public_runtime <= 0:
            raise ValueError("engineering case has non-positive public runtime")
        routes.append(RouteInput(
            route_id=str(component["component_id"]),
            public_runtime_min=public_runtime,
            cycle_runtime_min=public_runtime,
            public_service_starts_at_hub=True,
            public_service_returns_to_hub=True,
            vehicle_closure_added=False,
            rail_to_bus_passenger_event_supported=True,
            bus_to_rail_passenger_event_supported=True,
        ))
    if len(routes) != 2:
        raise ValueError("two typed components required")
    return tuple(routes)


def evaluate_timetable_context(profile, *, phase_vector, span_start, rail_index,
                               transfer_profiles):
    access_ratios = tuple(profile.get("exact_access_ratios", ()))
    if len(access_ratios) != 6:
        raise ValueError("six exact territorial access/equity ratios required")
    tuple(Fraction(value) for value in access_ratios)
    cases = profile["operational_source_model_screen"][
        "inherited_stage_f_engineering_grid"]["cases"]
    if len(cases) != 27:
        raise ValueError("inherited 27-case engineering grid changed")
    span_end = span_start + SPAN_MINUTES
    case_rows = []
    for case in cases:
        routes = routes_for_engineering_case(case)
        cells = []
        for route, phase in zip(routes, phase_vector):
            cells.extend(route_phase_cell_values(
                route, phase=phase, headway=HEADWAY_MIN,
                span_start=span_start, span_end=span_end,
                rail_index=rail_index, profiles=transfer_profiles))
        recovery = int(case["recovery_minutes"])
        fleet, _ = exact_vehicle_blocks(
            routes, phase_vector, headway=HEADWAY_MIN,
            span_start=span_start, span_end=span_end, recovery_min=recovery)
        miss = bus_to_rail_miss_share_by_stress(
            routes, phase_vector, headway=HEADWAY_MIN,
            span_start=span_start, span_end=span_end,
            rail_index=rail_index, profiles=transfer_profiles)
        case_rows.append({
            "runtime_multiplier": case["runtime_multiplier"],
            "dwell_per_nonhub_public_stop_event_min":
                case["dwell_per_nonhub_public_stop_event_min"],
            "recovery_minutes": case["recovery_minutes"],
            "exact_interlinable_vehicle_count": fleet,
            "minimum_transfer_quality": min(cells),
            "unweighted_mean_transfer_quality": fsum(cells) / len(cells),
            "bus_to_rail_miss_share_by_runtime_stress_min": miss,
        })
    return {
        "profile_id": profile["profile_id"],
        "exact_access_ratios": list(access_ratios),
        "span_start_min": span_start,
        "span_end_min": span_end,
        "route_1_hub_phase_min": phase_vector[0],
        "route_2_hub_phase_min": phase_vector[1],
        "engineering_case_count": len(case_rows),
        "robust_min_transfer_quality": min(
            row["minimum_transfer_quality"] for row in case_rows),
        "robust_unweighted_mean_transfer_quality": min(
            row["unweighted_mean_transfer_quality"] for row in case_rows),
        "maximum_exact_interlinable_vehicle_count": max(
            row["exact_interlinable_vehicle_count"] for row in case_rows),
        "minimum_exact_interlinable_vehicle_count": min(
            row["exact_interlinable_vehicle_count"] for row in case_rows),
        "all_engineering_cases_at_most_two_vehicles": all(
            row["exact_interlinable_vehicle_count"] <= 2 for row in case_rows),
        "worst_bus_to_rail_miss_share_by_runtime_stress_min": {
            stress: max(row["bus_to_rail_miss_share_by_runtime_stress_min"][stress]
                        for row in case_rows)
            for stress in ("0", "5", "10", "15")
        },
        "engineering_cases": case_rows,
    }


def robust_pareto_frontier(rows):
    """Retain no-weight robust timetable contexts across explicit axes."""
    prepared = []
    for row in rows:
        max_key = tuple(Fraction(value) for value in row["exact_access_ratios"]) + (
            row["robust_min_transfer_quality"],
            row["robust_unweighted_mean_transfer_quality"])
        min_key = (row["maximum_exact_interlinable_vehicle_count"],) + tuple(
            row["worst_bus_to_rail_miss_share_by_runtime_stress_min"][key]
            for key in ("0", "5", "10", "15"))
        prepared.append((row, max_key, min_key))

    def dominates(a_max, a_min, b_max, b_min):
        weak = all(x >= y for x, y in zip(a_max, b_max)) and all(
            x <= y for x, y in zip(a_min, b_min))
        strict = weak and (a_max != b_max or a_min != b_min)
        return weak and strict
    frontier = [row for i, (row, max_key, min_key) in enumerate(prepared)
                if not any(i != j and dominates(other_max, other_min, max_key, min_key)
                           for j, (_, other_max, other_min) in enumerate(prepared))]
    return sorted(frontier, key=lambda row: (
        row["profile_id"], row["span_start_min"],
        row["route_1_hub_phase_min"], row["route_2_hub_phase_min"]))
