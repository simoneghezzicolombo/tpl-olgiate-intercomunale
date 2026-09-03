#!/usr/bin/env python3
"""Fetch and audit the current official Regione Lombardia / Trenord GTFS.

This script deliberately keeps the live feed outside data/raw so a moving
upstream dataset is never confused with a frozen repository snapshot. The
output records the downloaded ZIP checksum and derives S8 service for one
civil date from GTFS calendar/calendar_dates semantics.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.transit_integrity import active_service_ids, find_olgiate_rail_stop

SOURCE_URL = "https://www.dati.lombardia.it/download/3z4k-mxz9/application/zip"
DATASET_URL = (
    "https://www.dati.lombardia.it/Mobilit-e-trasporti/"
    "Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9"
)
REQUIRED_TABLES = {"agency.txt", "routes.txt", "trips.txt", "stop_times.txt", "stops.txt"}


def _rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def _download(url: str, destination: Path) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "gate-c-transit-audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
        digest = hashlib.sha256()
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def _service_span(feed_dir: Path) -> tuple[str | None, str | None]:
    dates: list[date] = []
    calendar_dates = feed_dir / "calendar_dates.txt"
    if calendar_dates.exists():
        for row in _rows(calendar_dates):
            raw = row.get("date", "")
            if len(raw) == 8 and raw.isdigit():
                dates.append(datetime.strptime(raw, "%Y%m%d").date())
    calendar = feed_dir / "calendar.txt"
    if calendar.exists():
        for row in _rows(calendar):
            for field in ("start_date", "end_date"):
                raw = row.get(field, "")
                if len(raw) == 8 and raw.isdigit():
                    dates.append(datetime.strptime(raw, "%Y%m%d").date())
    if not dates:
        return None, None
    return min(dates).isoformat(), max(dates).isoformat()


def build_live_report(service_date: date) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="gate-c-trenord-") as tmp:
        root = Path(tmp)
        archive = root / "trenord_gtfs.zip"
        sha256 = _download(SOURCE_URL, archive)
        if not zipfile.is_zipfile(archive):
            raise RuntimeError("Regione Lombardia response is not a valid ZIP archive")

        feed_dir = root / "feed"
        feed_dir.mkdir()
        with zipfile.ZipFile(archive) as zf:
            names = {Path(name).name for name in zf.namelist() if not name.endswith("/")}
            missing = REQUIRED_TABLES - names
            if missing:
                raise RuntimeError(f"Official GTFS missing required tables: {sorted(missing)}")
            if not ({"calendar.txt", "calendar_dates.txt"} & names):
                raise RuntimeError("Official current GTFS has no GTFS service calendar table")
            zf.extractall(feed_dir)

        # Some archives may wrap files in one directory. Resolve the directory
        # that actually contains routes.txt rather than assuming ZIP layout.
        candidates = [p.parent for p in feed_dir.rglob("routes.txt")]
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one GTFS root, found {len(candidates)}")
        gtfs = candidates[0]

        active_services = active_service_ids(gtfs, service_date)
        if not active_services:
            raise RuntimeError(
                f"Current official feed has no active services on {service_date.isoformat()}"
            )

        stop = find_olgiate_rail_stop(gtfs)
        route_ids = {
            row.get("route_id", "")
            for row in _rows(gtfs / "routes.txt")
            if row.get("route_short_name", "") == "S8" or row.get("route_id", "") == "S8"
        }
        if not route_ids:
            raise RuntimeError("S8 is not present in current official Trenord GTFS")

        trips = {
            row["trip_id"]: row
            for row in _rows(gtfs / "trips.txt")
            if row.get("route_id") in route_ids and row.get("service_id") in active_services
        }
        events = []
        for row in _rows(gtfs / "stop_times.txt"):
            trip_id = row.get("trip_id", "")
            if trip_id not in trips or row.get("stop_id") != stop.get("stop_id"):
                continue
            trip = trips[trip_id]
            events.append(
                {
                    "trip_id": trip_id,
                    "service_id": trip.get("service_id", ""),
                    "trip_short_name": trip.get("trip_short_name", ""),
                    "arrival_time": row.get("arrival_time", ""),
                    "departure_time": row.get("departure_time", ""),
                }
            )
        events.sort(key=lambda row: (row["departure_time"], row["trip_id"]))
        if not events:
            raise RuntimeError(
                f"No active S8 events found at {stop.get('stop_name')} on {service_date.isoformat()}"
            )

        span_start, span_end = _service_span(gtfs)
        return {
            "gate": "C",
            "source_type": "LIVE_OFFICIAL_GTFS",
            "dataset_url": DATASET_URL,
            "download_url": SOURCE_URL,
            "download_sha256": sha256,
            "service_date": service_date.isoformat(),
            "feed_service_span": {"start": span_start, "end": span_end},
            "active_service_ids_count": len(active_services),
            "route_ids_resolved_for_s8": sorted(route_ids),
            "station": {
                "stop_id": stop.get("stop_id", ""),
                "stop_name": stop.get("stop_name", ""),
            },
            "active_s8_trips_count": len(trips),
            "active_s8_station_events_count": len(events),
            "events": events,
            "epistemic_status": "DERIVED_FROM_LIVE_OFFICIAL_GTFS",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-date", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    service_date = date.fromisoformat(args.service_date)
    report = build_live_report(service_date)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Current Trenord GTFS:",
        report["feed_service_span"],
        "S8 trips=", report["active_s8_trips_count"],
        "Olgiate events=", report["active_s8_station_events_count"],
        "sha256=", report["download_sha256"],
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
