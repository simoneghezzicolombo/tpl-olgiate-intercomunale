#!/usr/bin/env python3
"""Materialise audited PDF-row -> official stop identities for current service."""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.phase2_current_service_stop_identity import (  # noqa: E402
    GtfsStop,
    PageRow,
    normalize_stop_label,
    resolve_page,
    unique_route_patterns,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "phase2"
GTFS = ROOT / "data" / "raw" / "gtfs" / "agency_arriva"
PDF_ROWS = OUT / "current_service_pdf_stop_rows_2026-09-03.csv"
STOP_TIMES = OUT / "current_service_stop_times_2026-09-03.csv"
STOP_TRIP_MATRIX = OUT / "current_service_stop_trip_matrix_2026-09-03.csv"
PHASE2_STOPS = OUT / "existing_official_stops.csv"
IDENTITY_OUT = OUT / "current_service_stop_identity_2026-09-03.csv"
STOP_TIMES_OUT = OUT / "current_service_stop_times_with_identity_2026-09-03.csv"
MATRIX_OUT = OUT / "current_service_stop_trip_matrix_with_identity_2026-09-03.csv"
VALIDATION_OUT = OUT / "current_service_stop_identity_validation.json"
REQUIRED_ROUTES = ("D184", "D185", "D150", "D170")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty output {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    pdf_rows = read_csv(PDF_ROWS)
    current_stop_times = read_csv(STOP_TIMES)
    current_matrix = read_csv(STOP_TRIP_MATRIX)
    phase2_stops = read_csv(PHASE2_STOPS)
    gtfs_stops_rows = read_csv(GTFS / "stops.txt")
    gtfs_trips = read_csv(GTFS / "trips.txt")
    gtfs_stop_times = read_csv(GTFS / "stop_times.txt")

    observed_routes = {row["route_id"] for row in pdf_rows}
    if observed_routes != set(REQUIRED_ROUTES):
        raise ValueError(f"Unexpected PDF route universe: {sorted(observed_routes)}")

    gtfs_stops = {
        row["stop_id"]: GtfsStop(
            stop_id=row["stop_id"],
            stop_name=row["stop_name"],
            stop_lat=row.get("stop_lat", ""),
            stop_lon=row.get("stop_lon", ""),
        )
        for row in gtfs_stops_rows
    }
    patterns = unique_route_patterns(gtfs_trips, gtfs_stop_times, set(REQUIRED_ROUTES))
    if any(not patterns[route_id] for route_id in REQUIRED_ROUTES):
        raise ValueError("At least one required route has no historical official GTFS pattern")

    phase2_by_stop_id = {row["stop_id"]: row for row in phase2_stops}
    identity_rows: list[dict[str, object]] = []
    identity_by_key: dict[tuple[str, int, int], dict[str, object]] = {}

    groups: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in pdf_rows:
        key = (row["route_id"], int(row["source_page"]))
        groups.setdefault(key, []).append(row)

    for (route_id, source_page), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: int(row["stop_sequence_on_page"]))
        page_rows = [
            PageRow(
                route_id=route_id,
                source_page=source_page,
                stop_sequence_on_page=int(row["stop_sequence_on_page"]),
                stop_label_pdf=row["stop_label_pdf"],
            )
            for row in rows
        ]
        resolutions = resolve_page(page_rows, route_patterns=patterns[route_id], stops=gtfs_stops)
        for source, resolution in zip(rows, resolutions, strict=True):
            equivalent_ids = resolution.equivalent_stop_ids
            phase2_matches = [
                (stop_id, phase2_by_stop_id[stop_id])
                for stop_id in equivalent_ids
                if stop_id in phase2_by_stop_id
            ]
            if phase2_matches:
                cluster_ids = {row["physical_cluster_id"] for _, row in phase2_matches}
                if len(cluster_ids) != 1:
                    raise ValueError(
                        f"Exact-name/coordinate GTFS equivalence maps to multiple Phase 2 clusters: "
                        f"{equivalent_ids} -> {sorted(cluster_ids)}"
                    )
                canonical_stop_id, phase2 = sorted(phase2_matches, key=lambda item: item[0])[0]
                phase2_join_status = "JOINED_V1_PHYSICAL_CLUSTER_BY_EQUIVALENT_EXACT_GTFS_RECORD"
            elif resolution.stop_id:
                canonical_stop_id = resolution.stop_id
                phase2 = None
                phase2_join_status = "GTFS_IDENTIFIED_NOT_IN_V1_STOP_UNIVERSE"
            else:
                canonical_stop_id = ""
                phase2 = None
                phase2_join_status = "NO_RESOLVED_GTFS_IDENTITY"

            stop = gtfs_stops.get(canonical_stop_id)
            row_out: dict[str, object] = {
                "route_id": route_id,
                "source_page": source_page,
                "stop_sequence_on_page": resolution.row.stop_sequence_on_page,
                "stop_label_pdf": resolution.row.stop_label_pdf,
                "normalized_pdf_tokens": "|".join(normalize_stop_label(resolution.row.stop_label_pdf)),
                "identity_status": resolution.status,
                "historical_gtfs_stop_id": canonical_stop_id,
                "historical_gtfs_equivalent_stop_ids": "|".join(equivalent_ids),
                "historical_gtfs_equivalent_record_count": len(equivalent_ids),
                "historical_gtfs_stop_name": stop.stop_name if stop else "",
                "historical_gtfs_stop_lat": stop.stop_lat if stop else "",
                "historical_gtfs_stop_lon": stop.stop_lon if stop else "",
                "historical_gtfs_name_candidate_count": len(resolution.name_candidate_ids),
                "historical_gtfs_name_candidate_ids": "|".join(resolution.name_candidate_ids),
                "best_pattern_match_rows": resolution.best_pattern_match_rows,
                "tied_best_pattern_count": resolution.tied_best_pattern_count,
                "physical_cluster_id_v1": phase2.get("physical_cluster_id", "") if phase2 else "",
                "phase2_stop_name_v1": phase2.get("stop_name", "") if phase2 else "",
                "phase2_join_gtfs_stop_id": canonical_stop_id if phase2 else "",
                "phase2_join_status": phase2_join_status,
                "identity_evidence": (
                    "CURRENT_PRIMARY_PDF_LABEL_AND_ORDER_PLUS_VALIDITY_BOUNDED_HISTORICAL_OFFICIAL_GTFS"
                    if canonical_stop_id
                    else "CURRENT_PRIMARY_PDF_LABEL_WITHOUT_UNIQUE_HISTORICAL_GTFS_IDENTITY"
                ),
                "current_service_epistemic_status": source["epistemic_status"],
                "identity_epistemic_status": (
                    "DERIVED_IDENTITY_CROSSCHECK_NOT_CURRENT_GTFS_SERVICE_FACT"
                    if canonical_stop_id
                    else "UNRESOLVED_IDENTITY"
                ),
            }
            key = (route_id, source_page, resolution.row.stop_sequence_on_page)
            if key in identity_by_key:
                raise ValueError(f"Duplicate PDF stop-row identity key: {key}")
            identity_by_key[key] = row_out
            identity_rows.append(row_out)

    if len(identity_rows) != len(pdf_rows):
        raise ValueError("Identity materialisation did not preserve every PDF stop row")

    def attach_identity(rows: list[dict[str, str]], sequence_field: str) -> list[dict[str, object]]:
        joined: list[dict[str, object]] = []
        for row in rows:
            key = (row["route_id"], int(row["source_page"]), int(row[sequence_field]))
            identity = identity_by_key.get(key)
            if identity is None:
                raise ValueError(f"No identity row for current-service record {key}")
            joined.append({
                **row,
                "historical_gtfs_stop_id": identity["historical_gtfs_stop_id"],
                "physical_cluster_id_v1": identity["physical_cluster_id_v1"],
                "stop_identity_status": identity["identity_status"],
                "phase2_stop_join_status": identity["phase2_join_status"],
            })
        return joined

    joined_stop_times = attach_identity(current_stop_times, "pdf_row_sequence")
    joined_matrix = attach_identity(current_matrix, "stop_sequence_on_page")

    write_csv(IDENTITY_OUT, identity_rows)
    write_csv(STOP_TIMES_OUT, joined_stop_times)
    write_csv(MATRIX_OUT, joined_matrix)

    status_counts: dict[str, int] = {}
    join_counts: dict[str, int] = {}
    route_counts: dict[str, dict[str, int]] = {}
    for row in identity_rows:
        status = str(row["identity_status"])
        join_status = str(row["phase2_join_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
        join_counts[join_status] = join_counts.get(join_status, 0) + 1
        route = str(row["route_id"])
        route_counts.setdefault(route, {"pdf_rows": 0, "resolved_gtfs": 0, "joined_v1_cluster": 0})
        route_counts[route]["pdf_rows"] += 1
        if row["historical_gtfs_stop_id"]:
            route_counts[route]["resolved_gtfs"] += 1
        if row["physical_cluster_id_v1"]:
            route_counts[route]["joined_v1_cluster"] += 1

    resolved = sum(1 for row in identity_rows if row["historical_gtfs_stop_id"])
    joined_v1 = sum(1 for row in identity_rows if row["physical_cluster_id_v1"])
    validation: dict[str, object] = {
        "status": "PASS",
        "reference_date": "2026-09-03",
        "scope": "CURRENT_PDF_STOP_ROW_TO_OFFICIAL_STOP_IDENTITY_CROSSCHECK",
        "pdf_stop_rows_total": len(identity_rows),
        "resolved_historical_gtfs_identity_rows": resolved,
        "unresolved_or_ambiguous_rows": len(identity_rows) - resolved,
        "joined_v1_physical_cluster_rows": joined_v1,
        "identity_status_counts": status_counts,
        "phase2_join_status_counts": join_counts,
        "route_counts": route_counts,
        "current_stop_time_rows_preserved": len(joined_stop_times),
        "current_stop_trip_matrix_rows_preserved": len(joined_matrix),
        "matching_contract": {
            "edit_distance_fuzzy_matching_used": False,
            "forced_nearest_coordinate_matching_used": False,
            "manual_stop_alias_whitelist_used": False,
            "route_specific_manual_stop_mapping_used": False,
            "exact_name_coordinate_duplicate_gtfs_records_collapsed": True,
            "coordinate_distance_tolerance_for_equivalence_used": False,
            "name_rule": "CONSERVATIVE_TOKEN_CONTAINMENT_WITH_LONG_TOKEN_PREFIX_ONLY",
            "sequence_rule": "MAXIMUM_ORDERED_HISTORICAL_PATTERN_AGREEMENT; TIES PRESERVED",
            "duplicate_record_rule": "SAME_NORMALIZED_OFFICIAL_GTFS_NAME_AND_EXACT_NUMERIC_COORDINATES",
            "ambiguous_identity_policy": "UNRESOLVED_FAIL_OPEN_FOR_DATA_PRESERVATION_BUT_FORBIDDEN_FOR_WALKING_GJT_JOIN",
        },
        "historical_gtfs_semantics": {
            "role": "VALIDITY_BOUNDED_OFFICIAL_IDENTITY_AND_SEQUENCE_CROSSCHECK_ONLY",
            "used_to_assert_current_service_activation": False,
            "used_to_fill_current_unpublished_times": False,
            "current_pdf_times_remain_authoritative_for_2026_09_03": True,
        },
        "v1_cluster_semantics": {
            "join_key": "EXACT_GTFS_STOP_ID_OR_EXACT_NAME_COORDINATE_EQUIVALENT_GTFS_RECORD",
            "external_or_not_in_v1_stops_are_not_force_joined": True,
            "v2_refresh_expected": True,
        },
        "input_sha256": {
            "pdf_stop_rows": file_sha(PDF_ROWS),
            "current_stop_times": file_sha(STOP_TIMES),
            "current_stop_trip_matrix": file_sha(STOP_TRIP_MATRIX),
            "historical_gtfs_stops": file_sha(GTFS / "stops.txt"),
            "historical_gtfs_trips": file_sha(GTFS / "trips.txt"),
            "historical_gtfs_stop_times": file_sha(GTFS / "stop_times.txt"),
            "phase2_v1_existing_stops": file_sha(PHASE2_STOPS),
        },
        "output_sha256": {
            "identity": file_sha(IDENTITY_OUT),
            "stop_times_with_identity": file_sha(STOP_TIMES_OUT),
            "matrix_with_identity": file_sha(MATRIX_OUT),
        },
        "gjt_contract": {
            "rows_with_resolved_gtfs_identity_may_be_joined_to_spatial_stop_evidence": True,
            "ambiguous_or_unresolved_rows_may_not_be_used_as_spatial_stop_identity": True,
            "v1_cluster_absence_does_not_mean_stop_absence": True,
        },
    }
    VALIDATION_OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return validation


def main() -> None:
    validation = build()
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
