from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.gate_f_pareto import Objective, blocker_labels, decision_summary, identify_pareto_frontier, leave_one_objective_out_robustness


def _fixture(rows):
    objectives = (Objective("benefit", "max", "B", "benefit"), Objective("cost", "min", "E", "cost"))
    enriched = []
    for idx, (sid, benefit, cost, baseline) in enumerate(rows):
        enriched.append({
            "scenario_id": sid,
            "scenario_name": sid,
            "scenario_epistemic_status": "MODEL OUTPUT",
            "scenario_source": f"TEST_FIXTURE_{idx}",
            "is_baseline": baseline,
            "benefit": benefit,
            "benefit__status": "MODEL OUTPUT",
            "benefit__source": "TEST_FIXTURE",
            "cost": cost,
            "cost__status": "MODEL OUTPUT",
            "cost__source": "TEST_FIXTURE",
        })
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
    assert summary["recommendation_status"] == "NO_SINGLE_WINNER_PARETO_TRADEOFF"
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
