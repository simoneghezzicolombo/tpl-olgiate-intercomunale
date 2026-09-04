#!/usr/bin/env python3
"""Independent fail-closed red-team of Codex's RT001 V3 tournament/readiness work.

This audit does not build a competing tournament. It verifies that the Codex
readiness/contract/frontier chain preserves the certified epistemic boundary:
no fabricated demand-weighted GJT, no empirical-probability reinterpretation of
Stage-E engineering stress, no implicit decision inputs and no use of the broad
non-decisional Pareto frontier as a pruning or selection device.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

STATUS = "PASS_PHASE2_CODEX_TOURNAMENT_READINESS_REDTEAM_RT001_V3"
CONTRACT = "PHASE2_FAIL_CLOSED_CODEX_TOURNAMENT_READINESS_SEMANTIC_REDTEAM_RT001_V3"
AUDITED_CODEX_HEAD = "58c228ed614b4fb4d43c15a5c8e12e637074c5f2"

READINESS_STATUS = "PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3"
CONTRACT_AUDIT_STATUS = "PASS_PHASE2_LEGACY_TOURNAMENT_CONTRACT_AUDIT_RT001_V3"
FRONTIER_STATUS = "PASS_PHASE2_NON_DECISIONAL_TOURNAMENT_FRONTIER_RT001_V3"

FINDING_FIELDS = ["finding_id", "status", "subject", "evidence", "semantic_consequence"]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.suffix.lower() in {".csv", ".json"}:
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        return digest.hexdigest()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def strict_false(value: object, *, field: str) -> None:
    if value is not False:
        raise ValueError(f"{field} must remain false, got {value!r}")


def csv_false(row: Mapping[str, str], field: str) -> None:
    if str(row.get(field, "")).strip().lower() != "false":
        raise ValueError(f"{field} must remain false for {row.get('plan_context_id', '<row>')}")


def write_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def verify_hash(actual_path: Path, expected: object, *, label: str) -> None:
    actual = sha256_path(actual_path)
    if str(expected) != actual:
        raise ValueError(f"lineage hash mismatch for {label}: {actual} != {expected}")


def scan_frontier_consumers(root: Path, redteam_script: Path) -> list[str]:
    """Return executable Python consumers of the non-decisional frontier outputs.

    The frontier producer itself is allowed. Tests/docs/workflows are not scanned
    because they are validation/documentation surfaces, not downstream execution.
    """
    needles = (
        "non_decisional_pareto_frontier_rt001_v3",
        "non_decisional_pareto_membership_rt001_v3",
        "pareto_frontier_member",
    )
    allowed = {
        (root / "scripts/phase2_build_nondeci_tournament_frontier_rt001_v3.py").resolve(),
        redteam_script.resolve(),
    }
    consumers: list[str] = []
    for folder in (root / "scripts", root / "src"):
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.py")):
            resolved = path.resolve()
            if resolved in allowed:
                continue
            text = path.read_text(encoding="utf-8")
            if any(needle in text for needle in needles):
                consumers.append(str(path.relative_to(root)))
    return consumers


def build(args: argparse.Namespace) -> dict[str, object]:
    readiness = read_json(args.readiness_validation)
    audit = read_json(args.contract_audit_validation)
    frontier = read_json(args.frontier_validation)
    contract = read_json(args.frontier_contract)

    if readiness.get("status") != READINESS_STATUS or readiness.get("readiness_audit_pass") is not True:
        raise ValueError("Codex readiness audit is not certified PASS")
    if audit.get("status") != CONTRACT_AUDIT_STATUS or audit.get("audit_pass") is not True:
        raise ValueError("Codex legacy-contract audit is not certified PASS")
    if frontier.get("status") != FRONTIER_STATUS or frontier.get("non_decisional_frontier_build_pass") is not True:
        raise ValueError("Codex non-decisional frontier is not certified PASS")

    # Freeze and verify Codex's own lineage chain.
    verify_hash(args.context_readiness, audit.get("lineage", {}).get("context_readiness_sha256"), label="context readiness -> contract audit")
    verify_hash(args.readiness_validation, audit.get("lineage", {}).get("readiness_validation_sha256"), label="readiness validation -> contract audit")
    verify_hash(args.context_readiness, frontier.get("lineage", {}).get("context_readiness_sha256"), label="context readiness -> frontier")
    verify_hash(args.readiness_validation, frontier.get("lineage", {}).get("readiness_validation_sha256"), label="readiness validation -> frontier")
    verify_hash(args.contract_audit_validation, frontier.get("lineage", {}).get("contract_audit_sha256"), label="contract audit -> frontier")
    verify_hash(args.frontier_contract, frontier.get("lineage", {}).get("frontier_contract_sha256"), label="frontier contract -> frontier")
    verify_hash(args.frontier_csv, frontier.get("lineage", {}).get("frontier_output_sha256"), label="frontier output")
    verify_hash(args.membership_csv, frontier.get("lineage", {}).get("membership_output_sha256"), label="membership output")

    # Fail closed on every selection/probability/GJT availability boundary.
    for obj, name, fields in (
        (readiness, "readiness", (
            "final_tournament_execution_ready", "finalizer_invoked", "candidate_evaluation_rows_materialized",
            "recommendation_materialized", "decision_budget_selected", "uncertainty_band_selected",
            "calendar_selected", "recovery_selected", "primary_selected", "runner_up_selected",
            "weighted_composite_score", "full_demand_weighted_gjt_available",
            "empirical_missed_connection_probability_available", "stage_e_engineering_retention_is_probability",
        )),
        (audit, "contract audit", (
            "legacy_v2_tournament_schema_compatible", "legacy_v2_finalizer_run_authorized",
            "full_demand_weighted_gjt_available", "empirical_missed_connection_probability_available",
            "engineering_retention_reinterpreted_as_probability", "municipal_od_spatially_downscaled",
            "weighted_composite_score", "decision_budget_selected", "uncertainty_band_selected",
            "primary_selection_authorised", "runner_up_selection_authorised",
        )),
        (frontier, "frontier", (
            "legacy_v2_tournament_schema_compatible", "legacy_v2_finalizer_invoked",
            "candidate_evaluation_rows_materialized", "recommendation_materialized",
            "stage_e_engineering_retention_is_probability", "full_demand_weighted_gjt_available",
            "municipal_od_spatially_downscaled", "weighted_composite_score", "decision_budget_selected",
            "uncertainty_band_selected", "calendar_selected", "recovery_selected",
            "primary_selection_authorised", "runner_up_selection_authorised",
        )),
    ):
        for field in fields:
            strict_false(obj.get(field), field=f"{name}.{field}")

    blockers = {item.get("condition") for item in readiness.get("blockers", [])}
    required_blockers = {
        "FULL_DEMAND_WEIGHTED_GJT_UNAVAILABLE",
        "EMPIRICAL_MISSED_CONNECTION_PROBABILITY_UNAVAILABLE",
    }
    if not required_blockers.issubset(blockers):
        raise ValueError("readiness no longer explicitly blocks missing GJT/probability semantics")

    # Field-level schema audit must mark the dangerous legacy constructs unsupported.
    _, audit_rows = csv_rows(args.compatibility_csv)
    by_field = {row["required_field"]: row for row in audit_rows}
    required_semantic_failures = {
        "eligible": "MISSING",
        "median_gjt_improvement_min": "MISSING",
        "lower_quantile_gjt_improvement_min": "MISSING",
        "median_missed_connection_probability": "MISSING",
        "n_sensitivity_runs": "MISSING",
    }
    for field, availability in required_semantic_failures.items():
        row = by_field.get(field)
        if not row or row.get("availability") != availability or row.get("legacy_compatible") != "false":
            raise ValueError(f"legacy field {field} is not fail-closed")
    if by_field["median_gjt_improvement_min"].get("v3_permitted_use") != "PROHIBITED_TO_IMPUTE":
        raise ValueError("demand-weighted GJT is no longer explicitly prohibited from imputation")
    if by_field["median_missed_connection_probability"].get("v3_permitted_use") != "ENGINEERING_RETENTION_AS_SEPARATE_PARETO_AXIS_ONLY":
        raise ValueError("Stage-E retention is no longer kept separate from probability semantics")
    for field in ("decision_budget_km", "uncertainty_band_min"):
        row = by_field.get(field)
        if not row or row.get("availability") != "PENDING_CALLER_INPUT" or row.get("v3_permitted_use") != "DO_NOT_SELECT":
            raise ValueError(f"Decision Contract input {field} was implicitly selected")

    # The context-level readiness pack itself must not contain manufactured metrics.
    context_fields, context_rows = csv_rows(args.context_readiness)
    prohibited_context_fields = {
        "demand_weighted_gjt_improvement_min", "median_gjt_improvement_min",
        "lower_quantile_gjt_improvement_min", "missed_connection_probability",
        "median_missed_connection_probability",
    }
    leaked_context_fields = sorted(prohibited_context_fields.intersection(context_fields))
    if leaked_context_fields:
        raise ValueError(f"manufactured legacy metric columns leaked into readiness pack: {leaked_context_fields}")
    if len(context_rows) != int(readiness.get("represented_plan_context_count", -1)):
        raise ValueError("readiness context count mismatch")
    for row in context_rows:
        for field in (
            "full_demand_weighted_gjt_available", "empirical_missed_connection_probability_available",
            "final_hard_eligibility_evaluated", "final_candidate_evaluation_ready",
            "decision_budget_selected", "uncertainty_band_selected", "primary_selected",
            "runner_up_selected", "weighted_composite_score",
        ):
            csv_false(row, field)

    # Frontier output may expose supported axes only, never legacy finalist metrics.
    frontier_fields, frontier_rows = csv_rows(args.frontier_csv)
    leaked_frontier_fields = sorted(prohibited_context_fields.intersection(frontier_fields))
    if leaked_frontier_fields:
        raise ValueError(f"prohibited final-tournament semantics appear in frontier output: {leaked_frontier_fields}")
    if len(frontier_rows) != int(frontier.get("frontier_context_count", -1)):
        raise ValueError("frontier row count mismatch")
    for row in frontier_rows:
        for field in (
            "decision_budget_selected", "uncertainty_band_selected", "primary_selected", "runner_up_selected",
            "weighted_composite_score", "primary_selection_authorised", "runner_up_selection_authorised",
        ):
            csv_false(row, field)

    membership_fields, membership_rows = csv_rows(args.membership_csv)
    if len(membership_rows) != int(frontier.get("input_context_count", -1)):
        raise ValueError("Pareto membership is not lossless across all input contexts")
    if len({row["plan_context_id"] for row in membership_rows}) != len(membership_rows):
        raise ValueError("Pareto membership lost V3 plan-context identity")
    frontier_members = sum(row.get("pareto_frontier_member") == "true" for row in membership_rows)
    if frontier_members != int(frontier.get("frontier_context_count", -1)):
        raise ValueError("membership/frontier count mismatch")
    dominated_members = len(membership_rows) - frontier_members
    if dominated_members != int(frontier.get("dominated_context_count", -1)):
        raise ValueError("dominated membership count mismatch")
    for row in membership_rows:
        csv_false(row, "decision_budget_selected")
        csv_false(row, "uncertainty_band_selected")
        csv_false(row, "primary_selection_authorised")
        csv_false(row, "runner_up_selection_authorised")

    # Contract-level semantic inspection.
    if contract.get("contract") != "PHASE2_NON_DECISIONAL_CERTIFIED_METRIC_PARETO_FRONTIER_RT001_V3":
        raise ValueError("unexpected frontier contract")
    for field in (
        "weighted_composite_score", "decision_budget_selected", "uncertainty_band_selected",
        "calendar_selected", "recovery_selected", "primary_selection_authorised", "runner_up_selection_authorised",
    ):
        strict_false(contract.get(field), field=f"frontier contract.{field}")
    dimensions = list(contract.get("dimensions", []))
    if len(dimensions) != int(frontier.get("pareto_dimension_count", -1)):
        raise ValueError("frontier dimension count mismatch")
    dimension_fields = [str(item.get("field", "")) for item in dimensions]
    if any("demand_weighted_gjt" in field or "missed_connection_probability" in field for field in dimension_fields):
        raise ValueError("unsupported GJT/probability semantics entered Pareto dimensions")
    if any("weight" in item for item in dimensions):
        raise ValueError("Pareto contract dimension unexpectedly defines a weight")
    prohibited_reinterpretations = "\n".join(map(str, contract.get("prohibited_reinterpretations", []))).lower()
    for phrase in ("probability", "passenger demand", "demand-weighted gjt"):
        if phrase not in prohibited_reinterpretations:
            raise ValueError(f"frontier contract lost prohibited reinterpretation guard for {phrase}")

    root = args.repo_root.resolve()
    consumers = scan_frontier_consumers(root, Path(__file__))
    if consumers:
        raise ValueError(f"non-decisional frontier has executable downstream consumers: {consumers}")

    # Lower-bound descriptors can be compared as reported metrics, but they do
    # not establish latent true-system dominance and therefore cannot authorize pruning.
    lower_bound_axes = [field for field in dimension_fields if "lower_bound" in field]
    if not lower_bound_axes:
        raise ValueError("expected explicit lower-bound descriptors in frontier contract")

    findings = [
        {
            "finding_id": "TR-001",
            "status": "PASS",
            "subject": "Demand-weighted GJT",
            "evidence": "Certified lineage states full GJT unavailable; legacy GJT fields are MISSING and absent from readiness/frontier outputs.",
            "semantic_consequence": "No demand_weighted_gjt_improvement_min or equivalent finalist utility was manufactured.",
        },
        {
            "finding_id": "TR-002",
            "status": "PASS",
            "subject": "Missed-connection probability",
            "evidence": "Stage-E retention remains deterministic engineering evidence and the legacy probability field is MISSING.",
            "semantic_consequence": "Engineering stress/misses are not empirical probabilities.",
        },
        {
            "finding_id": "TR-003",
            "status": "PASS",
            "subject": "Legacy V2 finalizer",
            "evidence": f"V2 schema incompatible; {audit.get('rows_collapsed_by_legacy_identity')} contexts would be collapsed by legacy identity.",
            "semantic_consequence": "Legacy finalizer is fail-closed and was not invoked.",
        },
        {
            "finding_id": "TR-004",
            "status": "PASS",
            "subject": "Decision Contract inputs",
            "evidence": "decision_budget_km and uncertainty_band_min remain PENDING_CALLER_INPUT / DO_NOT_SELECT.",
            "semantic_consequence": "No budget or uncertainty preference was silently chosen.",
        },
        {
            "finding_id": "TR-005",
            "status": "PASS",
            "subject": "Non-decisional Pareto frontier",
            "evidence": f"{len(membership_rows)} contexts retained in membership; {frontier_members} non-dominated and {dominated_members} dominated on reported axes.",
            "semantic_consequence": "Frontier membership is descriptive only; all contexts remain auditable.",
        },
        {
            "finding_id": "TR-006",
            "status": "PASS_WITH_EPISTEMIC_LIMIT",
            "subject": "Lower-bound axes",
            "evidence": ", ".join(lower_bound_axes),
            "semantic_consequence": "Dominance is only over reported certified descriptors, not proof of latent true-system dominance; non-frontier pruning is unauthorized.",
        },
        {
            "finding_id": "TR-007",
            "status": "PASS",
            "subject": "Downstream pruning/selection consumer",
            "evidence": "No executable Python consumer of frontier membership/output exists outside the frontier producer in the audited Codex head.",
            "semantic_consequence": "The 4,211 dominated contexts are not currently pruned from a downstream tournament.",
        },
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    findings_path = args.output_dir / "tournament_readiness_redteam_findings_rt001_v3.csv"
    validation_path = args.output_dir / "tournament_readiness_redteam_rt001_v3_validation.json"
    write_csv(findings_path, FINDING_FIELDS, findings)

    result: dict[str, object] = {
        "status": STATUS,
        "contract": CONTRACT,
        "audit_pass": True,
        "audited_codex_head": AUDITED_CODEX_HEAD,
        "codex_readiness_status": readiness["status"],
        "codex_contract_audit_status": audit["status"],
        "codex_frontier_status": frontier["status"],
        "final_tournament_execution_ready": False,
        "final_selection_authorized": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_selected": False,
        "uncertainty_band_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "weighted_composite_score": False,
        "manufactured_demand_weighted_gjt": False,
        "manufactured_missed_connection_probability": False,
        "stage_e_engineering_retention_reinterpreted_as_probability": False,
        "municipal_od_spatially_downscaled": False,
        "legacy_v2_finalizer_authorized": False,
        "legacy_v2_finalizer_invoked": False,
        "frontier_is_descriptive_only": True,
        "frontier_is_ranking": False,
        "frontier_is_shortlist": False,
        "frontier_membership_may_authorize_pruning": False,
        "nonfrontier_pruning_authorized": False,
        "lower_bound_axes_establish_true_system_dominance": False,
        "downstream_frontier_executable_consumer_count": len(consumers),
        "input_context_count": len(membership_rows),
        "frontier_context_count": frontier_members,
        "dominated_context_count": dominated_members,
        "legacy_rows_collapsed_by_v2_identity": int(audit.get("rows_collapsed_by_legacy_identity", -1)),
        "pareto_dimension_count": len(dimensions),
        "lower_bound_axis_count": len(lower_bound_axes),
        "lower_bound_axes": lower_bound_axes,
        "finding_count": len(findings),
        "epistemic_limitations": [
            "Pareto dominance is defined only on the reported certified axes and must not be reinterpreted as latent true-system dominance.",
            "Lower-bound continuity/uncertainty descriptors do not authorize elimination of alternatives whose unobserved true values remain unresolved.",
            "The descriptive frontier cannot substitute for the missing full demand-weighted GJT, empirical reliability, complete current-service non-regression or caller-declared Decision Contract inputs.",
        ],
        "required_downstream_rule": "PRESERVE_ALL_16495_CONTEXTS_UNTIL_A_SEPARATELY_CERTIFIED_PRUNING_OR_FINAL_DECISION_CONTRACT_AUTHORIZES_ELIMINATION",
        "lineage": {
            "readiness_validation_sha256": sha256_path(args.readiness_validation),
            "context_readiness_sha256": sha256_path(args.context_readiness),
            "contract_audit_validation_sha256": sha256_path(args.contract_audit_validation),
            "compatibility_csv_sha256": sha256_path(args.compatibility_csv),
            "frontier_contract_sha256": sha256_path(args.frontier_contract),
            "frontier_validation_sha256": sha256_path(args.frontier_validation),
            "frontier_csv_sha256": sha256_path(args.frontier_csv),
            "membership_csv_sha256": sha256_path(args.membership_csv),
            "findings_output_sha256": sha256_path(findings_path),
        },
    }
    validation_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    ready = Path("outputs/phase2/final_tournament_readiness_rt001_v3")
    audit = Path("outputs/phase2/tournament_contract_audit_rt001_v3")
    frontier = Path("outputs/phase2/non_decisional_tournament_frontier_rt001_v3")
    parser.add_argument("--readiness-validation", type=Path, default=ready / "final_tournament_readiness_rt001_v3_validation.json")
    parser.add_argument("--context-readiness", type=Path, default=ready / "final_tournament_context_readiness_rt001_v3.csv.gz")
    parser.add_argument("--contract-audit-validation", type=Path, default=audit / "legacy_v2_tournament_contract_audit_rt001_v3.json")
    parser.add_argument("--compatibility-csv", type=Path, default=audit / "legacy_v2_tournament_input_compatibility_rt001_v3.csv")
    parser.add_argument("--frontier-contract", type=Path, default=Path("config/phase2_nondeci_tournament_frontier_rt001_v3.json"))
    parser.add_argument("--frontier-validation", type=Path, default=frontier / "non_decisional_pareto_frontier_rt001_v3_validation.json")
    parser.add_argument("--frontier-csv", type=Path, default=frontier / "non_decisional_pareto_frontier_rt001_v3.csv.gz")
    parser.add_argument("--membership-csv", type=Path, default=frontier / "non_decisional_pareto_membership_rt001_v3.csv.gz")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/tournament_readiness_redteam_rt001_v3"))
    return parser


def main() -> None:
    print(json.dumps(build(build_parser().parse_args()), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
