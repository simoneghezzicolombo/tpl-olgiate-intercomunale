#!/usr/bin/env python3
"""Finite Phase 2 decision-sufficiency and blocker-closure gate.

This audit never ranks or selects a network. It freezes the current blocker
universe, separates certified evidence gaps from human policy choices, and
reports two explicit decision pathways without silently selecting either one.
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
    "requirement_id", "requirement", "certified_source", "certified_evidence_semantics",
    "global_state", "legacy_v2_state", "v3_deterministic_state",
    "engineering_work_authorized_now", "human_action_required", "notes",
]
PATHWAY_FIELDS = [
    "pathway_id", "pathway_selected", "technical_open_data_requirement_count",
    "human_decision_requirement_count_after_pathway_selection", "not_required_requirement_count",
    "can_materialize_final_decision_now", "full_demand_weighted_gjt_required",
    "empirical_missed_connection_probability_required", "complete_current_service_nonregression_required",
    "route_level_demand_weight_sensitivity_required", "decision_semantics",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def require_bool(obj: Mapping[str, object], field: str, expected: bool, source: str) -> None:
    if obj.get(field) is not expected:
        raise ValueError(f"{source}: expected {field}={str(expected).lower()}")


def validate_sources(args: argparse.Namespace, cfg: Mapping[str, object]) -> dict[str, dict]:
    s = {
        "stage_e": read_json(args.stage_e_validation),
        "readiness": read_json(args.readiness_validation),
        "codex_redteam": read_json(args.codex_redteam_validation),
        "legacy_contract_audit": read_json(args.legacy_contract_audit),
        "frontier": read_json(args.frontier_validation),
        "stage_f": read_json(args.stage_f_validation),
        "current_baseline": read_json(args.current_baseline_validation),
        "old_vs_new": read_json(args.old_vs_new_validation),
    }
    n_contexts = int(cfg["expected_plan_context_count"])

    e = s["stage_e"]
    if e.get("status") != "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3":
        raise ValueError("Stage E RT001 V3 is not certified PASS")
    for field in ("stage_d_cross_implementation_audit_pass", "stage_d_fixture_is_final_selection_lineage", "planned_connection_identity_preserved"):
        require_bool(e, field, True, "Stage E")
    for field in ("delay_sensitivity_is_empirical_probability", "passenger_weighting_applied", "municipal_od_downscaled", "final_selection_authorized"):
        require_bool(e, field, False, "Stage E")
    if int(e.get("represented_plan_context_count", -1)) != n_contexts or int(e.get("selected_exact_timetable_count", -1)) != 6000:
        raise ValueError("Stage E certified universe changed")

    r = s["readiness"]
    if r.get("status") != "PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3":
        raise ValueError("tournament readiness is not certified PASS")
    for field in ("final_tournament_execution_ready", "full_demand_weighted_gjt_available", "empirical_missed_connection_probability_available", "candidate_evaluation_rows_materialized", "primary_selected", "runner_up_selected"):
        require_bool(r, field, False, "readiness")
    if int(r.get("represented_plan_context_count", -1)) != n_contexts:
        raise ValueError("readiness context universe changed")

    rt = s["codex_redteam"]
    if rt.get("status") != "PASS_PHASE2_CODEX_TOURNAMENT_READINESS_REDTEAM_RT001_V3":
        raise ValueError("independent tournament red-team is not PASS")
    require_bool(rt, "audit_pass", True, "Codex red-team")
    for field in (
        "manufactured_demand_weighted_gjt", "manufactured_missed_connection_probability",
        "stage_e_engineering_retention_reinterpreted_as_probability", "municipal_od_spatially_downscaled",
        "nonfrontier_pruning_authorized", "frontier_membership_may_authorize_pruning",
    ):
        require_bool(rt, field, False, "Codex red-team")
    if int(rt.get("input_context_count", -1)) != n_contexts:
        raise ValueError("Codex red-team context universe changed")

    legacy = s["legacy_contract_audit"]
    if legacy.get("status") != "PASS_PHASE2_LEGACY_TOURNAMENT_CONTRACT_AUDIT_RT001_V3":
        raise ValueError("legacy contract audit is not PASS")
    for field in ("legacy_v2_tournament_schema_compatible", "legacy_v2_finalizer_run_authorized", "full_demand_weighted_gjt_available", "empirical_missed_connection_probability_available"):
        require_bool(legacy, field, False, "legacy contract audit")

    f = s["frontier"]
    if f.get("status") != "PASS_PHASE2_NON_DECISIONAL_TOURNAMENT_FRONTIER_RT001_V3":
        raise ValueError("V3 descriptive frontier is not PASS")
    for field in ("legacy_v2_finalizer_invoked", "candidate_evaluation_rows_materialized", "recommendation_materialized", "primary_selection_authorised", "runner_up_selection_authorised"):
        require_bool(f, field, False, "frontier")
    if int(f.get("input_context_count", -1)) != n_contexts:
        raise ValueError("frontier context universe changed")

    sf = s["stage_f"]
    if sf.get("status") != "PASS_PHASE2_STAGE_F_ENGINEERING_SENSITIVITY_RT001_V3":
        raise ValueError("Stage F engineering sensitivity is not certified PASS")
    if sf.get("contract") != "PHASE2_STAGE_F_CERTIFIED_ENGINEERING_SENSITIVITY_RT001_V3":
        raise ValueError("unexpected Stage F contract")
    if sf.get("runtime_multiplier") != [0.9, 1.0, 1.1]:
        raise ValueError("Stage F runtime grid changed")
    if sf.get("dwell_per_nonhub_public_stop_occurrence_min") != [0.0, 0.5, 1.0]:
        raise ValueError("Stage F dwell grid changed")
    if sf.get("rail_event_clock_shift_min") != [-5.0, 0.0, 5.0]:
        raise ValueError("Stage F rail-shift grid changed")
    if sf.get("recovery_minutes") != [5, 10, 15] or int(sf.get("stress_case_count_per_timetable", -1)) != 81:
        raise ValueError("Stage F sensitivity grid is incomplete")
    if int(sf.get("selected_exact_timetable_count", -1)) != 6000 or int(sf.get("represented_plan_context_count", -1)) != n_contexts:
        raise ValueError("Stage F universe changed")
    require_bool(sf, "planned_connection_identity_preserved", True, "Stage F")
    for field in (
        "sensitivity_is_empirical_probability", "missed_connection_probability_inferred", "passenger_route_weights_inferred",
        "municipal_od_downscaled", "full_gjt_calculated", "next_target_rebinding_used_as_success",
        "technical_return_used_as_passenger_service", "final_selection_authorized", "primary_selected", "runner_up_selected",
        "weighted_composite_score",
    ):
        require_bool(sf, field, False, "Stage F")

    b = s["current_baseline"]
    if b.get("status") != "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V3":
        raise ValueError("current-service baseline V3 is not certified PASS")
    if b.get("contract") != "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V3":
        raise ValueError("unexpected current-service baseline contract")
    if b.get("baseline_role") != "CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY":
        raise ValueError("current-service lower-bound semantics changed")
    require_bool(b, "baseline_complete", False, "current-service baseline")
    require_bool(b, "may_infer_true_current_total_coverage", False, "current-service baseline")
    if int(b.get("target_pdf_stop_rows", -1)) != 51 or int(b.get("localized_rows", -1)) != 15 or int(b.get("unresolved_or_unlocalized_rows", -1)) != 36:
        raise ValueError("current-service V3 localization counts changed")
    expected_safeguard = "CANDIDATE_MAY_BE_REJECTED_ONLY_FOR_REGRESSION_BELOW_PROVEN_LOCALIZABLE_CURRENT_LOWER_BOUND; UNRESOLVED_CURRENT_STOPS_CANNOT_PROMOTE_OR_REJECT"
    if b.get("non_regression_safeguard_semantics") != expected_safeguard:
        raise ValueError("current-service non-regression safeguard semantics changed")

    ovn = s["old_vs_new"]
    if ovn.get("contract") != "PHASE2_SEMANTIC_OLD_VS_RT001_STAGE_E_ROBUSTNESS_AUDIT_V1":
        raise ValueError("unexpected old-vs-new Stage E audit contract")
    if ovn.get("failure_reasons") != []:
        raise ValueError("old-vs-new Stage E audit reports failure")
    require_bool(ovn, "deterministic_rebuild", True, "old-vs-new")
    require_bool(ovn, "bus_runtime_engineering_stress_is_empirical_probability", False, "old-vs-new")
    if int(ovn.get("block_unexplained_comparable_mismatch_count", -1)) != 0 or int(ovn.get("surface_unexplained_comparable_mismatch_count", -1)) != 0:
        raise ValueError("unexplained old-vs-new comparable mismatch remains")
    return s


def row(rid: str, requirement: str, source: str, semantics: str, global_state: str,
        legacy_state: str, v3_state: str, notes: str, human: bool = False) -> dict[str, object]:
    values = (global_state, legacy_state, v3_state)
    if any(value not in ALLOWED_STATES for value in values):
        raise ValueError(f"invalid blocker state for {rid}")
    return {
        "requirement_id": rid,
        "requirement": requirement,
        "certified_source": source,
        "certified_evidence_semantics": semantics,
        "global_state": global_state,
        "legacy_v2_state": legacy_state,
        "v3_deterministic_state": v3_state,
        "engineering_work_authorized_now": "false",
        "human_action_required": str(human).lower(),
        "notes": notes,
    }


def matrix_rows() -> list[dict[str, object]]:
    rows = [
        row("EVID-001", "RT001 lossless exact timetable lineage and independent Stage-D convergence",
            "Stage E RT001 V3 + Stage-D cross-audit lineage",
            "6,000 exact timetables over 16,495 exact-budget contexts with cross-implementation audit PASS",
            "CLOSED", "CLOSED", "CLOSED",
            "No further Stage-D rebuild is required unless a certified lineage contradiction appears."),
        row("EVID-002", "Final-lineage Stage E planned-connection and vehicle-block robustness",
            "Stage E RT001 V3", "Deterministic engineering robustness with frozen planned targets; not empirical probability",
            "CLOSED", "CLOSED", "CLOSED", "Do not reinterpret Stage E as a probability model."),
        row("EVID-003", "Legacy-vs-RT001 Stage E semantic regression audit", "A Stage E OLD-vs-NEW audit",
            "Zero unexplained comparable robustness or block mismatches; out-of-span correction explicitly isolated",
            "CLOSED", "CLOSED", "CLOSED", "The corrected passenger-return rule does not require another rerun."),
        row("EVID-004", "Tournament-readiness semantics and non-decisional Pareto safety",
            "Codex readiness/contract audit + A red-team",
            "No fabricated GJT/probability; descriptive Pareto membership cannot authorize pruning",
            "CLOSED", "CLOSED", "CLOSED", "All 16,495 contexts remain preserved until a separately authorized final decision."),
        row("EVID-005", "Stage F deterministic engineering sensitivity surface", "Stage F Engineering Sensitivity RT001 V3",
            "81 deterministic cases per exact timetable over runtime 0.9/1.0/1.1, dwell 0/0.5/1.0 and rail shift -5/0/+5; recovery 5/10/15 block sensitivity",
            "CLOSED", "CLOSED", "CLOSED", "Closes engineering sensitivity only; it creates neither passenger probabilities nor demand weights."),
        row("EVID-006", "Certified current-service localisable access reference", "Current Service Access Baseline V3",
            "15/51 official D184/D185 rows localized, 36 unresolved; certified localisable access lower bound only",
            "CLOSED_WITH_CERTIFIED_BOUND", "CLOSED_WITH_CERTIFIED_BOUND", "CLOSED_WITH_CERTIFIED_BOUND",
            "The artifact is complete as a certified lower bound and must never be relabeled as complete current service."),
        row("DATA-001", "Complete current-service non-regression / fair candidate-vs-current ordering", "Current Service Access Baseline V3",
            "True total current coverage remains unknown; unresolved current stops cannot promote or reject candidates",
            "OPEN_DATA_EVIDENCE", "OPEN_DATA_EVIDENCE", "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "A V3 decision may proceed only if the selected semantics keep current-service evidence explicitly lower-bound and make no true non-regression claim."),
        row("DATA-002", "Full candidate-level demand-weighted GJT improvement", "Certified tournament readiness + legacy contract audit",
            "full_demand_weighted_gjt_available=false; municipal OD has no authorized route/passenger spatial allocation",
            "OPEN_DATA_EVIDENCE", "OPEN_DATA_EVIDENCE", "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "Do not create a point GJT estimate or route-level demand by proxy."),
        row("DATA-003", "Empirical missed-connection probability", "Stage E/Stage F + certified tournament readiness",
            "Deterministic engineering retention exists; an empirical missed-connection probability does not",
            "OPEN_DATA_EVIDENCE", "OPEN_DATA_EVIDENCE", "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "Do not assign empirical probability mass to engineering stress cases."),
        row("DATA-004", "Route-level demand-weight perturbation sensitivity", "Stage F certified limitations + tournament readiness",
            "No authorized route-level demand attribution exists from municipal OD",
            "OPEN_DATA_EVIDENCE", "OPEN_DATA_EVIDENCE", "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "Stage F engineering sensitivity is complete without inventing demand perturbations."),
        row("HUMAN-001", "Select final decision semantics pathway", "This closure-gate contract",
            "Choose legacy full-evidence semantics or explicitly authorize V3 certified-metrics deterministic-robustness semantics",
            "HUMAN_DECISION_REQUIRED", "HUMAN_DECISION_REQUIRED", "HUMAN_DECISION_REQUIRED",
            "Selecting V3 accepts that the recommendation will not claim full demand-weighted GJT, empirical missed probability or complete-current-service non-regression.", True),
        row("HUMAN-002", "Select decision annual bus-km envelope", "Six exact materialized budget envelopes",
            "Normative caller choice; no implicit largest/default budget is authorized",
            "HUMAN_DECISION_REQUIRED", "HUMAN_DECISION_REQUIRED", "HUMAN_DECISION_REQUIRED",
            "Must match one of the six certified exact annual bus-km envelopes.", True),
        row("HUMAN-003", "Select uncertainty-band semantics/value if retained in the final Decision Contract", "Decision Contract boundary",
            "Caller-declared finite non-negative policy input; no default authorized",
            "HUMAN_DECISION_REQUIRED", "HUMAN_DECISION_REQUIRED", "HUMAN_DECISION_REQUIRED",
            "The gate does not choose or infer a tolerance.", True),
        row("HUMAN-004", "Specify a normative no-weight decision rule over the V3 trade-off set", "V3 non-decisional Pareto contract",
            "Pareto non-dominance exposes trade-offs but does not rank, shortlist or recommend",
            "HUMAN_DECISION_REQUIRED", "NOT_REQUIRED_UNDER_V3_CONTRACT", "HUMAN_DECISION_REQUIRED",
            "If V3 is chosen, supply an explicit policy/lexicographic rule; implementation must not invent hidden weights.", True),
        row("NREQ-001", "Pre-select one recovery value before final network decision", "Stage E/Stage F sensitivity semantics",
            "Recovery 5/10/15 is an engineering sensitivity dimension and is intentionally not selected",
            "NOT_REQUIRED_UNDER_V3_CONTRACT", "NOT_REQUIRED_UNDER_V3_CONTRACT", "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "Recovery may be chosen later as an operational implementation parameter."),
        row("NREQ-002", "Prune the 4,211 descriptive Pareto-nonfrontier contexts", "A Codex Tournament Readiness Red-Team",
            "nonfrontier_pruning_authorized=false; lower-bound axes do not establish latent true-system dominance",
            "NOT_REQUIRED_UNDER_V3_CONTRACT", "NOT_REQUIRED_UNDER_V3_CONTRACT", "NOT_REQUIRED_UNDER_V3_CONTRACT",
            "Preserve all 16,495 contexts until a separately certified final decision contract authorizes elimination."),
    ]
    return sorted(rows, key=lambda item: str(item["requirement_id"]))


def pathway_rows(rows: list[dict[str, object]], cfg: Mapping[str, object]) -> list[dict[str, object]]:
    legacy_open = sum(r["legacy_v2_state"] == "OPEN_DATA_EVIDENCE" for r in rows)
    v3_open = sum(r["v3_deterministic_state"] == "OPEN_DATA_EVIDENCE" for r in rows)
    return [
        {
            "pathway_id": cfg["legacy_v2_pathway_id"], "pathway_selected": "false",
            "technical_open_data_requirement_count": legacy_open,
            "human_decision_requirement_count_after_pathway_selection": 2,
            "not_required_requirement_count": sum(r["legacy_v2_state"] == "NOT_REQUIRED_UNDER_V3_CONTRACT" for r in rows),
            "can_materialize_final_decision_now": "false", "full_demand_weighted_gjt_required": "true",
            "empirical_missed_connection_probability_required": "true", "complete_current_service_nonregression_required": "true",
            "route_level_demand_weight_sensitivity_required": "true",
            "decision_semantics": "Retain legacy evaluated-candidate semantics; wait for missing passenger, reliability, demand-sensitivity and complete-current-service evidence, then supply budget and uncertainty band.",
        },
        {
            "pathway_id": cfg["v3_candidate_pathway_id"], "pathway_selected": "false",
            "technical_open_data_requirement_count": v3_open,
            "human_decision_requirement_count_after_pathway_selection": 3,
            "not_required_requirement_count": sum(r["v3_deterministic_state"] == "NOT_REQUIRED_UNDER_V3_CONTRACT" for r in rows),
            "can_materialize_final_decision_now": "false", "full_demand_weighted_gjt_required": "false",
            "empirical_missed_connection_probability_required": "false", "complete_current_service_nonregression_required": "false",
            "route_level_demand_weight_sensitivity_required": "false",
            "decision_semantics": "Use only certified V3 accessibility, exact production, deterministic connection/block robustness, field uncertainty and explicitly labelled current-service lower-bound evidence; make no unavailable GJT, probability or true-current non-regression claim.",
        },
    ]


def build(args: argparse.Namespace) -> dict[str, object]:
    cfg = read_json(args.config)
    if cfg.get("contract") != CONTRACT or set(cfg.get("allowed_states", [])) != ALLOWED_STATES:
        raise ValueError("closure-gate contract/state universe changed")
    if cfg.get("preserve_all_plan_contexts_until_final_decision") is not True:
        raise ValueError("closure gate must preserve all plan contexts")
    policy = cfg.get("new_blocker_creation_policy", {})
    if policy.get("blocker_universe_closed") is not True or policy.get("new_blocker_creation_authorized") is not False:
        raise ValueError("new-blocker freeze policy changed")
    validate_sources(args, cfg)

    rows = matrix_rows()
    pathways = pathway_rows(rows, cfg)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = args.output_dir / "final_decision_blocker_matrix_v3.csv"
    pathway_path = args.output_dir / "final_decision_pathway_summary_v3.csv"
    validation_path = args.output_dir / "final_decision_sufficiency_gate_v3_validation.json"
    write_csv(matrix_path, MATRIX_FIELDS, rows)
    write_csv(pathway_path, PATHWAY_FIELDS, pathways)

    global_counts = Counter(str(r["global_state"]) for r in rows)
    legacy_counts = Counter(str(r["legacy_v2_state"]) for r in rows)
    v3_counts = Counter(str(r["v3_deterministic_state"]) for r in rows)
    external = cfg["external_sources"]
    result = {
        "status": STATUS,
        "contract": CONTRACT,
        "audit_pass": True,
        "blocker_universe_closed": True,
        "new_blocker_creation_authorized": False,
        "new_blocker_creation_requires_gate_reopen": True,
        "new_blocker_creation_allowed_reasons": policy["gate_reopen_allowed_only_for"],
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
        "current_service_localized_rows": 15,
        "current_service_unresolved_rows": 36,
        "current_service_complete_nonregression_available": False,
        "full_demand_weighted_gjt_available": False,
        "empirical_missed_connection_probability_available": False,
        "legacy_v2_schema_compatible": False,
        "v3_descriptive_frontier_may_prune": False,
        "global_state_counts": dict(sorted(global_counts.items())),
        "legacy_v2_state_counts": dict(sorted(legacy_counts.items())),
        "v3_deterministic_state_counts": dict(sorted(v3_counts.items())),
        "legacy_v2_technical_open_data_requirement_count": sum(r["legacy_v2_state"] == "OPEN_DATA_EVIDENCE" for r in rows),
        "v3_deterministic_technical_open_data_requirement_count": sum(r["v3_deterministic_state"] == "OPEN_DATA_EVIDENCE" for r in rows),
        "human_decision_requirement_ids_before_final_selection": ["HUMAN-001", "HUMAN-002", "HUMAN-003", "HUMAN-004_IF_V3_SELECTED"],
        "finite_next_step_tree": {
            "step_1": "HUMAN_SELECT_FINAL_DECISION_SEMANTICS_PATHWAY",
            "if_legacy_v2": "WAIT_FOR_DATA_001_DATA_002_DATA_003_DATA_004_THEN_SUPPLY_BUDGET_AND_UNCERTAINTY_BAND",
            "if_v3_deterministic": "SUPPLY_BUDGET_UNCERTAINTY_BAND_AND_EXPLICIT_NO_WEIGHT_NORMATIVE_DECISION_RULE",
            "no_other_engineering_task_authorized_by_this_gate": True,
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
        "decision_boundary": "This gate closes blocker discovery, not the network decision. New engineering blockers require a gate reopen caused by certified validation failure, an explicit selected-contract requirement without certified source, or a certified lineage contradiction.",
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
    print(json.dumps(build(build_parser().parse_args()), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
