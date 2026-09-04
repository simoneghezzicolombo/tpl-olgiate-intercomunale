#!/usr/bin/env python3
"""Targeted preflight red-team for Alpha's exact GJT set-bounds work.

This is deliberately narrow. It does NOT compute candidate GJT, rank networks, or
create a new Phase-2 blocker. It verifies that the historical 243-case feeder-GFA
parameter grid can be reused only as monotone assumption-sensitivity axes for an
exact-timetable generalized-cost *bound* calculation, while explicitly forbidding
inheritance of the historical H/2 waiting assumption.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

STATUS = "PASS_PHASE2_GJT_BOUNDS_TARGETED_PRECHECK_A"
CONTRACT = "PHASE2_GJT_BOUNDS_MONOTONE_CORNER_ENVELOPE_PRECHECK_A"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def exact_cost(params: dict[str, float], itinerary: dict[str, float]) -> float:
    """Exact-timetable generalized cost used only for the monotonicity oracle.

    Origin waiting is intentionally absent. ``exact_transfer_wait`` is a supplied
    non-negative exact timetable component, not H/2 and not an empirical expected
    waiting distribution.
    """
    return (
        params["bus_ivt_weight"] * itinerary["bus_ivt"]
        + params["walk_weight"]
        * (itinerary["access_walk"] + params["station_transfer_walk_min"])
        + params["wait_weight"] * itinerary["exact_transfer_wait"]
        + params["transfer_penalty_min"]
    )


def product_grid(grid: dict[str, list[float]]) -> list[dict[str, float]]:
    keys = [
        "bus_ivt_weight",
        "walk_weight",
        "wait_weight",
        "transfer_penalty_min",
        "station_transfer_walk_min",
    ]
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(grid[key] for key in keys))
    ]


def corner(grid: dict[str, list[float]], which: str) -> dict[str, float]:
    fn = min if which == "min" else max
    return {key: float(fn(values)) for key, values in grid.items()}


def unit_best(params: dict[str, float], itineraries: list[dict[str, float]]) -> float:
    return min(exact_cost(params, itinerary) for itinerary in itineraries)


def municipal_bounds(
    params: dict[str, float],
    units: list[list[dict[str, float]]],
) -> tuple[float, float]:
    best_by_unit = [unit_best(params, itineraries) for itineraries in units]
    return min(best_by_unit), max(best_by_unit)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()

    cfg = read_json(args.config)
    if cfg.get("contract") != "PHASE2_FEEDER_GENERALIZED_ACCESS_SENSITIVITY_V2":
        raise ValueError("Unexpected feeder-GFA sensitivity contract")
    if cfg.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("Historical grid must remain assumption sensitivity, not empirical interval")

    waiting = cfg.get("waiting_assumption", {})
    historical_h2_present = "HALF_HEADWAY" in str(waiting.get("rule", "")).upper() or "uniform_headway/2" in str(cfg.get("formula", ""))
    if not historical_h2_present:
        raise ValueError("Expected historical H/2 assumption was not found; contract drift requires re-audit")
    if waiting.get("exact_s8_phase_used") is not False:
        raise ValueError("Historical feeder-GFA grid unexpectedly claims exact S8 phase")

    grid = cfg.get("parameter_grid", {})
    required = {
        "bus_ivt_weight",
        "walk_weight",
        "wait_weight",
        "transfer_penalty_min",
        "station_transfer_walk_min",
    }
    if set(grid) != required:
        raise ValueError(f"Unexpected parameter grid keys: {sorted(grid)}")
    if any(not values for values in grid.values()):
        raise ValueError("Empty sensitivity axis")
    if any(float(value) < 0 for values in grid.values() for value in values):
        raise ValueError("Negative parameter breaks the certified monotone precondition")

    cases = product_grid(grid)
    expected = int(cfg.get("expected_full_factorial_case_count", -1))
    if len(cases) != expected or expected != 243:
        raise ValueError(f"Expected 243 historical cases, got {len(cases)} / declared {expected}")

    # Deterministic oracle fixtures intentionally allow the best itinerary to switch
    # as coefficients change. This tests the stronger property needed by Alpha:
    # pointwise minimum over a coefficient-independent feasible itinerary set remains
    # coordinate-wise non-decreasing when every itinerary cost is non-decreasing.
    units = [
        [
            {"bus_ivt": 18.0, "access_walk": 2.0, "exact_transfer_wait": 3.0},
            {"bus_ivt": 12.0, "access_walk": 7.0, "exact_transfer_wait": 1.0},
        ],
        [
            {"bus_ivt": 8.0, "access_walk": 10.0, "exact_transfer_wait": 0.0},
            {"bus_ivt": 20.0, "access_walk": 1.0, "exact_transfer_wait": 5.0},
        ],
        [
            {"bus_ivt": 14.0, "access_walk": 4.0, "exact_transfer_wait": 2.0},
            {"bus_ivt": 9.0, "access_walk": 8.0, "exact_transfer_wait": 4.0},
        ],
    ]
    if any(component < 0 for unit in units for itinerary in unit for component in itinerary.values()):
        raise ValueError("Oracle fixture contains a negative generalized-cost component")

    low = corner(grid, "min")
    high = corner(grid, "max")
    low_bounds = municipal_bounds(low, units)
    high_bounds = municipal_bounds(high, units)

    all_bounds = [municipal_bounds(params, units) for params in cases]
    brute_lower_min = min(item[0] for item in all_bounds)
    brute_lower_max = max(item[0] for item in all_bounds)
    brute_upper_min = min(item[1] for item in all_bounds)
    brute_upper_max = max(item[1] for item in all_bounds)

    tol = 1e-12
    checks = {
        "lower_envelope_min_at_low_corner": abs(brute_lower_min - low_bounds[0]) <= tol,
        "lower_envelope_max_at_high_corner": abs(brute_lower_max - high_bounds[0]) <= tol,
        "upper_envelope_min_at_low_corner": abs(brute_upper_min - low_bounds[1]) <= tol,
        "upper_envelope_max_at_high_corner": abs(brute_upper_max - high_bounds[1]) <= tol,
    }
    if not all(checks.values()):
        raise ValueError(f"Two-corner oracle failed: {checks}")

    payload = {
        "status": STATUS,
        "contract": CONTRACT,
        "precheck_pass": True,
        "historical_grid_case_count": len(cases),
        "historical_grid_is_empirical_interval": False,
        "historical_h2_present": True,
        "historical_h2_authorized_for_exact_bounds": False,
        "origin_waiting_estimated_by_this_precheck": False,
        "exact_transfer_wait_may_be_used_as_nonnegative_component": True,
        "station_transfer_walk_is_additive_component_not_coefficient": True,
        "two_corner_envelope_exact_under_preconditions": True,
        "preconditions": {
            "all_generalized_cost_components_nonnegative": True,
            "all_varying_axes_coordinatewise_nonnegative": True,
            "feasible_itinerary_set_independent_of_gfa_coefficients": True,
            "no_coefficient_dependent_threshold_or_pruning": True,
        },
        "oracle": {
            "full_factorial_cases_checked": len(cases),
            "unit_count": len(units),
            "itineraries_per_unit": [len(unit) for unit in units],
            "checks": checks,
        },
        "epistemic_guards": {
            "worker_allocation_performed": False,
            "resident_population_used_as_demand": False,
            "departure_time_distribution_imputed": False,
            "full_expected_gjt_claimed": False,
            "ranking_or_selection_performed": False,
        },
        "final_alpha_exact_builder_review_pending": True,
        "decision_boundary": "PRECHECK_ONLY_NOT_A_NEW_PHASE2_BLOCKER_AND_NOT_FINAL_GJT_BOUNDS_CERTIFICATION",
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
