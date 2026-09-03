"""Gate C transit-integrity primitives.

Only official GTFS snapshots are admissible inputs here. The historical
``network_structural`` and ``network_2026_emergency`` folders are deliberately
not referenced because they are project reconstructions, not source evidence.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

CORE_BUS_ROUTES = ("D184", "D185", "D150", "D170")
OFFICIAL_ARRIVA = Path("data/raw/gtfs/agency_arriva")
OFFICIAL_LINEELECCO = Path("data/raw/gtfs/agency_lineelecco")
OFFICIAL_TRENORD = Path("data/raw/gtfs/rail_trenord")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def feed_declared_range(feed_dir: Path) -> tuple[date | None, date | None]:
    """Return GTFS feed_info declared range, if both fields are present."""
    rows = _rows(feed_dir / "feed_info.txt")
    if not rows:
        return None, None
    row = rows[0]
    start, end = row.get("feed_start_date", ""), row.get("feed_end_date", "")
    return (
        _parse_yyyymmdd(start) if start else None,
        _parse_yyyymmdd(end) if end else None,
    )


def active_service_ids(feed_dir: Path, service_date: date) -> set[str]:
    """Resolve active services using the GTFS calendar + calendar_dates rules.

    This intentionally does not infer dates from service_id strings. A feed
    with no calendar information therefore returns an empty set rather than a
    fabricated schedule.
    """
    active: set[str] = set()
    weekday = service_date.strftime("%A").lower()
    for row in _rows(feed_dir / "calendar.txt"):
        if not row.get("service_id"):
            continue
        start = _parse_yyyymmdd(row["start_date"])
        end = _parse_yyyymmdd(row["end_date"])
        if start <= service_date <= end and row.get(weekday, "0") == "1":
            active.add(row["service_id"])

    target = service_date.strftime("%Y%m%d")
    for row in _rows(feed_dir / "calendar_dates.txt"):
        if row.get("date") != target:
            continue
        sid = row.get("service_id", "")
        if row.get("exception_type") == "1":
            active.add(sid)
        elif row.get("exception_type") == "2":
            active.discard(sid)
    return active


def route_operator_map(feed_dir: Path) -> dict[str, dict[str, str]]:
    agencies = {r["agency_id"]: r for r in _rows(feed_dir / "agency.txt")}
    out: dict[str, dict[str, str]] = {}
    for route in _rows(feed_dir / "routes.txt"):
        agency = agencies.get(route.get("agency_id", ""), {})
        out[route["route_id"]] = {
            "route_short_name": route.get("route_short_name", ""),
            "route_long_name": route.get("route_long_name", ""),
            "agency_id": route.get("agency_id", ""),
            "agency_name": agency.get("agency_name", "UNRESOLVED"),
        }
    return out


def _trip_stop_sequences(feed_dir: Path, trip_ids: set[str]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in _rows(feed_dir / "stop_times.txt"):
        tid = row.get("trip_id", "")
        if tid not in trip_ids:
            continue
        try:
            seq = int(float(row.get("stop_sequence", "0")))
        except ValueError:
            seq = 0
        grouped[tid].append((seq, row.get("stop_id", "")))
    return {
        tid: tuple(stop for _, stop in sorted(vals))
        for tid, vals in grouped.items()
    }


def bus_route_audit(feed_dir: Path, service_date: date) -> list[dict[str, object]]:
    """Audit the four core routes directly from an official bus GTFS feed."""
    route_meta = route_operator_map(feed_dir)
    active_services = active_service_ids(feed_dir, service_date)
    trips = _rows(feed_dir / "trips.txt")
    results: list[dict[str, object]] = []
    for route_id in CORE_BUS_ROUTES:
        route_trips = [r for r in trips if r.get("route_id") == route_id]
        active_trips = [r for r in route_trips if r.get("service_id") in active_services]
        ids = {r["trip_id"] for r in active_trips}
        patterns = Counter(_trip_stop_sequences(feed_dir, ids).values())
        meta = route_meta.get(route_id, {})
        results.append({
            "route_id": route_id,
            "route_present": route_id in route_meta,
            "agency_id": meta.get("agency_id", "UNRESOLVED"),
            "agency_name": meta.get("agency_name", "UNRESOLVED"),
            "route_long_name": meta.get("route_long_name", ""),
            "all_snapshot_trips": len(route_trips),
            "active_trips": len(active_trips),
            "active_patterns": len(patterns),
            "active_pattern_trip_counts": sorted(patterns.values(), reverse=True),
            "epistemic_status": "DERIVED_FROM_OFFICIAL_GTFS",
        })
    return results


def _normalise(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


def find_olgiate_rail_stop(feed_dir: Path) -> dict[str, str]:
    """Resolve the official Trenord stop named Olgiate-Calco-Brivio.

    The railway station's official GTFS name omits ``Molgora``. Requiring that
    municipality name would incorrectly reject the actual source record.
    """
    candidates = []
    for row in _rows(feed_dir / "stops.txt"):
        tokens = set(_normalise(row.get("stop_name", "")).split())
        if {"OLGIATE", "CALCO", "BRIVIO"}.issubset(tokens):
            candidates.append(row)
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one Olgiate-Calco-Brivio rail stop, found {len(candidates)}"
        )
    return candidates[0]


def rail_has_standard_service_calendar(feed_dir: Path) -> bool:
    return bool(_rows(feed_dir / "calendar.txt") or _rows(feed_dir / "calendar_dates.txt"))


def s8_station_events(feed_dir: Path) -> dict[str, object]:
    """Extract S8 events at Olgiate from official Trenord GTFS tables.

    Because the repository snapshot lacks GTFS calendar/calendar_dates files,
    events are reported with their source service_id but are *not* declared
    active on any requested civil date.
    """
    stop = find_olgiate_rail_stop(feed_dir)
    s8_trips = {
        r["trip_id"]: r
        for r in _rows(feed_dir / "trips.txt")
        if r.get("route_id") == "S8"
    }
    events = []
    for row in _rows(feed_dir / "stop_times.txt"):
        tid = row.get("trip_id", "")
        if tid in s8_trips and row.get("stop_id") == stop.get("stop_id"):
            trip = s8_trips[tid]
            events.append({
                "trip_id": tid,
                "service_id": trip.get("service_id", ""),
                "trip_short_name": trip.get("trip_short_name", ""),
                "arrival_time": row.get("arrival_time", ""),
                "departure_time": row.get("departure_time", ""),
                "stop_id": stop.get("stop_id", ""),
                "stop_name": stop.get("stop_name", ""),
            })
    events.sort(key=lambda r: (r["departure_time"], r["trip_id"]))
    has_calendar = rail_has_standard_service_calendar(feed_dir)
    return {
        "route_id": "S8",
        "stop_id": stop.get("stop_id", ""),
        "stop_name": stop.get("stop_name", ""),
        "events": events,
        "events_count": len(events),
        "standard_service_calendar_present": has_calendar,
        "service_date_status": (
            "RESOLVABLE_FROM_GTFS_CALENDAR"
            if has_calendar
            else "PROVISIONAL_SERVICE_DATE_UNRESOLVED"
        ),
        "epistemic_status": "DERIVED_FROM_OFFICIAL_GTFS",
    }


def official_table_hashes(feed_dir: Path, names: Iterable[str]) -> dict[str, str]:
    out = {}
    for name in names:
        path = feed_dir / name
        if path.exists():
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def build_gate_c_report(service_date: date) -> dict[str, object]:
    bus_start, bus_end = feed_declared_range(OFFICIAL_ARRIVA)
    bus = bus_route_audit(OFFICIAL_ARRIVA, service_date)
    rail = s8_station_events(OFFICIAL_TRENORD)
    return {
        "gate": "C",
        "service_date_requested": service_date.isoformat(),
        "bus_feed": {
            "source": str(OFFICIAL_ARRIVA),
            "declared_start": bus_start.isoformat() if bus_start else None,
            "declared_end": bus_end.isoformat() if bus_end else None,
            "date_within_declared_feed_range": bool(
                bus_start and bus_end and bus_start <= service_date <= bus_end
            ),
            "routes": bus,
            "epistemic_status": "FACT_SNAPSHOT_AND_DERIVED_METRICS",
        },
        "rail_feed": rail,
        "invalidated_reconstructions": [
            "data/raw/gtfs/network_structural",
            "data/raw/gtfs/network_2026_emergency",
            "scripts/02_parse_gtfs.py",
            "src/gtfs_loader.py",
            "scripts/05_current_service.py transit metrics",
            "src/timetable_engine.py hard-coded S8 cadence",
            "scripts/11_train_coordination.py hard-coded node timetable",
        ],
    }


def write_report(path: Path, service_date: date) -> dict[str, object]:
    report = build_gate_c_report(service_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
