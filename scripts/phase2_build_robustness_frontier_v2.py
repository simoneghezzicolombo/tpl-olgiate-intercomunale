#!/usr/bin/env python3
"""Build no-weight Phase 2 scenario×timing robustness frontiers.

This stage is deliberately pre-service-plan. It applies only evidence-supported
hard safeguards, then computes Pareto frontiers separately for every declared
headway/span timing archetype.

Hard safeguards:
- reference-budget timing has at least one NO-EXTENSION feasible policy;
- candidate public walking access does not make the *worst municipality* worse
  than the proven, localizable current D184+D185 lower bound at 5, 8 or 10 min.

This follows docs/PHASE2_SERVICE_DESIGN_SPEC.md. It does not introduce separate
municipality-by-municipality floors. The lower-bound safeguard is asymmetric by
design: unresolved current stops are never imputed and therefore cannot promote
or reject a candidate. With the currently certified localizable baseline, the
worst-municipality lower bound is zero at all three thresholds, so the safeguard
is expected to be non-binding. That does not establish that true current-service
worst-municipality access is zero.

No weighted score is constructed. OD workers are not assigned to routes. S8
enters only through the already-certified route-level complete-match opportunity
counts whose upstream worker reference weights rail direction, not route demand.
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

STATUS = "PASS_PHASE2_ROBUSTNESS_FRONTIER_V2"
CONTRACT = "PHASE2_NO_WEIGHT_NON_REGRESSION_SCENARIO_TIMING_PARETO_V2"
THRESHOLDS = (5, 8, 10)
EPS = 1e-12

MAX_AXES = (
    "public_population_coverage_share_5min",
    "public_population_coverage_share_8min",
    "public_population_coverage_share_10min",
    "public_worst_municipality_coverage_share_5min",
    "public_worst_municipality_coverage_share_8min",
    "public_worst_municipality_coverage_share_10min",
    "s8_complete_supported_route_count",
)
MIN_AXES = (
    "s8_incomplete_supported_route_count",
    "public_operational_unknown_distance_share_lower_bound",
    "public_explicit_field_check_pending_count",
    "public_distance_km",
    "public_runtime_min",
    "public_route_count",
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def _f(row: dict[str, object], field: str) -> float:
    value = float(row[field])
    if not math.isfinite(value):
        raise ValueError(f"Non-finite {field}: {row.get(field)!r}")
    return value


def load_access_non_regression(
    access_path: Path,
    baseline: dict,
) -> tuple[dict[str, bool], dict[str, float], dict[str, str]]:
    """Apply only the specification's worst-municipality safeguard."""
    baseline_worst = {
        threshold: float(baseline["coverage_lower_bound"][str(threshold)]["worst_municipality_coverage_share"])
        for threshold in THRESHOLDS
    }
    required_fields = {
        f"public_worst_municipality_coverage_share_{threshold}min"
        for threshold in THRESHOLDS
    }
    result: dict[str, bool] = {}
    min_margin: dict[str, float] = {}
    fail_reason: dict[str, str] = {}
    for row in read_gzip_csv(access_path):
        scenario_id = str(row["scenario_id"])
        if scenario_id in result:
            raise ValueError(f"Duplicate access scenario {scenario_id}")
        missing = required_fields - set(row)
        if missing:
            raise ValueError(f"Access output lacks worst-municipality fields: {sorted(missing)}")
        margins: list[float] = []
        reasons: list[str] = []
        for threshold in THRESHOLDS:
            candidate = float(row[f"public_worst_municipality_coverage_share_{threshold}min"])
            current_lb = baseline_worst[threshold]
            margin = candidate - current_lb
            margins.append(margin)
            if margin < -EPS:
                reasons.append(f"worst@{threshold}min:{candidate:.12f}<{current_lb:.12f}")
        result[scenario_id] = not reasons
        min_margin[scenario_id] = min(margins)
        fail_reason[scenario_id] = "|".join(reasons)
    if len(result) != 100_000:
        raise ValueError(f"Expected 100000 access scenarios, got {len(result)}")
    return result, min_margin, fail_reason


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
    """Incremental exact skyline; deterministic by stable scenario sort."""
    frontier: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda r: str(r["scenario_id"])):
        if any(dominates(existing, row) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not dominates(row, existing)]
        frontier.append(row)
    frontier.sort(key=lambda r: str(r["scenario_id"]))
    return frontier


def profile_key(row: dict[str, object]) -> tuple:
    return tuple(round(float(row[f]), 12) for f in (*MAX_AXES, *MIN_AXES))


def dedupe_metric_profiles(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Retain every scenario ID through a representative+equivalent IDs field."""
    groups: dict[tuple, list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(profile_key(row), []).append(row)
    output: list[dict[str, object]] = []
    for same in groups.values():
        same.sort(key=lambda r: str(r["scenario_id"]))
        rep = dict(same[0])
        rep["equivalent_metric_scenario_ids"] = "|".join(str(r["scenario_id"]) for r in same)
        rep["equivalent_metric_scenario_count"] = len(same)
        output.append(rep)
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
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_lineage(
    *,
    access_path: Path,
    access_validation_path: Path,
    pre_gjt_path: Path,
    pre_gjt_validation_path: Path,
    baseline_path: Path,
) -> tuple[dict, dict, dict]:
    access = read_json(access_validation_path)
    pre = read_json(pre_gjt_validation_path)
    baseline = read_json(baseline_path)
    if access.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD":
        raise ValueError("Access Equity V2 is not PASS")
    bridge = access.get("hub_access_bridge", {})
    if bridge.get("status") != "VERIFIED_APPLIED" or bridge.get("scope") != "PEDESTRIAN_ACCESS_ONLY":
        raise ValueError("Verified FS hub-access bridge missing")
    if bridge.get("official_bus_stop_id") != "L00407" or bridge.get("physical_cluster_id") != "EX_039":
        raise ValueError("Unexpected FS hub-access bridge identity")
    if access.get("lineage", {}).get("scenario_output_sha256") != sha256_path(access_path):
        raise ValueError("Access output hash mismatch")
    if pre.get("status") != "PASS_PRE_GJT_MULTI_LAYER_SCREENING_V2_BUILD":
        raise ValueError("Pre-GJT V2 is not PASS")
    if pre.get("lineage", {}).get("access_sha256") != sha256_path(access_path):
        raise ValueError("Pre-GJT does not consume corrected access output")
    if pre.get("lineage", {}).get("output_sha256") != sha256_path(pre_gjt_path):
        raise ValueError("Pre-GJT output hash mismatch")
    if pre.get("passenger_demand_assigned_to_routes") is not False or pre.get("full_gjt_calculated") is not False:
        raise ValueError("Pre-GJT epistemic contract changed")
    if baseline.get("status") != "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V2":
        raise ValueError("Current-service lower bound is not PASS")
    if baseline.get("baseline_complete") is not False or baseline.get("may_infer_true_current_total_coverage") is not False:
        raise ValueError("Current-service lower bound lost incompleteness semantics")
    return access, pre, baseline


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--access", type=Path, required=True)
    p.add_argument("--access-validation", type=Path, required=True)
    p.add_argument("--pre-gjt", type=Path, required=True)
    p.add_argument("--pre-gjt-validation", type=Path, required=True)
    p.add_argument("--current-baseline-validation", type=Path, required=True)
    p.add_argument("--frontier-output", type=Path, required=True)
    p.add_argument("--audit-output", type=Path, required=True)
    p.add_argument("--validation-output", type=Path, required=True)
    args = p.parse_args()
    for path in (args.access, args.access_validation, args.pre_gjt, args.pre_gjt_validation, args.current_baseline_validation):
        if not path.is_file():
            raise FileNotFoundError(path)

    access_val, pre_val, baseline = validate_lineage(
        access_path=args.access,
        access_validation_path=args.access_validation,
        pre_gjt_path=args.pre_gjt,
        pre_gjt_validation_path=args.pre_gjt_validation,
        baseline_path=args.current_baseline_validation,
    )
    nr_pass, nr_margin, nr_reason = load_access_non_regression(args.access, baseline)

    timing_rows: dict[tuple[int, str], list[dict[str, object]]] = {}
    audit_counts: dict[tuple[int, str], dict[str, int]] = {}
    seen_scenarios: set[str] = set()
    for raw in read_gzip_csv(args.pre_gjt):
        scenario_id = str(raw["scenario_id"])
        headway = int(raw["uniform_headway_min"])
        span_id = str(raw["span_id"])
        key = (headway, span_id)
        counts = audit_counts.setdefault(key, {"rows": 0, "no_extension_feasible": 0, "non_regression_pass": 0, "eligible": 0})
        counts["rows"] += 1
        seen_scenarios.add(scenario_id)
        no_ext = int(raw["reference_budget_feasible_no_extension_policy_count"]) > 0
        if no_ext:
            counts["no_extension_feasible"] += 1
        if nr_pass[scenario_id]:
            counts["non_regression_pass"] += 1
        if not (no_ext and nr_pass[scenario_id]):
            continue
        counts["eligible"] += 1
        complete = int(raw["public_roundtrip_routes_with_complete_match_phase"]) + int(raw["public_directional_routes_with_complete_match_phase"])
        incomplete = int(raw["public_roundtrip_routes_without_complete_match_phase"]) + int(raw["public_directional_routes_without_complete_match_phase"])
        row: dict[str, object] = {
            "scenario_id": scenario_id,
            "topology_family": str(raw["topology_family"]),
            "uniform_headway_min": headway,
            "span_id": span_id,
            "span_start_min": int(raw["span_start_min"]),
            "span_end_min": int(raw["span_end_min"]),
            "reference_budget_feasible_no_extension_policy_count": int(raw["reference_budget_feasible_no_extension_policy_count"]),
            "current_lower_bound_non_regression_pass": True,
            "minimum_worst_municipality_threshold_margin_vs_current_lower_bound": nr_margin[scenario_id],
            "s8_complete_supported_route_count": complete,
            "s8_incomplete_supported_route_count": incomplete,
        }
        for field in (*MAX_AXES[:-1], *MIN_AXES[1:]):
            row[field] = _f(raw, field)
        row["public_explicit_field_check_pending_count"] = int(float(raw["public_explicit_field_check_pending_count"]))
        row["public_route_count"] = int(raw["public_route_count"])
        timing_rows.setdefault(key, []).append(row)

    if len(seen_scenarios) != 100_000:
        raise ValueError(f"Pre-GJT scenario universe changed: {len(seen_scenarios)}")

    frontier_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    frontier_summary: dict[str, dict[str, object]] = {}
    for key in sorted(audit_counts):
        headway, span_id = key
        eligible = timing_rows.get(key, [])
        profiles = dedupe_metric_profiles(eligible)
        profile_frontier = pareto(profiles) if profiles else []
        expanded: list[dict[str, object]] = []
        for rep in profile_frontier:
            ids = str(rep["equivalent_metric_scenario_ids"]).split("|")
            id_set = set(ids)
            by_id = {str(r["scenario_id"]): r for r in eligible if str(r["scenario_id"]) in id_set}
            for scenario_id in ids:
                out = dict(by_id[scenario_id])
                out["equivalent_metric_scenario_count"] = int(rep["equivalent_metric_scenario_count"])
                out["frontier_timing_key"] = f"H{headway}_{span_id}"
                frontier_rows.append(out)
                expanded.append(out)
        families: dict[str, int] = {}
        for row in expanded:
            fam = str(row["topology_family"])
            families[fam] = families.get(fam, 0) + 1
        counts = audit_counts[key]
        timing_name = f"H{headway}_{span_id}"
        frontier_summary[timing_name] = {
            **counts,
            "eligible_unique_metric_profile_count": len(profiles),
            "frontier_metric_profile_count": len(profile_frontier),
            "frontier_scenario_count": len(expanded),
            "frontier_family_counts": dict(sorted(families.items())),
        }
        audit_rows.append({
            "timing_key": timing_name,
            **counts,
            "eligible_unique_metric_profile_count": len(profiles),
            "frontier_metric_profile_count": len(profile_frontier),
            "frontier_scenario_count": len(expanded),
            "frontier_family_counts_json": json.dumps(dict(sorted(families.items())), sort_keys=True),
        })

    if not frontier_rows:
        raise ValueError("All timing frontiers are empty")
    frontier_rows.sort(key=lambda r: (int(r["uniform_headway_min"]), str(r["span_id"]), str(r["scenario_id"])))
    write_csv(args.frontier_output, frontier_rows)
    write_csv(args.audit_output, audit_rows)

    nr_pass_count = sum(nr_pass.values())
    baseline_worst = {
        str(threshold): float(baseline["coverage_lower_bound"][str(threshold)]["worst_municipality_coverage_share"])
        for threshold in THRESHOLDS
    }
    payload = {
        "status": STATUS,
        "contract": CONTRACT,
        "reference_budget_annual_bus_km": float(pre_val["reference_budget_annual_bus_km"]),
        "candidate_scenario_count": 100000,
        "current_lower_bound_non_regression_pass_scenario_count": nr_pass_count,
        "current_lower_bound_non_regression_fail_scenario_count": 100000 - nr_pass_count,
        "current_baseline_worst_municipality_coverage_share": baseline_worst,
        "non_regression_scope": "WORST_MUNICIPALITY_ACCESS_AT_5_8_10_MINUTES_VS_CERTIFIED_LOCALIZABLE_CURRENT_LOWER_BOUND",
        "non_regression_currently_binding": any(value > EPS for value in baseline_worst.values()),
        "unresolved_current_stops_used": False,
        "positive_extensions_in_main_frontier": False,
        "weighted_composite_score": False,
        "full_gjt_calculated": False,
        "passenger_demand_assigned_to_routes": False,
        "s8_worker_reference_semantics": pre_val["s8_worker_reference_semantics"],
        "pareto_maximise_axes": list(MAX_AXES),
        "pareto_minimise_axes": list(MIN_AXES),
        "timing_frontiers": frontier_summary,
        "lineage": {
            "access": str(args.access), "access_sha256": sha256_path(args.access),
            "access_validation": str(args.access_validation), "access_validation_sha256": sha256_path(args.access_validation),
            "pre_gjt": str(args.pre_gjt), "pre_gjt_sha256": sha256_path(args.pre_gjt),
            "pre_gjt_validation": str(args.pre_gjt_validation), "pre_gjt_validation_sha256": sha256_path(args.pre_gjt_validation),
            "current_baseline_validation": str(args.current_baseline_validation), "current_baseline_validation_sha256": sha256_path(args.current_baseline_validation),
            "frontier_output": str(args.frontier_output), "frontier_output_sha256": sha256_path(args.frontier_output),
            "audit_output": str(args.audit_output), "audit_output_sha256": sha256_path(args.audit_output),
        },
        "limitations": [
            "The current-service comparison is intentionally only a certified localizable lower bound; unresolved D184/D185 stop rows are not spatially imputed.",
            "The non-regression safeguard is currently non-binding because the certified localizable current worst-municipality lower bound is zero at 5, 8 and 10 minutes; this does not establish that true current-service worst-municipality access is zero.",
            "This frontier compares scenario×timing evidence, not exact vehicle blocks or a final service plan.",
            "S8 complete-match opportunity is route-level phase support, not full generalized journey time.",
            "The 1,882-worker S8 reference weights rail directions upstream and is not assigned to bus routes.",
            "Positive scheduled-extension shares are excluded from the main frontier and must remain a separate upper-bound sensitivity.",
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": STATUS,
        "non_regression_pass_scenarios": nr_pass_count,
        "current_baseline_worst_municipality_coverage_share": baseline_worst,
        "timing_frontiers": frontier_summary,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
