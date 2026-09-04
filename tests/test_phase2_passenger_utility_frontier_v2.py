from scripts.phase2_build_passenger_utility_frontier_v2 import (
    AVAILABILITY_MAX_AXES,
    PASSENGER_MAX_AXES,
    PASSENGER_MIN_AXES,
    dominates,
    optional_min_compare,
    pareto,
    stable_plan_id,
)


def row(plan_id="P", *, max_value=0.5, min_value=30.0, days=260, span=960):
    out = {field: max_value for field in PASSENGER_MAX_AXES}
    out.update({field: min_value for field in PASSENGER_MIN_AXES})
    out.update({"annual_service_days": days, "span_minutes": span, "plan_id": plan_id})
    return out


def test_stable_plan_id_is_deterministic_and_context_sensitive():
    a = stable_plan_id("S1", 30, "CORE_0600_2200", "IDEALISED_5_DAY_52_WEEK")
    b = stable_plan_id("S1", 30, "CORE_0600_2200", "IDEALISED_5_DAY_52_WEEK")
    c = stable_plan_id("S1", 20, "CORE_0600_2200", "IDEALISED_5_DAY_52_WEEK")
    assert a == b
    assert a != c
    assert a.startswith("PU2_")


def test_passenger_dominance_ignores_availability_inside_identical_context():
    better = row("better", max_value=0.6, min_value=20.0, days=260, span=960)
    worse = row("worse", max_value=0.5, min_value=30.0, days=365, span=1110)
    assert dominates(better, worse, include_availability=False)
    assert not dominates(better, worse, include_availability=True)


def test_availability_can_break_equal_passenger_profile_globally():
    more_service = row("more", days=365, span=1110)
    less_service = row("less", days=260, span=960)
    assert not dominates(more_service, less_service, include_availability=False)
    assert dominates(more_service, less_service, include_availability=True)


def test_missing_directional_cost_is_worse_than_finite_cost():
    assert optional_min_compare({"x": 20.0}, {"x": None}, "x") == -1
    assert optional_min_compare({"x": None}, {"x": 20.0}, "x") == 1
    assert optional_min_compare({"x": None}, {"x": None}, "x") == 0


def test_pareto_preserves_equivalent_profiles_instead_of_arbitrary_selection():
    a = row("A")
    b = row("B")
    frontier = pareto([b, a], include_availability=True)
    assert [r["plan_id"] for r in frontier] == ["A", "B"]


def test_pareto_removes_strictly_passenger_dominated_plan():
    best = row("best", max_value=0.7, min_value=20.0)
    dominated = row("dominated", max_value=0.4, min_value=40.0)
    frontier = pareto([dominated, best], include_availability=True)
    assert [r["plan_id"] for r in frontier] == ["best"]


def test_axis_partition_keeps_resource_metrics_out_of_passenger_utility():
    forbidden = {
        "annual_bus_km",
        "public_route_count",
        "public_explicit_field_check_pending_count",
        "public_operational_unknown_distance_share_lower_bound",
    }
    assert forbidden.isdisjoint(PASSENGER_MAX_AXES)
    assert forbidden.isdisjoint(PASSENGER_MIN_AXES)
    assert set(AVAILABILITY_MAX_AXES) == {"annual_service_days", "span_minutes"}
