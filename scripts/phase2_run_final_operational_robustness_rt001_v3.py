#!/usr/bin/env python3
"""Run certified Stage-E robustness on the lossless RT-001 Stage-D V3 schema.

This is an adapter-only runner. It preserves the Stage-E V2 robustness kernel
and builder algorithm byte-for-byte, while translating the Stage-D V3
``selected_timetable_id`` schema into the engine's internal timetable identity.
Final outputs preserve both ``selected_timetable_id`` and the parent
``stage_d_input_id``. No decision budget, calendar, recovery, PRIMARY or
RUNNER-UP is selected here.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import sys
from typing import Iterable

import scripts.phase2_build_final_operational_robustness_v2 as engine
from src.phase2_stage_e_stage_d_interface_v3 import validate_exact_interface

STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3"
CONTRACT = "PHASE2_PLANNED_CONNECTION_PRESERVING_OPERATIONAL_ROBUSTNESS_RT001_V3"
STAGE_D_STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"
STAGE_D_CONTRACT = "PHASE2_BUDGET_LOSSLESS_EXHAUSTIVE_EXACT_CLOCKFACE_TIMETABLE_RT001_V3"
SENSITIVITY_CONTRACT = "PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_SENSITIVITY_RT001_V3"
ENGINE_BUILDER_GIT_BLOB_SHA = "d6829e80d1bea5b8628f9c9d002be80998581781"
ENGINE_KERNEL_GIT_BLOB_SHA = "f9f191a646047c956ef61101abc227ef62da8249"
VEHICLE_ID_RE = re.compile(r"^V([1-9][0-9]*)$")

FINAL_FILES = {
    "connection": "final_operational_connection_audit_rt001_v3.csv.gz",
    "surface": "final_operational_robustness_surface_rt001_v3.csv.gz",
    "block": "final_operational_block_sensitivity_rt001_v3.csv.gz",
    "summary": "final_operational_robustness_summary_rt001_v3.csv.gz",
}
TEMP_FILES = {
    "connection": "final_operational_connection_audit_v2.csv.gz",
    "surface": "final_operational_robustness_surface_v2.csv.gz",
    "block": "final_operational_block_sensitivity_v2.csv.gz",
    "summary": "final_operational_robustness_summary_v2.csv.gz",
    "validation": "final_operational_robustness_v2_validation.json",
}


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    opener = gzip.open if path.suffix == ".gz" else open
    kwargs = {"mode": "rt", "encoding": "utf-8", "newline": ""} if path.suffix == ".gz" else {"mode": "r", "encoding": "utf-8", "newline": ""}
    with opener(path, **kwargs) as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


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


def parse_vehicle_id(value: object) -> int:
    match = VEHICLE_ID_RE.fullmatch(str(value).strip())
    if match is None:
        raise ValueError(f"non-canonical Stage-D V3 vehicle id: {value!r}")
    return int(match.group(1)) - 1


def _strict_bool(value: object) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"expected true/false, got {value!r}")


def _finite(value: object, field: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"non-finite {field}: {value!r}")
    return out


def validate_stage_d_lineage(args, validation: dict) -> None:
    if validation.get("status") != STAGE_D_STATUS or validation.get("contract") != STAGE_D_CONTRACT:
        raise ValueError("Stage-D RT001 V3 input is not the certified lossless contract")
    if validation.get("exact_budget_hard_cap_reapplied_after_materialisation") is not True:
        raise ValueError("Stage-D exact hard budget was not reapplied after materialisation")
    if int(validation.get("exact_budget_hard_ineligible_context_count", -1)) != 0:
        raise ValueError("Stage-D contains exact-budget-ineligible contexts")
    if validation.get("technical_vehicle_closure_used_as_passenger_return") is not False:
        raise ValueError("technical vehicle closure leaked into passenger return semantics")
    for key in ("decision_budget_selected", "calendar_selected", "recovery_selected", "primary_selected", "runner_up_selected", "weighted_composite_score", "topology_ranked"):
        if validation.get(key) is not False:
            raise ValueError(f"Stage-D non-selection boundary violated: {key}")
    lineage = validation.get("lineage", {})
    checks = (
        ("context_output_sha256", args.stage_d_contexts),
        ("timetable_output_sha256", args.stage_d_timetables),
        ("trip_output_sha256", args.stage_d_trips),
        ("route_inputs_sha256", args.route_input),
        ("s8_events_sha256", args.s8_events),
        ("s8_sensitivity_config_sha256", args.s8_sensitivity),
    )
    for key, path in checks:
        if lineage.get(key) != sha256_path(path):
            raise ValueError(f"Stage-D lineage hash mismatch: {key}")


def validate_stage_e_sensitivity(path: Path) -> tuple[dict, tuple[int, ...], tuple[float, ...], tuple[float, ...]]:
    config = load_json(path)
    if config.get("contract") != SENSITIVITY_CONTRACT:
        raise ValueError("unexpected Stage-E RT001 V3 sensitivity contract")
    if config.get("planned_connection_identity") != "FIX_NOMINAL_TARGET_EVENT_THEN_TEST_RETENTION_UNDER_PERTURBATION":
        raise ValueError("planned connection identity changed")
    if config.get("next_alternative_connection_semantics") != "REPORT_SEPARATELY_NEVER_REBIND_AS_PLANNED_SUCCESS":
        raise ValueError("alternative connection semantics changed")
    if config.get("bus_runtime_delay_source") != "CARRIED_FORWARD_FROM_CERTIFIED_STAGE_D_V2_ENGINEERING_SENSITIVITY_GRID_NOT_EMPIRICAL_PROBABILITY":
        raise ValueError("bus runtime engineering-sensitivity provenance changed")
    bus_stress = tuple(float(v) for v in config.get("bus_runtime_delay_minutes", []))
    if bus_stress != (0.0, 5.0, 10.0, 15.0):
        raise ValueError("authorised bus runtime sensitivity grid changed")
    rail_delays = tuple(float(v) for v in config.get("rail_arrival_delay_minutes", []))
    if rail_delays != (0.0,) or config.get("nonzero_rail_delay_sensitivity_authorized") is not False:
        raise ValueError("non-zero rail delay is not authorised")
    if config.get("technical_vehicle_return_is_passenger_service") is not False:
        raise ValueError("technical vehicle return passenger semantics changed")
    for key in ("passenger_weighting", "budget_selected", "calendar_selected", "recovery_selected", "primary_selected", "runner_up_selected", "weighted_composite_score"):
        if config.get(key) is not False:
            raise ValueError(f"Stage-E sensitivity contract violates non-selection boundary: {key}")
    return config, (), bus_stress, rail_delays


def prepare_engine_inputs(
    *,
    validation: dict,
    timetable_rows: list[dict[str, str]],
    trip_rows: list[dict[str, str]],
    route_semantics: dict[str, dict[str, object]],
) -> tuple[dict[str, dict[str, str]], dict[str, list[engine.ExactTrip]], dict[str, str], tuple[int, ...]]:
    recoveries = tuple(int(v) for v in validation.get("recovery_values_evaluated_not_selected", []))
    if recoveries != (5, 10, 15):
        raise ValueError("Stage-D V3 recovery grid changed")
    summaries: dict[str, dict[str, str]] = {}
    parent_by_timetable: dict[str, str] = {}
    for row in timetable_rows:
        tid = str(row.get("selected_timetable_id", ""))
        parent = str(row.get("stage_d_input_id", ""))
        if not tid or not parent or tid in summaries:
            raise ValueError("blank or duplicate selected_timetable_id")
        adapted = dict(row)
        adapted["stage_d_input_id"] = tid
        adapted["original_stage_d_input_id"] = parent
        summaries[tid] = adapted
        parent_by_timetable[tid] = parent

    trips_by_timetable: dict[str, list[engine.ExactTrip]] = {tid: [] for tid in summaries}
    seen: set[tuple[str, str, int]] = set()
    for row in trip_rows:
        tid = str(row.get("selected_timetable_id", ""))
        if tid not in summaries:
            raise ValueError(f"trip references unknown selected timetable {tid!r}")
        if str(row.get("stage_d_input_id", "")) != parent_by_timetable[tid]:
            raise ValueError(f"{tid}: trip parent Stage-D identity mismatch")
        rid = str(row.get("route_id", ""))
        if rid not in route_semantics:
            raise ValueError(f"{tid}: trip references unknown route {rid!r}")
        ordinal = int(row["trip_ordinal"])
        key = (tid, rid, ordinal)
        if key in seen:
            raise ValueError(f"duplicate exact trip {key}")
        seen.add(key)
        departure = _finite(row["departure_min"], "departure_min")
        public_end = _finite(row["public_service_end_min"], "public_service_end_min")
        vehicle_return = _finite(row["vehicle_return_hub_min"], "vehicle_return_hub_min")
        meta = route_semantics[rid]
        public_returns = bool(meta["public_service_returns_to_hub"])
        if bool(meta["bus_to_rail_passenger_event_supported"]) != public_returns:
            raise ValueError(f"{rid}: passenger-return route semantics conflict")
        if bool(meta["vehicle_closure_added"]) == public_returns:
            raise ValueError(f"{rid}: technical closure/public return semantics conflict")
        blocks = {r: parse_vehicle_id(row[f"vehicle_id_recovery{r}"]) for r in recoveries}
        trip = engine.ExactTrip(
            stage_d_input_id=tid,
            scenario_id=str(summaries[tid]["scenario_id"]),
            route_id=rid,
            trip_ordinal=ordinal,
            hub_departure_min=departure,
            public_hub_return_min=public_end if public_returns else None,
            vehicle_hub_return_min=vehicle_return,
            block_by_recovery=blocks,
        )
        trip.validate()
        trips_by_timetable[tid].append(trip)

    for tid, trips in trips_by_timetable.items():
        if not trips:
            raise ValueError(f"selected timetable without trips: {tid}")
        summary = summaries[tid]
        route_ids = tuple(str(v) for v in json.loads(summary["public_route_ids_json"]))
        if set(route_ids) != {trip.route_id for trip in trips}:
            raise ValueError(f"{tid}: timetable route set disagrees with trip rows")
        if len(trips) != int(summary["explicit_public_trip_count"]):
            raise ValueError(f"{tid}: explicit public trip count mismatch")
        for recovery in recoveries:
            observed = {int(t.block_by_recovery[recovery]) for t in trips}
            expected_fleet = int(summary[f"exact_fleet_recovery{recovery}"])
            if observed != set(range(expected_fleet)):
                raise ValueError(f"{tid}: recovery {recovery} vehicle IDs do not reproduce exact fleet")
        trips.sort(key=lambda t: (t.hub_departure_min, t.route_id, t.trip_ordinal))
    return summaries, trips_by_timetable, parent_by_timetable, recoveries


def rewrite_with_dual_identity(src: Path, dst: Path, parent_by_timetable: dict[str, str]) -> None:
    fields, rows = read_rows(src)
    if "stage_d_input_id" not in fields:
        raise ValueError(f"engine output lacks internal timetable identity: {src}")
    final_fields = ["selected_timetable_id", "stage_d_input_id"] + [f for f in fields if f != "stage_d_input_id"]
    raw, text, writer = deterministic_gzip_writer(dst, final_fields)
    try:
        for row in rows:
            tid = str(row["stage_d_input_id"])
            if tid not in parent_by_timetable:
                raise ValueError(f"engine output references unknown selected timetable {tid}")
            out = {
                "selected_timetable_id": tid,
                "stage_d_input_id": parent_by_timetable[tid],
            }
            out.update({k: v for k, v in row.items() if k != "stage_d_input_id"})
            writer.writerow(out)
    finally:
        close_writer(raw, text)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage-d-validation", type=Path, required=True)
    p.add_argument("--stage-d-contexts", type=Path, required=True)
    p.add_argument("--stage-d-timetables", type=Path, required=True)
    p.add_argument("--stage-d-trips", type=Path, required=True)
    p.add_argument("--route-input", type=Path, required=True)
    p.add_argument("--s8-events", type=Path, required=True)
    p.add_argument("--s8-sensitivity", type=Path, required=True)
    p.add_argument("--stage-e-sensitivity", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    for path in (
        args.stage_d_validation, args.stage_d_contexts, args.stage_d_timetables, args.stage_d_trips,
        args.route_input, args.s8_events, args.s8_sensitivity, args.stage_e_sensitivity,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    stage_d = load_json(args.stage_d_validation)
    validate_stage_d_lineage(args, stage_d)
    sensitivity, _unused, bus_stress, rail_delays = validate_stage_e_sensitivity(args.stage_e_sensitivity)
    summary_fields, timetable_rows = read_rows(args.stage_d_timetables)
    trip_fields, trip_rows = read_rows(args.stage_d_trips)
    context_fields, context_rows = read_rows(args.stage_d_contexts)
    readiness = validate_exact_interface(
        stage_d, timetable_rows, trip_rows,
        summary_fields=summary_fields, trip_fields=trip_fields,
        context_rows=context_rows, context_fields=context_fields,
    )
    if readiness.get("identity_field") != "selected_timetable_id" or readiness.get("stage_e_can_consume_without_context_collapse") is not True:
        raise ValueError("Stage-D V3 interface is not lossless for Stage E")
    if int(readiness.get("represented_plan_context_count_observed", -1)) != int(stage_d["stage_c_plan_context_count"]):
        raise ValueError("Stage-D context mapping coverage changed")

    route_semantics = engine.load_route_semantics(args.route_input)
    summaries, trips_by_timetable, parent_by_timetable, recoveries = prepare_engine_inputs(
        validation=stage_d,
        timetable_rows=timetable_rows,
        trip_rows=trip_rows,
        route_semantics=route_semantics,
    )
    if len(summaries) != int(stage_d["unique_selected_exact_timetable_count"]):
        raise ValueError("selected timetable count differs from Stage-D validation")
    if sum(len(v) for v in trips_by_timetable.values()) != int(stage_d["selected_exact_trip_row_count"]):
        raise ValueError("selected exact trip count differs from Stage-D validation")

    rail_events = engine.load_rail_events(args.s8_events)
    direction_counts = {d: sum(event.direction == d for event in rail_events) for d in engine.DIRECTIONS}
    internal_stage_d = dict(stage_d)
    internal_stage_d.update({
        "exact_timetable_constructed": True,
        "joint_vehicle_blocks_evaluated": True,
        "stage_d_daily_timing_input_count": len(summaries),
        "explicit_timetable_trip_count": sum(len(v) for v in trips_by_timetable.values()),
        "s8_event_count": len(rail_events),
        "s8_direction_counts": direction_counts,
    })

    def adapter_validate_inputs(_engine_args):
        return internal_stage_d, sensitivity, recoveries, bus_stress, rail_delays

    def adapter_load_summary(_path):
        return summaries

    def adapter_load_trips(_path, *, recoveries: tuple[int, ...], route_semantics: dict[str, dict[str, object]]):
        if tuple(recoveries) != tuple(recoveries_expected):
            raise ValueError("engine recovery grid changed during adapter call")
        if set(route_semantics) != set(route_semantics_expected):
            raise ValueError("engine route-semantics universe changed during adapter call")
        return trips_by_timetable

    recoveries_expected = recoveries
    route_semantics_expected = route_semantics
    original_validate = engine.validate_inputs
    original_summary_loader = engine.load_stage_d_summary
    original_trip_loader = engine.load_exact_trips
    original_argv = list(sys.argv)

    out = args.output_dir
    temp = out / ".engine_v2_internal"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True, exist_ok=True)
    try:
        engine.validate_inputs = adapter_validate_inputs
        engine.load_stage_d_summary = adapter_load_summary
        engine.load_exact_trips = adapter_load_trips
        sys.argv = [
            "phase2_build_final_operational_robustness_v2.py",
            "--stage-d-validation", str(args.stage_d_validation),
            "--stage-d-summary", str(args.stage_d_timetables),
            "--stage-d-trips", str(args.stage_d_trips),
            "--route-input", str(args.route_input),
            "--s8-events", str(args.s8_events),
            "--s8-sensitivity", str(args.s8_sensitivity),
            "--stage-e-sensitivity", str(args.stage_e_sensitivity),
            "--output-dir", str(temp),
            "--stage-d-lineage-role", engine.LOSSLESS_ROLE,
        ]
        rc = engine.main()
        if rc != 0:
            raise RuntimeError(f"certified Stage-E engine returned {rc}")
    finally:
        engine.validate_inputs = original_validate
        engine.load_stage_d_summary = original_summary_loader
        engine.load_exact_trips = original_trip_loader
        sys.argv = original_argv

    out.mkdir(parents=True, exist_ok=True)
    final_paths: dict[str, Path] = {}
    for key in ("connection", "surface", "block", "summary"):
        dst = out / FINAL_FILES[key]
        rewrite_with_dual_identity(temp / TEMP_FILES[key], dst, parent_by_timetable)
        final_paths[key] = dst

    engine_validation = load_json(temp / TEMP_FILES["validation"])
    if engine_validation.get("technical_return_used_as_passenger_service") is not False:
        raise AssertionError("certified Stage-E engine reported technical-return passenger leakage")
    if engine_validation.get("next_train_rebinding_used_as_success") is not False:
        raise AssertionError("certified Stage-E engine rebound a missed planned connection")
    if engine_validation.get("fixed_target_runtime_retention_monotonic_sanity") is not True:
        raise AssertionError("fixed-target runtime retention monotonic sanity failed")

    validation = dict(engine_validation)
    validation.update({
        "status": STATUS,
        "contract": CONTRACT,
        "stage_e_algorithm_changed": False,
        "stage_e_adapter_only": True,
        "stage_e_certified_v2_engine_status": engine_validation.get("status"),
        "stage_e_certified_v2_engine_contract": engine_validation.get("contract"),
        "stage_e_engine_builder_git_blob_sha": ENGINE_BUILDER_GIT_BLOB_SHA,
        "stage_e_engine_kernel_git_blob_sha": ENGINE_KERNEL_GIT_BLOB_SHA,
        "stage_d_status": stage_d["status"],
        "stage_d_contract": stage_d["contract"],
        "stage_d_daily_timing_input_count": int(stage_d["stage_d_daily_timing_input_count"]),
        "selected_timetable_count": len(summaries),
        "timetable_count": len(summaries),
        "stage_c_plan_context_count": int(stage_d["stage_c_plan_context_count"]),
        "represented_plan_context_count": int(readiness["represented_plan_context_count_observed"]),
        "stage_d_inputs_with_context_dependent_exact_split": int(readiness["stage_d_inputs_with_context_dependent_exact_split"]),
        "stage_e_consumption_identity": "selected_timetable_id",
        "stage_d_parent_identity_preserved": True,
        "context_mapping_mode": readiness.get("context_mapping_mode"),
        "stage_e_can_consume_without_context_collapse": True,
        "exact_public_trip_count": sum(len(v) for v in trips_by_timetable.values()),
        "bus_runtime_delay_minutes": list(bus_stress),
        "bus_runtime_delay_source": sensitivity["bus_runtime_delay_source"],
        "bus_runtime_delay_semantics": sensitivity["bus_runtime_delay_source_semantics"],
        "rail_arrival_delay_minutes": list(rail_delays),
        "nonzero_rail_delay_sensitivity_authorized": False,
        "recovery_minutes": list(recoveries),
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "final_selection_authorized": False,
    })
    validation["limitations"] = [
        "Bus runtime 0/5/10/15-minute cases are deterministic engineering sensitivities carried forward from the certified Stage-D V2 sensitivity grid; they are not observed delay probabilities and do not enter timetable phase selection.",
        "No certified non-zero rail-delay sensitivity exists in the current lineage; RAIL_TO_BUS perturbation therefore remains nominal rail arrival only.",
        "Current-service non-regression remains a comparison to a certified localizable lower bound, not proof of non-regression against complete real current service.",
        "Stage E produces robustness evidence only and does not rank or select networks.",
    ]
    validation["lineage"] = {
        "stage_d_validation_sha256": sha256_path(args.stage_d_validation),
        "stage_d_contexts_sha256": sha256_path(args.stage_d_contexts),
        "stage_d_timetables_sha256": sha256_path(args.stage_d_timetables),
        "stage_d_trips_sha256": sha256_path(args.stage_d_trips),
        "stage_d_route_input_sha256": sha256_path(args.route_input),
        "s8_events_sha256": sha256_path(args.s8_events),
        "s8_sensitivity_sha256": sha256_path(args.s8_sensitivity),
        "stage_e_sensitivity_sha256": sha256_path(args.stage_e_sensitivity),
        "connection_audit_sha256": sha256_path(final_paths["connection"]),
        "robustness_surface_sha256": sha256_path(final_paths["surface"]),
        "block_sensitivity_sha256": sha256_path(final_paths["block"]),
        "summary_sha256": sha256_path(final_paths["summary"]),
    }
    validation_path = out / "final_operational_robustness_rt001_v3_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.rmtree(temp)
    print(json.dumps({
        "status": STATUS,
        "selected_timetables": len(summaries),
        "represented_contexts": validation["represented_plan_context_count"],
        "exact_public_trips": validation["exact_public_trip_count"],
        "planned_connections": validation["planned_connection_count_across_profiles_and_directions"],
        "surface_rows": validation["robustness_surface_row_count"],
        "block_rows": validation["block_sensitivity_row_count"],
        "technical_return_connections": validation["technical_return_connection_count"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
