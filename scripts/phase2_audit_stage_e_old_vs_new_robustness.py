#!/usr/bin/env python3
"""Independent semantic audit of legacy Stage-E V2 versus RT001 Stage-E V3.

This audit compares certified evidence only. It does not rank topologies, select
budgets/calendars/recovery values, create demand weights, infer ridership or
interpret deterministic engineering stress as an empirical probability.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

STATUS_PASS = "PASS_PHASE2_STAGE_E_OLD_VS_NEW_ROBUSTNESS_AUDIT"
STATUS_FAIL = "FAIL_PHASE2_STAGE_E_OLD_VS_NEW_ROBUSTNESS_AUDIT"
CONTRACT = "PHASE2_SEMANTIC_OLD_VS_RT001_STAGE_E_ROBUSTNESS_AUDIT_V1"
OLD_STAGE_E_STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_V2"
NEW_STAGE_E_STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3"
EXPECTED_SPLIT_INPUT_COUNT = 634
EPS = 1e-9

SURFACE_METRICS = (
    "source_event_count",
    "planned_s8_connection_count",
    "useful_s8_connection_count_nominal",
    "unmatched_event_count_nominal",
    "planned_connections_retained",
    "planned_connections_missed",
    "planned_connection_retention_share",
    "mean_transfer_slack_min_nominal",
    "median_transfer_slack_min_nominal",
    "minimum_transfer_slack_min_nominal",
    "maximum_wait_min_nominal",
    "maximum_gap_between_useful_connections_min_nominal",
    "alternative_connection_available_after_miss_count",
    "mean_alternative_wait_after_miss_min",
    "median_alternative_wait_after_miss_min",
    "maximum_alternative_wait_after_miss_min",
    "mean_additional_departure_delay_vs_planned_target_min",
    "maximum_gap_between_retained_connections_min",
    "service_gap_increase_min",
    "retained_connection_gap_fully_observable",
    "next_train_rebinding_used_as_success",
)

BLOCK_METRICS = (
    "nominal_stage_d_fleet",
    "minimum_vehicle_requirement",
    "maximum_simultaneous_vehicle_requirement",
    "minimum_additional_vehicle_requirement",
    "vehicle_conflict_count_on_nominal_blocks",
    "turnaround_violation_count",
    "nominal_block_assignment_infeasible_under_case",
    "minimum_hub_turnaround_min",
    "minimum_block_slack_min",
    "median_block_slack_min",
    "maximum_block_slack_min",
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def deterministic_gzip_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)


def stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def strict_bool(value: object) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"expected strict boolean, got {value!r}")


def optional_float(value: object) -> float | None:
    text = str(value).strip()
    return None if text == "" else float(text)


def qfloat(value: object, digits: int = 6) -> str:
    return f"{float(value):.{digits}f}"


def in_service_span(value: float, start: float, end: float) -> bool:
    return start <= value < end


def parse_vehicle_id(value: object) -> int:
    text = str(value).strip().upper()
    if text.startswith("VEHICLE_"):
        text = text[8:]
    elif text.startswith("VEHICLE"):
        text = text[7:]
    elif text.startswith("V"):
        text = text[1:]
    if not text.isdigit():
        raise ValueError(f"unsupported vehicle id {value!r}")
    return int(text)


def normalize_route_phase_key(row: Mapping[str, str]) -> tuple[str, str, int, float, float, tuple[tuple[str, int], ...]]:
    route_ids = [str(v) for v in json.loads(row["public_route_ids_json"])]
    phases = [int(v) for v in json.loads(row["selected_phase_vector_json"])]
    if len(route_ids) != len(phases) or len(set(route_ids)) != len(route_ids):
        raise ValueError("invalid route/phase semantic identity")
    pairs = tuple(sorted(zip(route_ids, phases)))
    return (
        str(row["scenario_id"]),
        str(row["topology_family"]),
        int(row["uniform_headway_min"]),
        float(row["span_start_min"]),
        float(row["span_end_min"]),
        pairs,
    )


def normalize_base_key(row: Mapping[str, str]) -> tuple[str, str, int, float, float, tuple[str, ...]]:
    route_ids = tuple(sorted(str(v) for v in json.loads(row["public_route_ids_json"])))
    return (
        str(row["scenario_id"]),
        str(row["topology_family"]),
        int(row["uniform_headway_min"]),
        float(row["span_start_min"]),
        float(row["span_end_min"]),
        route_ids,
    )


def semantic_hash(row: Mapping[str, str]) -> str:
    return sha256_text(stable_json(normalize_route_phase_key(row)))[:24]


def base_hash(row: Mapping[str, str]) -> str:
    return sha256_text(stable_json(normalize_base_key(row)))[:24]


def metric_equal(a: object, b: object) -> bool:
    sa, sb = str(a).strip(), str(b).strip()
    if sa == sb:
        return True
    if sa == "" or sb == "":
        return False
    if sa.lower() in {"true", "false"} or sb.lower() in {"true", "false"}:
        return sa.lower() == sb.lower()
    try:
        fa, fb = float(sa), float(sb)
    except ValueError:
        return False
    return math.isclose(fa, fb, rel_tol=0.0, abs_tol=EPS)


def metric_delta(a: object, b: object) -> str:
    sa, sb = str(a).strip(), str(b).strip()
    if sa == "" or sb == "":
        return ""
    try:
        return f"{float(sb) - float(sa):.9f}"
    except ValueError:
        return ""


def expect_hash(lineage: Mapping[str, object], key: str, path: Path) -> None:
    expected = str(lineage.get(key, ""))
    actual = sha256_path(path)
    if not expected or expected != actual:
        raise ValueError(f"lineage hash mismatch {key}: expected={expected!r} actual={actual}")


def load_route_semantics(path: Path) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for row in csv_rows(path):
        rid = str(row["route_id"])
        if not rid or rid in result:
            raise ValueError("blank or duplicate route id")
        result[rid] = strict_bool(row["bus_to_rail_passenger_event_supported"])
    if not result:
        raise ValueError("empty route semantics")
    return result


def load_timetable_metadata(old_summary: Path, new_timetables: Path):
    old_by_id: dict[str, dict[str, str]] = {}
    new_by_id: dict[str, dict[str, str]] = {}
    old_sem_to_ids: dict[str, list[str]] = defaultdict(list)
    new_sem_to_ids: dict[str, list[str]] = defaultdict(list)
    old_base_to_ids: dict[str, list[str]] = defaultdict(list)
    new_base_to_source_ids: dict[str, set[str]] = defaultdict(set)

    for row in csv_rows(old_summary):
        oid = str(row["stage_d_input_id"])
        if not oid or oid in old_by_id:
            raise ValueError("duplicate old timetable id")
        row = dict(row)
        row["semantic_hash"] = semantic_hash(row)
        row["base_hash"] = base_hash(row)
        old_by_id[oid] = row
        old_sem_to_ids[row["semantic_hash"]].append(oid)
        old_base_to_ids[row["base_hash"]].append(oid)

    for row in csv_rows(new_timetables):
        nid = str(row["selected_timetable_id"])
        if not nid or nid in new_by_id:
            raise ValueError("duplicate new selected_timetable_id")
        row = dict(row)
        row["semantic_hash"] = semantic_hash(row)
        row["base_hash"] = base_hash(row)
        new_by_id[nid] = row
        new_sem_to_ids[row["semantic_hash"]].append(nid)
        new_base_to_source_ids[row["base_hash"]].add(str(row["stage_d_input_id"]))

    duplicate_old_semantics = {k: v for k, v in old_sem_to_ids.items() if len(v) != 1}
    duplicate_new_semantics = {k: v for k, v in new_sem_to_ids.items() if len(v) != 1}
    if duplicate_old_semantics or duplicate_new_semantics:
        raise ValueError(
            f"semantic timetable identity is not unique old={len(duplicate_old_semantics)} new={len(duplicate_new_semantics)}"
        )
    return old_by_id, new_by_id, old_sem_to_ids, new_sem_to_ids, old_base_to_ids, new_base_to_source_ids


def load_split_contexts(path: Path):
    tids_by_source: dict[str, set[str]] = defaultdict(set)
    contexts_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen_contexts: set[str] = set()
    for row in csv_rows(path):
        cid = str(row["plan_context_id"])
        source = str(row["stage_d_input_id"])
        tid = str(row["selected_timetable_id"])
        if not cid or cid in seen_contexts or not source or not tid:
            raise ValueError("invalid V3 context mapping")
        seen_contexts.add(cid)
        tids_by_source[source].add(tid)
        contexts_by_source[source].append(dict(row))
    split = {sid for sid, tids in tids_by_source.items() if len(tids) > 1}
    return tids_by_source, contexts_by_source, split, len(seen_contexts)


def trip_digest(signatures: list[tuple]) -> str:
    payload = "\n".join(stable_json(v) for v in sorted(signatures))
    return sha256_text(payload)


def load_old_trip_evidence(path: Path, tables: Mapping[str, Mapping[str, str]], route_semantics: Mapping[str, bool]):
    signatures: dict[str, list[tuple]] = defaultdict(list)
    outspan: dict[tuple[str, str, str], dict[str, object]] = {}
    counts = Counter()
    for row in csv_rows(path):
        oid = str(row["stage_d_input_id"])
        if oid not in tables:
            raise ValueError(f"old trip references unknown timetable {oid}")
        rid = str(row["route_id"])
        if rid not in route_semantics:
            raise ValueError(f"old trip references unknown route {rid}")
        signatures[oid].append((
            rid,
            int(row["trip_ordinal"]),
            int(row["phase_offset_min"]),
            qfloat(row["hub_departure_min"]),
            qfloat(row["vehicle_hub_return_min"]),
        ))
        counts[oid] += 1
        public_return = optional_float(row["public_hub_return_min"])
        if public_return is not None:
            if not route_semantics[rid]:
                raise ValueError(f"legacy Stage-D passenger return conflicts with route semantics: {rid}")
            start = float(tables[oid]["span_start_min"])
            end = float(tables[oid]["span_end_min"])
            if not in_service_span(public_return, start, end):
                key = (oid, rid, qfloat(public_return))
                if key in outspan:
                    raise ValueError(f"duplicate legacy out-of-span return event {key}")
                outspan[key] = {
                    "lineage": "LEGACY_V2",
                    "timetable_id": oid,
                    "semantic_hash": tables[oid]["semantic_hash"],
                    "source_stage_d_input_id": oid,
                    "route_id": rid,
                    "trip_ordinal": int(row["trip_ordinal"]),
                    "return_min": qfloat(public_return),
                    "span_start_min": qfloat(start),
                    "span_end_min": qfloat(end),
                    "boundary_relation": "AT_END" if math.isclose(public_return, end, abs_tol=EPS) else ("AFTER_END" if public_return > end else "BEFORE_START"),
                    "stage_e_connection_row_count": 0,
                    "stage_e_planned_connection_row_count": 0,
                    "profile_direction_counts": Counter(),
                    "misses_by_runtime_stress": Counter(),
                }
    digest = {oid: trip_digest(rows) for oid, rows in signatures.items()}
    return digest, counts, outspan


def load_new_trip_evidence(path: Path, tables: Mapping[str, Mapping[str, str]], route_semantics: Mapping[str, bool]):
    signatures: dict[str, list[tuple]] = defaultdict(list)
    outspan: dict[tuple[str, str, str], dict[str, object]] = {}
    counts = Counter()
    for row in csv_rows(path):
        nid = str(row["selected_timetable_id"])
        if nid not in tables:
            raise ValueError(f"new trip references unknown timetable {nid}")
        rid = str(row["route_id"])
        if rid not in route_semantics:
            raise ValueError(f"new trip references unknown route {rid}")
        signatures[nid].append((
            rid,
            int(row["trip_ordinal"]),
            int(row["route_phase_min"]),
            qfloat(row["departure_min"]),
            qfloat(row["vehicle_return_hub_min"]),
        ))
        counts[nid] += 1
        if route_semantics[rid]:
            public_end = float(row["public_service_end_min"])
            start = float(tables[nid]["span_start_min"])
            end = float(tables[nid]["span_end_min"])
            if not in_service_span(public_end, start, end):
                key = (nid, rid, qfloat(public_end))
                if key in outspan:
                    raise ValueError(f"duplicate V3 physical out-of-span return event {key}")
                outspan[key] = {
                    "lineage": "RT001_V3_PHYSICAL_RETURN",
                    "timetable_id": nid,
                    "semantic_hash": tables[nid]["semantic_hash"],
                    "source_stage_d_input_id": tables[nid]["stage_d_input_id"],
                    "route_id": rid,
                    "trip_ordinal": int(row["trip_ordinal"]),
                    "return_min": qfloat(public_end),
                    "span_start_min": qfloat(start),
                    "span_end_min": qfloat(end),
                    "boundary_relation": "AT_END" if math.isclose(public_end, end, abs_tol=EPS) else ("AFTER_END" if public_end > end else "BEFORE_START"),
                    "stage_e_connection_row_count": 0,
                    "stage_e_planned_connection_row_count": 0,
                    "profile_direction_counts": Counter(),
                    "misses_by_runtime_stress": Counter(),
                }
    digest = {nid: trip_digest(rows) for nid, rows in signatures.items()}
    return digest, counts, outspan


def scan_connection_audit(
    path: Path,
    *,
    identity_field: str,
    tables: Mapping[str, Mapping[str, str]],
    raw_outspan: dict[tuple[str, str, str], dict[str, object]],
):
    technical_true = 0
    outspan_direct_leaks = 0
    outspan_direct_examples: list[dict[str, object]] = []
    profile_ids: set[str] = set()
    directions: set[str] = set()
    connection_types: set[str] = set()
    rows = 0
    for row in csv_rows(path):
        rows += 1
        identity = str(row[identity_field])
        if identity not in tables:
            raise ValueError(f"connection row references unknown timetable {identity}")
        ctype = str(row["connection_type"])
        direction = str(row["direction"])
        profile = str(row["profile_id"])
        connection_types.add(ctype)
        directions.add(direction)
        profile_ids.add(profile)
        if strict_bool(row["technical_return_used_as_passenger_service"]):
            technical_true += 1
        if ctype != "BUS_TO_RAIL":
            continue
        source_time = float(row["source_time_min"])
        start = float(tables[identity]["span_start_min"])
        end = float(tables[identity]["span_end_min"])
        if not in_service_span(source_time, start, end):
            outspan_direct_leaks += 1
            if len(outspan_direct_examples) < 20:
                outspan_direct_examples.append({
                    "timetable_id": identity,
                    "route_id": row["route_id"],
                    "source_time_min": qfloat(source_time),
                    "span_start_min": qfloat(start),
                    "span_end_min": qfloat(end),
                    "profile_id": profile,
                    "direction": direction,
                })
        key = (identity, str(row["route_id"]), qfloat(source_time))
        event = raw_outspan.get(key)
        if event is not None:
            event["stage_e_connection_row_count"] = int(event["stage_e_connection_row_count"]) + 1
            if strict_bool(row["planned_connection_exists"]):
                event["stage_e_planned_connection_row_count"] = int(event["stage_e_planned_connection_row_count"]) + 1
            event["profile_direction_counts"][(profile, direction)] += 1
            payload = json.loads(row["sensitivity_results_json"])
            if not isinstance(payload, dict):
                raise ValueError("sensitivity_results_json is not a case-keyed object")
            for stress_key, item in sorted(payload.items(), key=lambda kv: float(kv[0])):
                if not isinstance(item, dict):
                    raise ValueError("invalid sensitivity case payload")
                if bool(item.get("planned_connection_exists")) and not bool(item.get("planned_connection_retained")):
                    event["misses_by_runtime_stress"][qfloat(stress_key, 9)] += 1
    return {
        "row_count": rows,
        "technical_return_true_count": technical_true,
        "direct_out_of_span_bus_to_rail_row_count": outspan_direct_leaks,
        "direct_out_of_span_examples": outspan_direct_examples,
        "profile_ids": sorted(profile_ids),
        "directions": sorted(directions),
        "connection_types": sorted(connection_types),
    }


def surface_key(row: Mapping[str, str], identity_to_sem: Mapping[str, str], identity_field: str):
    identity = str(row[identity_field])
    if identity not in identity_to_sem:
        raise ValueError(f"surface references unknown timetable {identity}")
    return (
        identity_to_sem[identity],
        str(row["profile_id"]),
        str(row["connection_type"]),
        str(row["direction"]),
        str(row["perturbation_dimension"]),
        qfloat(row["perturbation_min"], 9),
    )


def load_surface(path: Path, identity_to_sem: Mapping[str, str], identity_field: str):
    result = {}
    stresses = defaultdict(set)
    profiles, directions, types = set(), set(), set()
    for row in csv_rows(path):
        key = surface_key(row, identity_to_sem, identity_field)
        if key in result:
            raise ValueError(f"duplicate robustness surface key {key}")
        result[key] = {field: row.get(field, "") for field in SURFACE_METRICS}
        profiles.add(key[1]); types.add(key[2]); directions.add(key[3])
        stresses[(key[2], key[4])].add(float(key[5]))
    return result, {k: sorted(v) for k, v in stresses.items()}, sorted(profiles), sorted(directions), sorted(types)


def block_key(row: Mapping[str, str], identity_to_sem: Mapping[str, str], identity_field: str):
    identity = str(row[identity_field])
    if identity not in identity_to_sem:
        raise ValueError(f"block surface references unknown timetable {identity}")
    return (
        identity_to_sem[identity],
        int(float(row["recovery_min"])),
        qfloat(row["runtime_stress_min"], 9),
    )


def load_blocks(path: Path, identity_to_sem: Mapping[str, str], identity_field: str):
    result = {}
    recoveries, stresses = set(), set()
    for row in csv_rows(path):
        key = block_key(row, identity_to_sem, identity_field)
        if key in result:
            raise ValueError(f"duplicate block key {key}")
        result[key] = {field: row.get(field, "") for field in BLOCK_METRICS}
        recoveries.add(key[1]); stresses.add(float(key[2]))
    return result, sorted(recoveries), sorted(stresses)


def compare_fields(old: Mapping[str, str] | None, new: Mapping[str, str] | None, fields: Sequence[str]) -> list[str]:
    if old is None or new is None:
        return ["ROW_PRESENCE"]
    return [field for field in fields if not metric_equal(old.get(field, ""), new.get(field, ""))]


def flatten_counter(counter: Counter) -> str:
    return stable_json({f"{k[0]}|{k[1]}": v for k, v in sorted(counter.items())}) if counter else "{}"


def span_rows(events: Mapping[tuple[str, str, str], Mapping[str, object]]):
    for key in sorted(events):
        event = events[key]
        yield {
            "lineage": event["lineage"],
            "timetable_id": event["timetable_id"],
            "semantic_hash": event["semantic_hash"],
            "source_stage_d_input_id": event["source_stage_d_input_id"],
            "route_id": event["route_id"],
            "trip_ordinal": event["trip_ordinal"],
            "return_min": event["return_min"],
            "span_start_min": event["span_start_min"],
            "span_end_min": event["span_end_min"],
            "boundary_relation": event["boundary_relation"],
            "stage_e_connection_row_count": event["stage_e_connection_row_count"],
            "stage_e_planned_connection_row_count": event["stage_e_planned_connection_row_count"],
            "profile_direction_counts_json": flatten_counter(event["profile_direction_counts"]),
            "misses_by_runtime_stress_json": stable_json(dict(sorted(event["misses_by_runtime_stress"].items()))),
        }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--old-stage-e-dir", type=Path, required=True)
    p.add_argument("--new-stage-e-dir", type=Path, required=True)
    p.add_argument("--old-stage-d-summary", type=Path, required=True)
    p.add_argument("--old-stage-d-trips", type=Path, required=True)
    p.add_argument("--old-route-input", type=Path, required=True)
    p.add_argument("--new-stage-d-validation", type=Path, required=True)
    p.add_argument("--new-stage-d-contexts", type=Path, required=True)
    p.add_argument("--new-stage-d-timetables", type=Path, required=True)
    p.add_argument("--new-stage-d-trips", type=Path, required=True)
    p.add_argument("--new-route-input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    old_e = args.old_stage_e_dir
    new_e = args.new_stage_e_dir
    old_val_path = old_e / "final_operational_robustness_v2_validation.json"
    new_val_path = new_e / "final_operational_robustness_rt001_v3_validation.json"
    old_surface_path = old_e / "final_operational_robustness_surface_v2.csv.gz"
    new_surface_path = new_e / "final_operational_robustness_surface_rt001_v3.csv.gz"
    old_block_path = old_e / "final_operational_block_sensitivity_v2.csv.gz"
    new_block_path = new_e / "final_operational_block_sensitivity_rt001_v3.csv.gz"
    old_conn_path = old_e / "final_operational_connection_audit_v2.csv.gz"
    new_conn_path = new_e / "final_operational_connection_audit_rt001_v3.csv.gz"

    required = [
        old_val_path, new_val_path, old_surface_path, new_surface_path, old_block_path, new_block_path,
        old_conn_path, new_conn_path, args.old_stage_d_summary, args.old_stage_d_trips,
        args.old_route_input, args.new_stage_d_validation, args.new_stage_d_contexts,
        args.new_stage_d_timetables, args.new_stage_d_trips, args.new_route_input,
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    old_val = read_json(old_val_path)
    new_val = read_json(new_val_path)
    new_stage_d_val = read_json(args.new_stage_d_validation)
    if old_val.get("status") != OLD_STAGE_E_STATUS:
        raise ValueError("legacy Stage E is not certified PASS")
    if new_val.get("status") != NEW_STAGE_E_STATUS:
        raise ValueError("RT001 Stage E V3 is not certified PASS")
    if new_stage_d_val.get("status") != "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3":
        raise ValueError("Stage D V3 source is not certified PASS")
    if old_val.get("stage_d_fixture_is_final_selection_lineage") is not False:
        raise ValueError("legacy Stage E fixture role changed")
    if new_val.get("stage_d_fixture_is_final_selection_lineage") is not True:
        raise ValueError("new Stage E final lineage role missing")
    if new_val.get("underlying_stage_e_algorithm_changed") is not False:
        raise ValueError("new Stage E claims a changed robustness algorithm")
    if old_val.get("delay_sensitivity_is_empirical_probability") is not False or new_val.get("delay_sensitivity_is_empirical_probability") is not False:
        raise ValueError("engineering stress was relabelled as empirical probability")
    for payload, label in ((old_val, "old"), (new_val, "new")):
        for field in (
            "budget_selected", "calendar_selected", "recovery_values_selected", "primary_selected",
            "runner_up_selected", "weighted_composite_score", "passenger_weighting_applied",
            "municipal_od_downscaled", "ridership_forecast", "random_search", "final_selection_authorized",
        ):
            if payload.get(field) is not False:
                raise ValueError(f"{label} Stage E violates non-decisional boundary: {field}")

    old_lin = old_val["lineage"]
    expect_hash(old_lin, "connection_audit_sha256", old_conn_path)
    expect_hash(old_lin, "robustness_surface_sha256", old_surface_path)
    expect_hash(old_lin, "block_sensitivity_sha256", old_block_path)
    expect_hash(old_lin, "stage_d_summary_sha256", args.old_stage_d_summary)
    expect_hash(old_lin, "stage_d_trips_sha256", args.old_stage_d_trips)
    expect_hash(old_lin, "stage_d_route_input_sha256", args.old_route_input)

    new_lin = new_val["lineage"]
    expect_hash(new_lin, "final_operational_connection_audit_rt001_v3_sha256", new_conn_path)
    expect_hash(new_lin, "final_operational_robustness_surface_rt001_v3_sha256", new_surface_path)
    expect_hash(new_lin, "final_operational_block_sensitivity_rt001_v3_sha256", new_block_path)
    expect_hash(new_lin, "stage_d_v3_contexts_sha256", args.new_stage_d_contexts)
    expect_hash(new_lin, "stage_d_v3_timetables_sha256", args.new_stage_d_timetables)
    expect_hash(new_lin, "stage_d_v3_trips_sha256", args.new_stage_d_trips)
    expect_hash(new_lin, "stage_d_v3_route_input_sha256", args.new_route_input)
    expect_hash(new_lin, "stage_d_v3_validation_sha256", args.new_stage_d_validation)

    old_routes = load_route_semantics(args.old_route_input)
    new_routes = load_route_semantics(args.new_route_input)
    old_by_id, new_by_id, old_sem_to_ids, new_sem_to_ids, old_base_to_ids, new_base_to_sources = load_timetable_metadata(
        args.old_stage_d_summary, args.new_stage_d_timetables
    )
    old_id_to_sem = {oid: row["semantic_hash"] for oid, row in old_by_id.items()}
    new_id_to_sem = {nid: row["semantic_hash"] for nid, row in new_by_id.items()}

    tids_by_source, contexts_by_source, split_sources, context_count = load_split_contexts(args.new_stage_d_contexts)
    if len(split_sources) != EXPECTED_SPLIT_INPUT_COUNT:
        raise ValueError(f"RT001 split input count changed: {len(split_sources)} != {EXPECTED_SPLIT_INPUT_COUNT}")
    if len(split_sources) != int(new_stage_d_val.get("timing_inputs_with_budget_or_calendar_specific_selected_phase_count", -1)):
        raise ValueError("computed split count disagrees with Stage-D V3 validation")
    if context_count != int(new_val.get("represented_plan_context_count", -1)):
        raise ValueError("V3 plan-context count mismatch")

    old_trip_digest, old_trip_counts, old_outspan = load_old_trip_evidence(args.old_stage_d_trips, old_by_id, old_routes)
    new_trip_digest, new_trip_counts, new_outspan = load_new_trip_evidence(args.new_stage_d_trips, new_by_id, new_routes)
    if sum(old_trip_counts.values()) != int(old_val["exact_public_trip_count"]):
        raise ValueError("legacy exact trip count mismatch")
    if sum(new_trip_counts.values()) != int(new_val["exact_public_trip_count"]):
        raise ValueError("V3 exact trip count mismatch")

    old_conn_scan = scan_connection_audit(old_conn_path, identity_field="stage_d_input_id", tables=old_by_id, raw_outspan=old_outspan)
    new_conn_scan = scan_connection_audit(new_conn_path, identity_field="selected_timetable_id", tables=new_by_id, raw_outspan=new_outspan)
    if old_conn_scan["row_count"] != int(old_val["connection_candidate_row_count"]):
        raise ValueError("legacy connection row count mismatch")
    if new_conn_scan["row_count"] != int(new_val["connection_candidate_row_count"]):
        raise ValueError("V3 connection row count mismatch")

    old_surface, old_stresses, old_profiles, old_dirs, old_types = load_surface(old_surface_path, old_id_to_sem, "stage_d_input_id")
    new_surface, new_stresses, new_profiles, new_dirs, new_types = load_surface(new_surface_path, new_id_to_sem, "selected_timetable_id")
    if old_profiles != new_profiles or old_dirs != new_dirs or old_types != new_types:
        raise ValueError("profile/direction/connection-type domains changed")
    if old_profiles != list(old_val["transfer_profile_ids"]) or new_profiles != list(new_val["transfer_profile_ids"]):
        if sorted(old_val["transfer_profile_ids"]) != old_profiles or sorted(new_val["transfer_profile_ids"]) != new_profiles:
            raise ValueError("transfer profile IDs disagree with validation")
    expected_bus_stress = [0.0, 5.0, 10.0, 15.0]
    old_bus_grid = old_stresses.get(("BUS_TO_RAIL", "BUS_RUNTIME_DELAY"), [])
    new_bus_grid = new_stresses.get(("BUS_TO_RAIL", "BUS_RUNTIME_DELAY"), [])
    if old_bus_grid != expected_bus_stress or new_bus_grid != expected_bus_stress:
        raise ValueError(f"BUS_TO_RAIL engineering stress grid changed old={old_bus_grid} new={new_bus_grid}")
    old_rail_grid = old_stresses.get(("RAIL_TO_BUS", "RAIL_ARRIVAL_DELAY"), [])
    new_rail_grid = new_stresses.get(("RAIL_TO_BUS", "RAIL_ARRIVAL_DELAY"), [])
    if old_rail_grid != [0.0] or new_rail_grid != [0.0]:
        raise ValueError("RAIL_TO_BUS evidence is not nominal-only in one lineage")

    old_blocks, old_recoveries, old_block_stresses = load_blocks(old_block_path, old_id_to_sem, "stage_d_input_id")
    new_blocks, new_recoveries, new_block_stresses = load_blocks(new_block_path, new_id_to_sem, "selected_timetable_id")
    if old_recoveries != [5, 10, 15] or new_recoveries != [5, 10, 15]:
        raise ValueError("recovery grid changed")
    if old_block_stresses != expected_bus_stress or new_block_stresses != expected_bus_stress:
        raise ValueError("block engineering-stress grid changed")

    common_sem = set(old_sem_to_ids) & set(new_sem_to_ids)
    old_only_sem = set(old_sem_to_ids) - set(new_sem_to_ids)
    new_only_sem = set(new_sem_to_ids) - set(old_sem_to_ids)

    physical_equal_by_sem: dict[str, bool] = {}
    old_id_by_sem = {sem: ids[0] for sem, ids in old_sem_to_ids.items()}
    new_id_by_sem = {sem: ids[0] for sem, ids in new_sem_to_ids.items()}
    for sem in common_sem:
        oid, nid = old_id_by_sem[sem], new_id_by_sem[sem]
        physical_equal_by_sem[sem] = (
            old_trip_counts.get(oid, 0) == new_trip_counts.get(nid, 0)
            and old_trip_digest.get(oid) == new_trip_digest.get(nid)
        )

    legacy_outspan_by_sem = Counter(event["semantic_hash"] for event in old_outspan.values())
    new_physical_outspan_by_sem = Counter(event["semantic_hash"] for event in new_outspan.values())

    surface_rows_out: list[dict[str, object]] = []
    surface_mismatch_matrix = Counter()
    surface_mismatch_by_sem = Counter()
    surface_unexplained_by_sem = Counter()
    explained_span_surface_mismatch = 0
    unexplained_surface_mismatch = 0
    rail_nominal_unexplained = 0
    surface_common_key_count = 0
    all_surface_keys = {
        key for key in set(old_surface) | set(new_surface)
        if key[0] in common_sem
    }
    for key in sorted(all_surface_keys):
        sem, profile, ctype, direction, perturb_dim, perturb_min = key
        old_row, new_row = old_surface.get(key), new_surface.get(key)
        mismatches = compare_fields(old_row, new_row, SURFACE_METRICS)
        physical_equal = physical_equal_by_sem[sem]
        span_affected = legacy_outspan_by_sem[sem] > 0
        if old_row is not None and new_row is not None:
            surface_common_key_count += 1
        if not mismatches:
            cause = "UNCHANGED_SEMANTIC_EVIDENCE"
        elif not physical_equal:
            cause = "CHANGED_TIMETABLE_TRIP_UNIVERSE"
        elif ctype == "BUS_TO_RAIL" and span_affected:
            cause = "OUT_OF_SPAN_PUBLIC_RETURN_CORRECTION"
            explained_span_surface_mismatch += 1
        else:
            cause = "UNEXPLAINED_COMPARABLE_MISMATCH"
            unexplained_surface_mismatch += 1
            surface_unexplained_by_sem[sem] += 1
            if ctype == "RAIL_TO_BUS" and math.isclose(float(perturb_min), 0.0, abs_tol=EPS):
                rail_nominal_unexplained += 1
        if mismatches:
            surface_mismatch_by_sem[sem] += 1
            surface_mismatch_matrix[(ctype, profile, direction, perturb_min, cause)] += 1
        oid, nid = old_id_by_sem[sem], new_id_by_sem[sem]
        source = str(new_by_id[nid]["stage_d_input_id"])
        surface_rows_out.append({
            "semantic_hash": sem,
            "old_stage_d_input_id": oid,
            "new_selected_timetable_id": nid,
            "new_stage_d_input_id": source,
            "new_source_is_rt001_context_split": str(source in split_sources).lower(),
            "physical_trip_universe_equal": str(physical_equal).lower(),
            "legacy_out_of_span_return_count": legacy_outspan_by_sem[sem],
            "profile_id": profile,
            "connection_type": ctype,
            "direction": direction,
            "perturbation_dimension": perturb_dim,
            "perturbation_min": perturb_min,
            "old_row_present": str(old_row is not None).lower(),
            "new_row_present": str(new_row is not None).lower(),
            "mismatch_fields_json": stable_json(mismatches),
            "difference_class": cause,
            "old_planned_connections": "" if old_row is None else old_row.get("planned_s8_connection_count", ""),
            "new_planned_connections": "" if new_row is None else new_row.get("planned_s8_connection_count", ""),
            "old_retained": "" if old_row is None else old_row.get("planned_connections_retained", ""),
            "new_retained": "" if new_row is None else new_row.get("planned_connections_retained", ""),
            "old_missed": "" if old_row is None else old_row.get("planned_connections_missed", ""),
            "new_missed": "" if new_row is None else new_row.get("planned_connections_missed", ""),
            "old_retention_share": "" if old_row is None else old_row.get("planned_connection_retention_share", ""),
            "new_retention_share": "" if new_row is None else new_row.get("planned_connection_retention_share", ""),
            "retention_share_delta_new_minus_old": "" if old_row is None or new_row is None else metric_delta(old_row.get("planned_connection_retention_share", ""), new_row.get("planned_connection_retention_share", "")),
            "old_service_gap_increase_min": "" if old_row is None else old_row.get("service_gap_increase_min", ""),
            "new_service_gap_increase_min": "" if new_row is None else new_row.get("service_gap_increase_min", ""),
            "service_gap_delta_new_minus_old_min": "" if old_row is None or new_row is None else metric_delta(old_row.get("service_gap_increase_min", ""), new_row.get("service_gap_increase_min", "")),
        })

    block_rows_out: list[dict[str, object]] = []
    block_mismatch_matrix = Counter()
    block_mismatch_by_sem = Counter()
    block_unexplained_by_sem = Counter()
    unexplained_block_mismatch = 0
    all_block_keys = {key for key in set(old_blocks) | set(new_blocks) if key[0] in common_sem}
    for key in sorted(all_block_keys):
        sem, recovery, stress = key
        old_row, new_row = old_blocks.get(key), new_blocks.get(key)
        mismatches = compare_fields(old_row, new_row, BLOCK_METRICS)
        physical_equal = physical_equal_by_sem[sem]
        if not mismatches:
            cause = "UNCHANGED_SEMANTIC_EVIDENCE"
        elif not physical_equal:
            cause = "CHANGED_TIMETABLE_TRIP_UNIVERSE"
        else:
            cause = "UNEXPLAINED_COMPARABLE_MISMATCH"
            unexplained_block_mismatch += 1
            block_unexplained_by_sem[sem] += 1
        if mismatches:
            block_mismatch_by_sem[sem] += 1
            block_mismatch_matrix[(recovery, stress, cause)] += 1
        oid, nid = old_id_by_sem[sem], new_id_by_sem[sem]
        source = str(new_by_id[nid]["stage_d_input_id"])
        block_rows_out.append({
            "semantic_hash": sem,
            "old_stage_d_input_id": oid,
            "new_selected_timetable_id": nid,
            "new_stage_d_input_id": source,
            "new_source_is_rt001_context_split": str(source in split_sources).lower(),
            "physical_trip_universe_equal": str(physical_equal).lower(),
            "recovery_min": recovery,
            "runtime_stress_min": stress,
            "old_row_present": str(old_row is not None).lower(),
            "new_row_present": str(new_row is not None).lower(),
            "mismatch_fields_json": stable_json(mismatches),
            "difference_class": cause,
            "old_nominal_stage_d_fleet": "" if old_row is None else old_row.get("nominal_stage_d_fleet", ""),
            "new_nominal_stage_d_fleet": "" if new_row is None else new_row.get("nominal_stage_d_fleet", ""),
            "old_minimum_vehicle_requirement": "" if old_row is None else old_row.get("minimum_vehicle_requirement", ""),
            "new_minimum_vehicle_requirement": "" if new_row is None else new_row.get("minimum_vehicle_requirement", ""),
            "old_additional_vehicle_requirement": "" if old_row is None else old_row.get("minimum_additional_vehicle_requirement", ""),
            "new_additional_vehicle_requirement": "" if new_row is None else new_row.get("minimum_additional_vehicle_requirement", ""),
            "old_nominal_block_infeasible": "" if old_row is None else old_row.get("nominal_block_assignment_infeasible_under_case", ""),
            "new_nominal_block_infeasible": "" if new_row is None else new_row.get("nominal_block_assignment_infeasible_under_case", ""),
            "old_vehicle_conflicts": "" if old_row is None else old_row.get("vehicle_conflict_count_on_nominal_blocks", ""),
            "new_vehicle_conflicts": "" if new_row is None else new_row.get("vehicle_conflict_count_on_nominal_blocks", ""),
        })

    split_rows_out = []
    for source in sorted(split_sources):
        rows = contexts_by_source[source]
        tids = sorted(tids_by_source[source])
        split_rows_out.append({
            "stage_d_input_id": source,
            "selected_timetable_count": len(tids),
            "selected_timetable_ids_json": stable_json(tids),
            "represented_plan_context_count": len(rows),
            "budget_suffixes_json": stable_json(sorted({str(r["budget_suffix"]) for r in rows})),
            "calendar_ids_json": stable_json(sorted({str(r["calendar_id"]) for r in rows})),
            "selected_phase_vectors_json": stable_json(sorted({str(r["selected_phase_vector_json"]) for r in rows})),
        })

    classification_rows = []
    category_counts = Counter()
    semantic_hashes = sorted(set(old_sem_to_ids) | set(new_sem_to_ids))
    for sem in semantic_hashes:
        oid = old_id_by_sem.get(sem, "")
        nid = new_id_by_sem.get(sem, "")
        if oid and nid:
            source = str(new_by_id[nid]["stage_d_input_id"])
            physical_equal = physical_equal_by_sem[sem]
            split = source in split_sources
            span = legacy_outspan_by_sem[sem] > 0
            unexplained = surface_unexplained_by_sem[sem] > 0 or block_unexplained_by_sem[sem] > 0
            if unexplained:
                category = "UNEXPLAINED_COMPARABLE_MISMATCH"
            elif not physical_equal:
                category = "CHANGED_TIMETABLE_TRIP_UNIVERSE_COMMON_SEMANTIC_KEY"
            elif surface_mismatch_by_sem[sem] and span:
                category = "OUT_OF_SPAN_PUBLIC_RETURN_CORRECTION_WITHIN_RT001_SPLIT" if split else "OUT_OF_SPAN_PUBLIC_RETURN_CORRECTION"
            elif split:
                category = "UNCHANGED_COMMON_PHASE_WITHIN_RT001_CONTEXT_SPLIT"
            else:
                category = "UNCHANGED_CASE"
            base = str(new_by_id[nid]["base_hash"])
        elif nid:
            source = str(new_by_id[nid]["stage_d_input_id"])
            base = str(new_by_id[nid]["base_hash"])
            split = source in split_sources
            old_base_present = base in old_base_to_ids
            if split:
                category = "RT001_CONTEXT_SPLIT_NEW_PHASE"
            elif old_base_present:
                category = "RT001_PHASE_RESELECTION_WITHOUT_CONTEXT_SPLIT_NEW_PHASE"
            else:
                category = "CHANGED_TIMETABLE_TRIP_UNIVERSE_NEW_ONLY"
            physical_equal = False
            span = False
        else:
            source = ""
            base = str(old_by_id[oid]["base_hash"])
            source_candidates = new_base_to_sources.get(base, set())
            split = any(s in split_sources for s in source_candidates)
            if split:
                category = "RT001_CONTEXT_SPLIT_REPLACED_LEGACY_PHASE"
            elif source_candidates:
                category = "RT001_PHASE_RESELECTION_WITHOUT_CONTEXT_SPLIT_OLD_PHASE"
            else:
                category = "CHANGED_TIMETABLE_TRIP_UNIVERSE_OLD_ONLY"
            physical_equal = False
            span = legacy_outspan_by_sem[sem] > 0
        category_counts[category] += 1
        classification_rows.append({
            "semantic_hash": sem,
            "base_hash": base,
            "old_stage_d_input_id": oid,
            "new_selected_timetable_id": nid,
            "new_stage_d_input_id": source,
            "rt001_context_split_source": str(split).lower(),
            "physical_trip_universe_equal": str(physical_equal).lower(),
            "legacy_out_of_span_return_count": legacy_outspan_by_sem[sem],
            "new_physical_out_of_span_return_count": new_physical_outspan_by_sem[sem],
            "surface_mismatch_row_count": surface_mismatch_by_sem[sem],
            "block_mismatch_row_count": block_mismatch_by_sem[sem],
            "change_class": category,
        })

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    split_path = out / "rt001_context_split_inputs.csv.gz"
    span_path = out / "span_return_rule_audit.csv.gz"
    surface_out_path = out / "semantic_robustness_surface_comparison.csv.gz"
    block_out_path = out / "semantic_block_sensitivity_comparison.csv.gz"
    class_path = out / "semantic_timetable_change_classification.csv.gz"

    deterministic_gzip_csv(split_path, list(split_rows_out[0]), split_rows_out)
    all_span_rows = list(span_rows(old_outspan)) + list(span_rows(new_outspan))
    span_fields = [
        "lineage", "timetable_id", "semantic_hash", "source_stage_d_input_id", "route_id", "trip_ordinal",
        "return_min", "span_start_min", "span_end_min", "boundary_relation", "stage_e_connection_row_count",
        "stage_e_planned_connection_row_count", "profile_direction_counts_json", "misses_by_runtime_stress_json",
    ]
    deterministic_gzip_csv(span_path, span_fields, sorted(all_span_rows, key=lambda r: (r["lineage"], r["timetable_id"], r["route_id"], float(r["return_min"]))))
    deterministic_gzip_csv(surface_out_path, list(surface_rows_out[0]), surface_rows_out)
    deterministic_gzip_csv(block_out_path, list(block_rows_out[0]), block_rows_out)
    deterministic_gzip_csv(class_path, list(classification_rows[0]), classification_rows)

    legacy_outspan_connection_rows = sum(int(e["stage_e_connection_row_count"]) for e in old_outspan.values())
    legacy_outspan_planned_rows = sum(int(e["stage_e_planned_connection_row_count"]) for e in old_outspan.values())
    new_outspan_connection_rows = sum(int(e["stage_e_connection_row_count"]) for e in new_outspan.values())
    new_outspan_planned_rows = sum(int(e["stage_e_planned_connection_row_count"]) for e in new_outspan.values())

    mismatches_examples = [
        {
            "kind": "SURFACE",
            "semantic_hash": r["semantic_hash"],
            "connection_type": r["connection_type"],
            "profile_id": r["profile_id"],
            "direction": r["direction"],
            "perturbation_min": r["perturbation_min"],
            "difference_class": r["difference_class"],
            "mismatch_fields_json": r["mismatch_fields_json"],
        }
        for r in surface_rows_out if r["mismatch_fields_json"] != "[]"
    ] + [
        {
            "kind": "BLOCK",
            "semantic_hash": r["semantic_hash"],
            "recovery_min": r["recovery_min"],
            "runtime_stress_min": r["runtime_stress_min"],
            "difference_class": r["difference_class"],
            "mismatch_fields_json": r["mismatch_fields_json"],
        }
        for r in block_rows_out if r["mismatch_fields_json"] != "[]"
    ]
    mismatches_examples = sorted(mismatches_examples, key=stable_json)[:30]

    failure_reasons = []
    if new_conn_scan["direct_out_of_span_bus_to_rail_row_count"] != 0 or new_outspan_connection_rows != 0:
        failure_reasons.append("RT001_V3_OUT_OF_SPAN_PASSENGER_RETURN_LEAK")
    if new_conn_scan["technical_return_true_count"] != 0:
        failure_reasons.append("RT001_V3_TECHNICAL_RETURN_USED_AS_PASSENGER_SERVICE")
    if old_conn_scan["technical_return_true_count"] != 0:
        failure_reasons.append("LEGACY_TECHNICAL_RETURN_FLAG_TRUE")
    if unexplained_surface_mismatch != 0:
        failure_reasons.append("UNEXPLAINED_SURFACE_MISMATCH_ON_COMPARABLE_CASE")
    if rail_nominal_unexplained != 0:
        failure_reasons.append("UNEXPLAINED_RAIL_TO_BUS_NOMINAL_MISMATCH")
    if unexplained_block_mismatch != 0:
        failure_reasons.append("UNEXPLAINED_BLOCK_MISMATCH_ON_COMPARABLE_CASE")

    validation = {
        "status": STATUS_PASS if not failure_reasons else STATUS_FAIL,
        "contract": CONTRACT,
        "pass_semantics": "PASS_MEANS_SOURCE_CLOSED_SEMANTIC_COMPARISON_COMPLETED_AND_ALL_COMPARABLE_DIFFERENCES_ARE_EXPLAINED_BY_CERTIFIED_LINEAGE_CHANGES_NOT_THAT_OLD_AND_NEW_ARE_AGGREGATE_IDENTICAL",
        "failure_reasons": failure_reasons,
        "legacy_stage_e_status": old_val["status"],
        "new_stage_e_status": new_val["status"],
        "legacy_stage_e_fixture_is_final_selection_lineage": False,
        "new_stage_e_fixture_is_final_selection_lineage": True,
        "legacy_timetable_count": len(old_by_id),
        "new_selected_timetable_count": len(new_by_id),
        "new_source_daily_timing_input_count": len(tids_by_source),
        "new_represented_plan_context_count": context_count,
        "rt001_context_split_stage_d_input_count": len(split_sources),
        "expected_rt001_context_split_stage_d_input_count": EXPECTED_SPLIT_INPUT_COUNT,
        "rt001_context_split_count_exactly_confirmed": len(split_sources) == EXPECTED_SPLIT_INPUT_COUNT,
        "semantic_timetable_common_count": len(common_sem),
        "semantic_timetable_old_only_count": len(old_only_sem),
        "semantic_timetable_new_only_count": len(new_only_sem),
        "common_semantic_timetables_with_equal_operational_trip_universe_count": sum(physical_equal_by_sem.values()),
        "common_semantic_timetables_with_changed_operational_trip_universe_count": len(common_sem) - sum(physical_equal_by_sem.values()),
        "legacy_exact_trip_count": sum(old_trip_counts.values()),
        "new_exact_trip_count": sum(new_trip_counts.values()),
        "transfer_profile_ids": old_profiles,
        "directions": old_dirs,
        "connection_types": old_types,
        "bus_runtime_engineering_stress_minutes": expected_bus_stress,
        "bus_runtime_engineering_stress_is_empirical_probability": False,
        "rail_to_bus_delay_evidence_minutes": [0.0],
        "recovery_minutes_evaluated_not_selected": [5, 10, 15],
        "surface_comparison_row_count": len(surface_rows_out),
        "surface_common_present_both_row_count": surface_common_key_count,
        "surface_mismatch_row_count": sum(1 for r in surface_rows_out if r["mismatch_fields_json"] != "[]"),
        "surface_mismatch_explained_by_out_of_span_return_correction_count": explained_span_surface_mismatch,
        "surface_unexplained_comparable_mismatch_count": unexplained_surface_mismatch,
        "rail_to_bus_nominal_unexplained_comparable_mismatch_count": rail_nominal_unexplained,
        "surface_mismatch_matrix": {
            "|".join(map(str, key)): value for key, value in sorted(surface_mismatch_matrix.items(), key=lambda kv: tuple(map(str, kv[0])))
        },
        "block_comparison_row_count": len(block_rows_out),
        "block_mismatch_row_count": sum(1 for r in block_rows_out if r["mismatch_fields_json"] != "[]"),
        "block_unexplained_comparable_mismatch_count": unexplained_block_mismatch,
        "block_mismatch_matrix": {
            "|".join(map(str, key)): value for key, value in sorted(block_mismatch_matrix.items(), key=lambda kv: tuple(map(str, kv[0])))
        },
        "legacy_raw_out_of_span_public_return_trip_count": len(old_outspan),
        "legacy_out_of_span_bus_to_rail_connection_row_count": legacy_outspan_connection_rows,
        "legacy_out_of_span_bus_to_rail_planned_connection_row_count": legacy_outspan_planned_rows,
        "legacy_direct_out_of_span_bus_to_rail_row_count": old_conn_scan["direct_out_of_span_bus_to_rail_row_count"],
        "new_raw_physical_out_of_span_return_trip_count": len(new_outspan),
        "new_out_of_span_bus_to_rail_connection_row_count": new_outspan_connection_rows,
        "new_out_of_span_bus_to_rail_planned_connection_row_count": new_outspan_planned_rows,
        "new_direct_out_of_span_bus_to_rail_row_count": new_conn_scan["direct_out_of_span_bus_to_rail_row_count"],
        "span_start_inclusive_end_exclusive_rule_enforced_in_new_stage_e": new_conn_scan["direct_out_of_span_bus_to_rail_row_count"] == 0 and new_outspan_connection_rows == 0,
        "legacy_out_of_span_examples": old_conn_scan["direct_out_of_span_examples"][:20],
        "new_out_of_span_violation_examples": new_conn_scan["direct_out_of_span_examples"][:20],
        "change_classification_counts": dict(sorted(category_counts.items())),
        "mismatch_examples": mismatches_examples,
        "technical_return_used_as_passenger_service_legacy": old_conn_scan["technical_return_true_count"] != 0,
        "technical_return_used_as_passenger_service_new": new_conn_scan["technical_return_true_count"] != 0,
        "ridership_created": False,
        "municipal_od_allocated": False,
        "passenger_weights_created": False,
        "synthetic_observations_created": False,
        "topologies_ranked": False,
        "budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "deterministic_rebuild": True,
        "lineage": {
            "legacy_stage_e_validation_sha256": sha256_path(old_val_path),
            "legacy_stage_e_connection_sha256": sha256_path(old_conn_path),
            "legacy_stage_e_surface_sha256": sha256_path(old_surface_path),
            "legacy_stage_e_block_sha256": sha256_path(old_block_path),
            "legacy_stage_d_summary_sha256": sha256_path(args.old_stage_d_summary),
            "legacy_stage_d_trips_sha256": sha256_path(args.old_stage_d_trips),
            "legacy_route_input_sha256": sha256_path(args.old_route_input),
            "new_stage_e_validation_sha256": sha256_path(new_val_path),
            "new_stage_e_connection_sha256": sha256_path(new_conn_path),
            "new_stage_e_surface_sha256": sha256_path(new_surface_path),
            "new_stage_e_block_sha256": sha256_path(new_block_path),
            "new_stage_d_validation_sha256": sha256_path(args.new_stage_d_validation),
            "new_stage_d_contexts_sha256": sha256_path(args.new_stage_d_contexts),
            "new_stage_d_timetables_sha256": sha256_path(args.new_stage_d_timetables),
            "new_stage_d_trips_sha256": sha256_path(args.new_stage_d_trips),
            "new_route_input_sha256": sha256_path(args.new_route_input),
            "rt001_context_split_inputs_sha256": sha256_path(split_path),
            "span_return_rule_audit_sha256": sha256_path(span_path),
            "semantic_robustness_surface_comparison_sha256": sha256_path(surface_out_path),
            "semantic_block_sensitivity_comparison_sha256": sha256_path(block_out_path),
            "semantic_timetable_change_classification_sha256": sha256_path(class_path),
        },
    }
    validation_path = out / "stage_e_old_vs_new_robustness_audit_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": validation["status"],
        "common_semantic_timetables": len(common_sem),
        "rt001_split_inputs": len(split_sources),
        "legacy_outspan_returns": len(old_outspan),
        "legacy_outspan_connection_rows": legacy_outspan_connection_rows,
        "new_outspan_connection_rows": new_outspan_connection_rows,
        "surface_unexplained": unexplained_surface_mismatch,
        "block_unexplained": unexplained_block_mismatch,
        "change_classes": validation["change_classification_counts"],
    }, indent=2, sort_keys=True))
    return 0 if validation["status"] == STATUS_PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
