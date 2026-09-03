#!/usr/bin/env python3
"""Join certified Phase 2 structural evidence and materialise Pareto frontiers.

This is a topology-level pre-tournament evidence layer. It does not rank
scenarios, select a service policy, calculate full passenger GJT, select an S8
phase or authorise discarding non-frontier scenarios from the later plan-level
tournament.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_pretournament_structural_frontier_v2 import (
    CONTRACT,
    STATUS,
    MetricPoint,
    nondominated_metric_points,
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def loadj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def open_csv(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def deterministic_gzip_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def load_rows(path: Path, required: set[str], label: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with open_csv(path) as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise ValueError(f"{label} missing columns: {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            scenario_id = str(row["scenario_id"]).strip()
            if not scenario_id:
                raise ValueError(f"{label} empty scenario_id at line {line_no}")
            if scenario_id in rows:
                raise ValueError(f"{label} duplicate scenario_id {scenario_id}")
            rows[scenario_id] = row
    if not rows:
        raise ValueError(f"{label} is empty")
    return rows


def validate_lineage(
    *,
    access: Path,
    access_validation: Path,
    territorial: Path,
    territorial_validation: Path,
    service: Path,
    service_validation: Path,
) -> tuple[dict, dict, dict, float]:
    av = loadj(access_validation)
    tv = loadj(territorial_validation)
    sv = loadj(service_validation)

    if av.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or av.get("contract") != "PHASE2_BUILDING_CATCHMENT_ACCESS_EQUITY_V2":
        raise ValueError("Access/Equity V2 upstream is not certified")
    if av.get("lineage", {}).get("scenario_output_sha256") != sha(access):
        raise ValueError("Access/Equity V2 output hash mismatch")
    if int(av.get("scenario_count", -1)) != 100000 or av.get("topology_ranked") is not False:
        raise ValueError("Unexpected Access/Equity V2 semantics")

    if tv.get("status") != "PASS_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2_BUILD" or tv.get("contract") != "PHASE2_TERRITORIAL_COMMUTING_ADDRESSABILITY_V2":
        raise ValueError("Territorial Commuting Addressability V2 upstream is not certified")
    if tv.get("lineage", {}).get("scenario_output_sha256") != sha(territorial):
        raise ValueError("Territorial V2 output hash mismatch")
    if int(tv.get("scenario_count", -1)) != 100000 or tv.get("topology_ranked") is not False:
        raise ValueError("Unexpected Territorial V2 semantics")

    if sv.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD" or sv.get("contract") != "PHASE2_SERVICE_POLICY_FEASIBILITY_SEARCH_V2":
        raise ValueError("Service Policy Search V2 upstream is not certified")
    if sv.get("lineage", {}).get("feasibility_output_sha256") != sha(service):
        raise ValueError("Service-policy feasibility output hash mismatch")
    if int(sv.get("scenario_count", -1)) != 100000 or sv.get("topology_ranked") is not False or sv.get("service_policy_selected") is not False:
        raise ValueError("Unexpected Service Policy Search V2 semantics")
    reference_count = int(sv.get("feasible_scenario_counts_by_budget", {}).get("reference", -1))
    if reference_count <= 0:
        raise ValueError("Missing reference-budget feasibility count")
    caps = [float(v) for v in sv.get("budget_caps_annual_bus_km", [])]
    if len(caps) != 6:
        raise ValueError("Unexpected budget envelope count")
    reference_cap = caps[2]
    if abs(reference_cap - 111419.0) > 1e-9:
        raise ValueError("Reference screening envelope is not the certified 111,419 bus-km/year value")
    return av, tv, sv, reference_cap


ACCESS_REQUIRED = {
    "scenario_id", "topology_family",
    "public_population_covered_10min", "public_population_coverage_share_10min",
    "public_worst_municipality_10min", "public_worst_municipality_coverage_share_10min",
    "public_plus_extensions_population_covered_10min", "public_plus_extensions_population_coverage_share_10min",
    "public_plus_extensions_worst_municipality_10min", "public_plus_extensions_worst_municipality_coverage_share_10min",
}
TERRITORIAL_REQUIRED = {
    "scenario_id", "topology_family",
    "public_structurally_addressable_od_relation_count",
    "public_structurally_addressable_worker_od_mass_upper_bound",
    "public_other_core_worker_od_mass_upper_bound",
    "public_s8_direct_worker_od_mass_upper_bound",
    "public_other_external_worker_od_mass_upper_bound",
    "public_plus_extensions_structurally_addressable_od_relation_count",
    "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
    "public_plus_extensions_other_core_worker_od_mass_upper_bound",
    "public_plus_extensions_s8_direct_worker_od_mass_upper_bound",
    "public_plus_extensions_other_external_worker_od_mass_upper_bound",
}
SERVICE_REQUIRED = {
    "scenario_id", "topology_family",
    "feasible_policy_count_reference",
    "min_feasible_headway_min_reference",
    "max_feasible_span_min_reference",
    "max_feasible_annual_service_days_reference",
    "min_aggregate_interlinable_fleet_lower_bound_reference",
    "max_annual_bus_km_within_envelope_reference",
}


JOINED_FIELDS = [
    "scenario_id", "topology_family",
    "reference_budget_screening_feasible", "feasible_policy_count_reference",
    "min_feasible_headway_min_reference", "max_feasible_span_min_reference",
    "max_feasible_annual_service_days_reference",
    "min_aggregate_interlinable_fleet_lower_bound_reference",
    "max_annual_bus_km_within_envelope_reference",
    "public_population_covered_10min", "public_population_coverage_share_10min",
    "public_worst_municipality_10min", "public_worst_municipality_coverage_share_10min",
    "public_structurally_addressable_od_relation_count",
    "public_structurally_addressable_worker_od_mass_upper_bound",
    "public_other_core_worker_od_mass_upper_bound",
    "public_s8_direct_worker_od_mass_upper_bound",
    "public_other_external_worker_od_mass_upper_bound",
    "public_plus_extensions_population_covered_10min",
    "public_plus_extensions_population_coverage_share_10min",
    "public_plus_extensions_worst_municipality_10min",
    "public_plus_extensions_worst_municipality_coverage_share_10min",
    "public_plus_extensions_structurally_addressable_od_relation_count",
    "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
    "public_plus_extensions_other_core_worker_od_mass_upper_bound",
    "public_plus_extensions_s8_direct_worker_od_mass_upper_bound",
    "public_plus_extensions_other_external_worker_od_mass_upper_bound",
    "public_structural_pareto_frontier", "public_plus_extensions_upper_bound_pareto_frontier",
    "structural_frontier_union", "topology_ranked", "service_policy_selected",
    "full_passenger_gjt_calculated", "s8_phase_selected", "nonfrontier_pruning_authorized",
]


def build_joined(access_rows, territorial_rows, service_rows):
    ids = set(access_rows)
    if ids != set(territorial_rows) or ids != set(service_rows):
        raise ValueError("Scenario ID sets differ across certified inputs")
    if len(ids) != 100000:
        raise ValueError(f"Expected 100000 common scenarios, got {len(ids)}")

    joined: dict[str, dict[str, str]] = {}
    public_points: dict[str, MetricPoint] = {}
    extension_points: dict[str, MetricPoint] = {}
    feasible_ids: set[str] = set()

    for scenario_id in sorted(ids):
        a = access_rows[scenario_id]
        t = territorial_rows[scenario_id]
        s = service_rows[scenario_id]
        families = {a["topology_family"], t["topology_family"], s["topology_family"]}
        if len(families) != 1:
            raise ValueError(f"Topology family mismatch for {scenario_id}: {families}")
        family = families.pop()
        feasible_count = int(s["feasible_policy_count_reference"])
        feasible = feasible_count > 0
        if feasible:
            feasible_ids.add(scenario_id)
            public_points[scenario_id] = MetricPoint.from_values(
                a["public_population_coverage_share_10min"],
                a["public_worst_municipality_coverage_share_10min"],
                t["public_structurally_addressable_worker_od_mass_upper_bound"],
            )
            extension_points[scenario_id] = MetricPoint.from_values(
                a["public_plus_extensions_population_coverage_share_10min"],
                a["public_plus_extensions_worst_municipality_coverage_share_10min"],
                t["public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound"],
            )

        row = {
            "scenario_id": scenario_id,
            "topology_family": family,
            "reference_budget_screening_feasible": "true" if feasible else "false",
            "feasible_policy_count_reference": str(feasible_count),
            "min_feasible_headway_min_reference": s["min_feasible_headway_min_reference"],
            "max_feasible_span_min_reference": s["max_feasible_span_min_reference"],
            "max_feasible_annual_service_days_reference": s["max_feasible_annual_service_days_reference"],
            "min_aggregate_interlinable_fleet_lower_bound_reference": s["min_aggregate_interlinable_fleet_lower_bound_reference"],
            "max_annual_bus_km_within_envelope_reference": s["max_annual_bus_km_within_envelope_reference"],
        }
        for field in (
            "public_population_covered_10min", "public_population_coverage_share_10min",
            "public_worst_municipality_10min", "public_worst_municipality_coverage_share_10min",
            "public_plus_extensions_population_covered_10min", "public_plus_extensions_population_coverage_share_10min",
            "public_plus_extensions_worst_municipality_10min", "public_plus_extensions_worst_municipality_coverage_share_10min",
        ):
            row[field] = a[field]
        for field in TERRITORIAL_REQUIRED - {"scenario_id", "topology_family"}:
            row[field] = t[field]
        row.update({
            "public_structural_pareto_frontier": "false",
            "public_plus_extensions_upper_bound_pareto_frontier": "false",
            "structural_frontier_union": "false",
            "topology_ranked": "false",
            "service_policy_selected": "false",
            "full_passenger_gjt_calculated": "false",
            "s8_phase_selected": "false",
            "nonfrontier_pruning_authorized": "false",
        })
        joined[scenario_id] = row
    return joined, feasible_ids, public_points, extension_points


def frontier_ids(points_by_id: dict[str, MetricPoint]) -> tuple[set[str], frozenset[MetricPoint]]:
    frontier_points = nondominated_metric_points(points_by_id.values())
    return {scenario_id for scenario_id, point in points_by_id.items() if point in frontier_points}, frontier_points


def write_gz(path: Path, rows: list[dict[str, str]]) -> None:
    raw, text = deterministic_gzip_writer(path)
    try:
        writer = csv.DictWriter(text, fieldnames=JOINED_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        text.close()
        raw.close()


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=JOINED_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def family_counts(ids: set[str], joined: dict[str, dict[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(joined[i]["topology_family"] for i in ids).items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--access-validation", type=Path, required=True)
    parser.add_argument("--territorial", type=Path, required=True)
    parser.add_argument("--territorial-validation", type=Path, required=True)
    parser.add_argument("--service-feasibility", type=Path, required=True)
    parser.add_argument("--service-validation", type=Path, required=True)
    parser.add_argument("--joined-output", type=Path, required=True)
    parser.add_argument("--public-frontier-output", type=Path, required=True)
    parser.add_argument("--extension-frontier-output", type=Path, required=True)
    parser.add_argument("--union-output", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()

    av, tv, sv, reference_cap = validate_lineage(
        access=args.access, access_validation=args.access_validation,
        territorial=args.territorial, territorial_validation=args.territorial_validation,
        service=args.service_feasibility, service_validation=args.service_validation,
    )
    access_rows = load_rows(args.access, ACCESS_REQUIRED, "access")
    territorial_rows = load_rows(args.territorial, TERRITORIAL_REQUIRED, "territorial")
    service_rows = load_rows(args.service_feasibility, SERVICE_REQUIRED, "service")
    joined, feasible_ids, public_points, extension_points = build_joined(access_rows, territorial_rows, service_rows)

    expected_feasible = int(sv["feasible_scenario_counts_by_budget"]["reference"])
    if len(feasible_ids) != expected_feasible:
        raise ValueError(f"Reference-feasible scenario count mismatch: {len(feasible_ids)} != {expected_feasible}")

    public_ids, public_metric_points = frontier_ids(public_points)
    extension_ids, extension_metric_points = frontier_ids(extension_points)
    union_ids = public_ids | extension_ids
    for scenario_id in public_ids:
        joined[scenario_id]["public_structural_pareto_frontier"] = "true"
    for scenario_id in extension_ids:
        joined[scenario_id]["public_plus_extensions_upper_bound_pareto_frontier"] = "true"
    for scenario_id in union_ids:
        joined[scenario_id]["structural_frontier_union"] = "true"

    joined_rows = [joined[i] for i in sorted(joined)]
    public_rows = [joined[i] for i in sorted(public_ids)]
    extension_rows = [joined[i] for i in sorted(extension_ids)]
    union_rows = [joined[i] for i in sorted(union_ids)]
    write_gz(args.joined_output, joined_rows)
    write_csv(args.public_frontier_output, public_rows)
    write_csv(args.extension_frontier_output, extension_rows)
    write_csv(args.union_output, union_rows)

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "scenario_count": len(joined),
        "reference_budget_screening_only": True,
        "reference_budget_screening_cap_annual_bus_km": reference_cap,
        "reference_budget_feasible_scenario_count": len(feasible_ids),
        "pareto_objectives": [
            "MAX_PUBLIC_10MIN_LOCATED_POPULATION_COVERAGE_SHARE",
            "MAX_PUBLIC_10MIN_WORST_MUNICIPALITY_COVERAGE_SHARE",
            "MAX_TERRITORIAL_STRUCTURALLY_ADDRESSABLE_WORKER_OD_MASS_UPPER_BOUND",
        ],
        "public_frontier_scenario_count": len(public_ids),
        "public_frontier_unique_metric_point_count": len(public_metric_points),
        "public_frontier_family_counts": family_counts(public_ids, joined),
        "public_plus_extensions_upper_bound_frontier_scenario_count": len(extension_ids),
        "public_plus_extensions_upper_bound_frontier_unique_metric_point_count": len(extension_metric_points),
        "public_plus_extensions_upper_bound_frontier_family_counts": family_counts(extension_ids, joined),
        "structural_frontier_union_scenario_count": len(union_ids),
        "structural_frontier_union_family_counts": family_counts(union_ids, joined),
        "extension_frontier_semantics": "UPPER_BOUND_ALL_OPTIONAL_EXTENSION_ANCHORS_PRESENT_NOT_EXTENSION_SHARE_OR_TIMETABLE_SELECTION",
        "service_extrema_semantics": "DESCRIPTIVE_INDEPENDENT_EXTREMA_ACROSS_REFERENCE_FEASIBLE_POLICIES_NOT_ONE_JOINT_PLAN",
        "nonfrontier_scenarios_discarded_from_final_tournament": False,
        "nonfrontier_pruning_authorized": False,
        "decision_budget_selected": False,
        "weighted_composite_score_used": False,
        "topology_ranked": False,
        "topology_selected": False,
        "service_policy_selected": False,
        "full_passenger_gjt_calculated": False,
        "s8_feeder_metric_used_in_pareto": False,
        "s8_phase_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "access_sha256": sha(args.access),
            "access_validation_sha256": sha(args.access_validation),
            "territorial_sha256": sha(args.territorial),
            "territorial_validation_sha256": sha(args.territorial_validation),
            "service_feasibility_sha256": sha(args.service_feasibility),
            "service_validation_sha256": sha(args.service_validation),
            "joined_output_sha256": sha(args.joined_output),
            "public_frontier_output_sha256": sha(args.public_frontier_output),
            "extension_frontier_output_sha256": sha(args.extension_frontier_output),
            "union_output_sha256": sha(args.union_output),
        },
        "epistemic_note": (
            "Pareto membership is a topology-level structural classification, not a ranking. "
            "It uses only certified 10-minute resident access, worst-municipality access and "
            "municipal work-OD structural addressability among scenarios with at least one "
            "service policy feasible under the validated 111,419 bus-km/year reference envelope. "
            "The reference envelope is a screening reference, not a declared final decision budget. "
            "Non-frontier scenarios remain eligible for later plan-level evaluation because service "
            "frequency, runtime, joint timetable/S8 phase and robustness can change the final result."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
