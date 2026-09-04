#!/usr/bin/env python3
"""Export source-closed, non-decisional finalist data for the visual workstream.

The export contains exact route anchor order and certified point coordinates.
It does not create routed polylines, geocode missing anchors, rank finalists or
select PRIMARY / RUNNER-UP.  Connections between exported points must therefore
be presented as schematic unless a separately certified route geometry exists.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

STATUS = "PASS_PHASE2_FINALIST_SITE_DATA_EXPORT_A"
EXPECTED_TIMETABLES = {
    "D4RT001V3_a87577dd79b3cb3e",
    "D4RT001V3_a81a3718416f5cb2",
    "D4RT001V3_c7318c775dcc1931",
    "D4RT001V3_a83abc3b41a4ee68",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def existing_cluster_points(path: Path) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_csv(path):
        cluster = row.get("physical_cluster_id", "").strip()
        if cluster:
            grouped.setdefault(cluster, []).append(row)
    result: dict[str, dict[str, str]] = {}
    for cluster, rows in grouped.items():
        # Use an actual frozen GTFS stop coordinate, never a synthetic centroid.
        representative = sorted(rows, key=lambda r: (r.get("stop_id", ""), r.get("stop_name", "")))[0]
        result[cluster] = {
            "display_name": representative.get("stop_name", "") or cluster,
            "lat": representative.get("stop_lat", ""),
            "lon": representative.get("stop_lon", ""),
            "coordinate_status": "FROZEN_OFFICIAL_GTFS_STOP_COORDINATE",
            "coordinate_source_id": representative.get("stop_id", ""),
            "municipality": representative.get("COMUNE", ""),
        }
    return result


def proposed_points(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        cid = row.get("candidate_id", "").strip()
        if not cid:
            continue
        result[cid] = {
            "display_name": cid,
            "lat": row.get("lat", ""),
            "lon": row.get("lon", ""),
            "coordinate_status": "FROZEN_PROPOSED_STOP_CANDIDATE_COORDINATE",
            "coordinate_source_id": cid,
            "municipality": row.get("COMUNE", ""),
        }
    return result


def resolve_anchor(anchor: str, existing: dict[str, dict[str, str]], proposed: dict[str, dict[str, str]], label: str) -> dict[str, str]:
    raw = anchor.strip()
    if raw in existing:
        return {**existing[raw], "anchor_id": raw}
    if raw.startswith("existing:") and raw.split(":", 1)[1] in existing:
        key = raw.split(":", 1)[1]
        return {**existing[key], "anchor_id": raw}
    if raw in proposed:
        return {**proposed[raw], "anchor_id": raw, "display_name": label or raw}
    if raw.startswith("proposed:") and raw.split(":", 1)[1] in proposed:
        key = raw.split(":", 1)[1]
        return {**proposed[key], "anchor_id": raw, "display_name": label or raw}
    if raw == "rail:S01514":
        return {
            "anchor_id": raw,
            "display_name": label or "Olgiate-Calco-Brivio FS",
            "lat": "",
            "lon": "",
            "coordinate_status": "CANONICAL_RAIL_COORDINATE_NOT_MATERIALISED_IN_PINNED_STOP_TABLES",
            "coordinate_source_id": "",
            "municipality": "",
        }
    return {
        "anchor_id": raw,
        "display_name": label or raw,
        "lat": "",
        "lon": "",
        "coordinate_status": "UNRESOLVED_FROM_PINNED_STOP_TABLES",
        "coordinate_source_id": "",
        "municipality": "",
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--diagnostic-dir", type=Path, default=Path("outputs/phase2/finalist_simplicity_diagnostic_a"))
    p.add_argument("--existing-stops", type=Path, default=Path(".finalist_sources/existing_official_stops.csv"))
    p.add_argument("--proposed-stops", type=Path, default=Path(".finalist_sources/proposed_stop_candidates.csv"))
    p.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/finalist_site_data_a"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    routes_path = args.diagnostic_dir / "finalist_route_structure_v3.csv"
    timetables_path = args.diagnostic_dir / "finalist_timetable_structure_v3.csv"
    departures_path = args.diagnostic_dir / "finalist_exact_departures_v3.csv"
    validation_path = args.diagnostic_dir / "finalist_simplicity_diagnostic_v3_validation.json"

    routes = read_csv(routes_path)
    timetables = read_csv(timetables_path)
    departures = read_csv(departures_path)
    diagnostic_validation = json.loads(validation_path.read_text(encoding="utf-8"))
    timetable_ids = {r["selected_timetable_id"] for r in timetables}
    if timetable_ids != EXPECTED_TIMETABLES:
        raise ValueError(f"unexpected finalist timetable set: {sorted(timetable_ids)}")
    if diagnostic_validation.get("status") != "PASS_PHASE2_FINALIST_SIMPLICITY_DIAGNOSTIC_V3":
        raise ValueError("upstream finalist diagnostic is not PASS")

    existing = existing_cluster_points(args.existing_stops)
    proposed = proposed_points(args.proposed_stops)

    timetable_meta = {r["selected_timetable_id"]: r for r in timetables}
    sequence_rows: list[dict[str, object]] = []
    unresolved: set[str] = set()
    for route in sorted(routes, key=lambda r: (r["selected_timetable_id"], int(r["route_ordinal"]))):
        anchors = json.loads(route["anchors_json"])
        labels = json.loads(route["anchor_labels_json"])
        if len(anchors) != len(labels):
            raise ValueError("anchor/label cardinality mismatch")
        meta = timetable_meta[route["selected_timetable_id"]]
        for idx, (anchor, label) in enumerate(zip(anchors, labels), start=1):
            point = resolve_anchor(str(anchor), existing, proposed, str(label))
            if point["coordinate_status"] == "UNRESOLVED_FROM_PINNED_STOP_TABLES":
                unresolved.add(str(anchor))
            sequence_rows.append({
                "selected_timetable_id": route["selected_timetable_id"],
                "plan_context_id": route["plan_context_id"],
                "scenario_id": route["scenario_id"],
                "topology_family": route["topology_family"],
                "span_minutes": meta["span_minutes"],
                "span_start_clock": meta["span_start_clock"],
                "span_end_clock": meta["span_end_clock"],
                "route_ordinal": route["route_ordinal"],
                "route_id": route["route_id"],
                "phase_min": route["phase_min"],
                "sequence_index": idx,
                "anchor_id": point["anchor_id"],
                "display_name": point["display_name"],
                "municipality": point["municipality"],
                "lat": point["lat"],
                "lon": point["lon"],
                "coordinate_status": point["coordinate_status"],
                "coordinate_source_id": point["coordinate_source_id"],
                "public_service_returns_to_hub": route["public_service_returns_to_hub"],
                "vehicle_closure_added": route["vehicle_closure_added"],
                "geometry_semantics": "ORDERED_CERTIFIED_ANCHOR_POINTS_ONLY_NO_ROUTED_POLYLINE",
            })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sequence_path = args.output_dir / "finalist_route_stop_sequence_site_a.csv"
    fields = [
        "selected_timetable_id", "plan_context_id", "scenario_id", "topology_family",
        "span_minutes", "span_start_clock", "span_end_clock", "route_ordinal", "route_id",
        "phase_min", "sequence_index", "anchor_id", "display_name", "municipality", "lat", "lon",
        "coordinate_status", "coordinate_source_id", "public_service_returns_to_hub",
        "vehicle_closure_added", "geometry_semantics",
    ]
    write_csv(sequence_path, fields, sequence_rows)

    # Copy the exact diagnostic tables into a stable site-facing package without
    # altering their values or semantics.
    for source_name, target_name in (
        ("finalist_timetable_structure_v3.csv", "finalist_timetables_site_a.csv"),
        ("finalist_route_structure_v3.csv", "finalist_routes_site_a.csv"),
        ("finalist_exact_departures_v3.csv", "finalist_departures_site_a.csv"),
        ("finalist_stage_f_summary_v3.csv", "finalist_stage_f_site_a.csv"),
    ):
        (args.output_dir / target_name).write_bytes((args.diagnostic_dir / source_name).read_bytes())

    coordinate_counts: dict[str, int] = {}
    for row in sequence_rows:
        status = str(row["coordinate_status"])
        coordinate_counts[status] = coordinate_counts.get(status, 0) + 1

    manifest = {
        "status": STATUS,
        "purpose": "NONDECISIONAL_VISUALISATION_INPUT_FOR_FOUR_FINALISTS",
        "selected_timetable_ids": sorted(timetable_ids),
        "finalist_count": 4,
        "route_count": len(routes),
        "sequence_point_count": len(sequence_rows),
        "topology_families": sorted({r["topology_family"] for r in timetables}),
        "span_minutes": sorted({int(r["span_minutes"]) for r in timetables}),
        "coordinate_status_counts": coordinate_counts,
        "unresolved_nonrail_anchor_ids": sorted(unresolved),
        "actual_routed_geometry_exported": False,
        "schematic_connection_between_ordered_points_permitted": True,
        "schematic_connection_must_be_labelled_as_schematic": True,
        "geocoding_used": False,
        "nearest_neighbour_matching_used": False,
        "fuzzy_matching_used": False,
        "invented_coordinates_used": False,
        "weighted_score_used": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "diagnostic_validation_sha256": sha256_path(validation_path),
            "diagnostic_routes_sha256": sha256_path(routes_path),
            "diagnostic_timetables_sha256": sha256_path(timetables_path),
            "diagnostic_departures_sha256": sha256_path(departures_path),
            "existing_stops_sha256": sha256_path(args.existing_stops),
            "proposed_stops_sha256": sha256_path(args.proposed_stops),
            "site_sequence_sha256": sha256_path(sequence_path),
        },
    }
    (args.output_dir / "finalist_site_data_manifest_a.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
