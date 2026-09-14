#!/usr/bin/env python3
"""Build the exact no-weight hub-phase frontier for the corrected RT-031 pair."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from src.phase2_exact_timetable_optimizer_v2 import load_profiles
from src.phase2_rt031_hub_phase_frontier_v3 import exact_surface, pareto_frontier


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def main(args):
    typed = json.loads(args.typed_audit.read_text(encoding="utf-8"))
    if typed.get("contract") != "RT031_TARGET_COVER_TYPED_SERVICE_SHORTLIST_V3":
        raise ValueError("unexpected typed candidate contract")
    if typed.get("every_component_serves_olgiate_fs") is not True:
        raise ValueError("all components must serve Olgiate FS")
    if typed.get("network_selected") is not False:
        raise ValueError("candidate selection boundary changed")
    profiles = typed.get("profiles", [])
    if len(profiles) != 1 or profiles[0].get("profile_id") != "TARGET_COVER_2M_H60_16H_260D":
        raise ValueError("corrected two-movement H60 profile required")
    if profiles[0].get("movement_count") != 2 or profiles[0].get("timetable_assigned") is not False:
        raise ValueError("candidate movement/timetable semantics changed")

    transfer_profiles = load_profiles(args.sensitivity)
    with args.s8_events.open(encoding="utf-8", newline="") as handle:
        rail_events = list(csv.DictReader(handle))
    if len(rail_events) != 74:
        raise ValueError("frozen S8 event universe changed")

    surface = exact_surface(rail_events, transfer_profiles, period=60)
    regular_h30 = [
        row for row in surface["phase_vectors"]
        if row["combined_hub_max_gap_min"] == 30
    ]
    regular_h30_frontier = pareto_frontier(regular_h30)
    dimension_names = [
        key for key in surface["phase_vectors"][0]
        if key not in {"route_1_hub_phase_min", "route_2_hub_phase_min"}
    ]
    output = {
        "contract": "RT031_HUB_PHASE_PARETO_FRONTIER_V3",
        "status": "PASS_EXACT_NON_DECISIONAL_PHASE_FRONTIER",
        "candidate_profile_id": profiles[0]["profile_id"],
        "hub_event_semantics": (
            "REPEATING_PUBLIC_PICKUP_DROPOFF_EVENT_AT_OLGIATE_FS;"
            "CLOCK_PHASE_ONLY_NOT_DAILY_TIMETABLE"
        ),
        "cyclic_period_min": 60,
        "phase_domain": "ORDERED_ROUTE_SPECIFIC_INTEGER_MINUTES_0_TO_59",
        "evaluated_phase_vector_count": surface["evaluated_phase_vector_count"],
        "frontier_phase_vector_count": len(surface["frontier"]),
        "regular_30_min_hub_subset": {
            "status": "DIAGNOSTIC_DESIGN_SUBSPACE_NOT_SELECTED",
            "rule": "combined_hub_max_gap_min == 30",
            "phase_vector_count": len(regular_h30),
            "pareto_phase_vector_count": len(regular_h30_frontier),
        },
        "pareto_dimensions": [
            {
                "field": name,
                "direction": "min" if name == "combined_hub_max_gap_min" else "max",
            }
            for name in dimension_names
        ],
        "transfer_profile_status": "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL",
        "rail_event_status": "FROZEN_OFFICIAL_GTFS_2026_09_03",
        "passenger_demand_weights_applied": False,
        "municipal_od_spatially_downscaled": False,
        "empirical_missed_connection_probability_computed": False,
        "deterministic_robustness_claimed": False,
        "daily_service_span_selected": False,
        "timetable_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "typed_audit": sha256(args.typed_audit),
            "s8_events": sha256(args.s8_events),
            "sensitivity": sha256(args.sensitivity),
        },
        "frontier": surface["frontier"],
        "regular_30_min_hub_frontier": regular_h30_frontier,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "rt031_hub_phase_frontier_v3.json").write_bytes(canonical(output))
    audit = {
        key: value for key, value in output.items()
        if key not in {"frontier", "regular_30_min_hub_frontier"}
    }
    audit["frontier_sha256"] = sha256(args.output_dir / "rt031_hub_phase_frontier_v3.json")
    (args.output_dir / "rt031_hub_phase_frontier_v3_audit.json").write_bytes(canonical(audit))
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed-audit", type=Path, required=True)
    parser.add_argument("--s8-events", type=Path, required=True)
    parser.add_argument("--sensitivity", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
