#!/usr/bin/env python3
"""Build the RT-001 budget-lossless no-extension policy surface.

This stage starts from the certified budget-neutral Service-Ready Frontier V2.
For each scenario×timing, no-extension policy context and declared budget it
computes the exact minimum and maximum annual bus-km over the COMPLETE integer
route-specific phase domain, before any phase is selected.

For a uniform headway/span, each public route has either floor(span/headway) or
ceil(span/headway) departures per service day depending on its integer phase.
Because route phases are independent in Stage D, the aggregate exact minimum is
floor(span/headway) times the closed equal-pattern-set cycle distance, and the
aggregate exact maximum is ceil(span/headway) times that distance. Therefore:

* min > cap  => NO phase can satisfy the budget, safe hard exclusion;
* max <= cap => ALL phases satisfy the budget;
* min <= cap < max => SOME phases satisfy the budget and the context MUST survive
  until exact timetable materialisation.

No continuous-clockface feasibility bitmask is used as a hard filter. No Pareto
screening is performed here, because phase-dependent production may not dominate
candidates before the phase is selected. Positive scheduled-extension shares are
outside this main surface.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

STATUS = "PASS_PHASE2_BUDGET_LOSSLESS_POLICY_SURFACE_V2"
CONTRACT = "PHASE2_EXACT_EXISTENTIAL_INTEGER_PHASE_BUDGET_SURFACE_V2"
BUDGET_SUFFIX = {
    -0.2: "m20pct",
    -0.1: "m10pct",
    0.0: "reference",
    0.1: "p10pct",
    0.2: "p20pct",
    0.3: "p30pct",
}
EXPECTED_BUDGETS = tuple(BUDGET_SUFFIX.values())
EPS = 1e-8
CYCLE_DISTANCE_FIELD = "public_equal_pattern_set_cycle_distance_km_lower_bound"
CYCLE_RUNTIME_FIELD = "public_equal_pattern_set_cycle_runtime_min_lower_bound"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def finite_float(value: object, *, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite {field}: {value!r}")
    return result


def deterministic_gzip_writer(path: Path, fields: Sequence[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def exact_departure_bounds(span_minutes: int, headway_min: int) -> tuple[int, int]:
    if span_minutes <= 0 or headway_min <= 0:
        raise ValueError("span and headway must be positive")
    q, r = divmod(span_minutes, headway_min)
    return q, q if r == 0 else q + 1


def classify_budget(*, exact_min: float, exact_max: float, cap: float) -> str:
    if not all(math.isfinite(v) for v in (exact_min, exact_max, cap)):
        raise ValueError("budget classification requires finite values")
    if exact_min < -EPS or exact_max + EPS < exact_min or cap < 0:
        raise ValueError("invalid budget envelope values")
    if exact_min > cap + EPS:
        return "NO_PHASE_BUDGET_FEASIBLE"
    if exact_max <= cap + EPS:
        return "ALL_PHASES_BUDGET_FEASIBLE"
    return "SOME_PHASES_BUDGET_FEASIBLE"


def load_budgets(path: Path, validation_path: Path) -> list[dict[str, object]]:
    validation = read_json(validation_path)
    if validation.get("status") != "PASS" or int(validation.get("envelope_count", -1)) != 6:
        raise ValueError("Budget envelopes are not certified")
    rows = []
    for row in read_csv(path):
        change = round(float(row["budget_change_fraction"]), 10)
        if change not in BUDGET_SUFFIX:
            raise ValueError(f"Unexpected budget change {change}")
        cap = finite_float(row["annual_bus_km_cap"], field="annual_bus_km_cap")
        rows.append({
            "budget_suffix": BUDGET_SUFFIX[change],
            "budget_change_fraction": change,
            "budget_cap_annual_bus_km": cap,
        })
    rows.sort(key=lambda r: EXPECTED_BUDGETS.index(str(r["budget_suffix"])))
    if tuple(r["budget_suffix"] for r in rows) != EXPECTED_BUDGETS:
        raise ValueError("Budget envelope set changed")
    if [float(r["budget_cap_annual_bus_km"]) for r in rows] != [float(v) for v in validation["annual_bus_km_caps"]]:
        raise ValueError("Budget cap values disagree with validation")
    return rows


def load_policies(path: Path, validation_path: Path) -> dict[tuple[int, str], list[dict[str, object]]]:
    validation = read_json(validation_path)
    if validation.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD":
        raise ValueError("Service Policy Search V2 is not certified")
    if validation.get("contract") != "PHASE2_SERVICE_POLICY_FEASIBILITY_SEARCH_V2":
        raise ValueError("Unexpected service-policy contract")
    if validation.get("lineage", {}).get("policy_grid_sha256") != sha256_path(path):
        raise ValueError("Policy grid hash mismatch")
    if validation.get("production_semantics") != "MODEL_OUTPUT_CONTINUOUS_CLOCKFACE_PRODUCTION_APPROXIMATION":
        raise ValueError("Expected old continuous production semantics for audit lineage")
    if validation.get("exact_departure_count") is not False:
        raise ValueError("Old service-policy surface unexpectedly claims exact departures")
    by_timing: dict[tuple[int, str], list[dict[str, object]]] = {}
    seen = 0
    for row in read_csv(path):
        share = finite_float(row["extension_share"], field="extension_share")
        if abs(share) > 1e-12:
            continue
        policy = {
            "policy_index": int(row["policy_index"]),
            "policy_id": str(row["policy_id"]),
            "uniform_headway_min": int(row["uniform_headway_min"]),
            "span_id": str(row["span_id"]),
            "span_start_min": int(row["span_start_min"]),
            "span_end_min": int(row["span_end_min"]),
            "span_minutes": int(row["span_minutes"]),
            "calendar_id": str(row["calendar_id"]),
            "annual_service_days": int(row["annual_service_days"]),
            "recovery_min": int(row["recovery_min"]),
            "extension_share": 0.0,
        }
        if policy["span_minutes"] != policy["span_end_min"] - policy["span_start_min"]:
            raise ValueError("Policy span arithmetic mismatch")
        by_timing.setdefault((policy["uniform_headway_min"], policy["span_id"]), []).append(policy)
        seen += 1
    if seen != 72 or len(by_timing) != 8:
        raise ValueError(f"Unexpected no-extension policy grid: {seen} rows / {len(by_timing)} timings")
    for key, rows in by_timing.items():
        rows.sort(key=lambda r: (str(r["calendar_id"]), int(r["recovery_min"]), str(r["policy_id"])))
        if len(rows) != 9:
            raise ValueError(f"Timing {key} does not have 9 calendar×recovery policies")
        if {int(r["recovery_min"]) for r in rows} != {5, 10, 15}:
            raise ValueError(f"Timing {key} recovery set changed")
    return by_timing


def validate_service_ready(path: Path, validation_path: Path) -> dict:
    validation = read_json(validation_path)
    if validation.get("status") != "PASS_PHASE2_SERVICE_READY_FRONTIER_V2":
        raise ValueError("Service-Ready Frontier V2 is not certified")
    if validation.get("contract") != "PHASE2_BUDGET_NEUTRAL_SERVICE_READY_PARETO_V2":
        raise ValueError("Unexpected Service-Ready contract")
    if validation.get("lineage", {}).get("frontier_output_sha256") != sha256_path(path):
        raise ValueError("Service-Ready frontier hash mismatch")
    if int(validation.get("frontier_row_count_all_timings", -1)) != 21237:
        raise ValueError("Unexpected Service-Ready row count")
    for key in ("budget_filter_applied", "calendar_selected", "recovery_selected", "service_policy_selected", "s8_phase_selected", "exact_timetable_constructed", "full_gjt_calculated", "weighted_composite_score"):
        if validation.get(key) is not False:
            raise ValueError(f"Service-Ready upstream violates budget-neutral contract: {key}")
    return validation


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--service-ready", type=Path, required=True)
    p.add_argument("--service-ready-validation", type=Path, required=True)
    p.add_argument("--policy-grid", type=Path, required=True)
    p.add_argument("--policy-validation", type=Path, required=True)
    p.add_argument("--budget-envelopes", type=Path, required=True)
    p.add_argument("--budget-validation", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--audit-output", type=Path, required=True)
    p.add_argument("--validation-output", type=Path, required=True)
    args = p.parse_args()
    for path in (args.service_ready, args.service_ready_validation, args.policy_grid, args.policy_validation, args.budget_envelopes, args.budget_validation):
        if not path.is_file():
            raise FileNotFoundError(path)

    service_ready_validation = validate_service_ready(args.service_ready, args.service_ready_validation)
    policies = load_policies(args.policy_grid, args.policy_validation)
    budgets = load_budgets(args.budget_envelopes, args.budget_validation)

    source_rows = list(read_csv(args.service_ready))
    if len(source_rows) != 21237:
        raise ValueError(f"Expected 21237 Service-Ready rows, got {len(source_rows)}")
    required = {
        "scenario_id", "topology_family", "uniform_headway_min", "span_id", "span_start_min", "span_end_min",
        CYCLE_DISTANCE_FIELD, CYCLE_RUNTIME_FIELD, "public_route_count",
    }
    if not required <= set(source_rows[0]):
        raise ValueError(f"Service-Ready schema missing {sorted(required-set(source_rows[0]))}")

    extra_fields = [
        "policy_index", "policy_id", "calendar_id", "annual_service_days", "recovery_min", "extension_share",
        "budget_suffix", "budget_change_fraction", "budget_cap_annual_bus_km",
        "exact_min_departures_per_route_per_day", "exact_max_departures_per_route_per_day",
        "continuous_pattern_sets_per_day_audit_only", "exact_min_annual_bus_km", "exact_max_annual_bus_km",
        "continuous_annual_bus_km_audit_only", "annual_bus_km",
        "annual_bus_km_semantics", "exact_budget_phase_feasibility_class", "exact_budget_phase_feasible",
        "continuous_hard_filter_would_pass", "recovered_from_continuous_hard_filter",
        "aggregate_interlinable_fleet_lower_bound", "expected_pattern_set_cycle_distance_km",
        "expected_pattern_set_cycle_runtime_min", "exact_phase_selected", "exact_timetable_constructed",
        "budget_selected", "calendar_selected", "recovery_selected", "service_policy_selected",
        "weighted_composite_score", "positive_extension_share_in_main_surface",
    ]
    fields = list(source_rows[0].keys()) + [f for f in extra_fields if f not in source_rows[0]]
    raw, text, writer = deterministic_gzip_writer(args.output, fields)

    class_counts = {"ALL_PHASES_BUDGET_FEASIBLE": 0, "SOME_PHASES_BUDGET_FEASIBLE": 0, "NO_PHASE_BUDGET_FEASIBLE": 0}
    retained_by_budget = {b: 0 for b in EXPECTED_BUDGETS}
    recovered_by_budget = {b: 0 for b in EXPECTED_BUDGETS}
    recovered_scenarios: set[str] = set()
    retained_contexts = 0
    candidate_contexts = 0
    try:
        for source in source_rows:
            sid = str(source["scenario_id"])
            headway = int(source["uniform_headway_min"])
            span_id = str(source["span_id"])
            cycle_distance = finite_float(source[CYCLE_DISTANCE_FIELD], field=CYCLE_DISTANCE_FIELD)
            cycle_runtime = finite_float(source[CYCLE_RUNTIME_FIELD], field=CYCLE_RUNTIME_FIELD)
            route_count = int(float(source["public_route_count"]))
            if cycle_distance <= 0 or cycle_runtime <= 0 or route_count <= 0:
                raise ValueError(f"Invalid operational primitives for {sid}")
            timing_policies = policies.get((headway, span_id))
            if not timing_policies:
                raise ValueError(f"No no-extension policies for {(headway,span_id)}")
            for policy in timing_policies:
                span_minutes = int(policy["span_minutes"])
                floor_count, ceil_count = exact_departure_bounds(span_minutes, headway)
                days = int(policy["annual_service_days"])
                exact_min = cycle_distance * floor_count * days
                exact_max = cycle_distance * ceil_count * days
                continuous_sets = span_minutes / headway
                continuous_annual = cycle_distance * continuous_sets * days
                fleet_lb = math.ceil((cycle_runtime + int(policy["recovery_min"]) * route_count) / headway)
                for budget in budgets:
                    candidate_contexts += 1
                    cap = float(budget["budget_cap_annual_bus_km"])
                    klass = classify_budget(exact_min=exact_min, exact_max=exact_max, cap=cap)
                    class_counts[klass] += 1
                    if klass == "NO_PHASE_BUDGET_FEASIBLE":
                        continue
                    retained_contexts += 1
                    suffix = str(budget["budget_suffix"])
                    retained_by_budget[suffix] += 1
                    continuous_pass = continuous_annual <= cap + EPS
                    recovered = not continuous_pass
                    if recovered:
                        recovered_by_budget[suffix] += 1
                        recovered_scenarios.add(sid)
                    out = dict(source)
                    out.update({
                        "policy_index": int(policy["policy_index"]),
                        "policy_id": str(policy["policy_id"]),
                        "calendar_id": str(policy["calendar_id"]),
                        "annual_service_days": days,
                        "recovery_min": int(policy["recovery_min"]),
                        "extension_share": 0.0,
                        "budget_suffix": suffix,
                        "budget_change_fraction": budget["budget_change_fraction"],
                        "budget_cap_annual_bus_km": cap,
                        "exact_min_departures_per_route_per_day": floor_count,
                        "exact_max_departures_per_route_per_day": ceil_count,
                        "continuous_pattern_sets_per_day_audit_only": continuous_sets,
                        "exact_min_annual_bus_km": exact_min,
                        "exact_max_annual_bus_km": exact_max,
                        "continuous_annual_bus_km_audit_only": continuous_annual,
                        "annual_bus_km": exact_min,
                        "annual_bus_km_semantics": "EXACT_MINIMUM_OVER_COMPLETE_INTEGER_PHASE_DOMAIN_NOT_SELECTED_TIMETABLE",
                        "exact_budget_phase_feasibility_class": klass,
                        "exact_budget_phase_feasible": "true",
                        "continuous_hard_filter_would_pass": "true" if continuous_pass else "false",
                        "recovered_from_continuous_hard_filter": "true" if recovered else "false",
                        "aggregate_interlinable_fleet_lower_bound": fleet_lb,
                        "expected_pattern_set_cycle_distance_km": cycle_distance,
                        "expected_pattern_set_cycle_runtime_min": cycle_runtime,
                        "exact_phase_selected": "false",
                        "exact_timetable_constructed": "false",
                        "budget_selected": "false",
                        "calendar_selected": "false",
                        "recovery_selected": "false",
                        "service_policy_selected": "false",
                        "weighted_composite_score": "false",
                        "positive_extension_share_in_main_surface": "false",
                    })
                    writer.writerow(out)
    finally:
        text.close()
        raw.close()

    if candidate_contexts != 21237 * 9 * 6:
        raise AssertionError(f"Unexpected context Cartesian count {candidate_contexts}")
    if retained_contexts <= 0:
        raise ValueError("Lossless budget surface is empty")

    audit_rows = []
    for budget in budgets:
        suffix = str(budget["budget_suffix"])
        audit_rows.append({
            "budget_suffix": suffix,
            "budget_change_fraction": budget["budget_change_fraction"],
            "budget_cap_annual_bus_km": budget["budget_cap_annual_bus_km"],
            "retained_context_count": retained_by_budget[suffix],
            "recovered_from_continuous_hard_filter_count": recovered_by_budget[suffix],
        })
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    with args.audit_output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(audit_rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(audit_rows)

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "service_ready_row_count": 21237,
        "no_extension_policy_count": 72,
        "policy_contexts_per_timing": 9,
        "budget_count": 6,
        "candidate_context_count_before_exact_budget": candidate_contexts,
        "retained_exact_phase_feasible_context_count": retained_contexts,
        "exact_phase_feasibility_class_counts": class_counts,
        "retained_by_budget": retained_by_budget,
        "recovered_from_continuous_hard_filter_by_budget": recovered_by_budget,
        "recovered_from_continuous_hard_filter_total": sum(recovered_by_budget.values()),
        "recovered_unique_scenario_count": len(recovered_scenarios),
        "exact_budget_rule": "RETAIN_IFF_MINIMUM_ANNUAL_BUS_KM_OVER_COMPLETE_INTEGER_ROUTE_PHASE_DOMAIN_LE_BUDGET_CAP",
        "exact_minimum_derivation": "FLOOR_SPAN_OVER_HEADWAY_TIMES_CLOSED_EQUAL_PATTERN_SET_CYCLE_DISTANCE_TIMES_ANNUAL_SERVICE_DAYS",
        "exact_maximum_derivation": "CEIL_SPAN_OVER_HEADWAY_TIMES_CLOSED_EQUAL_PATTERN_SET_CYCLE_DISTANCE_TIMES_ANNUAL_SERVICE_DAYS",
        "route_specific_integer_phase_domain_preserved": True,
        "continuous_clockface_used_as_hard_filter": False,
        "old_feasibility_bitmask_used_as_hard_filter": False,
        "pareto_screening_applied_in_this_stage": False,
        "phase_dependent_annual_bus_km_used_for_dominance": False,
        "annual_bus_km_field_semantics": "EXACT_MINIMUM_OVER_COMPLETE_INTEGER_PHASE_DOMAIN_NOT_SELECTED_TIMETABLE",
        "positive_extension_share_in_main_surface": False,
        "exact_phase_selected": False,
        "exact_timetable_constructed": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "service_policy_selected": False,
        "weighted_composite_score": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "service_ready": str(args.service_ready),
            "service_ready_sha256": sha256_path(args.service_ready),
            "service_ready_validation": str(args.service_ready_validation),
            "service_ready_validation_sha256": sha256_path(args.service_ready_validation),
            "policy_grid": str(args.policy_grid),
            "policy_grid_sha256": sha256_path(args.policy_grid),
            "policy_validation": str(args.policy_validation),
            "policy_validation_sha256": sha256_path(args.policy_validation),
            "budget_envelopes": str(args.budget_envelopes),
            "budget_envelopes_sha256": sha256_path(args.budget_envelopes),
            "budget_validation": str(args.budget_validation),
            "budget_validation_sha256": sha256_path(args.budget_validation),
            "output": str(args.output),
            "output_sha256": sha256_path(args.output),
            "audit_output": str(args.audit_output),
            "audit_output_sha256": sha256_path(args.audit_output),
        },
        "limitations": [
            "This surface establishes exact existential budget eligibility before phase selection; it does not select an exact timetable.",
            "The annual_bus_km compatibility field is the exact minimum over the complete integer phase domain, not selected-timetable production.",
            "Exact timetable production and exact vehicle blocks remain downstream and must reapply the hard cap to the selected phase vector.",
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": STATUS, "retained": retained_contexts, "recovered": validation["recovered_from_continuous_hard_filter_total"], "classes": class_counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
