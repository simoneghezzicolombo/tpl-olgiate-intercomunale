#!/usr/bin/env python3
"""Generate explicit Gate E sensitivity thresholds before Gate D is available.

All design values supplied on the command line are ASSUMPTION. This tool does
not claim a route is feasible; it tells Gate D which runtime/distance thresholds
a proposed operating policy would have to satisfy.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operating_envelope import (  # noqa: E402
    maximum_cycle_min_for_headway,
    maximum_pure_running_min_for_headway,
    max_symmetric_route_km_for_budget,
)
from src.service_math import ServiceMathError, load_pdb_budget  # noqa: E402


def numbers(value: str) -> list[float]:
    try:
        out = [float(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc
    if not out:
        raise argparse.ArgumentTypeError("at least one number required")
    return out


def integers(value: str) -> list[int]:
    try:
        out = [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not out:
        raise argparse.ArgumentTypeError("at least one integer required")
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--headways", type=numbers, required=True)
    p.add_argument("--vehicles-each-direction", type=integers, required=True)
    p.add_argument("--dwell-min", type=numbers, required=True)
    p.add_argument("--recovery-min", type=numbers, required=True)
    p.add_argument("--cycles-per-day-each-direction", type=integers, required=True)
    p.add_argument("--service-days", type=integers, required=True)
    p.add_argument("--budget", type=Path, default=ROOT / "data" / "risorse_tpl_pdb.csv")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    try:
        budget = float(load_pdb_budget(args.budget)["D184+D185"])
        rows: list[dict[str, object]] = []
        for headway in args.headways:
            for vehicles in args.vehicles_each_direction:
                for dwell in args.dwell_min:
                    for recovery in args.recovery_min:
                        max_cycle = maximum_cycle_min_for_headway(headway, vehicles)
                        max_running = maximum_pure_running_min_for_headway(
                            headway, vehicles, dwell, recovery
                        )
                        for cycles in args.cycles_per_day_each_direction:
                            for days in args.service_days:
                                rows.append({
                                    "analysis_mode": "SENSITIVITY",
                                    "result_status": "SENSITIVITY_ONLY_NOT_PROJECT_RESULT",
                                    "headway_each_direction_min": headway,
                                    "headway_status": "ASSUMPTION",
                                    "in_service_vehicles_each_direction": vehicles,
                                    "vehicle_policy_status": "ASSUMPTION",
                                    "dwell_min": dwell,
                                    "dwell_status": "ASSUMPTION",
                                    "recovery_min": recovery,
                                    "recovery_status": "ASSUMPTION",
                                    "cycles_per_day_each_direction": cycles,
                                    "cycles_status": "ASSUMPTION",
                                    "service_days_year": days,
                                    "service_days_status": "ASSUMPTION",
                                    "maximum_cycle_min_compatible_with_headway": max_cycle,
                                    "maximum_pure_running_min_compatible_with_headway": max_running,
                                    "runtime_threshold_status": "DERIVED_FROM_ASSUMPTIONS",
                                    "maximum_common_route_km_under_pdb_budget": max_symmetric_route_km_for_budget(
                                        budget, cycles, days
                                    ),
                                    "route_km_threshold_status": "DERIVED_FROM_ASSUMPTIONS_AND_PDB_BENCHMARK",
                                    "pdb_budget_bus_km": budget,
                                    "pdb_budget_status": "DERIVED_FROM_RECONSTRUCTED_LINE_TOTALS",
                                    "gate_d_use": "COMPARE_VALIDATED_D_RUNTIME_AND_ROUTE_KM_TO_THESE_THRESHOLDS",
                                })
        if not rows:
            raise ServiceMathError("no operating-envelope rows generated")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader(); writer.writerows(rows)
        print(f"Operating-envelope sensitivity rows: {len(rows)}")
        print("All policy inputs are ASSUMPTION; output is not a project result.")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_OPERATING_ENVELOPE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
