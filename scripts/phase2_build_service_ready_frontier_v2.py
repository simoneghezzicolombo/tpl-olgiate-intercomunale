#!/usr/bin/env python3
"""Build a budget-neutral service-ready Phase 2 frontier.

This is the safe upstream universe for budget/policy exploration. It recomputes
Pareto frontiers from all 100,000 operationally valid scenarios for every timing
archetype, without applying the reference-budget feasibility filter.

Compared with the multiblock evidence frontier it adds two primitive production
axes: minimum closed equal-pattern-set cycle distance and runtime. For any fixed
no-extension clockface policy, annual bus-km is monotone in the first primitive
and the fleet lower bound is monotone in cycle runtime plus route count. Thus a
scenario dominated here cannot become Pareto-superior merely because a different
budget envelope, calendar or recovery value is later selected.

No budget, calendar, recovery value, service policy, S8 phase or timetable is
selected here.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

from scripts.phase2_build_robustness_frontier_v2 import (
    EPS,
    MAX_AXES as ROBUSTNESS_MAX_AXES,
    MIN_AXES as ROBUSTNESS_MIN_AXES,
    load_access_non_regression,
    validate_lineage as validate_robustness_inputs,
)
from scripts.phase2_build_multiblock_frontier_v2 import (
    TERRITORIAL_CORE_AXIS,
    TERRITORIAL_EXTERNAL_AXIS,
    load_territorial,
)

STATUS = "PASS_PHASE2_SERVICE_READY_FRONTIER_V2"
CONTRACT = "PHASE2_BUDGET_NEUTRAL_SERVICE_READY_PARETO_V2"
CYCLE_DISTANCE_AXIS = "public_equal_pattern_set_cycle_distance_km_lower_bound"
CYCLE_RUNTIME_AXIS = "public_equal_pattern_set_cycle_runtime_min_lower_bound"
MAX_AXES = (*ROBUSTNESS_MAX_AXES, TERRITORIAL_CORE_AXIS, TERRITORIAL_EXTERNAL_AXIS)
MIN_AXES = (*ROBUSTNESS_MIN_AXES, CYCLE_DISTANCE_AXIS, CYCLE_RUNTIME_AXIS)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def finite_float(row: dict[str, object], field: str) -> float:
    value = float(row[field])
    if not math.isfinite(value):
        raise ValueError(f"Non-finite {field}: {row.get(field)!r}")
    return value


def dominates(a: dict[str, object], b: dict[str, object]) -> bool:
    any_strict = False
    for field in MAX_AXES:
        av, bv = float(a[field]), float(b[field])
        if av < bv - EPS:
            return False
        if av > bv + EPS:
            any_strict = True
    for field in MIN_AXES:
        av, bv = float(a[field]), float(b[field])
        if av > bv + EPS:
            return False
        if av < bv - EPS:
            any_strict = True
    return any_strict


def pareto(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    frontier: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda r: str(r["scenario_id"])):
        if any(dominates(existing, row) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not dominates(row, existing)]
        frontier.append(row)
    frontier.sort(key=lambda r: str(r["scenario_id"]))
    return frontier


def profile_key(row: dict[str, object]) -> tuple:
    return tuple(round(float(row[field]), 12) for field in (*MAX_AXES, *MIN_AXES))


def dedupe_metric_profiles(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple, list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(profile_key(row), []).append(row)
    output: list[dict[str, object]] = []
    for same in groups.values():
        same.sort(key=lambda r: str(r["scenario_id"]))
        representative = dict(same[0])
        representative["equivalent_metric_scenario_ids"] = "|".join(
            str(row["scenario_id"]) for row in same
        )
        representative["equivalent_metric_scenario_count"] = len(same)
        output.append(representative)
    return output


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing empty output {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def load_operational(path: Path, validation_path: Path) -> tuple[dict[str, dict[str, str]], dict]:
    validation = read_json(validation_path)
    if validation.get("status") != "PASS_OPERATIONAL_SCREENING_V2_BUILD":
        raise ValueError("Operational Screening V2 is not PASS")
    if validation.get("contract") != "PHASE2_OPERATIONAL_LOWER_BOUND_SCREENING_V2":
        raise ValueError("Unexpected Operational Screening V2 contract")
    if validation.get("lineage", {}).get("operational_screening_sha256") != sha256_path(path):
        raise ValueError("Operational Screening V2 hash mismatch")
    if int(validation.get("scenario_count", -1)) != 100000:
        raise ValueError("Unexpected operational scenario universe")
    if int(validation.get("operational_pass_count", -1)) != 100000 or int(validation.get("operational_fail_count", -1)) != 0:
        raise ValueError("Service-ready frontier requires the certified all-PASS operational universe")
    if any(validation.get(field) is not False for field in (
        "headway_assumed", "calendar_assumed", "service_days_assumed", "recovery_assumed",
        "fleet_assumed", "extension_share_assumed", "service_policy_selected", "topology_ranked",
        "stop_set_selected", "annual_service_plan_produced",
    )):
        raise ValueError("Operational validation contains a downstream service selection")

    result: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        scenario_id = str(row["scenario_id"])
        if scenario_id in result:
            raise ValueError(f"Duplicate operational scenario {scenario_id}")
        if row.get("operational_screen_status") != "PASS_TO_SERVICE_POLICY_SEARCH":
            raise ValueError(f"Operational scenario {scenario_id} is not PASS")
        for field in (CYCLE_DISTANCE_AXIS, CYCLE_RUNTIME_AXIS):
            if finite_float(row, field) <= 0:
                raise ValueError(f"{scenario_id}: non-positive {field}")
        result[scenario_id] = row
    if len(result) != 100000:
        raise ValueError(f"Expected 100000 operational rows, got {len(result)}")
    return result, validation


def load_reference_frontier(path: Path, validation_path: Path) -> tuple[dict[str, set[str]], dict]:
    validation = read_json(validation_path)
    if validation.get("status") != "PASS_PHASE2_MULTIBLOCK_FRONTIER_V2":
        raise ValueError("Reference-budget multiblock frontier is not PASS")
    if validation.get("contract") != "PHASE2_NO_WEIGHT_MULTIBLOCK_SCENARIO_TIMING_PARETO_V2":
        raise ValueError("Unexpected reference-budget multiblock contract")
    if validation.get("prior_frontier_used_as_filter") is not False:
        raise ValueError("Reference multiblock frontier has invalid filter semantics")
    if validation.get("lineage", {}).get("frontier_output_sha256") != sha256_path(path):
        raise ValueError("Reference multiblock frontier hash mismatch")
    membership: dict[str, set[str]] = {}
    for row in read_csv(path):
        membership.setdefault(str(row["frontier_timing_key"]), set()).add(str(row["scenario_id"]))
    if not membership:
        raise ValueError("Reference multiblock frontier is empty")
    return membership, validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--access-validation", type=Path, required=True)
    parser.add_argument("--pre-gjt", type=Path, required=True)
    parser.add_argument("--pre-gjt-validation", type=Path, required=True)
    parser.add_argument("--current-baseline-validation", type=Path, required=True)
    parser.add_argument("--territorial", type=Path, required=True)
    parser.add_argument("--territorial-validation", type=Path, required=True)
    parser.add_argument("--operational", type=Path, required=True)
    parser.add_argument("--operational-validation", type=Path, required=True)
    parser.add_argument("--reference-frontier", type=Path, required=True)
    parser.add_argument("--reference-frontier-validation", type=Path, required=True)
    parser.add_argument("--frontier-output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()

    for path in vars(args).values():
        if isinstance(path, Path) and path in (args.frontier_output, args.audit_output, args.validation_output):
            continue
        if isinstance(path, Path) and not path.is_file():
            raise FileNotFoundError(path)

    access_val, pre_val, baseline = validate_robustness_inputs(
        access_path=args.access,
        access_validation_path=args.access_validation,
        pre_gjt_path=args.pre_gjt,
        pre_gjt_validation_path=args.pre_gjt_validation,
        baseline_path=args.current_baseline_validation,
    )
    territorial, territorial_val = load_territorial(args.territorial, args.territorial_validation)
    operational, operational_val = load_operational(args.operational, args.operational_validation)
    reference_membership, reference_val = load_reference_frontier(
        args.reference_frontier, args.reference_frontier_validation
    )
    nonreg_pass, nonreg_margin, _ = load_access_non_regression(args.access, baseline)

    timing_rows: dict[tuple[int, str], list[dict[str, object]]] = {}
    timing_counts: dict[tuple[int, str], int] = {}
    seen_scenarios: set[str] = set()
    for raw in read_gzip_csv(args.pre_gjt):
        scenario_id = str(raw["scenario_id"])
        if scenario_id not in territorial or scenario_id not in operational:
            raise ValueError(f"Scenario missing required downstream evidence: {scenario_id}")
        seen_scenarios.add(scenario_id)
        headway = int(raw["uniform_headway_min"])
        span_id = str(raw["span_id"])
        key = (headway, span_id)
        timing_counts[key] = timing_counts.get(key, 0) + 1
        if not nonreg_pass[scenario_id]:
            continue

        op = operational[scenario_id]
        t = territorial[scenario_id]
        complete = (
            int(raw["public_roundtrip_routes_with_complete_match_phase"])
            + int(raw["public_directional_routes_with_complete_match_phase"])
        )
        incomplete = (
            int(raw["public_roundtrip_routes_without_complete_match_phase"])
            + int(raw["public_directional_routes_without_complete_match_phase"])
        )
        row: dict[str, object] = {
            "scenario_id": scenario_id,
            "topology_family": str(raw["topology_family"]),
            "uniform_headway_min": headway,
            "span_id": span_id,
            "span_start_min": int(raw["span_start_min"]),
            "span_end_min": int(raw["span_end_min"]),
            "current_lower_bound_non_regression_pass": True,
            "minimum_worst_municipality_threshold_margin_vs_current_lower_bound": nonreg_margin[scenario_id],
            "s8_complete_supported_route_count": complete,
            "s8_incomplete_supported_route_count": incomplete,
            TERRITORIAL_CORE_AXIS: t["core"],
            TERRITORIAL_EXTERNAL_AXIS: t["external"],
            "territorial_total_worker_mass_upper_bound_reporting_only": t["total"],
            CYCLE_DISTANCE_AXIS: finite_float(op, CYCLE_DISTANCE_AXIS),
            CYCLE_RUNTIME_AXIS: finite_float(op, CYCLE_RUNTIME_AXIS),
            "public_max_single_route_cycle_runtime_min_lower_bound": finite_float(
                op, "public_max_single_route_cycle_runtime_min_lower_bound"
            ),
            "public_closure_added_route_count": int(op["public_closure_added_route_count"]),
            "public_explicit_proposed_stop_count": int(op["public_explicit_proposed_stop_count"]),
            "public_explicit_existing_stop_count": int(op["public_explicit_existing_stop_count"]),
        }
        for field in (*ROBUSTNESS_MAX_AXES[:-1], *ROBUSTNESS_MIN_AXES[1:]):
            row[field] = finite_float(raw, field)
        row["public_explicit_field_check_pending_count"] = int(
            float(raw["public_explicit_field_check_pending_count"])
        )
        row["public_route_count"] = int(raw["public_route_count"])
        timing_rows.setdefault(key, []).append(row)

    if len(seen_scenarios) != 100000:
        raise ValueError(f"Pre-GJT scenario universe changed: {len(seen_scenarios)}")
    if set(timing_counts.values()) != {100000} or len(timing_counts) != 8:
        raise ValueError(f"Unexpected timing row counts: {timing_counts}")

    frontier_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    timing_summary: dict[str, dict[str, object]] = {}
    reference_recovered_total = 0

    for key in sorted(timing_counts):
        headway, span_id = key
        timing_name = f"H{headway}_{span_id}"
        eligible = timing_rows.get(key, [])
        profiles = dedupe_metric_profiles(eligible)
        profile_frontier = pareto(profiles)
        expanded: list[dict[str, object]] = []
        for representative in profile_frontier:
            ids = str(representative["equivalent_metric_scenario_ids"]).split("|")
            id_set = set(ids)
            by_id = {
                str(row["scenario_id"]): row for row in eligible
                if str(row["scenario_id"]) in id_set
            }
            for scenario_id in ids:
                out = dict(by_id[scenario_id])
                out["equivalent_metric_scenario_count"] = int(
                    representative["equivalent_metric_scenario_count"]
                )
                out["frontier_timing_key"] = timing_name
                out["on_reference_budget_multiblock_frontier"] = (
                    "true" if scenario_id in reference_membership.get(timing_name, set()) else "false"
                )
                frontier_rows.append(out)
                expanded.append(out)

        ids = {str(row["scenario_id"]) for row in expanded}
        reference_ids = reference_membership.get(timing_name, set())
        retained_reference = len(ids & reference_ids)
        missing_reference = len(reference_ids - ids)
        outside_reference = len(ids - reference_ids)
        reference_recovered_total += outside_reference
        if missing_reference:
            raise ValueError(
                f"Service-ready universal frontier unexpectedly loses {missing_reference} "
                f"reference-frontier scenarios for {timing_name}"
            )
        families: dict[str, int] = {}
        for row in expanded:
            family = str(row["topology_family"])
            families[family] = families.get(family, 0) + 1
        summary = {
            "rows": timing_counts[key],
            "non_regression_eligible": len(eligible),
            "unique_metric_profile_count": len(profiles),
            "frontier_metric_profile_count": len(profile_frontier),
            "frontier_scenario_count": len(expanded),
            "frontier_family_counts": dict(sorted(families.items())),
            "reference_budget_frontier_scenario_count": len(reference_ids),
            "reference_budget_frontier_retained_count": retained_reference,
            "reference_budget_frontier_missing_count": missing_reference,
            "service_ready_frontier_outside_reference_slice_count": outside_reference,
        }
        timing_summary[timing_name] = summary
        audit_rows.append({
            "timing_key": timing_name,
            **{k: v for k, v in summary.items() if k != "frontier_family_counts"},
            "frontier_family_counts_json": json.dumps(summary["frontier_family_counts"], sort_keys=True),
        })

    frontier_rows.sort(
        key=lambda row: (
            int(row["uniform_headway_min"]), str(row["span_id"]), str(row["scenario_id"])
        )
    )
    write_csv(args.frontier_output, frontier_rows)
    write_csv(args.audit_output, audit_rows)

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "candidate_scenario_count": 100000,
        "timing_archetype_count": 8,
        "timing_frontiers": timing_summary,
        "frontier_row_count_all_timings": len(frontier_rows),
        "service_ready_frontier_outside_reference_slice_count_all_timings": reference_recovered_total,
        "pareto_maximise_axes": list(MAX_AXES),
        "pareto_minimise_axes": list(MIN_AXES),
        "budget_filter_applied": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "service_policy_selected": False,
        "s8_phase_selected": False,
        "exact_timetable_constructed": False,
        "weighted_composite_score": False,
        "full_gjt_calculated": False,
        "passenger_demand_assigned_to_routes": False,
        "mode_choice_inferred": False,
        "ridership_forecast": False,
        "positive_extensions_selected": False,
        "production_monotonicity_contract": {
            "annual_bus_km": "MONOTONE_IN_CLOSED_EQUAL_PATTERN_SET_CYCLE_DISTANCE_FOR_FIXED_HEADWAY_SPAN_CALENDAR",
            "fleet_lower_bound": "MONOTONE_IN_CYCLE_RUNTIME_AND_ROUTE_COUNT_FOR_FIXED_HEADWAY_RECOVERY",
            "purpose": "SAFE_SUPERSET_FOR_LATER_NO_EXTENSION_POLICY_AND_BUDGET_FRONTIERS",
        },
        "territorial_evaluated_worker_mass": int(territorial_val["evaluated_od_worker_mass"]),
        "lineage": {
            "access": str(args.access),
            "access_sha256": sha256_path(args.access),
            "access_validation": str(args.access_validation),
            "access_validation_sha256": sha256_path(args.access_validation),
            "pre_gjt": str(args.pre_gjt),
            "pre_gjt_sha256": sha256_path(args.pre_gjt),
            "pre_gjt_validation": str(args.pre_gjt_validation),
            "pre_gjt_validation_sha256": sha256_path(args.pre_gjt_validation),
            "current_baseline_validation": str(args.current_baseline_validation),
            "current_baseline_validation_sha256": sha256_path(args.current_baseline_validation),
            "territorial": str(args.territorial),
            "territorial_sha256": sha256_path(args.territorial),
            "territorial_validation": str(args.territorial_validation),
            "territorial_validation_sha256": sha256_path(args.territorial_validation),
            "operational": str(args.operational),
            "operational_sha256": sha256_path(args.operational),
            "operational_validation": str(args.operational_validation),
            "operational_validation_sha256": sha256_path(args.operational_validation),
            "reference_frontier": str(args.reference_frontier),
            "reference_frontier_sha256": sha256_path(args.reference_frontier),
            "reference_frontier_validation": str(args.reference_frontier_validation),
            "reference_frontier_validation_sha256": sha256_path(args.reference_frontier_validation),
            "frontier_output": str(args.frontier_output),
            "frontier_output_sha256": sha256_path(args.frontier_output),
            "audit_output": str(args.audit_output),
            "audit_output_sha256": sha256_path(args.audit_output),
        },
        "upstream_statuses": {
            "access": access_val.get("status"),
            "pre_gjt": pre_val.get("status"),
            "territorial": territorial_val.get("status"),
            "operational": operational_val.get("status"),
            "reference_multiblock": reference_val.get("status"),
        },
        "limitations": [
            "This is a budget-neutral safe superset, not a recommendation or service plan.",
            "Calendar, recovery and budget are deliberately unresolved policy inputs.",
            "Cycle distance/runtime are certified operational lower bounds, not exact vehicle blocks.",
            "Territorial worker masses remain structural municipal-OD addressability upper bounds, not bus ridership.",
            "Exact S8 phase, explicit departures and perturbation reliability remain downstream tasks.",
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
