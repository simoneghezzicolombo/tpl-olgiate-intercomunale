"""Exact pool-scoped frequent-service territorial shortlist.

This layer applies the approved frequent-service preference and the hard budget
to an already computed candidate frontier, then retains access/equity Pareto
profiles.  It does not assign a timetable or select a network.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from fractions import Fraction


ACCESS_FIELDS = (
    "potential_core_share_5min",
    "potential_core_share_8min",
    "potential_core_share_10min",
    "potential_worst_municipality_share_5min",
    "potential_worst_municipality_share_8min",
    "potential_worst_municipality_share_10min",
)


def select_frequent_access_frontier(
        candidates, *, current_exact_ratios, headway_min: int,
        span_minutes: int):
    """Return exact access/equity nondominated benchmark improvements.

    Service eligibility is read from each candidate's certified service surface.
    Exact ratios, not display floats, decide all comparisons.
    """
    if headway_min <= 0 or headway_min > 30 or span_minutes <= 0:
        raise ValueError("positive approved frequent-service context required")
    current = tuple(Fraction(value) for value in current_exact_ratios)
    if len(current) != len(ACCESS_FIELDS):
        raise ValueError("six current access/equity ratios required")
    admitted = []
    seen = set()
    for row in candidates:
        identity = str(row.get("portfolio_id", ""))
        if not identity or identity in seen:
            raise ValueError("unique portfolio identity required")
        seen.add(identity)
        ratios = tuple(Fraction(value) for value in row.get("exact_access_ratios", ()))
        if len(ratios) != len(ACCESS_FIELDS):
            raise ValueError("six exact candidate ratios required")
        contexts = [item for item in row.get("service_surface", ())
                    if item.get("uniform_headway_min_per_movement") == headway_min
                    and item.get("span_minutes") == span_minutes]
        if len(contexts) != 1:
            raise ValueError("unique requested service context required")
        if contexts[0].get("within_approved_reference_cap") is not True:
            continue
        if (all(value >= baseline for value, baseline in zip(ratios, current))
                and any(value > baseline for value, baseline in zip(ratios, current))):
            admitted.append((row, ratios))
    frontier = []
    for index, (row, ratios) in enumerate(admitted):
        dominated = any(
            other_index != index
            and all(other >= value for other, value in zip(other_ratios, ratios))
            and any(other > value for other, value in zip(other_ratios, ratios))
            for other_index, (_, other_ratios) in enumerate(admitted)
        )
        if not dominated:
            frontier.append(row)
    frontier.sort(key=lambda row: row["portfolio_id"])
    return {
        "eligible_benchmark_improvement_count": len(admitted),
        "access_equity_frontier_count": len(frontier),
        "headway_min": headway_min,
        "span_minutes": span_minutes,
        "pareto_dimensions": [
            {"field": field, "direction": "max"} for field in ACCESS_FIELDS],
        "shortlist": frontier,
        "weighted_score": False,
        "network_selected": False,
    }


def engineering_cycle_sensitivity(
        components, *, headway_min: int,
        runtime_multipliers=("0.9", "1.0", "1.1"),
        dwell_per_nonhub_event_min=("0.0", "0.5", "1.0"),
        recovery_minutes=(5, 10, 15)):
    """Apply the inherited deterministic Stage-F grid to closed movements."""
    headway = Decimal(str(headway_min))
    if not headway.is_finite() or headway <= 0 or not components:
        raise ValueError("positive headway and components required")
    parsed = []
    for row in components:
        running = Decimal(str(row["running_minutes_source_model_excludes_dwell"]))
        events = row["nonhub_public_stop_event_count"]
        if (not running.is_finite() or running <= 0 or type(events) is not int
                or events < 0):
            raise ValueError("valid component runtime and event count required")
        parsed.append((row["component_id"], running, events))
    cases = []
    for multiplier_raw in runtime_multipliers:
        multiplier = Decimal(str(multiplier_raw))
        for dwell_raw in dwell_per_nonhub_event_min:
            dwell = Decimal(str(dwell_raw))
            for recovery_raw in recovery_minutes:
                recovery = Decimal(str(recovery_raw))
                if (multiplier <= 0 or dwell < 0 or recovery < 0
                        or not all(value.is_finite()
                                   for value in (multiplier, dwell, recovery))):
                    raise ValueError("invalid engineering sensitivity grid")
                component_rows = []
                for identity, running, event_count in parsed:
                    cycle = running * multiplier + dwell * event_count + recovery
                    fleet = int((cycle / headway).to_integral_value(
                        rounding=ROUND_CEILING))
                    component_rows.append({
                        "component_id": identity,
                        "cycle_minutes_source_model_sensitivity": str(cycle),
                        "minimum_independent_vehicle_count": fleet,
                    })
                cases.append({
                    "runtime_multiplier": str(multiplier),
                    "dwell_per_nonhub_public_stop_event_min": str(dwell),
                    "recovery_minutes": str(recovery),
                    "components": component_rows,
                    "independently_operated_fleet_lower_bound": sum(
                        row["minimum_independent_vehicle_count"]
                        for row in component_rows),
                    "one_vehicle_per_component_sufficient_under_source_model": all(
                        row["minimum_independent_vehicle_count"] == 1
                        for row in component_rows),
                })
    return {
        "cases": cases,
        "case_count": len(cases),
        "all_cases_one_vehicle_per_component": all(
            row["one_vehicle_per_component_sufficient_under_source_model"]
            for row in cases),
        "maximum_independently_operated_fleet_lower_bound": max(
            row["independently_operated_fleet_lower_bound"] for row in cases),
        "sensitivity_is_empirical_probability": False,
        "vehicle_block_plan_certified": False,
    }
