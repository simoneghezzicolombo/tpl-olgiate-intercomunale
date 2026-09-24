#!/usr/bin/env python3
"""Materialise Phase-2 Stage-D exact timetables and S8 phase selection V2."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

from src.phase2_exact_timetable_optimizer_v2 import (
    RECOVERIES,
    RouteInput,
    brute_force_oracle,
    bus_to_rail_miss_share_by_stress,
    choose_exact_phase_vector,
    clockface_times,
    exact_vehicle_blocks,
    load_profiles,
    precompute_route_phase_cells,
    rail_event_index,
    strict_bool,
)

STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2"
CONTRACT = "PHASE2_EXHAUSTIVE_EXACT_TIMETABLE_S8_AND_VEHICLE_BLOCKS_V2"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def load_routes(path: Path) -> dict[str, RouteInput]:
    result: dict[str, RouteInput] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            route = RouteInput(
                route_id=str(row["route_id"]),
                public_runtime_min=float(row["public_runtime_min"]),
                cycle_runtime_min=float(row["cycle_runtime_min"]),
                public_service_starts_at_hub=strict_bool(row["public_service_starts_at_hub"]),
                public_service_returns_to_hub=strict_bool(row["public_service_returns_to_hub"]),
                vehicle_closure_added=strict_bool(row["vehicle_closure_added"]),
                rail_to_bus_passenger_event_supported=strict_bool(row["rail_to_bus_passenger_event_supported"]),
                bus_to_rail_passenger_event_supported=strict_bool(row["bus_to_rail_passenger_event_supported"]),
            )
            route.validate()
            if route.route_id in result:
                raise ValueError(f"duplicate route {route.route_id}")
            result[route.route_id] = route
    if not result:
        raise ValueError("empty Stage-D route input")
    return result


def load_rail(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "trip_id": str(row["trip_id"]),
                "direction": str(row["direction"]).upper(),
                "arrival_min": float(row["arrival_min"]),
                "departure_min": float(row["departure_min"]),
            })
    if len(rows) != 74:
        raise ValueError(f"expected 74 frozen S8 events, got {len(rows)}")
    return rows


def validate_upstream(args) -> dict:
    val = read_json(args.input_validation)
    if val.get("status") != "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_V2":
        raise ValueError("Stage-D input manifest is not PASS")
    if val.get("contract") != "PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_V2":
        raise ValueError("unexpected Stage-D input contract")
    if int(val.get("stage_d_daily_timing_input_count", -1)) != 5345:
        raise ValueError("Stage-D input count changed")
    if int(val.get("passenger_plan_context_count_represented", -1)) != 16883:
        raise ValueError("Stage-C decision context count changed")
    if val.get("daily_timing_context_deduplicated_losslessly") is not True:
        raise ValueError("Stage-D input deduplication is not certified lossless")
    for key in ("phase_selected", "exact_timetable_constructed", "joint_vehicle_block_feasibility_evaluated", "candidate_eliminated", "decision_budget_selected", "calendar_selected", "recovery_selected", "primary_selected", "runner_up_selected", "weighted_composite_score"):
        if val.get(key) is not False:
            raise ValueError(f"upstream selection boundary violated: {key}")
    lineage = val.get("lineage", {})
    if lineage.get("timing_output_sha256") not in (None, sha256_path(args.timing_input)):
        raise ValueError("Stage-D timing input hash mismatch")
    if lineage.get("route_output_sha256") not in (None, sha256_path(args.route_input)):
        raise ValueError("Stage-D route input hash mismatch")
    return val


def close_writer(raw, text) -> None:
    text.flush(); text.close(); raw.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--timing-input", type=Path, required=True)
    p.add_argument("--route-input", type=Path, required=True)
    p.add_argument("--input-validation", type=Path, required=True)
    p.add_argument("--s8-events", type=Path, required=True)
    p.add_argument("--s8-sensitivity", type=Path, required=True)
    p.add_argument("--summary-output", type=Path, required=True)
    p.add_argument("--trips-output", type=Path, required=True)
    p.add_argument("--validation-output", type=Path, required=True)
    args = p.parse_args()
    for path in (args.timing_input, args.route_input, args.input_validation, args.s8_events, args.s8_sensitivity):
        if not path.is_file():
            raise FileNotFoundError(path)

    input_val = validate_upstream(args)
    route_lookup = load_routes(args.route_input)
    rail_events = load_rail(args.s8_events)
    rail_index = rail_event_index(rail_events)
    profiles = load_profiles(args.s8_sensitivity)

    with gzip.open(args.timing_input, "rt", encoding="utf-8", newline="") as f:
        timing_rows = list(csv.DictReader(f))
    if len(timing_rows) != 5345:
        raise ValueError(f"expected 5345 timing inputs, got {len(timing_rows)}")
    timing_rows.sort(key=lambda r: str(r["stage_d_input_id"]))

    summary_fields = [
        "stage_d_input_id", "scenario_id", "topology_family", "uniform_headway_min", "span_id", "span_start_min", "span_end_min",
        "public_route_count", "public_route_ids_json", "selected_phase_vector_json", "phase_vectors_evaluated", "oracle_phase_vectors_evaluated",
        "robust_min_transfer_quality", "robust_unweighted_mean_transfer_quality", "explicit_public_trip_count",
        "exact_fleet_recovery5", "exact_fleet_recovery10", "exact_fleet_recovery15", "bus_to_rail_miss_share_by_runtime_stress_json",
        "represented_plan_count", "represented_plan_context_ids_json", "represented_budget_suffixes_json", "represented_calendar_ids_json",
        "retained_current_localizable_cluster_count", "retained_current_localizable_cluster_share",
        "retained_current_localizable_directed_adjacent_pair_count", "retained_current_localizable_directed_adjacent_pair_share",
        "historical_station_cluster_EX_011_retained", "phase_selected", "exact_timetable_constructed", "recovery_selected",
        "decision_budget_selected", "primary_selected", "runner_up_selected", "weighted_composite_score",
    ]
    trip_fields = [
        "stage_d_input_id", "scenario_id", "route_id", "phase_offset_min", "trip_ordinal", "hub_departure_min",
        "public_hub_return_min", "vehicle_hub_return_min", "vehicle_block_recovery5", "vehicle_block_recovery10", "vehicle_block_recovery15",
    ]
    sraw, stext, swriter = deterministic_gzip_writer(args.summary_output, summary_fields)
    traw, ttext, twriter = deterministic_gzip_writer(args.trips_output, trip_fields)

    total_vectors = 0
    total_trips = 0
    one_route = 0
    two_route = 0
    fleet_ranges = {r: [] for r in RECOVERIES}
    selected_quality_min = []
    represented_contexts: set[str] = set()
    route_phase_cache: dict[tuple[str,int,int,int], tuple[tuple[float, ...], ...]] = {}

    try:
        for row in timing_rows:
            input_id = str(row["stage_d_input_id"])
            headway = int(row["uniform_headway_min"])
            start, end = int(row["span_start_min"]), int(row["span_end_min"])
            route_ids = tuple(str(v) for v in json.loads(row["public_route_ids_json"]))
            if len(route_ids) != int(row["public_route_count"]) or len(set(route_ids)) != len(route_ids):
                raise ValueError(f"invalid route set for {input_id}")
            routes = tuple(route_lookup[rid] for rid in route_ids)
            if len(routes) == 1: one_route += 1
            elif len(routes) == 2: two_route += 1
            else: raise ValueError(f"unsupported route count {len(routes)} for {input_id}")

            route_tables = []
            for route in routes:
                cache_key = (route.route_id, headway, start, end)
                table = route_phase_cache.get(cache_key)
                if table is None:
                    table = precompute_route_phase_cells((route,), headway=headway, span_start=start, span_end=end, rail_index=rail_index, profiles=profiles)[0]
                    route_phase_cache[cache_key] = table
                route_tables.append(table)
            precomputed = tuple(route_tables)
            selected, count = choose_exact_phase_vector(headway, precomputed)
            oracle, oracle_count = brute_force_oracle(headway, precomputed)
            expected_count = int(row["naive_joint_phase_vector_count"])
            if count != expected_count or oracle_count != expected_count:
                raise AssertionError(f"phase domain cardinality mismatch for {input_id}")
            if selected.phase_vector != oracle.phase_vector or selected.objective_key != oracle.objective_key:
                raise AssertionError(f"oracle mismatch for {input_id}")
            total_vectors += count
            selected_quality_min.append(selected.robust_min_transfer_quality)

            block_assignments: dict[int, dict[tuple[str, int], int]] = {}
            fleet_by_recovery: dict[int, int] = {}
            for recovery in RECOVERIES:
                fleet, assignment = exact_vehicle_blocks(routes, selected.phase_vector, headway=headway, span_start=start, span_end=end, recovery_min=recovery)
                fleet_by_recovery[recovery] = fleet
                block_assignments[recovery] = assignment
                fleet_ranges[recovery].append(fleet)

            explicit_trip_count = 0
            for route, phase in zip(routes, selected.phase_vector):
                departures = clockface_times(phase, headway, start, end)
                for ordinal, departure in enumerate(departures):
                    explicit_trip_count += 1
                    total_trips += 1
                    twriter.writerow({
                        "stage_d_input_id": input_id,
                        "scenario_id": row["scenario_id"],
                        "route_id": route.route_id,
                        "phase_offset_min": phase,
                        "trip_ordinal": ordinal,
                        "hub_departure_min": f"{departure:.6f}",
                        "public_hub_return_min": f"{departure + route.public_runtime_min:.6f}" if route.public_service_returns_to_hub else "",
                        "vehicle_hub_return_min": f"{departure + route.cycle_runtime_min:.6f}",
                        "vehicle_block_recovery5": block_assignments[5][(route.route_id, ordinal)],
                        "vehicle_block_recovery10": block_assignments[10][(route.route_id, ordinal)],
                        "vehicle_block_recovery15": block_assignments[15][(route.route_id, ordinal)],
                    })

            contexts = json.loads(row["represented_plan_context_ids_json"])
            if len(contexts) != int(row["represented_plan_count"]):
                raise ValueError(f"represented-plan mismatch for {input_id}")
            overlap = represented_contexts.intersection(contexts)
            if overlap:
                raise ValueError(f"decision context repeated across timing inputs: {sorted(overlap)[:2]}")
            represented_contexts.update(contexts)
            stress = bus_to_rail_miss_share_by_stress(routes, selected.phase_vector, headway=headway, span_start=start, span_end=end, rail_index=rail_index, profiles=profiles)
            swriter.writerow({
                "stage_d_input_id": input_id,
                "scenario_id": row["scenario_id"],
                "topology_family": row["topology_family"],
                "uniform_headway_min": headway,
                "span_id": row["span_id"],
                "span_start_min": start,
                "span_end_min": end,
                "public_route_count": len(routes),
                "public_route_ids_json": json.dumps(route_ids, separators=(",", ":")),
                "selected_phase_vector_json": json.dumps(selected.phase_vector, separators=(",", ":")),
                "phase_vectors_evaluated": count,
                "oracle_phase_vectors_evaluated": oracle_count,
                "robust_min_transfer_quality": f"{selected.robust_min_transfer_quality:.15g}",
                "robust_unweighted_mean_transfer_quality": f"{selected.robust_unweighted_mean_transfer_quality:.15g}",
                "explicit_public_trip_count": explicit_trip_count,
                "exact_fleet_recovery5": fleet_by_recovery[5],
                "exact_fleet_recovery10": fleet_by_recovery[10],
                "exact_fleet_recovery15": fleet_by_recovery[15],
                "bus_to_rail_miss_share_by_runtime_stress_json": json.dumps(stress, sort_keys=True, separators=(",", ":")),
                "represented_plan_count": row["represented_plan_count"],
                "represented_plan_context_ids_json": row["represented_plan_context_ids_json"],
                "represented_budget_suffixes_json": row["represented_budget_suffixes_json"],
                "represented_calendar_ids_json": row["represented_calendar_ids_json"],
                "retained_current_localizable_cluster_count": row["retained_current_localizable_cluster_count"],
                "retained_current_localizable_cluster_share": row["retained_current_localizable_cluster_share"],
                "retained_current_localizable_directed_adjacent_pair_count": row["retained_current_localizable_directed_adjacent_pair_count"],
                "retained_current_localizable_directed_adjacent_pair_share": row["retained_current_localizable_directed_adjacent_pair_share"],
                "historical_station_cluster_EX_011_retained": row["historical_station_cluster_EX_011_retained"],
                "phase_selected": "true", "exact_timetable_constructed": "true", "recovery_selected": "false",
                "decision_budget_selected": "false", "primary_selected": "false", "runner_up_selected": "false", "weighted_composite_score": "false",
            })
    finally:
        close_writer(sraw, stext)
        close_writer(traw, ttext)

    if len(represented_contexts) != 16883:
        raise ValueError(f"lossless Stage-C fanout changed: {len(represented_contexts)}")
    expected_total_vectors = sum(int(row["naive_joint_phase_vector_count"]) for row in timing_rows)
    if total_vectors != expected_total_vectors:
        raise AssertionError("not all declared phase vectors were evaluated")

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "stage_d_daily_timing_input_count": len(timing_rows),
        "represented_stage_c_plan_context_count": len(represented_contexts),
        "one_route_problem_count": one_route,
        "two_route_problem_count": two_route,
        "maximum_joint_phase_vector_count": max(int(r["naive_joint_phase_vector_count"]) for r in timing_rows),
        "total_joint_phase_vectors_evaluated": total_vectors,
        "exact_route_phase_cache_key_count": len(route_phase_cache),
        "route_phase_cache_is_memoization_not_pruning": True,
        "oracle_equivalence_checked_problem_count": len(timing_rows),
        "oracle_equivalence_complete": True,
        "all_integer_phase_vectors_evaluated": True,
        "phase_pruning_used": False,
        "cross_scenario_equivalence_used": False,
        "route_specific_phase_offsets_allowed": True,
        "phase_objective": ["MAX_ROBUST_MIN_TRANSFER_QUALITY", "MAX_UNWEIGHTED_MEAN_TRANSFER_QUALITY", "LOWEST_PHASE_VECTOR_LEXICOGRAPHIC"],
        "explicit_timetable_trip_count": total_trips,
        "s8_event_count": len(rail_events),
        "s8_direction_counts": {d: sum(1 for e in rail_events if e["direction"] == d) for d in ("MILANO", "LECCO")},
        "transfer_profile_count": len(profiles),
        "runtime_stress_minutes_reported_not_selected": [0, 5, 10, 15],
        "runtime_stress_semantics": "ENGINEERING_STRESS_ONLY_NOT_EMPIRICAL_DELAY_PROBABILITY_AND_NOT_PHASE_OBJECTIVE",
        "recovery_values_evaluated_not_selected": list(RECOVERIES),
        "fleet_range_by_recovery": {str(r): [min(fleet_ranges[r]), max(fleet_ranges[r])] for r in RECOVERIES},
        "selected_robust_min_transfer_quality_range": [min(selected_quality_min), max(selected_quality_min)],
        "phase_selected": True,
        "exact_timetable_constructed": True,
        "joint_vehicle_blocks_evaluated": True,
        "recovery_selected": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "candidate_eliminated": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "passenger_demand_weights_applied_to_phase": False,
        "worker_reference_assigned_to_routes": False,
        "municipal_od_downscaled": False,
        "ridership_forecast": False,
        "weighted_composite_score": False,
        "continuity_used_in_phase_objective": False,
        "continuity_retained_for_final_lexicographic_tiebreak": True,
        "lineage": {
            "stage_d_input_validation_sha256": sha256_path(args.input_validation),
            "stage_d_timing_input_sha256": sha256_path(args.timing_input),
            "stage_d_route_input_sha256": sha256_path(args.route_input),
            "s8_events_sha256": sha256_path(args.s8_events),
            "s8_sensitivity_sha256": sha256_path(args.s8_sensitivity),
            "summary_output_sha256": sha256_path(args.summary_output),
            "trips_output_sha256": sha256_path(args.trips_output),
            "upstream_stage_d_input_contract": input_val["contract"],
        },
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": STATUS,
        "problems": len(timing_rows),
        "phase_vectors": total_vectors,
        "trips": total_trips,
        "oracle_checked": len(timing_rows),
        "fleet_ranges": validation["fleet_range_by_recovery"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
