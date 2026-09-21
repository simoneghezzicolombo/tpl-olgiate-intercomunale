#!/usr/bin/env python3
"""Full 736-line, 30-phase H30-peak/H60-off-peak 18h diagnostic surface."""
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
    mixed_service_templates,
)


TYPED_SHA256 = "d2d27d1c5fb4f1faaeaa4d911735daab57c64dd3a173c2e887c500027cb9f60f"
SHARD_COUNT = 8
PROFILE_COUNT = 736
TEMPLATE_ID = "H30_PEAK_H60_18H"


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def logical_sha256(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate_typed(path):
    if sha256(path) != TYPED_SHA256:
        raise ValueError("pinned complete typed frontier drift")
    typed = json.loads(path.read_text(encoding="utf-8"))
    if (typed.get("contract") != "RT031_MUNICIPAL_FRONTIER_TYPED_BINDING_V4"
            or typed.get("status")
            != "PASS_FULL_WITHIN_CAP_FRONTIER_TYPED_PENDING_OPERATIONS"
            or typed.get("within_cap_profile_count") != PROFILE_COUNT
            or typed.get("within_cap_frontier_binding_complete") is not True
            or typed.get("network_selected") is not False):
        raise ValueError("typed frontier contract drift")
    profiles = sorted(typed["profiles"], key=lambda row: row[
        "source_candidate_line_id"])
    if len(profiles) != PROFILE_COUNT or len({row["source_candidate_line_id"]
                                               for row in profiles}) != PROFILE_COUNT:
        raise ValueError("typed frontier identity drift")
    return profiles


def compact_context(row):
    return {key: value for key, value in row.items()
            if key not in {"engineering_cases", "departures_min"}}


def build_shard(args):
    if not 0 <= args.shard_index < SHARD_COUNT:
        raise ValueError("invalid shard index")
    profiles = validate_typed(args.typed_audit)
    selected = profiles[args.shard_index::SHARD_COUNT]
    with args.s8_events.open(encoding="utf-8", newline="") as handle:
        events = list(csv.DictReader(handle))
    if len(events) != 74:
        raise ValueError("frozen S8 event count drift")
    rail = rail_event_index(events)
    transfer_profiles = load_profiles(args.sensitivity)
    template = next(row for row in mixed_service_templates()
                    if row["template_id"] == TEMPLATE_ID)
    contexts = [compact_context(evaluate_mixed_context(
        profile, profile, template=template, phase=phase,
        rail_index=rail, transfer_profiles=transfer_profiles))
        for profile in selected for phase in PHASE_DOMAIN]
    if len(selected) != PROFILE_COUNT // SHARD_COUNT or len(contexts) != (
            PROFILE_COUNT // SHARD_COUNT) * len(PHASE_DOMAIN):
        raise ValueError("shard coverage drift")
    result = {
        "contract": "RT031_FULL_MUNICIPAL_18H_PHASE_SHARD_V4",
        "status": "PASS_FULL_SHARD_NON_DECISIONAL",
        "shard_index": args.shard_index,
        "shard_count": SHARD_COUNT,
        "profile_count": len(selected),
        "context_count": len(contexts),
        "engineering_cases_per_context": 27,
        "template_id": TEMPLATE_ID,
        "input_sha256": {
            "typed_audit": TYPED_SHA256,
            "s8_events": logical_sha256(args.s8_events),
            "sensitivity": logical_sha256(args.sensitivity),
        },
        "contexts": contexts,
        "service_pattern_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / f"full_municipal_18h_phase_shard_{args.shard_index}.json"
    path.write_bytes(canonical(result))
    return result


def aggregate_shards(paths, expected_ids):
    if len(paths) != SHARD_COUNT:
        raise ValueError("all eight shards required")
    shards = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    indices = [row.get("shard_index") for row in shards]
    if set(indices) != set(range(SHARD_COUNT)) or len(set(indices)) != SHARD_COUNT:
        raise ValueError("shard index coverage drift")
    lineage = shards[0]["input_sha256"]
    if lineage.get("typed_audit") != TYPED_SHA256:
        raise ValueError("aggregate typed lineage drift")
    contexts = []
    for shard in shards:
        if (shard.get("contract") != "RT031_FULL_MUNICIPAL_18H_PHASE_SHARD_V4"
                or shard.get("status") != "PASS_FULL_SHARD_NON_DECISIONAL"
                or shard.get("shard_count") != SHARD_COUNT
                or shard.get("profile_count") != PROFILE_COUNT // SHARD_COUNT
                or shard.get("context_count") != (PROFILE_COUNT // SHARD_COUNT) * 30
                or shard.get("engineering_cases_per_context") != 27
                or shard.get("template_id") != TEMPLATE_ID
                or shard.get("input_sha256") != lineage
                or shard.get("network_selected") is not False):
            raise ValueError("shard contract or lineage drift")
        contexts.extend(shard["contexts"])
    keys = {(row["source_candidate_line_id"], row["phase_min"])
            for row in contexts}
    if (len(contexts) != PROFILE_COUNT * 30 or len(keys) != len(contexts)
            or {identity for identity, _ in keys} != set(expected_ids)
            or any({phase for identity, phase in keys if identity == candidate}
                   != set(PHASE_DOMAIN) for candidate in expected_ids)):
        raise ValueError("full candidate/phase coverage drift")
    contexts.sort(key=lambda row: (row["source_candidate_line_id"],
                                   row["phase_min"]))
    by_candidate = {}
    for row in contexts:
        by_candidate.setdefault(row["source_candidate_line_id"], []).append(row)
    summaries = []
    for identity, rows in sorted(by_candidate.items()):
        summaries.append({
            "source_candidate_line_id": identity,
            "retained_current_exact_stop_count": rows[0][
                "retained_current_exact_stop_count"],
            "maximum_exact_vehicle_count_across_phases": max(
                row["maximum_exact_vehicle_count"] for row in rows),
            "robust_min_transfer_quality_range": [
                min(row["robust_min_transfer_quality"] for row in rows),
                max(row["robust_min_transfer_quality"] for row in rows)],
            "robust_unweighted_mean_transfer_quality_range": [
                min(row["robust_unweighted_mean_transfer_quality"] for row in rows),
                max(row["robust_unweighted_mean_transfer_quality"] for row in rows)],
        })
    return {
        "contract": "RT031_FULL_MUNICIPAL_18H_PHASE_SURFACE_V4",
        "status": "PASS_COMPLETE_NON_DECISIONAL_18H_PHASE_SURFACE",
        "within_cap_candidate_count": PROFILE_COUNT,
        "phase_count_per_candidate": len(PHASE_DOMAIN),
        "context_count": len(contexts),
        "engineering_realisation_count": len(contexts) * 27,
        "template_id": TEMPLATE_ID,
        "daily_departure_count": 20,
        "service_span_minutes": 1080,
        "h30_peak_hours": 2,
        "h60_offpeak_hours": 16,
        "input_sha256": lineage,
        "pareto_frontier_computed": False,
        "popular_times_used_as_demand": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "deterministic_miss_share_is_empirical_probability": False,
        "observed_dwell_validation_complete": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "service_pattern_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "candidate_summaries": summaries,
        "contexts": contexts,
    }


def build_aggregate(args):
    profiles = validate_typed(args.typed_audit)
    expected = [row["source_candidate_line_id"] for row in profiles]
    paths = sorted(args.shard_dir.rglob("full_municipal_18h_phase_shard_*.json"))
    result = aggregate_shards(paths, expected)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "full_municipal_18h_phase_surface_v4.json"
    path.write_bytes(canonical(result))
    audit = {key: value for key, value in result.items()
             if key not in {"contexts", "candidate_summaries"}}
    audit["result_sha256"] = sha256(path)
    (args.output_dir / "full_municipal_18h_phase_surface_v4_audit.json").write_bytes(
        canonical(audit))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("shard", "aggregate"))
    parser.add_argument("--typed-audit", type=Path, required=True)
    parser.add_argument("--s8-events", type=Path)
    parser.add_argument("--sensitivity", type=Path)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "shard":
        if (args.s8_events is None or args.sensitivity is None
                or args.shard_index is None):
            parser.error("shard requires events, sensitivity and index")
        build_shard(args)
    else:
        if args.shard_dir is None:
            parser.error("aggregate requires shard directory")
        build_aggregate(args)
