#!/usr/bin/env python3
"""Audit current official Arriva/Lecco Trasporti timetable PDFs.

Current summer-2026 bus service is published as primary timetable PDFs while
the Agency GTFS snapshot in the repository ends on 2026-06-08. PDF timetable
columns are therefore source-grounded RECONSTRUCTED records, never GTFS trips.
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

import pdfplumber

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
    request = urllib.request.Request(url, headers={"User-Agent": "gate-c-transit-audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    if not payload.startswith(b"%PDF"):
        raise RuntimeError(f"Official timetable URL did not return PDF: {url}")
    return payload, hashlib.sha256(payload).hexdigest()


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.upper()).strip()


def _cluster_top(words: list[dict[str, object]], allowed: set[str]) -> list[list[dict[str, object]]]:
    selected = [w for w in words if str(w["text"]).strip().upper() in allowed]
    selected.sort(key=lambda w: float(w["top"]))
    clusters: list[list[dict[str, object]]] = []
    for word in selected:
        top = float(word["top"])
        for cluster in clusters:
            ctop = sum(float(x["top"]) for x in cluster) / len(cluster)
            if abs(top - ctop) <= 2.5:
                cluster.append(word)
                break
        else:
            clusters.append([word])
    return clusters


def _header_columns(words: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str | None]]:
    day_clusters = _cluster_top(words, DAY_CODES)
    if not day_clusters:
        raise RuntimeError("No scheduled-day word-coordinate clusters found")
    day_row = max(day_clusters, key=len)
    if len(day_row) < 2:
        raise RuntimeError("Scheduled-day header could not be separated from legend")
    day_top = sum(float(w["top"]) for w in day_row) / len(day_row)
    days = sorted(day_row, key=lambda w: float(w["x0"]))

    note_candidates = []
    for cluster in _cluster_top(words, NOTE_CODES):
        top = sum(float(w["top"]) for w in cluster) / len(cluster)
        distance = abs(top - day_top)
        if 1.0 < distance <= 25.0:
            note_candidates.append((distance, cluster))
    note_row = min(note_candidates, key=lambda item: item[0])[1] if note_candidates else []

    notes: list[str | None] = [None] * len(days)
    if note_row:
        xs = [float(w["x0"]) for w in days]
        spacings = [b - a for a, b in zip(xs, xs[1:]) if b > a]
        tolerance = (min(spacings) * 0.6) if spacings else 20.0
        for note in note_row:
            distances = [abs(float(note["x0"]) - x) for x in xs]
            index = min(range(len(distances)), key=distances.__getitem__)
            if distances[index] > tolerance:
                raise RuntimeError(f"Unmapped note {note['text']} at x={note['x0']}")
            if notes[index] is not None:
                raise RuntimeError(f"Multiple notes mapped to column {index + 1}")
            notes[index] = str(note["text"]).strip().upper()
    return days, notes


def _note_allows(note: str | None, service_date: date) -> bool:
    within = EXCEPTION_FROM <= service_date <= EXCEPTION_TO
    if note == "A":
        return not within
    if note == "B":
        return within
    if note == "D":
        return not (within and service_date.weekday() == 5)
    return True


def _audit_columns(words: list[dict[str, object]], service_date: date) -> list[dict[str, object]]:
    days, notes = _header_columns(words)
    weekday_code = str(service_date.weekday() + 1)
    holiday = (service_date.month, service_date.day) in {(1, 1), (8, 15), (12, 25)}
    output = []
    for index, (day, note) in enumerate(zip(days, notes), start=1):
        day_code = str(day["text"]).strip()
        weekday_ok = weekday_code in day_code
        active = weekday_ok and not holiday and _note_allows(note, service_date)
        output.append({
            "column": index,
            "x": round(float(day["x0"]), 3),
            "day_code": day_code,
            "note": note,
            "scheduled_for_weekday": weekday_ok,
            "active_on_service_date": active,
        })
    return output


def _direction_ok(route_id: str, text: str) -> bool:
    normalised = _normalise(text)
    return any(all(token in normalised for token in option) for option in DIRECTIONS[route_id])


def audit_route(route_id: str, service_date: date) -> dict[str, object]:
    payload, sha256 = _download(SOURCES[route_id])
    if not (VALID_FROM <= service_date <= VALID_TO):
        raise RuntimeError(f"{route_id}: {service_date} outside timetable validity")

    pages_out = []
    text_parts = []
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        if len(pdf.pages) != EXPECTED_PAGE_COUNTS[route_id]:
            raise RuntimeError(f"{route_id}: unexpected PDF page count {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True) or page.extract_text() or ""
            words = page.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=False)
            text_parts.append(text)
            if not _direction_ok(route_id, text):
                raise RuntimeError(f"{route_id} page {page_number}: route direction not resolved")
            columns = _audit_columns(words, service_date)
            pages_out.append({
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
        "pages": pages_out,
        "scheduled_columns_total": sum(p["scheduled_columns"] for p in pages_out),
        "weekday_eligible_columns_before_notes": sum(p["weekday_eligible_columns"] for p in pages_out),
        "active_timetable_columns": sum(p["active_columns"] for p in pages_out),
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
    return {
        "gate": "C",
        "source_class": "OFFICIAL_OPERATOR_PRIMARY_TIMETABLE_PDFS",
        "service_date": service_date.isoformat(),
        "routes": [audit_route(route_id, service_date) for route_id in SOURCES],
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
