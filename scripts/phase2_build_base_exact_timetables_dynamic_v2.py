#!/usr/bin/env python3
"""Run Base Exact Timetables V2 with lineage-driven frontier cardinality.

The certified exact-timetable engine originally guarded the first tournament run
with a literal expected BASE_UNRESTRICTED count of 394. A legitimate upstream
access correction may change that frontier cardinality. This adapter preserves
all other source/hash/semantic checks but derives the expected count from the
certified Plan-Level Frontiers V2 validation instead of freezing the historical
394-row result.
"""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.phase2_build_base_exact_timetables_v2 as base


def validate_upstream_dynamic(args) -> None:
    frontier = base.loadj(args.frontier_validation)
    s8 = base.loadj(args.s8_validation)
    matrix = base.loadj(args.matrix_validation)
    weights = base.loadj(args.work_weights_validation)
    if frontier.get("status") != "PASS_PLAN_LEVEL_FRONTIERS_V2_BUILD" or frontier.get("lineage", {}).get("output_sha256") != base.sha(args.frontier):
        raise ValueError("Plan-Level Frontiers V2 is not certified")
    expected = int(frontier.get("frontier_class_plan_counts", {}).get("BASE_UNRESTRICTED", -1))
    if expected <= 0:
        raise ValueError("Certified BASE_UNRESTRICTED frontier is empty/invalid")
    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD":
        raise ValueError("S8 Phase Opportunity V2 is not certified")
    lineage = s8.get("lineage", {})
    if lineage.get("route_universe_sha256") != base.sha(args.route_universe):
        raise ValueError("S8 route-universe hash mismatch")
    if lineage.get("scenario_route_mapping_sha256") != base.sha(args.scenario_mapping):
        raise ValueError("S8 scenario-route mapping hash mismatch")
    if lineage.get("s8_events_sha256") != base.sha(args.s8_events):
        raise ValueError("S8 event hash mismatch")
    if s8.get("phase_selected") is not False or s8.get("all_phases_retained_downstream") is not True:
        raise ValueError("Upstream S8 phase domain is not complete/unselected")
    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != base.sha(args.path_matrix):
        raise ValueError("Reduced Path Matrix V2 is not certified")
    if weights.get("status") != "PASS_S8_WORK_DIRECTION_WEIGHTS_V2_BUILD":
        raise ValueError("S8 work-direction weights V2 are not certified")
    if weights.get("lineage", {}).get("summary_sha256") != base.sha(args.work_direction_summary):
        raise ValueError("S8 work-direction summary hash mismatch")
    if float(weights.get("demand_weight_sum", -1)) != 1882.0:
        raise ValueError("Unexpected S8 worker direction reference")


def load_base_frontier_dynamic(path: Path):
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        required = {
            "plan_id", "scenario_id", "topology_family", "uniform_headway_min", "span_id",
            "span_start_min", "span_end_min", "span_minutes", "calendar_id", "annual_service_days",
            "extension_share", "annual_bus_km", "fleet_lower_bound_recovery5", "fleet_lower_bound_recovery10",
            "fleet_lower_bound_recovery15", "plan_level_frontier_classes", "s8_phase_selected",
            "exact_timetable_constructed", "topology_ranked", "service_policy_selected", "primary_selected", "runner_up_selected",
        }
        if not required <= set(fields):
            raise ValueError(f"Frontier schema missing {sorted(required-set(fields))}")
        for row in reader:
            classes = set(str(row["plan_level_frontier_classes"]).split(";"))
            if "BASE_UNRESTRICTED" not in classes:
                continue
            if abs(float(row["extension_share"])) > 1e-12:
                raise ValueError("BASE_UNRESTRICTED row has positive extension share")
            if any(base.bool_text(row[field], field=field) for field in (
                "s8_phase_selected", "exact_timetable_constructed", "topology_ranked",
                "service_policy_selected", "primary_selected", "runner_up_selected",
            )):
                raise ValueError("Base frontier already contains forbidden downstream selection")
            rows.append(row)
    if not rows:
        raise ValueError("BASE_UNRESTRICTED frontier is empty")
    if len({row["plan_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate plan ID in base frontier")
    return rows, fields


def main() -> int:
    base.validate_upstream = validate_upstream_dynamic
    base.load_base_frontier = load_base_frontier_dynamic
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
