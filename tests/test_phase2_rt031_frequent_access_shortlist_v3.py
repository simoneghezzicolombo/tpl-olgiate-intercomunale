from src.phase2_rt031_frequent_access_shortlist_v3 import (
    engineering_cycle_sensitivity,
    select_frequent_access_frontier,
)


def candidate(identity, ratios, *, within=True, headway=30, span=720):
    return {
        "portfolio_id": identity,
        "exact_access_ratios": [str(value) for value in ratios],
        "service_surface": [{
            "uniform_headway_min_per_movement": headway,
            "span_minutes": span,
            "within_approved_reference_cap": within,
        }],
    }


def test_exact_frontier_keeps_incomparable_profiles_and_removes_dominated():
    rows = [
        candidate("balanced", [3, 3, 3, 3, 3, 3]),
        candidate("total", [4, 4, 4, 2, 2, 2]),
        candidate("dominated", [2, 2, 2, 2, 2, 2]),
    ]
    result = select_frequent_access_frontier(
        rows, current_exact_ratios=[1] * 6, headway_min=30, span_minutes=720)
    assert result["eligible_benchmark_improvement_count"] == 3
    assert [row["portfolio_id"] for row in result["shortlist"]] == [
        "balanced", "total"]
    assert result["weighted_score"] is False
    assert result["network_selected"] is False


def test_budget_and_requested_service_context_are_hard_filters():
    rows = [
        candidate("inside", [2] * 6),
        candidate("over", [9] * 6, within=False),
    ]
    result = select_frequent_access_frontier(
        rows, current_exact_ratios=[1] * 6, headway_min=30, span_minutes=720)
    assert [row["portfolio_id"] for row in result["shortlist"]] == ["inside"]


def test_no_benchmark_regression_is_admitted():
    rows = [candidate("tradeoff", [2, 2, 2, 2, 2, 0])]
    result = select_frequent_access_frontier(
        rows, current_exact_ratios=[1] * 6, headway_min=30, span_minutes=720)
    assert result["eligible_benchmark_improvement_count"] == 0
    assert result["shortlist"] == []


def test_engineering_grid_preserves_dwell_runtime_and_recovery_axes():
    result = engineering_cycle_sensitivity([
        {"component_id": "a", "running_minutes_source_model_excludes_dwell": "15",
         "nonhub_public_stop_event_count": 10},
        {"component_id": "b", "running_minutes_source_model_excludes_dwell": "20",
         "nonhub_public_stop_event_count": 5},
    ], headway_min=30)
    assert result["case_count"] == 27
    nominal = next(row for row in result["cases"]
                   if row["runtime_multiplier"] == "1.0"
                   and row["dwell_per_nonhub_public_stop_event_min"] == "0.5"
                   and row["recovery_minutes"] == "5")
    assert nominal["independently_operated_fleet_lower_bound"] == 2
    stressed = next(row for row in result["cases"]
                    if row["runtime_multiplier"] == "1.1"
                    and row["dwell_per_nonhub_public_stop_event_min"] == "1.0"
                    and row["recovery_minutes"] == "15")
    assert stressed["independently_operated_fleet_lower_bound"] == 4
    assert result["all_cases_one_vehicle_per_component"] is False
    assert result["sensitivity_is_empirical_probability"] is False
