"""Topology-neutral current-service stop timetable reconstruction.

Production evidence comes only from pinned Gate C official operator PDFs and the
stored official Agency/Arriva GTFS. PDF timetable columns are reconstructed
records, never promoted to GTFS trips. Legacy hard-coded current-service files
are deliberately outside this module.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
from typing import Iterable

import pdfplumber

GATE_C_COMMIT = "dcc3e75ae3b4f4ea5170f48e85345b83620c5536"
GATE_C_REPORT_PATH = "outputs/gate_c/live_bus_timetables_2026-09-03.json"
GATE_C_REPORT_URL = (
    "https://raw.githubusercontent.com/simoneghezzicolombo/"
    "tpl-olgiate-intercomunale/"
    f"{GATE_C_COMMIT}/{GATE_C_REPORT_PATH}"
)
REFERENCE_DATE = date(2026, 9, 3)
REQUIRED_ROUTES = ("D184", "D185", "D150", "D170")
EXPECTED_GATE_C = {
    "D184": {"scheduled": 12, "active": 12, "gtfs_trips": 15, "gtfs_active": 15, "patterns": 8},
    "D185": {"scheduled": 13, "active": 13, "gtfs_trips": 27, "gtfs_active": 19, "patterns": 9},
    "D150": {"scheduled": 39, "active": 30, "gtfs_trips": 41, "gtfs_active": 33, "patterns": 28},
    "D170": {"scheduled": 55, "active": 49, "gtfs_trips": 118, "gtfs_active": 96, "patterns": 49},
}
TIME_RE = re.compile(r"^(\d{1,2})[:.](\d{2})$")
DAY_CODES = {"123456", "12345", "6"}
NOTE_CODES = {"A", "B", "D", "V", "BV"}


class TimetableAmbiguity(RuntimeError):
    """Raised whenever the source cannot be mapped unambiguously."""


@dataclass(frozen=True)
class PdfColumn:
    page: int
    column: int
    x: float
    day_code: str
    note_code: str | None
    active_on_reference_date: bool


@dataclass(frozen=True)
class StopRow:
    page: int
    row_index: int
    stop_label: str
    top: float
    values: tuple[str | None, ...]


def fetch_bytes(url: str, *, user_agent: str = "phase2-current-service-stop-timetable/1.0") -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    return payload


def fetch_gate_c_report() -> tuple[dict, str]:
    payload = fetch_bytes(GATE_C_REPORT_URL)
    digest = hashlib.sha256(payload).hexdigest()
    report = json.loads(payload.decode("utf-8"))
    if report.get("gate") != "C" or report.get("service_date") != REFERENCE_DATE.isoformat():
        raise TimetableAmbiguity("Pinned Gate C report identity/date mismatch")
    if report.get("source_class") != "OFFICIAL_OPERATOR_PRIMARY_TIMETABLE_PDFS":
        raise TimetableAmbiguity("Pinned Gate C report has unexpected source class")
    return report, digest


def _normalise_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalise_upper(value: str) -> str:
    return _normalise_space(value).upper()


def _cluster_by_top(words: Iterable[dict], *, tolerance: float = 2.5) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    for word in sorted(words, key=lambda w: float(w["top"])):
        top = float(word["top"])
        for cluster in clusters:
            centre = sum(float(x["top"]) for x in cluster) / len(cluster)
            if abs(top - centre) <= tolerance:
                cluster.append(word)
                break
        else:
            clusters.append([word])
    return clusters


def _header_columns(words: list[dict], service_date: date) -> tuple[list[PdfColumn], float]:
    day_words = [w for w in words if str(w["text"]).strip() in DAY_CODES]
    clusters = _cluster_by_top(day_words)
    if not clusters:
        raise TimetableAmbiguity("No day-code row found")
    day_row = max(clusters, key=len)
    if len(day_row) < 2:
        raise TimetableAmbiguity("Day-code row cannot be distinguished from legend")
    day_row.sort(key=lambda w: float(w["x0"]))
    day_top = sum(float(w["top"]) for w in day_row) / len(day_row)

    xs = [float(w["x0"]) for w in day_row]
    positive_spacings = [b - a for a, b in zip(xs, xs[1:]) if b > a]
    if not positive_spacings:
        raise TimetableAmbiguity("Timetable columns have no horizontal separation")
    tolerance = min(positive_spacings) * 0.62

    note_words = [w for w in words if str(w["text"]).strip().upper() in NOTE_CODES]
    note_clusters = []
    for cluster in _cluster_by_top(note_words):
        top = sum(float(w["top"]) for w in cluster) / len(cluster)
        distance = abs(top - day_top)
        if 1.0 < distance <= 30.0:
            note_clusters.append((distance, cluster))
    notes: list[str | None] = [None] * len(day_row)
    if note_clusters:
        note_row = min(note_clusters, key=lambda item: item[0])[1]
        for note in note_row:
            distances = [abs(float(note["x0"]) - x) for x in xs]
            idx = min(range(len(distances)), key=distances.__getitem__)
            if distances[idx] > tolerance:
                raise TimetableAmbiguity(f"Unmapped note code {note['text']}")
            code = str(note["text"]).strip().upper()
            if notes[idx] is not None:
                # Some PDFs concatenate two single-letter notes in the same cell.
                combined = notes[idx] + code
                if combined not in {"BV", "VB"}:
                    raise TimetableAmbiguity(f"Multiple note codes on column {idx + 1}")
                notes[idx] = "BV"
            else:
                notes[idx] = code

    weekday_code = str(service_date.weekday() + 1)
    within_exception = date(2026, 7, 27) <= service_date <= date(2026, 8, 30)
    holiday = (service_date.month, service_date.day) in {(1, 1), (8, 15), (12, 25)}
    output: list[PdfColumn] = []
    for idx, (word, note) in enumerate(zip(day_row, notes), start=1):
        day_code = str(word["text"]).strip()
        active = weekday_code in day_code and not holiday
        if note == "A":
            active = active and not within_exception
        elif note in {"B", "BV"}:
            active = active and within_exception
        elif note == "D" and within_exception and service_date.weekday() == 5:
            active = False
        output.append(PdfColumn(0, idx, float(word["x0"]), day_code, note, active))
    return output, day_top


def _legend_top(words: list[dict], day_top: float) -> float:
    candidates = [
        float(w["top"])
        for w in words
        if float(w["top"]) > day_top and str(w["text"]).strip().upper().startswith("SIMBOLOGIA")
    ]
    if not candidates:
        raise TimetableAmbiguity("Timetable legend boundary not found")
    return min(candidates)


def _parse_clock(token: str) -> str | None:
    match = TIME_RE.fullmatch(token.strip())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 29 and 0 <= minute <= 59):
        raise TimetableAmbiguity(f"Invalid published clock token {token!r}")
    return f"{hour:02d}:{minute:02d}"


def service_minutes(clock: str) -> int:
    hour, minute = (int(x) for x in clock.split(":"))
    return hour * 60 + minute


def _row_label(row: list[dict], first_column_x: float) -> str:
    label_words = [
        w for w in row
        if float(w["x1"]) < first_column_x - 3.0
        and _parse_clock(str(w["text"])) is None
        and str(w["text"]).strip() != "|"
    ]
    label_words.sort(key=lambda w: float(w["x0"]))
    return _normalise_space(" ".join(str(w["text"]) for w in label_words))


def _parse_stop_rows(words: list[dict], columns: list[PdfColumn], day_top: float, page_number: int) -> list[StopRow]:
    bottom = _legend_top(words, day_top)
    xs = [c.x for c in columns]
    spacings = [b - a for a, b in zip(xs, xs[1:]) if b > a]
    tolerance = min(spacings) * 0.45 if spacings else 12.0
    candidate_words = [w for w in words if day_top + 8.0 < float(w["top"]) < bottom - 2.0]
    rows = _cluster_by_top(candidate_words, tolerance=2.2)
    parsed: list[StopRow] = []
    for row in rows:
        row.sort(key=lambda w: float(w["x0"]))
        has_cell_marker = any(_parse_clock(str(w["text"])) is not None or str(w["text"]).strip() == "|" for w in row)
        if not has_cell_marker:
            continue
        label = _row_label(row, xs[0])
        if not label:
            continue
        values: list[str | None] = [None] * len(columns)
        for word in row:
            text = str(word["text"]).strip()
            clock = _parse_clock(text)
            if clock is None:
                continue
            x = float(word["x0"])
            distances = [abs(x - col_x) for col_x in xs]
            idx = min(range(len(distances)), key=distances.__getitem__)
            if distances[idx] > tolerance:
                raise TimetableAmbiguity(
                    f"Page {page_number}: time {text} on {label!r} does not align to a timetable column"
                )
            if values[idx] is not None:
                raise TimetableAmbiguity(
                    f"Page {page_number}: multiple times map to column {idx + 1} on {label!r}"
                )
            values[idx] = clock
        parsed.append(StopRow(page_number, len(parsed) + 1, label, sum(float(w["top"]) for w in row) / len(row), tuple(values)))
    if len(parsed) < 2:
        raise TimetableAmbiguity(f"Page {page_number}: fewer than two timetable stop rows parsed")
    labels = [r.stop_label for r in parsed]
    if len(labels) != len(set((i, label) for i, label in enumerate(labels))):
        raise TimetableAmbiguity(f"Page {page_number}: invalid stop-row identity")
    return parsed


def _resolve_direction(page_text: str) -> tuple[str, str, str]:
    lines = [_normalise_space(line) for line in page_text.splitlines() if "→" in line]
    lines = [line for line in lines if len(line) <= 140]
    if len(lines) != 1:
        raise TimetableAmbiguity(f"Expected one route direction heading, found {len(lines)}")
    heading = lines[0]
    parts = [_normalise_space(part) for part in heading.split("→") if _normalise_space(part)]
    if len(parts) < 2:
        raise TimetableAmbiguity("Direction heading has fewer than two endpoints")
    return heading, parts[0], parts[-1]


def _unwrap_minutes(clocks: list[str]) -> list[int]:
    output: list[int] = []
    day_offset = 0
    previous: int | None = None
    for clock in clocks:
        raw = service_minutes(clock)
        value = raw + day_offset
        if previous is not None and value < previous:
            if previous - value >= 12 * 60:
                day_offset += 24 * 60
                value = raw + day_offset
            else:
                raise TimetableAmbiguity(f"Published stop times decrease within trip: {clocks}")
        output.append(value)
        previous = value
    return output


def reconstruct_route(route_report: dict, pdf_payload: bytes, *, service_date: date = REFERENCE_DATE) -> tuple[list[dict], list[dict], list[dict]]:
    route_id = str(route_report["route_id"])
    if route_id not in REQUIRED_ROUTES:
        raise TimetableAmbiguity(f"Unexpected route {route_id}")
    digest = hashlib.sha256(pdf_payload).hexdigest()
    if digest != route_report.get("download_sha256"):
        raise TimetableAmbiguity(f"{route_id}: official PDF SHA256 differs from pinned Gate C evidence")
    if not pdf_payload.startswith(b"%PDF"):
        raise TimetableAmbiguity(f"{route_id}: source is not a PDF")

    trips: list[dict] = []
    stop_times: list[dict] = []
    page_stops: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_payload)) as pdf:
        if len(pdf.pages) != len(route_report.get("pages", [])):
            raise TimetableAmbiguity(f"{route_id}: page count differs from Gate C")
        for p_idx, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=False)
            page_text = page.extract_text() or ""
            direction_heading, origin_label, terminal_label = _resolve_direction(page_text)
            columns0, day_top = _header_columns(words, service_date)
            columns = [PdfColumn(p_idx, c.column, c.x, c.day_code, c.note_code, c.active_on_reference_date) for c in columns0]
            gate_page = route_report["pages"][p_idx - 1]
            if len(columns) != gate_page.get("scheduled_columns"):
                raise TimetableAmbiguity(f"{route_id} page {p_idx}: column count differs from Gate C")
            rows = _parse_stop_rows(words, columns, day_top, p_idx)
            for row in rows:
                page_stops.append({
                    "route_id": route_id,
                    "source_page": p_idx,
                    "direction_heading": direction_heading,
                    "direction_origin": origin_label,
                    "direction_terminal": terminal_label,
                    "stop_sequence_on_page": row.row_index,
                    "stop_label_pdf": row.stop_label,
                    "service_context": "TEMPORARY_DEVIATION_CURRENT" if route_id == "D185" else "PUBLISHED_CURRENT_TIMETABLE",
                    "source_url": route_report["url"],
                    "source_pdf_sha256": digest,
                    "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
                })
            for col in columns:
                trip_id = f"PDF20260903:{route_id}:P{p_idx:02d}:C{col.column:02d}"
                timed = [(row, row.values[col.column - 1]) for row in rows if row.values[col.column - 1] is not None]
                if len(timed) < 2:
                    raise TimetableAmbiguity(f"{trip_id}: fewer than two published stop times")
                clocks = [str(clock) for _, clock in timed]
                minutes = _unwrap_minutes(clocks)
                trips.append({
                    "trip_id": trip_id,
                    "route_id": route_id,
                    "source_page": p_idx,
                    "source_column": col.column,
                    "direction_heading": direction_heading,
                    "direction_origin": origin_label,
                    "direction_terminal": terminal_label,
                    "day_code": col.day_code,
                    "note_code": col.note_code or "",
                    "active_on_reference_date": col.active_on_reference_date,
                    "reference_date": service_date.isoformat(),
                    "valid_from": route_report["valid_from"],
                    "valid_to": route_report["valid_to"],
                    "first_published_time": clocks[0],
                    "last_published_time": clocks[-1],
                    "scheduled_runtime_min": minutes[-1] - minutes[0],
                    "published_timed_stops": len(timed),
                    "runtime_semantics": "SCHEDULED_PUBLISHED_TIME_NOT_OBSERVED_RUNTIME",
                    "source_url": route_report["url"],
                    "source_pdf_sha256": digest,
                    "gate_c_commit": GATE_C_COMMIT,
                    "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
                })
                for seq, ((row, clock), minute_value) in enumerate(zip(timed, minutes), start=1):
                    stop_times.append({
                        "trip_id": trip_id,
                        "route_id": route_id,
                        "trip_stop_sequence": seq,
                        "pdf_row_sequence": row.row_index,
                        "stop_label_pdf": row.stop_label,
                        "published_time": clock,
                        "service_minutes": minute_value,
                        "active_on_reference_date": col.active_on_reference_date,
                        "direction_origin": origin_label,
                        "direction_terminal": terminal_label,
                        "source_page": p_idx,
                        "source_column": col.column,
                        "source_url": route_report["url"],
                        "source_pdf_sha256": digest,
                        "runtime_semantics": "SCHEDULED_PUBLISHED_TIME_NOT_OBSERVED_RUNTIME",
                        "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
                    })
    return trips, stop_times, page_stops


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _active_service_ids(calendar_dates: list[dict[str, str]], service_date: date) -> set[str]:
    key = service_date.strftime("%Y%m%d")
    additions = {r["service_id"] for r in calendar_dates if r.get("date") == key and r.get("exception_type") == "1"}
    removals = {r["service_id"] for r in calendar_dates if r.get("date") == key and r.get("exception_type") == "2"}
    return additions - removals


def audit_historical_gtfs(gtfs_dir: Path, *, audit_date: date = date(2026, 5, 6)) -> dict[str, dict[str, int]]:
    routes = _read_csv(gtfs_dir / "routes.txt")
    trips = _read_csv(gtfs_dir / "trips.txt")
    stop_times = _read_csv(gtfs_dir / "stop_times.txt")
    calendar_dates = _read_csv(gtfs_dir / "calendar_dates.txt")
    route_ids = {r["route_id"] for r in routes if r.get("route_short_name") in REQUIRED_ROUTES}
    if route_ids != set(REQUIRED_ROUTES):
        raise TimetableAmbiguity(f"Official GTFS route universe mismatch: {sorted(route_ids)}")
    active_services = _active_service_ids(calendar_dates, audit_date)
    trip_route = {r["trip_id"]: r["route_id"] for r in trips if r["route_id"] in route_ids}
    trip_service = {r["trip_id"]: r["service_id"] for r in trips if r["route_id"] in route_ids}
    seqs: dict[str, list[tuple[int, str]]] = {tid: [] for tid in trip_route}
    for row in stop_times:
        tid = row.get("trip_id", "")
        if tid in seqs:
            seqs[tid].append((int(row["stop_sequence"]), row["stop_id"]))
    output: dict[str, dict[str, int]] = {}
    for route_id in REQUIRED_ROUTES:
        tids = [tid for tid, rid in trip_route.items() if rid == route_id]
        patterns = {tuple(stop for _, stop in sorted(seqs[tid])) for tid in tids}
        output[route_id] = {
            "snapshot_trips": len(tids),
            "active_trips_on_2026_05_06": sum(trip_service[tid] in active_services for tid in tids),
            "stop_patterns": len(patterns),
        }
    return output


def build_conditions(route_reports: list[dict]) -> list[dict]:
    d185 = next((r for r in route_reports if r.get("route_id") == "D185"), None)
    if not d185 or not d185.get("notes_detected", {}).get("brivio_bridge_cantu_deviation"):
        raise TimetableAmbiguity("D185 Brivio temporary-deviation evidence is missing")
    return [{
        "condition_id": "D185_BRIVIO_BRIDGE_PONTE_CANTU_2026",
        "route_id": "D185",
        "condition_type": "TEMPORARY_DEVIATION_AND_STOP_SUSPENSION",
        "valid_from": "2026-05-04",
        "valid_to": "UNKNOWN_FROM_TIMETABLE_SOURCE",
        "reference_date_active": True,
        "routing_effect": "SERVICES_USE_PONTE_CANTU",
        "stop_effect": "CISANO_SOSTA_SUSPENDED",
        "ordinary_network_baseline_replaced": False,
        "source_url": d185["url"],
        "source_pdf_sha256": d185["download_sha256"],
        "epistemic_status": "FACT_TEMPORARY_SERVICE_CONDITION_FROM_PRIMARY_TIMETABLE",
    }]


def validate_against_gate_c(route_reports: list[dict], trips: list[dict]) -> None:
    report_by_route = {r["route_id"]: r for r in route_reports}
    if set(report_by_route) != set(REQUIRED_ROUTES):
        raise TimetableAmbiguity("Gate C route universe mismatch")
    for route_id, expected in EXPECTED_GATE_C.items():
        source = report_by_route[route_id]
        if source.get("scheduled_columns_total") != expected["scheduled"]:
            raise TimetableAmbiguity(f"{route_id}: Gate C scheduled-column regression")
        if source.get("active_timetable_columns") != expected["active"]:
            raise TimetableAmbiguity(f"{route_id}: Gate C active-column regression")
        route_trips = [t for t in trips if t["route_id"] == route_id]
        if len(route_trips) != expected["scheduled"]:
            raise TimetableAmbiguity(f"{route_id}: reconstructed trip count mismatch")
        if sum(bool(t["active_on_reference_date"]) for t in route_trips) != expected["active"]:
            raise TimetableAmbiguity(f"{route_id}: reconstructed active trip count mismatch")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise TimetableAmbiguity(f"Refusing to write empty output {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
