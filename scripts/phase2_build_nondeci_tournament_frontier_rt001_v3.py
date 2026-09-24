#!/usr/bin/env python3
"""Build the RT001 V3 non-decisional Pareto frontier from certified metrics only."""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import gzip
import json
from pathlib import Path
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase2_build_final_tournament_readiness_rt001_v3 import (
    deterministic_gzip_csv,
    sha256_path,
)


STATUS = "PASS_PHASE2_NON_DECISIONAL_TOURNAMENT_FRONTIER_RT001_V3"
AUDIT_STATUS = "PASS_PHASE2_LEGACY_TOURNAMENT_CONTRACT_AUDIT_RT001_V3"
READINESS_STATUS = "PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3"
EXPECTED_CONTRACT = "PHASE2_NON_DECISIONAL_CERTIFIED_METRIC_PARETO_FRONTIER_RT001_V3"

MEMBERSHIP_FIELDS = [
    "plan_context_id",
    "selected_timetable_id",
    "scenario_id",
    "plan_id",
    "budget_suffix",
    "budget_cap_annual_bus_km",
    "evidence_completeness_class",
    "pareto_partition_id",
    "pareto_frontier_member",
    "pareto_equivalent_metric_vector_count",
    "decision_budget_selected",
    "uncertainty_band_selected",
    "primary_selection_authorised",
    "runner_up_selection_authorised",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def strict_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be true or false, got {value!r}")


def decimal_value(value: object, *, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a finite decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{field} must be a finite decimal")
    return number


def validate_contract(contract: Mapping[str, object], input_fields: set[str]) -> list[dict[str, str]]:
    if contract.get("contract") != EXPECTED_CONTRACT:
        raise ValueError("unexpected V3 non-decisional frontier contract")
    for flag in (
        "weighted_composite_score",
        "decision_budget_selected",
        "uncertainty_band_selected",
        "calendar_selected",
        "recovery_selected",
        "primary_selection_authorised",
        "runner_up_selection_authorised",
    ):
        if contract.get(flag) is not False:
            raise ValueError(f"V3 contract decision boundary violated: {flag}")
    if contract.get("identity_fields") != ["plan_context_id", "selected_timetable_id"]:
        raise ValueError("V3 identity must preserve plan context and exact timetable")
    if contract.get("partition_fields") != ["budget_suffix", "evidence_completeness_class"]:
        raise ValueError("V3 partitions must preserve budget and evidence-completeness semantics")
    dimensions = list(contract.get("dimensions", []))
    if not dimensions:
        raise ValueError("V3 contract requires at least one Pareto dimension")
    fields = [str(item.get("field", "")) for item in dimensions]
    if len(fields) != len(set(fields)) or any(not field for field in fields):
        raise ValueError("V3 contract contains blank or duplicate dimensions")
    missing = set(fields) - input_fields
    if missing:
        raise ValueError(f"readiness input is missing V3 dimensions: {sorted(missing)}")
    for item in dimensions:
        if item.get("direction") not in {"min", "max"}:
            raise ValueError(f"invalid Pareto direction for {item.get('field')}")
        if item.get("required_when") not in {"ALWAYS", "BUS_TO_RAIL_METRIC_PRESENT"}:
            raise ValueError(f"invalid missingness rule for {item.get('field')}")
        if not item.get("source_stage") or not item.get("semantics"):
            raise ValueError(f"incomplete provenance semantics for {item.get('field')}")
    return dimensions


def evidence_class(row: Mapping[str, str]) -> str:
    retention = row["stage_e_bus_to_rail_worst_retention_share_engineering"]
    gap = row["stage_e_bus_to_rail_max_service_gap_increase_min_engineering"]
    observed = int(row["stage_e_bus_to_rail_observed_profile_count"])
    if bool(retention) != bool(gap):
        raise ValueError(f"inconsistent BUS_TO_RAIL missingness for {row['plan_context_id']}")
    if retention:
        if observed <= 0:
            raise ValueError(f"BUS_TO_RAIL metric without observed profile for {row['plan_context_id']}")
        return "BIDIRECTIONAL_ENGINEERING_RETENTION_AVAILABLE"
    if observed != 0:
        raise ValueError(f"missing BUS_TO_RAIL metric with observed profile for {row['plan_context_id']}")
    return "NO_PLANNED_BUS_TO_RAIL_METRIC"


def applicable_dimensions(dimensions: list[dict[str, str]], completeness: str) -> list[dict[str, str]]:
    if completeness == "BIDIRECTIONAL_ENGINEERING_RETENTION_AVAILABLE":
        return dimensions
    return [item for item in dimensions if item["required_when"] == "ALWAYS"]


def metric_vector(row: Mapping[str, str], dimensions: list[dict[str, str]]) -> tuple[Decimal, ...]:
    values = []
    for item in dimensions:
        field = item["field"]
        raw = row[field]
        if raw == "":
            raise ValueError(f"missing applicable Pareto metric {field} for {row['plan_context_id']}")
        if field == "stage_e_any_block_infeasibility_under_sensitivity":
            values.append(Decimal(int(strict_bool(raw, field=field))))
        else:
            values.append(decimal_value(raw, field=field))
    return tuple(values)


def dominates(left: tuple[Decimal, ...], right: tuple[Decimal, ...], dimensions: list[dict[str, str]]) -> bool:
    no_worse = True
    strictly_better = False
    for lv, rv, item in zip(left, right, dimensions):
        if item["direction"] == "max":
            if lv < rv:
                no_worse = False
                break
            strictly_better = strictly_better or lv > rv
        else:
            if lv > rv:
                no_worse = False
                break
            strictly_better = strictly_better or lv < rv
    return no_worse and strictly_better


def pareto_vectors(vectors: set[tuple[Decimal, ...]], dimensions: list[dict[str, str]]) -> set[tuple[Decimal, ...]]:
    def best_first(vector: tuple[Decimal, ...]):
        return tuple(-value if item["direction"] == "max" else value for value, item in zip(vector, dimensions))

    frontier: list[tuple[Decimal, ...]] = []
    for vector in sorted(vectors, key=best_first):
        if any(dominates(existing, vector, dimensions) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not dominates(vector, existing, dimensions)]
        frontier.append(vector)
    return set(frontier)


def build(args: argparse.Namespace) -> dict[str, object]:
    audit = read_json(args.contract_audit)
    readiness = read_json(args.readiness_validation)
    contract = read_json(args.frontier_contract)
    fields, rows = read_csv(args.context_readiness)
    _, budget_rows = read_csv(args.budget_envelopes)

    if audit.get("status") != AUDIT_STATUS or audit.get("audit_pass") is not True:
        raise ValueError("legacy tournament contract audit is not PASS")
    if audit.get("legacy_v2_tournament_schema_compatible") is not False:
        raise ValueError("V3 fallback is allowed only after legacy incompatibility is proven")
    if audit.get("legacy_v2_finalizer_run_authorized") is not False:
        raise ValueError("legacy finalizer unexpectedly authorised")
    if readiness.get("status") != READINESS_STATUS or readiness.get("final_tournament_execution_ready") is not False:
        raise ValueError("readiness boundary changed")
    if sha256_path(args.context_readiness) != audit.get("lineage", {}).get("context_readiness_sha256"):
        raise ValueError("contract audit/context readiness hash mismatch")
    dimensions = validate_contract(contract, set(fields))

    budgets = {row["budget_suffix"]: decimal_value(row["annual_bus_km_cap"], field="annual_bus_km_cap") for row in budget_rows}
    if len(budgets) != int(readiness.get("budget_envelope_count", -1)):
        raise ValueError("budget envelope count mismatch")

    partitions: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    context_ids: set[str] = set()
    for row in rows:
        context_id = row["plan_context_id"]
        if not context_id or context_id in context_ids:
            raise ValueError(f"blank or duplicate V3 context identity: {context_id}")
        context_ids.add(context_id)
        for flag in (
            "final_candidate_evaluation_ready",
            "decision_budget_selected",
            "uncertainty_band_selected",
            "primary_selected",
            "runner_up_selected",
            "weighted_composite_score",
        ):
            if strict_bool(row[flag], field=flag):
                raise ValueError(f"readiness input decision boundary violated: {flag}")
        suffix = row["budget_suffix"]
        if suffix not in budgets:
            raise ValueError(f"unknown budget suffix {suffix}")
        cap = decimal_value(row["budget_cap_annual_bus_km"], field="budget_cap_annual_bus_km")
        if cap != budgets[suffix]:
            raise ValueError(f"budget cap mismatch for {context_id}")
        partitions[(suffix, evidence_class(row))].append(row)

    frontier_rows: list[dict[str, object]] = []
    membership_rows: list[dict[str, object]] = []
    partition_summary: dict[str, dict[str, object]] = {}
    for (suffix, completeness), members in sorted(partitions.items(), key=lambda item: (budgets[item[0][0]], item[0][1])):
        applicable = applicable_dimensions(dimensions, completeness)
        vector_members: dict[tuple[Decimal, ...], list[dict[str, str]]] = defaultdict(list)
        for row in members:
            vector_members[metric_vector(row, applicable)].append(row)
        frontier = pareto_vectors(set(vector_members), applicable)
        partition_id = f"{suffix}|{completeness}"
        frontier_context_count = sum(len(vector_members[vector]) for vector in frontier)
        partition_summary[partition_id] = {
            "budget_suffix": suffix,
            "annual_bus_km_cap": float(budgets[suffix]),
            "evidence_completeness_class": completeness,
            "input_context_count": len(members),
            "unique_metric_vector_count": len(vector_members),
            "frontier_metric_vector_count": len(frontier),
            "frontier_context_count": frontier_context_count,
            "dominated_context_count": len(members) - frontier_context_count,
            "applicable_dimension_count": len(applicable),
            "applicable_dimensions": [item["field"] for item in applicable],
        }
        for vector, equivalent_rows in vector_members.items():
            is_frontier = vector in frontier
            equivalence_count = len(equivalent_rows)
            for row in equivalent_rows:
                membership_rows.append({
                    "plan_context_id": row["plan_context_id"],
                    "selected_timetable_id": row["selected_timetable_id"],
                    "scenario_id": row["scenario_id"],
                    "plan_id": row["plan_id"],
                    "budget_suffix": suffix,
                    "budget_cap_annual_bus_km": row["budget_cap_annual_bus_km"],
                    "evidence_completeness_class": completeness,
                    "pareto_partition_id": partition_id,
                    "pareto_frontier_member": str(is_frontier).lower(),
                    "pareto_equivalent_metric_vector_count": equivalence_count,
                    "decision_budget_selected": "false",
                    "uncertainty_band_selected": "false",
                    "primary_selection_authorised": "false",
                    "runner_up_selection_authorised": "false",
                })
                if is_frontier:
                    output = dict(row)
                    output.update({
                        "evidence_completeness_class": completeness,
                        "pareto_partition_id": partition_id,
                        "pareto_frontier_member": "true",
                        "pareto_equivalent_metric_vector_count": equivalence_count,
                        "primary_selection_authorised": "false",
                        "runner_up_selection_authorised": "false",
                    })
                    frontier_rows.append(output)

    membership_rows.sort(key=lambda row: str(row["plan_context_id"]))
    frontier_rows.sort(key=lambda row: (budgets[str(row["budget_suffix"])], str(row["evidence_completeness_class"]), str(row["plan_context_id"])))
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    frontier_path = output_dir / "non_decisional_pareto_frontier_rt001_v3.csv.gz"
    membership_path = output_dir / "non_decisional_pareto_membership_rt001_v3.csv.gz"
    validation_path = output_dir / "non_decisional_pareto_frontier_rt001_v3_validation.json"
    added_fields = [
        "evidence_completeness_class",
        "pareto_partition_id",
        "pareto_frontier_member",
        "pareto_equivalent_metric_vector_count",
        "primary_selection_authorised",
        "runner_up_selection_authorised",
    ]
    deterministic_gzip_csv(frontier_path, fields + added_fields, frontier_rows)
    deterministic_gzip_csv(membership_path, MEMBERSHIP_FIELDS, membership_rows)

    result: dict[str, object] = {
        "status": STATUS,
        "contract": EXPECTED_CONTRACT,
        "non_decisional_frontier_build_pass": True,
        "legacy_v2_tournament_schema_compatible": False,
        "legacy_v2_finalizer_invoked": False,
        "candidate_evaluation_rows_materialized": False,
        "recommendation_materialized": False,
        "input_context_count": len(rows),
        "frontier_context_count": len(frontier_rows),
        "dominated_context_count": len(rows) - len(frontier_rows),
        "partition_count": len(partitions),
        "budget_envelope_count": len(budgets),
        "evidence_completeness_class_count": len({key[1] for key in partitions}),
        "pareto_dimension_count": len(dimensions),
        "dominance_numeric_semantics": "EXACT_DECIMAL_ZERO_TOLERANCE",
        "missing_value_semantics": "NO_IMPUTATION_SEPARATE_EVIDENCE_COMPLETENESS_PARTITIONS",
        "stage_e_engineering_retention_is_probability": False,
        "full_demand_weighted_gjt_available": False,
        "municipal_od_spatially_downscaled": False,
        "weighted_composite_score": False,
        "decision_budget_selected": False,
        "uncertainty_band_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "partition_summary": partition_summary,
        "decision_boundary": (
            "Frontier membership reports non-dominance only within each budget and evidence-completeness partition. "
            "It is not a rank, utility score, finalist list or recommendation."
        ),
        "lineage": {
            "frontier_contract_sha256": sha256_path(args.frontier_contract),
            "contract_audit_sha256": sha256_path(args.contract_audit),
            "context_readiness_sha256": sha256_path(args.context_readiness),
            "readiness_validation_sha256": sha256_path(args.readiness_validation),
            "budget_envelopes_sha256": sha256_path(args.budget_envelopes),
            "frontier_output_sha256": sha256_path(frontier_path),
            "membership_output_sha256": sha256_path(membership_path),
        },
    }
    validation_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    readiness = Path("outputs/phase2/final_tournament_readiness_rt001_v3")
    audit = Path("outputs/phase2/tournament_contract_audit_rt001_v3")
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier-contract", type=Path, default=Path("config/phase2_nondeci_tournament_frontier_rt001_v3.json"))
    parser.add_argument("--contract-audit", type=Path, default=audit / "legacy_v2_tournament_contract_audit_rt001_v3.json")
    parser.add_argument("--context-readiness", type=Path, default=readiness / "final_tournament_context_readiness_rt001_v3.csv.gz")
    parser.add_argument("--readiness-validation", type=Path, default=readiness / "final_tournament_readiness_rt001_v3_validation.json")
    parser.add_argument("--budget-envelopes", type=Path, default=readiness / "final_tournament_budget_envelopes_rt001_v3.csv")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/non_decisional_tournament_frontier_rt001_v3"))
    return parser


def main() -> None:
    print(json.dumps(build(build_parser().parse_args()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
