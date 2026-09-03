#!/usr/bin/env python3
"""Validate a date-level future service calendar and derive service-day counts.

A single calendar date cannot belong to multiple additive service-day groups for
the same scenario. ASSUMPTION dates are sensitivity-only.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import ServiceMathError, validate_epistemic_status  # noqa: E402

CONTRACT = "GATE_E_SERVICE_DATES_V1"
REQUIRED = (
    "contract_version", "scenario_id", "service_day_group", "service_date",
    "analysis_mode", "epistemic_status", "source_artifact", "source_commit",
)


def validate_and_aggregate(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    if not rows:
        raise ServiceMathError("service calendar contains no rows")
    seen: dict[tuple[str, date], str] = {}
    grouped: dict[tuple[str, str, int, str, str], set[date]] = defaultdict(set)
    for row in rows:
        if row["contract_version"].strip().upper() != CONTRACT:
            raise ServiceMathError(f"contract_version must be {CONTRACT}")
        scenario = row["scenario_id"].strip()
        group = row["service_day_group"].strip()
        mode = row["analysis_mode"].strip().upper()
        status = row["epistemic_status"].strip().upper()
        artifact, commit = row["source_artifact"].strip(), row["source_commit"].strip()
        if not scenario or not group:
            raise ServiceMathError("scenario_id and service_day_group are required")
        validate_epistemic_status(status, mode, "service_date")
        if mode == "PRODUCTION" and (not artifact or not commit):
            raise ServiceMathError("production service-date rows require source artifact and commit lineage")
        try:
            d = date.fromisoformat(row["service_date"].strip())
        except ValueError as exc:
            raise ServiceMathError(f"invalid ISO service_date {row['service_date']!r}") from exc
        key = (scenario, d)
        previous = seen.get(key)
        if previous is not None and previous != group:
            raise ServiceMathError(
                f"{scenario} {d}: date assigned to multiple additive service-day groups: {previous!r}, {group!r}"
            )
        if previous == group:
            raise ServiceMathError(f"{scenario} {d}: duplicate service-date row for group {group!r}")
        seen[key] = group
        grouped[(scenario, group, d.year, mode, status)].add(d)

    out = []
    for (scenario, group, year, mode, status), dates in sorted(grouped.items()):
        out.append({
            "scenario_id": scenario,
            "service_day_group": group,
            "calendar_year": year,
            "service_days_year": len(dates),
            "service_days_status": status,
            "analysis_mode": mode,
            "first_service_date": min(dates).isoformat(),
            "last_service_date": max(dates).isoformat(),
            "calendar_semantics": "DERIVED_FROM_EXPLICIT_NONOVERLAPPING_DATE_SET",
            "result_status": (
                "SENSITIVITY_ONLY_NOT_PROJECT_RESULT" if status == "ASSUMPTION"
                else "ELIGIBLE_AS_SERVICE_DAY_COUNT_INPUT"
            ),
        })
    return out


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"service calendar missing columns: {sorted(missing)}")
        return [{k: row[k].strip() for k in REQUIRED} for row in reader]


def write(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ServiceMathError("refusing to write empty service calendar summary")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        rows = validate_and_aggregate(read(args.input))
        write(args.output, rows)
        print(f"Service-calendar groups: {len(rows)}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_SERVICE_CALENDAR_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
