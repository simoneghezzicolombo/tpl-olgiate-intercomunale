#!/usr/bin/env python3
"""Build GATE_E_V2 input deterministically from normalized Gate C and Gate D handoffs."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import GATE_E_V2_COLUMNS, ServiceMathError, read_service_band_plans  # noqa: E402

KEYS = ("scenario_id", "service_day_group", "band_id", "direction")
C_COLUMNS = KEYS + (
    "band_start_time", "band_end_time", "upstream_gate_c_status", "gate_c_artifact",
    "gate_c_commit", "shared_stop_pattern_status", "target_headway_min",
    "target_headway_status", "daily_cycles", "daily_cycles_status", "service_days_year",
    "service_days_status", "dwell_min", "dwell_status", "recovery_min", "recovery_status",
)
D_COLUMNS = KEYS + (
    "upstream_gate_d_status", "gate_d_artifact", "gate_d_commit", "route_km",
    "route_km_status", "pure_running_min", "pure_running_status",
)


def load(path: Path, required: tuple[str, ...], label: str) -> dict[tuple[str, ...], dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"{label} missing columns: {sorted(missing)}")
        out = {}
        for row in reader:
            key = tuple(row[k].strip() for k in KEYS)
            if not all(key):
                raise ServiceMathError(f"{label} has blank join key: {key}")
            if key in out:
                raise ServiceMathError(f"{label} duplicate join key: {key}")
            out[key] = {k: row[k].strip() for k in required}
    if not out:
        raise ServiceMathError(f"{label} contains no rows")
    return out


def build(c_rows, d_rows):
    c_keys, d_keys = set(c_rows), set(d_rows)
    if c_keys != d_keys:
        only_c = sorted(c_keys - d_keys)
        only_d = sorted(d_keys - c_keys)
        raise ServiceMathError(f"C/D handoff keys differ; only_C={only_c[:5]} only_D={only_d[:5]}")
    out = []
    for key in sorted(c_keys):
        c, d = c_rows[key], d_rows[key]
        row = {
            "contract_version": "GATE_E_V2",
            "scenario_id": c["scenario_id"], "service_day_group": c["service_day_group"],
            "band_id": c["band_id"], "band_start_time": c["band_start_time"],
            "band_end_time": c["band_end_time"], "direction": c["direction"],
            "analysis_mode": "PRODUCTION",
            "upstream_gate_c_status": c["upstream_gate_c_status"],
            "upstream_gate_d_status": d["upstream_gate_d_status"],
            "gate_c_artifact": c["gate_c_artifact"], "gate_c_commit": c["gate_c_commit"],
            "gate_d_artifact": d["gate_d_artifact"], "gate_d_commit": d["gate_d_commit"],
            "shared_stop_pattern_status": c["shared_stop_pattern_status"],
            "route_km": d["route_km"], "route_km_status": d["route_km_status"],
            "pure_running_min": d["pure_running_min"], "pure_running_status": d["pure_running_status"],
            "dwell_min": c["dwell_min"], "dwell_status": c["dwell_status"],
            "recovery_min": c["recovery_min"], "recovery_status": c["recovery_status"],
            "target_headway_min": c["target_headway_min"], "target_headway_status": c["target_headway_status"],
            "daily_cycles": c["daily_cycles"], "daily_cycles_status": c["daily_cycles_status"],
            "service_days_year": c["service_days_year"], "service_days_status": c["service_days_status"],
        }
        out.append(row)
    return out


def write(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GATE_E_V2_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gate-c", type=Path, required=True)
    p.add_argument("--gate-d", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        rows = build(load(args.gate_c, C_COLUMNS, "Gate C"), load(args.gate_d, D_COLUMNS, "Gate D"))
        write(args.output, rows)
        read_service_band_plans(args.output)
        print(f"GATE_E_V2 input built and validated: {len(rows)} rows")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_BUILD_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
