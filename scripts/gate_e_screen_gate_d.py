#!/usr/bin/env python3
"""Cross-screen normalized Gate D metrics against explicit Gate E sensitivity envelopes."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_d_screen import screen_rows  # noqa: E402
from src.service_math import ServiceMathError  # noqa: E402

D_REQUIRED = (
    "scenario_id", "service_day_group", "band_id", "direction", "upstream_gate_d_status",
    "gate_d_artifact", "gate_d_commit", "route_km", "route_km_status", "pure_running_min",
    "pure_running_status",
)
ENV_REQUIRED = (
    "analysis_mode", "result_status", "headway_each_direction_min", "headway_status",
    "in_service_vehicles_each_direction", "vehicle_policy_status", "dwell_min", "dwell_status",
    "recovery_min", "recovery_status", "cycles_per_day_each_direction", "cycles_status",
    "service_days_year", "service_days_status", "maximum_pure_running_min_compatible_with_headway",
    "maximum_common_route_km_under_pdb_budget",
)


def read_csv(path: Path, required: tuple[str, ...], label: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"{label} missing columns: {sorted(missing)}")
        rows = [dict(row) for row in reader]
    if not rows:
        raise ServiceMathError(f"{label} contains no rows")
    return rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gate-d", type=Path, required=True)
    p.add_argument("--envelope", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        d_rows = read_csv(args.gate_d, D_REQUIRED, "normalized Gate D handoff")
        envelopes = read_csv(args.envelope, ENV_REQUIRED, "Gate E operating envelope")
        for env in envelopes:
            if env["analysis_mode"].strip().upper() != "SENSITIVITY":
                raise ServiceMathError("operating-envelope rows must be SENSITIVITY")
            if env["result_status"].strip() != "SENSITIVITY_ONLY_NOT_PROJECT_RESULT":
                raise ServiceMathError("operating-envelope row is not explicitly sensitivity-only")
            assumption_statuses = (
                env["headway_status"], env["vehicle_policy_status"], env["dwell_status"],
                env["recovery_status"], env["cycles_status"], env["service_days_status"],
            )
            if {s.strip().upper() for s in assumption_statuses} != {"ASSUMPTION"}:
                raise ServiceMathError("all operating-envelope policy inputs must be ASSUMPTION")

        rows = [screen_rows(d, env) for d in d_rows for env in envelopes]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader(); writer.writerows(rows)
        print(f"Gate D sensitivity screening rows: {len(rows)}")
        print("Screen status: SENSITIVITY_ONLY_NOT_GATE_E_VERDICT")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_GATE_D_SCREEN_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
