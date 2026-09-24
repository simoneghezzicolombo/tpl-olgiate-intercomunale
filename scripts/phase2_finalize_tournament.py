#!/usr/bin/env python3
"""Materialise the Phase 2 finalist tournament from REAL evaluated candidates.

This script deliberately does not create candidate metrics. It consumes a table
whose rows are already robust topology+service `CandidateEvaluation` results and
turns them into the decision artefacts required by the Phase 2 specification:

- non-dominated robust frontier;
- budget/utility curve;
- primary and runner-up finalists;
- final recommendation record with explicit decision-rule provenance.

Both the uncertainty band and the decision budget are mandatory caller choices.
The script will not silently choose a tolerance or promote the largest available
budget envelope into the normative decision budget.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Iterable

from src.phase2_candidate_tournament import (
    CandidateEvaluation,
    CandidateKey,
    candidate_budget_frontier,
    candidate_frontier,
    candidate_to_dict,
    select_candidates,
)


REQUIRED_COLUMNS = {
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
}

BUDGET_MATCH_REL_TOL = 1e-9
BUDGET_MATCH_ABS_TOL_KM = 1e-6


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _parse_bool(raw: object) -> bool:
    value = str(raw).strip().lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    raise ValueError(f"Cannot parse boolean value {raw!r}")


def _finite_float(name: str, raw: object) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def load_candidates(path: Path) -> list[CandidateEvaluation]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - fieldnames)
        if missing:
            raise ValueError(f"Candidate evaluation input missing columns: {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError("Candidate evaluation input is empty")

    evaluations: list[CandidateEvaluation] = []
    for index, row in enumerate(rows, start=2):
        try:
            evaluation = CandidateEvaluation(
                key=CandidateKey(
                    scenario_id=str(row["scenario_id"]).strip(),
                    plan_id=str(row["plan_id"]).strip(),
                ),
                eligible=_parse_bool(row["eligible"]),
                median_gjt_improvement_min=_finite_float(
                    "median_gjt_improvement_min", row["median_gjt_improvement_min"]
                ),
                lower_quantile_gjt_improvement_min=_finite_float(
                    "lower_quantile_gjt_improvement_min", row["lower_quantile_gjt_improvement_min"]
                ),
                median_missed_connection_probability=_finite_float(
                    "median_missed_connection_probability", row["median_missed_connection_probability"]
                ),
                annual_bus_km=_finite_float("annual_bus_km", row["annual_bus_km"]),
                public_pattern_complexity=int(row["public_pattern_complexity"]),
                unverified_elements=int(row["unverified_elements"]),
                retained_existing_stops_share=_finite_float(
                    "retained_existing_stops_share", row["retained_existing_stops_share"]
                ),
                n_sensitivity_runs=int(row["n_sensitivity_runs"]),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid candidate evaluation at CSV row {index}: {exc}") from exc
        evaluations.append(evaluation)

    candidate_ids = [row.candidate_id for row in evaluations]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Candidate evaluation input contains duplicate scenario_id + plan_id rows")
    if not any(row.eligible for row in evaluations):
        raise ValueError("Candidate evaluation input contains no eligible candidates")
    return evaluations


def load_budget_envelopes(path: Path) -> list[float]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if "annual_bus_km_cap" not in fields:
            raise ValueError("Budget envelope input requires annual_bus_km_cap")
        rows = list(reader)
    if not rows:
        raise ValueError("Budget envelope input is empty")
    try:
        values = [_finite_float("annual_bus_km_cap", row["annual_bus_km_cap"]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid budget envelope input: {exc}") from exc
    if any(value <= 0 for value in values):
        raise ValueError("Budget envelopes must be positive")
    return sorted(set(values))


def _match_declared_budget(decision_budget_km: object, budgets: list[float]) -> float:
    if decision_budget_km is None:
        raise ValueError("decision_budget_km is required and has no implicit default")
    decision_budget = _finite_float("decision_budget_km", decision_budget_km)
    if decision_budget <= 0:
        raise ValueError("decision_budget_km must be positive")
    matches = [
        value
        for value in budgets
        if math.isclose(
            decision_budget,
            value,
            rel_tol=BUDGET_MATCH_REL_TOL,
            abs_tol=BUDGET_MATCH_ABS_TOL_KM,
        )
    ]
    if len(matches) != 1:
        raise ValueError(
            "decision_budget_km must match exactly one declared budget envelope "
            f"within rel_tol={BUDGET_MATCH_REL_TOL} and abs_tol={BUDGET_MATCH_ABS_TOL_KM} km"
        )
    return matches[0]


def _write_csv(path: Path, rows: Iterable[dict[str, object]], *, fieldnames: list[str] | None = None) -> None:
    materialised = list(rows)
    if not materialised:
        raise ValueError(f"Refusing to write empty CSV {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(materialised[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(materialised)


def finalise(
    *,
    candidates_path: Path,
    budget_path: Path,
    output_dir: Path,
    uncertainty_band_min: float,
    decision_budget_km: float | None,
) -> dict[str, object]:
    uncertainty_band = _finite_float("uncertainty_band_min", uncertainty_band_min)
    if uncertainty_band < 0:
        raise ValueError("uncertainty_band_min cannot be negative")

    evaluations = load_candidates(candidates_path)
    budgets = load_budget_envelopes(budget_path)
    decision_budget = _match_declared_budget(decision_budget_km, budgets)

    decision_pool = [row for row in evaluations if row.eligible and row.annual_bus_km <= decision_budget]
    if not decision_pool:
        raise ValueError("No eligible candidates fit within the declared decision budget")

    frontier = candidate_frontier(evaluations)
    budget_curve = candidate_budget_frontier(evaluations, budgets)
    selection = select_candidates(decision_pool, uncertainty_band_min=uncertainty_band)

    frontier_rows = [candidate_to_dict(row) for row in frontier]
    finalist_rows = [
        {"rank": "PRIMARY", **candidate_to_dict(selection.primary)},
    ]
    if selection.runner_up is not None:
        finalist_rows.append({"rank": "RUNNER_UP", **candidate_to_dict(selection.runner_up)})

    output_dir.mkdir(parents=True, exist_ok=True)
    frontier_path = output_dir / "frontier.csv"
    budget_curve_path = output_dir / "budget_utility_curve.csv"
    finalists_path = output_dir / "finalists.csv"
    recommendation_path = output_dir / "final_recommendation.json"

    _write_csv(frontier_path, frontier_rows)
    _write_csv(budget_curve_path, budget_curve)
    _write_csv(finalists_path, finalist_rows)

    recommendation: dict[str, object] = {
        "status": "DECISION_MATERIALISED_FROM_EVALUATED_CANDIDATES",
        "decision_budget_bus_km_year": decision_budget,
        "decision_budget_contract": "EXPLICIT_CALLER_DECLARED_MATCHED_TO_MATERIALISED_ENVELOPE",
        "budget_match_rel_tol": BUDGET_MATCH_REL_TOL,
        "budget_match_abs_tol_km": BUDGET_MATCH_ABS_TOL_KM,
        "uncertainty_band_min": uncertainty_band,
        "tie_break_invoked": selection.tie_break_invoked,
        "decision_rule": {
            "step_1": "HARD_ELIGIBILITY",
            "step_2": "MAXIMISE_ROBUST_DEMAND_WEIGHTED_GJT_IMPROVEMENT",
            "step_3": "UNCERTAINTY_BAND_THEN_LEXICOGRAPHIC_PRACTICAL_TIE_BREAK",
            "tie_break_order": [
                "LOWER_MEDIAN_MISSED_CONNECTION_PROBABILITY",
                "LOWER_PUBLIC_PATTERN_COMPLEXITY",
                "LOWER_ANNUAL_BUS_KM",
                "FEWER_UNVERIFIED_ELEMENTS",
                "HIGHER_EXISTING_STOP_RETENTION",
                "HIGHER_LOWER_QUANTILE_GJT_IMPROVEMENT",
                "STABLE_CANDIDATE_ID",
            ],
            "weighted_composite_score": False,
            "implicit_budget_default": False,
        },
        "primary": candidate_to_dict(selection.primary),
        "runner_up": candidate_to_dict(selection.runner_up) if selection.runner_up else None,
        "eligible_candidates_within_decision_budget": len(decision_pool),
        "eligible_candidates_total": sum(row.eligible for row in evaluations),
        "candidate_rows_total": len(evaluations),
        "frontier_candidate_count": len(frontier),
        "budget_envelopes_bus_km_year": budgets,
        "input_lineage": {
            "candidate_evaluations_path": str(candidates_path),
            "candidate_evaluations_sha256": _sha256_path(candidates_path),
            "budget_envelopes_path": str(budget_path),
            "budget_envelopes_sha256": _sha256_path(budget_path),
        },
        "output_semantics": (
            "This record selects among already evaluated topology+service candidates. "
            "It does not create route geometry, demand weights, timetables or passenger metrics."
        ),
    }
    recommendation_path.write_text(
        json.dumps(recommendation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return recommendation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--budgets", required=True, type=Path)
    parser.add_argument("--output-dir", default="outputs/phase2", type=Path)
    parser.add_argument("--uncertainty-band-min", required=True, type=float)
    parser.add_argument(
        "--decision-budget-km",
        required=True,
        type=float,
        help="Explicit normative budget for primary/runner-up selection; must match a declared envelope.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    result = finalise(
        candidates_path=args.candidates,
        budget_path=args.budgets,
        output_dir=args.output_dir,
        uncertainty_band_min=args.uncertainty_band_min,
        decision_budget_km=args.decision_budget_km,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
