#!/usr/bin/env python3
"""Audit current official Arriva/Lecco Trasporti timetable PDFs.

The operator publishes summer 2026 service as primary timetable PDFs while the
Agency GTFS page still exposes the 2025-2026 snapshot. This audit downloads the
primary PDFs, verifies validity/directions and reconstructs schedule columns
from their actual PDF coordinates. Reconstructed records are never labelled
GTFS.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

from pypdf import PdfReader

SOURCES = {
    "D184": "https://www.leccotrasporti.it/percorsi/estivo/linea-d184.pdf",
    "D185": "https://www.leccotrasporti.it/percorsi/estivo/linea-d185.pdf",
    "D150": "https://www.leccotrasporti.it/percorsi/estivo/linea-d150.pdf",
    "D170": "https://www.leccotrasporti.it/percorsi/estivo/linea-d170.pdf",
}
EXPECTED_PAGE_COUNTS = {"D184": 2, "D185": 2, "D150": 2, "D170": 4}
VALID_FROM = date(2026, 6, 9)
VALID_TO = date(2026, 9, 13)
SUMMER_EXCEPTION_FROM = date(2026, 7, 27)
SUMMER_EXCEPTION_TO = date(2026, 8, 30)
VALIDITY_RE = re.compile(
    r"ORARIO\s+IN\s+VIGORE\s+dal\s+9\s+Giugno\s+al\s+13\s+Settembre\s+2026",
    re.IGNORECASE,
)
DAY_CODES = {"123456", "12345", "6"}
NOTE_CODES = {"A", "B", "D", "V"}
EXPECTED_DIRECTION_TOKENS = {
    "D184": (("OLGIATE", "RAVELLINO"), ("RAVELLINO", "OLGIATE")),
    "D185": (("CELANA", "BRIVIO", "OLGIATE"), ("OLGIATE", "BRIVIO", "CELANA")),
    "D150": (("LECCO", "VALGREGHENTINO", "MERATE"), ("MERATE", "VALGREGHENTINO", "LECCO")),
    "D170": (("MONTEVECCHIA", "CARNATE", "VIMERCATE"), ("VIMERCATE", "CARNATE", "MONTEVECCHIA")),
}


def _download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "gate-c-transit-audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    if not payload.startswith(b"%PDF"):
        raise RuntimeError(f"Official timetable URL did not return a PDF: {url}")
    return payload, hashlib.sha256(payload).hexdigest()


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.upper()).strip()


def _extract_page(reader: PdfReader, page_index: int) -> tuple[str, list[dict[str, object]]]:
    page = reader.pages[page_index]
    fragments: list[dict[str, object]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        value = (text or "").strip()
        if not value:
            return
        fragments.append({"text": value, "x": float(tm[4]), "y": float(tm[5])})

    try:
        text = page.extract_text(extraction_mode="layout", visitor_text=visitor) or ""
    except TypeError:
        text = page.extract_text(visitor_text=visitor) or ""
    return text, fragments


def _find_row_y(fragments: list[dict[str, object]], needle: str) -> float:
    needle = needle.upper()
    matches = [float(f["y"]) for f in fragments if needle in str(f["text"]).upper()]
    if not matches:
        raise RuntimeError(f"PDF row label not found: {needle}")
    return max(matches)


def _row_fragments(
    fragments: list[dict[str, object]], row_y: float, allowed: set[str], tolerance: float = 4.0
) -> list[dict[str, object]]:
    rows = []
    for frag in fragments:
        value = str(frag["text"]).strip().upper()
        if value in allowed and abs(float(frag["y"]) - row_y) <= tolerance:
            rows.append({"text": value, "x": float(frag["x"]), "y": float(frag["y"])})
    return sorted(rows, key=lambda f: float(f["x"]))


def _map_notes_to_columns(
    day_columns: list[dict[str, object]], note_fragments: list[dict[str, object]]
) -> list[str | None]:
    notes: list[str | None] = [None] * len(day_columns)
    if not note_fragments:
        return notes
    xs = [float(col["x"]) for col in day_columns]
    spacings = [b - a for a, b in zip(xs, xs[1:]) if b > a]
    tolerance = (min(spacings) / 2.0) if spacings else 20.0
    for note in note_fragments:
        distances = [abs(float(note["x"]) - x) for x in xs]
        index = min(range(len(distances)), key=distances.__getitem__)
        if distances[index] > tolerance:
            raise RuntimeError(
                f"Could not assign note {note['text']} at x={note['x']} to a schedule column"
            )
        if notes[index] is not None:
            raise RuntimeError(f"Multiple note codes mapped to timetable column {index + 1}")
        notes[index] = str(note["text"])
    return notes


def _note_allows_service(note: str | None, service_date: date) -> bool:
    in_exception_window = SUMMER_EXCEPTION_FROM <= service_date <= SUMMER_EXCEPTION_TO
    if note == "A":
        return not in_exception_window
    if note == "B":
        return in_exception_window
    if note == "D":
        return not (in_exception_window and service_date.weekday() == 5)
    # V is a stop-pattern note, not a service-date restriction.
    return True


def _column_audit(
    fragments: list[dict[str, object]], service_date: date
) -> list[dict[str, object]]:
    day_y = _find_row_y(fragments, "scheduled days of operation")
    day_columns = _row_fragments(fragments, day_y, DAY_CODES)
    if not day_columns:
        raise RuntimeError("No coordinate-level scheduled-day columns resolved")

    try:
        note_y = _find_row_y(fragments, "NOTE:")
        note_fragments = _row_fragments(fragments, note_y, NOTE_CODES)
    except RuntimeError:
        note_fragments = []
    notes = _map_notes_to_columns(day_columns, note_fragments)

    weekday_code = str(service_date.weekday() + 1)  # Monday=1 ... Saturday=6
    global_holiday = (service_date.month, service_date.day) in {(1, 1), (8, 15), (12, 25)}
    output = []
    for index, (column, note) in enumerate(zip(day_columns, notes), start=1):
        scheduled_for_weekday = weekday_code in str(column["text"])
        active = scheduled_for_weekday and not global_holiday and _note_allows_service(note, service_date)
        output.append(
            {
                "column": index,
                "x": round(float(column["x"]), 3),
                "day_code": str(column["text"]),
                "note": note,
                "scheduled_for_weekday": scheduled_for_weekday,
                "active_on_service_date": active,
            }
        )
    return output


def _direction_matches(route_id: str, normalised_page: str) -> bool:
    candidates = EXPECTED_DIRECTION_TOKENS[route_id]
    return any(all(token in normalised_page for token in tokens) for tokens in candidates)


def audit_route(route_id: str, service_date: date) -> dict[str, object]:
    url = SOURCES[route_id]
    payload, sha256 = _download(url)
    reader = PdfReader(io.BytesIO(payload))
    if len(reader.pages) != EXPECTED_PAGE_COUNTS[route_id]:
        raise RuntimeError(
            f"{route_id}: expected {EXPECTED_PAGE_COUNTS[route_id]} pages, found {len(reader.pages)}"
        )
    if not (VALID_FROM <= service_date <= VALID_TO):
        raise RuntimeError(f"{route_id}: requested date is outside primary timetable validity")

    pages = []
    full_text_parts = []
    for page_index in range(len(reader.pages)):
        text, fragments = _extract_page(reader, page_index)
        full_text_parts.append(text)
        normalised = _normalise(text)
        if not _direction_matches(route_id, normalised):
            raise RuntimeError(f"{route_id} page {page_index + 1}: direction tokens absent")
        columns = _column_audit(fragments, service_date)
        pages.append(
            {
                "page": page_index + 1,
                "scheduled_columns": len(columns),
                "weekday_eligible_columns": sum(c["scheduled_for_weekday"] for c in columns),
                "active_columns": sum(c["active_on_service_date"] for c in columns),
                "columns": columns,
            }
        )

    full_text = "\n".join(full_text_parts)
    normalised_full = _normalise(full_text)
    if route_id not in normalised_full:
        raise RuntimeError(f"{route_id}: route id absent from primary timetable")
    if not VALIDITY_RE.search(full_text):
        raise RuntimeError(f"{route_id}: expected summer 2026 validity statement not found")

    notes_detected = {
        "A_suspended_27_july_to_30_august": (
            "27 LUGLIO" in normalised_full
            and "30 AGOSTO" in normalised_full
            and "SOSPESA" in normalised_full
        ),
        "B_only_27_july_to_30_august": (
            "SI EFFETTUA SOLO DAL 27 LUGLIO AL 30 AGOSTO" in normalised_full
            or "RUNS ONLY FROM JULY 27TH TO AUGUST 30TH" in normalised_full
        ),
        "D_no_saturday_27_july_to_30_august": (
            "27 LUGLIO" in normalised_full
            and "30 AGOSTO" in normalised_full
            and "NON SI EFFETTUA IL SABATO" in normalised_full
        ),
        "brivio_bridge_cantu_deviation": (
            route_id == "D185"
            and "PONTE CANT" in normalised_full
            and "CISANO SOSTA" in normalised_full
            and "SOSPESA" in normalised_full
        ),
    }

    return {
        "route_id": route_id,
        "url": url,
        "download_sha256": sha256,
        "page_count": len(reader.pages),
        "valid_from": VALID_FROM.isoformat(),
        "valid_to": VALID_TO.isoformat(),
        "service_date_requested": service_date.isoformat(),
        "service_date_within_validity": True,
        "pages": pages,
        "scheduled_columns_total": sum(p["scheduled_columns"] for p in pages),
        "weekday_eligible_columns_before_notes": sum(p["weekday_eligible_columns"] for p in pages),
        "active_timetable_columns": sum(p["active_columns"] for p in pages),
        "notes_detected": notes_detected,
        "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
        "warning": (
            "A timetable column is a source-grounded reconstructed run representation, not a GTFS trip."
        ),
    }


def build_report(service_date: date) -> dict[str, object]:
    routes = [audit_route(route_id, service_date) for route_id in SOURCES]
    if not all(route["service_date_within_validity"] for route in routes):
        raise RuntimeError("Not every route timetable covers the requested date")
    return {
        "gate": "C",
        "source_class": "OFFICIAL_OPERATOR_PRIMARY_TIMETABLE_PDFS",
        "service_date": service_date.isoformat(),
        "routes": routes,
        "epistemic_status": "FACT_PRIMARY_SOURCES_WITH_RECONSTRUCTED_COLUMN_AUDIT",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-date", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    service_date = date.fromisoformat(args.service_date)
    report = build_report(service_date)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for route in report["routes"]:
        print(
            route["route_id"],
            "scheduled=", route["scheduled_columns_total"],
            "weekday_eligible=", route["weekday_eligible_columns_before_notes"],
            "active=", route["active_timetable_columns"],
            "sha256=", route["download_sha256"],
        )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
