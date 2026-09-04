#!/usr/bin/env python3
"""Build the no-weight Phase 2 multiblock scenario×timing Pareto frontier.

This stage recomputes the frontier from the full hard-eligible universe. It does
NOT filter the already-built robustness frontier and then add territorial OD,
because doing so could lose scenarios that were dominated before the new OD
axes existed.

Evidence blocks kept separate in the Pareto vector:
- walking access and municipal equity;
- S8 complete/incomplete phase support;
- structurally addressable OTHER_CORE municipal OD worker mass;
- structurally addressable represented OTHER_EXTERNAL municipal OD worker mass;
- operational uncertainty, field checks, route distance/runtime and complexity.

No weighted composite, passenger assignment, mode-choice model or full GJT is
introduced.
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
    MAX_AXES as ROBUSTNESS_MAX_AXES,
    MIN_AXES as ROBUSTNESS_MIN_AXES,
    EPS,
    load_access_non_regression,
    validate_lineage as validate_robustness_inputs,
)

STATUS = "PASS_PHASE2_MULTIBLOCK_FRONTIER_V2"
CONTRACT = "PHASE2_NO_WEIGHT_MULTIBLOCK_SCENARIO_TIMING_PARETO_V2"
TERRITORIAL_STATUS = "PASS_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2_BUILD"
TERRITORIAL_CONTRACT = "PHASE2_STRUCTURALLY_ADDRESSABLE_MUNICIPAL_OD_WORKER_MASS_UPPER_BOUND_V2"
TERRITORIAL_CORE_AXIS = "territorial_other_core_worker_mass_upper_bound"
TERRITORIAL_EXTERNAL_AXIS = "territorial_other_external_worker_mass_upper_bound"
MAX_AXES = (*ROBUSTNESS_MAX_AXES, TERRITORIAL_CORE_AXIS, TERRITORIAL_EXTERNAL_AXIS)
MIN_AXES = tuple(ROBUSTNESS_MIN_AXES)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
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


def load_territorial(
    path: Path,
    validation_path: Path,
) -> tuple[dict[str, dict[str, int]], dict]:
    validation = read_json(validation_path)
    if validation.get("status") != TERRITORIAL_STATUS or validation.get("contract") != TERRITORIAL_CONTRACT:
        raise ValueError("Territorial Commuting Addressability V2 is not certified")
    forbidden_true = (
        "passenger_assignment_inferred", "mode_choice_inferred", "ridership_forecast",
        "walking_access_to_exact_home_or_workplace_inferred", "s8_direct_in_primary_territorial_metric",
    )
    if any(validation.get(field) is not False for field in forbidden_true):
        raise ValueError("Territorial epistemic contract changed")
    if validation.get("technical_return_edges_used") is not False:
        raise ValueError("Territorial metric unexpectedly uses technical-return edges")
    if validation.get("lineage", {}).get("output_sha256") != sha256_path(path):
        raise ValueError("Territorial output hash differs from certified validation")
    if int(validation.get("scenario_count", -1)) != 100000:
        raise ValueError("Unexpected territorial scenario universe")
    if int(validation.get("evaluated_other_core_worker_mass", -1)) != 1055:
        raise ValueError("OTHER_CORE territorial mass changed")
    if int(validation.get("evaluated_other_external_worker_mass", -1)) != 800:
        raise ValueError("Represented OTHER_EXTERNAL territorial mass changed")

    result: dict[str, dict[str, int]] = {}
    for row in read_gzip_csv(path):
        scenario_id = str(row["scenario_id"])
        if scenario_id in result:
            raise ValueError(f"Duplicate territorial scenario {scenario_id}")
        core = int(row["structurally_addressable_other_core_worker_mass_upper_bound"])
        external = int(row["structurally_addressable_other_external_worker_mass_upper_bound"])
        total = int(row["structurally_addressable_od_worker_mass_upper_bound"])
        if core < 0 or external < 0 or total != core + external:
            raise ValueError(f"{scenario_id}: inconsistent territorial decomposition")
        if core > 1055 or external > 800:
            raise ValueError(f"{scenario_id}: territorial mass exceeds evaluated universe")
        result[scenario_id] = {"core": core, "external": external, "total": total}
    if len(result) != 100000:
        raise ValueError(f"Expected 100000 territorial scenarios, got {len(result)}")
    return result, validation


def load_old_frontier_membership(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in read_csv(path):
        timing = str(row["frontier_timing_key"])
        result.setdefault(timing, set()).add(str(row["scenario_id"]))
    if not result:
        raise ValueError("Prior robustness frontier is empty")
    return result


def validate_old_frontier(path: Path, validation_path: Path) -> dict:
    validation = read_json(validation_path)
    if validation.get("status") != "PASS_PHASE2_ROBUSTNESS_FRONTIER_V2":
        raise ValueError("Prior robustness frontier is not PASS")
    if validation.get("contract") != "PHASE2_NO_WEIGHT_NON_REGRESSION_SCENARIO_TIMING_PARETO_V2":
        raise ValueError("Unexpected prior robustness frontier contract")
    if validation.get("weighted_composite_score") is not False:
        raise ValueError("Prior robustness frontier unexpectedly uses a weighted score")
    if validation.get("lineage", {}).get("frontier_output_sha256") != sha256_path(path):
        raise ValueError("Prior robustness frontier hash mismatch")
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--access-validation", type=Path, required=True)
    parser.add_argument("--pre-gjt", type=Path, required=True)
    parser.add_argument("--pre-gjt-validation", type=Path, required=True)
    parser.add_argument("--current-baseline-validation", type=Path, required=True)
    parser.add_argument("--territorial", type=Path, required=True)
    parser.add_argument("--territorial-validation", type=Path, required=True)
    parser.add_argument("--prior-frontier", type=Path, required=True)
    parser.add_argument("--prior-frontier-validation", type=Path, required=True)
    parser.add_argument("--frontier-output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()

    for path in (
        args.access, args.access_validation, args.pre_gjt, args.pre_gjt_validation,
        args.current_baseline_validation, args.territorial, args.territorial_validation,
        args.prior_frontier, args.prior_frontier_validation,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    access_val, pre_val, baseline = validate_robustness_inputs(
        access_path=args.access,
        access_validation_path=args.access_validation,
        pre_gjt_path=args.pre_gjt,
        pre_gjt_validation_path=args.pre_gjt_validation,
        baseline_path=args.current_baseline_validation,
    )
    territorial, territorial_val = load_territorial(
        args.territorial, args.territorial_validation
    )
    prior_val = validate_old_frontier(args.prior_frontier, args.prior_frontier_validation)
    prior_membership = load_old_frontier_membership(args.prior_frontier)
    nonreg_pass, nonreg_margin, _ = load_access_non_regression(args.access, baseline)

    timing_rows: dict[tuple[int, str], list[dict[str, object]]] = {}
    audit_counts: dict[tuple[int, str], dict[str, int]] = {}
    seen_scenarios: set[str] = set()
    for raw in read_gzip_csv(args.pre_gjt):
        scenario_id = str(raw["scenario_id"])
        if scenario_id not in territorial:
            raise ValueError(f"Pre-GJT scenario missing territorial evidence: {scenario_id}")
        headway = int(raw["uniform_headway_min"])
        span_id = str(raw["span_id"])
        key = (headway, span_id)
        counts = audit_counts.setdefault(
            key, {"rows": 0, "no_extension_feasible": 0, "non_regression_pass": 0, "eligible": 0}
        )
        counts["rows"] += 1
        seen_scenarios.add(scenario_id)
        no_extension = int(raw["reference_budget_feasible_no_extension_policy_count"]) > 0
        if no_extension:
            counts["no_extension_feasible"] += 1
        if nonreg_pass[scenario_id]:
            counts["non_regression_pass"] += 1
        if not (no_extension and nonreg_pass[scenario_id]):
            continue
        counts["eligible"] += 1

        complete = (
            int(raw["public_roundtrip_routes_with_complete_match_phase"])
            + int(raw["public_directional_routes_with_complete_match_phase"])
        )
        incomplete = (
            int(raw["public_roundtrip_routes_without_complete_match_phase"])
            + int(raw["public_directional_routes_without_complete_match_phase"])
        )
        t = territorial[scenario_id]
        row: dict[str, object] = {
            "scenario_id": scenario_id,
            "topology_family": str(raw["topology_family"]),
            "uniform_headway_min": headway,
            "span_id": span_id,
            "span_start_min": int(raw["span_start_min"]),
            "span_end_min": int(raw["span_end_min"]),
            "reference_budget_feasible_no_extension_policy_count": int(
                raw["reference_budget_feasible_no_extension_policy_count"]
            ),
            "current_lower_bound_non_regression_pass": True,
            "minimum_worst_municipality_threshold_margin_vs_current_lower_bound": nonreg_margin[scenario_id],
            "s8_complete_supported_route_count": complete,
            "s8_incomplete_supported_route_count": incomplete,
            TERRITORIAL_CORE_AXIS: t["core"],
            TERRITORIAL_EXTERNAL_AXIS: t["external"],
            "territorial_total_worker_mass_upper_bound_reporting_only": t["total"],
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

    frontier_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    timing_summary: dict[str, dict[str, object]] = {}
    preferred_headway_frontier_count = 0
    recovered_total = 0

    for key in sorted(audit_counts):
        headway, span_id = key
        timing_name = f"H{headway}_{span_id}"
        eligible = timing_rows.get(key, [])
        profiles = dedupe_metric_profiles(eligible)
        profile_frontier = pareto(profiles) if profiles else []
        expanded: list[dict[str, object]] = []
        for representative in profile_frontier:
            ids = str(representative["equivalent_metric_scenario_ids"]).split("|")
            id_set = set(ids)
            by_id = {
                str(row["scenario_id"]): row
                for row in eligible if str(row["scenario_id"]) in id_set
            }
            for scenario_id in ids:
                out = dict(by_id[scenario_id])
                out["equivalent_metric_scenario_count"] = int(
                    representative["equivalent_metric_scenario_count"]
                )
                out["frontier_timing_key"] = timing_name
                out["was_on_prior_robustness_frontier"] = (
                    "true" if scenario_id in prior_membership.get(timing_name, set()) else "false"
                )
                frontier_rows.append(out)
                expanded.append(out)

        new_ids = {str(row["scenario_id"]) for row in expanded}
        old_ids = prior_membership.get(timing_name, set())
        recovered = len(new_ids - old_ids)
        retained_old = len(new_ids & old_ids)
        displaced_old = len(old_ids - new_ids)
        recovered_total += recovered
        if headway <= 30:
            preferred_headway_frontier_count += len(expanded)

        families: dict[str, int] = {}
        for row in expanded:
            family = str(row["topology_family"])
            families[family] = families.get(family, 0) + 1
        counts = audit_counts[key]
        summary = {
            **counts,
            "eligible_unique_metric_profile_count": len(profiles),
            "frontier_metric_profile_count": len(profile_frontier),
            "frontier_scenario_count": len(expanded),
            "frontier_family_counts": dict(sorted(families.items())),
            "prior_frontier_scenario_count": len(old_ids),
            "recovered_due_to_territorial_axes_count": recovered,
            "retained_from_prior_frontier_count": retained_old,
            "prior_frontier_displaced_after_multiblock_recompute_count": displaced_old,
        }
        timing_summary[timing_name] = summary
        audit_rows.append({
            "timing_key": timing_name,
            **counts,
            "eligible_unique_metric_profile_count": len(profiles),
            "frontier_metric_profile_count": len(profile_frontier),
            "frontier_scenario_count": len(expanded),
            "prior_frontier_scenario_count": len(old_ids),
            "recovered_due_to_territorial_axes_count": recovered,
            "retained_from_prior_frontier_count": retained_old,
            "prior_frontier_displaced_after_multiblock_recompute_count": displaced_old,
            "frontier_family_counts_json": json.dumps(dict(sorted(families.items())), sort_keys=True),
        })

    if not frontier_rows:
        raise ValueError("All multiblock timing frontiers are empty")
    if preferred_headway_frontier_count <= 0:
        raise ValueError("No <=30 minute multiblock frontier remains")

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
        "timing_frontiers": timing_summary,
        "frontier_row_count_all_timings": len(frontier_rows),
        "frontier_row_count_headway_30_or_better": preferred_headway_frontier_count,
        "recovered_due_to_territorial_axes_count_all_timings": recovered_total,
        "pareto_maximise_axes": list(MAX_AXES),
        "pareto_minimise_axes": list(MIN_AXES),
        "territorial_axis_semantics": {
            TERRITORIAL_CORE_AXIS: "OTHER_CORE worker mass structurally addressable on directed public-anchor graph",
            TERRITORIAL_EXTERNAL_AXIS: "represented OTHER_EXTERNAL worker mass structurally addressable on directed public-anchor graph",
        },
        "territorial_evaluated_worker_mass": int(territorial_val["evaluated_od_worker_mass"]),
        "territorial_evaluated_other_core_worker_mass": int(territorial_val["evaluated_other_core_worker_mass"]),
        "territorial_evaluated_other_external_worker_mass": int(territorial_val["evaluated_other_external_worker_mass"]),
        "territorial_unrepresented_worker_mass_not_scored": int(
            territorial_val["otherwise_territorial_but_destination_not_in_routing_anchor_universe_worker_mass"]
        ),
        "weighted_composite_score": False,
        "full_gjt_calculated": False,
        "passenger_demand_assigned_to_routes": False,
        "mode_choice_inferred": False,
        "ridership_forecast": False,
        "exact_timetable_constructed": False,
        "service_policy_selected": False,
        "technical_return_edges_used_for_territorial_access": False,
        "positive_extensions_in_main_frontier": False,
        "prior_frontier_used_as_filter": False,
        "prior_frontier_role": "AUDIT_COMPARATOR_ONLY_RECOMPUTE_FROM_FULL_HARD_ELIGIBLE_UNIVERSE",
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
            "prior_frontier": str(args.prior_frontier),
            "prior_frontier_sha256": sha256_path(args.prior_frontier),
            "prior_frontier_validation": str(args.prior_frontier_validation),
            "prior_frontier_validation_sha256": sha256_path(args.prior_frontier_validation),
            "frontier_output": str(args.frontier_output),
            "frontier_output_sha256": sha256_path(args.frontier_output),
            "audit_output": str(args.audit_output),
            "audit_output_sha256": sha256_path(args.audit_output),
        },
        "limitations": [
            "Territorial worker masses are structural municipal OD addressability upper bounds, not predicted bus passengers.",
            "SELF is excluded because exact submunicipal workplace geography is unavailable.",
            "S8_DIRECT is excluded from the territorial axes and remains in the separate feeder evidence block.",
            "OTHER_EXTERNAL destinations absent from the V2 routing-anchor universe are not imputed or scored.",
            "The current-service non-regression safeguard remains a certified localizable lower bound and is currently non-binding.",
            "This frontier is still scenario×timing evidence, not an exact timetable or vehicle-block plan.",
        ],
        "upstream_statuses": {
            "access": access_val.get("status"),
            "pre_gjt": pre_val.get("status"),
            "prior_robustness": prior_val.get("status"),
            "territorial": territorial_val.get("status"),
        },
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
