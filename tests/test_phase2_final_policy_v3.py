from __future__ import annotations

from decimal import Decimal

from scripts.phase2_dry_run_final_policy_v3 import dominates, pareto_rows, strict_lexicographic_trace


def row(**overrides):
    base = {
        "plan_context_id": "P",
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
