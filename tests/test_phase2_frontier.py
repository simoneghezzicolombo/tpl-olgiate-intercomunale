"""Tests for Phase 2 frontier preservation.

All values are TEST_FIXTURE_ONLY and are not territorial evidence.
"""
from src.phase2_frontier import apply_robustness_floor, non_dominated_frontier
from src.phase2_optimizer_core import RobustScenarioEvaluation


def _row(
    scenario_id,
    median,
    lower,
    missed,
    km,
    *,
    eligible=True,
    complexity=2,
    unverified=0,
    retained=1.0,
):
    return RobustScenarioEvaluation(
        scenario_id=scenario_id,
        eligible=eligible,
        median_gjt_improvement_min=median,
        lower_quantile_gjt_improvement_min=lower,
        median_missed_connection_probability=missed,
        annual_bus_km=km,
        public_pattern_complexity=complexity,
        unverified_elements=unverified,
        retained_existing_stops_share=retained,
        n_sensitivity_runs=10,
    )


def test_dominated_candidate_is_removed_without_weighted_score():
    strong = _row("A", 5.0, 3.0, 0.05, 90_000)
    dominated = _row("B", 4.0, 2.0, 0.10, 100_000)
    frontier = non_dominated_frontier([dominated, strong])
    assert [row.scenario_id for row in frontier] == ["A"]


def test_true_tradeoff_is_preserved():
    utility = _row("UTILITY", 6.0, 3.5, 0.08, 105_000)
    economy = _row("ECONOMY", 4.5, 3.0, 0.04, 80_000)
    frontier = non_dominated_frontier([utility, economy])
    assert {row.scenario_id for row in frontier} == {"UTILITY", "ECONOMY"}


def test_ineligible_candidate_never_enters_frontier():
    ineligible = _row("BAD", 100.0, 100.0, 0.0, 1.0, eligible=False)
    valid = _row("VALID", 1.0, 0.5, 0.1, 100_000)
    assert [row.scenario_id for row in non_dominated_frontier([ineligible, valid])] == ["VALID"]


def test_simplicity_is_not_silently_promoted_to_pareto_objective():
    complex_but_equal = _row("A", 5.0, 3.0, 0.05, 90_000, complexity=10)
    simple_but_equal = _row("B", 5.0, 3.0, 0.05, 90_000, complexity=1)
    frontier = non_dominated_frontier([complex_but_equal, simple_but_equal])
    assert {row.scenario_id for row in frontier} == {"A", "B"}


def test_declared_robustness_floor_removes_fragile_candidate():
    stable = _row("STABLE", 4.0, 1.0, 0.05, 90_000)
    fragile = _row("FRAGILE", 7.0, -2.0, 0.05, 90_000)
    screened = apply_robustness_floor(
        [stable, fragile],
        minimum_lower_quantile_gjt_improvement_min=0.0,
    )
    assert [row.scenario_id for row in screened] == ["STABLE"]
