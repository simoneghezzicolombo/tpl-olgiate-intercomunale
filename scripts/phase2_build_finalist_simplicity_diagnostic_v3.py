#!/usr/bin/env python3
"""Materialise a non-decisional simplicity/clockface diagnostic for V3 finalists.

The diagnostic operates only on the four policy-dry-run survivors and pinned
Stage-D / Stage-F evidence.  It does not assign a complexity score and does not
select PRIMARY or RUNNER-UP.  It reports observable public-facing structure:
route anchor sequences, shared anchors, public-return semantics, exact phases,
clockface departure gaps and the certified Stage-F timetable summary.
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
EXPECTED_TIMETABLES = {
    "D4RT001V3_1c3385bee64c718f",
    "D4RT001V3_9ca3a9a3989ac75f",
    "D4RT001V3_9a17bac9fbfdc609",
    "D4RT001V3_21d8e6b9be8ea59e",
}


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
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_json_list(value: str) -> list:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"expected JSON list, got {type(parsed).__name__}")
    return parsed


def minute_to_clock(minute: int) -> str:
    minute %= 24 * 60
    return f"{minute // 60:02d}:{minute % 60:02d}"


def circular_gap_summary(minutes: list[int], headway: int) -> dict[str, object]:
    unique = sorted({minute % headway for minute in minutes})
    if not unique:
        return {"combined_phase_minutes_json": "[]", "combined_phase_gap_minutes_json": "[]", "max_combined_phase_gap_min": "", "min_combined_phase_gap_min": ""}
    if len(unique) == 1:
        gaps = [headway]
    else:
        gaps = [b - a for a, b in zip(unique, unique[1:])] + [headway - unique[-1] + unique[0]]
    return {
        "combined_phase_minutes_json": json.dumps(unique, separators=(",", ":")),
        "combined_phase_gap_minutes_json": json.dumps(gaps, separators=(",", ":")),
        "max_combined_phase_gap_min": max(gaps),
        "min_combined_phase_gap_min": min(gaps),
    }


def jaccard_nonhub(left: list[str], right: list[str]) -> tuple[int, int, float]:
    # Rail hub may appear repeatedly in route sequences; it is removed from the
    # overlap diagnostic because every finalist is station-centred by design.
    def nonhub(values: list[str]) -> set[str]:
        return {v for v in values if not (v.startswith("rail:") or v == "EX_039")}
    a, b = nonhub(left), nonhub(right)
    union = a | b
    shared = a & b
    return len(shared), len(union), (len(shared) / len(union) if union else 0.0)


def build_anchor_labels(paths: list[Path]) -> dict[str, str]:
    """Best-effort labels from certified stop-universe tables, never fuzzy."""
    result: dict[str, str] = {"rail:S01514": "Olgiate-Calco-Brivio FS", "EX_039": "Olgiate-Calco-Brivio FS pedestrian hub"}
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
            label = next((row.get(field, "").strip() for field in label_fields if row.get(field, "").strip()), "")
            if not label:
                continue
            for field in id_fields:
                key = row.get(field, "").strip()
                if key and key not in result:
                    result[key] = label
    return result


def build(args: argparse.Namespace) -> dict:
    finalist_fields, finalists = read_csv(args.finalists)
    if len(finalists) != EXPECTED_FINALISTS:
        raise ValueError(f"expected {EXPECTED_FINALISTS} dry-run finalists, got {len(finalists)}")
    timetable_ids = {row["selected_timetable_id"] for row in finalists}
    if timetable_ids != EXPECTED_TIMETABLES:
        raise ValueError(f"unexpected finalist timetable set: {sorted(timetable_ids)}")
    if any(row.get("uniform_headway_min") != "60" for row in finalists):
        raise ValueError("current policy diagnostic finalists are expected to be H60")

    timetable_fields, timetable_rows = read_csv(args.stage_d_timetables)
    selected_tt = {row["selected_timetable_id"]: row for row in timetable_rows if row["selected_timetable_id"] in timetable_ids}
    if set(selected_tt) != timetable_ids:
        raise ValueError("not all finalist timetable IDs exist in canonical Stage D")

    route_fields, route_rows = read_csv(args.stage_d_routes)
    routes = {row["route_id"]: row for row in route_rows}

    trip_fields, trip_rows = read_csv(args.stage_d_trips)
    finalist_trips = [row for row in trip_rows if row["selected_timetable_id"] in timetable_ids]
    if not finalist_trips:
        raise ValueError("no exact Stage-D trips found for finalists")

    stage_f_fields, stage_f_rows = read_csv(args.stage_f_summary)
    finalist_stage_f = [row for row in stage_f_rows if row.get("selected_timetable_id") in timetable_ids]
    if len(finalist_stage_f) != EXPECTED_FINALISTS:
        raise ValueError(f"expected one Stage-F summary row per finalist, got {len(finalist_stage_f)}")

    labels = build_anchor_labels([args.existing_stops, args.proposed_stops, args.settlement_anchors])
    finalist_by_tt = {row["selected_timetable_id"]: row for row in finalists}

    trips_by_tt_route: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for trip in finalist_trips:
        trips_by_tt_route[(trip["selected_timetable_id"], trip["route_id"])].append(trip)

    route_output: list[dict[str, object]] = []
    timetable_output: list[dict[str, object]] = []
    departures_output: list[dict[str, object]] = []

    for tt_id in sorted(timetable_ids):
        finalist = finalist_by_tt[tt_id]
        tt = selected_tt[tt_id]
        route_ids = [str(v) for v in parse_json_list(tt["public_route_ids_json"])]
        phases = [int(v) for v in parse_json_list(tt["selected_phase_vector_json"])]
        if len(route_ids) != len(phases):
            raise ValueError(f"route/phase cardinality mismatch for {tt_id}")
        if int(tt["public_route_count"]) != len(route_ids):
            raise ValueError(f"public route count mismatch for {tt_id}")

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
            route_trips = sorted(trips_by_tt_route[(tt_id, route_id)], key=lambda r: float(r["public_departure_min"]))
            if not route_trips:
                raise ValueError(f"no exact trips for {tt_id}/{route_id}")
            exact_trip_count += len(route_trips)
            departure_minutes = [int(round(float(r["public_departure_min"]))) for r in route_trips]
            route_phase_values = sorted({minute % int(tt["uniform_headway_min"]) for minute in departure_minutes})
            all_departure_phases.extend(route_phase_values)
            intervals = [b - a for a, b in zip(departure_minutes, departure_minutes[1:])]
            public_return = str(route.get("public_service_returns_to_hub", "")).strip().lower() == "true"
            technical_closure = str(route.get("vehicle_closure_added", "")).strip().lower() == "true"
            public_return_count += int(public_return)
            technical_closure_count += int(technical_closure)

            labelled_sequence = [labels.get(anchor, anchor) for anchor in anchors]
            route_output.append({
                "plan_context_id": finalist["plan_context_id"],
                "selected_timetable_id": tt_id,
                "scenario_id": finalist["scenario_id"],
                "topology_family": finalist["topology_family"],
                "route_ordinal": ordinal,
                "route_id": route_id,
                "phase_min": phase,
                "phase_clock": minute_to_clock(int(tt["span_start_min"]) + phase),
                "anchor_count": len(anchors),
                "anchors_json": json.dumps(anchors, separators=(",", ":")),
                "anchor_labels_json": json.dumps(labelled_sequence, ensure_ascii=False, separators=(",", ":")),
                "public_runtime_min": route.get("public_runtime_min", ""),
                "cycle_runtime_min": route.get("cycle_runtime_min", ""),
                "public_service_starts_at_hub": route.get("public_service_starts_at_hub", ""),
                "public_service_returns_to_hub": route.get("public_service_returns_to_hub", ""),
                "vehicle_closure_added": route.get("vehicle_closure_added", ""),
                "rail_to_bus_supported": route.get("rail_to_bus_passenger_event_supported", ""),
                "bus_to_rail_supported": route.get("bus_to_rail_passenger_event_supported", ""),
                "exact_public_trip_count": len(route_trips),
                "first_public_departure_min": departure_minutes[0],
                "first_public_departure_clock": minute_to_clock(departure_minutes[0]),
                "last_public_departure_min": departure_minutes[-1],
                "last_public_departure_clock": minute_to_clock(departure_minutes[-1]),
                "observed_departure_phase_values_json": json.dumps(route_phase_values, separators=(",", ":")),
                "observed_intervals_json": json.dumps(sorted(set(intervals)), separators=(",", ":")),
                "perfect_clockface_route": str(all(interval == int(tt["uniform_headway_min"]) for interval in intervals)).lower(),
            })
            for trip in route_trips:
                departures_output.append({
                    "selected_timetable_id": tt_id,
                    "topology_family": finalist["topology_family"],
                    "route_id": route_id,
                    "public_departure_min": trip["public_departure_min"],
                    "public_departure_clock": minute_to_clock(int(round(float(trip["public_departure_min"])))),
                    "public_service_end_min": trip.get("public_service_end_min", ""),
                    "vehicle_return_hub_min": trip.get("vehicle_return_hub_min", ""),
                })

        shared_count = union_count = 0
        overlap = 0.0
        if len(sequences) == 2:
            shared_count, union_count, overlap = jaccard_nonhub(sequences[0], sequences[1])
        phase_summary = circular_gap_summary(all_departure_phases, int(tt["uniform_headway_min"]))
        timetable_output.append({
            "plan_context_id": finalist["plan_context_id"],
            "selected_timetable_id": tt_id,
            "scenario_id": finalist["scenario_id"],
            "topology_family": finalist["topology_family"],
            "uniform_headway_min": tt["uniform_headway_min"],
            "span_start_min": tt["span_start_min"],
            "span_end_min": tt["span_end_min"],
            "span_start_clock": minute_to_clock(int(tt["span_start_min"])),
            "span_end_clock": minute_to_clock(int(tt["span_end_min"])),
            "span_minutes": finalist["span_minutes"],
            "public_route_count": len(route_ids),
            "public_route_ids_json": tt["public_route_ids_json"],
            "selected_phase_vector_json": tt["selected_phase_vector_json"],
            "exact_public_trip_count": exact_trip_count,
            "public_return_route_count": public_return_count,
            "technical_closure_route_count": technical_closure_count,
            "shared_nonhub_anchor_count": shared_count,
            "union_nonhub_anchor_count": union_count,
            "route_nonhub_anchor_jaccard": f"{overlap:.12f}",
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

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    timetable_fields_out = list(timetable_output[0].keys())
    route_fields_out = list(route_output[0].keys())
    departure_fields_out = list(departures_output[0].keys())
    write_csv(output_dir / "finalist_timetable_structure_v3.csv", timetable_fields_out, timetable_output)
    write_csv(output_dir / "finalist_route_structure_v3.csv", route_fields_out, route_output)
    write_csv(output_dir / "finalist_exact_departures_v3.csv", departure_fields_out, sorted(departures_output, key=lambda r: (r["selected_timetable_id"], r["public_departure_min"], r["route_id"])))
    write_csv(output_dir / "finalist_stage_f_summary_v3.csv", stage_f_fields, sorted(finalist_stage_f, key=lambda r: r["selected_timetable_id"]))

    result = {
        "status": STATUS,
        "contract": CONTRACT,
        "dry_run_finalist_count": len(finalists),
        "selected_timetable_count": len(timetable_ids),
        "route_structure_row_count": len(route_output),
        "exact_public_trip_count": len(finalist_trips),
        "stage_f_summary_row_count": len(finalist_stage_f),
        "weighted_complexity_score": False,
        "public_route_count_used_as_complexity_score": False,
        "topology_family_used_as_automatic_simplicity_rank": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "current_service_v4_required_before_final_selection": True,
        "observable_simplicity_dimensions": [
            "route_anchor_sequences",
            "route_anchor_overlap",
            "public_return_semantics",
            "technical_closure_semantics",
            "route_phase_relationship",
            "combined_station_departure_spacing",
            "exact_route_clockface_regularity",
        ],
        "lineage": {
            "finalists_sha256": sha256_path(args.finalists),
            "stage_d_timetables_sha256": sha256_path(args.stage_d_timetables),
            "stage_d_trips_sha256": sha256_path(args.stage_d_trips),
            "stage_d_routes_sha256": sha256_path(args.stage_d_routes),
            "stage_f_summary_sha256": sha256_path(args.stage_f_summary),
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
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/finalist_simplicity_diagnostic_v3"))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), indent=2, sort_keys=True))
