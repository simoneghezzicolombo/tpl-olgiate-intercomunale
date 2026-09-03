"""Tests for the final Phase 2 tournament materialiser.

All candidate values are TEST_FIXTURE_ONLY. Tests use temporary files only and
never create Phase 2 territorial outputs in the repository.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.phase2_finalize_tournament import build_parser, finalise, load_candidates


CANDIDATE_FIELDS = [
    "scenario_id",
    "plan_id",
    "eligible",
    "median_gjt_improvement_min",
    "lower_quantile_gjt_improvement_min",
    "median_missed_connection_probability",
    "annual_bus_km",
    "public_pattern_complexity",
    "unverified_elements",
    "retained_existing_stops_share",
    "n_sensitivity_runs",
]


def _write_candidates(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_budgets(path: Path):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["annual_bus_km_cap"])
        writer.writeheader()
        for value in (90_000, 110_000, 130_000):
            writer.writerow({"annual_bus_km_cap": value})


def _row(scenario, plan, median, missed, km, *, eligible=True, complexity=2):
    return {
        "scenario_id": scenario,
        "plan_id": plan,
        "eligible": str(eligible).lower(),
        "median_gjt_improvement_min": median,
        "lower_quantile_gjt_improvement_min": float(median) - 1.0 if str(median).lower() not in {"nan", "inf", "-inf"} else median,
        "median_missed_connection_probability": missed,
        "annual_bus_km": km,
        "public_pattern_complexity": complexity,
        "unverified_elements": 0,
        "retained_existing_stops_share": 1.0,
        "n_sensitivity_runs": 10,
    }


def test_finalise_writes_required_phase2_decision_artifacts(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    out = tmp_path / "out"
    _write_candidates(
        candidates,
        [
            _row("LOOP", "FAST", 6.0, 0.08, 108_000),
            _row("LOOP", "SLOW", 5.9, 0.02, 90_000),
            _row("RADIAL", "BASE", 4.0, 0.01, 80_000),
        ],
    )
    _write_budgets(budgets)

    result = finalise(
        candidates_path=candidates,
        budget_path=budgets,
        output_dir=out,
        uncertainty_band_min=0.2,
        decision_budget_km=110_000,
    )

    assert result["primary"]["scenario_id"] == "LOOP"
    assert result["primary"]["plan_id"] == "SLOW"
    assert result["runner_up"]["plan_id"] == "FAST"
    assert result["tie_break_invoked"] is True
    assert result["decision_rule"]["weighted_composite_score"] is False
    assert result["decision_rule"]["implicit_budget_default"] is False
    assert result["decision_budget_bus_km_year"] == 110_000
    assert result["decision_budget_contract"] == "EXPLICIT_CALLER_DECLARED_MATCHED_TO_MATERIALISED_ENVELOPE"

    for filename in (
        "frontier.csv",
        "budget_utility_curve.csv",
        "finalists.csv",
        "final_recommendation.json",
    ):
        assert (out / filename).exists()

    recommendation = json.loads((out / "final_recommendation.json").read_text(encoding="utf-8"))
    assert recommendation["primary"]["candidate_id"] == result["primary"]["candidate_id"]
    assert len(recommendation["input_lineage"]["candidate_evaluations_sha256"]) == 64
    assert len(recommendation["input_lineage"]["budget_envelopes_sha256"]) == 64


def test_decision_budget_filters_expensive_candidate_before_selection(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(
        candidates,
        [
            _row("EXPENSIVE", "P", 100.0, 0.0, 120_000),
            _row("AFFORDABLE", "P", 3.0, 0.1, 90_000),
        ],
    )
    _write_budgets(budgets)
    result = finalise(
        candidates_path=candidates,
        budget_path=budgets,
        output_dir=tmp_path / "out",
        uncertainty_band_min=0.0,
        decision_budget_km=110_000,
    )
    assert result["primary"]["scenario_id"] == "AFFORDABLE"
    assert result["eligible_candidates_within_decision_budget"] == 1


def test_decision_budget_is_required_and_has_no_max_envelope_fallback(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(candidates, [_row("S", "P", 3.0, 0.1, 90_000)])
    _write_budgets(budgets)
    with pytest.raises(ValueError, match="decision_budget_km is required"):
        finalise(
            candidates_path=candidates,
            budget_path=budgets,
            output_dir=tmp_path / "out",
            uncertainty_band_min=0.1,
            decision_budget_km=None,
        )


def test_cli_requires_decision_budget(tmp_path):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--candidates", str(tmp_path / "candidates.csv"),
                "--budgets", str(tmp_path / "budgets.csv"),
                "--uncertainty-band-min", "0.1",
            ]
        )


def test_decision_budget_must_match_materialised_envelope(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(candidates, [_row("S", "P", 3.0, 0.1, 90_000)])
    _write_budgets(budgets)
    with pytest.raises(ValueError, match="must match exactly one declared budget envelope"):
        finalise(
            candidates_path=candidates,
            budget_path=budgets,
            output_dir=tmp_path / "out",
            uncertainty_band_min=0.1,
            decision_budget_km=100_000,
        )


def test_decision_budget_rejects_negative_and_non_finite_values(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(candidates, [_row("S", "P", 3.0, 0.1, 90_000)])
    _write_budgets(budgets)
    for bad in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            finalise(
                candidates_path=candidates,
                budget_path=budgets,
                output_dir=tmp_path / "out",
                uncertainty_band_min=0.1,
                decision_budget_km=bad,
            )


def test_budget_match_tolerates_only_numeric_roundoff(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(candidates, [_row("S", "P", 3.0, 0.1, 90_000)])
    _write_budgets(budgets)
    result = finalise(
        candidates_path=candidates,
        budget_path=budgets,
        output_dir=tmp_path / "out",
        uncertainty_band_min=0.1,
        decision_budget_km=110_000.00000001,
    )
    assert result["decision_budget_bus_km_year"] == 110_000


def test_duplicate_topology_plan_rows_fail_closed(tmp_path):
    candidates = tmp_path / "candidates.csv"
    same = _row("S", "P", 3.0, 0.1, 90_000)
    _write_candidates(candidates, [same, same])
    with pytest.raises(ValueError, match="duplicate scenario_id \+ plan_id"):
        load_candidates(candidates)


def test_missing_required_candidate_column_fails_closed(tmp_path):
    path = tmp_path / "bad.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scenario_id", "plan_id"])
        writer.writeheader()
        writer.writerow({"scenario_id": "S", "plan_id": "P"})
    with pytest.raises(ValueError, match="missing columns"):
        load_candidates(path)


def test_non_finite_candidate_metric_fails_closed(tmp_path):
    path = tmp_path / "bad.csv"
    _write_candidates(path, [_row("S", "P", "nan", 0.1, 90_000)])
    with pytest.raises(ValueError, match="must be finite"):
        load_candidates(path)


def test_uncertainty_band_is_mandatory_semantically_and_cannot_be_negative(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(candidates, [_row("S", "P", 3.0, 0.1, 90_000)])
    _write_budgets(budgets)
    with pytest.raises(ValueError, match="uncertainty_band_min"):
        finalise(
            candidates_path=candidates,
            budget_path=budgets,
            output_dir=tmp_path / "out",
            uncertainty_band_min=-0.1,
            decision_budget_km=90_000,
        )


def test_uncertainty_band_rejects_nan(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(candidates, [_row("S", "P", 3.0, 0.1, 90_000)])
    _write_budgets(budgets)
    with pytest.raises(ValueError, match="must be finite"):
        finalise(
            candidates_path=candidates,
            budget_path=budgets,
            output_dir=tmp_path / "out",
            uncertainty_band_min=float("nan"),
            decision_budget_km=90_000,
        )


def test_no_candidate_inside_decision_budget_fails_closed(tmp_path):
    candidates = tmp_path / "candidates.csv"
    budgets = tmp_path / "budgets.csv"
    _write_candidates(candidates, [_row("S", "P", 3.0, 0.1, 120_000)])
    _write_budgets(budgets)
    with pytest.raises(ValueError, match="No eligible candidates fit"):
        finalise(
            candidates_path=candidates,
            budget_path=budgets,
            output_dir=tmp_path / "out",
            uncertainty_band_min=0.1,
            decision_budget_km=90_000,
        )
