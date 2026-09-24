from __future__ import annotations

import csv
import gzip
from pathlib import Path

from scripts.phase2_build_final_tournament_readiness_rt001_v3 import (
    CONTRACT,
    STATUS,
    build,
    build_parser,
    build_sensitivity_rows,
)


def repo_args(tmp_path: Path):
    return build_parser().parse_args(["--output-dir", str(tmp_path)])


def test_full_certified_lineage_builds_a_fail_closed_readiness_pack(tmp_path: Path) -> None:
    result = build(repo_args(tmp_path))

    assert result["status"] == STATUS
    assert result["contract"] == CONTRACT
    assert result["readiness_audit_pass"] is True
    assert result["final_tournament_execution_ready"] is False
    assert result["represented_plan_context_count"] == 16_495
    assert result["distinct_selected_timetable_count"] == 6_000
    assert result["rt001_recovered_context_count"] == 646
    assert result["budget_envelopes_annual_bus_km"] == [
        89_135.2,
        100_277.1,
        111_419.0,
        122_560.9,
        133_702.8,
        144_844.7,
    ]
    for field in (
        "finalizer_invoked",
        "candidate_evaluation_rows_materialized",
        "recommendation_materialized",
        "decision_budget_selected",
        "uncertainty_band_selected",
        "primary_selected",
        "runner_up_selected",
        "weighted_composite_score",
        "full_demand_weighted_gjt_available",
        "empirical_missed_connection_probability_available",
    ):
        assert result[field] is False

    with gzip.open(
        tmp_path / "final_tournament_context_readiness_rt001_v3.csv.gz",
        "rt",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 16_495
    assert {row["final_candidate_evaluation_ready"] for row in rows} == {"false"}
    assert {row["primary_selected"] for row in rows} == {"false"}
    assert {row["runner_up_selected"] for row in rows} == {"false"}
    assert sum(row["recovered_from_continuous_hard_filter"] == "true" for row in rows) == 646
    assert all(float(row["exact_budget_margin_annual_bus_km"]) >= -1e-6 for row in rows)


def test_full_build_is_byte_deterministic(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    build(repo_args(left))
    build(repo_args(right))

    for name in (
        "final_tournament_context_readiness_rt001_v3.csv.gz",
        "final_tournament_budget_envelopes_rt001_v3.csv",
        "final_tournament_sensitivity_readiness_rt001_v3.csv",
    ):
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_required_sensitivity_gaps_remain_explicit() -> None:
    rows = build_sensitivity_rows(
        stage_e={
            "bus_runtime_delay_minutes": [0, 5, 10, 15],
            "rail_arrival_delay_minutes": [0],
            "recovery_minutes": [5, 10, 15],
        },
        journey={"full_gjt_ready": False},
        behavioral_rows=[
            {"walk_weight": "1.5", "wait_weight": "1.5"},
            {"walk_weight": "2.0", "wait_weight": "2.5"},
        ],
        budget_count=6,
    )
    indexed = {row["dimension"]: row for row in rows}

    assert indexed["WALK_WEIGHT"]["readiness_status"] == "PARAMETER_GRID_ONLY"
    assert indexed["BUS_RUNNING_TIME"]["readiness_status"] == "PARTIAL_ENGINEERING_STRESS_ONLY"
    assert indexed["DWELL_VARIATION"]["readiness_status"] == "MISSING"
    assert indexed["RAIL_DELAY"]["readiness_status"] == "NOMINAL_ONLY"
    assert indexed["ANNUAL_BUS_KM_ENVELOPE"]["readiness_status"] == "AVAILABLE_NOT_SELECTED"
    assert indexed["FULL_DEMAND_WEIGHTED_GJT"]["readiness_status"] == "MISSING"
    assert all(row["authorized_for_final_selection"] == "false" for row in rows)
