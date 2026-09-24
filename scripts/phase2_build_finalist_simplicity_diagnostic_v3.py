#!/usr/bin/env python3
"""Materialise the non-decisional Phase 2 Finalist Simplicity Diagnostic V3.

The four-finalist universe is sourced exclusively from the Final Policy Dry Run
V3. Each dry-run survivor must map deterministically to one canonical Stage-D
exact timetable from the pinned lineage. No weighted complexity score, ranking,
PRIMARY or RUNNER-UP selection is produced.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

STATUS = "PASS_PHASE2_FINALIST_SIMPLICITY_DIAGNOSTIC_V3"
CONTRACT = "PHASE2_NONDECISIONAL_FINALIST_SIMPLICITY_CLOCKFACE_V3"
EXPECTED_FINALISTS = 4
EXPECTED_TOPOLOGIES = {"two_independent_loops", "interlined_figure8"}
EXPECTED_SPANS_MIN = {960, 1110}
EXPECTED_HEADWAY_MIN = 60
STAGE_D_TIMETABLE_PREFIX = "D4RT001V3_"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def parse_json_list(value: str) -> list:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"expected JSON list, got {type(parsed).__name__}")
    return parsed


def strict_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field}: expected true/false, got {value!r}")


def minute_to_clock(minute: int | float | str) -> str:
    whole = int(round(float(minute))) % (24 * 60)
    return f"{whole // 60:02d}:{whole % 60:02d}"


def circular_gap_summary(minutes: list[int], headway: int) -> dict[str, object]:
    unique = sorted({minute % headway for minute in minutes})
    if not unique:
        return {
            "combined_phase_minutes_json": "[]",
            "combined_phase_gap_minutes_json": "[]",
            "max_combined_phase_gap_min": "",
            "min_combined_phase_gap_min": "",
        }
    if len(unique) == 1:
        gaps = [headway]
    else:
        gaps = [b - a for a, b in zip(unique, unique[1:])] + [
            headway - unique[-1] + unique[0]
        ]
    return {
        "combined_phase_minutes_json": json.dumps(unique, separators=(",", ":")),
        "combined_phase_gap_minutes_json": json.dumps(gaps, separators=(",", ":")),
        "max_combined_phase_gap_min": max(gaps),
        "min_combined_phase_gap_min": min(gaps),
    }


def jaccard_nonhub(left: list[str], right: list[str]) -> tuple[int, int, float]:
    """Descriptive overlap only. It is never converted to a simplicity score."""
    def nonhub(values: list[str]) -> set[str]:
        return {v for v in values if not (v.startswith("rail:") or v == "EX_039")}

    a, b = nonhub(left), nonhub(right)
    union = a | b
    shared = a & b
    return len(shared), len(union), (len(shared) / len(union) if union else 0.0)


def stable_stage_d_timetable_id(stage_d_input_id: str, phases: list[int]) -> str:
    """Reproduce the pinned Stage-D deterministic timetable identity."""
    payload = json.dumps(
        {"stage_d_input_id": stage_d_input_id, "phases": list(phases)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return STAGE_D_TIMETABLE_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def finalist_alias(topology_family: str, span_minutes: int) -> str:
    topology_code = {
        "interlined_figure8": "FIG",
        "two_independent_loops": "TWO",
    }.get(topology_family)
    if topology_code is None:
        raise ValueError(f"unsupported finalist topology {topology_family!r}")
    hours = span_minutes / 60
    hours_label = str(int(hours)) if float(hours).is_integer() else f"{hours:.1f}".rstrip("0").rstrip(".")
    return f"TT-{topology_code}-{hours_label}"


def build_anchor_labels(paths: list[Path]) -> dict[str, str]:
    """Use exact certified identifiers only; no fuzzy or nearest-neighbour matching."""
    result: dict[str, str] = {
        "rail:S01514": "Olgiate-Calco-Brivio FS",
        "EX_039": "Olgiate-Calco-Brivio FS pedestrian hub",
    }
    id_candidates = (
        "anchor_id", "candidate_id", "stop_id", "physical_cluster_id", "cluster_id",
        "existing_stop_id", "proposed_stop_id", "id",
    )
    label_candidates = (
        "display_name", "stop_name", "name", "label", "settlement_name",
        "destination_name", "municipality", "source_stop_name",
    )
    for path in paths:
        fields, rows = read_csv(path)
        id_fields = [field for field in id_candidates if field in fields]
        label_fields = [field for field in label_candidates if field in fields]
        for row in rows:
            label = next(
                (row.get(field, "").strip() for field in label_fields if row.get(field, "").strip()),
                "",
            )
            if not label:
                continue
            for field in id_fields:
                key = row.get(field, "").strip()
                if key and key not in result:
                    result[key] = label
    return result


def validate_finalist_lineage(
    finalists: list[dict[str, str]],
    timetable_rows: list[dict[str, str]],
) -> tuple[dict[str, dict[str, str]], list[dict[str, object]]]:
    if len(finalists) != EXPECTED_FINALISTS:
        raise ValueError(f"expected {EXPECTED_FINALISTS} dry-run finalists, got {len(finalists)}")

    dry_ids = [row.get("selected_timetable_id", "").strip() for row in finalists]
    if any(not value for value in dry_ids) or len(set(dry_ids)) != EXPECTED_FINALISTS:
        raise ValueError("dry-run finalists must contain four unique selected_timetable_id values")

    if {row["topology_family"] for row in finalists} != EXPECTED_TOPOLOGIES:
        raise ValueError("unexpected dry-run topology family universe")
    if {int(row["span_minutes"]) for row in finalists} != EXPECTED_SPANS_MIN:
        raise ValueError("unexpected dry-run service-span universe")
    if any(int(row["uniform_headway_min"]) != EXPECTED_HEADWAY_MIN for row in finalists):
        raise ValueError("all four finalists must remain H60")

    structural_keys = [(row["topology_family"], int(row["span_minutes"])) for row in finalists]
    if len(set(structural_keys)) != EXPECTED_FINALISTS:
        raise ValueError("finalist topology/span mapping is not one-to-one")

    selected: dict[str, dict[str, str]] = {}
    seen_stage_d: set[str] = set()
    dry_id_set = set(dry_ids)
    for row in timetable_rows:
        tt_id = row.get("selected_timetable_id", "").strip()
        if not tt_id:
            raise ValueError("blank selected_timetable_id in Stage D")
        if tt_id in seen_stage_d:
            raise ValueError(f"duplicate Stage-D selected_timetable_id {tt_id}")
        seen_stage_d.add(tt_id)
        if tt_id in dry_id_set:
            selected[tt_id] = row

    if set(selected) != dry_id_set:
        missing = sorted(dry_id_set - set(selected))
        raise ValueError(f"dry-run finalists missing from pinned Stage D: {missing}")

    lineage_rows: list[dict[str, object]] = []
    for finalist in sorted(finalists, key=lambda row: (row["topology_family"], int(row["span_minutes"]))):
        tt_id = finalist["selected_timetable_id"]
        tt = selected[tt_id]
        phases = [int(value) for value in parse_json_list(tt["selected_phase_vector_json"])]
        route_ids = [str(value) for value in parse_json_list(tt["public_route_ids_json"])]
        recomputed = stable_stage_d_timetable_id(tt["stage_d_input_id"], phases)
        if recomputed != tt_id:
            raise ValueError(f"{tt_id}: Stage-D deterministic identity mismatch; recomputed {recomputed}")

        comparisons = {
            "scenario_id": (finalist["scenario_id"], tt["scenario_id"]),
            "topology_family": (finalist["topology_family"], tt["topology_family"]),
            "uniform_headway_min": (int(finalist["uniform_headway_min"]), int(tt["uniform_headway_min"])),
            "span_minutes": (int(finalist["span_minutes"]), int(tt["span_end_min"]) - int(tt["span_start_min"])),
            "public_route_count": (int(finalist["public_route_count"]), int(tt["public_route_count"])),
        }
        mismatches = {
            key: {"dry_run": left, "stage_d": right}
            for key, (left, right) in comparisons.items()
            if left != right
        }
        if mismatches:
            raise ValueError(f"{tt_id}: dry-run/Stage-D structural mismatch {mismatches}")
        if int(tt["uniform_headway_min"]) != EXPECTED_HEADWAY_MIN:
            raise ValueError(f"{tt_id}: Stage D is not H60")
        if len(route_ids) != int(tt["public_route_count"]) or len(phases) != len(route_ids):
            raise ValueError(f"{tt_id}: route/phase cardinality mismatch")
        if strict_bool(tt["exact_timetable_constructed"], field="exact_timetable_constructed") is not True:
            raise ValueError(f"{tt_id}: Stage-D row is not an exact constructed timetable")

        span_minutes = int(finalist["span_minutes"])
        lineage_rows.append({
            "finalist_alias": finalist_alias(finalist["topology_family"], span_minutes),
            "plan_context_id": finalist["plan_context_id"],
            "selected_timetable_id": tt_id,
            "stage_d_input_id": tt["stage_d_input_id"],
            "scenario_id": finalist["scenario_id"],
            "topology_family": finalist["topology_family"],
            "service_span_min": span_minutes,
            "uniform_headway_min": int(tt["uniform_headway_min"]),
            "public_route_count": int(tt["public_route_count"]),
            "public_route_ids": route_ids,
            "selected_phase_vector_min": phases,
            "derived_timetable_id": recomputed,
            "derived_timetable_id_verified": True,
        })

    aliases = {row["finalist_alias"] for row in lineage_rows}
    if aliases != {"TT-FIG-16", "TT-TWO-16", "TT-FIG-18.5", "TT-TWO-18.5"}:
        raise ValueError(f"unexpected structurally-derived finalist aliases {sorted(aliases)}")
    return selected, lineage_rows


def build(args: argparse.Namespace) -> dict:
    _, finalists = read_csv(args.finalists)
    timetable_fields, timetable_rows = read_csv(args.stage_d_timetables)
    required_tt_fields = {
        "selected_timetable_id", "stage_d_input_id", "scenario_id", "topology_family",
        "uniform_headway_min", "span_start_min", "span_end_min", "public_route_count",
        "public_route_ids_json", "selected_phase_vector_json", "exact_timetable_constructed",
    }
    if not required_tt_fields.issubset(timetable_fields):
        raise ValueError(f"Stage-D timetable schema missing {sorted(required_tt_fields - set(timetable_fields))}")

    selected_tt, lineage_rows = validate_finalist_lineage(finalists, timetable_rows)
    timetable_ids = set(selected_tt)
    finalist_by_tt = {row["selected_timetable_id"]: row for row in finalists}
    lineage_by_tt = {row["selected_timetable_id"]: row for row in lineage_rows}

    _, route_rows = read_csv(args.stage_d_routes)
    if len({row["route_id"] for row in route_rows}) != len(route_rows):
        raise ValueError("duplicate route_id in pinned Stage-D route input")
    routes = {row["route_id"]: row for row in route_rows}

    trip_fields, trip_rows = read_csv(args.stage_d_trips)
    required_trip_fields = {
        "selected_timetable_id", "route_id", "route_phase_min", "trip_ordinal",
        "departure_min", "public_service_end_min", "vehicle_return_hub_min",
    }
    if not required_trip_fields.issubset(trip_fields):
        raise ValueError(f"Stage-D trip schema missing {sorted(required_trip_fields - set(trip_fields))}")
    finalist_trips = [row for row in trip_rows if row["selected_timetable_id"] in timetable_ids]
    if not finalist_trips:
        raise ValueError("no exact Stage-D trips found for finalists")

    stage_f_fields, stage_f_rows = read_csv(args.stage_f_summary)
    finalist_stage_f = [row for row in stage_f_rows if row.get("selected_timetable_id") in timetable_ids]
    stage_f_by_tt: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in finalist_stage_f:
        stage_f_by_tt[row["selected_timetable_id"]].append(row)
    if set(stage_f_by_tt) != timetable_ids:
        raise ValueError("Stage-F summary does not cover all four finalists")
    profile_sets = {tt_id: {row["profile_id"] for row in rows} for tt_id, rows in stage_f_by_tt.items()}
    profile_counts = {tt_id: len(values) for tt_id, values in profile_sets.items()}
    if set(profile_counts.values()) != {3}:
        raise ValueError(f"expected three Stage-F profiles per finalist, got {profile_counts}")
    if len({tuple(sorted(values)) for values in profile_sets.values()}) != 1:
        raise ValueError("Stage-F profile universe differs across finalists")
    if len(finalist_stage_f) != EXPECTED_FINALISTS * 3:
        raise ValueError(f"expected 12 Stage-F finalist summary rows, got {len(finalist_stage_f)}")
    for row in finalist_stage_f:
        for field in ("primary_selected", "runner_up_selected", "weighted_composite_score"):
            if strict_bool(row[field], field=f"Stage-F {field}") is not False:
                raise ValueError(f"Stage-F non-decisional contract violated by {field}")

    labels = build_anchor_labels([args.existing_stops, args.proposed_stops, args.settlement_anchors])

    trips_by_tt_route: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for trip in finalist_trips:
        trips_by_tt_route[(trip["selected_timetable_id"], trip["route_id"])].append(trip)

    route_output: list[dict[str, object]] = []
    timetable_output: list[dict[str, object]] = []
    departures_output: list[dict[str, object]] = []

    for tt_id in sorted(timetable_ids):
        finalist = finalist_by_tt[tt_id]
        lineage = lineage_by_tt[tt_id]
        tt = selected_tt[tt_id]
        alias = str(lineage["finalist_alias"])
        route_ids = [str(v) for v in parse_json_list(tt["public_route_ids_json"])]
        phases = [int(v) for v in parse_json_list(tt["selected_phase_vector_json"])]

        sequences: list[list[str]] = []
        all_departure_phases: list[int] = []
        public_return_count = 0
        technical_closure_count = 0
        exact_trip_count = 0

        for ordinal, (route_id, phase) in enumerate(zip(route_ids, phases), start=1):
            if route_id not in routes:
                raise ValueError(f"route {route_id} missing from canonical Stage-D route input")
            route = routes[route_id]
            anchors = [str(v) for v in parse_json_list(route["anchors_json"])]
            sequences.append(anchors)
            route_trips = sorted(
                trips_by_tt_route[(tt_id, route_id)],
                key=lambda row: (float(row["departure_min"]), int(row["trip_ordinal"])),
            )
            if not route_trips:
                raise ValueError(f"no exact trips for {tt_id}/{route_id}")
            exact_trip_count += len(route_trips)
            departure_minutes = [int(round(float(row["departure_min"]))) for row in route_trips]
            route_phase_values = sorted({minute % int(tt["uniform_headway_min"]) for minute in departure_minutes})
            all_departure_phases.extend(route_phase_values)
            intervals = [b - a for a, b in zip(departure_minutes, departure_minutes[1:])]
            public_return = strict_bool(route["public_service_returns_to_hub"], field=f"{route_id}.public_service_returns_to_hub")
            technical_closure = strict_bool(route["vehicle_closure_added"], field=f"{route_id}.vehicle_closure_added")
            public_return_count += int(public_return)
            technical_closure_count += int(technical_closure)
            technical_closure_min = float(route["cycle_runtime_min"]) - float(route["public_runtime_min"])
            if technical_closure_min < -1e-9:
                raise ValueError(f"{route_id}: cycle runtime shorter than public runtime")

            labelled_sequence = [labels.get(anchor, anchor) for anchor in anchors]
            route_output.append({
                "finalist_alias": alias,
                "plan_context_id": finalist["plan_context_id"],
                "selected_timetable_id": tt_id,
                "stage_d_input_id": tt["stage_d_input_id"],
                "scenario_id": finalist["scenario_id"],
                "topology_family": finalist["topology_family"],
                "service_span_min": finalist["span_minutes"],
                "public_route_ordinal": ordinal,
                "public_route_slot": f"route_{ordinal}",
                "route_id": route_id,
                "phase_min": phase,
                "first_clockface_departure_min": int(tt["span_start_min"]) + phase,
                "first_clockface_departure_clock": minute_to_clock(int(tt["span_start_min"]) + phase),
                "anchor_count": len(anchors),
                "anchors_json": json.dumps(anchors, separators=(",", ":")),
                "anchor_labels_json": json.dumps(labelled_sequence, ensure_ascii=False, separators=(",", ":")),
                "sequence_semantics": "ORDERED_CERTIFIED_ANCHORS_ONLY_NO_ROUTED_GEOMETRY",
                "public_runtime_min": route["public_runtime_min"],
                "cycle_runtime_min": route["cycle_runtime_min"],
                "technical_closure_min": f"{max(0.0, technical_closure_min):.9f}",
                "public_service_starts_at_hub": route["public_service_starts_at_hub"],
                "public_service_returns_to_hub": route["public_service_returns_to_hub"],
                "vehicle_closure_added": route["vehicle_closure_added"],
                "rail_to_bus_supported": route["rail_to_bus_passenger_event_supported"],
                "bus_to_rail_supported": route["bus_to_rail_passenger_event_supported"],
                "exact_public_trip_count": len(route_trips),
                "first_public_departure_min": route_trips[0]["departure_min"],
                "first_public_departure_clock": minute_to_clock(route_trips[0]["departure_min"]),
                "last_public_departure_min": route_trips[-1]["departure_min"],
                "last_public_departure_clock": minute_to_clock(route_trips[-1]["departure_min"]),
                "observed_departure_phase_values_json": json.dumps(route_phase_values, separators=(",", ":")),
                "observed_intervals_json": json.dumps(sorted(set(intervals)), separators=(",", ":")),
                "perfect_clockface_route": str(all(interval == int(tt["uniform_headway_min"]) for interval in intervals)).lower(),
            })

            for trip in route_trips:
                public_end = float(trip["public_service_end_min"])
                vehicle_return = float(trip["vehicle_return_hub_min"])
                closure = vehicle_return - public_end
                if closure < -1e-9:
                    raise ValueError(f"{tt_id}/{route_id}: vehicle return precedes public service end")
                departures_output.append({
                    "finalist_alias": alias,
                    "selected_timetable_id": tt_id,
                    "topology_family": finalist["topology_family"],
                    "service_span_min": finalist["span_minutes"],
                    "public_route_ordinal": ordinal,
                    "route_id": route_id,
                    "trip_ordinal": trip["trip_ordinal"],
                    "route_phase_min": trip["route_phase_min"],
                    "public_departure_min": trip["departure_min"],
                    "public_departure_clock": minute_to_clock(trip["departure_min"]),
                    "public_service_end_min": trip["public_service_end_min"],
                    "public_service_end_clock": minute_to_clock(trip["public_service_end_min"]),
                    "vehicle_return_hub_min": trip["vehicle_return_hub_min"],
                    "vehicle_return_hub_clock": minute_to_clock(trip["vehicle_return_hub_min"]),
                    "technical_closure_min": f"{max(0.0, closure):.9f}",
                    "technical_closure_distinct_from_passenger_service": "true",
                })

        shared_count = union_count = 0
        overlap = 0.0
        if len(sequences) == 2:
            shared_count, union_count, overlap = jaccard_nonhub(sequences[0], sequences[1])
        phase_summary = circular_gap_summary(all_departure_phases, int(tt["uniform_headway_min"]))
        timetable_output.append({
            "finalist_alias": alias,
            "plan_context_id": finalist["plan_context_id"],
            "selected_timetable_id": tt_id,
            "stage_d_input_id": tt["stage_d_input_id"],
            "derived_timetable_id_verified": "true",
            "scenario_id": finalist["scenario_id"],
            "topology_family": finalist["topology_family"],
            "uniform_headway_min": tt["uniform_headway_min"],
            "span_start_min": tt["span_start_min"],
            "span_end_min": tt["span_end_min"],
            "span_start_clock": minute_to_clock(tt["span_start_min"]),
            "span_end_clock": minute_to_clock(tt["span_end_min"]),
            "span_minutes": finalist["span_minutes"],
            "public_route_count": len(route_ids),
            "public_route_ids_json": tt["public_route_ids_json"],
            "selected_phase_vector_json": tt["selected_phase_vector_json"],
            "exact_public_trip_count": exact_trip_count,
            "public_return_route_count": public_return_count,
            "technical_closure_route_count": technical_closure_count,
            "shared_nonhub_anchor_count": shared_count,
            "union_nonhub_anchor_count": union_count,
            "route_nonhub_anchor_jaccard_descriptive_only": f"{overlap:.12f}",
            **phase_summary,
            "combined_departure_regular_if_equal_gaps": str(len(set(json.loads(phase_summary["combined_phase_gap_minutes_json"]))) <= 1).lower(),
            "exact_annual_bus_km": finalist["exact_annual_bus_km"],
            "total_coverage_10m": finalist["public_population_coverage_share_10min"],
            "worst_municipality_coverage_10m": finalist["public_worst_municipality_coverage_share_10min"],
            "bidirectional_reachable_share": finalist["bidirectional_reachable_share"],
            "stage_e_worst_bidirectional_retention": finalist["stage_e_bidirectional_worst_retention_share_engineering"],
            "stage_e_worst_block_slack_min": finalist["stage_e_worst_minimum_block_slack_min_engineering"],
            "field_check_pending_count": finalist["public_explicit_field_check_pending_count"],
        })

    if len(timetable_output) != EXPECTED_FINALISTS:
        raise ValueError("timetable output cardinality drift")
    if len(route_output) != EXPECTED_FINALISTS * 2:
        raise ValueError("route output cardinality drift")

    enriched_stage_f: list[dict[str, object]] = []
    for row in finalist_stage_f:
        finalist = finalist_by_tt[row["selected_timetable_id"]]
        lineage = lineage_by_tt[row["selected_timetable_id"]]
        enriched_stage_f.append({
            "finalist_alias": lineage["finalist_alias"],
            "plan_context_id": finalist["plan_context_id"],
            "service_span_min": finalist["span_minutes"],
            **row,
        })

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "finalist_timetable_structure_v3.csv", list(timetable_output[0].keys()), sorted(timetable_output, key=lambda row: str(row["finalist_alias"])))
    write_csv(output_dir / "finalist_route_structure_v3.csv", list(route_output[0].keys()), sorted(route_output, key=lambda row: (str(row["finalist_alias"]), int(row["public_route_ordinal"]))))
    write_csv(output_dir / "finalist_exact_departures_v3.csv", list(departures_output[0].keys()), sorted(departures_output, key=lambda row: (str(row["finalist_alias"]), int(row["public_route_ordinal"]), float(row["public_departure_min"]), int(row["trip_ordinal"]))))
    write_csv(output_dir / "finalist_stage_f_summary_v3.csv", list(enriched_stage_f[0].keys()), sorted(enriched_stage_f, key=lambda row: (str(row["finalist_alias"]), str(row["profile_id"]))))

    profile_ids = sorted(next(iter(profile_sets.values())))
    result = {
        "status": STATUS,
        "contract": CONTRACT,
        "diagnostic_role": "NON_DECISIONAL_DESCRIPTIVE_STRUCTURE_ONLY",
        "dry_run_finalist_count": len(finalists),
        "selected_timetable_count": len(timetable_ids),
        "finalist_aliases": sorted(row["finalist_alias"] for row in lineage_rows),
        "topology_families": sorted(EXPECTED_TOPOLOGIES),
        "service_span_minutes": sorted(EXPECTED_SPANS_MIN),
        "uniform_headway_min": EXPECTED_HEADWAY_MIN,
        "route_structure_row_count": len(route_output),
        "exact_public_trip_count": len(finalist_trips),
        "stage_f_summary_row_count": len(finalist_stage_f),
        "stage_f_profile_count_per_finalist": len(profile_ids),
        "stage_f_profile_ids": profile_ids,
        "stage_d_deterministic_id_rebuild_pass": True,
        "dry_run_to_stage_d_structural_join_pass": True,
        "technical_closure_kept_distinct_from_passenger_service": True,
        "actual_routed_geometry_exported": False,
        "route_geometry_semantics": "ORDERED_CERTIFIED_ANCHOR_SEQUENCE_ONLY_NO_ROAD_GEOMETRY",
        "weighted_complexity_score": False,
        "synthetic_complexity_score": False,
        "public_route_count_used_as_complexity_score": False,
        "topology_family_used_as_automatic_simplicity_rank": False,
        "simplicity_rank_materialized": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "winner_implied": False,
        "lineage_mappings": lineage_rows,
        "observable_simplicity_dimensions": [
            "route_anchor_sequences",
            "route_anchor_overlap_descriptive_only",
            "public_return_semantics",
            "technical_closure_semantics",
            "route_phase_relationship",
            "combined_station_departure_spacing",
            "exact_route_clockface_regularity",
            "stage_f_engineering_profiles",
        ],
        "source_commits": {
            "stage_d": args.stage_d_evidence_commit,
            "stage_f": args.stage_f_evidence_commit,
        },
        "lineage_sha256": {
            "finalists": sha256_path(args.finalists),
            "stage_d_timetables": sha256_path(args.stage_d_timetables),
            "stage_d_trips": sha256_path(args.stage_d_trips),
            "stage_d_routes": sha256_path(args.stage_d_routes),
            "stage_f_summary": sha256_path(args.stage_f_summary),
            "existing_stops": sha256_path(args.existing_stops),
            "proposed_stops": sha256_path(args.proposed_stops),
            "settlement_anchors": sha256_path(args.settlement_anchors),
        },
    }
    (output_dir / "finalist_simplicity_diagnostic_v3_validation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalists", type=Path, default=Path("outputs/phase2/final_policy_dry_run_v3/final_layer_survivors_diagnostic_v3.csv"))
    parser.add_argument("--stage-d-timetables", type=Path, default=Path(".finalist_sources/exact_selected_timetables_rt001_v3.csv"))
    parser.add_argument("--stage-d-trips", type=Path, default=Path(".finalist_sources/exact_selected_trips_rt001_v3.csv.gz"))
    parser.add_argument("--stage-d-routes", type=Path, default=Path(".finalist_sources/stage_d_public_route_inputs_rt001_v3.csv"))
    parser.add_argument("--stage-f-summary", type=Path, default=Path(".finalist_sources/stage_f_engineering_timetable_summary_rt001_v3.csv.gz"))
    parser.add_argument("--existing-stops", type=Path, default=Path(".finalist_sources/existing_official_stops.csv"))
    parser.add_argument("--proposed-stops", type=Path, default=Path(".finalist_sources/proposed_stop_candidates.csv"))
    parser.add_argument("--settlement-anchors", type=Path, default=Path(".finalist_sources/settlement_destination_anchors.csv"))
    parser.add_argument("--stage-d-evidence-commit", default="d41bb678382d018929c1c6b46542f12549f20d4f")
    parser.add_argument("--stage-f-evidence-commit", default="746a17c796f8e5fc24a636e47d304cd9293f2a43")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/finalist_simplicity_diagnostic_v3"))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), indent=2, sort_keys=True))
