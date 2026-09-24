from __future__ import annotations

import csv
from decimal import Decimal
import gzip
from pathlib import Path

from scripts.phase2_audit_tournament_contract_rt001_v3 import (
    STATUS as AUDIT_STATUS,
    build as build_audit,
    build_parser as audit_parser,
)
from scripts.phase2_build_nondeci_tournament_frontier_rt001_v3 import (
    STATUS as FRONTIER_STATUS,
    build as build_frontier,
    build_parser as frontier_parser,
    dominates,
    pareto_vectors,
)


def test_exact_pareto_engine_preserves_tradeoffs_and_removes_dominated_vectors() -> None:
    dimensions = [
        {"field": "benefit", "direction": "max"},
        {"field": "cost", "direction": "min"},
    ]
    high_benefit = (Decimal("10"), Decimal("8"))
    low_cost = (Decimal("8"), Decimal("5"))
    dominated = (Decimal("7"), Decimal("9"))

    assert dominates(high_benefit, dominated, dimensions)
    assert not dominates(high_benefit, low_cost, dimensions)
    assert pareto_vectors({high_benefit, low_cost, dominated}, dimensions) == {high_benefit, low_cost}


def test_legacy_contract_audit_fails_closed_field_by_field(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    result = build_audit(audit_parser().parse_args(["--output-dir", str(output)]))

    assert result["status"] == AUDIT_STATUS
    assert result["legacy_v2_tournament_schema_compatible"] is False
    assert result["legacy_v2_finalizer_run_authorized"] is False
    assert result["legacy_v2_required_column_count"] == 11
    assert result["v3_unique_plan_context_count"] == 16_495
    assert result["legacy_unique_scenario_plan_identity_count"] == 9_534
    assert result["rows_collapsed_by_legacy_identity"] == 6_961
    assert "median_gjt_improvement_min" in result["incompatible_or_semantically_unsupported_fields"]
    assert "median_missed_connection_probability" in result["incompatible_or_semantically_unsupported_fields"]
    assert result["decision_budget_selected"] is False
    assert result["uncertainty_band_selected"] is False

    with (output / "legacy_v2_tournament_input_compatibility_rt001_v3.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = {row["required_field"]: row for row in csv.DictReader(handle)}
    assert rows["median_gjt_improvement_min"]["availability"] == "MISSING"
    assert rows["median_missed_connection_probability"]["v3_permitted_use"] == "ENGINEERING_RETENTION_AS_SEPARATE_PARETO_AXIS_ONLY"
    assert rows["decision_budget_km"]["availability"] == "PENDING_CALLER_INPUT"


def test_v3_frontier_is_nondeci_and_preserves_all_context_membership(tmp_path: Path) -> None:
    audit_output = tmp_path / "audit"
    build_audit(audit_parser().parse_args(["--output-dir", str(audit_output)]))
    frontier_output = tmp_path / "frontier"
    args = frontier_parser().parse_args([
        "--contract-audit",
        str(audit_output / "legacy_v2_tournament_contract_audit_rt001_v3.json"),
        "--output-dir",
        str(frontier_output),
    ])
    result = build_frontier(args)

    assert result["status"] == FRONTIER_STATUS
    assert result["legacy_v2_tournament_schema_compatible"] is False
    assert result["legacy_v2_finalizer_invoked"] is False
    assert result["candidate_evaluation_rows_materialized"] is False
    assert result["recommendation_materialized"] is False
    assert result["input_context_count"] == 16_495
    assert result["frontier_context_count"] == 12_284
    assert result["dominated_context_count"] == 4_211
    assert result["partition_count"] == 12
    assert result["pareto_dimension_count"] == 29
    assert {row["applicable_dimension_count"] for row in result["partition_summary"].values()} == {25, 29}
    assert result["dominance_numeric_semantics"] == "EXACT_DECIMAL_ZERO_TOLERANCE"
    for field in (
        "weighted_composite_score",
        "decision_budget_selected",
        "uncertainty_band_selected",
        "primary_selection_authorised",
        "runner_up_selection_authorised",
    ):
        assert result[field] is False

    with gzip.open(
        frontier_output / "non_decisional_pareto_membership_rt001_v3.csv.gz",
        "rt",
        encoding="utf-8",
        newline="",
    ) as handle:
        membership = list(csv.DictReader(handle))
    assert len(membership) == 16_495
    assert sum(row["pareto_frontier_member"] == "true" for row in membership) == 12_284
    assert {row["primary_selection_authorised"] for row in membership} == {"false"}
    assert {row["runner_up_selection_authorised"] for row in membership} == {"false"}

    with gzip.open(
        frontier_output / "non_decisional_pareto_frontier_rt001_v3.csv.gz",
        "rt",
        encoding="utf-8",
        newline="",
    ) as handle:
        frontier_reader = csv.DictReader(handle)
        assert "demand_weighted_gjt_improvement_min" not in (frontier_reader.fieldnames or [])
        assert "missed_connection_probability" not in (frontier_reader.fieldnames or [])
