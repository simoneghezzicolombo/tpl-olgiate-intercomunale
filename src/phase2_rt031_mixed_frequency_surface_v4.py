"""Non-decisional H30-peak/H60-off-peak timetable helpers for RT031."""
from __future__ import annotations

from bisect import bisect_left
from decimal import Decimal
from fractions import Fraction
import heapq
from math import fsum

from src.phase2_exact_timetable_optimizer_v2 import (
    DIRECTIONS,
    RUNTIME_STRESS_MIN,
    transfer_quality_from_slack,
)
from src.phase2_rt031_single_line_timetable_surface_v3 import (
    route_for_engineering_case,
)


ANNUAL_SERVICE_DAYS = 260
PHASE_DOMAIN = tuple(range(30))


def _template(template_id, start, span_hours, peak_slots):
    base = tuple(start + 60 * slot for slot in range(span_hours))
    extras = tuple(start + 60 * slot + 30 for slot in peak_slots)
    departures = tuple(sorted(base + extras))
    if len(departures) != 20 or set(
            b - a for a, b in zip(departures, departures[1:])) - {30, 60}:
        raise ValueError("mixed template must contain 20 H30/H60 departures")
    return {
        "template_id": template_id,
        "nominal_span_start_min": start,
        "span_minutes": span_hours * 60,
        "h30_peak_hours": len(peak_slots),
        "h60_base_hours": span_hours,
        "nominal_departure_minutes": departures,
    }


def mixed_service_templates():
    """Simple clockface templates; all have exactly 20 daily departures."""
    return (
        _template("H30_PEAK_H60_12H", 7 * 60, 12,
                  tuple(range(0, 4)) + tuple(range(8, 12))),
        _template("H30_PEAK_H60_14H", 6 * 60, 14,
                  (1, 2, 3, 11, 12, 13)),
        _template("H30_PEAK_H60_16H", 6 * 60, 16, (1, 2, 11, 12)),
        _template("H30_PEAK_H60_18H", 6 * 60, 18, (1, 12)),
    )


def phased_departures(template, phase):
    if phase not in PHASE_DOMAIN:
        raise ValueError("phase must preserve the common H30 clockface")
    return tuple(float(value + phase)
                 for value in template["nominal_departure_minutes"])


def _next(values, at_or_after):
    index = bisect_left(values, at_or_after)
    return None if index >= len(values) else float(values[index])


def route_cell_values_for_departures(route, departures, *, envelope_start,
                                     envelope_end, rail_index, profiles):
    route.validate()
    cells = []
    for profile in profiles:
        for direction in DIRECTIONS:
            arrivals = [value for value in rail_index[direction]["arrivals"]
                        if envelope_start <= value < envelope_end]
            if not arrivals:
                raise ValueError("mixed service envelope contains no rail arrivals")
            qualities = []
            for arrival in arrivals:
                departure = _next(departures, arrival)
                qualities.append(0.0 if departure is None else
                    transfer_quality_from_slack(
                        departure - arrival - profile.transfer_walk_min, profile))
            cells.append(fsum(qualities) / len(qualities))
            returns = tuple(value + route.public_runtime_min for value in departures)
            qualities = []
            for arrival in returns:
                departure = _next(rail_index[direction]["departures"], arrival)
                qualities.append(0.0 if departure is None else
                    transfer_quality_from_slack(
                        departure - arrival - profile.transfer_walk_min, profile))
            cells.append(fsum(qualities) / len(qualities))
    return tuple(cells)


def exact_vehicle_count_for_departures(route, departures, recovery_min):
    if recovery_min < 0:
        raise ValueError("recovery must be non-negative")
    available = []
    count = 0
    for departure in departures:
        ready = departure + route.cycle_runtime_min + recovery_min
        if available and available[0] <= departure + 1e-12:
            heapq.heapreplace(available, ready)
        else:
            heapq.heappush(available, ready)
            count += 1
    return count


def miss_share_for_departures(route, departures, rail_index, profiles):
    result = {}
    for stress in RUNTIME_STRESS_MIN:
        misses = 0
        total = 0
        for nominal in (value + route.public_runtime_min for value in departures):
            arrival = nominal + stress
            for profile in profiles:
                for direction in DIRECTIONS:
                    departure = _next(rail_index[direction]["departures"], arrival)
                    total += 1
                    if (departure is None
                            or departure - arrival - profile.transfer_walk_min < 0):
                        misses += 1
        result[str(stress)] = misses / total
    return result


def evaluate_mixed_context(profile, municipal_candidate, *, template, phase,
                           rail_index, transfer_profiles):
    departures = phased_departures(template, phase)
    envelope_start = template["nominal_span_start_min"] + phase
    envelope_end = envelope_start + template["span_minutes"]
    cases = profile["operational_source_model_screen"][
        "inherited_stage_f_engineering_grid"]["cases"]
    if len(cases) != 27:
        raise ValueError("inherited deterministic engineering grid changed")
    case_rows = []
    for case in cases:
        route = route_for_engineering_case(case)
        cells = route_cell_values_for_departures(
            route, departures, envelope_start=envelope_start,
            envelope_end=envelope_end, rail_index=rail_index,
            profiles=transfer_profiles)
        recovery = int(case["recovery_minutes"])
        case_rows.append({
            "runtime_multiplier": case["runtime_multiplier"],
            "dwell_per_nonhub_public_stop_event_min":
                case["dwell_per_nonhub_public_stop_event_min"],
            "recovery_minutes": case["recovery_minutes"],
            "exact_vehicle_count": exact_vehicle_count_for_departures(
                route, departures, recovery),
            "minimum_transfer_quality": min(cells),
            "unweighted_mean_transfer_quality": fsum(cells) / len(cells),
            "deterministic_bus_to_rail_miss_share_by_runtime_stress_min":
                miss_share_for_departures(
                    route, departures, rail_index, transfer_profiles),
        })
    distance = profile["total_distance_m"]
    return {
        "profile_id": profile["profile_id"],
        "source_candidate_line_id": profile["source_candidate_line_id"],
        "template_id": template["template_id"],
        "span_minutes": template["span_minutes"],
        "h30_peak_hours": template["h30_peak_hours"],
        "h60_base_hours": template["h60_base_hours"],
        "phase_min": phase,
        "departure_count": len(departures),
        "departures_min": list(departures),
        "exact_total_coverage": municipal_candidate["exact_total_coverage"],
        "exact_municipality_coverage":
            municipal_candidate["exact_municipality_coverage"],
        "retained_current_exact_stop_count":
            profile["retained_current_exact_stop_count"],
        "conditional_annual_bus_km": str(
            Decimal(str(distance)) * len(departures)
            * ANNUAL_SERVICE_DAYS / Decimal(1000)),
        "robust_min_transfer_quality": min(
            row["minimum_transfer_quality"] for row in case_rows),
        "robust_unweighted_mean_transfer_quality": min(
            row["unweighted_mean_transfer_quality"] for row in case_rows),
        "maximum_exact_vehicle_count": max(
            row["exact_vehicle_count"] for row in case_rows),
        "minimum_exact_vehicle_count": min(
            row["exact_vehicle_count"] for row in case_rows),
        "worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min": {
            stress: max(row[
                "deterministic_bus_to_rail_miss_share_by_runtime_stress_min"]
                [stress] for row in case_rows)
            for stress in ("0", "5", "10", "15")
        },
        "engineering_cases": case_rows,
    }


def mixed_pareto_frontier(rows, municipality_codes):
    """Exact no-weight frontier with caller-preferred longer span as one axis."""
    codes = tuple(sorted(str(value) for value in municipality_codes))
    prepared = []
    for row in rows:
        benefit = tuple(
            Fraction(row["exact_total_coverage"][str(threshold)])
            for threshold in (5, 8, 10)
        ) + tuple(
            Fraction(row["exact_municipality_coverage"][code][str(threshold)])
            for code in codes for threshold in (5, 8, 10)
        ) + (
            Fraction(row["retained_current_exact_stop_count"], 11),
            Fraction(row["span_minutes"], 1),
            Fraction(row["h30_peak_hours"], 1),
            Fraction(str(row["robust_min_transfer_quality"])),
            Fraction(str(row["robust_unweighted_mean_transfer_quality"])),
            -Fraction(row["conditional_annual_bus_km"]),
            -Fraction(row["maximum_exact_vehicle_count"], 1),
        ) + tuple(
            -Fraction(str(row[
                "worst_deterministic_bus_to_rail_miss_share_by_runtime_stress_min"]
                [stress])) for stress in ("0", "5", "10", "15")
        )
        prepared.append((row, benefit))

    def dominates(left, right):
        return (all(a >= b for a, b in zip(left, right))
                and left != right)

    frontier = []
    for row, vector in prepared:
        if any(dominates(other_vector, vector)
               for _, other_vector in frontier):
            continue
        frontier = [(other_row, other_vector)
                    for other_row, other_vector in frontier
                    if not dominates(vector, other_vector)]
        frontier.append((row, vector))
    return sorted((row for row, _ in frontier), key=lambda row: (
        row["profile_id"], row["template_id"], row["phase_min"]))
