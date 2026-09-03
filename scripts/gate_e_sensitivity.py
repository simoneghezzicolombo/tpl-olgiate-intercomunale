#!/usr/bin/env python3
"""Formula-only Gate E sensitivity surfaces.

All user-supplied scenario values are ASSUMPTION and outputs are SENSITIVITY_ONLY.
This script never promotes a route or operating plan to a project result.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import (  # noqa: E402
    ServiceMathError,
    budget_break_even_route_km,
    combined_headway_rate_equivalent,
    load_pdb_budget,
    minimum_vehicles_for_regular_headway,
)


def floats(value: str) -> list[float]:
    try:
        values = [float(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc
    if not values:
        raise argparse.ArgumentTypeError("at least one value required")
    return values


def ints(value: str) -> list[int]:
    try:
        values = [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not values:
        raise argparse.ArgumentTypeError("at least one value required")
    return values


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cycles-per-day-each-direction", type=ints, required=True)
    p.add_argument("--service-days", type=ints, required=True)
    p.add_argument("--cycle-minutes", type=floats, required=True)
    p.add_argument("--headways", type=floats, required=True)
    p.add_argument("--budget", type=Path, default=ROOT / "data" / "risorse_tpl_pdb.csv")
    p.add_argument("--budget-output", type=Path, required=True)
    p.add_argument("--fleet-output", type=Path, required=True)
    args = p.parse_args()
    try:
        budget = float(load_pdb_budget(args.budget)["D184+D185"])
        budget_rows = []
        for cycles in args.cycles_per_day_each_direction:
            for days in args.service_days:
                directional_cycles_year = 2 * cycles * days
                budget_rows.append({
                    "analysis_mode": "SENSITIVITY",
                    "epistemic_status_cycles_per_day": "ASSUMPTION",
                    "epistemic_status_service_days": "ASSUMPTION",
                    "pdb_budget_status": "DERIVED_FROM_RECONSTRUCTED_LINE_TOTALS",
                    "cycles_per_day_each_direction": cycles,
                    "service_days_year": days,
                    "directional_cycles_year_total_CW_plus_CCW": directional_cycles_year,
                    "pdb_budget_bus_km": budget,
                    "break_even_mean_route_km_per_directional_cycle": budget_break_even_route_km(
                        budget, directional_cycles_year
                    ),
                    "result_status": "SENSITIVITY_ONLY_NOT_PROJECT_RESULT",
                })
        fleet_rows = []
        for cycle in args.cycle_minutes:
            for headway in args.headways:
                per_direction = minimum_vehicles_for_regular_headway(cycle, headway)
                fleet_rows.append({
                    "analysis_mode": "SENSITIVITY",
                    "epistemic_status_cycle_minutes": "ASSUMPTION",
                    "epistemic_status_headway": "ASSUMPTION",
                    "cycle_minutes": cycle,
                    "headway_each_direction_min": headway,
                    "minimum_in_service_vehicles_each_direction": per_direction,
                    "minimum_in_service_vehicles_CW_plus_CCW": 2 * per_direction,
                    "combined_rate_equivalent_min_if_shared_stops_and_even_phasing": combined_headway_rate_equivalent(headway, headway),
                    "fleet_semantics": "LOWER_BOUND_EXCLUDES_DEADHEAD_RELIEF_SPARES_INTERLINING",
                    "result_status": "SENSITIVITY_ONLY_NOT_PROJECT_RESULT",
                })
        write_csv(args.budget_output, budget_rows)
        write_csv(args.fleet_output, fleet_rows)
        print(f"Sensitivity budget rows: {len(budget_rows)}")
        print(f"Sensitivity fleet rows: {len(fleet_rows)}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_SENSITIVITY_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
