#!/usr/bin/env python3
"""Build the exhaustive H30/10h timetable surface for eight one-line candidates."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from src.phase2_exact_timetable_optimizer_v2 import load_profiles, rail_event_index
from src.phase2_rt031_single_line_timetable_surface_v3 import (
    HEADWAY_MIN,
    SPAN_MINUTES,
    evaluate_single_line_context,
    robust_single_line_pareto_frontier,
    single_line_phase_vectors,
    single_line_span_starts,
)


TYPED_AUDIT_SHA256 = "80e912ab0775461cb63d8be9f6efb8daa0d6bf45a330d4e78dbd9bcdde387be3"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def main(args):
    if sha256(args.typed_audit) != TYPED_AUDIT_SHA256:
        raise ValueError("pinned one-line typed audit lineage drift")
    typed = json.loads(args.typed_audit.read_text(encoding="utf-8"))
    if (typed.get("contract") != "RT031_SINGLE_LINE_H30_10H_TYPED_CONTEXT_V3"
            or typed.get("status")
            != "PASS_EIGHT_TYPED_SINGLE_LINE_CANDIDATES_PENDING_OPERATIONS"
            or typed.get("profile_count") != 8
            or typed.get("single_recognizable_line_structure_certified") is not True
            or typed.get("network_selected") is not False):
        raise ValueError("typed one-line contract drift")
    transfer_profiles = load_profiles(args.sensitivity)
    with args.s8_events.open(encoding="utf-8", newline="") as handle:
        events = list(csv.DictReader(handle))
    if len(events) != 74:
        raise ValueError("frozen S8 event universe changed")
    rail = rail_event_index(events)
    starts = single_line_span_starts()
    vectors = single_line_phase_vectors()
    contexts = [evaluate_single_line_context(
        profile, phase=vector[0], span_start=start,
        rail_index=rail, transfer_profiles=transfer_profiles)
        for profile in typed["profiles"] for start in starts for vector in vectors]
    frontier = robust_single_line_pareto_frontier(contexts)
    profile_ids = [row["profile_id"] for row in typed["profiles"]]
    per_profile = []
    for identity in profile_ids:
        subset = [row for row in contexts if row["profile_id"] == identity]
        per_profile.append({
            "profile_id": identity,
            "timetable_context_count": len(subset),
            "robust_pareto_context_count": sum(
                row["profile_id"] == identity for row in frontier),
            "all_case_two_vehicle_context_count": sum(
                row["all_engineering_cases_at_most_two_vehicles"]
                for row in subset),
            "minimum_of_maximum_exact_vehicle_count": min(
                row["maximum_exact_vehicle_count"] for row in subset),
            "maximum_of_maximum_exact_vehicle_count": max(
                row["maximum_exact_vehicle_count"] for row in subset),
        })
    output = {
        "contract": "RT031_SINGLE_LINE_H30_10H_DAILY_TIMETABLE_SURFACE_V3",
        "status": "PASS_EXHAUSTIVE_DECLARED_SURFACE_NO_TIMETABLE_SELECTED",
        "candidate_profile_count": len(profile_ids),
        "candidate_profile_ids": profile_ids,
        "headway_min": HEADWAY_MIN,
        "span_minutes": SPAN_MINUTES,
        "span_start_domain": list(starts),
        "span_domain_rule": "ALL_H30_ALIGNED_10H_WINDOWS_WITHIN_FROZEN_S8_0530_2400_DESIGN_WINDOW",
        "phase_vector_count_per_span": len(vectors),
        "engineering_case_count_per_context": 27,
        "evaluated_timetable_context_count": len(contexts),
        "evaluated_engineering_realisation_count": sum(
            row["engineering_case_count"] for row in contexts),
        "robust_pareto_context_count": len(frontier),
        "per_profile_summary": per_profile,
        "pareto_dimensions": [
            *[{"field": f"exact_access_ratio_{index + 1}", "direction": "max"}
              for index in range(6)],
            {"field": "retained_current_exact_stop_share", "direction": "max"},
            {"field": "robust_min_transfer_quality", "direction": "max"},
            {"field": "robust_unweighted_mean_transfer_quality", "direction": "max"},
            {"field": "conditional_annual_bus_km", "direction": "min"},
            {"field": "maximum_exact_vehicle_count", "direction": "min"},
            *[{"field": f"worst_deterministic_bus_to_rail_miss_share_runtime_stress_{stress}_min",
               "direction": "min"} for stress in (0, 5, 10, 15)],
        ],
        "weighted_score": False,
        "current_stop_retention_is_pareto_preference": True,
        "transfer_quality_status": "ASSUMPTION_SENSITIVITY_NOT_PASSENGER_WEIGHTED",
        "runtime_dwell_recovery_status": "DETERMINISTIC_ENGINEERING_GRID_NOT_PROBABILITY",
        "deterministic_miss_share_is_empirical_missed_connection_probability": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "observed_dwell_validation_complete": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "span_selected": False,
        "phase_selected": False,
        "timetable_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "typed_audit": TYPED_AUDIT_SHA256,
            "s8_events": sha256(args.s8_events),
            "sensitivity": sha256(args.sensitivity),
        },
        "robust_pareto_contexts": frontier,
        "all_contexts": contexts,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = args.output_dir / "single_line_h30_timetable_surface_v3.json"
    result.write_bytes(canonical(output))
    audit = {key: value for key, value in output.items()
             if key not in {"robust_pareto_contexts", "all_contexts"}}
    audit["result_sha256"] = sha256(result)
    (args.output_dir / "single_line_h30_timetable_surface_v3_audit.json").write_bytes(
        canonical(audit))
    print(json.dumps(audit, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed-audit", type=Path, required=True)
    parser.add_argument("--s8-events", type=Path, required=True)
    parser.add_argument("--sensitivity", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
