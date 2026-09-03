#!/usr/bin/env python3
"""Audit observed CW/CCW/combined headways from Gate C departure events."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.headway_audit import (  # noqa: E402
    combined_observed_headway_stats,
    headway_evidence_status,
    observed_headway_stats,
)
from src.service_math import ServiceMathError  # noqa: E402

REQUIRED = (
    "scenario_id", "service_day_group", "band_id", "stop_id", "direction",
    "departure_time", "analysis_mode", "epistemic_status", "upstream_gate_c_status",
    "gate_c_artifact", "gate_c_commit", "shared_stop_pattern_status",
)
KEY = ("scenario_id", "service_day_group", "band_id", "stop_id")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"departure handoff missing columns: {sorted(missing)}")
        rows = [{k: row[k].strip() for k in REQUIRED} for row in reader]
    if not rows:
        raise ServiceMathError("departure handoff contains no rows")
    for row in rows:
        if row["direction"].upper() not in {"CW", "CCW"}:
            raise ServiceMathError("departure direction must be CW or CCW")
    return rows


def aggregate(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[k] for k in KEY), []).append(row)
    out = []
    for key, group in sorted(grouped.items()):
        directions = {d: [r for r in group if r["direction"].upper() == d] for d in ("CW", "CCW")}
        statuses = {r["upstream_gate_c_status"].upper() for r in group}
        modes = {r["analysis_mode"].upper() for r in group}
        artifacts = {r["gate_c_artifact"] for r in group}
        commits = {r["gate_c_commit"] for r in group}
        shared_pattern = {r["shared_stop_pattern_status"].upper() for r in group}
        if len(statuses) != 1 or len(modes) != 1 or len(artifacts) != 1 or len(commits) != 1:
            raise ServiceMathError(f"{key}: inconsistent Gate C lineage/status within stop-band")
        status = headway_evidence_status(
            next(iter(statuses)), [r["epistemic_status"] for r in group], next(iter(modes)),
            next(iter(artifacts)), next(iter(commits)),
        )
        cw_stats = observed_headway_stats([r["departure_time"] for r in directions["CW"]])
        ccw_stats = observed_headway_stats([r["departure_time"] for r in directions["CCW"]])
        combined_allowed = bool(
            shared_pattern == {"CONFIRMED"} and directions["CW"] and directions["CCW"]
        )
        combined = (
            combined_observed_headway_stats(
                [r["departure_time"] for r in directions["CW"]],
                [r["departure_time"] for r in directions["CCW"]],
            )
            if combined_allowed else None
        )
        row = {
            "scenario_id": key[0], "service_day_group": key[1], "band_id": key[2], "stop_id": key[3],
            "headway_evidence_status": status,
            "shared_stop_pattern_status": next(iter(shared_pattern)) if len(shared_pattern) == 1 else "INCONSISTENT",
            "CW_n_departures": cw_stats["n_departures"], "CW_mean_headway_min": cw_stats["mean_headway_min"],
            "CW_max_headway_min": cw_stats["max_headway_min"], "CCW_n_departures": ccw_stats["n_departures"],
            "CCW_mean_headway_min": ccw_stats["mean_headway_min"], "CCW_max_headway_min": ccw_stats["max_headway_min"],
            "combined_headway_computed": combined_allowed,
            "combined_mean_headway_min": combined["mean_headway_min"] if combined else None,
            "combined_p90_headway_min": combined["p90_headway_min"] if combined else None,
            "combined_max_headway_min": combined["max_headway_min"] if combined else None,
            "combined_simultaneous_CW_CCW_departures": combined["simultaneous_CW_CCW_departures"] if combined else None,
            "combined_rate_equivalent_from_directional_observed_means_min": combined["rate_equivalent_from_directional_observed_means_min"] if combined else None,
            "combined_max_gap_to_rate_equivalent_ratio": combined["max_gap_to_rate_equivalent_ratio"] if combined else None,
            "boundary_gap_semantics": "EXCLUDED_REQUIRES_ADJACENT_BANDS_OR_FULL_DAY_TIMETABLE",
        }
        out.append(row)
    return out


def write(path: Path, rows: list[dict[str, object]]) -> None:
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
        rows = aggregate(read_rows(args.input))
        write(args.output, rows)
        print(f"Observed headway audit rows: {len(rows)}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_HEADWAY_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
