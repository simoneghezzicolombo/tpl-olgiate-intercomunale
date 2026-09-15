"""Exhaustive non-decisional H30/10h timetable surface for one-line candidates."""
from __future__ import annotations

from fractions import Fraction
from math import fsum

from src.phase2_exact_timetable_optimizer_v2 import (
    RouteInput,
    bus_to_rail_miss_share_by_stress,
    exact_vehicle_blocks,
    route_phase_cell_values,
)
from src.phase2_rt031_daily_timetable_surface_v3 import aligned_span_starts


HEADWAY_MIN = 30
SPAN_MINUTES = 600


def single_line_span_starts():
    return aligned_span_starts(span_minutes=SPAN_MINUTES)


def single_line_phase_vectors():
    return tuple((phase,) for phase in range(HEADWAY_MIN))


def route_for_engineering_case(case):
    components = case.get("components", ())
    if len(components) != 1:
        raise ValueError("one typed service component required")
    recovery = float(case["recovery_minutes"])
    public_runtime = float(
        components[0]["cycle_minutes_source_model_sensitivity"]) - recovery
    if public_runtime <= 0:
        raise ValueError("engineering case has non-positive public runtime")
    return RouteInput(
        route_id=str(components[0]["component_id"]),
        public_runtime_min=public_runtime,
        cycle_runtime_min=public_runtime,
        public_service_starts_at_hub=True,
        public_service_returns_to_hub=True,
        vehicle_closure_added=False,
        rail_to_bus_passenger_event_supported=True,
        bus_to_rail_passenger_event_supported=True,
    )


def evaluate_single_line_context(profile, *, phase, span_start, rail_index,
                                 transfer_profiles):
    ratios = tuple(profile.get("exact_access_ratios", ()))
    if len(ratios) != 6:
        raise ValueError("six exact access/equity ratios required")
    tuple(Fraction(value) for value in ratios)
    retention = profile.get("retained_current_exact_stop_count")
    if type(retention) is not int or not 0 <= retention <= 11:
        raise ValueError("valid exact current-stop retention count required")
    cases = profile["operational_source_model_screen"][
        "inherited_stage_f_engineering_grid"]["cases"]
    if len(cases) != 27:
        raise ValueError("inherited deterministic engineering grid changed")
    span_end = span_start + SPAN_MINUTES
    case_rows = []
    for case in cases:
        route = route_for_engineering_case(case)
        cells = route_phase_cell_values(
            route, phase=phase, headway=HEADWAY_MIN,
            span_start=span_start, span_end=span_end,
            rail_index=rail_index, profiles=transfer_profiles)
        recovery = int(case["recovery_minutes"])
        fleet, _ = exact_vehicle_blocks(
            (route,), (phase,), headway=HEADWAY_MIN,
            span_start=span_start, span_end=span_end, recovery_min=recovery)
        misses = bus_to_rail_miss_share_by_stress(
            (route,), (phase,), headway=HEADWAY_MIN,
            span_start=span_start, span_end=span_end,
            rail_index=rail_index, profiles=transfer_profiles)
        case_rows.append({
            "runtime_multiplier": case["runtime_multiplier"],
            "dwell_per_nonhub_public_stop_event_min":
                case["dwell_per_nonhub_public_stop_event_min"],
            "recovery_minutes": case["recovery_minutes"],
            "exact_vehicle_count": fleet,
            "minimum_transfer_quality": min(cells),
            "unweighted_mean_transfer_quality": fsum(cells) / len(cells),
            "deterministic_bus_to_rail_miss_share_by_runtime_stress_min": misses,
        })
    return {
        "profile_id": profile["profile_id"],
        "source_candidate_line_id": profile["source_candidate_line_id"],
        "exact_access_ratios": list(ratios),
        "retained_current_exact_stop_count": retention,
        "conditional_annual_bus_km": profile["conditional_annual_bus_km"],
        "span_start_min": span_start,
        "span_end_min": span_end,
        "single_line_hub_phase_min": phase,
        "engineering_case_count": len(case_rows),
        "robust_min_transfer_quality": min(
            row["minimum_transfer_quality"] for row in case_rows),
        "robust_unweighted_mean_transfer_quality": min(
            row["unweighted_mean_transfer_quality"] for row in case_rows),
        "maximum_exact_vehicle_count": max(
            row["exact_vehicle_count"] for row in case_rows),
        "minimum_exact_vehicle_count": min(
            row["exact_vehicle_count"] for row in case_rows),
        "all_engineering_cases_at_most_two_vehicles": all(
            row["exact_vehicle_count"] <= 2 for row in case_rows),
        "worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min": {
            stress: max(
                row["deterministic_bus_to_rail_miss_share_by_runtime_stress_min"]
                [stress] for row in case_rows)
            for stress in ("0", "5", "10", "15")
        },
        "engineering_cases": case_rows,
    }


def robust_single_line_pareto_frontier(rows):
    """No-weight Pareto frontier including retention and annual resources."""
    prepared = []
    for row in rows:
        max_key = tuple(Fraction(value) for value in row["exact_access_ratios"]) + (
            Fraction(row["retained_current_exact_stop_count"], 11),
            row["robust_min_transfer_quality"],
            row["robust_unweighted_mean_transfer_quality"],
        )
        min_key = (
            Fraction(str(row["conditional_annual_bus_km"])),
            row["maximum_exact_vehicle_count"],
        ) + tuple(
            row["worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min"]
            [stress] for stress in ("0", "5", "10", "15"))
        prepared.append((row, max_key, min_key))

    def dominates(left_max, left_min, right_max, right_min):
        weak = (all(a >= b for a, b in zip(left_max, right_max))
                and all(a <= b for a, b in zip(left_min, right_min)))
        return weak and (left_max != right_max or left_min != right_min)

    frontier = [row for index, (row, max_key, min_key) in enumerate(prepared)
                if not any(index != other_index and dominates(
                    other_max, other_min, max_key, min_key)
                    for other_index, (_, other_max, other_min)
                    in enumerate(prepared))]
    return sorted(frontier, key=lambda row: (
        row["profile_id"], row["span_start_min"],
        row["single_line_hub_phase_min"]))
