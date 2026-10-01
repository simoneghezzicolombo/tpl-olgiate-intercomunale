#!/usr/bin/env python3
"""Exact vehicle-block screen for every typed within-cap municipal line."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_mixed_frequency_surface_v4 import (
    exact_vehicle_count_for_departures,
    mixed_service_templates,
    phased_departures,
)
from src.phase2_rt031_single_line_timetable_surface_v3 import (
    route_for_engineering_case,
)


TYPED_AUDIT_SHA256 = "d2d27d1c5fb4f1faaeaa4d911735daab57c64dd3a173c2e887c500027cb9f60f"


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def screen_profile(profile, templates):
    cases = profile["operational_source_model_screen"][
        "inherited_stage_f_engineering_grid"]["cases"]
    if len(cases) != 27:
        raise ValueError("inherited engineering grid drift")
    if profile["timetable_assigned"] is not False:
        raise ValueError("typed input unexpectedly assigns timetable")
    fleet = {}
    for template in templates:
        departures = phased_departures(template, 0)
        counts = [exact_vehicle_count_for_departures(
            route_for_engineering_case(case), departures,
            int(case["recovery_minutes"])) for case in cases]
        fleet[template["template_id"]] = {
            "maximum_exact_vehicle_count": max(counts),
            "minimum_exact_vehicle_count": min(counts),
            "engineering_case_count": len(counts),
        }
    return {
        "source_candidate_line_id": profile["source_candidate_line_id"],
        "retained_current_exact_stop_count": profile[
            "retained_current_exact_stop_count"],
        "conditional_annual_bus_km_at_20_daily_cycles": profile[
            "conditional_annual_bus_km_at_20_daily_cycles"],
        "fleet_by_template": fleet,
    }


def build_screen(typed):
    if (typed.get("contract") != "RT031_MUNICIPAL_FRONTIER_TYPED_BINDING_V4"
            or typed.get("status")
            != "PASS_FULL_WITHIN_CAP_FRONTIER_TYPED_PENDING_OPERATIONS"
            or typed.get("within_cap_profile_count") != 736
            or typed.get("within_cap_frontier_binding_complete") is not True
            or typed.get("network_selected") is not False):
        raise ValueError("pinned municipal typed contract drift")
    templates = mixed_service_templates()
    rows = [screen_profile(profile, templates) for profile in typed["profiles"]]
    ids = [row["source_candidate_line_id"] for row in rows]
    if len(rows) != 736 or len(set(ids)) != 736:
        raise ValueError("typed profile identity drift")
    rows.sort(key=lambda row: row["source_candidate_line_id"])
    per_template = []
    for template in templates:
        identity = template["template_id"]
        distribution = Counter(row["fleet_by_template"][identity][
            "maximum_exact_vehicle_count"] for row in rows)
        by_retention = {}
        for retained in sorted({row["retained_current_exact_stop_count"]
                                for row in rows}):
            subset = [row for row in rows if row[
                "retained_current_exact_stop_count"] == retained]
            counts = Counter(row["fleet_by_template"][identity][
                "maximum_exact_vehicle_count"] for row in subset)
            by_retention[str(retained)] = {
                str(fleet): counts[fleet] for fleet in sorted(counts)}
        per_template.append({
            "template_id": identity,
            "span_minutes": template["span_minutes"],
            "h30_peak_hours": template["h30_peak_hours"],
            "h60_offpeak_hours": template["h60_offpeak_hours"],
            "daily_departure_count": len(template["nominal_departure_minutes"]),
            "fleet_max_distribution": {
                str(key): distribution[key] for key in sorted(distribution)},
            "fleet_max_distribution_by_retained_current_stop_count":
                by_retention,
            "at_most_three_vehicle_profile_count": sum(
                count for fleet, count in distribution.items() if fleet <= 3),
        })
    return {
        "contract": "RT031_MUNICIPAL_FRONTIER_FLEET_SCREEN_V4",
        "status": "PASS_FULL_WITHIN_CAP_FLEET_SCREEN_NON_DECISIONAL",
        "within_cap_typed_profile_count": len(rows),
        "engineering_cases_per_profile_template": 27,
        "clock_phase_invariance": "COMMON_TRANSLATION_OF_ALL_DEPARTURES_PRESERVES_EXACT_VEHICLE_COUNT",
        "phase_rotation_evaluated_for_transfer_quality": False,
        "transfer_quality_evaluated": False,
        "observed_dwell_validation_complete": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "deterministic_miss_share_is_empirical_probability": False,
        "current_stop_retention_used_as_filter": False,
        "municipality_non_regression_used_as_filter": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "service_pattern_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {"municipal_typed_audit": TYPED_AUDIT_SHA256},
        "per_template_summary": per_template,
        "profiles": rows,
    }


def main(args):
    if hashlib.sha256(args.typed_audit.read_bytes()).hexdigest() != TYPED_AUDIT_SHA256:
        raise ValueError("pinned municipal typed audit drift")
    output = build_screen(json.loads(args.typed_audit.read_text(encoding="utf-8")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = args.output_dir / "municipal_frontier_fleet_screen_v4.json"
    result.write_bytes(canonical(output))
    audit = {key: value for key, value in output.items() if key != "profiles"}
    audit["result_sha256"] = hashlib.sha256(result.read_bytes()).hexdigest()
    (args.output_dir / "municipal_frontier_fleet_screen_v4_audit.json").write_bytes(
        canonical(audit))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
