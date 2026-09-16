#!/usr/bin/env python3
"""Evaluate fixed-resource H30-peak/H60-off-peak templates on typed RT031 lines."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from src.phase2_exact_timetable_optimizer_v2 import load_profiles, rail_event_index
from src.phase2_rt031_mixed_frequency_surface_v4 import (
    PHASE_DOMAIN,
    evaluate_mixed_context,
    mixed_pareto_frontier,
    mixed_service_templates,
)


TYPED_AUDIT_SHA256 = "735c8f650dbcfc6c429e21cbad374be78cb7436af390bef84b54161baf6337cd"
MUNICIPAL_FRONTIER_SHA256 = "0757d9513e21e1e68a7fc43c1732b45c4ccd83242e84d20ea8a324d0866bca26"
UNIFORM_H30_SURFACE_SHA256 = "08e950b773eb2b8ddbc91c3112539d40afe822c7d2205859459f774af4da5481"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def logical_sha256(path):
    return hashlib.sha256(
        Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def main(args):
    if sha256(args.typed_audit) != TYPED_AUDIT_SHA256:
        raise ValueError("pinned typed one-line evidence drift")
    if sha256(args.municipal_frontier) != MUNICIPAL_FRONTIER_SHA256:
        raise ValueError("pinned municipal frontier drift")
    if sha256(args.uniform_h30_surface) != UNIFORM_H30_SURFACE_SHA256:
        raise ValueError("pinned uniform H30 surface drift")
    typed = json.loads(args.typed_audit.read_text(encoding="utf-8"))
    municipal = json.loads(args.municipal_frontier.read_text(encoding="utf-8"))
    uniform = json.loads(args.uniform_h30_surface.read_text(encoding="utf-8"))
    if (typed.get("profile_count") != 17
            or typed.get("single_recognizable_line_structure_certified") is not True
            or typed.get("network_selected") is not False):
        raise ValueError("typed one-line contract drift")
    if (municipal.get("contract")
            != "RT031_SINGLE_LINE_MUNICIPAL_ACCESS_FRONTIER_V4"
            or municipal.get("frontier_count") != 778
            or municipal.get("network_selected") is not False):
        raise ValueError("municipal frontier contract drift")
    if (uniform.get("contract")
            != "RT031_SINGLE_LINE_H30_10H_DAILY_TIMETABLE_SURFACE_V3"
            or uniform.get("evaluated_timetable_context_count") != 9180
            or uniform.get("network_selected") is not False):
        raise ValueError("uniform H30 surface contract drift")
    municipal_by_id = {
        row["candidate_line_id"]: row for row in municipal["frontier"]}
    profile_ids = [row["source_candidate_line_id"] for row in typed["profiles"]]
    if len(set(profile_ids)) != 17 or any(
            identity not in municipal_by_id for identity in profile_ids):
        raise ValueError("typed diagnostic subset is not contained in municipal frontier")

    with args.s8_events.open(encoding="utf-8", newline="") as handle:
        events = list(csv.DictReader(handle))
    if len(events) != 74:
        raise ValueError("frozen S8 event universe changed")
    rail = rail_event_index(events)
    transfer_profiles = load_profiles(args.sensitivity)
    with args.popular_times_profile.open(encoding="utf-8", newline="") as handle:
        popular = list(csv.DictReader(handle))
    if (len(popular) != 24
            or {row["observed_weekdays_n"] for row in popular} != {"4", "5"}
            or max(popular, key=lambda row: float(
                row["weekday_mean_within_day_index_0_100"]))["hour_local"]
            != "18:00"):
        raise ValueError("weekday Popular Times shape evidence changed")

    templates = mixed_service_templates()
    contexts = [
        evaluate_mixed_context(
            profile, municipal_by_id[profile["source_candidate_line_id"]],
            template=template, phase=phase, rail_index=rail,
            transfer_profiles=transfer_profiles)
        for profile in typed["profiles"]
        for template in templates
        for phase in PHASE_DOMAIN
    ]
    codes = municipal["municipality_codes"]
    frontier = mixed_pareto_frontier(contexts, codes)
    uniform_contexts = []
    for source in uniform["all_contexts"]:
        candidate = municipal_by_id[source["source_candidate_line_id"]]
        row = dict(source)
        row["template_id"] = "UNIFORM_H30_10H"
        row["span_minutes"] = 600
        row["h30_peak_hours"] = 10
        row["h60_base_hours"] = 0
        row["phase_min"] = row.pop("single_line_hub_phase_min")
        row["departure_count"] = 20
        row["exact_total_coverage"] = candidate["exact_total_coverage"]
        row["exact_municipality_coverage"] = candidate[
            "exact_municipality_coverage"]
        uniform_contexts.append(row)
    uniform_reduced = []
    for profile_id in sorted({row["profile_id"] for row in uniform_contexts}):
        uniform_reduced.extend(mixed_pareto_frontier(
            [row for row in uniform_contexts if row["profile_id"] == profile_id],
            codes))
    joint_frontier = mixed_pareto_frontier(
        uniform_reduced + contexts, codes)
    per_template = [{
        "template_id": template["template_id"],
        "span_minutes": template["span_minutes"],
        "h30_peak_hours": template["h30_peak_hours"],
        "h60_base_hours": template["h60_base_hours"],
        "h60_offpeak_hours": template["h60_offpeak_hours"],
        "daily_departure_count": len(template["nominal_departure_minutes"]),
        "evaluated_context_count": sum(
            row["template_id"] == template["template_id"] for row in contexts),
        "pareto_context_count": sum(
            row["template_id"] == template["template_id"] for row in frontier),
        "all_grid_at_most_three_vehicle_context_count": sum(
            row["template_id"] == template["template_id"]
            and row["maximum_exact_vehicle_count"] <= 3 for row in contexts),
        "minimum_of_maximum_exact_vehicle_count": min(
            row["maximum_exact_vehicle_count"] for row in contexts
            if row["template_id"] == template["template_id"]),
        "maximum_of_maximum_exact_vehicle_count": max(
            row["maximum_exact_vehicle_count"] for row in contexts
            if row["template_id"] == template["template_id"]),
    } for template in templates]
    per_profile = [{
        "profile_id": profile["profile_id"],
        "source_candidate_line_id": profile["source_candidate_line_id"],
        "evaluated_context_count": sum(
            row["profile_id"] == profile["profile_id"] for row in contexts),
        "pareto_context_count": sum(
            row["profile_id"] == profile["profile_id"] for row in frontier),
        "all_grid_at_most_three_vehicle_context_count": sum(
            row["profile_id"] == profile["profile_id"]
            and row["maximum_exact_vehicle_count"] <= 3 for row in contexts),
        "minimum_of_maximum_exact_vehicle_count": min(
            row["maximum_exact_vehicle_count"] for row in contexts
            if row["profile_id"] == profile["profile_id"]),
        "maximum_of_maximum_exact_vehicle_count": max(
            row["maximum_exact_vehicle_count"] for row in contexts
            if row["profile_id"] == profile["profile_id"]),
    } for profile in typed["profiles"]]
    output = {
        "contract": "RT031_MIXED_FREQUENCY_TIMETABLE_SURFACE_V4",
        "status": "PASS_TYPED_SUBSET_DIAGNOSTIC_NO_SERVICE_PATTERN_SELECTED",
        "municipal_frontier_candidate_count": municipal["frontier_count"],
        "evaluated_typed_candidate_count": len(profile_ids),
        "typed_subset_complete_for_municipal_frontier": False,
        "evaluated_context_count": len(contexts),
        "evaluated_engineering_realisation_count": sum(
            len(row["engineering_cases"]) for row in contexts),
        "pareto_context_count": len(frontier),
        "phase_domain": list(PHASE_DOMAIN),
        "template_count": len(templates),
        "templates": list(templates),
        "per_template_summary": per_template,
        "per_profile_summary": per_profile,
        "pareto_dimensions": [
            *[{"field": f"potential_core_share_{threshold}min", "direction": "max"}
              for threshold in (5, 8, 10)],
            *[{"field": f"potential_municipality_{code}_share_{threshold}min",
               "direction": "max"}
              for code in codes for threshold in (5, 8, 10)],
            {"field": "retained_current_exact_stop_share", "direction": "max"},
            {"field": "service_span_minutes", "direction": "max"},
            {"field": "h30_peak_hours", "direction": "max"},
            {"field": "robust_min_transfer_quality", "direction": "max"},
            {"field": "robust_unweighted_mean_transfer_quality", "direction": "max"},
            {"field": "conditional_annual_bus_km", "direction": "min"},
            {"field": "maximum_exact_vehicle_count", "direction": "min"},
            *[{"field": f"worst_deterministic_bus_to_rail_miss_share_runtime_stress_{stress}_min",
               "direction": "min"} for stress in (0, 5, 10, 15)],
        ],
        "longer_service_span_is_caller_preference": True,
        "all_templates_have_equal_daily_departure_count": True,
        "h30_h60_hours_partition_span": all(
            template["h30_peak_hours"] + template["h60_offpeak_hours"]
            == template["span_minutes"] // 60
            for template in templates),
        "daily_departure_count": 20,
        "popular_times_role": "QUALITATIVE_TEMPORAL_PLAUSIBILITY_FOR_TESTED_WINDOWS_ONLY",
        "popular_times_used_as_demand": False,
        "popular_times_used_as_weight": False,
        "popular_times_used_as_hard_filter": False,
        "uniform_h30_10h_input_context_count": len(uniform_contexts),
        "uniform_h30_10h_safe_within_profile_preprune_count": len(uniform_reduced),
        "uniform_h30_10h_joint_frontier_comparison_complete": True,
        "joint_pareto_context_count": len(joint_frontier),
        "joint_pareto_uniform_h30_10h_context_count": sum(
            row["template_id"] == "UNIFORM_H30_10H" for row in joint_frontier),
        "joint_pareto_mixed_frequency_context_count": sum(
            row["template_id"] != "UNIFORM_H30_10H" for row in joint_frontier),
        "deterministic_miss_share_is_empirical_missed_connection_probability": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "observed_dwell_validation_complete": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "service_pattern_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "typed_audit": TYPED_AUDIT_SHA256,
            "municipal_frontier": MUNICIPAL_FRONTIER_SHA256,
            "uniform_h30_surface": UNIFORM_H30_SURFACE_SHA256,
            "s8_events": logical_sha256(args.s8_events),
            "sensitivity": logical_sha256(args.sensitivity),
            "popular_times_profile": logical_sha256(args.popular_times_profile),
        },
        "pareto_contexts": frontier,
        "joint_pareto_contexts": joint_frontier,
        "mixed_contexts": contexts,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = args.output_dir / "rt031_mixed_frequency_timetable_surface_v4.json"
    result.write_bytes(canonical(output))
    audit = {key: value for key, value in output.items()
             if key not in {"pareto_contexts", "joint_pareto_contexts",
                            "mixed_contexts"}}
    audit["result_sha256"] = sha256(result)
    (args.output_dir / "rt031_mixed_frequency_timetable_surface_v4_audit.json").write_bytes(
        canonical(audit))
    print(json.dumps(audit, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed-audit", type=Path, required=True)
    parser.add_argument("--municipal-frontier", type=Path, required=True)
    parser.add_argument("--uniform-h30-surface", type=Path, required=True)
    parser.add_argument("--s8-events", type=Path, required=True)
    parser.add_argument("--sensitivity", type=Path, required=True)
    parser.add_argument("--popular-times-profile", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
