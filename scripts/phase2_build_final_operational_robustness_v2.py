#!/usr/bin/env python3
"""Build Phase 2 Stage E Final Operational Robustness V2.

The builder consumes a certified exact Stage-D timetable and produces source-
closed operational reliability evidence. It never ranks networks or selects a
budget, calendar, recovery, PRIMARY or RUNNER-UP.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Iterable

from src.phase2_final_operational_robustness_v2 import (
    DIRECTIONS,
    BusDepartureIndex,
    ConnectionCandidate,
    ConnectionEvaluation,
    ExactTrip,
    RailEvent,
    TransferProfile,
    audit_nominal_block_assignment,
    build_bus_departure_index,
    build_rail_departure_index,
    evaluate_bus_to_rail_connection,
    evaluate_rail_to_bus_connection,
    maximum_gap,
    mean_or_none,
    median_or_none,
    optional_float,
    plan_bus_to_rail_connections,
    plan_rail_to_bus_connections,
    strict_bool,
)

STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_V2"
CONTRACT = "PHASE2_PLANNED_CONNECTION_PRESERVING_OPERATIONAL_ROBUSTNESS_V2"
FIXTURE_ROLE = "CURRENT_STAGE_D_USED_AS_ENGINE_VALIDATION_FIXTURE_NOT_FINAL_SELECTION_LINEAGE"
LOSSLESS_ROLE = "LOSSLESS_STAGE_D_FINAL_SELECTION_LINEAGE"

CONNECTION_FIELDS = [
    "stage_d_input_id", "scenario_id", "route_id", "connection_id", "connection_type", "direction",
    "profile_id", "transfer_walk_min", "source_event_id", "source_time_min", "planned_target_event_id",
    "planned_target_time_min", "nominal_transfer_slack_min", "planned_connection_exists",
    "perturbation_dimension", "sensitivity_results_json", "technical_return_used_as_passenger_service",
]

SURFACE_FIELDS = [
    "stage_d_input_id", "scenario_id", "topology_family", "profile_id", "connection_type", "direction",
    "perturbation_dimension", "perturbation_min", "source_event_count", "planned_s8_connection_count",
    "useful_s8_connection_count_nominal", "unmatched_event_count_nominal", "planned_connections_retained",
    "planned_connections_missed", "planned_connection_retention_share", "mean_transfer_slack_min_nominal",
    "median_transfer_slack_min_nominal", "minimum_transfer_slack_min_nominal", "maximum_wait_min_nominal",
    "first_useful_connection_source_min", "last_useful_connection_source_min", "first_useful_target_min",
    "last_useful_target_min", "maximum_gap_between_useful_connections_min_nominal",
    "alternative_connection_available_after_miss_count", "mean_alternative_wait_after_miss_min",
    "median_alternative_wait_after_miss_min", "maximum_alternative_wait_after_miss_min",
    "mean_additional_departure_delay_vs_planned_target_min", "first_planned_connection_lost",
    "last_planned_connection_lost", "first_lost_source_event_id", "last_lost_source_event_id",
    "maximum_gap_between_retained_connections_min", "service_gap_increase_min",
    "retained_connection_gap_fully_observable", "next_train_rebinding_used_as_success",
]

BLOCK_FIELDS = [
    "stage_d_input_id", "scenario_id", "topology_family", "recovery_min", "runtime_stress_min",
    "nominal_stage_d_fleet", "minimum_vehicle_requirement", "maximum_simultaneous_vehicle_requirement",
    "minimum_additional_vehicle_requirement", "vehicle_conflict_count_on_nominal_blocks",
    "turnaround_violation_count", "nominal_block_assignment_infeasible_under_case",
    "minimum_hub_turnaround_min", "minimum_block_slack_min", "median_block_slack_min",
    "maximum_block_slack_min", "recovery_selected", "runtime_stress_selected",
]

SUMMARY_FIELDS = [
    "stage_d_input_id", "scenario_id", "topology_family", "profile_id",
    "bus_to_rail_planned_connection_count", "rail_to_bus_planned_connection_count",
    "bus_to_rail_worst_retention_share", "rail_to_bus_worst_retention_share",
    "bidirectional_worst_retention_share", "bus_to_rail_max_service_gap_increase_min",
    "rail_to_bus_max_service_gap_increase_min", "worst_minimum_block_slack_min",
    "maximum_minimum_vehicle_requirement", "maximum_additional_vehicle_requirement",
    "maximum_vehicle_conflict_count_on_nominal_blocks", "any_block_infeasibility_under_sensitivity",
    "primary_selected", "runner_up_selected", "weighted_composite_score",
]


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    return raw, text, writer


def close_writer(raw, text) -> None:
    text.flush()
    text.close()
    raw.close()


def fmt(value: float | int | None, digits: int = 9) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(float(value)):
        raise ValueError(f"cannot format non-finite value {value}")
    return f"{float(value):.{digits}f}"


def load_profiles(path: Path) -> tuple[TransferProfile, ...]:
    payload = load_json(path)
    if payload.get("contract") != "PHASE2_S8_PHASING_SENSITIVITY_V2":
        raise ValueError("unexpected transfer sensitivity contract")
    profiles = tuple(
        TransferProfile(
            profile_id=str(row["profile_id"]),
            transfer_walk_min=float(row["transfer_walk_min"]),
            preferred_wait_min=float(row["preferred_wait_min"]),
            miss_transition_scale_min=float(row["miss_transition_scale_min"]),
            wait_decay_min=float(row["wait_decay_min"]),
        )
        for row in payload.get("transfer_profiles", [])
    )
    if not profiles or len({p.profile_id for p in profiles}) != len(profiles):
        raise ValueError("invalid transfer profile set")
    for profile in profiles:
        profile.validate()
    return profiles


def load_rail_events(path: Path) -> tuple[RailEvent, ...]:
    rows: list[RailEvent] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            event = RailEvent(
                trip_id=str(row["trip_id"]),
                direction=str(row["direction"]).upper(),
                arrival_min=float(row["arrival_min"]),
                departure_min=float(row["departure_min"]),
            )
            event.validate()
            rows.append(event)
    if len({e.trip_id for e in rows}) != len(rows):
        raise ValueError("duplicate frozen S8 trip_id")
    return tuple(rows)


def load_route_semantics(path: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rid = str(row["route_id"])
            if not rid or rid in result:
                raise ValueError("blank or duplicate route_id")
            returns = strict_bool(row["public_service_returns_to_hub"])
            closure = strict_bool(row["vehicle_closure_added"])
            b2r = strict_bool(row["bus_to_rail_passenger_event_supported"])
            r2b = strict_bool(row["rail_to_bus_passenger_event_supported"])
            if b2r != returns:
                raise ValueError(f"{rid}: BUS_TO_RAIL support conflicts with public return")
            if closure == returns:
                raise ValueError(f"{rid}: technical closure/public return semantics conflict")
            if not r2b:
                raise ValueError(f"{rid}: exact Stage-D public route lacks RAIL_TO_BUS support")
            result[rid] = {
                "public_service_returns_to_hub": returns,
                "vehicle_closure_added": closure,
                "bus_to_rail_passenger_event_supported": b2r,
                "rail_to_bus_passenger_event_supported": r2b,
            }
    if not result:
        raise ValueError("empty route semantics input")
    return result


def load_exact_trips(
    path: Path,
    *,
    recoveries: tuple[int, ...],
    route_semantics: dict[str, dict[str, object]],
) -> dict[str, list[ExactTrip]]:
    groups: dict[str, list[ExactTrip]] = defaultdict(list)
    seen: set[tuple[str, str, int]] = set()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {
            "stage_d_input_id", "scenario_id", "route_id", "trip_ordinal", "hub_departure_min",
            "public_hub_return_min", "vehicle_hub_return_min",
        } | {f"vehicle_block_recovery{r}" for r in recoveries}
        missing = required - fields
        if missing:
            raise ValueError(f"exact trip schema missing fields: {sorted(missing)}")
        for row in reader:
            rid = str(row["route_id"])
            if rid not in route_semantics:
                raise ValueError(f"exact trip references unknown route {rid}")
            public_return = optional_float(row["public_hub_return_min"], field="public_hub_return_min")
            b2r = bool(route_semantics[rid]["bus_to_rail_passenger_event_supported"])
            if (public_return is not None) != b2r:
                raise ValueError(f"{rid}: technical return leaked into passenger return semantics")
            trip = ExactTrip(
                stage_d_input_id=str(row["stage_d_input_id"]),
                scenario_id=str(row["scenario_id"]),
                route_id=rid,
                trip_ordinal=int(row["trip_ordinal"]),
                hub_departure_min=float(row["hub_departure_min"]),
                public_hub_return_min=public_return,
                vehicle_hub_return_min=float(row["vehicle_hub_return_min"]),
                block_by_recovery={r: int(row[f"vehicle_block_recovery{r}"]) for r in recoveries},
            )
            trip.validate()
            key = (trip.stage_d_input_id, rid, trip.trip_ordinal)
            if key in seen:
                raise ValueError(f"duplicate exact trip {key}")
            seen.add(key)
            groups[trip.stage_d_input_id].append(trip)
    for rows in groups.values():
        rows.sort(key=lambda t: (t.hub_departure_min, t.route_id, t.trip_ordinal))
    return dict(groups)


def load_stage_d_summary(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sid = str(row["stage_d_input_id"])
            if not sid or sid in result:
                raise ValueError("blank or duplicate stage_d_input_id in exact summary")
            result[sid] = row
    if not result:
        raise ValueError("empty exact Stage-D summary")
    return result


def validate_inputs(args) -> tuple[dict, dict, tuple[int, ...], tuple[float, ...], tuple[float, ...]]:
    stage_d = load_json(args.stage_d_validation)
    if stage_d.get("status") != "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2":
        raise ValueError("exact Stage-D input is not certified PASS")
    if stage_d.get("contract") != "PHASE2_EXHAUSTIVE_EXACT_TIMETABLE_S8_AND_VEHICLE_BLOCKS_V2":
        raise ValueError("unexpected exact Stage-D contract")
    if stage_d.get("exact_timetable_constructed") is not True or stage_d.get("joint_vehicle_blocks_evaluated") is not True:
        raise ValueError("Stage-D exact timetable/block evidence incomplete")
    for field in ("decision_budget_selected", "calendar_selected", "recovery_selected", "primary_selected", "runner_up_selected", "weighted_composite_score"):
        if stage_d.get(field) is not False:
            raise ValueError(f"Stage-D fixture violates non-selection boundary: {field}")
    lineage = stage_d.get("lineage", {})
    checks = (
        ("summary_output_sha256", args.stage_d_summary),
        ("trips_output_sha256", args.stage_d_trips),
        ("stage_d_route_input_sha256", args.route_input),
        ("s8_events_sha256", args.s8_events),
        ("s8_sensitivity_sha256", args.s8_sensitivity),
    )
    for key, path in checks:
        if lineage.get(key) != sha256_path(path):
            raise ValueError(f"Stage-D lineage hash mismatch: {key}")

    config = load_json(args.stage_e_sensitivity)
    if config.get("contract") != "PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_SENSITIVITY_V2":
        raise ValueError("unexpected Stage-E sensitivity contract")
    if config.get("bus_runtime_delay_source") != "STAGE_D_VALIDATION_RUNTIME_STRESS_MINUTES_REPORTED_NOT_SELECTED":
        raise ValueError("Stage-E bus runtime sensitivity source changed")
    if config.get("recovery_source") != "STAGE_D_VALIDATION_RECOVERY_VALUES_EVALUATED_NOT_SELECTED":
        raise ValueError("Stage-E recovery sensitivity source changed")
    if config.get("planned_connection_identity") != "FIX_NOMINAL_TARGET_EVENT_THEN_TEST_RETENTION_UNDER_PERTURBATION":
        raise ValueError("planned-connection identity contract changed")
    if config.get("next_alternative_connection_semantics") != "REPORT_SEPARATELY_NEVER_REBIND_AS_PLANNED_SUCCESS":
        raise ValueError("alternative-connection semantics changed")
    rail_delays = tuple(float(v) for v in config.get("rail_arrival_delay_minutes", []))
    if not rail_delays:
        raise ValueError("rail sensitivity must explicitly contain at least the nominal zero case")
    if config.get("nonzero_rail_delay_sensitivity_authorized") is False and any(abs(v) > 1e-12 for v in rail_delays):
        raise ValueError("non-zero rail delay supplied without certified authorization")
    if any(v < 0 or not math.isfinite(v) for v in rail_delays):
        raise ValueError("rail delays must be finite and non-negative")

    recoveries = tuple(int(v) for v in stage_d.get("recovery_values_evaluated_not_selected", []))
    bus_stress = tuple(float(v) for v in stage_d.get("runtime_stress_minutes_reported_not_selected", []))
    if not recoveries or not bus_stress:
        raise ValueError("Stage-D did not expose recovery/runtime sensitivity values")
    if any(v < 0 for v in recoveries) or any(v < 0 or not math.isfinite(v) for v in bus_stress):
        raise ValueError("invalid certified recovery/runtime sensitivity values")
    return stage_d, config, recoveries, bus_stress, rail_delays


def evaluation_payload(e: ConnectionEvaluation) -> dict[str, object]:
    return {
        "planned_connection_exists": e.planned_connection_exists,
        "planned_connection_retained": e.planned_connection_retained,
        "perturbed_ready_min": round(e.perturbed_ready_min, 9),
        "next_alternative_event_id": e.next_alternative_event_id,
        "next_alternative_time_min": None if e.next_alternative_time_min is None else round(e.next_alternative_time_min, 9),
        "next_alternative_wait_min": None if e.next_alternative_wait_min is None else round(e.next_alternative_wait_min, 9),
        "additional_wait_vs_planned_target_min": None if e.additional_wait_vs_planned_target_min is None else round(e.additional_wait_vs_planned_target_min, 9),
    }


def build_surface_row(
    *,
    summary: dict[str, str],
    candidates: list[ConnectionCandidate],
    evaluations: list[ConnectionEvaluation],
    perturbation_dimension: str,
    perturbation_min: float,
) -> dict[str, object]:
    if len(candidates) != len(evaluations):
        raise ValueError("candidate/evaluation length mismatch")
    planned_pairs = [(c, e) for c, e in zip(candidates, evaluations) if c.planned_connection_exists]
    planned = [c for c, _ in planned_pairs]
    retained = [c for c, e in planned_pairs if e.planned_connection_retained is True]
    missed_pairs = [(c, e) for c, e in planned_pairs if e.planned_connection_retained is False]
    missed = [c for c, _ in missed_pairs]
    alt_waits = [e.next_alternative_wait_min for _, e in missed_pairs if e.next_alternative_wait_min is not None]
    additional = [e.additional_wait_vs_planned_target_min for _, e in missed_pairs if e.additional_wait_vs_planned_target_min is not None]
    slacks = [c.nominal_slack_min for c in planned if c.nominal_slack_min is not None]
    planned_sorted = sorted(planned, key=lambda c: (c.source_time_min, c.source_event_id, c.route_id))
    missed_ids = {c.connection_id for c in missed}
    nominal_gap = maximum_gap(c.source_time_min for c in planned)
    retained_gap = maximum_gap(c.source_time_min for c in retained)
    gap_observable = len(retained) >= 2
    service_gap_increase = None
    if nominal_gap is not None and retained_gap is not None:
        service_gap_increase = retained_gap - nominal_gap
    first_lost = bool(planned_sorted and planned_sorted[0].connection_id in missed_ids)
    last_lost = bool(planned_sorted and planned_sorted[-1].connection_id in missed_ids)
    missed_sorted = sorted(missed, key=lambda c: (c.source_time_min, c.source_event_id, c.route_id))
    retention_share = None if not planned else len(retained) / len(planned)
    return {
        "stage_d_input_id": summary["stage_d_input_id"],
        "scenario_id": summary["scenario_id"],
        "topology_family": summary["topology_family"],
        "profile_id": candidates[0].profile_id if candidates else "",
        "connection_type": candidates[0].connection_type if candidates else "",
        "direction": candidates[0].direction if candidates else "",
        "perturbation_dimension": perturbation_dimension,
        "perturbation_min": fmt(perturbation_min),
        "source_event_count": len(candidates),
        "planned_s8_connection_count": len(planned),
        "useful_s8_connection_count_nominal": len(planned),
        "unmatched_event_count_nominal": len(candidates) - len(planned),
        "planned_connections_retained": len(retained),
        "planned_connections_missed": len(missed),
        "planned_connection_retention_share": fmt(retention_share),
        "mean_transfer_slack_min_nominal": fmt(mean_or_none(slacks)),
        "median_transfer_slack_min_nominal": fmt(median_or_none(slacks)),
        "minimum_transfer_slack_min_nominal": fmt(None if not slacks else min(slacks)),
        "maximum_wait_min_nominal": fmt(None if not slacks else max(slacks)),
        "first_useful_connection_source_min": fmt(None if not planned_sorted else planned_sorted[0].source_time_min),
        "last_useful_connection_source_min": fmt(None if not planned_sorted else planned_sorted[-1].source_time_min),
        "first_useful_target_min": fmt(None if not planned_sorted else planned_sorted[0].planned_target_time_min),
        "last_useful_target_min": fmt(None if not planned_sorted else planned_sorted[-1].planned_target_time_min),
        "maximum_gap_between_useful_connections_min_nominal": fmt(nominal_gap),
        "alternative_connection_available_after_miss_count": len(alt_waits),
        "mean_alternative_wait_after_miss_min": fmt(mean_or_none(alt_waits)),
        "median_alternative_wait_after_miss_min": fmt(median_or_none(alt_waits)),
        "maximum_alternative_wait_after_miss_min": fmt(None if not alt_waits else max(alt_waits)),
        "mean_additional_departure_delay_vs_planned_target_min": fmt(mean_or_none(additional)),
        "first_planned_connection_lost": str(first_lost).lower(),
        "last_planned_connection_lost": str(last_lost).lower(),
        "first_lost_source_event_id": "" if not missed_sorted else missed_sorted[0].source_event_id,
        "last_lost_source_event_id": "" if not missed_sorted else missed_sorted[-1].source_event_id,
        "maximum_gap_between_retained_connections_min": fmt(retained_gap),
        "service_gap_increase_min": fmt(service_gap_increase),
        "retained_connection_gap_fully_observable": str(gap_observable).lower(),
        "next_train_rebinding_used_as_success": "false",
    }


def min_or_none(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    return None if not clean else min(clean)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage-d-validation", type=Path, required=True)
    p.add_argument("--stage-d-summary", type=Path, required=True)
    p.add_argument("--stage-d-trips", type=Path, required=True)
    p.add_argument("--route-input", type=Path, required=True)
    p.add_argument("--s8-events", type=Path, required=True)
    p.add_argument("--s8-sensitivity", type=Path, required=True)
    p.add_argument("--stage-e-sensitivity", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--stage-d-lineage-role", choices=(FIXTURE_ROLE, LOSSLESS_ROLE), required=True)
    args = p.parse_args()
    for path in (
        args.stage_d_validation, args.stage_d_summary, args.stage_d_trips, args.route_input,
        args.s8_events, args.s8_sensitivity, args.stage_e_sensitivity,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    stage_d, stage_e_config, recoveries, bus_stress, rail_delays = validate_inputs(args)
    profiles = load_profiles(args.s8_sensitivity)
    rail_events = load_rail_events(args.s8_events)
    if len(rail_events) != int(stage_d["s8_event_count"]):
        raise ValueError("S8 event count differs from Stage-D validation")
    direction_counts = {d: sum(e.direction == d for e in rail_events) for d in DIRECTIONS}
    if direction_counts != {str(k): int(v) for k, v in stage_d["s8_direction_counts"].items()}:
        raise ValueError("S8 direction counts differ from Stage-D validation")
    route_semantics = load_route_semantics(args.route_input)
    trips_by_input = load_exact_trips(args.stage_d_trips, recoveries=recoveries, route_semantics=route_semantics)
    summaries = load_stage_d_summary(args.stage_d_summary)
    if len(summaries) != int(stage_d["stage_d_daily_timing_input_count"]):
        raise ValueError("exact timetable count differs from Stage-D validation")
    if set(summaries) != set(trips_by_input):
        raise ValueError("exact summary/trip timetable universe mismatch")
    exact_trip_count = sum(len(v) for v in trips_by_input.values())
    if exact_trip_count != int(stage_d["explicit_timetable_trip_count"]):
        raise ValueError("exact trip count differs from Stage-D validation")

    rail_index = build_rail_departure_index(rail_events)
    out = args.output_dir
    connection_path = out / "final_operational_connection_audit_v2.csv.gz"
    surface_path = out / "final_operational_robustness_surface_v2.csv.gz"
    block_path = out / "final_operational_block_sensitivity_v2.csv.gz"
    summary_path = out / "final_operational_robustness_summary_v2.csv.gz"
    validation_path = out / "final_operational_robustness_v2_validation.json"

    craw, ctext, cwriter = deterministic_gzip_writer(connection_path, CONNECTION_FIELDS)
    sraw, stext, swriter = deterministic_gzip_writer(surface_path, SURFACE_FIELDS)
    braw, btext, bwriter = deterministic_gzip_writer(block_path, BLOCK_FIELDS)
    qraw, qtext, qwriter = deterministic_gzip_writer(summary_path, SUMMARY_FIELDS)

    connection_candidate_rows = 0
    planned_connections = 0
    unmatched_candidates = 0
    surface_rows = 0
    block_rows = 0
    block_infeasible_cases = 0
    cases_requiring_additional_vehicle = 0
    missed_planned_by_runtime: dict[str, int] = {fmt(v): 0 for v in bus_stress}
    all_runtime_retention_monotonic = True
    technical_return_connection_count = 0
    stage_summary_rows = 0

    try:
        for stage_id in sorted(summaries):
            summary = summaries[stage_id]
            trips = trips_by_input[stage_id]
            if len(trips) != int(summary["explicit_public_trip_count"]):
                raise ValueError(f"{stage_id}: explicit trip count mismatch")
            if {t.scenario_id for t in trips} != {summary["scenario_id"]}:
                raise ValueError(f"{stage_id}: scenario identity mismatch")
            stated_routes = tuple(str(v) for v in json.loads(summary["public_route_ids_json"]))
            if set(stated_routes) != {t.route_id for t in trips}:
                raise ValueError(f"{stage_id}: public route identity mismatch")
            bus_index: BusDepartureIndex = build_bus_departure_index(trips)

            b2r = plan_bus_to_rail_connections(trips, rail_events, profiles)
            r2b = plan_rail_to_bus_connections(
                trips, rail_events, profiles,
                span_start_min=float(summary["span_start_min"]),
                span_end_min=float(summary["span_end_min"]),
            )
            candidates = b2r + r2b
            groups: dict[tuple[str, str, str], list[ConnectionCandidate]] = defaultdict(list)
            eval_cache: dict[str, dict[float, ConnectionEvaluation]] = {}

            for candidate in candidates:
                candidate.validate()
                groups[(candidate.profile_id, candidate.connection_type, candidate.direction)].append(candidate)
                connection_candidate_rows += 1
                planned_connections += int(candidate.planned_connection_exists)
                unmatched_candidates += int(not candidate.planned_connection_exists)
                if candidate.connection_type == "BUS_TO_RAIL":
                    sensitivity = {
                        delay: evaluate_bus_to_rail_connection(
                            candidate, bus_runtime_delay_min=delay, rail_index=rail_index
                        )
                        for delay in bus_stress
                    }
                    observed = [sensitivity[d].planned_connection_retained for d in sorted(bus_stress)]
                    if candidate.planned_connection_exists:
                        booleans = [1 if v is True else 0 for v in observed]
                        if any(b > a for a, b in zip(booleans, booleans[1:])):
                            all_runtime_retention_monotonic = False
                    for delay, ev in sensitivity.items():
                        if ev.planned_connection_retained is False:
                            missed_planned_by_runtime[fmt(delay)] += 1
                else:
                    sensitivity = {
                        delay: evaluate_rail_to_bus_connection(
                            candidate, rail_arrival_delay_min=delay, bus_index=bus_index
                        )
                        for delay in rail_delays
                    }
                eval_cache[candidate.connection_id] = sensitivity
                cwriter.writerow({
                    "stage_d_input_id": candidate.stage_d_input_id,
                    "scenario_id": candidate.scenario_id,
                    "route_id": candidate.route_id,
                    "connection_id": candidate.connection_id,
                    "connection_type": candidate.connection_type,
                    "direction": candidate.direction,
                    "profile_id": candidate.profile_id,
                    "transfer_walk_min": fmt(candidate.transfer_walk_min),
                    "source_event_id": candidate.source_event_id,
                    "source_time_min": fmt(candidate.source_time_min),
                    "planned_target_event_id": candidate.planned_target_event_id or "",
                    "planned_target_time_min": fmt(candidate.planned_target_time_min),
                    "nominal_transfer_slack_min": fmt(candidate.nominal_slack_min),
                    "planned_connection_exists": str(candidate.planned_connection_exists).lower(),
                    "perturbation_dimension": "BUS_RUNTIME_DELAY" if candidate.connection_type == "BUS_TO_RAIL" else "RAIL_ARRIVAL_DELAY",
                    "sensitivity_results_json": json.dumps(
                        {fmt(k): evaluation_payload(v) for k, v in sorted(sensitivity.items())},
                        sort_keys=True, separators=(",", ":"),
                    ),
                    "technical_return_used_as_passenger_service": "false",
                })

            technical_routes = {rid for rid, meta in route_semantics.items() if meta["vehicle_closure_added"]}
            technical_return_connection_count += sum(
                c.connection_type == "BUS_TO_RAIL" and c.route_id in technical_routes for c in candidates
            )

            surface_stats: dict[tuple[str, str, str, float], dict[str, object]] = {}
            for key in sorted(groups):
                profile_id, connection_type, direction = key
                group = sorted(groups[key], key=lambda c: (c.source_time_min, c.route_id, c.source_event_id))
                cases = bus_stress if connection_type == "BUS_TO_RAIL" else rail_delays
                dimension = "BUS_RUNTIME_DELAY" if connection_type == "BUS_TO_RAIL" else "RAIL_ARRIVAL_DELAY"
                for case in cases:
                    evaluations = [eval_cache[c.connection_id][case] for c in group]
                    row = build_surface_row(
                        summary=summary, candidates=group, evaluations=evaluations,
                        perturbation_dimension=dimension, perturbation_min=case,
                    )
                    swriter.writerow(row)
                    surface_rows += 1
                    surface_stats[(profile_id, connection_type, direction, case)] = row

            block_stats = []
            for recovery in recoveries:
                stated_fleet_field = f"exact_fleet_recovery{recovery}"
                if stated_fleet_field not in summary:
                    raise ValueError(f"{stage_id}: summary lacks {stated_fleet_field}")
                for stress in bus_stress:
                    stats = audit_nominal_block_assignment(
                        trips, recovery_min=recovery, runtime_stress_min=stress
                    )
                    if abs(stress) <= 1e-12:
                        if int(stats["minimum_vehicle_requirement"]) != int(summary[stated_fleet_field]):
                            raise ValueError(f"{stage_id}: nominal Stage-D fleet reproduction failed for recovery {recovery}")
                    block_infeasible_cases += int(bool(stats["nominal_block_assignment_infeasible_under_case"]))
                    cases_requiring_additional_vehicle += int(int(stats["minimum_additional_vehicle_requirement"]) > 0)
                    row = {
                        "stage_d_input_id": stage_id,
                        "scenario_id": summary["scenario_id"],
                        "topology_family": summary["topology_family"],
                        "recovery_min": recovery,
                        "runtime_stress_min": fmt(stress),
                        "nominal_stage_d_fleet": stats["nominal_stage_d_fleet"],
                        "minimum_vehicle_requirement": stats["minimum_vehicle_requirement"],
                        "maximum_simultaneous_vehicle_requirement": stats["maximum_simultaneous_vehicle_requirement"],
                        "minimum_additional_vehicle_requirement": stats["minimum_additional_vehicle_requirement"],
                        "vehicle_conflict_count_on_nominal_blocks": stats["vehicle_conflict_count_on_nominal_blocks"],
                        "turnaround_violation_count": stats["turnaround_violation_count"],
                        "nominal_block_assignment_infeasible_under_case": str(stats["nominal_block_assignment_infeasible_under_case"]).lower(),
                        "minimum_hub_turnaround_min": fmt(stats["minimum_hub_turnaround_min"]),
                        "minimum_block_slack_min": fmt(stats["minimum_block_slack_min"]),
                        "median_block_slack_min": fmt(stats["median_block_slack_min"]),
                        "maximum_block_slack_min": fmt(stats["maximum_block_slack_min"]),
                        "recovery_selected": "false",
                        "runtime_stress_selected": "false",
                    }
                    bwriter.writerow(row)
                    block_rows += 1
                    block_stats.append(row)

            for profile in profiles:
                b2r_rows = [
                    row for (pid, ctype, _direction, _case), row in surface_stats.items()
                    if pid == profile.profile_id and ctype == "BUS_TO_RAIL"
                ]
                r2b_rows = [
                    row for (pid, ctype, _direction, _case), row in surface_stats.items()
                    if pid == profile.profile_id and ctype == "RAIL_TO_BUS"
                ]

                def shares(rows):
                    return [float(r["planned_connection_retention_share"]) for r in rows if r["planned_connection_retention_share"] != ""]

                b2r_values = shares(b2r_rows)
                r2b_values = shares(r2b_rows)
                b2r_share = min(b2r_values) if b2r_values else None
                r2b_share = min(r2b_values) if r2b_values else None
                bidirectional = min_or_none((b2r_share, r2b_share))
                b2r_gaps = [float(r["service_gap_increase_min"]) for r in b2r_rows if r["service_gap_increase_min"] != ""]
                r2b_gaps = [float(r["service_gap_increase_min"]) for r in r2b_rows if r["service_gap_increase_min"] != ""]
                block_slacks = [float(r["minimum_block_slack_min"]) for r in block_stats if r["minimum_block_slack_min"] != ""]
                qwriter.writerow({
                    "stage_d_input_id": stage_id,
                    "scenario_id": summary["scenario_id"],
                    "topology_family": summary["topology_family"],
                    "profile_id": profile.profile_id,
                    "bus_to_rail_planned_connection_count": sum(int(r["planned_s8_connection_count"]) for r in b2r_rows if float(r["perturbation_min"]) == min(bus_stress)),
                    "rail_to_bus_planned_connection_count": sum(int(r["planned_s8_connection_count"]) for r in r2b_rows if float(r["perturbation_min"]) == min(rail_delays)),
                    "bus_to_rail_worst_retention_share": fmt(b2r_share),
                    "rail_to_bus_worst_retention_share": fmt(r2b_share),
                    "bidirectional_worst_retention_share": fmt(bidirectional),
                    "bus_to_rail_max_service_gap_increase_min": fmt(None if not b2r_gaps else max(b2r_gaps)),
                    "rail_to_bus_max_service_gap_increase_min": fmt(None if not r2b_gaps else max(r2b_gaps)),
                    "worst_minimum_block_slack_min": fmt(None if not block_slacks else min(block_slacks)),
                    "maximum_minimum_vehicle_requirement": max(int(r["minimum_vehicle_requirement"]) for r in block_stats),
                    "maximum_additional_vehicle_requirement": max(int(r["minimum_additional_vehicle_requirement"]) for r in block_stats),
                    "maximum_vehicle_conflict_count_on_nominal_blocks": max(int(r["vehicle_conflict_count_on_nominal_blocks"]) for r in block_stats),
                    "any_block_infeasibility_under_sensitivity": str(any(r["nominal_block_assignment_infeasible_under_case"] == "true" for r in block_stats)).lower(),
                    "primary_selected": "false",
                    "runner_up_selected": "false",
                    "weighted_composite_score": "false",
                })
                stage_summary_rows += 1
    finally:
        close_writer(craw, ctext)
        close_writer(sraw, stext)
        close_writer(braw, btext)
        close_writer(qraw, qtext)

    if technical_return_connection_count != 0:
        raise AssertionError("technical vehicle return created passenger BUS_TO_RAIL connection")
    if not all_runtime_retention_monotonic:
        raise AssertionError("fixed planned BUS_TO_RAIL retention improved under greater delay")

    role_is_final = args.stage_d_lineage_role == LOSSLESS_ROLE
    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "exact_timetable_input_required": True,
        "planned_connection_identity_preserved": True,
        "next_train_rebinding_used_as_success": False,
        "next_alternative_connection_reported_separately": True,
        "technical_return_used_as_passenger_service": False,
        "bus_to_rail_and_rail_to_bus_separate": True,
        "recovery_values_selected": False,
        "budget_selected": False,
        "calendar_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "passenger_weighting_applied": False,
        "municipal_od_downscaled": False,
        "ridership_forecast": False,
        "random_search": False,
        "delay_sensitivity_is_empirical_probability": False,
        "deterministic_rebuild": True,
        "stage_d_fixture_is_final_selection_lineage": role_is_final,
        "stage_d_lineage_role": args.stage_d_lineage_role,
        "stage_d_fixture_status": stage_d["status"],
        "stage_d_fixture_contract": stage_d["contract"],
        "timetable_count": len(summaries),
        "exact_public_trip_count": exact_trip_count,
        "connection_candidate_row_count": connection_candidate_rows,
        "planned_connection_count_across_profiles_and_directions": planned_connections,
        "unmatched_connection_candidate_count": unmatched_candidates,
        "robustness_surface_row_count": surface_rows,
        "block_sensitivity_row_count": block_rows,
        "summary_row_count": stage_summary_rows,
        "transfer_profile_count": len(profiles),
        "transfer_profile_ids": [p.profile_id for p in profiles],
        "bus_runtime_delay_minutes": list(bus_stress),
        "bus_runtime_delay_semantics": "DETERMINISTIC_ENGINEERING_SENSITIVITY_NOT_EMPIRICAL_PROBABILITY",
        "rail_arrival_delay_minutes": list(rail_delays),
        "nonzero_rail_delay_sensitivity_authorized": bool(stage_e_config["nonzero_rail_delay_sensitivity_authorized"]),
        "rail_delay_semantics": stage_e_config["rail_delay_semantics"],
        "recovery_minutes": list(recoveries),
        "block_sensitivity_semantics": "ADD_RUNTIME_STRESS_TO_EXACT_VEHICLE_RETURN_THEN_TEST_NOMINAL_BLOCKS_AND_RECOMPUTE_MINIMUM_FLEET",
        "fixed_target_runtime_retention_monotonic_sanity": all_runtime_retention_monotonic,
        "technical_return_connection_count": technical_return_connection_count,
        "nominal_block_assignment_infeasible_case_count": block_infeasible_cases,
        "cases_requiring_additional_vehicle_count": cases_requiring_additional_vehicle,
        "planned_bus_to_rail_misses_by_runtime_delay": missed_planned_by_runtime,
        "rt003_status": "FORMALISED_LIMITATION_CURRENT_BASELINE_IS_CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY",
        "rt004_status": "GOVERNANCE_STATUS_REFRESHED_ON_STAGE_E_BRANCH_AGENT_PROTOCOL_NOT_HISTORICALLY_PRESENT",
        "final_selection_authorized": False,
        "limitations": [
            "Current Stage-D input is a development/regression fixture unless stage_d_fixture_is_final_selection_lineage=true.",
            "No certified non-zero rail-delay sensitivity was found in the current lineage; current RAIL_TO_BUS perturbation therefore remains nominal rail arrival only.",
            "Runtime and recovery cases are deterministic engineering sensitivities, not observed probability distributions.",
            "Current-service non-regression remains a comparison to a certified localizable lower bound, not proof of non-regression against complete real current service.",
            "Stage E produces reliability evidence only and does not rank or select networks."
        ],
        "lineage": {
            "stage_d_validation_sha256": sha256_path(args.stage_d_validation),
            "stage_d_summary_sha256": sha256_path(args.stage_d_summary),
            "stage_d_trips_sha256": sha256_path(args.stage_d_trips),
            "stage_d_route_input_sha256": sha256_path(args.route_input),
            "s8_events_sha256": sha256_path(args.s8_events),
            "s8_sensitivity_sha256": sha256_path(args.s8_sensitivity),
            "stage_e_sensitivity_sha256": sha256_path(args.stage_e_sensitivity),
            "connection_audit_sha256": sha256_path(connection_path),
            "robustness_surface_sha256": sha256_path(surface_path),
            "block_sensitivity_sha256": sha256_path(block_path),
            "summary_sha256": sha256_path(summary_path)
        }
    }
    out.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": validation["status"],
        "timetable_count": validation["timetable_count"],
        "planned_connections": validation["planned_connection_count_across_profiles_and_directions"],
        "surface_rows": validation["robustness_surface_row_count"],
        "block_rows": validation["block_sensitivity_row_count"],
        "block_infeasible_cases": validation["nominal_block_assignment_infeasible_case_count"],
        "additional_vehicle_cases": validation["cases_requiring_additional_vehicle_count"]
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
