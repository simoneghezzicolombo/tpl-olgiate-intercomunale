#!/usr/bin/env python3
"""Audit the legacy V2 final-tournament schema against certified RT001 V3 evidence."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase2_build_final_tournament_readiness_rt001_v3 import sha256_path
from scripts.phase2_finalize_tournament import REQUIRED_COLUMNS


STATUS = "PASS_PHASE2_LEGACY_TOURNAMENT_CONTRACT_AUDIT_RT001_V3"
CONTRACT = "PHASE2_FIELD_LEVEL_LEGACY_TOURNAMENT_COMPATIBILITY_AUDIT_RT001_V3"
CONTEXT_SOURCE = "outputs/phase2/final_tournament_readiness_rt001_v3/final_tournament_context_readiness_rt001_v3.csv.gz"
STAGE_E_SOURCE = "outputs/phase2/final_operational_robustness_rt001_v3/final_operational_robustness_rt001_v3_validation.json"
BUDGET_SOURCE = "outputs/phase2/final_tournament_readiness_rt001_v3/final_tournament_budget_envelopes_rt001_v3.csv"

AUDIT_FIELDS = [
    "input_object",
    "required_field",
    "legacy_required_semantics",
    "certified_source",
    "certified_source_field",
    "certified_semantics",
    "availability",
    "legacy_compatible",
    "compatibility_reason",
    "v3_permitted_use",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_header(path: Path) -> list[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def identity_counts(path: Path) -> tuple[int, int, int]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    identities = {(row["scenario_id"], row["plan_id"]) for row in rows}
    contexts = {row["plan_context_id"] for row in rows}
    return len(rows), len(identities), len(contexts)


def audit_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    readiness = read_json(args.readiness_validation)
    passenger = read_json(args.passenger_validation)
    continuity = read_json(args.continuity_validation)
    stage_e = read_json(args.stage_e_validation)
    journey = read_json(args.journey_validation)
    header = set(csv_header(args.context_readiness))

    if readiness.get("status") != "PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3":
        raise ValueError("final-tournament readiness audit is not certified PASS")
    if readiness.get("final_tournament_execution_ready") is not False:
        raise ValueError("unexpected final-tournament readiness state")
    if passenger.get("full_gjt_calculated") is not False or journey.get("full_gjt_ready") is not False:
        raise ValueError("full-GJT boundary changed; contract audit must be revised")
    if stage_e.get("delay_sensitivity_is_empirical_probability") is not False:
        raise ValueError("Stage E probability boundary changed; contract audit must be revised")
    if continuity.get("continuity_is_complete_current_service_measure") is not False:
        raise ValueError("continuity completeness boundary changed; contract audit must be revised")

    def row(
        input_object: str,
        required_field: str,
        required_semantics: str,
        source: str,
        source_field: str,
        certified_semantics: str,
        availability: str,
        compatible: bool,
        reason: str,
        permitted: str,
    ) -> dict[str, str]:
        return {
            "input_object": input_object,
            "required_field": required_field,
            "legacy_required_semantics": required_semantics,
            "certified_source": source,
            "certified_source_field": source_field,
            "certified_semantics": certified_semantics,
            "availability": availability,
            "legacy_compatible": str(compatible).lower(),
            "compatibility_reason": reason,
            "v3_permitted_use": permitted,
        }

    context_source = CONTEXT_SOURCE
    rows = [
        row("CandidateKey", "scenario_id", "structural scenario identity", context_source, "scenario_id",
            "certified structural scenario identity", "AVAILABLE", True, "Semantics agree.", "IDENTITY_COMPONENT"),
        row("CandidateKey", "plan_id", "globally unique service-plan identity within scenario", context_source, "plan_id",
            "Passenger Utility plan ID is not global across budget envelopes and can map to different exact timetable selections.",
            "AVAILABLE_WITH_COLLISIONS", False, "The V2 `(scenario_id, plan_id)` key collapses budget-qualified exact timetable contexts.",
            "USE_ONLY_WITH_PLAN_CONTEXT_ID_AND_SELECTED_TIMETABLE_ID"),
        row("CandidateEvaluation", "eligible", "complete final hard-constraint eligibility", "NO_CERTIFIED_SOURCE", "",
            "Exact budget feasibility is certified, but complete current-service non-regression and the full final hard gate are not.",
            "MISSING", False, "Partial hard-gate evidence cannot be promoted to final eligibility.", "REPORT_COMPONENT_EVIDENCE_ONLY"),
        row("CandidateEvaluation", "median_gjt_improvement_min", "median robust demand-weighted GJT improvement", "NO_CERTIFIED_SOURCE", "",
            "Municipal OD is not spatially allocated to routes/passengers; full_gjt_ready=false.", "MISSING", False,
            "No supported candidate-level demand-weighted GJT distribution exists.", "PROHIBITED_TO_IMPUTE"),
        row("CandidateEvaluation", "lower_quantile_gjt_improvement_min", "lower quantile of robust demand-weighted GJT improvement", "NO_CERTIFIED_SOURCE", "",
            "No supported candidate-level demand-weighted GJT distribution exists.", "MISSING", False,
            "A quantile cannot be calculated without the missing GJT sensitivity results.", "PROHIBITED_TO_IMPUTE"),
        row("CandidateEvaluation", "median_missed_connection_probability", "median empirical missed-connection probability", STAGE_E_SOURCE,
            "delay_sensitivity_is_empirical_probability", "false: Stage E is deterministic engineering stress/retention only.",
            "MISSING", False, "Deterministic miss counts or retention shares are not probabilities.", "ENGINEERING_RETENTION_AS_SEPARATE_PARETO_AXIS_ONLY"),
        row("CandidateEvaluation", "annual_bus_km", "one annual production value per V2 candidate identity", context_source,
            "exact_annual_bus_km", "exact selected-timetable production for a budget-qualified plan context", "AVAILABLE_CONTEXT_LEVEL", False,
            "The value is certified but the V2 identity can collapse contexts with different exact timetables/production.", "EXACT_PARETO_AXIS_WITH_V3_IDENTITY"),
        row("CandidateEvaluation", "public_pattern_complexity", "certified public clockface complexity", context_source,
            "public_route_count", "public route count only; not a certified clockface-complexity metric", "PROXY_ONLY", False,
            "Route count cannot silently substitute for the documented complexity construct.", "REPORT_ROUTE_COUNT_ONLY"),
        row("CandidateEvaluation", "unverified_elements", "complete count of unverified candidate elements", context_source,
            "public_explicit_field_check_pending_count + public_operational_unknown_distance_share_lower_bound",
            "two separate partial evidence-quality dimensions with different units", "PARTIAL", False,
            "They cannot be summed into one count without an unsupported rule.", "KEEP_AS_SEPARATE_PARETO_AXES"),
        row("CandidateEvaluation", "retained_existing_stops_share", "complete existing-stop retention share", context_source,
            "retained_current_localizable_cluster_share_lower_bound", "certified localisable lower bound over 7 clusters; not complete service continuity",
            "LOWER_BOUND_ONLY", False, "The V2 field name implies completeness not supported by RT-003 evidence.", "LOWER_BOUND_PARETO_AXIS_WITH_LABEL"),
        row("CandidateEvaluation", "n_sensitivity_runs", "count of integrated final GJT/probability sensitivity runs", "NO_CERTIFIED_SOURCE", "",
            "Stage E has engineering cases and Passenger GJT has a parameter grid, but no integrated final candidate evaluation runs.",
            "MISSING", False, "Independent grids cannot be counted as completed final sensitivity runs.", "REPORT_GRIDS_SEPARATELY"),
        row("BudgetEnvelope", "annual_bus_km_cap", "materialised exact annual bus-km envelope", BUDGET_SOURCE,
            "annual_bus_km_cap", "six exact envelopes retained without normative selection", "AVAILABLE", True,
            "Semantics agree when kept as separate frontier partitions.", "PARTITION_ONLY_NOT_SELECTED"),
        row("DecisionContract", "decision_budget_km", "explicit caller-selected envelope", "CALLER_DECLARED", "",
            "No value supplied and no default authorised.", "PENDING_CALLER_INPUT", True,
            "The legacy requirement is valid but intentionally unsatisfied.", "DO_NOT_SELECT"),
        row("DecisionContract", "uncertainty_band_min", "explicit finite non-negative practical-equivalence band", "CALLER_DECLARED", "",
            "No value supplied and no default authorised.", "PENDING_CALLER_INPUT", True,
            "The legacy requirement is valid but intentionally unsatisfied.", "DO_NOT_SELECT"),
    ]

    required_covered = {item["required_field"] for item in rows if item["input_object"] == "CandidateEvaluation"}
    required_covered.update({"scenario_id", "plan_id"})
    if required_covered != set(REQUIRED_COLUMNS):
        raise ValueError(f"field audit does not exactly cover legacy REQUIRED_COLUMNS: {sorted(set(REQUIRED_COLUMNS) ^ required_covered)}")
    referenced_context_fields = {
        field
        for item in rows
        if item["certified_source"] == context_source
        for field in item["certified_source_field"].split(" + ")
    }
    missing_header = referenced_context_fields - header
    if missing_header:
        raise ValueError(f"readiness context is missing audited source fields: {sorted(missing_header)}")
    return rows


def build(args: argparse.Namespace) -> dict[str, object]:
    rows = audit_rows(args)
    row_count, legacy_identity_count, context_count = identity_counts(args.context_readiness)
    collisions = row_count - legacy_identity_count
    if context_count != row_count or collisions <= 0:
        raise ValueError("expected lossless V3 context identity and proven V2 identity collisions")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "legacy_v2_tournament_input_compatibility_rt001_v3.csv"
    json_path = args.output_dir / "legacy_v2_tournament_contract_audit_rt001_v3.json"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    incompatible = [row["required_field"] for row in rows if row["legacy_compatible"] == "false"]
    result: dict[str, object] = {
        "status": STATUS,
        "contract": CONTRACT,
        "audit_pass": True,
        "legacy_v2_tournament_schema_compatible": False,
        "legacy_v2_finalizer_run_authorized": False,
        "legacy_v2_required_column_count": len(REQUIRED_COLUMNS),
        "audited_input_row_count": len(rows),
        "context_row_count": row_count,
        "v3_unique_plan_context_count": context_count,
        "legacy_unique_scenario_plan_identity_count": legacy_identity_count,
        "rows_collapsed_by_legacy_identity": collisions,
        "incompatible_or_semantically_unsupported_fields": incompatible,
        "full_demand_weighted_gjt_available": False,
        "empirical_missed_connection_probability_available": False,
        "engineering_retention_reinterpreted_as_probability": False,
        "municipal_od_spatially_downscaled": False,
        "weighted_composite_score": False,
        "decision_budget_selected": False,
        "uncertainty_band_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "required_action": "USE_V3_NON_DECISIONAL_PARETO_FRONTIER_CONTRACT_ONLY",
        "lineage": {
            "context_readiness_sha256": sha256_path(args.context_readiness),
            "readiness_validation_sha256": sha256_path(args.readiness_validation),
            "passenger_validation_sha256": sha256_path(args.passenger_validation),
            "continuity_validation_sha256": sha256_path(args.continuity_validation),
            "stage_e_validation_sha256": sha256_path(args.stage_e_validation),
            "journey_validation_sha256": sha256_path(args.journey_validation),
            "budget_envelopes_sha256": sha256_path(args.budget_envelopes),
            "field_audit_output_sha256": sha256_path(csv_path),
        },
    }
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    root = Path("outputs/phase2/final_tournament_readiness_rt001_v3")
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-readiness", type=Path, default=root / "final_tournament_context_readiness_rt001_v3.csv.gz")
    parser.add_argument("--readiness-validation", type=Path, default=root / "final_tournament_readiness_rt001_v3_validation.json")
    parser.add_argument("--budget-envelopes", type=Path, default=root / "final_tournament_budget_envelopes_rt001_v3.csv")
    parser.add_argument("--passenger-validation", type=Path, default=Path("outputs/phase2/passenger_utility_frontier_rt001_v3/passenger_utility_frontier_rt001_v3_validation.json"))
    parser.add_argument("--continuity-validation", type=Path, default=Path("outputs/phase2/current_service_continuity_rt001_v3/current_service_continuity_rt001_v3_validation.json"))
    parser.add_argument("--stage-e-validation", type=Path, default=Path("outputs/phase2/final_operational_robustness_rt001_v3/final_operational_robustness_rt001_v3_validation.json"))
    parser.add_argument("--journey-validation", type=Path, default=Path("outputs/phase2/passenger_gjt_v2/passenger_journey_universe_v2_validation.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/tournament_contract_audit_rt001_v3"))
    return parser


def main() -> None:
    print(json.dumps(build(build_parser().parse_args()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
