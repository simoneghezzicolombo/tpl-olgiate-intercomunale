#!/usr/bin/env python3
"""Build the exhaustive non-decisional H30 daily timetable surface."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from src.phase2_exact_timetable_optimizer_v2 import load_profiles, rail_event_index
from src.phase2_rt031_daily_timetable_surface_v3 import (
    HEADWAY_MIN, SPAN_MINUTES, aligned_span_starts,
    evaluate_timetable_context, regular_h15_phase_vectors,
    robust_pareto_frontier,
)

TYPED_AUDIT_SHA256 = "32c0c7677a3e352b0876a2285694008b3242f2347a61b91c1faa588096c0513f"
PHASE_FRONTIER_SHA256 = "c2fe62139941fb5eed70d223d82a29b9cd9fa71fcc9f8fae7d60768219da4d8d"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def main(args):
    if sha256(args.typed_audit) != TYPED_AUDIT_SHA256:
        raise ValueError("pinned typed-shortlist lineage drift")
    if sha256(args.phase_frontier) != PHASE_FRONTIER_SHA256:
        raise ValueError("pinned exact phase-frontier lineage drift")
    typed = json.loads(args.typed_audit.read_text(encoding="utf-8"))
    phase = json.loads(args.phase_frontier.read_text(encoding="utf-8"))
    if (typed.get("status") != "PASS_FIVE_TYPED_DEVELOPMENT_PROFILES_PENDING_OPERATIONS"
            or typed.get("profile_count") != 5
            or typed.get("network_selected") is not False):
        raise ValueError("typed shortlist contract drift")
    if (phase.get("status") != "PASS_EXACT_NON_DECISIONAL_H30_PHASE_FRONTIER"
            or phase.get("timetable_selected") is not False
            or phase["regular_15_min_combined_hub_subset"]["phase_vector_count"] != 30):
        raise ValueError("phase-frontier contract drift")
    expected_ids = [row["profile_id"] for row in typed["profiles"]]
    if phase.get("candidate_profile_ids") != expected_ids:
        raise ValueError("candidate identity lineage changed")

    transfer_profiles = load_profiles(args.sensitivity)
    with args.s8_events.open(encoding="utf-8", newline="") as handle:
        events = list(csv.DictReader(handle))
    if len(events) != 74:
        raise ValueError("frozen S8 event universe changed")
    rail = rail_event_index(events)
    starts = aligned_span_starts()
    vectors = regular_h15_phase_vectors()
    evidence_vectors = sorted(
        (int(row["route_1_hub_phase_min"]), int(row["route_2_hub_phase_min"]))
        for row in phase["regular_15_min_combined_hub_frontier"])
    if sorted(vectors) != evidence_vectors:
        raise ValueError("regular-H15 diagnostic phase domain changed")

    contexts = []
    for profile in typed["profiles"]:
        for start in starts:
            for vector in vectors:
                contexts.append(evaluate_timetable_context(
                    profile, phase_vector=vector, span_start=start,
                    rail_index=rail, transfer_profiles=transfer_profiles))
    frontier = robust_pareto_frontier(contexts)
    two_vehicle = [row for row in contexts
                   if row["all_engineering_cases_at_most_two_vehicles"]]
    per_profile = []
    for identity in expected_ids:
        subset = [row for row in contexts if row["profile_id"] == identity]
        per_profile.append({
            "profile_id": identity,
            "timetable_context_count": len(subset),
            "robust_pareto_context_count": sum(
                row["profile_id"] == identity for row in frontier),
            "all_case_two_vehicle_context_count": sum(
                row["all_engineering_cases_at_most_two_vehicles"] for row in subset),
            "minimum_of_maximum_exact_vehicle_count": min(
                row["maximum_exact_interlinable_vehicle_count"] for row in subset),
            "maximum_of_maximum_exact_vehicle_count": max(
                row["maximum_exact_interlinable_vehicle_count"] for row in subset),
        })
    output = {
        "contract": "RT031_FREQUENT_DAILY_TIMETABLE_ROBUST_SURFACE_V3",
        "status": "PASS_EXHAUSTIVE_DECLARED_SURFACE_NO_TIMETABLE_SELECTED",
        "candidate_profile_count": len(expected_ids),
        "candidate_profile_ids": expected_ids,
        "headway_min_per_component": HEADWAY_MIN,
        "combined_hub_pattern": "REGULAR_H15_DIAGNOSTIC_SUBSPACE",
        "span_minutes": SPAN_MINUTES,
        "span_start_domain": list(starts),
        "span_domain_rule": "ALL_H30_ALIGNED_12H_WINDOWS_CONTAINED_IN_FROZEN_S8_0530_2400_DESIGN_WINDOW",
        "phase_vector_count_per_span": len(vectors),
        "engineering_case_count_per_context": 27,
        "evaluated_timetable_context_count": len(contexts),
        "evaluated_engineering_realisation_count": sum(
            row["engineering_case_count"] for row in contexts),
        "robust_pareto_context_count": len(frontier),
        "all_case_two_vehicle_context_count": len(two_vehicle),
        "per_profile_summary": per_profile,
        "pareto_dimensions": [
            *[{"field": f"exact_access_ratio_{index + 1}", "direction": "max"}
              for index in range(6)],
            {"field": "robust_min_transfer_quality", "direction": "max"},
            {"field": "robust_unweighted_mean_transfer_quality", "direction": "max"},
            {"field": "maximum_exact_interlinable_vehicle_count", "direction": "min"},
            *[{"field": f"worst_bus_to_rail_miss_share_runtime_stress_{stress}_min",
               "direction": "min"} for stress in (0, 5, 10, 15)],
        ],
        "transfer_quality_status": "ASSUMPTION_SENSITIVITY_NOT_PASSENGER_WEIGHTED",
        "runtime_dwell_recovery_status": "DETERMINISTIC_INHERITED_GRID_NOT_PROBABILITY",
        "observed_dwell_validation_complete": False,
        "span_selected": False,
        "phase_selected": False,
        "timetable_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "typed_audit": TYPED_AUDIT_SHA256,
            "phase_frontier": PHASE_FRONTIER_SHA256,
            "s8_events": sha256(args.s8_events),
            "sensitivity": sha256(args.sensitivity),
        },
        "robust_pareto_contexts": frontier,
        "all_contexts": contexts,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "rt031_frequent_daily_timetable_surface_v3.json"
    result_path.write_bytes(canonical(output))
    audit = {key: value for key, value in output.items()
             if key not in {"robust_pareto_contexts", "all_contexts"}}
    audit["result_sha256"] = sha256(result_path)
    (args.output_dir / "rt031_frequent_daily_timetable_surface_v3_audit.json").write_bytes(
        canonical(audit))
    print(json.dumps(audit, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed-audit", type=Path, required=True)
    parser.add_argument("--phase-frontier", type=Path, required=True)
    parser.add_argument("--s8-events", type=Path, required=True)
    parser.add_argument("--sensitivity", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
