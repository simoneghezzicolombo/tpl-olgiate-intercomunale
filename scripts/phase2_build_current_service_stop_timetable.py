#!/usr/bin/env python3
"""Build the audited Phase 2 current-service stop x trip timetable."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.phase2_current_service_stop_timetable import (  # noqa: E402
    EXPECTED_GATE_C,
    GATE_C_COMMIT,
    REFERENCE_DATE,
    REQUIRED_ROUTES,
    TimetableAmbiguity,
    audit_historical_gtfs,
    build_conditions,
    fetch_bytes,
    fetch_gate_c_report,
    reconstruct_route,
    validate_against_gate_c,
    write_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/phase2")
    parser.add_argument("--gtfs-dir", default="data/raw/gtfs/agency_arriva")
    args = parser.parse_args()

    out = Path(args.output_dir)
    gtfs_dir = Path(args.gtfs_dir)
    report, gate_c_report_sha = fetch_gate_c_report()
    route_reports = list(report["routes"])
    report_routes = {str(r["route_id"]) for r in route_reports}
    if report_routes != set(REQUIRED_ROUTES):
        raise TimetableAmbiguity(f"Unexpected current-service route universe: {sorted(report_routes)}")

    all_trips: list[dict] = []
    all_stop_times: list[dict] = []
    all_stops: list[dict] = []
    source_rows: list[dict] = []
    for route in route_reports:
        route_id = str(route["route_id"])
        payload = fetch_bytes(str(route["url"]))
        trips, stop_times, stops = reconstruct_route(route, payload, service_date=REFERENCE_DATE)
        all_trips.extend(trips)
        all_stop_times.extend(stop_times)
        all_stops.extend(stops)
        source_rows.append({
            "route_id": route_id,
            "publisher": "Lecco Trasporti / Arriva Italia",
            "source_url": route["url"],
            "source_pdf_sha256": route["download_sha256"],
            "valid_from": route["valid_from"],
            "valid_to": route["valid_to"],
            "reference_date": REFERENCE_DATE.isoformat(),
            "scheduled_columns": route["scheduled_columns_total"],
            "active_columns": route["active_timetable_columns"],
            "epistemic_status": "FACT_PRIMARY_SOURCE_WITH_RECONSTRUCTED_STOP_TIMETABLE",
        })

    validate_against_gate_c(route_reports, all_trips)
    gtfs_audit = audit_historical_gtfs(gtfs_dir, audit_date=date(2026, 5, 6))
    for route_id, expected in EXPECTED_GATE_C.items():
        observed = gtfs_audit[route_id]
        expected_tuple = (expected["gtfs_trips"], expected["gtfs_active"], expected["patterns"])
        observed_tuple = (
            observed["snapshot_trips"],
            observed["active_trips_on_2026_05_06"],
            observed["stop_patterns"],
        )
        if observed_tuple != expected_tuple:
            raise TimetableAmbiguity(
                f"{route_id}: historical official GTFS cross-check differs from Gate C: "
                f"{observed_tuple} != {expected_tuple}"
            )

    conditions = build_conditions(route_reports)
    all_trips.sort(key=lambda r: (r["route_id"], int(r["source_page"]), int(r["source_column"])))
    all_stop_times.sort(key=lambda r: (r["route_id"], r["trip_id"], int(r["trip_stop_sequence"])))
    all_stops.sort(key=lambda r: (r["route_id"], int(r["source_page"]), int(r["stop_sequence_on_page"])))

    write_csv(out / "current_service_sources_2026-09-03.csv", source_rows)
    write_csv(out / "current_service_trips_2026-09-03.csv", all_trips)
    write_csv(out / "current_service_stop_times_2026-09-03.csv", all_stop_times)
    write_csv(out / "current_service_pdf_stop_rows_2026-09-03.csv", all_stops)
    write_csv(out / "current_service_temporary_conditions_2026-09-03.csv", conditions)

    active_trips = [r for r in all_trips if bool(r["active_on_reference_date"])]
    active_stop_times = [r for r in all_stop_times if bool(r["active_on_reference_date"])]
    validation = {
        "status": "PASS",
        "reference_date": REFERENCE_DATE.isoformat(),
        "scope": "STOP_LEVEL_AND_TRIP_LEVEL_CURRENT_SERVICE_REFERENCE",
        "gate_c_commit": GATE_C_COMMIT,
        "gate_c_report_sha256": gate_c_report_sha,
        "source_class": "OFFICIAL_OPERATOR_PRIMARY_TIMETABLE_PDFS",
        "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
        "route_ids": list(REQUIRED_ROUTES),
        "scheduled_trip_columns_total": len(all_trips),
        "active_trip_columns_on_reference_date": len(active_trips),
        "stop_time_rows_total": len(all_stop_times),
        "active_stop_time_rows_on_reference_date": len(active_stop_times),
        "pdf_stop_rows_total": len(all_stops),
        "temporary_conditions_count": len(conditions),
        "historical_gtfs_crosscheck_date": "2026-05-06",
        "historical_gtfs_crosscheck": gtfs_audit,
        "calendar_semantics": {
            "validity": "FROM_OFFICIAL_TIMETABLE_PDF",
            "day_codes": "FROM_COLUMN_HEADER_COORDINATES",
            "note_codes": "FROM_COLUMN_NOTE_COORDINATES",
            "reference_date_activation": "DERIVED_FROM_PUBLISHED_DAY_AND_NOTE_RULES",
            "annual_service_days": "NOT_INFERRED",
        },
        "runtime_semantics": {
            "published_stop_times": "OFFICIAL_SCHEDULED_TIMES",
            "scheduled_runtime": "DERIVED_DIFFERENCE_OF_PUBLISHED_STOP_TIMES",
            "observed_runtime": "NOT_AVAILABLE_FROM_THIS_SOURCE",
            "observed_runtime_substitution": False,
        },
        "temporary_service_semantics": {
            "D185_reference_date_context": "TEMPORARY_DEVIATION_CURRENT",
            "ordinary_network_baseline_overwritten": False,
            "brivio_condition": conditions[0],
        },
        "forbidden_inputs": [
            "outputs/current_service_baseline.csv",
            "scripts/05_current_service.py",
            "data/raw/gtfs/network_structural/",
            "data/raw/gtfs/network_2026_emergency/",
        ],
        "not_identified_by_this_workstream": [
            "annual_bus_km",
            "passenger_demand",
            "observed_runtime",
            "unpublished_frequency",
            "unpublished_headway",
        ],
        "gjt_readiness": {
            "scheduled_in_vehicle_time_between_published_timed_stops": True,
            "scheduled_wait_from_explicit_active_trip_departures": True,
            "stop_sequence": True,
            "route_and_trip_identity": True,
            "walking_access_join": "REQUIRES_SEPARATE_STOP_IDENTITY_OR_SPATIAL_JOIN_WHERE_PDF_LABEL_IS_NOT_UNIQUE",
            "reliability_observed_runtime": "NOT_AVAILABLE",
        },
        "legacy_current_service_files_used": False,
    }
    (out / "current_service_stop_timetable_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Current-service stop timetable reconstructed from official primary PDFs")
    print("scheduled columns:", len(all_trips), "active:", len(active_trips))
    print("stop-time rows:", len(all_stop_times), "active:", len(active_stop_times))
    for route_id in REQUIRED_ROUTES:
        rows = [r for r in all_trips if r["route_id"] == route_id]
        print(route_id, "scheduled=", len(rows), "active=", sum(bool(r["active_on_reference_date"]) for r in rows))


if __name__ == "__main__":
    main()
