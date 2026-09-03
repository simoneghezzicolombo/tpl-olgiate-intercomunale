#!/usr/bin/env python3
"""Audit current official Arriva/Lecco Trasporti timetable PDFs.

Current summer-2026 bus service is published as primary timetable PDFs while
the Agency GTFS snapshot in the repository ends on 2026-06-08. This audit
keeps the distinction explicit: PDF timetable columns are source-grounded
RECONSTRUCTED records, never GTFS trips.
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
EXCEPTION_FROM = date(2026, 7, 27)
EXCEPTION_TO = date(2026, 8, 30)
DAY_CODES = {"123456", "12345", "6"}
NOTE_CODES = {"A", "B", "D", "V"}
VALIDITY_RE = re.compile(
    r"ORARIO\s+IN\s+VIGORE\s+dal\s+9\s+Giugno\s+al\s+13\s+Settembre\s+2026",
    re.IGNORECASE,
)
DIRECTIONS = {
    "D184": (("OLGIATE", "RAVELLINO"), ("RAVELLINO", "OLGIATE")),
    "D185": (("CELANA", "BRIVIO", "OLGIATE"), ("OLGIATE", "BRIVIO", "CELANA")),
    "D150": (("LECCO", "VALGREGHENTINO", "MERATE"), ("MERATE", "VALGREGHENTINO", "LECCO")),
    "D170": (("MONTEVECCHIA", "CARNATE", "VIMERCATE"), ("VIMERCATE", "CARNATE", "MONTEVECCHIA")),
}


def _download(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "gate-c-transit-audit/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        payload = response.read()
    if not payload.startswith(b"%PDF"):
        raise RuntimeError(f"Official timetable URL did not return PDF: {url}")
    return payload, hashlib.sha256(payload).hexdigest()


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.upper()).strip()


def _page_text_and_fragments(page) -> tuple[str, list[dict[str, object]]]:
    # pypdf deliberately ignores visitor_text in layout mode, so extract the
    # human-readable layout and coordinates in two separate passes.
    try:
        layout_text = page.extract_text(extraction_mode="layout") or ""
    except TypeError:
        layout_text = page.extract_text() or ""

    fragments: list[dict[str, object]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        value = (text or "").strip()
        if value:
            fragments.append({"text": value, "x": float(tm[4]), "y": float(tm[5])})

    page.extract_text(visitor_text=visitor)
    return layout_text, fragments


def _cluster_y(fragments: list[dict[str, object]], allowed: set[str]) -> list[list[dict[str, object]]]:
    selected = [f for f in fragments if str(f["text"]).strip().upper() in allowed]
    selected.sort(key=lambda f: float(f["y"]), reverse=True)
    clusters: list[list[dict[str, object]]] = []
    for frag in selected:
        y = float(frag["y"])
        placed = False
        for cluster in clusters:
            cy = sum(float(x["y"]) for x in cluster) / len(cluster)
            if abs(y - cy) <= 2.5:
                cluster.append(frag)
                placed = True
                break
        if not placed:
            clusters.append([frag])
    return clusters


def _header_columns(fragments: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str | None]]:
    day_clusters = _cluster_y(fragments, DAY_CODES)
    if not day_clusters:
        raise RuntimeError("No scheduled-day coordinate clusters found")
    day_cluster = max(day_clusters, key=len)
    if len(day_cluster) < 2:
        raise RuntimeError("Scheduled-day header could not be distinguished from legend text")
    day_y = sum(float(f["y"]) for f in day_cluster) / len(day_cluster)
    days = sorted(day_cluster, key=lambda f: float(f["x"]))

    note_clusters = _cluster_y(fragments, NOTE_CODES)
    candidates = []
    for cluster in note_clusters:
        y = sum(float(f["y"]) for f in cluster) / len(cluster)
        distance = abs(y - day_y)
        if 1.0 < distance <= 30.0:
            candidates.append((distance, cluster))
    notes_row = min(candidates, key=lambda item: item[0])[1] if candidates else []

    notes: list[str | None] = [None] * len(days)
    if notes_row:
        xs = [float(f["x"]) for f in days]
        spacings = [b - a for a, b in zip(xs, xs[1:]) if b > a]
        tolerance = (min(spacings) * 0.55) if spacings else 20.0
        for note in notes_row:
            distances = [abs(float(note["x"]) - x) for x in xs]
            idx = min(range(len(distances)), key=distances.__getitem__)
            if distances[idx] > tolerance:
                raise RuntimeError(f"Unmapped note {note['text']} at x={note['x']}")
            if notes[idx] is not None:
                raise RuntimeError(f"Multiple notes mapped to column {idx + 1}")
            notes[idx] = str(note["text"]).strip().upper()
    return days, notes


def _note_allows(note: str | None, service_date: date) -> bool:
    within = EXCEPTION_FROM <= service_date <= EXCEPTION_TO
    if note == "A":
        return not within
    if note == "B":
        return within
    if note == "D":
        return not (within and service_date.weekday() == 5)
    return True  # blank or V; V changes stop pattern, not service date


def _audit_columns(fragments: list[dict[str, object]], service_date: date) -> list[dict[str, object]]:
    days, notes = _header_columns(fragments)
    weekday_code = str(service_date.weekday() + 1)
    holiday = (service_date.month, service_date.day) in {(1, 1), (8, 15), (12, 25)}
    rows = []
    for index, (day, note) in enumerate(zip(days, notes), start=1):
        day_code = str(day["text"]).strip()
        weekday_ok = weekday_code in day_code
        active = weekday_ok and not holiday and _note_allows(note, service_date)
        rows.append({
            "column": index,
            "x": round(float(day["x"]), 3),
            "day_code": day_code,
            "note": note,
            "scheduled_for_weekday": weekday_ok,
            "active_on_service_date": active,
        })
    return rows


def _direction_ok(route_id: str, text: str) -> bool:
    normalised = _normalise(text)
    return any(all(token in normalised for token in option) for option in DIRECTIONS[route_id])


def audit_route(route_id: str, service_date: date) -> dict[str, object]:
    payload, sha256 = _download(SOURCES[route_id])
    reader = PdfReader(io.BytesIO(payload))
    if len(reader.pages) != EXPECTED_PAGE_COUNTS[route_id]:
        raise RuntimeError(f"{route_id}: unexpected PDF page count {len(reader.pages)}")
    if not (VALID_FROM <= service_date <= VALID_TO):
        raise RuntimeError(f"{route_id}: {service_date} outside timetable validity")

    pages = []
    text_parts = []
    for page_number, page in enumerate(reader.pages, start=1):
        text, fragments = _page_text_and_fragments(page)
        text_parts.append(text)
        if not _direction_ok(route_id, text):
            raise RuntimeError(f"{route_id} page {page_number}: route direction not resolved")
        columns = _audit_columns(fragments, service_date)
        pages.append({
            "page": page_number,
            "scheduled_columns": len(columns),
            "weekday_eligible_columns": sum(bool(c["scheduled_for_weekday"]) for c in columns),
            "active_columns": sum(bool(c["active_on_service_date"]) for c in columns),
            "columns": columns,
        })

    full_text = "\n".join(text_parts)
    normalised = _normalise(full_text)
    if route_id not in normalised or not VALIDITY_RE.search(full_text):
        raise RuntimeError(f"{route_id}: source identity/validity statement not verified")

    return {
        "route_id": route_id,
        "url": SOURCES[route_id],
        "download_sha256": sha256,
        "valid_from": VALID_FROM.isoformat(),
        "valid_to": VALID_TO.isoformat(),
        "service_date": service_date.isoformat(),
        "pages": pages,
        "scheduled_columns_total": sum(p["scheduled_columns"] for p in pages),
        "weekday_eligible_columns_before_notes": sum(p["weekday_eligible_columns"] for p in pages),
        "active_timetable_columns": sum(p["active_columns"] for p in pages),
        "notes_detected": {
            "A_suspension_rule": "SOSPESA DAL 27 LUGLIO AL 30 AGOSTO" in normalised,
            "B_only_rule": (
                "SI EFFETTUA SOLO DAL 27 LUGLIO AL 30 AGOSTO" in normalised
                or "RUNS ONLY FROM JULY 27TH TO AUGUST 30TH" in normalised
            ),
            "D_saturday_rule": "NON SI EFFETTUA IL SABATO" in normalised,
            "brivio_bridge_cantu_deviation": (
                route_id == "D185" and "PONTE CANT" in normalised and "CISANO SOSTA" in normalised
            ),
        },
        "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
        "warning": "Timetable columns are source-grounded reconstructed runs, not GTFS trip records.",
    }


def build_report(service_date: date) -> dict[str, object]:
    routes = [audit_route(route_id, service_date) for route_id in SOURCES]
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
    report = build_report(date.fromisoformat(args.service_date))
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
