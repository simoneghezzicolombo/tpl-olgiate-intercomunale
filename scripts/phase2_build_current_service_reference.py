#!/usr/bin/env python3
"""Materialise the Phase 2 current-service reference from authoritative Gate C.

This script does not parse the legacy `outputs/current_service_baseline.csv` and
never imports `scripts/05_current_service.py`. It consumes the immutable Gate C
PASS output at its validated commit and exposes a compact dated service reference
for Phase 2.

The output is deliberately route-level. Gate C validated active timetable columns
from primary operator PDFs, but did not reconstruct a full stop x trip matrix.
Phase 2 therefore must not infer stop-level GJT or annual production from this
snapshot until those separate layers are materialised.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import urllib.request


GATE_C_COMMIT = "dcc3e75ae3b4f4ea5170f48e85345b83620c5536"
GATE_C_PATH = "outputs/gate_c/live_bus_timetables_2026-09-03.json"
GATE_C_URL = (
    "https://raw.githubusercontent.com/"
    "simoneghezzicolombo/tpl-olgiate-intercomunale/"
    f"{GATE_C_COMMIT}/{GATE_C_PATH}"
)
SERVICE_DATE = "2026-09-03"
REQUIRED_ROUTE_IDS = {"D184", "D185", "D150", "D170"}


def fetch_pinned_source(url: str = GATE_C_URL) -> tuple[dict, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "phase2-current-service-reference/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    digest = sha256(payload).hexdigest()
    return json.loads(payload.decode("utf-8")), digest


def build_reference(report: dict) -> list[dict[str, object]]:
    if report.get("gate") != "C":
        raise ValueError("Pinned source is not a Gate C report")
    if report.get("service_date") != SERVICE_DATE:
        raise ValueError("Gate C service date does not match Phase 2 reference date")
    if report.get("source_class") != "OFFICIAL_OPERATOR_PRIMARY_TIMETABLE_PDFS":
        raise ValueError("Unexpected Gate C current-bus source class")

    routes = report.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("Gate C report contains no routes")
    route_ids = {str(row.get("route_id", "")) for row in routes}
    if route_ids != REQUIRED_ROUTE_IDS:
        raise ValueError(f"Unexpected Gate C route universe: {sorted(route_ids)}")

    output: list[dict[str, object]] = []
    for row in routes:
        active = row.get("active_timetable_columns")
        if not isinstance(active, int) or active <= 0:
            raise ValueError(f"{row.get('route_id')}: invalid active timetable-column count")
        status = str(row.get("epistemic_status", ""))
        if status != "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE":
            raise ValueError(f"{row.get('route_id')}: unexpected epistemic status {status}")
        pdf_sha = str(row.get("download_sha256", ""))
        if len(pdf_sha) != 64:
            raise ValueError(f"{row.get('route_id')}: missing primary-PDF SHA256")

        output.append({
            "service_date": SERVICE_DATE,
            "route_id": row["route_id"],
            "active_timetable_columns": active,
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"],
            "source_url": row["url"],
            "source_pdf_sha256": pdf_sha,
            "epistemic_status": status,
            "gate_c_commit": GATE_C_COMMIT,
            "gate_c_artifact": GATE_C_PATH,
            "semantic_scope": "DATED_ROUTE_LEVEL_SERVICE_REFERENCE",
        })
    return sorted(output, key=lambda item: str(item["route_id"]))


def write_outputs(
    rows: list[dict[str, object]],
    *,
    source_sha256: str,
    csv_path: Path,
    validation_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0])
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    validation = {
        "status": "PASS",
        "service_date": SERVICE_DATE,
        "gate_c_commit": GATE_C_COMMIT,
        "gate_c_artifact": GATE_C_PATH,
        "gate_c_raw_url": GATE_C_URL,
        "gate_c_artifact_sha256": source_sha256,
        "route_ids": [row["route_id"] for row in rows],
        "route_count": len(rows),
        "active_timetable_columns_total": sum(int(row["active_timetable_columns"]) for row in rows),
        "dated_route_level_reference": True,
        "stop_level_timetable_matrix": "NOT_MATERIALISED_BY_GATE_C",
        "annual_production_from_this_snapshot": "NOT_IDENTIFIABLE",
        "legacy_outputs_current_service_baseline_csv": "FORBIDDEN_AS_PHASE2_EVIDENCE",
        "legacy_scripts_05_current_service_py": "FORBIDDEN_AS_PHASE2_EVIDENCE",
        "epistemic_note": (
            "Active timetable columns are reconstructed from official primary operator PDFs by Gate C. "
            "They are not GTFS trips, stop-level journey records or annual bus-km."
        ),
    }
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv-output",
        default="outputs/phase2/current_service_reference_2026-09-03.csv",
    )
    parser.add_argument(
        "--validation-output",
        default="outputs/phase2/current_service_reference_validation.json",
    )
    args = parser.parse_args()

    report, source_sha = fetch_pinned_source()
    rows = build_reference(report)
    write_outputs(
        rows,
        source_sha256=source_sha,
        csv_path=Path(args.csv_output),
        validation_path=Path(args.validation_output),
    )
    print(f"Gate C source SHA256: {source_sha}")
    for row in rows:
        print(row["route_id"], row["active_timetable_columns"], row["epistemic_status"])


if __name__ == "__main__":
    main()
