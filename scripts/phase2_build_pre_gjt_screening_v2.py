#!/usr/bin/env python3
"""Materialise the non-decisional Phase 2 pre-GJT multi-layer screening surface."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_pre_gjt_screening_v2 import (
    CONTRACT,
    STATUS,
    TimingKey,
    build_timing_policy_masks,
    strict_bool,
    summarise_route_timing,
)


OUTPUT_FIELDS = [
    "scenario_id", "topology_family", "uniform_headway_min", "span_id", "span_start_min", "span_end_min",
    "reference_budget_annual_bus_km", "reference_budget_feasible_policy_count",
    "reference_budget_feasible_no_extension_policy_count", "reference_budget_feasible_positive_extension_policy_count",
    "reference_budget_timing_feasible",
    "public_route_count", "public_roundtrip_supported_route_count", "public_rail_to_bus_only_route_count",
    "public_roundtrip_routes_with_complete_match_phase", "public_roundtrip_routes_without_complete_match_phase",
    "public_directional_routes_with_complete_match_phase", "public_directional_routes_without_complete_match_phase",
    "public_roundtrip_best_phase_gap_min_min_across_complete_routes", "public_roundtrip_best_phase_gap_min_max_across_complete_routes",
    "public_roundtrip_worst_phase_gap_min_min_across_complete_routes", "public_roundtrip_worst_phase_gap_min_max_across_complete_routes",
    "public_directional_best_phase_gap_min_min_across_complete_routes", "public_directional_best_phase_gap_min_max_across_complete_routes",
    "public_directional_worst_phase_gap_min_min_across_complete_routes", "public_directional_worst_phase_gap_min_max_across_complete_routes",
    "extension_route_count", "extension_roundtrip_supported_route_count", "extension_rail_to_bus_only_route_count",
    "extension_roundtrip_routes_with_complete_match_phase", "extension_roundtrip_routes_without_complete_match_phase",
    "extension_directional_routes_with_complete_match_phase", "extension_directional_routes_without_complete_match_phase",
    "extension_roundtrip_best_phase_gap_min_max_across_complete_routes", "extension_roundtrip_worst_phase_gap_min_max_across_complete_routes",
    "public_population_coverage_share_5min", "public_population_coverage_share_8min", "public_population_coverage_share_10min",
    "public_worst_municipality_coverage_share_5min", "public_worst_municipality_coverage_share_8min", "public_worst_municipality_coverage_share_10min",
    "public_plus_extensions_population_coverage_share_10min", "public_plus_extensions_worst_municipality_coverage_share_10min",
    "public_operational_unknown_distance_share_lower_bound", "public_explicit_field_check_pending_count",
    "public_distance_km", "public_runtime_min",
    "public_plus_extensions_access_is_presence_not_frequency_adjusted", "optional_extensions_selected", "passenger_demand_assigned_to_routes",
    "s8_direction_weights_are_route_demand", "full_gjt_calculated", "phase_selected", "topology_ranked", "service_policy_selected",
    "primary_selected", "runner_up_selected",
]


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_gzip_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def index_rows(rows: list[dict[str, str]], *, key: str, label: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if not value or value in out:
            raise ValueError(f"{label} has missing or duplicate {key}")
        out[value] = row
    return out


def parse_ids(value: str, *, scenario_id: str, field: str) -> list[str]:
    raw = json.loads(value)
    if not isinstance(raw, list) or any(not isinstance(v, str) or not v for v in raw):
        raise ValueError(f"{scenario_id}: invalid {field}")
    if len(raw) != len(set(raw)):
        raise ValueError(f"{scenario_id}: duplicate route in {field}")
    return raw


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.9f}"


def validate_contracts(args) -> tuple[dict, dict, dict, dict, dict]:
    op = read_json(args.operational_validation)
    access = read_json(args.access_validation)
    policy = read_json(args.policy_validation)
    support = read_json(args.s8_support_validation)
    gaps = read_json(args.s8_gap_validation)
    if op.get("status") != "PASS_OPERATIONAL_SCREENING_V2_BUILD" or op.get("contract") != "PHASE2_OPERATIONAL_LOWER_BOUND_SCREENING_V2":
        raise ValueError("Operational Screening V2 is not certified")
    if access.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or access.get("contract") != "PHASE2_BUILDING_CATCHMENT_ACCESS_EQUITY_V2":
        raise ValueError("Access Equity V2 is not certified")
    if policy.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD" or policy.get("contract") != "PHASE2_SERVICE_POLICY_FEASIBILITY_SEARCH_V2":
        raise ValueError("Service Policy Search V2 is not certified")
    if support.get("status") != "PASS_S8_PASSENGER_SUPPORT_MASK_V2_BUILD" or support.get("contract") != "PHASE2_S8_PASSENGER_SUPPORT_MASK_V2":
        raise ValueError("S8 passenger-support mask is not certified")
    if gaps.get("status") != "PASS_S8_TRANSFER_GAP_ENVELOPE_V2_BUILD" or gaps.get("contract") != "PHASE2_S8_TRANSFER_GAP_ENVELOPE_V2":
        raise ValueError("S8 transfer-gap envelope is not certified")
    if any(op.get(k) is not False for k in ("service_policy_selected", "topology_ranked", "stop_set_selected")):
        raise ValueError("Operational upstream contains a selection")
    if any(access.get(k) is not False for k in ("passenger_demand_inferred", "topology_ranked", "service_policy_selected", "primary_selected", "runner_up_selected")):
        raise ValueError("Access upstream contains a forbidden inference/selection")
    if any(policy.get(k) is not False for k in ("passenger_utility_calculated", "topology_ranked", "service_policy_selected", "s8_phase_selected")):
        raise ValueError("Service-policy upstream contains a forbidden utility/selection")
    if support.get("passenger_demand_assigned_to_routes") is not False or support.get("topology_ranked") is not False:
        raise ValueError("S8 support upstream violates route-demand/ranking separation")
    if gaps.get("worker_reference_assigned_to_routes") is not False or gaps.get("phase_selected") is not False or gaps.get("topology_ranked") is not False:
        raise ValueError("S8 gap upstream violates demand/phase/ranking separation")
    if int(op.get("scenario_count", -1)) != 100000 or int(access.get("scenario_count", -1)) != 100000 or int(policy.get("scenario_count", -1)) != 100000 or int(support.get("scenario_count", -1)) != 100000:
        raise ValueError("Upstream scenario counts do not all equal 100,000")
    if float(op.get("budget_reference_annual_bus_km", -1)) != 111419.0:
        raise ValueError("Unexpected reference annual bus-km budget")
    return op, access, policy, support, gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operational", type=Path, required=True)
    parser.add_argument("--operational-validation", type=Path, required=True)
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--access-validation", type=Path, required=True)
    parser.add_argument("--policy-grid", type=Path, required=True)
    parser.add_argument("--policy-feasibility", type=Path, required=True)
    parser.add_argument("--policy-validation", type=Path, required=True)
    parser.add_argument("--s8-scenario-mapping", type=Path, required=True)
    parser.add_argument("--s8-scenario-support", type=Path, required=True)
    parser.add_argument("--s8-support-validation", type=Path, required=True)
    parser.add_argument("--s8-gap-envelope", type=Path, required=True)
    parser.add_argument("--s8-gap-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()
    for path in vars(args).values():
        if isinstance(path, Path) and path in (args.output, args.validation):
            continue
        if isinstance(path, Path) and not path.is_file():
            raise FileNotFoundError(path)

    op_val, access_val, policy_val, support_val, gap_val = validate_contracts(args)
    policy_rows = read_csv(args.policy_grid)
    timing_masks = build_timing_policy_masks(policy_rows)
    if len(timing_masks) != 8:
        raise ValueError(f"Expected eight timing archetypes, got {len(timing_masks)}")

    operational = index_rows(read_csv(args.operational), key="scenario_id", label="operational")
    access = index_rows(read_gzip_csv(args.access), key="scenario_id", label="access")
    feasibility = index_rows(read_gzip_csv(args.policy_feasibility), key="scenario_id", label="policy feasibility")
    scenario_support = index_rows(read_gzip_csv(args.s8_scenario_support), key="scenario_id", label="S8 scenario support")
    mapping = index_rows(read_gzip_csv(args.s8_scenario_mapping), key="scenario_id", label="S8 scenario mapping")
    expected_ids = set(mapping)
    for label, table in (("operational", operational), ("access", access), ("policy feasibility", feasibility), ("S8 scenario support", scenario_support)):
        if set(table) != expected_ids:
            raise ValueError(f"{label} scenario universe differs from S8 mapping")
    if len(expected_ids) != 100000:
        raise ValueError("Expected exactly 100,000 scenarios")

    gap_rows = read_gzip_csv(args.s8_gap_envelope)
    gap_lookup: dict[tuple[str, int, str], dict[str, str]] = {}
    for row in gap_rows:
        key = (str(row["route_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
        if key in gap_lookup:
            raise ValueError("Duplicate route×timing row in S8 gap envelope")
        if row.get("demand_weight_semantics") != "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE":
            raise ValueError("S8 gap row lost direction-weight-only semantics")
        if strict_bool(row.get("passenger_demand_assigned_to_route"), field="passenger_demand_assigned_to_route"):
            raise ValueError("S8 gap row assigns passenger demand to route")
        gap_lookup[key] = row
    if len(gap_lookup) != int(gap_val["route_timing_row_count"]):
        raise ValueError("S8 gap lookup count differs from validation")

    reference_budget = float(op_val["budget_reference_annual_bus_km"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = args.output.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    reference_feasible_scenarios: set[str] = set()
    feasible_timing_rows = 0
    timing_feasible_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    row_count = 0
    try:
        writer = csv.DictWriter(text, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for scenario_id in sorted(expected_ids):
            op = operational[scenario_id]
            acc = access[scenario_id]
            feas = feasibility[scenario_id]
            supp = scenario_support[scenario_id]
            maprow = mapping[scenario_id]
            families = {str(r["topology_family"]) for r in (op, acc, feas, supp, maprow)}
            if len(families) != 1:
                raise ValueError(f"{scenario_id}: topology family mismatch across layers")
            family = families.pop()
            family_counts[family] = family_counts.get(family, 0) + 1
            public_ids = parse_ids(maprow["public_route_ids_json"], scenario_id=scenario_id, field="public_route_ids_json")
            extension_ids = parse_ids(maprow["extension_route_ids_json"], scenario_id=scenario_id, field="extension_route_ids_json")
            if int(supp["public_route_count"]) != len(public_ids) or int(supp["extension_route_count"]) != len(extension_ids):
                raise ValueError(f"{scenario_id}: route counts differ between mapping and support mask")
            reference_mask = int(str(feas["feasible_policy_mask_hex_reference"]), 16)
            stated_reference_count = int(feas["feasible_policy_count_reference"])
            if reference_mask.bit_count() != stated_reference_count:
                raise ValueError(f"{scenario_id}: reference feasibility mask/count mismatch")
            timing_partition_total = 0
            scenario_any_feasible = False
            for timing, masks in timing_masks.items():
                timing_count, no_ext_count, positive_ext_count = masks.count(reference_mask)
                timing_partition_total += timing_count
                if timing_count:
                    scenario_any_feasible = True
                    feasible_timing_rows += 1
                    timing_name = f"H{timing.headway_min}_{timing.span_id}"
                    timing_feasible_counts[timing_name] = timing_feasible_counts.get(timing_name, 0) + 1
                public_s8 = summarise_route_timing(public_ids, timing_key=timing, gap_lookup=gap_lookup)
                extension_s8 = summarise_route_timing(extension_ids, timing_key=timing, gap_lookup=gap_lookup)
                if public_s8.roundtrip_route_count != int(supp["public_roundtrip_supported_route_count"]) or public_s8.directional_only_route_count != int(supp["public_rail_to_bus_only_route_count"]):
                    raise ValueError(f"{scenario_id}: public S8 support counts disagree with support mask")
                if extension_s8.roundtrip_route_count != int(supp["extension_roundtrip_supported_route_count"]) or extension_s8.directional_only_route_count != int(supp["extension_rail_to_bus_only_route_count"]):
                    raise ValueError(f"{scenario_id}: extension S8 support counts disagree with support mask")
                row = {
                    "scenario_id": scenario_id,
                    "topology_family": family,
                    "uniform_headway_min": timing.headway_min,
                    "span_id": timing.span_id,
                    "span_start_min": timing.span_start_min,
                    "span_end_min": timing.span_end_min,
                    "reference_budget_annual_bus_km": f"{reference_budget:.6f}",
                    "reference_budget_feasible_policy_count": timing_count,
                    "reference_budget_feasible_no_extension_policy_count": no_ext_count,
                    "reference_budget_feasible_positive_extension_policy_count": positive_ext_count,
                    "reference_budget_timing_feasible": "true" if timing_count else "false",
                    "public_route_count": public_s8.route_count,
                    "public_roundtrip_supported_route_count": public_s8.roundtrip_route_count,
                    "public_rail_to_bus_only_route_count": public_s8.directional_only_route_count,
                    "public_roundtrip_routes_with_complete_match_phase": public_s8.roundtrip_complete_route_count,
                    "public_roundtrip_routes_without_complete_match_phase": public_s8.roundtrip_incomplete_route_count,
                    "public_directional_routes_with_complete_match_phase": public_s8.directional_complete_route_count,
                    "public_directional_routes_without_complete_match_phase": public_s8.directional_incomplete_route_count,
                    "public_roundtrip_best_phase_gap_min_min_across_complete_routes": fmt(public_s8.roundtrip_best_min),
                    "public_roundtrip_best_phase_gap_min_max_across_complete_routes": fmt(public_s8.roundtrip_best_max),
                    "public_roundtrip_worst_phase_gap_min_min_across_complete_routes": fmt(public_s8.roundtrip_worst_min),
                    "public_roundtrip_worst_phase_gap_min_max_across_complete_routes": fmt(public_s8.roundtrip_worst_max),
                    "public_directional_best_phase_gap_min_min_across_complete_routes": fmt(public_s8.directional_best_min),
                    "public_directional_best_phase_gap_min_max_across_complete_routes": fmt(public_s8.directional_best_max),
                    "public_directional_worst_phase_gap_min_min_across_complete_routes": fmt(public_s8.directional_worst_min),
                    "public_directional_worst_phase_gap_min_max_across_complete_routes": fmt(public_s8.directional_worst_max),
                    "extension_route_count": extension_s8.route_count,
                    "extension_roundtrip_supported_route_count": extension_s8.roundtrip_route_count,
                    "extension_rail_to_bus_only_route_count": extension_s8.directional_only_route_count,
                    "extension_roundtrip_routes_with_complete_match_phase": extension_s8.roundtrip_complete_route_count,
                    "extension_roundtrip_routes_without_complete_match_phase": extension_s8.roundtrip_incomplete_route_count,
                    "extension_directional_routes_with_complete_match_phase": extension_s8.directional_complete_route_count,
                    "extension_directional_routes_without_complete_match_phase": extension_s8.directional_incomplete_route_count,
                    "extension_roundtrip_best_phase_gap_min_max_across_complete_routes": fmt(extension_s8.roundtrip_best_max),
                    "extension_roundtrip_worst_phase_gap_min_max_across_complete_routes": fmt(extension_s8.roundtrip_worst_max),
                    "public_population_coverage_share_5min": acc["public_population_coverage_share_5min"],
                    "public_population_coverage_share_8min": acc["public_population_coverage_share_8min"],
                    "public_population_coverage_share_10min": acc["public_population_coverage_share_10min"],
                    "public_worst_municipality_coverage_share_5min": acc["public_worst_municipality_coverage_share_5min"],
                    "public_worst_municipality_coverage_share_8min": acc["public_worst_municipality_coverage_share_8min"],
                    "public_worst_municipality_coverage_share_10min": acc["public_worst_municipality_coverage_share_10min"],
                    "public_plus_extensions_population_coverage_share_10min": acc["public_plus_extensions_population_coverage_share_10min"],
                    "public_plus_extensions_worst_municipality_coverage_share_10min": acc["public_plus_extensions_worst_municipality_coverage_share_10min"],
                    "public_operational_unknown_distance_share_lower_bound": op["public_operational_unknown_distance_share_lower_bound"],
                    "public_explicit_field_check_pending_count": op["public_explicit_field_check_pending_count"],
                    "public_distance_km": op["public_distance_km"],
                    "public_runtime_min": op["public_runtime_min"],
                    "public_plus_extensions_access_is_presence_not_frequency_adjusted": "true" if extension_ids else "false",
                    "optional_extensions_selected": "false",
                    "passenger_demand_assigned_to_routes": "false",
                    "s8_direction_weights_are_route_demand": "false",
                    "full_gjt_calculated": "false",
                    "phase_selected": "false",
                    "topology_ranked": "false",
                    "service_policy_selected": "false",
                    "primary_selected": "false",
                    "runner_up_selected": "false",
                }
                writer.writerow(row)
                row_count += 1
            if timing_partition_total != stated_reference_count:
                raise ValueError(f"{scenario_id}: timing masks do not partition reference feasible policies")
            if scenario_any_feasible:
                reference_feasible_scenarios.add(scenario_id)
    finally:
        text.close()
        raw.close()

    if row_count != 100000 * len(timing_masks):
        raise ValueError("Unexpected scenario×timing row count")
    expected_ref_scenarios = int(policy_val["feasible_scenario_counts_by_budget"]["reference"])
    if len(reference_feasible_scenarios) != expected_ref_scenarios:
        raise ValueError("Reference-budget feasible scenario count differs from Service Policy Search V2")

    report = {
        "status": STATUS,
        "contract": CONTRACT,
        "evidence_label": "MULTI_LAYER_DECISION_SURFACE_NOT_PASSENGER_GJT_NOT_RANKING",
        "scenario_count": 100000,
        "timing_archetype_count": len(timing_masks),
        "scenario_timing_row_count": row_count,
        "reference_budget_annual_bus_km": reference_budget,
        "reference_budget_feasible_scenario_count": len(reference_feasible_scenarios),
        "reference_budget_infeasible_scenario_count": 100000 - len(reference_feasible_scenarios),
        "reference_budget_feasible_scenario_timing_count": feasible_timing_rows,
        "reference_budget_infeasible_scenario_timing_count": row_count - feasible_timing_rows,
        "reference_budget_feasible_scenario_counts_by_timing": dict(sorted(timing_feasible_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "population_access_metric": "DASYMETRIC_BUILDING_POPULATION_WALK_COVERAGE_NOT_PASSENGER_DEMAND",
        "s8_gap_metric": gap_val["gap_metric"],
        "s8_worker_reference": gap_val["worker_direction_weight_reference"],
        "s8_worker_reference_semantics": "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE",
        "optional_extensions_selected": False,
        "passenger_demand_assigned_to_routes": False,
        "full_gjt_calculated": False,
        "pareto_frontier_computed": False,
        "phase_selected": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "limitations": [
            "Municipal 2021 work OD is not spatially allocated to routes or stops.",
            "The 1,882-worker S8-addressable subset only weights Milano-versus-Lecco transfer directions upstream.",
            "Public-plus-extension walking coverage represents service presence if extensions are operated; it is not frequency-adjusted.",
            "S8 best/worst phase gaps are route-level phase opportunities, not a constructed interlined vehicle timetable.",
            "Operational unknown-distance share is retained explicitly and proposed stops remain FIELD_CHECK_PENDING where upstream says so.",
        ],
        "lineage": {
            "operational": str(args.operational), "operational_sha256": sha256_path(args.operational),
            "operational_validation": str(args.operational_validation), "operational_validation_sha256": sha256_path(args.operational_validation),
            "access": str(args.access), "access_sha256": sha256_path(args.access),
            "access_validation": str(args.access_validation), "access_validation_sha256": sha256_path(args.access_validation),
            "policy_grid": str(args.policy_grid), "policy_grid_sha256": sha256_path(args.policy_grid),
            "policy_feasibility": str(args.policy_feasibility), "policy_feasibility_sha256": sha256_path(args.policy_feasibility),
            "policy_validation": str(args.policy_validation), "policy_validation_sha256": sha256_path(args.policy_validation),
            "s8_scenario_mapping": str(args.s8_scenario_mapping), "s8_scenario_mapping_sha256": sha256_path(args.s8_scenario_mapping),
            "s8_scenario_support": str(args.s8_scenario_support), "s8_scenario_support_sha256": sha256_path(args.s8_scenario_support),
            "s8_support_validation": str(args.s8_support_validation), "s8_support_validation_sha256": sha256_path(args.s8_support_validation),
            "s8_gap_envelope": str(args.s8_gap_envelope), "s8_gap_envelope_sha256": sha256_path(args.s8_gap_envelope),
            "s8_gap_validation": str(args.s8_gap_validation), "s8_gap_validation_sha256": sha256_path(args.s8_gap_validation),
            "output": str(args.output), "output_sha256": sha256_path(args.output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "status", "scenario_timing_row_count", "reference_budget_feasible_scenario_count",
        "reference_budget_feasible_scenario_timing_count", "reference_budget_feasible_scenario_counts_by_timing",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
