import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_pareto import (
    Objective,
    blocker_labels,
    build_epistemic_audit,
    decision_summary,
    dominance_pairs,
    identify_pareto_frontier,
    identify_robust_pareto_frontier,
    leave_one_objective_out_robustness,
)


def _fixture(rows, *, status="MODEL OUTPUT"):
    objectives = (
        Objective("benefit", "max", "B", "benefit", "unit"),
        Objective("cost", "min", "E", "cost", "unit"),
    )
    enriched = []
    for idx, (sid, benefit, cost, baseline) in enumerate(rows):
        enriched.append(
            {
                "scenario_id": sid,
                "scenario_name": sid,
                "topology_family": "TEST",
                "scenario_epistemic_status": "MODEL OUTPUT",
                "scenario_source": f"TEST_FIXTURE_{idx}",
                "is_baseline": baseline,
                "road_feasible": True,
                "road_feasible__status": "DERIVED",
                "road_feasible__source": "TEST_D",
                "benefit": benefit,
                "benefit__status": status,
                "benefit__source": "TEST_FIXTURE",
                "cost": cost,
                "cost__status": "MODEL OUTPUT",
                "cost__source": "TEST_FIXTURE",
            }
        )
    return pd.DataFrame(enriched), objectives


def test_dominated_scenario_is_not_on_frontier():
    df, objectives = _fixture([("BASE", 1, 5, True), ("DOMINATOR", 2, 4, False), ("TRADEOFF", 3, 8, False)])
    out = identify_pareto_frontier(df, objectives).set_index("scenario_id")
    assert not bool(out.loc["BASE", "pareto_optimal"])
    assert bool(out.loc["DOMINATOR", "pareto_optimal"])
    assert bool(out.loc["TRADEOFF", "pareto_optimal"])
    assert "DOMINATOR" in out.loc["BASE", "dominated_by"]


def test_missing_metric_provenance_is_rejected():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    df.loc[1, "benefit__source"] = ""
    with pytest.raises(ValueError, match="traceable source"):
        identify_pareto_frontier(df, objectives)


def test_invalidated_metric_is_rejected():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    df.loc[1, "cost__status"] = "INVALIDATED"
    with pytest.raises(ValueError, match="Unsupported epistemic status"):
        identify_pareto_frontier(df, objectives)


def test_upstream_blocker_prevents_recommendation():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    out = identify_pareto_frontier(df, objectives)
    summary = decision_summary(out, {"A": "PASS", "B": "IN_PROGRESS", "C": "PASS", "D": "PASS", "E": "PASS"}, objectives)
    assert summary["verdict"] == "PROVISIONAL"
    assert summary["recommended_scenario_id"] is None
    assert summary["dependency_status"] == ["BLOCKED_BY_GATE_B"]


def test_multiple_pareto_options_do_not_create_weighted_winner():
    df, objectives = _fixture([("BASE", 1, 5, True), ("FAST_BUT_COSTLY", 3, 9, False), ("LEAN", 2, 4, False)])
    out = identify_pareto_frontier(df, objectives)
    summary = decision_summary(out, {g: "PASS" for g in "ABCDE"}, objectives)
    assert summary["recommendation_status"] == "NO_SINGLE_WINNER_ROBUST_PARETO_TRADEOFF"
    assert summary["recommended_scenario_id"] is None


def test_leave_one_out_robustness_is_bounded_and_weight_free():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    out = leave_one_objective_out_robustness(df, objectives)
    assert (out["pareto_robustness_count"] <= out["pareto_robustness_runs"]).all()
    assert (out["pareto_robustness_share"].between(0, 1)).all()
    assert not any(col.startswith("score_") for col in out.columns)


def test_blocker_labels_require_all_upstream_gates():
    assert blocker_labels({"A": "PASS", "B": "PASS", "C": "PASS", "D": "PASS", "E": "PASS"}) == []
    assert blocker_labels({"A": "PASS"}) == ["BLOCKED_BY_GATE_B", "BLOCKED_BY_GATE_C", "BLOCKED_BY_GATE_D", "BLOCKED_BY_GATE_E"]


def test_string_false_baseline_is_not_truthy():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    df["is_baseline"] = ["True", "False"]
    out = identify_pareto_frontier(df, objectives)
    assert len(out) == 2


def test_percentage_range_validation():
    objectives = (Objective("population_covered_pct", "max", "B", "coverage", "%"),)
    df, _ = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    df["population_covered_pct"] = [50, 101]
    df["population_covered_pct__status"] = "MODEL OUTPUT"
    df["population_covered_pct__source"] = "TEST"
    with pytest.raises(ValueError, match="between 0 and 100"):
        identify_pareto_frontier(df, objectives)


def test_single_scenario_is_rejected():
    df, objectives = _fixture([("BASE", 1, 5, True)])
    with pytest.raises(ValueError, match="at least two scenarios"):
        identify_pareto_frontier(df, objectives)


def test_road_infeasible_direct_injection_is_rejected():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 9, 1, False)])
    df.loc[df["scenario_id"] == "ALT", "road_feasible"] = False
    with pytest.raises(ValueError, match="Road-infeasible scenarios must be excluded"):
        identify_pareto_frontier(df, objectives)


def test_scenario_names_and_topology_do_not_bias_pareto():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    baseline = identify_pareto_frontier(df, objectives).set_index("scenario_id")["pareto_optimal"].to_dict()
    df.loc[df["scenario_id"] == "BASE", "scenario_name"] = "Raccomandata Pareto Ottimale Figure-8"
    df.loc[df["scenario_id"] == "BASE", "topology_family"] = "FIGURE_8"
    altered = identify_pareto_frontier(df, objectives).set_index("scenario_id")["pareto_optimal"].to_dict()
    assert baseline == altered


def test_row_order_does_not_change_frontier():
    df, objectives = _fixture([("BASE", 1, 5, True), ("A", 2, 4, False), ("B", 3, 8, False)])
    first = identify_pareto_frontier(df, objectives).set_index("scenario_id")["pareto_optimal"].to_dict()
    second = identify_pareto_frontier(df.sample(frac=1, random_state=1), objectives).set_index("scenario_id")["pareto_optimal"].to_dict()
    assert first == second


def test_unbounded_estimate_blocks_definitive_recommendation():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)], status="ESTIMATE")
    point = identify_pareto_frontier(df, objectives)
    summary = decision_summary(point, {g: "PASS" for g in "ABCDE"}, objectives)
    assert summary["verdict"] == "PROVISIONAL"
    assert summary["recommendation_status"] == "NO_DEFINITIVE_RECOMMENDATION_UNCERTAINTY"
    assert summary["recommended_scenario_id"] is None


def test_bounded_nonoverlap_estimate_can_support_unique_robust_dominance():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 4, 2, False)], status="ESTIMATE")
    df["benefit__lower"] = [0.9, 3.5]
    df["benefit__upper"] = [1.1, 4.5]
    robust = identify_robust_pareto_frontier(df, objectives).set_index("scenario_id")
    assert robust.loc["ALT", "robust_pareto_optimal"]
    assert not robust.loc["BASE", "robust_pareto_optimal"]
    point = identify_pareto_frontier(df, objectives)
    summary = decision_summary(point, {g: "PASS" for g in "ABCDE"}, objectives)
    assert summary["recommendation_status"] == "UNIQUE_ROBUST_PARETO_DOMINANT"
    assert summary["recommended_scenario_id"] == "ALT"


def test_overlapping_uncertainty_prevents_false_unique_winner():
    df, objectives = _fixture([("BASE", 2, 5, True), ("ALT", 3, 4, False)], status="ESTIMATE")
    df["benefit__lower"] = [1.0, 2.0]
    df["benefit__upper"] = [3.5, 4.0]
    robust = identify_robust_pareto_frontier(df, objectives)
    assert robust["robust_pareto_optimal"].all()
    point = identify_pareto_frontier(df, objectives)
    summary = decision_summary(point, {g: "PASS" for g in "ABCDE"}, objectives)
    assert summary["recommended_scenario_id"] is None
    assert summary["recommendation_status"] == "NO_SINGLE_WINNER_ROBUST_PARETO_TRADEOFF"


def test_dominance_pairs_are_auditable():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    pairs = dominance_pairs(df, objectives)
    assert len(pairs) == 1
    assert pairs.iloc[0]["dominator_scenario_id"] == "ALT"
    assert pairs.iloc[0]["dominated_scenario_id"] == "BASE"
    assert set(pairs.iloc[0]["strictly_better_objectives"].split(";")) == {"benefit", "cost"}


def test_epistemic_audit_is_long_and_traceable():
    df, objectives = _fixture([("BASE", 1, 5, True), ("ALT", 2, 4, False)])
    audit = build_epistemic_audit(df, objectives)
    assert len(audit) == 4
    assert set(audit["objective"]) == {"benefit", "cost"}
    assert audit["source"].astype(str).str.len().gt(0).all()
