#!/usr/bin/env python3
"""Fetch official public source material for Current-Service Baseline V4."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
from urllib.request import Request, urlopen

SOURCES = (
    {
        "dataset_id": "official_gtfs_arriva_addabus_2025_2026",
        "source_org": "Agenzia TPL Como-Lecco-Varese",
        "url": "https://halleyweb.com/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip",
        "filename": "official_gtfs_arriva_addabus_2025_2026.zip",
        "role": "HISTORICAL_OFFICIAL_STOP_IDENTITY_COORDS_SEQUENCE_ROUTE_MEMBERSHIP",
        "required": True,
    },
    {
        "dataset_id": "arriva_current_timetable_page_2026_09_04",
        "source_org": "Arriva Italia",
        "url": "https://bergamo.arriva.it/orari-e-percorsi/",
        "filename": "arriva_orari_current_2026_09_04.html",
        "role": "CURRENT_ROUTE_LEVEL_ACTIVATION_EVIDENCE",
        "required": True,
    },
    {
        "dataset_id": "atp_brivio_temporary_disruption_notice_2026",
        "source_org": "Agenzia TPL Como-Lecco-Varese",
        "url": "https://www.tplcomoleccovarese.it/atpcolc/po/mostra_news.php?area=H&id=1137",
        "filename": "atp_brivio_temporary_disruption_2026.html",
        "role": "TEMPORARY_DISRUPTION_EVIDENCE_EXCLUDED_FROM_STRUCTURAL_BASELINE",
        "required": True,
    },
    {
        "dataset_id": "arriva_future_timetable_page_2026_09_14",
        "source_org": "Arriva Italia",
        "url": "https://bergamo.arriva.it/orari-invernali-2026-27/",
        "filename": "arriva_future_2026_09_14.html",
        "role": "FUTURE_2026_09_14_CONTINUITY_CORROBORATION_ONLY",
        "required": False,
    },
    {
        "dataset_id": "atp_d184_kml_2025",
        "source_org": "Agenzia TPL Como-Lecco-Varese",
        "url": "https://www.tplcomoleccovarese.it/atpcolc/images/Fil%20KML%202025/Urbano%20e%20interurbano%20Lecco/D184.kml",
        "filename": "D184_official_2025.kml",
        "role": "OFFICIAL_ROUTE_GEOMETRY_CORROBORATION",
        "required": False,
    },
    {
        "dataset_id": "atp_d185_kml_2025",
        "source_org": "Agenzia TPL Como-Lecco-Varese",
        "url": "https://www.tplcomoleccovarese.it/atpcolc/images/Fil%20KML%202025/Urbano%20e%20interurbano%20Lecco/D185.kml",
        "filename": "D185_official_2025.kml",
        "role": "OFFICIAL_ROUTE_GEOMETRY_CORROBORATION",
        "required": False,
    },
)

FIELDS = [
    "dataset_id", "source_org", "source_url", "retrieval_timestamp_utc",
    "filename", "sha256", "epistemic_role", "required", "available", "notes",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    last = None
    for attempt in range(3):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 Phase2CurrentServiceBaselineV4/1.0",
                    "Accept": "*/*",
                },
            )
            with urlopen(req, timeout=90) as response:
                data = response.read()
            if not data:
                raise ValueError("empty response")
            return data
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed: {last}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", type=Path, required=True)
    ap.add_argument("--manifest-output", type=Path, required=True)
    args = ap.parse_args()

    args.source_dir.mkdir(parents=True, exist_ok=True)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []
    failures = []

    for source in SOURCES:
        available = False
        digest = ""
        notes = ""
        try:
            payload = fetch(source["url"])
            target = args.source_dir / source["filename"]
            target.write_bytes(payload)
            digest = sha256_bytes(payload)
            available = True
        except Exception as exc:
            notes = str(exc)
            if source["required"]:
                failures.append(f"{source['dataset_id']}: {exc}")

        rows.append({
            "dataset_id": source["dataset_id"],
            "source_org": source["source_org"],
            "source_url": source["url"],
            "retrieval_timestamp_utc": timestamp,
            "filename": source["filename"],
            "sha256": digest,
            "epistemic_role": source["role"],
            "required": str(source["required"]).lower(),
            "available": str(available).lower(),
            "notes": notes,
        })

    with args.manifest_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    if failures:
        raise SystemExit("Required official-source acquisition failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
