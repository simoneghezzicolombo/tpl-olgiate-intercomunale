#!/usr/bin/env python3
"""Audit current official Arriva/Lecco Trasporti timetable PDFs.

The operator currently publishes summer 2026 bus service as primary timetable
PDFs while the Agency GTFS page still exposes the 2025-2026 feed snapshot.
This script verifies the current primary sources without pretending they are
GTFS. Any structured values emitted here are explicitly reconstructed from
those primary timetable documents.
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
VALIDITY_RE = re.compile(
    r"ORARIO\s+IN\s+VIGORE\s+dal\s+9\s+Giugno\s+al\s+13\s+Settembre\s+2026",
    re.IGNORECASE,
)
DAY_TOKEN_RE = re.compile(r"(?<!\d)(?:123456|12345|6)(?!\d)")
TIME_RE = re.compile(r"(?<!\d)(?:[0-2]?\d)[.:][0-5]\d(?!\d)")

EXPECTED_DIRECTION_TOKENS = {
    "D184": (("OLGIATE", "RAVELLINO"), ("RAVELLINO", "OLGIATE")),
    "D185": (("CELANA", "BRIVIO", "OLGIATE"), ("OLGIATE", "BRIVIO", "CELANA")),
    "D150": (("LECCO", "VALGREGHENTINO", "MERATE"), ("MERATE", "VALGREGHENTINO", "LECCO")),
    "D170": (("MONTEVECCHIA", "CARNATE", "VIMERCATE"), ("VIMERCATE", "CARNATE", "MONTEVECCHIA")),
}

# These are source assertions, not model outputs. They deliberately make the
# audit fail if the operator republishes a timetable with different rules so a
# human can inspect the changed primary document instead of silently accepting it.
EXPECTED_DOCUMENT_RULES = {
    "D184": {
        "suspended_27_july_to_30_august": True,
        "only_27_july_to_30_august": False,
        "brivio_bridge_cantu_deviation": False,
    },
    "D185": {
        "suspended_27_july_to_30_august": True,
        "only_27_july_to_30_august": False,
        "brivio_bridge_cantu_deviation": True,
    },
    "D150": {
        "suspended_27_july_to_30_august": True,
        "only_27_july_to_30_august": True,
        "brivio_bridge_cantu_deviation": False,
    },
    "D170": {
        "suspended_27_july_to_30_august": True,
        "only_27_july_to_30_august": True,
        "brivio_bridge_cantu_deviation": False,
    },
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


def _extract_pages(payload: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(payload))
    pages = []
    for page in reader.pages:
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            text = page.extract_text() or ""
        pages.append(text)
    return pages


def _header_day_tokens(page_text: str) -> list[str]:
    lines = page_text.splitlines()
    for index, line in enumerate(lines):
        if "scheduled days of operation" in line.lower() or "giorni di effettuazione" in line.lower():
            tokens = DAY_TOKEN_RE.findall(line)
            if tokens:
                return tokens
            for nearby in lines[index + 1 : index + 3]:
                tokens = DAY_TOKEN_RE.findall(nearby)
                if tokens:
                    return tokens
    # Deliberately narrow fallback, only the header area.
    top = "\n".join(lines[: max(12, len(lines) // 4)])
    return DAY_TOKEN_RE.findall(top)


def _direction_matches(route_id: str, normalised_page: str) -> bool:
    candidates = EXPECTED_DIRECTION_TOKENS[route_id]
    return any(all(token in normalised_page for token in tokens) for tokens in candidates)


def _detect_notes(route_id: str, normalised: str) -> dict[str, bool]:
    notes = {
        "suspended_27_july_to_30_august": bool(
            re.search(r"SOSPESA\s+DAL\s+27\s+LUGLIO\s+AL\s+30\s+AGOSTO", normalised)
        ),
        "only_27_july_to_30_august": bool(
            re.search(
                r"SI\s+EFFETTUA\s+SOLO\s+DAL\s+27\s+LUGLIO\s+AL\s+30\s+AGOSTO",
                normalised,
            )
        ),
        "brivio_bridge_cantu_deviation": (
            route_id == "D185"
            and "PONTE CANT" in normalised
            and "CISANO SOSTA" in normalised
            and "SOSPESA" in normalised
        ),
    }
    if notes != EXPECTED_DOCUMENT_RULES[route_id]:
        raise RuntimeError(
            f"{route_id}: primary timetable service rules changed or parser drifted; "
            f"expected {EXPECTED_DOCUMENT_RULES[route_id]}, found {notes}"
        )
    return notes


def audit_route(route_id: str, service_date: date) -> dict[str, object]:
    url = SOURCES[route_id]
    payload, sha256 = _download(url)
    pages = _extract_pages(payload)
    full_text = "\n".join(pages)
    normalised = _normalise(full_text)

    if len(pages) != EXPECTED_PAGE_COUNTS[route_id]:
        raise RuntimeError(
            f"{route_id}: expected {EXPECTED_PAGE_COUNTS[route_id]} pages, found {len(pages)}"
        )
    if route_id not in normalised:
        raise RuntimeError(f"{route_id}: route id absent from primary timetable")
    if not VALIDITY_RE.search(full_text):
        raise RuntimeError(f"{route_id}: expected summer 2026 validity statement not found")
    if not (VALID_FROM <= service_date <= VALID_TO):
        raise RuntimeError(f"{route_id}: requested date is outside primary timetable validity")

    weekday = service_date.isoweekday()
    page_audits = []
    for page_number, page_text in enumerate(pages, start=1):
        page_norm = _normalise(page_text)
        day_tokens = _header_day_tokens(page_text)
        if not day_tokens:
            raise RuntimeError(f"{route_id} page {page_number}: no scheduled-day columns resolved")
        if not _direction_matches(route_id, page_norm):
            raise RuntimeError(f"{route_id} page {page_number}: expected route direction tokens absent")
        weekday_eligible = (
            sum(str(weekday) in token for token in day_tokens)
            if 1 <= weekday <= 6
            else 0
        )
        page_audits.append(
            {
                "page": page_number,
                "scheduled_columns": len(day_tokens),
                "scheduled_day_codes": day_tokens,
                "weekday_eligible_columns_before_note_exceptions": weekday_eligible,
                "time_tokens_count": len(TIME_RE.findall(page_text)),
            }
        )

    notes = _detect_notes(route_id, normalised)

    return {
        "route_id": route_id,
        "url": url,
        "download_sha256": sha256,
        "page_count": len(pages),
        "valid_from": VALID_FROM.isoformat(),
        "valid_to": VALID_TO.isoformat(),
        "service_date_requested": service_date.isoformat(),
        "service_date_within_validity": True,
        "pages": page_audits,
        "weekday_eligible_columns_before_note_exceptions_total": sum(
            page["weekday_eligible_columns_before_note_exceptions"] for page in page_audits
        ),
        "notes_detected": notes,
        "column_level_exception_application_status": "PENDING_COORDINATE_VALIDATION",
        "epistemic_status": "RECONSTRUCTED_FROM_PRIMARY_TIMETABLE",
        "warning": (
            "Document columns/day codes and source rules are reconstructed from the official PDF. "
            "Weekday-eligible columns are not active-trip counts until note letters are reliably "
            "mapped to their individual columns."
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
        "epistemic_status": "FACT_PRIMARY_SOURCES_WITH_RECONSTRUCTED_DOCUMENT_AUDIT",
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
            "pages=", route["page_count"],
            "columns=", [p["scheduled_columns"] for p in route["pages"]],
            "weekday_eligible_before_notes=",
            route["weekday_eligible_columns_before_note_exceptions_total"],
            "sha256=", route["download_sha256"],
        )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
