#!/usr/bin/env python3
"""Exact H30 hub-phase surface for all five typed development profiles."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from src.phase2_exact_timetable_optimizer_v2 import load_profiles
from src.phase2_rt031_hub_phase_frontier_v3 import (
    exact_repeating_surface,
    pareto_frontier,
)


TYPED_AUDIT_SHA256 = "32c0c7677a3e352b0876a2285694008b3242f2347a61b91c1faa588096c0513f"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def main(args):
    if sha256(args.typed_audit) != TYPED_AUDIT_SHA256:
        raise ValueError("pinned typed-shortlist lineage drift")
    typed = json.loads(args.typed_audit.read_text(encoding="utf-8"))
    if (typed.get("contract")
            != "RT031_FREQUENT_ACCESS_TYPED_DEVELOPMENT_SHORTLIST_V3"
            or typed.get("status")
            != "PASS_FIVE_TYPED_DEVELOPMENT_PROFILES_PENDING_OPERATIONS"
            or typed.get("profile_count") != 5
            or typed.get("every_component_serves_olgiate_fs") is not True
            or typed.get("network_selected") is not False):
        raise ValueError("typed development-shortlist contract drift")
    profiles = typed["profiles"]
    if any(row.get("headway_min_design_context") != 30
           or row.get("span_minutes_design_context") != 720
           or row.get("movement_count") != 2
           or row.get("timetable_assigned") is not False
           for row in profiles):
        raise ValueError("frequent development service context drift")

    transfer_profiles = load_profiles(args.sensitivity)
    with args.s8_events.open(encoding="utf-8", newline="") as handle:
        rail_events = list(csv.DictReader(handle))
    if len(rail_events) != 74:
        raise ValueError("frozen S8 event universe changed")
    surface = exact_repeating_surface(
        rail_events, transfer_profiles, route_headway_min=30, period=60)
    regular_h15 = [row for row in surface["phase_vectors"]
                   if row["combined_hub_max_gap_min"] == 15]
    regular_h15_frontier = pareto_frontier(regular_h15)
    dimensions = [key for key in surface["phase_vectors"][0]
                  if key not in {"route_1_hub_phase_min", "route_2_hub_phase_min"}]
    output = {
        "contract": "RT031_FREQUENT_SHORTLIST_HUB_PHASE_FRONTIER_V3",
        "status": "PASS_EXACT_NON_DECISIONAL_H30_PHASE_FRONTIER",
        "candidate_profile_ids": [row["profile_id"] for row in profiles],
        "candidate_profile_count": len(profiles),
        "shared_phase_surface_across_profiles": True,
        "reason_shared": (
            "ALL_PROFILES_HAVE_TWO_INDEPENDENT_H30_COMPONENTS_AND_PHASE_METRICS_USE_HUB_EVENTS_ONLY"),
        "clock_period_min": 60,
        "per_component_headway_min": 30,
        "phase_domain": "ORDERED_ROUTE_SPECIFIC_INTEGER_MINUTES_0_TO_29",
        "evaluated_phase_vector_count": surface["evaluated_phase_vector_count"],
        "frontier_phase_vector_count": len(surface["frontier"]),
        "regular_15_min_combined_hub_subset": {
            "status": "DIAGNOSTIC_DESIGN_SUBSPACE_NOT_SELECTED",
            "rule": "combined_hub_max_gap_min == 15",
            "phase_vector_count": len(regular_h15),
            "pareto_phase_vector_count": len(regular_h15_frontier),
        },
        "pareto_dimensions": [{
            "field": name,
            "direction": "min" if name == "combined_hub_max_gap_min" else "max",
        } for name in dimensions],
        "rail_event_status": "FROZEN_OFFICIAL_GTFS_2026_09_03",
        "transfer_profile_status": "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL",
        "runtime_dwell_recovery_grid_linked": True,
        "runtime_grid_all_cases_two_vehicle_feasible": False,
        "daily_span_boundary": "12H_DESIGN_CONTEXT_NOT_EXACT_DAILY_TRIP_TABLE",
        "passenger_demand_weights_applied": False,
        "empirical_missed_connection_probability_computed": False,
        "timetable_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "typed_audit": TYPED_AUDIT_SHA256,
            "s8_events": sha256(args.s8_events),
            "sensitivity": sha256(args.sensitivity),
        },
        "frontier": surface["frontier"],
        "regular_15_min_combined_hub_frontier": regular_h15_frontier,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "rt031_frequent_hub_phase_frontier_v3.json"
    path.write_bytes(canonical(output))
    audit = {key: value for key, value in output.items()
             if key not in {"frontier", "regular_15_min_combined_hub_frontier"}}
    audit["frontier_sha256"] = sha256(path)
    (args.output_dir / "rt031_frequent_hub_phase_frontier_v3_audit.json").write_bytes(
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
