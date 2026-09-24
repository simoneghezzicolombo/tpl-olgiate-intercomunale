#!/usr/bin/env python3
"""Build explicit no-weight budget × service-policy Pareto frontiers V2.

The input service-ready frontier is a budget-neutral safe superset.  Each policy
context fixes headway, span, annual service days and recovery.  Within a fixed
context, annual bus-km and the aggregate interlinable fleet lower bound are
comparable operational outcomes and may enter the Pareto vector without hiding
service quantity inside a weighted score.

All six declared budget envelopes are evaluated independently.  No budget,
calendar, recovery value, topology, S8 phase or exact timetable is selected.
Positive scheduled-extension shares are intentionally excluded from this main
surface and remain a separate sensitivity workstream.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.phase2_build_robustness_frontier_v2 import EPS, MIN_AXES as ROBUSTNESS_MIN_AXES
from scripts.phase2_build_service_ready_frontier_v2 import (
    MAX_AXES as EVIDENCE_MAX_AXES,
    CYCLE_RUNTIME_AXIS,
)
from scripts.phase2_run_operational_screening_v2 import load_budget_envelopes
from src.phase2_service_policy_search import (
    PolicyDesign,
    evaluate_policy_for_scenario,
    load_design_space,
)

STATUS = "PASS_PHASE2_BUDGET_POLICY_FRONTIERS_V2"
CONTRACT = "PHASE2_EXPLICIT_POLICY_CONTEXT_BUDGET_PARETO_V2"
BUDGET_SUFFIXES = ("m20pct", "m10pct", "reference", "p10pct", "p20pct", "p30pct")
ANNUAL_KM_AXIS = "annual_bus_km"
FLEET_AXIS = "aggregate_interlinable_fleet_lower_bound"
MAX_AXES = tuple(EVIDENCE_MAX_AXES)
MIN_AXES = (*ROBUSTNESS_MIN_AXES, CYCLE_RUNTIME_AXIS, ANNUAL_KM_AXIS, FLEET_AXIS)


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


def strict_bool(value: object) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Expected explicit boolean, got {value!r}")


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


def pareto(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    frontier: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda r: str(r["scenario_id"])):
        if any(dominates(existing, row) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not dominates(row, existing)]
        frontier.append(row)
    frontier.sort(key=lambda r: str(r["scenario_id"]))
    return frontier


def open_deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def validate_service_ready(path: Path, validation_path: Path) -> dict:
    validation = read_json(validation_path)
    if validation.get("status") != "PASS_PHASE2_SERVICE_READY_FRONTIER_V2":
        raise ValueError("Service-ready frontier is not PASS")
    if validation.get("contract") != "PHASE2_BUDGET_NEUTRAL_SERVICE_READY_PARETO_V2":
        raise ValueError("Unexpected service-ready frontier contract")
    if validation.get("budget_filter_applied") is not False or validation.get("decision_budget_selected") is not False:
        raise ValueError("Service-ready upstream must remain budget neutral")
    if validation.get("service_policy_selected") is not False:
        raise ValueError("Service-ready upstream already selected a policy")
    if validation.get("production_monotonicity_contract", {}).get("purpose") != "SAFE_SUPERSET_FOR_LATER_NO_EXTENSION_POLICY_AND_BUDGET_FRONTIERS":
        raise ValueError("Service-ready monotonicity contract is missing")
    if validation.get("lineage", {}).get("frontier_output_sha256") != sha256_path(path):
        raise ValueError("Service-ready frontier hash mismatch")
    return validation


def validate_policy_inputs(
    *,
    config_path: Path,
    policy_grid_path: Path,
    feasibility_path: Path,
    policy_validation_path: Path,
    operational_path: Path,
) -> tuple[list[PolicyDesign], dict]:
    validation = read_json(policy_validation_path)
    if validation.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD":
        raise ValueError("Service Policy Search V2 is not PASS")
    if validation.get("contract") != "PHASE2_SERVICE_POLICY_FEASIBILITY_SEARCH_V2":
        raise ValueError("Unexpected Service Policy Search V2 contract")
    if int(validation.get("policy_count", -1)) != 288 or int(validation.get("nonextension_applicable_policy_count", -1)) != 72:
        raise ValueError("Unexpected policy universe size")
    if validation.get("service_policy_selected") is not False or validation.get("exact_timetable_constructed") is not False:
        raise ValueError("Service-policy upstream contains downstream selection")
    lineage = validation.get("lineage", {})
    expected_actual = {
        "design space": (lineage.get("design_space_sha256"), sha256_path(config_path)),
        "policy grid": (lineage.get("policy_grid_sha256"), sha256_path(policy_grid_path)),
        "feasibility": (lineage.get("feasibility_output_sha256"), sha256_path(feasibility_path)),
        "operational": (lineage.get("operational_screening_sha256"), sha256_path(operational_path)),
    }
    for label, (expected, actual) in expected_actual.items():
        if expected != actual:
            raise ValueError(f"Service-policy lineage hash mismatch for {label}")

    _, policies = load_design_space(config_path)
    if len(policies) != 288:
        raise ValueError("Generated policy universe does not contain 288 policies")
    grid = list(read_csv(policy_grid_path))
    if len(grid) != 288:
        raise ValueError("Persisted policy grid does not contain 288 policies")
    for policy, row in zip(policies, grid):
        checks = {
            "policy_index": str(policy.policy_index),
            "policy_id": policy.policy_id,
            "uniform_headway_min": str(policy.uniform_headway_min),
            "span_id": policy.span_id,
            "calendar_id": policy.calendar_id,
            "annual_service_days": str(policy.annual_service_days),
            "recovery_min": str(policy.recovery_min),
        }
        for field, expected in checks.items():
            if str(row[field]) != expected:
                raise ValueError(f"Policy-grid mismatch at {policy.policy_id}: {field}")
        if not math.isclose(float(row["extension_share"]), policy.extension_share, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"Policy-grid extension-share mismatch at {policy.policy_id}")
        if strict_bool(row["exact_timetable"]):
            raise ValueError("Policy grid unexpectedly contains exact timetable")
        if strict_bool(row["s8_phase_selected"]):
            raise ValueError("Policy grid unexpectedly selects S8 phase")
    nonextension = [p for p in policies if math.isclose(p.extension_share, 0.0, rel_tol=0.0, abs_tol=1e-12)]
    if len(nonextension) != 72:
        raise ValueError("Expected exactly 72 no-extension policy contexts")
    return nonextension, validation


def load_operational_subset(path: Path, scenario_ids: set[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        scenario_id = str(row["scenario_id"])
        if scenario_id not in scenario_ids:
            continue
        if row.get("operational_screen_status") != "PASS_TO_SERVICE_POLICY_SEARCH":
            raise ValueError(f"Service-ready scenario {scenario_id} is not operational PASS")
        out[scenario_id] = row
    if set(out) != scenario_ids:
        missing = sorted(scenario_ids - set(out))[:5]
        raise ValueError(f"Operational subset missing service-ready scenarios: {missing}")
    return out


def load_feasibility_subset(path: Path, scenario_ids: set[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in read_gzip_csv(path):
        scenario_id = str(row["scenario_id"])
        if scenario_id in scenario_ids:
            out[scenario_id] = row
    if set(out) != scenario_ids:
        missing = sorted(scenario_ids - set(out))[:5]
        raise ValueError(f"Feasibility subset missing service-ready scenarios: {missing}")
    return out


def policy_metric_row(
    *,
    frontier_row: dict[str, str],
    operational_row: dict[str, str],
    policy: PolicyDesign,
) -> dict[str, object]:
    family = str(frontier_row["topology_family"])
    if family != str(operational_row["topology_family"]):
        raise ValueError(f"Topology family mismatch for {frontier_row['scenario_id']}")
    ext_distance = str(operational_row.get("extension_equal_pattern_set_cycle_distance_km_lower_bound", "")).strip()
    ext_runtime = str(operational_row.get("extension_equal_pattern_set_cycle_runtime_min_lower_bound", "")).strip()
    metrics = evaluate_policy_for_scenario(
        policy,
        topology_family=family,
        public_cycle_distance_km=finite_float(operational_row, "public_equal_pattern_set_cycle_distance_km_lower_bound"),
        public_cycle_runtime_min=finite_float(operational_row, "public_equal_pattern_set_cycle_runtime_min_lower_bound"),
        public_route_count=int(operational_row["public_route_count"]),
        extension_cycle_distance_km=None if not ext_distance else float(ext_distance),
        extension_cycle_runtime_min=None if not ext_runtime else float(ext_runtime),
    )
    if metrics is None:
        raise ValueError(f"No-extension policy unexpectedly inapplicable to {family}")
    row: dict[str, object] = dict(frontier_row)
    row.update({
        "policy_index": policy.policy_index,
        "policy_id": policy.policy_id,
        "calendar_id": policy.calendar_id,
        "annual_service_days": policy.annual_service_days,
        "recovery_min": policy.recovery_min,
        "extension_share": 0.0,
        ANNUAL_KM_AXIS: metrics.annual_bus_km,
        FLEET_AXIS: metrics.aggregate_interlinable_fleet_lower_bound,
        "expected_pattern_set_cycle_distance_km": metrics.expected_pattern_set_cycle_distance_km,
        "expected_pattern_set_cycle_runtime_min": metrics.expected_pattern_set_cycle_runtime_min,
    })
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-ready-frontier", type=Path, required=True)
    parser.add_argument("--service-ready-validation", type=Path, required=True)
    parser.add_argument("--operational", type=Path, required=True)
    parser.add_argument("--operational-validation", type=Path, required=True)
    parser.add_argument("--policy-config", type=Path, required=True)
    parser.add_argument("--policy-grid", type=Path, required=True)
    parser.add_argument("--policy-feasibility", type=Path, required=True)
    parser.add_argument("--policy-validation", type=Path, required=True)
    parser.add_argument("--budget-envelopes", type=Path, required=True)
    parser.add_argument("--budget-validation", type=Path, required=True)
    parser.add_argument("--frontier-output", type=Path, required=True)
    parser.add_argument("--context-audit-output", type=Path, required=True)
    parser.add_argument("--presence-output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()
    for path in vars(args).values():
        if isinstance(path, Path) and path in (
            args.frontier_output, args.context_audit_output, args.presence_output, args.validation_output
        ):
            continue
        if isinstance(path, Path) and not path.is_file():
            raise FileNotFoundError(path)

    service_ready_val = validate_service_ready(args.service_ready_frontier, args.service_ready_validation)
    policies, policy_val = validate_policy_inputs(
        config_path=args.policy_config,
        policy_grid_path=args.policy_grid,
        feasibility_path=args.policy_feasibility,
        policy_validation_path=args.policy_validation,
        operational_path=args.operational,
    )
    budget_rows, budget_val = load_budget_envelopes(args.budget_envelopes, args.budget_validation)
    budget_caps = dict(zip(BUDGET_SUFFIXES, [cap for _, cap in budget_rows]))
    policy_caps = [float(v) for v in policy_val["budget_caps_annual_bus_km"]]
    if any(not math.isclose(policy_caps[i], list(budget_caps.values())[i], rel_tol=0.0, abs_tol=1e-8) for i in range(6)):
        raise ValueError("Service-policy and declared budget envelopes differ")

    frontier_rows = list(read_csv(args.service_ready_frontier))
    if len(frontier_rows) != int(service_ready_val["frontier_row_count_all_timings"]):
        raise ValueError("Service-ready frontier row count differs from validation")
    scenario_ids = {str(row["scenario_id"]) for row in frontier_rows}
    operational = load_operational_subset(args.operational, scenario_ids)
    feasibility = load_feasibility_subset(args.policy_feasibility, scenario_ids)

    policies_by_timing: dict[tuple[int, str], list[PolicyDesign]] = defaultdict(list)
    for policy in policies:
        policies_by_timing[(policy.uniform_headway_min, policy.span_id)].append(policy)
    if len(policies_by_timing) != 8 or any(len(v) != 9 for v in policies_by_timing.values()):
        raise ValueError("Expected 8 timing archetypes × 9 no-extension calendar/recovery policies")

    candidates_by_policy: dict[str, list[dict[str, object]]] = defaultdict(list)
    policy_lookup = {p.policy_id: p for p in policies}
    for row in frontier_rows:
        timing = (int(row["uniform_headway_min"]), str(row["span_id"]))
        if timing not in policies_by_timing:
            raise ValueError(f"Unknown frontier timing {timing}")
        scenario_id = str(row["scenario_id"])
        op = operational[scenario_id]
        feas = feasibility[scenario_id]
        for policy in policies_by_timing[timing]:
            candidate = policy_metric_row(frontier_row=row, operational_row=op, policy=policy)
            # Cross-check every declared budget against the persisted lossless mask.
            for suffix, cap in budget_caps.items():
                direct = float(candidate[ANNUAL_KM_AXIS]) <= cap + 1e-8
                mask = int(str(feas[f"feasible_policy_mask_hex_{suffix}"]), 16)
                from_mask = bool(mask & (1 << policy.policy_index))
                if direct != from_mask:
                    raise ValueError(
                        f"{scenario_id}/{policy.policy_id}/{suffix}: recomputed feasibility differs from mask"
                    )
            candidates_by_policy[policy.policy_id].append(candidate)

    if set(candidates_by_policy) != set(policy_lookup):
        missing = sorted(set(policy_lookup) - set(candidates_by_policy))
        raise ValueError(f"Some policy contexts have no service-ready candidates: {missing[:5]}")

    frontier_fields = list(frontier_rows[0].keys()) + [
        "policy_index", "policy_id", "calendar_id", "annual_service_days", "recovery_min",
        "extension_share", ANNUAL_KM_AXIS, FLEET_AXIS,
        "expected_pattern_set_cycle_distance_km", "expected_pattern_set_cycle_runtime_min",
        "budget_suffix", "budget_change_fraction", "budget_cap_annual_bus_km", "policy_context_id",
    ]
    raw, text, writer = open_deterministic_gzip_writer(args.frontier_output, frontier_fields)

    context_audit: list[dict[str, object]] = []
    presence: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    context_frontier_count = 0
    total_frontier_rows = 0
    budget_summary: dict[str, dict[str, object]] = {
        suffix: {
            "frontier_row_count": 0,
            "unique_scenario_ids": set(),
            "unique_scenario_ids_headway_30_or_better": set(),
            "nonempty_policy_context_count": 0,
        }
        for suffix in BUDGET_SUFFIXES
    }
    budget_fraction = dict(zip(BUDGET_SUFFIXES, [fraction for fraction, _ in budget_rows]))

    try:
        for policy in policies:
            candidates = candidates_by_policy[policy.policy_id]
            timing_key = f"H{policy.uniform_headway_min}_{policy.span_id}"
            for suffix in BUDGET_SUFFIXES:
                cap = budget_caps[suffix]
                feasible = [r for r in candidates if float(r[ANNUAL_KM_AXIS]) <= cap + 1e-8]
                frontier = pareto(feasible) if feasible else []
                context_id = f"{suffix}__{policy.policy_id}"
                if frontier:
                    context_frontier_count += 1
                    budget_summary[suffix]["nonempty_policy_context_count"] += 1
                families: dict[str, int] = {}
                for row in frontier:
                    out = dict(row)
                    out.update({
                        "budget_suffix": suffix,
                        "budget_change_fraction": budget_fraction[suffix],
                        "budget_cap_annual_bus_km": cap,
                        "policy_context_id": context_id,
                    })
                    writer.writerow(out)
                    total_frontier_rows += 1
                    scenario_id = str(row["scenario_id"])
                    families[str(row["topology_family"])] = families.get(str(row["topology_family"]), 0) + 1
                    presence[(suffix, timing_key, scenario_id)].add(policy.policy_id)
                    budget_summary[suffix]["frontier_row_count"] += 1
                    budget_summary[suffix]["unique_scenario_ids"].add(scenario_id)
                    if policy.uniform_headway_min <= 30:
                        budget_summary[suffix]["unique_scenario_ids_headway_30_or_better"].add(scenario_id)
                context_audit.append({
                    "budget_suffix": suffix,
                    "budget_change_fraction": budget_fraction[suffix],
                    "budget_cap_annual_bus_km": cap,
                    "policy_id": policy.policy_id,
                    "uniform_headway_min": policy.uniform_headway_min,
                    "span_id": policy.span_id,
                    "calendar_id": policy.calendar_id,
                    "annual_service_days": policy.annual_service_days,
                    "recovery_min": policy.recovery_min,
                    "extension_share": policy.extension_share,
                    "service_ready_candidate_count": len(candidates),
                    "budget_feasible_candidate_count": len(feasible),
                    "frontier_scenario_count": len(frontier),
                    "frontier_family_counts_json": json.dumps(dict(sorted(families.items())), sort_keys=True),
                })
    finally:
        text.flush()
        text.close()
        raw.close()

    if len(context_audit) != 72 * 6:
        raise ValueError(f"Expected 432 policy×budget contexts, got {len(context_audit)}")
    if total_frontier_rows <= 0:
        raise ValueError("All budget-policy frontiers are empty")

    context_audit.sort(key=lambda r: (
        BUDGET_SUFFIXES.index(str(r["budget_suffix"])), int(r["uniform_headway_min"]),
        str(r["span_id"]), str(r["calendar_id"]), int(r["recovery_min"]), str(r["policy_id"]),
    ))
    args.context_audit_output.parent.mkdir(parents=True, exist_ok=True)
    with args.context_audit_output.open("w", encoding="utf-8", newline="") as handle:
        writer2 = csv.DictWriter(handle, fieldnames=list(context_audit[0].keys()), lineterminator="\n")
        writer2.writeheader()
        writer2.writerows(context_audit)

    policies_per_timing = 9
    presence_rows: list[dict[str, object]] = []
    summary_by_budget_timing: dict[str, dict[str, object]] = {}
    for (suffix, timing_key, scenario_id), policy_ids in sorted(
        presence.items(), key=lambda item: (BUDGET_SUFFIXES.index(item[0][0]), item[0][1], item[0][2])
    ):
        sample_policy = policy_lookup[sorted(policy_ids)[0]]
        calendars = sorted({policy_lookup[p].calendar_id for p in policy_ids})
        recoveries = sorted({policy_lookup[p].recovery_min for p in policy_ids})
        presence_rows.append({
            "budget_suffix": suffix,
            "budget_change_fraction": budget_fraction[suffix],
            "budget_cap_annual_bus_km": budget_caps[suffix],
            "timing_key": timing_key,
            "uniform_headway_min": sample_policy.uniform_headway_min,
            "span_id": sample_policy.span_id,
            "scenario_id": scenario_id,
            "frontier_policy_context_count": len(policy_ids),
            "declared_policy_context_count_for_timing": policies_per_timing,
            "frontier_in_all_declared_calendar_recovery_contexts": str(len(policy_ids) == policies_per_timing).lower(),
            "frontier_policy_ids": "|".join(sorted(policy_ids)),
            "frontier_calendar_ids": "|".join(calendars),
            "frontier_recovery_min_values": "|".join(str(v) for v in recoveries),
        })

    presence_by_context: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in presence_rows:
        presence_by_context[(str(row["budget_suffix"]), str(row["timing_key"]))].append(row)
    for suffix in BUDGET_SUFFIXES:
        for timing, policies_here in sorted(policies_by_timing.items()):
            timing_key = f"H{timing[0]}_{timing[1]}"
            rows_here = presence_by_context.get((suffix, timing_key), [])
            matching_audit = [
                r for r in context_audit
                if r["budget_suffix"] == suffix and int(r["uniform_headway_min"]) == timing[0] and r["span_id"] == timing[1]
            ]
            nonempty = sum(int(r["frontier_scenario_count"]) > 0 for r in matching_audit)
            all_nine = sum(strict_bool(r["frontier_in_all_declared_calendar_recovery_contexts"]) for r in rows_here)
            summary_by_budget_timing[f"{suffix}__{timing_key}"] = {
                "declared_policy_context_count": 9,
                "nonempty_policy_context_count": nonempty,
                "frontier_scenario_union_count": len(rows_here),
                "frontier_scenario_intersection_all_9_contexts_count": all_nine,
            }

    args.presence_output.parent.mkdir(parents=True, exist_ok=True)
    if not presence_rows:
        raise ValueError("Scenario presence output is empty")
    with args.presence_output.open("w", encoding="utf-8", newline="") as handle:
        writer3 = csv.DictWriter(handle, fieldnames=list(presence_rows[0].keys()), lineterminator="\n")
        writer3.writeheader()
        writer3.writerows(presence_rows)

    clean_budget_summary: dict[str, dict[str, object]] = {}
    for suffix, summary in budget_summary.items():
        clean_budget_summary[suffix] = {
            "cap_annual_bus_km": budget_caps[suffix],
            "change_fraction": budget_fraction[suffix],
            "frontier_row_count": int(summary["frontier_row_count"]),
            "unique_scenario_count": len(summary["unique_scenario_ids"]),
            "unique_scenario_count_headway_30_or_better": len(summary["unique_scenario_ids_headway_30_or_better"]),
            "nonempty_policy_context_count": int(summary["nonempty_policy_context_count"]),
        }

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "service_ready_frontier_row_count": len(frontier_rows),
        "service_ready_unique_scenario_count": len(scenario_ids),
        "declared_no_extension_policy_context_count": 72,
        "declared_budget_envelope_count": 6,
        "policy_budget_context_count": 432,
        "nonempty_policy_budget_context_count": context_frontier_count,
        "frontier_row_count": total_frontier_rows,
        "budget_summary": clean_budget_summary,
        "budget_timing_robust_presence_summary": summary_by_budget_timing,
        "pareto_maximise_axes": list(MAX_AXES),
        "pareto_minimise_axes": list(MIN_AXES),
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "service_policy_selected": False,
        "s8_phase_selected": False,
        "exact_timetable_constructed": False,
        "exact_vehicle_blocks_constructed": False,
        "positive_extension_share_in_main_surface": False,
        "weighted_composite_score": False,
        "full_gjt_calculated": False,
        "passenger_demand_assigned_to_routes": False,
        "mode_choice_inferred": False,
        "ridership_forecast": False,
        "policy_context_semantics": "HEADWAY_SPAN_CALENDAR_RECOVERY_FIXED_BEFORE_WITHIN_CONTEXT_PARETO",
        "budget_semantics": "EXPLICIT_HARD_CAP_EVALUATED_INDEPENDENTLY_NOT_A_SCORE_WEIGHT",
        "fleet_semantics": "AGGREGATE_INTERLINABLE_LOWER_BOUND_NOT_EXACT_VEHICLE_BLOCK_PLAN",
        "lineage": {
            "service_ready_frontier": str(args.service_ready_frontier),
            "service_ready_frontier_sha256": sha256_path(args.service_ready_frontier),
            "service_ready_validation": str(args.service_ready_validation),
            "service_ready_validation_sha256": sha256_path(args.service_ready_validation),
            "operational": str(args.operational),
            "operational_sha256": sha256_path(args.operational),
            "operational_validation": str(args.operational_validation),
            "operational_validation_sha256": sha256_path(args.operational_validation),
            "policy_config": str(args.policy_config),
            "policy_config_sha256": sha256_path(args.policy_config),
            "policy_grid": str(args.policy_grid),
            "policy_grid_sha256": sha256_path(args.policy_grid),
            "policy_feasibility": str(args.policy_feasibility),
            "policy_feasibility_sha256": sha256_path(args.policy_feasibility),
            "policy_validation": str(args.policy_validation),
            "policy_validation_sha256": sha256_path(args.policy_validation),
            "budget_envelopes": str(args.budget_envelopes),
            "budget_envelopes_sha256": sha256_path(args.budget_envelopes),
            "budget_validation": str(args.budget_validation),
            "budget_validation_sha256": sha256_path(args.budget_validation),
            "frontier_output": str(args.frontier_output),
            "frontier_output_sha256": sha256_path(args.frontier_output),
            "context_audit_output": str(args.context_audit_output),
            "context_audit_output_sha256": sha256_path(args.context_audit_output),
            "presence_output": str(args.presence_output),
            "presence_output_sha256": sha256_path(args.presence_output),
        },
        "upstream_statuses": {
            "service_ready": service_ready_val.get("status"),
            "service_policy": policy_val.get("status"),
            "budget_envelopes": budget_val.get("status"),
        },
        "limitations": [
            "Each frontier is conditional on an explicit policy context; no calendar or recovery level is declared best here.",
            "Annual bus-km uses the certified continuous-clockface production approximation, not an exact trip table.",
            "Fleet is a lower bound under aggregate interlining and is not an exact block schedule.",
            "S8 phase and missed-connection reliability are not yet constructed at this stage.",
            "Positive scheduled-extension shares are excluded from the main surface and require separate comparison.",
            "Final PRIMARY/RUNNER-UP remains blocked by the explicit decision-budget and uncertainty-band contract.",
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
