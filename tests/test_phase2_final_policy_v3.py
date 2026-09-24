from __future__ import annotations

from scripts.phase2_dry_run_final_policy_v3 import (
    dominates,
    h60_exception_test,
    pareto_rows,
    strict_lexicographic_trace,
)


def row(**overrides):
    base = {
        "plan_context_id": "P",
        "selected_timetable_id": "T",
        "stage_e_any_block_infeasibility_under_sensitivity": "false",
        "public_population_coverage_share_10min": "0.70",
        "public_population_coverage_share_8min": "0.60",
        "public_population_coverage_share_5min": "0.50",
        "public_worst_municipality_coverage_share_10min": "0.40",
        "public_worst_municipality_coverage_share_8min": "0.30",
        "public_worst_municipality_coverage_share_5min": "0.20",
        "uniform_headway_min": "30",
        "span_minutes": "900",
        "annual_service_days": "300",
        "bidirectional_reachable_share": "0.50",
        "stage_e_bidirectional_worst_retention_share_engineering": "0.80",
        "exact_annual_bus_km": "100000",
        "public_explicit_field_check_pending_count": "2",
    }
    base.update(overrides)
    return base


def territorial_dims():
    return [
        {"field": "public_population_coverage_share_10min", "direction": "max", "dimension_group": "TOTAL"},
        {"field": "public_population_coverage_share_8min", "direction": "max", "dimension_group": "TOTAL"},
        {"field": "public_population_coverage_share_5min", "direction": "max", "dimension_group": "TOTAL"},
        {"field": "public_worst_municipality_coverage_share_10min", "direction": "max", "dimension_group": "EQUITY"},
        {"field": "public_worst_municipality_coverage_share_8min", "direction": "max", "dimension_group": "EQUITY"},
        {"field": "public_worst_municipality_coverage_share_5min", "direction": "max", "dimension_group": "EQUITY"},
    ]


def test_useful_service_pareto_preserves_coverage_frequency_tradeoff():
    dims = [
        {"field": "public_population_coverage_share_10min", "direction": "max"},
        {"field": "uniform_headway_min", "direction": "min"},
    ]
    high_coverage_hourly = row(plan_context_id="H60", public_population_coverage_share_10min="0.80", uniform_headway_min="60")
    lower_coverage_halfhour = row(plan_context_id="H30", public_population_coverage_share_10min="0.70", uniform_headway_min="30")
    survivors = pareto_rows([high_coverage_hourly, lower_coverage_halfhour], dims)
    assert {item["plan_context_id"] for item in survivors} == {"H60", "H30"}


def test_dominated_service_is_removed_without_weights():
    dims = [
        {"field": "public_population_coverage_share_10min", "direction": "max"},
        {"field": "uniform_headway_min", "direction": "min"},
    ]
    better = row(plan_context_id="A", public_population_coverage_share_10min="0.80", uniform_headway_min="30")
    worse = row(plan_context_id="B", public_population_coverage_share_10min="0.70", uniform_headway_min="60")
    assert dominates(better, worse, dims)
    assert [item["plan_context_id"] for item in pareto_rows([better, worse], dims)] == ["A"]


def test_h60_does_not_override_frequent_for_coverage_only_gain():
    frequent = [row(plan_context_id="H30", selected_timetable_id="T30")]
    hourly = [row(
        plan_context_id="H60", selected_timetable_id="T60", uniform_headway_min="60",
        public_population_coverage_share_10min="0.80",
        public_population_coverage_share_8min="0.70",
        public_population_coverage_share_5min="0.60",
        public_worst_municipality_coverage_share_10min="0.39",
    )]
    _audit, qualifying = h60_exception_test(frequent, hourly, territorial_dims())
    assert qualifying == []


def test_h60_exception_requires_broad_total_and_equity_superiority():
    frequent = [row(plan_context_id="H30", selected_timetable_id="T30")]
    hourly = [row(
        plan_context_id="H60", selected_timetable_id="T60", uniform_headway_min="60",
        public_population_coverage_share_10min="0.80",
        public_population_coverage_share_8min="0.70",
        public_population_coverage_share_5min="0.60",
        public_worst_municipality_coverage_share_10min="0.50",
        public_worst_municipality_coverage_share_8min="0.40",
        public_worst_municipality_coverage_share_5min="0.30",
    )]
    audit, qualifying = h60_exception_test(frequent, hourly, territorial_dims())
    assert [item["plan_context_id"] for item in qualifying] == ["H60"]
    assert audit[0]["h60_exception_pass"] == "true"


def test_h60_must_beat_componentwise_best_across_multiple_frequent_frontier_rows():
    frequent = [
        row(plan_context_id="F1", public_population_coverage_share_10min="0.80", public_worst_municipality_coverage_share_10min="0.30"),
        row(plan_context_id="F2", public_population_coverage_share_10min="0.70", public_worst_municipality_coverage_share_10min="0.50"),
    ]
    hourly = [row(
        plan_context_id="H60", selected_timetable_id="T60", uniform_headway_min="60",
        public_population_coverage_share_10min="0.79",
        public_worst_municipality_coverage_share_10min="0.55",
    )]
    _audit, qualifying = h60_exception_test(frequent, hourly, territorial_dims())
    assert qualifying == []


def test_strict_lexicographic_trace_exposes_exact_brittleness():
    criteria = [
        {"field": "public_population_coverage_share_10min", "direction": "max"},
        {"field": "uniform_headway_min", "direction": "min"},
    ]
    a = row(plan_context_id="A", public_population_coverage_share_10min="0.700000001", uniform_headway_min="60")
    b = row(plan_context_id="B", public_population_coverage_share_10min="0.700000000", uniform_headway_min="30")
    trace, survivors = strict_lexicographic_trace([a, b], criteria)
    assert trace[0]["survivor_count"] == 1
    assert survivors[0]["plan_context_id"] == "A"


def test_block_infeasibility_is_numeric_boolean_for_policy_comparison():
    dims = [{"field": "stage_e_any_block_infeasibility_under_sensitivity", "direction": "min"}]
    robust = row(plan_context_id="R", stage_e_any_block_infeasibility_under_sensitivity="false")
    fragile = row(plan_context_id="F", stage_e_any_block_infeasibility_under_sensitivity="true")
    assert dominates(robust, fragile, dims)


def test_equivalent_metric_vectors_all_survive():
    dims = [{"field": "public_population_coverage_share_10min", "direction": "max"}]
    a = row(plan_context_id="A")
    b = row(plan_context_id="B")
    assert {item["plan_context_id"] for item in pareto_rows([a, b], dims)} == {"A", "B"}
