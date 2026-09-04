#!/usr/bin/env python3
"""Build the finite Phase 2 final-decision sufficiency / blocker-closure gate.

The gate does not rank or select networks. It freezes the currently certified
blocker universe, distinguishes evidence gaps from caller decisions, and reports
two explicit decision pathways without silently choosing either one.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Mapping

STATUS = "PASS_PHASE2_FINAL_DECISION_SUFFICIENCY_GATE_V3"
CONTRACT = "PHASE2_FINITE_BLOCKER_CLOSURE_AND_DECISION_PATHWAY_V3"
ALLOWED_STATES = {
    "CLOSED",
    "CLOSED_WITH_CERTIFIED_BOUND",
    "OPEN_DATA_EVIDENCE",
    "HUMAN_DECISION_REQUIRED",
    "NOT_REQUIRED_UNDER_V3_CONTRACT",
}

MATRIX_FIELDS = [
    "requirement_id",
    "requirement",
    "certified_source",
    "certified_evidence_semantics",
    "global_state",
    "legacy_v2_state",
    "v3_deterministic_state",
    "engineering_work_authorized_now",
    "human_action_required",
    "notes",
]

PATHWAY_FIELDS = [
    "pathway_id",
    "pathway_selected",
    "technical_open_data_requirement_count",
    "human_decision_requirement_count_after_pathway_selection",
    "not_required_requirement_count",
    "can_materialize_final_decision_now",
    "full_demand_weighted_gjt_required",
    "empirical_missed_connection_probability_required",
    "complete_current_service_nonregression_required",
    "route_level_demand_weight_sensitivity_required",
    "decision_semantics",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def strict_false(obj: Mapping[str, object], field: str, *, source: str) -> None:
    if obj.get(field) is not False:
        raise ValueError(f"{source}: expected {field}=false")


def strict_true(obj: Mapping[str, object], field: str, *, source: str) -> None:
    if obj.get(field) is not True:
        raise ValueError(f"{source}: expected {field}=true")


def validate_sources(args: argparse.Namespace, cfg: Mapping[str, object]) -> dict[str, dict]:
    sources = {
        "stage_e": read_json(args.stage_e_validation),
        "readiness": read_json(args.readiness_validation),
        "codex_redteam": read_json(args.codex_redteam_validation),
        "legacy_contract_audit": read_json(args.legacy_contract_audit),
        "frontier": read_json(args.frontier_validation),
        "stage_f": read_json(args.stage_f_validation),
        "current_baseline": read_json(args.current_baseline_validation),
        "old_vs_new": read_json(args.old_vs_new_validation),
    }

    stage_e = sources["stage_e"]
    if stage_e.get("status") != "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3":
        raise ValueError("Stage E RT001 V3 is not certified PASS")
    strict_true(stage_e, "stage_d_cross_implementation_audit_pass", source="Stage E")
    strict_true(stage_e, "stage_d_fixture_is_final_selection_lineage", source="Stage E")
    strict_true(stage_e, "planned_connection_identity_preserved", source="Stage E")
    strict_false(stage_e, "delay_sensitivity_is_empirical_probability", source="Stage E")
    strict_false(stage_e, "passenger_weighting_applied", source="Stage E")
    strict_false(stage_e, "municipal_od_downscaled", source="Stage E")
    strict_false(stage_e, "final_selection_authorized", source="Stage E")
    if int(stage_e.get("represented_plan_context_count", -1)) != int(cfg["expected_plan_context_count"]):
        raise ValueError("Stage E context count does not match closure-gate contract")

    readiness = sources["readiness"]
    if readiness.get("status") != "PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3":
        raise ValueError("Codex tournament readiness is not certified PASS")
    strict_false(readiness, "final_tournament_execution_ready", source="readiness")
    strict_false(readiness, "full_demand_weighted_gjt_available", source="readiness")
    strict_false(readiness, "empirical_missed_connection_probability_available", source="readiness")
    strict_false(readiness, "candidate_evaluation_rows_materialized", source="readiness")
    strict_false(readiness, "primary_selected", source="readiness")
    strict_false(readiness, "runner_up_selected", source="readiness")

    redteam = sources["codex_redteam"]
    if redteam.get("status") != "PASS_PHASE2_CODEX_TOURNAMENT_READINESS_REDTEAM_RT001_V3":
        raise ValueError("independent tournament-readiness red-team is not PASS")
    strict_true(redteam, "audit_pass", source="Codex red-team")
    strict_false(redteam, "manufactured_demand_weighted_gjt", source="Codex red-team")
    strict_false(redteam, "manufactured_missed_connection_probability", source="Codex red-team")
    strict_false(redteam, "stage_e_engineering_retention_reinterpreted_as_probability", source="Codex red-team")
    strict_false(redteam, "municipal_od_spatially_downscaled", source="Codex red-team")
    strict_false(redteam, "nonfrontier_pruning_authorized", source="Codex red-team")
    strict_false(redteam, "frontier_membership_may_authorize_pruning", source="Codex red-team")
    if int(redteam.get("input_context_count", -1)) != int(cfg["expected_plan_context_count"]):
        raise ValueError("Codex red-team context count mismatch")

    legacy = sources["legacy_contract_audit"]
    if legacy.get("status") != "PASS_PHASE2_LEGACY_TOURNAMENT_CONTRACT_AUDIT_RT001_V3":
        raise ValueError("legacy tournament contract audit is not PASS")
    strict_false(legacy, "legacy_v2_tournament_schema_compatible", source="legacy contract audit")
    strict_false(legacy, "legacy_v2_finalizer_run_authorized", source="legacy contract audit")
    strict_false(legacy, "full_demand_weighted_gjt_available", source="legacy contract audit")
    strict_false(legacy, "empirical_missed_connection_probability_available", source="legacy contract audit")

    frontier = sources["frontier"]
    if frontier.get("status") != "PASS_PHASE2_NON_DECISIONAL_TOURNAMENT_FRONTIER_RT001_V3":
        raise ValueError("V3 descriptive frontier is not PASS")
    strict_false(frontier, "legacy_v2_finalizer_invoked", source="frontier")
    strict_false(frontier, "candidate_evaluation_rows_materialized", source="frontier")
    strict_false(frontier, "recommendation_materialized", source="frontier")
    strict_false(frontier, "primary_selection_authorised", source="frontier")
    strict_false(frontier, "runner_up_selection_authorised", source="frontier")
    if int(frontier.get("input_context_count", -1)) != int(cfg["expected_plan_context_count"]):
        raise ValueError("frontier context count mismatch")

    stage_f = sources["stage_f"]
    if stage_f.get("status") != "PASS_PHASE2_STAGE_F_ENGINEERING_ROBUSTNESS_RT001_V3":
        raise ValueError("Stage F engineering robustness is not PASS")
    if stage_f.get("contract") != "PHASE2_STAGE_F_DETERMINISTIC_ENGINEERING_SENSITIVITY_RT001_V3":
        raise ValueError("unexpected Stage F contract")
    strict_true(stage_f, "validation_pass", source="Stage F")
    strict_true(stage_f, "full_stage_f_surface_materialized", source="Stage F")
    strict_true(stage_f, "stage_f_blocker_closed_for_engineering_sensitivity", source="Stage F")
    strict_true(stage_f, "runtime_decrease_sensitivity_materialized", source="Stage F")
    strict_true(stage_f, "dwell_sensitivity_materialized", source="Stage F")
    strict_true(stage_f, "nonzero_rail_shift_sensitivity_materialized", source="Stage F")
    strict_false(stage_f, "assumption_sensitivity_is_empirical_probability", source="Stage F")
    strict_false(stage_f, "connection_retention_is_probability", source="Stage F")
    strict_false(stage_f, "passenger_weighting_applied", source="Stage F")
    strict_false(stage_f, "municipal_od_downscaled", source="Stage F")
    strict_false(stage_f, "final_selection_authorized", source="Stage F")
    if int(stage_f.get("timetable_count", -1)) != 6000:
        raise ValueError("Stage F does not cover all 6,000 exact timetables")

    baseline = sources["current_baseline"]
    if baseline.get("overall_status") != "PASS_CURRENT_SERVICE_ACCESS_BASELINE_V3":
        raise ValueError("current-service baseline V3 is not PASS")
    if baseline.get("contract") != "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V3":
        raise ValueError("unexpected current-service baseline V3 contract")
    strict_false(baseline, "baseline_complete", source="current baseline")
    strict_false(baseline, "may_infer_true_current_total_coverage", source="current baseline")
    governance = baseline.get("comparison_governance", {})
    if not isinstance(governance, dict):
        raise ValueError("current-service comparison governance missing")
    strict_false(governance, "true_current_total_coverage_available", source="current baseline governance")
    strict_false(governance, "candidate_vs_current_fair_ordering_possible", source="current baseline governance")
    strict_false(governance, "no_regression_decision_authorized", source="current baseline governance")
    if int(baseline.get("localized_rows", -1)) != 12 or int(baseline.get("unresolved_rows", -1)) != 39:
        raise ValueError("current-service localization counts changed; closure gate requires review")

    old_new = sources["old_vs_new"]
    if old_new.get("contract") != "PHASE2_SEMANTIC_OLD_VS_RT001_STAGE_E_ROBUSTNESS_AUDIT_V1":
        raise ValueError("unexpected Stage E old-vs-new audit contract")
    if old_new.get("failure_reasons") != []:
        raise ValueError("Stage E old-vs-new audit reports failures")
    strict_true(old_new, "deterministic_rebuild", source="old-vs-new")
    strict_false(old_new, "bus_runtime_engineering_stress_is_empirical_probability", source="old-vs-new")
    if int(old_new.get("block_unexplained_comparable_mismatch_count", -1)) != 0:
        raise ValueError("unexplained comparable block mismatch remains")
    if int(old_new.get("surface_unexplained_comparable_mismatch_count", -1)) != 0:
        raise ValueError("unexplained comparable robustness mismatch remains")

    return sources


def matrix_rows() -> list[dict[str, object]]:
    rows = [
        {
            "requirement_id": "EVID-001",
            "requirement": "RT001 lossless exact timetable lineage and independent Stage-D convergence",
            "certified_source": "Stage E RT001 V3 + Stage-D cross-audit lineage",
            "certified_evidence_semantics": "6,000 exact timetables over 16,495 exact-budget contexts with cross-implementation audit PASS",
            "global_state": "CLOSED",
            "legacy_v2_state": "CLOSED",
            "v3_deterministic_state": "CLOSED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "No further Stage-D rebuild is required unless a certified lineage contradiction appears.",
        },
        {
            "requirement_id": "EVID-002",
            "requirement": "Final-lineage Stage E planned-connection and vehicle-block robustness",
            "certified_source": "Stage E RT001 V3",
            "certified_evidence_semantics": "Deterministic engineering robustness with frozen planned targets; not empirical probability",
            "global_state": "CLOSED",
            "legacy_v2_state": "CLOSED",
            "v3_deterministic_state": "CLOSED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "Stage E must not be reinterpreted as a delay-probability model.",
        },
        {
            "requirement_id": "EVID-003",
            "requirement": "Legacy-vs-RT001 Stage E semantic regression audit",
            "certified_source": "A Stage E OLD-vs-NEW audit",
            "certified_evidence_semantics": "Comparable differences fully attributed; zero unexplained comparable robustness or block mismatches",
            "global_state": "CLOSED",
            "legacy_v2_state": "CLOSED",
            "v3_deterministic_state": "CLOSED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "Out-of-span passenger-return correction is certified and does not require another rerun.",
        },
        {
            "requirement_id": "EVID-004",
            "requirement": "Tournament-readiness semantics and non-decisional Pareto safety",
            "certified_source": "Codex readiness/contract audit + A red-team",
            "certified_evidence_semantics": "No fabricated GJT/probability; Pareto membership is descriptive and cannot authorize pruning",
            "global_state": "CLOSED",
            "legacy_v2_state": "CLOSED",
            "v3_deterministic_state": "CLOSED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "All 16,495 contexts remain preserved until a separately authorized final decision.",
        },
        {
            "requirement_id": "EVID-005",
            "requirement": "Stage F deterministic engineering sensitivity surface",
            "certified_source": "Stage F Engineering Robustness RT001 V3",
            "certified_evidence_semantics": "81-case deterministic sensitivity over runtime 0.9/1.0/1.1, dwell 0/0.5/1.0, rail shift -5/0/+5 and certified transfer profiles; block surface with recovery 5/10/15",
            "global_state": "CLOSED",
            "legacy_v2_state": "CLOSED",
            "v3_deterministic_state": "CLOSED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "This closes the engineering-sensitivity sub-blocker only; it does not create passenger probabilities or demand weights.",
        },
        {
            "requirement_id": "EVID-006",
            "requirement": "Certified current-service localisable access reference",
            "certified_source": "Current Service Access Baseline V3",
            "certified_evidence_semantics": "12/51 rows localized, 39 unresolved; certified access lower bound only",
            "global_state": "CLOSED_WITH_CERTIFIED_BOUND",
            "legacy_v2_state": "CLOSED_WITH_CERTIFIED_BOUND",
            "v3_deterministic_state": "CLOSED_WITH_CERTIFIED_BOUND",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "The lower-bound artifact is complete as a lower bound. It must never be relabeled as complete current service.",
        },
        {
            "requirement_id": "DATA-001",
            "requirement": "Complete current-service non-regression / fair candidate-vs-current ordering",
            "certified_source": "Current Service Access Baseline V3 comparison governance",
            "certified_evidence_semantics": "True current total coverage and complete no-regression ordering are unavailable",
            "global_state": "OPEN_DATA_EVIDENCE",
            "legacy_v2_state": "OPEN_DATA_EVIDENCE",
            "v3_deterministic_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "V3 may proceed only if its human-selected semantics explicitly retain the current-service evidence as a labelled lower bound rather than claiming true non-regression.",
        },
        {
            "requirement_id": "DATA-002",
            "requirement": "Full candidate-level demand-weighted GJT improvement",
            "certified_source": "Final Tournament Readiness RT001 V3 + legacy contract audit",
            "certified_evidence_semantics": "full_demand_weighted_gjt_available=false; municipal OD has no authorized route/passenger spatial allocation",
            "global_state": "OPEN_DATA_EVIDENCE",
            "legacy_v2_state": "OPEN_DATA_EVIDENCE",
            "v3_deterministic_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "Do not create a point GJT estimate or route-level demand by proxy. A future certified evidence/model contract could reopen this gate.",
        },
        {
            "requirement_id": "DATA-003",
            "requirement": "Empirical missed-connection probability",
            "certified_source": "Stage E/Stage F + Final Tournament Readiness RT001 V3",
            "certified_evidence_semantics": "Deterministic engineering retention exists; empirical missed-connection probability does not",
            "global_state": "OPEN_DATA_EVIDENCE",
            "legacy_v2_state": "OPEN_DATA_EVIDENCE",
            "v3_deterministic_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "Engineering stress must remain deterministic evidence and must not be assigned empirical probability mass.",
        },
        {
            "requirement_id": "DATA-004",
            "requirement": "Route-level demand-weight perturbation sensitivity",
            "certified_source": "Final Tournament Readiness RT001 V3",
            "certified_evidence_semantics": "No authorized route-level demand attribution exists from municipal OD",
            "global_state": "OPEN_DATA_EVIDENCE",
            "legacy_v2_state": "OPEN_DATA_EVIDENCE",
            "v3_deterministic_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "The Stage F engineering surface is complete without inventing demand perturbations; this remains a legacy/full-passenger-evaluation evidence gap.",
        },
        {
            "requirement_id": "HUMAN-001",
            "requirement": "Select final decision semantics pathway",
            "certified_source": "This closure-gate contract",
            "certified_evidence_semantics": "Choose either wait for legacy full-evidence semantics or explicitly authorize V3 certified-metrics deterministic-robustness semantics",
            "global_state": "HUMAN_DECISION_REQUIRED",
            "legacy_v2_state": "HUMAN_DECISION_REQUIRED",
            "v3_deterministic_state": "HUMAN_DECISION_REQUIRED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "true",
            "notes": "Selecting V3 means accepting that the recommendation will not claim full demand-weighted GJT, empirical missed-connection probability or complete-current-service non-regression.",
        },
        {
            "requirement_id": "HUMAN-002",
            "requirement": "Select decision annual bus-km envelope",
            "certified_source": "Six exact materialized budget envelopes",
            "certified_evidence_semantics": "Normative caller choice; no implicit largest/default budget is authorized",
            "global_state": "HUMAN_DECISION_REQUIRED",
            "legacy_v2_state": "HUMAN_DECISION_REQUIRED",
            "v3_deterministic_state": "HUMAN_DECISION_REQUIRED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "true",
            "notes": "Must match one of the six certified exact annual bus-km envelopes.",
        },
        {
            "requirement_id": "HUMAN-003",
            "requirement": "Select uncertainty band semantics/value if retained in final Decision Contract",
            "certified_source": "Decision Contract boundary",
            "certified_evidence_semantics": "Caller-declared finite non-negative policy input; no default authorized",
            "global_state": "HUMAN_DECISION_REQUIRED",
            "legacy_v2_state": "HUMAN_DECISION_REQUIRED",
            "v3_deterministic_state": "HUMAN_DECISION_REQUIRED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "true",
            "notes": "The gate does not choose or infer a tolerance.",
        },
        {
            "requirement_id": "HUMAN-004",
            "requirement": "Specify a normative no-weight decision rule over the V3 trade-off set",
            "certified_source": "V3 non-decisional Pareto contract",
            "certified_evidence_semantics": "Pareto non-dominance exposes trade-offs but does not rank, shortlist or recommend",
            "global_state": "HUMAN_DECISION_REQUIRED",
            "legacy_v2_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "v3_deterministic_state": "HUMAN_DECISION_REQUIRED",
            "engineering_work_authorized_now": "false",
            "human_action_required": "true",
            "notes": "This can be an explicit lexicographic/policy rule; the implementation must not invent hidden weights.",
        },
        {
            "requirement_id": "NREQ-001",
            "requirement": "Pre-select one recovery value before final network decision",
            "certified_source": "Stage E/Stage F sensitivity semantics",
            "certified_evidence_semantics": "Recovery 5/10/15 is an engineering sensitivity dimension and is intentionally not selected",
            "global_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "legacy_v2_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "v3_deterministic_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "Recovery may be chosen later as an operational implementation parameter; it is not a prerequisite for comparing network evidence.",
        },
        {
            "requirement_id": "NREQ-002",
            "requirement": "Prune the 4,211 descriptive Pareto-nonfrontier contexts",
            "certified_source": "A Codex Tournament Readiness Red-Team",
            "certified_evidence_semantics": "nonfrontier_pruning_authorized=false; lower-bound axes do not establish latent true-system dominance",
            "global_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "legacy_v2_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "v3_deterministic_state": "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "engineering_work_authorized_now": "false",
            "human_action_required": "false",
            "notes": "Preserve all 16,495 contexts until a separately certified final decision contract authorizes elimination.",
        },
    ]
    rows.sort(key=lambda row: str(row["requirement_id"]))
    for row in rows:
        for field in ("global_state", "legacy_v2_state", "v3_deterministic_state"):
            if row[field] not in ALLOWED_STATES:
                raise ValueError(f"invalid blocker state {row[field]} for {row['requirement_id']}")
    return rows


def pathway_rows(rows: list[dict[str, object]], cfg: Mapping[str, object]) -> list[dict[str, object]]:
    indexed = {str(row["requirement_id"]): row for row in rows}
    legacy_open = [row for row in rows if row["legacy_v2_state"] == "OPEN_DATA_EVIDENCE"]
    v3_open = [row for row in rows if row["v3_deterministic_state"] == "OPEN_DATA_EVIDENCE"]
    legacy_human = [
        indexed["HUMAN-002"],
        indexed["HUMAN-003"],
    ]
    v3_human = [
        indexed["HUMAN-002"],
        indexed["HUMAN-003"],
        indexed["HUMAN-004"],
    ]
    result = [
        {
            "pathway_id": cfg["legacy_v2_pathway_id"],
            "pathway_selected": "false",
            "technical_open_data_requirement_count": len(legacy_open),
            "human_decision_requirement_count_after_pathway_selection": len(legacy_human),
            "not_required_requirement_count": sum(row["legacy_v2_state"] == "NOT_REQUIRED_UNDER_V3_CONTRACT" for row in rows),
            "can_materialize_final_decision_now": "false",
            "full_demand_weighted_gjt_required": "true",
            "empirical_missed_connection_probability_required": "true",
            "complete_current_service_nonregression_required": "true",
            "route_level_demand_weight_sensitivity_required": "true",
            "decision_semantics": "Retain legacy evaluated-candidate semantics; wait for the missing certified passenger/reliability/current-service evidence before final selection.",
        },
        {
            "pathway_id": cfg["v3_candidate_pathway_id"],
            "pathway_selected": "false",
            "technical_open_data_requirement_count": len(v3_open),
            "human_decision_requirement_count_after_pathway_selection": len(v3_human),
            "not_required_requirement_count": sum(row["v3_deterministic_state"] == "NOT_REQUIRED_UNDER_V3_CONTRACT" for row in rows),
            "can_materialize_final_decision_now": "false",
            "full_demand_weighted_gjt_required": "false",
            "empirical_missed_connection_probability_required": "false",
            "complete_current_service_nonregression_required": "false",
            "route_level_demand_weight_sensitivity_required": "false",
            "decision_semantics": "Use only certified V3 accessibility, exact production, deterministic connection/block robustness, field-uncertainty and explicitly labelled current-service lower-bound evidence; make no claims of unavailable passenger GJT, empirical reliability or complete-current-service non-regression.",
        },
    ]
    return result


def build(args: argparse.Namespace) -> dict[str, object]:
    cfg = read_json(args.config)
    if cfg.get("contract") != CONTRACT:
        raise ValueError("unexpected closure-gate contract")
    if set(cfg.get("allowed_states", [])) != ALLOWED_STATES:
        raise ValueError("allowed blocker-state universe changed")
    if cfg.get("preserve_all_plan_contexts_until_final_decision") is not True:
        raise ValueError("closure gate must preserve all contexts")
    new_policy = cfg.get("new_blocker_creation_policy", {})
    if new_policy.get("blocker_universe_closed") is not True or new_policy.get("new_blocker_creation_authorized") is not False:
        raise ValueError("new-blocker freeze policy changed")

    sources = validate_sources(args, cfg)
    rows = matrix_rows()
    pathways = pathway_rows(rows, cfg)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = output_dir / "final_decision_blocker_matrix_v3.csv"
    pathway_path = output_dir / "final_decision_pathway_summary_v3.csv"
    validation_path = output_dir / "final_decision_sufficiency_gate_v3_validation.json"
    write_csv(matrix_path, MATRIX_FIELDS, rows)
    write_csv(pathway_path, PATHWAY_FIELDS, pathways)

    global_counts = Counter(str(row["global_state"]) for row in rows)
    legacy_counts = Counter(str(row["legacy_v2_state"]) for row in rows)
    v3_counts = Counter(str(row["v3_deterministic_state"]) for row in rows)
    external = cfg["external_sources"]
    result: dict[str, object] = {
        "status": STATUS,
        "contract": CONTRACT,
        "audit_pass": True,
        "blocker_universe_closed": True,
        "new_blocker_creation_authorized": False,
        "new_blocker_creation_requires_gate_reopen": True,
        "new_blocker_creation_allowed_reasons": new_policy["gate_reopen_allowed_only_for"],
        "legacy_field_absence_alone_may_create_new_blocker": False,
        "descriptive_pareto_nonmembership_may_create_new_blocker": False,
        "preserve_all_plan_contexts": True,
        "preserved_plan_context_count": int(cfg["expected_plan_context_count"]),
        "final_decision_pathway_selected": False,
        "can_materialize_final_decision_now": False,
        "final_selection_authorized": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_selected": False,
        "uncertainty_band_selected": False,
        "normative_v3_decision_rule_selected": False,
        "weighted_composite_score": False,
        "manufactured_demand_weighted_gjt": False,
        "manufactured_missed_connection_probability": False,
        "stage_e_or_f_engineering_stress_is_probability": False,
        "municipal_od_spatially_downscaled": False,
        "current_service_lower_bound_relabelled_as_complete": False,
        "stage_f_engineering_sensitivity_closed": True,
        "stage_f_empirical_reliability_created": False,
        "current_service_baseline_state": "CLOSED_WITH_CERTIFIED_BOUND",
        "current_service_complete_nonregression_available": False,
        "full_demand_weighted_gjt_available": False,
        "empirical_missed_connection_probability_available": False,
        "legacy_v2_schema_compatible": False,
        "v3_descriptive_frontier_may_prune": False,
        "global_state_counts": dict(sorted(global_counts.items())),
        "legacy_v2_state_counts": dict(sorted(legacy_counts.items())),
        "v3_deterministic_state_counts": dict(sorted(v3_counts.items())),
        "legacy_v2_technical_open_data_requirement_count": sum(row["legacy_v2_state"] == "OPEN_DATA_EVIDENCE" for row in rows),
        "v3_deterministic_technical_open_data_requirement_count": sum(row["v3_deterministic_state"] == "OPEN_DATA_EVIDENCE" for row in rows),
        "human_decision_requirement_ids_before_final_selection": [
            "HUMAN-001",
            "HUMAN-002",
            "HUMAN-003",
            "HUMAN-004_IF_V3_SELECTED"
        ],
        "finite_next_step_tree": {
            "step_1": "HUMAN_SELECT_FINAL_DECISION_SEMANTICS_PATHWAY",
            "if_legacy_v2": "WAIT_FOR_DATA_001_DATA_002_DATA_003_DATA_004_THEN_SUPPLY_BUDGET_AND_UNCERTAINTY_BAND",
            "if_v3_deterministic": "SUPPLY_BUDGET_UNCERTAINTY_BAND_AND_EXPLICIT_NO_WEIGHT_NORMATIVE_DECISION_RULE",
            "no_other_engineering_task_authorized_by_this_gate": True
        },
        "non_certified_gjt_identifiability_workstream_consumed": False,
        "non_certified_gjt_identifiability_workstream_reason": cfg["non_certified_informative_workstreams"]["gjt_identifiability_bounds_v3"]["reason"],
        "lineage": {
            "config_sha256": sha256_path(args.config),
            "stage_e_validation_sha256": sha256_path(args.stage_e_validation),
            "readiness_validation_sha256": sha256_path(args.readiness_validation),
            "codex_redteam_validation_sha256": sha256_path(args.codex_redteam_validation),
            "legacy_contract_audit_sha256": sha256_path(args.legacy_contract_audit),
            "frontier_validation_sha256": sha256_path(args.frontier_validation),
            "stage_f_source_commit": external["stage_f"]["commit"],
            "stage_f_validation_sha256": sha256_path(args.stage_f_validation),
            "current_service_baseline_source_commit": external["current_service_baseline_v3"]["commit"],
            "current_service_baseline_validation_sha256": sha256_path(args.current_baseline_validation),
            "stage_e_old_vs_new_source_commit": external["stage_e_old_vs_new_audit"]["commit"],
            "stage_e_old_vs_new_validation_sha256": sha256_path(args.old_vs_new_validation),
            "blocker_matrix_sha256": sha256_path(matrix_path),
            "pathway_summary_sha256": sha256_path(pathway_path),
        },
        "decision_boundary": (
            "This gate closes the blocker-discovery phase, not the network decision. "
            "No new engineering blocker is authorized unless the gate is reopened by a certified validation failure, "
            "an explicit selected-contract requirement without a certified source, or a certified lineage contradiction."
        ),
    }
    validation_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/phase2_final_decision_sufficiency_gate_v3.json"))
    p.add_argument("--stage-e-validation", type=Path, default=Path("outputs/phase2/final_operational_robustness_rt001_v3/final_operational_robustness_rt001_v3_validation.json"))
    p.add_argument("--readiness-validation", type=Path, default=Path("outputs/phase2/final_tournament_readiness_rt001_v3/final_tournament_readiness_rt001_v3_validation.json"))
    p.add_argument("--codex-redteam-validation", type=Path, default=Path("outputs/phase2/tournament_readiness_redteam_rt001_v3/tournament_readiness_redteam_rt001_v3_validation.json"))
    p.add_argument("--legacy-contract-audit", type=Path, default=Path("outputs/phase2/tournament_contract_audit_rt001_v3/legacy_v2_tournament_contract_audit_rt001_v3.json"))
    p.add_argument("--frontier-validation", type=Path, default=Path("outputs/phase2/non_decisional_tournament_frontier_rt001_v3/non_decisional_pareto_frontier_rt001_v3_validation.json"))
    p.add_argument("--stage-f-validation", type=Path, default=Path(".decision_gate_sources/stage_f_validation.json"))
    p.add_argument("--current-baseline-validation", type=Path, default=Path(".decision_gate_sources/current_service_baseline_v3_validation.json"))
    p.add_argument("--old-vs-new-validation", type=Path, default=Path(".decision_gate_sources/stage_e_old_vs_new_validation.json"))
    p.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/final_decision_sufficiency_gate_v3"))
    return p


def main() -> None:
    result = build(build_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
