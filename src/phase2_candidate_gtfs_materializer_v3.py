from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable


REQUIRED_GTFS_FILES = (
    "agency.txt",
    "calendar.txt",
    "routes.txt",
    "stop_times.txt",
    "stops.txt",
    "trips.txt",
)


@dataclass(frozen=True)
class AgencyDefinition:
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str


@dataclass(frozen=True)
class BoardingPoint:
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


@dataclass(frozen=True)
class RouteDefinition:
    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int


@dataclass(frozen=True)
class StopCall:
    stop_id: str
    stop_sequence: int
    cumulative_time_sec: int


@dataclass(frozen=True)
class ServicePattern:
    pattern_id: str
    route_id: str
    service_id: str
    direction_id: int
    stop_calls: tuple[StopCall, ...]
    departures_sec: tuple[int, ...]


@dataclass(frozen=True)
class ServiceCalendar:
    service_id: str
    monday: int
    tuesday: int
    wednesday: int
    thursday: int
    friday: int
    saturday: int
    sunday: int
    start_date: str
    end_date: str


@dataclass(frozen=True)
class CandidateGTFS:
    files: tuple[tuple[str, bytes], ...]
    zip_bytes: bytes
    zip_sha256: str

    def file_bytes(self, filename: str) -> bytes:
        mapping = dict(self.files)
        try:
            return mapping[filename]
        except KeyError as exc:
            raise KeyError(f"GTFS file not present: {filename}") from exc


def _nonempty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _unique_by_id(rows: Iterable[object], attr: str, label: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for row in rows:
        value = _nonempty(getattr(row, attr), f"{label} {attr}")
        if value in result:
            raise ValueError(f"duplicate {label} identity: {value}")
        result[value] = row
    if not result:
        raise ValueError(f"{label} collection must not be empty")
    return result


def _validate_agency(agency: AgencyDefinition) -> None:
    _nonempty(agency.agency_id, "agency_id")
    _nonempty(agency.agency_name, "agency_name")
    url = _nonempty(agency.agency_url, "agency_url")
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError("agency_url must be an absolute HTTP(S) URL")
    _nonempty(agency.agency_timezone, "agency_timezone")


def _validate_boarding_points(stops: dict[str, BoardingPoint]) -> None:
    for stop_id, stop in stops.items():
        _nonempty(stop.stop_name, f"stop_name for {stop_id}")
        lat = float(stop.stop_lat)
        lon = float(stop.stop_lon)
        if not isfinite(lat) or not -90.0 <= lat <= 90.0:
            raise ValueError(f"invalid latitude for stop {stop_id}")
        if not isfinite(lon) or not -180.0 <= lon <= 180.0:
            raise ValueError(f"invalid longitude for stop {stop_id}")


def _validate_routes(routes: dict[str, RouteDefinition]) -> None:
    for route_id, route in routes.items():
        if not route.route_short_name.strip() and not route.route_long_name.strip():
            raise ValueError(f"route {route_id} requires short name or long name")
        if isinstance(route.route_type, bool) or not isinstance(route.route_type, int) or route.route_type < 0:
            raise ValueError(f"invalid route_type for route {route_id}")


def _parse_date(value: str, label: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y%m%d")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must use YYYYMMDD") from exc
    if parsed.strftime("%Y%m%d") != value:
        raise ValueError(f"{label} must use YYYYMMDD")
    return parsed


def _validate_calendars(calendars: dict[str, ServiceCalendar]) -> None:
    weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    for service_id, cal in calendars.items():
        for field in weekdays:
            if getattr(cal, field) not in (0, 1):
                raise ValueError(f"invalid weekday flag {field} for service {service_id}")
        if not any(getattr(cal, field) == 1 for field in weekdays):
            raise ValueError(f"service {service_id} has no active weekday")
        start = _parse_date(cal.start_date, f"start_date for {service_id}")
        end = _parse_date(cal.end_date, f"end_date for {service_id}")
        if start > end:
            raise ValueError(f"service {service_id} starts after it ends")


def _trip_id(pattern_id: str, departure_sec: int) -> str:
    return f"{pattern_id}__T{departure_sec:07d}"


def _validate_patterns(patterns, *, stops, routes, calendars) -> None:
    trip_ids: set[str] = set()
    for pattern_id, pattern in patterns.items():
        if pattern.route_id not in routes:
            raise ValueError(f"pattern {pattern_id} references missing route {pattern.route_id}")
        if pattern.service_id not in calendars:
            raise ValueError(f"pattern {pattern_id} references missing service {pattern.service_id}")
        if pattern.direction_id not in (0, 1):
            raise ValueError(f"invalid direction_id for pattern {pattern_id}")
        calls = tuple(pattern.stop_calls)
        if len(calls) < 2:
            raise ValueError(f"pattern {pattern_id} requires at least two stop calls")
        if [c.stop_sequence for c in calls] != list(range(1, len(calls) + 1)):
            raise ValueError(f"pattern {pattern_id} stop_sequence must be contiguous from 1")
        offsets: list[int] = []
        for call in calls:
            if call.stop_id not in stops:
                raise ValueError(f"pattern {pattern_id} references missing stop {call.stop_id}")
            if isinstance(call.cumulative_time_sec, bool) or not isinstance(call.cumulative_time_sec, int):
                raise ValueError(f"pattern {pattern_id} cumulative time must be integer seconds")
            if call.cumulative_time_sec < 0:
                raise ValueError(f"pattern {pattern_id} cumulative time must be non-negative")
            offsets.append(call.cumulative_time_sec)
        if offsets[0] != 0:
            raise ValueError(f"pattern {pattern_id} first cumulative time must be zero")
        if any(b < a for a, b in zip(offsets, offsets[1:])):
            raise ValueError(f"pattern {pattern_id} cumulative time decreases")
        departures = tuple(pattern.departures_sec)
        if not departures:
            raise ValueError(f"pattern {pattern_id} requires at least one explicit departure")
        if len(set(departures)) != len(departures):
            raise ValueError(f"pattern {pattern_id} has duplicate departure times")
        for departure in departures:
            if isinstance(departure, bool) or not isinstance(departure, int) or departure < 0:
                raise ValueError(f"pattern {pattern_id} departure must be non-negative integer seconds")
            trip_id = _trip_id(pattern_id, departure)
            if trip_id in trip_ids:
                raise ValueError(f"duplicate generated trip identity: {trip_id}")
            trip_ids.add(trip_id)


def format_gtfs_time(total_seconds: int) -> str:
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, int) or total_seconds < 0:
        raise ValueError("GTFS time must be non-negative integer seconds")
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _csv_bytes(fieldnames: tuple[str, ...], rows: Iterable[dict[str, object]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def _deterministic_zip(files: tuple[tuple[str, bytes], ...]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for filename, content in sorted(files):
            info = zipfile.ZipInfo(filename=filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return out.getvalue()


def build_candidate_gtfs(*, agency, boarding_points, routes, patterns, calendars) -> CandidateGTFS:
    _validate_agency(agency)
    stop_map = _unique_by_id(boarding_points, "stop_id", "stop")
    route_map = _unique_by_id(routes, "route_id", "route")
    pattern_map = _unique_by_id(patterns, "pattern_id", "pattern")
    calendar_map = _unique_by_id(calendars, "service_id", "service")
    _validate_boarding_points(stop_map)
    _validate_routes(route_map)
    _validate_calendars(calendar_map)
    _validate_patterns(pattern_map, stops=stop_map, routes=route_map, calendars=calendar_map)

    agency_bytes = _csv_bytes(("agency_id", "agency_name", "agency_url", "agency_timezone"), [{
        "agency_id": agency.agency_id.strip(), "agency_name": agency.agency_name.strip(),
        "agency_url": agency.agency_url.strip(), "agency_timezone": agency.agency_timezone.strip(),
    }])
    stops_bytes = _csv_bytes(("stop_id", "stop_name", "stop_lat", "stop_lon"), (
        {"stop_id": sid, "stop_name": s.stop_name.strip(), "stop_lat": format(float(s.stop_lat), ".8f"), "stop_lon": format(float(s.stop_lon), ".8f")}
        for sid, s in sorted(stop_map.items())
    ))
    routes_bytes = _csv_bytes(("route_id", "agency_id", "route_short_name", "route_long_name", "route_type"), (
        {"route_id": rid, "agency_id": agency.agency_id.strip(), "route_short_name": r.route_short_name.strip(), "route_long_name": r.route_long_name.strip(), "route_type": r.route_type}
        for rid, r in sorted(route_map.items())
    ))
    calendar_bytes = _csv_bytes(("service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"), (
        {"service_id": sid, "monday": c.monday, "tuesday": c.tuesday, "wednesday": c.wednesday, "thursday": c.thursday, "friday": c.friday, "saturday": c.saturday, "sunday": c.sunday, "start_date": c.start_date, "end_date": c.end_date}
        for sid, c in sorted(calendar_map.items())
    ))

    trip_rows: list[dict[str, object]] = []
    stop_time_rows: list[dict[str, object]] = []
    for pattern_id, pattern in sorted(pattern_map.items()):
        for departure in sorted(pattern.departures_sec):
            trip_id = _trip_id(pattern_id, departure)
            trip_rows.append({"route_id": pattern.route_id, "service_id": pattern.service_id, "trip_id": trip_id, "direction_id": pattern.direction_id})
            for call in pattern.stop_calls:
                timestamp = format_gtfs_time(departure + call.cumulative_time_sec)
                stop_time_rows.append({"trip_id": trip_id, "arrival_time": timestamp, "departure_time": timestamp, "stop_id": call.stop_id, "stop_sequence": call.stop_sequence})

    trips_bytes = _csv_bytes(("route_id", "service_id", "trip_id", "direction_id"), sorted(trip_rows, key=lambda r: str(r["trip_id"])))
    stop_times_bytes = _csv_bytes(("trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"), sorted(stop_time_rows, key=lambda r: (str(r["trip_id"]), int(r["stop_sequence"]))))
    files = tuple(sorted((
        ("agency.txt", agency_bytes), ("calendar.txt", calendar_bytes), ("routes.txt", routes_bytes),
        ("stop_times.txt", stop_times_bytes), ("stops.txt", stops_bytes), ("trips.txt", trips_bytes),
    )))
    if tuple(name for name, _ in files) != REQUIRED_GTFS_FILES:
        raise AssertionError("internal GTFS file-set error")
    zip_bytes = _deterministic_zip(files)
    return CandidateGTFS(files=files, zip_bytes=zip_bytes, zip_sha256=hashlib.sha256(zip_bytes).hexdigest())
