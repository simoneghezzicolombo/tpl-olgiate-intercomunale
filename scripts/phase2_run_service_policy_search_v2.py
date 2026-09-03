#!/usr/bin/env python3
"""Materialise the compact, lossless Service-Policy Search V2 feasibility sweep."""
from __future__ import annotations

import argparse
from bisect import bisect_left
import csv
import gzip
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_screen_structural_catalog import sha256_path
from src.phase2_service_policy_search import (
    evaluate_policy_for_scenario,
    load_design_space,
)


BUDGET_SUFFIXES = ("m20pct", "m10pct", "reference", "p10pct", "p20pct", "p30pct")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_inputs(
    *,
    operational_path: Path,
    operational_validation_path: Path,
    design_space_path: Path,
    s8_contract_path: Path,
    s8_characterization_path: Path,
    current_timetable_validation_path: Path,
) -> tuple[dict, dict, dict, dict]:
    op = _load_json(operational_validation_path)
    s8 = _load_json(s8_contract_path)
    s8c = _load_json(s8_characterization_path)
    current = _load_json(current_timetable_validation_path)
    if op.get("status") != "PASS_OPERATIONAL_SCREENING_V2_BUILD":
        raise ValueError("Operational Screening V2 upstream status is not PASS")
    if op.get("contract") != "PHASE2_OPERATIONAL_LOWER_BOUND_SCREENING_V2":
        raise ValueError("Unexpected Operational Screening V2 contract")
    if op.get("lineage", {}).get("operational_screening_sha256") != sha256_path(operational_path):
        raise ValueError("Operational Screening V2 hash mismatch")
    if int(op.get("operational_pass_count", -1)) != 100_000 or int(op.get("operational_fail_count", -1)) != 0:
        raise ValueError("Service-policy search requires all certified operational scenarios")
    if any(op.get(key) is not False for key in (
        "headway_assumed", "calendar_assumed", "service_days_assumed", "recovery_assumed",
        "fleet_assumed", "extension_share_assumed", "service_policy_selected", "topology_ranked",
        "stop_set_selected", "annual_service_plan_produced",
    )):
        raise ValueError("Operational upstream already contains a forbidden service-policy assumption/selection")

    if s8.get("model") != "PHASE2_S8_INTERCHANGE_OPPORTUNITY_V1":
        raise ValueError("Unexpected S8 interchange contract")
    if int(s8.get("active_s8_events", -1)) != 74:
        raise ValueError("Unexpected active S8 event count")
    directions = s8c.get("directions", {})
    for direction in ("MILANO", "LECCO"):
        if int(directions[direction]["event_count"]) != 37:
            raise ValueError(f"Unexpected S8 event count for {direction}")
        if not math.isclose(float(directions[direction]["headway_median_min"]), 30.0):
            raise ValueError(f"Unexpected S8 median headway for {direction}")
    if current.get("status") != "PASS":
        raise ValueError("Current-service stop timetable is not PASS")
    if current.get("calendar_semantics", {}).get("annual_service_days") != "NOT_INFERRED":
        raise ValueError("Current timetable unexpectedly supplies annual service days")

    design_payload, _ = load_design_space(design_space_path)
    return op, s8, s8c, design_payload


def write_policy_grid(path: Path, policies) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "policy_index", "policy_id", "uniform_headway_min", "span_id", "span_start_min",
            "span_end_min", "span_minutes", "calendar_id", "annual_service_days", "recovery_min",
            "extension_share", "headway_status", "span_status", "calendar_status", "recovery_status",
            "extension_share_status", "production_status", "fleet_status", "exact_timetable", "s8_phase_selected",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for p in policies:
            writer.writerow({
                "policy_index": p.policy_index,
                "policy_id": p.policy_id,
                "uniform_headway_min": p.uniform_headway_min,
                "span_id": p.span_id,
                "span_start_min": p.span_start_min,
                "span_end_min": p.span_end_min,
                "span_minutes": p.span_minutes,
                "calendar_id": p.calendar_id,
                "annual_service_days": p.annual_service_days,
                "recovery_min": p.recovery_min,
                "extension_share": f"{p.extension_share:.2f}",
                "headway_status": "ASSUMPTION_DESIGN_SPACE",
                "span_status": "ASSUMPTION_DESIGN_SPACE",
                "calendar_status": "ASSUMPTION_DESIGN_SPACE_NOT_ACTUAL_CALENDAR",
                "recovery_status": "ASSUMPTION_SENSITIVITY",
                "extension_share_status": "ASSUMPTION_DESIGN_SPACE",
                "production_status": "MODEL_OUTPUT_CONTINUOUS_CLOCKFACE_PRODUCTION_APPROXIMATION",
                "fleet_status": "MODEL_OUTPUT_LOWER_BOUND_NOT_VEHICLE_BLOCK_PLAN",
                "exact_timetable": "false",
                "s8_phase_selected": "false",
            })


def _open_deterministic_gzip_text(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, gz, text


def materialise_feasibility(*, operational_path: Path, policies, budget_caps: list[float], output_path: Path) -> dict:
    if len(budget_caps) != 6 or budget_caps != sorted(budget_caps):
        raise ValueError("Expected six ascending Phase 2 annual bus-km envelopes")
    policy_count = len(policies)
    hex_width = math.ceil(policy_count / 4)
    nonextension_policies = [p for p in policies if math.isclose(p.extension_share, 0.0, abs_tol=1e-12)]
    if len(policies) != 288 or len(nonextension_policies) != 72:
        raise ValueError(f"Unexpected service policy universe size: {len(policies)} / {len(nonextension_policies)}")

    scenario_count = 0
    family_counts: dict[str, int] = {}
    feasible_scenario_counts = [0] * len(budget_caps)
    feasible_policy_total_counts = [0] * len(budget_caps)
    zero_feasible_examples: list[str] = []

    raw, gz, text = _open_deterministic_gzip_text(output_path)
    try:
        with operational_path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            base_fields = ["scenario_id", "topology_family", "applicable_policy_count"]
            fields = list(base_fields)
            for suffix in BUDGET_SUFFIXES:
                fields.extend([
                    f"feasible_policy_count_{suffix}",
                    f"feasible_policy_mask_hex_{suffix}",
                    f"min_feasible_headway_min_{suffix}",
                    f"max_feasible_span_min_{suffix}",
                    f"max_feasible_annual_service_days_{suffix}",
                    f"min_aggregate_interlinable_fleet_lower_bound_{suffix}",
                    f"max_annual_bus_km_within_envelope_{suffix}",
                ])
            writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
            writer.writeheader()

            for line_no, row in enumerate(reader, start=2):
                if row.get("operational_screen_status") != "PASS_TO_SERVICE_POLICY_SEARCH":
                    raise ValueError(f"Operational row {line_no} is not eligible for service-policy search")
                scenario_id = str(row["scenario_id"])
                family = str(row["topology_family"])
                public_distance = float(row["public_equal_pattern_set_cycle_distance_km_lower_bound"])
                public_runtime = float(row["public_equal_pattern_set_cycle_runtime_min_lower_bound"])
                route_count = int(row["public_route_count"])
                ext_distance_raw = str(row.get("extension_equal_pattern_set_cycle_distance_km_lower_bound", "")).strip()
                ext_runtime_raw = str(row.get("extension_equal_pattern_set_cycle_runtime_min_lower_bound", "")).strip()
                ext_distance = float(ext_distance_raw) if ext_distance_raw else None
                ext_runtime = float(ext_runtime_raw) if ext_runtime_raw else None
                applicable = policies if family == "scheduled_extensions" else nonextension_policies

                masks = [0] * len(budget_caps)
                counts = [0] * len(budget_caps)
                min_headway: list[int | None] = [None] * len(budget_caps)
                max_span: list[int | None] = [None] * len(budget_caps)
                max_days: list[int | None] = [None] * len(budget_caps)
                min_fleet: list[int | None] = [None] * len(budget_caps)
                max_km: list[float | None] = [None] * len(budget_caps)

                for policy in applicable:
                    metrics = evaluate_policy_for_scenario(
                        policy,
                        topology_family=family,
                        public_cycle_distance_km=public_distance,
                        public_cycle_runtime_min=public_runtime,
                        public_route_count=route_count,
                        extension_cycle_distance_km=ext_distance,
                        extension_cycle_runtime_min=ext_runtime,
                    )
                    if metrics is None:
                        continue
                    first = bisect_left(budget_caps, metrics.annual_bus_km - 1e-9)
                    if first >= len(budget_caps):
                        continue
                    bit = 1 << policy.policy_index
                    for idx in range(first, len(budget_caps)):
                        masks[idx] |= bit
                        counts[idx] += 1
                        min_headway[idx] = policy.uniform_headway_min if min_headway[idx] is None else min(min_headway[idx], policy.uniform_headway_min)
                        max_span[idx] = policy.span_minutes if max_span[idx] is None else max(max_span[idx], policy.span_minutes)
                        max_days[idx] = policy.annual_service_days if max_days[idx] is None else max(max_days[idx], policy.annual_service_days)
                        min_fleet[idx] = metrics.aggregate_interlinable_fleet_lower_bound if min_fleet[idx] is None else min(min_fleet[idx], metrics.aggregate_interlinable_fleet_lower_bound)
                        max_km[idx] = metrics.annual_bus_km if max_km[idx] is None else max(max_km[idx], metrics.annual_bus_km)

                out = {
                    "scenario_id": scenario_id,
                    "topology_family": family,
                    "applicable_policy_count": len(applicable),
                }
                for idx, suffix in enumerate(BUDGET_SUFFIXES):
                    out[f"feasible_policy_count_{suffix}"] = counts[idx]
                    out[f"feasible_policy_mask_hex_{suffix}"] = format(masks[idx], f"0{hex_width}x")
                    out[f"min_feasible_headway_min_{suffix}"] = "" if min_headway[idx] is None else min_headway[idx]
                    out[f"max_feasible_span_min_{suffix}"] = "" if max_span[idx] is None else max_span[idx]
                    out[f"max_feasible_annual_service_days_{suffix}"] = "" if max_days[idx] is None else max_days[idx]
                    out[f"min_aggregate_interlinable_fleet_lower_bound_{suffix}"] = "" if min_fleet[idx] is None else min_fleet[idx]
                    out[f"max_annual_bus_km_within_envelope_{suffix}"] = "" if max_km[idx] is None else f"{max_km[idx]:.6f}"
                    feasible_policy_total_counts[idx] += counts[idx]
                    if counts[idx] > 0:
                        feasible_scenario_counts[idx] += 1
                if counts[-1] == 0 and len(zero_feasible_examples) < 20:
                    zero_feasible_examples.append(scenario_id)
                writer.writerow(out)
                scenario_count += 1
                family_counts[family] = family_counts.get(family, 0) + 1
    finally:
        text.flush()
        text.close()
        raw.close()

    return {
        "scenario_count": scenario_count,
        "family_counts": dict(sorted(family_counts.items())),
        "policy_count": policy_count,
        "nonextension_applicable_policy_count": len(nonextension_policies),
        "scheduled_extension_applicable_policy_count": policy_count,
        "feasible_scenario_counts_by_budget": dict(zip(BUDGET_SUFFIXES, feasible_scenario_counts)),
        "feasible_policy_pair_counts_by_budget": dict(zip(BUDGET_SUFFIXES, feasible_policy_total_counts)),
        "zero_feasible_examples_at_highest_budget": zero_feasible_examples,
        "policy_mask_hex_width": hex_width,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operational-screening", required=True, type=Path)
    parser.add_argument("--operational-validation", required=True, type=Path)
    parser.add_argument("--design-space", required=True, type=Path)
    parser.add_argument("--s8-contract", required=True, type=Path)
    parser.add_argument("--s8-characterization", required=True, type=Path)
    parser.add_argument("--current-timetable-validation", required=True, type=Path)
    parser.add_argument("--policy-grid-output", required=True, type=Path)
    parser.add_argument("--feasibility-output", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    for path in (
        args.operational_screening, args.operational_validation, args.design_space,
        args.s8_contract, args.s8_characterization, args.current_timetable_validation,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    op, s8, s8c, design_payload = validate_inputs(
        operational_path=args.operational_screening,
        operational_validation_path=args.operational_validation,
        design_space_path=args.design_space,
        s8_contract_path=args.s8_contract,
        s8_characterization_path=args.s8_characterization,
        current_timetable_validation_path=args.current_timetable_validation,
    )
    _, policies = load_design_space(args.design_space)
    write_policy_grid(args.policy_grid_output, policies)
    budget_caps = [float(v) for v in op["budget_caps_annual_bus_km"]]
    summary = materialise_feasibility(
        operational_path=args.operational_screening,
        policies=policies,
        budget_caps=budget_caps,
        output_path=args.feasibility_output,
    )
    if summary["scenario_count"] != 100_000:
        raise RuntimeError(f"Expected 100000 scenarios, got {summary['scenario_count']}")

    validation = {
        "status": "PASS_SERVICE_POLICY_SEARCH_V2_BUILD",
        "contract": "PHASE2_SERVICE_POLICY_FEASIBILITY_SEARCH_V2",
        "evidence_label": "ASSUMPTION_DESIGN_SPACE_FEASIBILITY_NOT_SERVICE_PLAN",
        **summary,
        "budget_change_fractions": op["budget_change_fractions"],
        "budget_caps_annual_bus_km": budget_caps,
        "uniform_clockface_baseline": True,
        "peak_offpeak_differentiation": False,
        "production_semantics": "MODEL_OUTPUT_CONTINUOUS_CLOCKFACE_PRODUCTION_APPROXIMATION",
        "exact_departure_count": False,
        "exact_timetable_constructed": False,
        "s8_phase_selected": False,
        "passenger_utility_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "stop_set_selected": False,
        "fleet_is_lower_bound_not_block_plan": True,
        "current_annual_service_days_inferred": False,
        "s8_factual_reference": {
            "service_date": s8["service_date"],
            "active_events": s8["active_s8_events"],
            "milano_median_headway_min": s8c["directions"]["MILANO"]["headway_median_min"],
            "lecco_median_headway_min": s8c["directions"]["LECCO"]["headway_median_min"],
        },
        "design_space": {
            "headways_min": design_payload["headways_min"],
            "spans": design_payload["spans"],
            "annual_service_days": design_payload["annual_service_days"],
            "recovery_min": design_payload["recovery_min"],
            "scheduled_extension_shares": design_payload["scheduled_extension_shares"],
        },
        "lineage": {
            "operational_screening": str(args.operational_screening),
            "operational_screening_sha256": sha256_path(args.operational_screening),
            "operational_validation": str(args.operational_validation),
            "operational_validation_sha256": sha256_path(args.operational_validation),
            "design_space": str(args.design_space),
            "design_space_sha256": sha256_path(args.design_space),
            "s8_contract": str(args.s8_contract),
            "s8_contract_sha256": sha256_path(args.s8_contract),
            "s8_characterization": str(args.s8_characterization),
            "s8_characterization_sha256": sha256_path(args.s8_characterization),
            "current_timetable_validation": str(args.current_timetable_validation),
            "current_timetable_validation_sha256": sha256_path(args.current_timetable_validation),
            "policy_grid": str(args.policy_grid_output),
            "policy_grid_sha256": sha256_path(args.policy_grid_output),
            "feasibility_output": str(args.feasibility_output),
            "feasibility_output_sha256": sha256_path(args.feasibility_output),
        },
        "epistemic_note": (
            "The policy universe is an explicit ASSUMPTION/DESIGN_SPACE. Feasibility masks losslessly retain every "
            "budget-feasible policy in the declared grid for each operationally valid topology. No passenger utility, "
            "S8 clock phase, exact timetable or recommendation is computed here."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
