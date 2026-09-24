#!/usr/bin/env python3
"""Run the certified Stage-E V2 engine on the repaired RT-001 Stage-D V3 lineage.

This is an interface adapter, not a new robustness model.  The underlying
planned-connection and vehicle-block mathematics remain in
``phase2_build_final_operational_robustness_v2`` unchanged.

The repaired Stage D can select more than one exact phase vector for one daily
``stage_d_input_id`` because budget/calendar contexts have different hard caps.
Therefore the robustness unit here is ``selected_timetable_id``.  The original
daily input identity and all plan-context membership are preserved in a separate
lossless mapping artifact.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Iterable, Mapping

import scripts.phase2_build_final_operational_robustness_v2 as engine

STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3"
CONTRACT = "PHASE2_PLANNED_CONNECTION_PRESERVING_OPERATIONAL_ROBUSTNESS_RT001_V3"
STAGE_D_STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"
CROSS_AUDIT_STATUS = "PASS_PHASE2_STAGE_D_V3_CROSS_IMPLEMENTATION_EQUIVALENCE"
RUNTIME_PROVENANCE_STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2"
LOSSLESS_ROLE = engine.LOSSLESS_ROLE

FINAL_FILES = {
    "final_operational_connection_audit_v2.csv.gz": "final_operational_connection_audit_rt001_v3.csv.gz",
    "final_operational_robustness_surface_v2.csv.gz": "final_operational_robustness_surface_rt001_v3.csv.gz",
    "final_operational_block_sensitivity_v2.csv.gz": "final_operational_block_sensitivity_rt001_v3.csv.gz",
    "final_operational_robustness_summary_v2.csv.gz": "final_operational_robustness_summary_rt001_v3.csv.gz",
}


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_gzip_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def deterministic_gzip_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)


def parse_vehicle_id(value: object, *, field: str) -> int:
    text = str(value).strip()
    if not text:
        raise ValueError(f"blank vehicle assignment {field}")
    match = re.fullmatch(r"(?:V|VEHICLE_?)(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    raise ValueError(f"unsupported exact vehicle assignment {field}={text!r}")


def validate_source_contracts(args) -> tuple[dict, dict, dict, dict]:
    stage_d = read_json(args.stage_d_validation)
    cross = read_json(args.cross_audit_validation)
    runtime = read_json(args.runtime_sensitivity_provenance)
    config = read_json(args.stage_e_sensitivity)

    if stage_d.get("status") != STAGE_D_STATUS:
        raise ValueError("Stage-D RT001 V3 is not certified PASS")
    if stage_d.get("exact_budget_hard_cap_reapplied_after_materialisation") is not True:
        raise ValueError("Stage-D V3 did not re-apply exact hard budget")
    if int(stage_d.get("exact_budget_hard_ineligible_context_count", -1)) != 0:
        raise ValueError("Stage-D V3 contains hard-budget-ineligible contexts")
    for field in ("decision_budget_selected", "calendar_selected", "recovery_selected", "primary_selected", "runner_up_selected", "weighted_composite_score"):
        if stage_d.get(field) is not False:
            raise ValueError(f"Stage-D V3 selection boundary violated: {field}")

    lineage = stage_d.get("lineage", {})
    source_checks = (
        ("context_output_sha256", args.stage_d_contexts),
        ("timetable_output_sha256", args.stage_d_timetables),
        ("trip_output_sha256", args.stage_d_trips),
        ("route_inputs_sha256", args.route_input),
        ("s8_events_sha256", args.s8_events),
        ("s8_sensitivity_config_sha256", args.s8_sensitivity),
    )
    for key, path in source_checks:
        if lineage.get(key) != sha256_path(path):
            raise ValueError(f"Stage-D V3 source hash mismatch: {key}")

    if cross.get("status") != CROSS_AUDIT_STATUS or cross.get("equivalent") is not True:
        raise ValueError("independent Stage-D V3 cross-implementation audit is not PASS")
    for field in (
        "differing_context_count", "differing_selected_phase_context_count",
        "semantic_timetables_only_a_count", "semantic_timetables_only_b_count",
        "differing_semantic_timetable_count", "differing_semantic_trip_set_count",
    ):
        if int(cross.get(field, -1)) != 0:
            raise ValueError(f"cross-audit mismatch remains: {field}")

    if runtime.get("status") != RUNTIME_PROVENANCE_STATUS:
        raise ValueError("runtime sensitivity provenance is not the certified Stage-D V2 contract")
    bus_stress = tuple(float(v) for v in runtime.get("runtime_stress_minutes_reported_not_selected", []))
    if bus_stress != (0.0, 5.0, 10.0, 15.0):
        raise ValueError(f"unexpected certified runtime sensitivity grid: {bus_stress}")
    if runtime.get("runtime_stress_semantics") != "ENGINEERING_STRESS_ONLY_NOT_EMPIRICAL_DELAY_PROBABILITY_AND_NOT_PHASE_OBJECTIVE":
        raise ValueError("runtime sensitivity semantics changed")

    if config.get("contract") != "PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_SENSITIVITY_V2":
        raise ValueError("Stage-E sensitivity contract changed")
    if config.get("bus_runtime_delay_source") != "STAGE_D_VALIDATION_RUNTIME_STRESS_MINUTES_REPORTED_NOT_SELECTED":
        raise ValueError("Stage-E runtime sensitivity provenance contract changed")
    if config.get("recovery_source") != "STAGE_D_VALIDATION_RECOVERY_VALUES_EVALUATED_NOT_SELECTED":
        raise ValueError("Stage-E recovery provenance contract changed")
    if config.get("planned_connection_identity") != "FIX_NOMINAL_TARGET_EVENT_THEN_TEST_RETENTION_UNDER_PERTURBATION":
        raise ValueError("planned-connection identity changed")
    if config.get("next_alternative_connection_semantics") != "REPORT_SEPARATELY_NEVER_REBIND_AS_PLANNED_SUCCESS":
        raise ValueError("alternative connection semantics changed")
    if config.get("nonzero_rail_delay_sensitivity_authorized") is not False:
        raise ValueError("non-zero rail delay unexpectedly authorised")
    if [float(v) for v in config.get("rail_arrival_delay_minutes", [])] != [0.0]:
        raise ValueError("rail delay must remain nominal-only")
    return stage_d, cross, runtime, config


def load_route_semantics(path: Path) -> dict[str, bool]:
    semantics: dict[str, bool] = {}
    for row in read_csv(path):
        rid = str(row["route_id"])
        if not rid or rid in semantics:
            raise ValueError("blank or duplicate route_id")
        semantics[rid] = engine.strict_bool(row["bus_to_rail_passenger_event_supported"])
    if not semantics:
        raise ValueError("empty route semantics")
    return semantics


def materialise_compatibility_inputs(args, temp: Path, stage_d: Mapping[str, object]) -> tuple[Path, Path, dict[str, dict[str, str]], int]:
    timetable_rows = read_csv(args.stage_d_timetables)
    context_rows = read_gzip_csv(args.stage_d_contexts)
    trip_rows = read_gzip_csv(args.stage_d_trips)
    semantics = load_route_semantics(args.route_input)

    tables: dict[str, dict[str, str]] = {}
    for row in timetable_rows:
        tid = str(row.get("selected_timetable_id", ""))
        if not tid or tid in tables:
            raise ValueError("blank or duplicate selected_timetable_id")
        tables[tid] = row
    if len(tables) != int(stage_d.get("unique_selected_exact_timetable_count", stage_d.get("selected_timetable_count", -1))):
        raise ValueError("selected exact timetable count disagrees with Stage-D validation")

    context_by_tid: dict[str, list[dict[str, str]]] = {tid: [] for tid in tables}
    seen_context: set[str] = set()
    for row in context_rows:
        cid = str(row.get("plan_context_id", ""))
        tid = str(row.get("selected_timetable_id", ""))
        if not cid or cid in seen_context:
            raise ValueError("blank or duplicate plan_context_id")
        if tid not in tables:
            raise ValueError(f"context references unknown selected timetable {tid!r}")
        if str(row["stage_d_input_id"]) != str(tables[tid]["stage_d_input_id"]):
            raise ValueError(f"context/timetable daily-input mismatch for {cid}")
        seen_context.add(cid)
        context_by_tid[tid].append(row)
    if len(seen_context) != int(stage_d["stage_c_plan_context_count"]):
        raise ValueError("lossless plan-context mapping count mismatch")
    if any(not rows for rows in context_by_tid.values()):
        raise ValueError("selected timetable without represented plan context")

    normalized_summary_rows: list[dict[str, object]] = []
    for tid in sorted(tables):
        row = tables[tid]
        normalized_summary_rows.append({
            "stage_d_input_id": tid,
            "scenario_id": row["scenario_id"],
            "topology_family": row["topology_family"],
            "span_start_min": row["span_start_min"],
            "span_end_min": row["span_end_min"],
            "public_route_ids_json": row["public_route_ids_json"],
            "explicit_public_trip_count": row["explicit_public_trip_count"],
            "exact_fleet_recovery5": row["exact_fleet_recovery5"],
            "exact_fleet_recovery10": row["exact_fleet_recovery10"],
            "exact_fleet_recovery15": row["exact_fleet_recovery15"],
        })
    summary_fields = list(normalized_summary_rows[0])
    summary_path = temp / "stage_e_normalized_exact_summary.csv.gz"
    deterministic_gzip_csv(summary_path, summary_fields, normalized_summary_rows)

    normalized_trip_rows: list[dict[str, object]] = []
    seen_trip: set[tuple[str, str, int]] = set()
    for row in trip_rows:
        tid = str(row.get("selected_timetable_id", ""))
        if tid not in tables:
            raise ValueError(f"trip references unknown selected timetable {tid!r}")
        rid = str(row["route_id"])
        ordinal = int(row["trip_ordinal"])
        key = (tid, rid, ordinal)
        if key in seen_trip:
            raise ValueError(f"duplicate exact trip {key}")
        seen_trip.add(key)
        if rid not in semantics:
            raise ValueError(f"unknown route semantics {rid}")
        public_return = row["public_service_end_min"] if semantics[rid] else ""
        normalized_trip_rows.append({
            "stage_d_input_id": tid,
            "scenario_id": tables[tid]["scenario_id"],
            "route_id": rid,
            "trip_ordinal": ordinal,
            "hub_departure_min": row["departure_min"],
            "public_hub_return_min": public_return,
            "vehicle_hub_return_min": row["vehicle_return_hub_min"],
            "vehicle_block_recovery5": parse_vehicle_id(row["vehicle_id_recovery5"], field="vehicle_id_recovery5"),
            "vehicle_block_recovery10": parse_vehicle_id(row["vehicle_id_recovery10"], field="vehicle_id_recovery10"),
            "vehicle_block_recovery15": parse_vehicle_id(row["vehicle_id_recovery15"], field="vehicle_id_recovery15"),
        })
    if len(normalized_trip_rows) != int(stage_d.get("selected_exact_trip_row_count", stage_d.get("explicit_public_trip_count", -1))):
        raise ValueError("exact trip count disagrees with Stage-D validation")
    trip_fields = list(normalized_trip_rows[0])
    trip_path = temp / "stage_e_normalized_exact_trips.csv.gz"
    deterministic_gzip_csv(trip_path, trip_fields, normalized_trip_rows)
    return summary_path, trip_path, tables, len(context_rows)


def rewrite_engine_outputs(temp_out: Path, final_out: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for source_name, final_name in FINAL_FILES.items():
        source = temp_out / source_name
        rows = read_gzip_csv(source)
        if not rows:
            raise ValueError(f"empty Stage-E engine output {source_name}")
        fields = list(rows[0])
        if "stage_d_input_id" not in fields:
            raise ValueError(f"legacy Stage-E output lacks exact-unit identity: {source_name}")
        new_fields = ["selected_timetable_id" if f == "stage_d_input_id" else f for f in fields]
        rewritten = []
        for row in rows:
            new_row = {}
            for field in fields:
                new_row["selected_timetable_id" if field == "stage_d_input_id" else field] = row[field]
            rewritten.append(new_row)
        destination = final_out / final_name
        deterministic_gzip_csv(destination, new_fields, rewritten)
        hashes[final_name] = sha256_path(destination)
    return hashes


def write_context_map(args, final_out: Path, valid_timetables: set[str]) -> tuple[Path, int]:
    rows = read_gzip_csv(args.stage_d_contexts)
    fields = [
        "plan_context_id", "plan_id", "selected_timetable_id", "stage_d_input_id",
        "scenario_id", "topology_family", "budget_suffix", "calendar_id",
        "annual_service_days", "budget_cap_annual_bus_km", "exact_annual_bus_km",
    ]
    out_rows = []
    seen = set()
    for row in sorted(rows, key=lambda r: str(r["plan_context_id"])):
        cid = str(row["plan_context_id"])
        tid = str(row["selected_timetable_id"])
        if cid in seen or tid not in valid_timetables:
            raise ValueError("invalid plan-context to exact-timetable mapping")
        seen.add(cid)
        out_rows.append({field: row[field] for field in fields})
    path = final_out / "stage_e_plan_context_map_rt001_v3.csv.gz"
    deterministic_gzip_csv(path, fields, out_rows)
    return path, len(out_rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage-d-validation", type=Path, required=True)
    p.add_argument("--stage-d-contexts", type=Path, required=True)
    p.add_argument("--stage-d-timetables", type=Path, required=True)
    p.add_argument("--stage-d-trips", type=Path, required=True)
    p.add_argument("--cross-audit-validation", type=Path, required=True)
    p.add_argument("--runtime-sensitivity-provenance", type=Path, required=True)
    p.add_argument("--route-input", type=Path, required=True)
    p.add_argument("--s8-events", type=Path, required=True)
    p.add_argument("--s8-sensitivity", type=Path, required=True)
    p.add_argument("--stage-e-sensitivity", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    for path in (
        args.stage_d_validation, args.stage_d_contexts, args.stage_d_timetables, args.stage_d_trips,
        args.cross_audit_validation, args.runtime_sensitivity_provenance, args.route_input,
        args.s8_events, args.s8_sensitivity, args.stage_e_sensitivity,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    stage_d, cross, runtime, config = validate_source_contracts(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stage-e-rt001-v3-") as tmp:
        root = Path(tmp)
        normalized_summary, normalized_trips, tables, context_count = materialise_compatibility_inputs(args, root, stage_d)
        engine_out = root / "engine-output"

        rail_rows = read_csv(args.s8_events)
        directions = {d: sum(str(r["direction"]).upper() == d for r in rail_rows) for d in engine.DIRECTIONS}
        recoveries = tuple(int(v) for v in stage_d["recovery_values_evaluated_not_selected"])
        bus_stress = tuple(float(v) for v in runtime["runtime_stress_minutes_reported_not_selected"])
        rail_delays = tuple(float(v) for v in config["rail_arrival_delay_minutes"])
        profile_count = len(read_json(args.s8_sensitivity)["transfer_profiles"])

        stage_d_for_engine = dict(stage_d)
        stage_d_for_engine.update({
            "s8_event_count": len(rail_rows),
            "s8_direction_counts": directions,
            "stage_d_daily_timing_input_count": len(tables),
            "explicit_timetable_trip_count": int(stage_d.get("selected_exact_trip_row_count", stage_d.get("explicit_public_trip_count"))),
            "transfer_profile_count": profile_count,
            "runtime_stress_minutes_reported_not_selected": list(bus_stress),
        })

        def validate_inputs_v3(_engine_args):
            return stage_d_for_engine, config, recoveries, bus_stress, rail_delays

        original_validate = engine.validate_inputs
        old_argv = sys.argv[:]
        engine.validate_inputs = validate_inputs_v3
        try:
            sys.argv = [
                "phase2_build_final_operational_robustness_v2.py",
                "--stage-d-validation", str(args.stage_d_validation),
                "--stage-d-summary", str(normalized_summary),
                "--stage-d-trips", str(normalized_trips),
                "--route-input", str(args.route_input),
                "--s8-events", str(args.s8_events),
                "--s8-sensitivity", str(args.s8_sensitivity),
                "--stage-e-sensitivity", str(args.stage_e_sensitivity),
                "--output-dir", str(engine_out),
                "--stage-d-lineage-role", LOSSLESS_ROLE,
            ]
            rc = engine.main()
            if rc != 0:
                raise RuntimeError(f"certified Stage-E engine exited {rc}")
        finally:
            engine.validate_inputs = original_validate
            sys.argv = old_argv

        output_hashes = rewrite_engine_outputs(engine_out, args.output_dir)
        mapping_path, observed_context_count = write_context_map(args, args.output_dir, set(tables))
        if observed_context_count != context_count or context_count != int(stage_d["stage_c_plan_context_count"]):
            raise ValueError("Stage-E context mapping is not lossless")

        base_validation = read_json(engine_out / "final_operational_robustness_v2_validation.json")
        if base_validation.get("status") != engine.STATUS:
            raise ValueError("underlying certified Stage-E engine did not PASS")
        if int(base_validation["timetable_count"]) != len(tables):
            raise ValueError("Stage-E engine did not use selected_timetable_id universe")
        if int(base_validation["exact_public_trip_count"]) != int(stage_d_for_engine["explicit_timetable_trip_count"]):
            raise ValueError("Stage-E exact trip count mismatch")

        final_validation = dict(base_validation)
        final_validation.update({
            "status": STATUS,
            "contract": CONTRACT,
            "underlying_engine_status": engine.STATUS,
            "underlying_engine_contract": engine.CONTRACT,
            "underlying_stage_e_algorithm_changed": False,
            "robustness_unit_identity": "selected_timetable_id",
            "legacy_engine_internal_identity_alias": "stage_d_input_id temporarily carries selected_timetable_id only inside adapter",
            "source_daily_timing_problem_count": int(stage_d["stage_d_daily_timing_input_count"]),
            "selected_exact_timetable_count": len(tables),
            "represented_plan_context_count": context_count,
            "plan_context_to_selected_timetable_mapping_lossless": True,
            "stage_d_cross_implementation_audit_required": True,
            "stage_d_cross_implementation_audit_pass": True,
            "runtime_sensitivity_provenance_separate_from_stage_d_v3": True,
            "runtime_sensitivity_provenance_status": runtime["status"],
            "runtime_sensitivity_semantics": runtime["runtime_stress_semantics"],
            "runtime_sensitivity_is_empirical_probability": False,
            "stage_d_fixture_is_final_selection_lineage": True,
            "stage_d_lineage_role": LOSSLESS_ROLE,
            "final_selection_authorized": False,
        })
        final_validation["lineage"] = {
            "stage_d_v3_validation_sha256": sha256_path(args.stage_d_validation),
            "stage_d_v3_contexts_sha256": sha256_path(args.stage_d_contexts),
            "stage_d_v3_timetables_sha256": sha256_path(args.stage_d_timetables),
            "stage_d_v3_trips_sha256": sha256_path(args.stage_d_trips),
            "stage_d_v3_route_input_sha256": sha256_path(args.route_input),
            "stage_d_v3_cross_audit_sha256": sha256_path(args.cross_audit_validation),
            "runtime_sensitivity_provenance_sha256": sha256_path(args.runtime_sensitivity_provenance),
            "s8_events_sha256": sha256_path(args.s8_events),
            "s8_sensitivity_sha256": sha256_path(args.s8_sensitivity),
            "stage_e_sensitivity_sha256": sha256_path(args.stage_e_sensitivity),
            "plan_context_map_sha256": sha256_path(mapping_path),
            **{name.replace(".csv.gz", "_sha256"): digest for name, digest in sorted(output_hashes.items())},
        }
        validation_path = args.output_dir / "final_operational_robustness_rt001_v3_validation.json"
        validation_path.write_text(json.dumps(final_validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": STATUS,
        "source_daily_timing_problem_count": int(stage_d["stage_d_daily_timing_input_count"]),
        "selected_exact_timetable_count": len(tables),
        "represented_plan_context_count": context_count,
        "exact_public_trip_count": final_validation["exact_public_trip_count"],
        "planned_connections": final_validation["planned_connection_count_across_profiles_and_directions"],
        "robustness_surface_rows": final_validation["robustness_surface_row_count"],
        "block_sensitivity_rows": final_validation["block_sensitivity_row_count"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
