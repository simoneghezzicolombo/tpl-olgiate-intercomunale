"""Tests for final topology+service candidate identity and ranking.

All values are TEST_FIXTURE_ONLY and are not territorial evidence.
"""
import pytest

from src.phase2_candidate_tournament import (
    CandidateEvaluation,
    CandidateKey,
    CandidateSensitivityResult,
    aggregate_candidate_evaluation,
    candidate_budget_frontier,
    candidate_frontier,
    select_candidates,
)
from src.phase2_optimizer_core import HardConstraintResult


def _eval(scenario, plan, median, lower, missed, km, *, eligible=True, complexity=2):
    return CandidateEvaluation(
        key=CandidateKey(scenario, plan),
        eligible=eligible,
        median_gjt_improvement_min=median,
        lower_quantile_gjt_improvement_min=lower,
        median_missed_connection_probability=missed,
        annual_bus_km=km,
        public_pattern_complexity=complexity,
        unverified_elements=0,
        retained_existing_stops_share=1.0,
        n_sensitivity_runs=10,
    )


def test_same_topology_different_service_plans_have_distinct_candidate_ids():
    a = CandidateKey("SCENARIO", "PLAN_20_MIN")
    b = CandidateKey("SCENARIO", "PLAN_40_MIN")
    assert a.candidate_id != b.candidate_id
    assert a.candidate_id == CandidateKey("SCENARIO", "PLAN_20_MIN").candidate_id


def test_aggregation_filters_by_both_scenario_and_plan():
    key_a = CandidateKey("S", "P1")
    key_b = CandidateKey("S", "P2")
    rows = [
        CandidateSensitivityResult(key_a, "LOW", 2.0, 0.0, 0.1),
        CandidateSensitivityResult(key_a, "HIGH", 6.0, 0.0, 0.2),
        CandidateSensitivityResult(key_b, "LOW", 100.0, 0.0, 0.0),
    ]
    result = aggregate_candidate_evaluation(
        key=key_a,
        hard_constraints=HardConstraintResult(True, True, True, True, True, True),
        sensitivity_results=rows,
        annual_bus_km=100_000,
        public_pattern_complexity=2,
        unverified_elements=0,
        retained_existing_stops_share=1.0,
    )
    assert result.median_gjt_improvement_min == pytest.approx(4.0)
    assert result.n_sensitivity_runs == 2


def test_duplicate_sensitivity_id_for_same_candidate_fails_closed():
    key = CandidateKey("S", "P")
    rows = [
        CandidateSensitivityResult(key, "A", 1.0, 0.0, 0.1),
        CandidateSensitivityResult(key, "A", 2.0, 0.0, 0.1),
    ]
    with pytest.raises(ValueError, match="Duplicate sensitivity_id"):
        aggregate_candidate_evaluation(
            key=key,
            hard_constraints=HardConstraintResult(True, True, True, True, True, True),
            sensitivity_results=rows,
            annual_bus_km=100_000,
            public_pattern_complexity=2,
            unverified_elements=0,
            retained_existing_stops_share=1.0,
        )


def test_non_finite_sensitivity_metrics_fail_closed():
    key = CandidateKey("S", "P")
    with pytest.raises(ValueError, match="must be finite"):
        CandidateSensitivityResult(key, "A", float("nan"), 0.0, 0.1)
    with pytest.raises(ValueError, match="must be finite"):
        CandidateSensitivityResult(key, "A", 1.0, float("inf"), 0.1)
    with pytest.raises(ValueError, match="must be finite"):
        CandidateSensitivityResult(key, "A", 1.0, 0.0, float("nan"))


def test_non_finite_candidate_metrics_fail_closed():
    with pytest.raises(ValueError, match="must be finite"):
        _eval("S", "P", float("nan"), 1.0, 0.1, 90_000)
    with pytest.raises(ValueError, match="must be finite"):
        _eval("S", "P", 2.0, float("inf"), 0.1, 90_000)
    with pytest.raises(ValueError, match="must be finite"):
        _eval("S", "P", 2.0, 1.0, 0.1, float("inf"))


def test_selection_can_choose_between_two_plans_on_same_topology():
    fast = _eval("LOOP", "FAST", 6.0, 3.0, 0.08, 110_000, complexity=2)
    slow = _eval("LOOP", "SLOW", 5.9, 3.5, 0.02, 90_000, complexity=2)
    other = _eval("RADIAL", "BASE", 4.0, 3.0, 0.01, 80_000, complexity=1)
    selection = select_candidates([fast, slow, other], uncertainty_band_min=0.2)
    assert selection.tie_break_invoked is True
    assert selection.primary.key == CandidateKey("LOOP", "SLOW")
    assert selection.runner_up is not None
    assert selection.runner_up.key == CandidateKey("LOOP", "FAST")


def test_uncertainty_band_must_be_finite():
    valid = _eval("S", "P", 2.0, 1.0, 0.1, 90_000)
    with pytest.raises(ValueError, match="must be finite"):
        select_candidates([valid], uncertainty_band_min=float("nan"))


def test_ineligible_plan_on_good_topology_cannot_win():
    bad = _eval("S", "INFEASIBLE_FAST", 100.0, 90.0, 0.0, 50_000, eligible=False)
    valid = _eval("S", "VALID", 2.0, 1.0, 0.1, 90_000)
    selection = select_candidates([bad, valid], uncertainty_band_min=0.5)
    assert selection.primary.key.plan_id == "VALID"


def test_candidate_frontier_preserves_real_service_tradeoffs():
    utility = _eval("S", "HIGH_FREQ", 6.0, 4.0, 0.05, 120_000)
    economy = _eval("S", "LOW_FREQ", 4.5, 3.0, 0.03, 80_000)
    dominated = _eval("X", "BAD", 3.0, 2.0, 0.10, 100_000)
    frontier = candidate_frontier([utility, economy, dominated])
    assert {row.key.plan_id for row in frontier} == {"HIGH_FREQ", "LOW_FREQ"}


def test_frontier_tolerance_must_be_finite():
    valid = _eval("S", "P", 2.0, 1.0, 0.1, 90_000)
    with pytest.raises(ValueError, match="must be finite"):
        candidate_frontier([valid], tolerance=float("nan"))


def test_budget_frontier_reports_plan_identity_not_only_topology():
    low = _eval("S", "LOW", 2.0, 1.0, 0.1, 80_000)
    mid = _eval("S", "MID", 4.0, 2.0, 0.1, 100_000)
    high = _eval("S", "HIGH", 5.0, 3.0, 0.1, 120_000)
    rows = candidate_budget_frontier([low, mid, high], [90_000, 110_000, 130_000])
    assert [row["plan_id"] for row in rows] == ["LOW", "MID", "HIGH"]
    assert rows[1]["scenario_id"] == "S"
    assert rows[1]["candidate_id"] == mid.candidate_id


def test_budget_frontier_does_not_silently_drop_invalid_envelopes():
    valid = _eval("S", "P", 2.0, 1.0, 0.1, 90_000)
    with pytest.raises(ValueError):
        candidate_budget_frontier([valid], [90_000, float("nan")])
    with pytest.raises(ValueError, match="positive"):
        candidate_budget_frontier([valid], [90_000, -1])
