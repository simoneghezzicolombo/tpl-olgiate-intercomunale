from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.phase2_build_final_decision_sufficiency_gate_v3 import (
    CONTRACT,
    STATUS,
    build,
    build_parser,
)


def args_for(output_dir: Path):
    return build_parser().parse_args(["--output-dir", str(output_dir)])


def test_certified_gate_freezes_blocker_universe_and_preserves_contexts(tmp_path: Path) -> None:
    result = build(args_for(tmp_path))
    assert result["status"] == STATUS
    assert result["contract"] == CONTRACT
    assert result["audit_pass"] is True
    assert result["blocker_universe_closed"] is True
    assert result["new_blocker_creation_authorized"] is False
    assert result["new_blocker_creation_requires_gate_reopen"] is True
    assert result["preserve_all_plan_contexts"] is True
    assert result["preserved_plan_context_count"] == 16_495
    assert result["can_materialize_final_decision_now"] is False
    assert result["final_selection_authorized"] is False
    assert result["primary_selection_authorised"] is False
    assert result["runner_up_selection_authorised"] is False
    assert result["v3_descriptive_frontier_may_prune"] is False


def test_v3_pathway_has_no_unresolved_technical_data_requirement_but_still_needs_human_contract(tmp_path: Path) -> None:
    result = build(args_for(tmp_path))
    assert result["legacy_v2_technical_open_data_requirement_count"] == 4
    assert result["v3_deterministic_technical_open_data_requirement_count"] == 0
    assert result["final_decision_pathway_selected"] is False
    assert result["decision_budget_selected"] is False
    assert result["uncertainty_band_selected"] is False
    assert result["normative_v3_decision_rule_selected"] is False

    with (tmp_path / "final_decision_pathway_summary_v3.csv").open(encoding="utf-8", newline="") as handle:
        rows = {row["pathway_id"]: row for row in csv.DictReader(handle)}
    v3 = rows["V3_CERTIFIED_METRICS_DETERMINISTIC_ROBUSTNESS"]
    assert v3["technical_open_data_requirement_count"] == "0"
    assert v3["human_decision_requirement_count_after_pathway_selection"] == "3"
    assert v3["full_demand_weighted_gjt_required"] == "false"
    assert v3["empirical_missed_connection_probability_required"] == "false"
    assert v3["complete_current_service_nonregression_required"] == "false"


def test_no_missing_semantics_are_manufactured(tmp_path: Path) -> None:
    result = build(args_for(tmp_path))
    for field in (
        "manufactured_demand_weighted_gjt",
        "manufactured_missed_connection_probability",
        "stage_e_or_f_engineering_stress_is_probability",
        "municipal_od_spatially_downscaled",
        "current_service_lower_bound_relabelled_as_complete",
        "weighted_composite_score",
    ):
        assert result[field] is False
    assert result["stage_f_engineering_sensitivity_closed"] is True
    assert result["stage_f_empirical_reliability_created"] is False
    assert result["current_service_baseline_state"] == "CLOSED_WITH_CERTIFIED_BOUND"
    assert result["current_service_localized_rows"] == 15
    assert result["current_service_unresolved_rows"] == 36


def test_blocker_matrix_contains_only_frozen_states_and_no_engineering_authorisation(tmp_path: Path) -> None:
    build(args_for(tmp_path))
    with (tmp_path / "final_decision_blocker_matrix_v3.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    allowed = {
        "CLOSED",
        "CLOSED_WITH_CERTIFIED_BOUND",
        "OPEN_DATA_EVIDENCE",
        "HUMAN_DECISION_REQUIRED",
        "NOT_REQUIRED_UNDER_V3_CONTRACT",
    }
    assert len(rows) == 16
    assert all(row["global_state"] in allowed for row in rows)
    assert all(row["legacy_v2_state"] in allowed for row in rows)
    assert all(row["v3_deterministic_state"] in allowed for row in rows)
    assert {row["engineering_work_authorized_now"] for row in rows} == {"false"}
    indexed = {row["requirement_id"]: row for row in rows}
    assert indexed["EVID-005"]["global_state"] == "CLOSED"
    assert indexed["EVID-006"]["global_state"] == "CLOSED_WITH_CERTIFIED_BOUND"
    assert indexed["DATA-002"]["legacy_v2_state"] == "OPEN_DATA_EVIDENCE"
    assert indexed["DATA-002"]["v3_deterministic_state"] == "NOT_REQUIRED_UNDER_V3_CONTRACT"
    assert indexed["NREQ-002"]["v3_deterministic_state"] == "NOT_REQUIRED_UNDER_V3_CONTRACT"


def test_full_build_is_byte_deterministic(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    build(args_for(left))
    build(args_for(right))
    for filename in (
        "final_decision_blocker_matrix_v3.csv",
        "final_decision_pathway_summary_v3.csv",
        "final_decision_sufficiency_gate_v3_validation.json",
    ):
        assert (left / filename).read_bytes() == (right / filename).read_bytes()


def test_validation_json_does_not_authorize_hidden_selection(tmp_path: Path) -> None:
    build(args_for(tmp_path))
    payload = json.loads((tmp_path / "final_decision_sufficiency_gate_v3_validation.json").read_text(encoding="utf-8"))
    assert payload["finite_next_step_tree"]["no_other_engineering_task_authorized_by_this_gate"] is True
    assert payload["non_certified_gjt_identifiability_workstream_consumed"] is False
    assert payload["human_decision_requirement_ids_before_final_selection"] == [
        "HUMAN-001",
        "HUMAN-002",
        "HUMAN-003",
        "HUMAN-004_IF_V3_SELECTED",
    ]
