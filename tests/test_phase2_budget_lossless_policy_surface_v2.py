import math

from scripts.phase2_build_budget_lossless_policy_surface_v2 import (
    classify_budget,
    exact_departure_bounds,
)


def test_extended_h20_has_exact_55_or_56_departures():
    assert exact_departure_bounds(1110, 20) == (55, 56)


def test_extended_h60_has_exact_18_or_19_departures():
    assert exact_departure_bounds(1110, 60) == (18, 19)


def test_integer_span_has_identical_min_max_departures():
    assert exact_departure_bounds(960, 15) == (64, 64)
    assert exact_departure_bounds(960, 20) == (48, 48)
    assert exact_departure_bounds(960, 30) == (32, 32)
    assert exact_departure_bounds(960, 60) == (16, 16)


def test_some_phase_budget_feasible_is_retained_class():
    assert classify_budget(exact_min=100.0, exact_max=110.0, cap=105.0) == "SOME_PHASES_BUDGET_FEASIBLE"


def test_all_phase_budget_feasible_class():
    assert classify_budget(exact_min=100.0, exact_max=110.0, cap=110.0) == "ALL_PHASES_BUDGET_FEASIBLE"


def test_no_phase_budget_feasible_class():
    assert classify_budget(exact_min=100.01, exact_max=110.0, cap=100.0) == "NO_PHASE_BUDGET_FEASIBLE"


def test_continuous_filter_can_reject_exact_phase_feasible_context():
    # H60 extended: continuous is 18.5 pattern sets/day, exact minimum is 18.
    distance = 20.0
    days = 365
    exact_min = distance * 18 * days
    exact_max = distance * 19 * days
    continuous = distance * 18.5 * days
    cap = exact_min + 0.25 * (exact_max - exact_min)
    assert exact_min < cap < continuous < exact_max
    assert classify_budget(exact_min=exact_min, exact_max=exact_max, cap=cap) == "SOME_PHASES_BUDGET_FEASIBLE"


def test_exact_minimum_is_jointly_achievable_with_independent_route_phases():
    # For two routes, each route can independently choose a floor-count phase.
    distances = (7.5, 12.5)
    floor_count, ceil_count = exact_departure_bounds(1110, 60)
    aggregate_min = sum(d * floor_count for d in distances)
    aggregate_max = sum(d * ceil_count for d in distances)
    assert math.isclose(aggregate_min, 20.0 * 18)
    assert math.isclose(aggregate_max, 20.0 * 19)


def test_invalid_budget_values_fail_closed():
    try:
        classify_budget(exact_min=float("nan"), exact_max=1.0, cap=1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("non-finite budget input must fail closed")
