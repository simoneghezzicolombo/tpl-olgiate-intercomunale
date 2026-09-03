#!/usr/bin/env python3
"""Gate E service math.

This script intentionally contains no candidate routes, runtimes, frequencies,
judgements or recommendations. It consumes explicit Gate C/D service inputs and
computes deterministic service mathematics. Without upstream inputs it can only
emit the PdB benchmark reconstruction and exits BLOCKED_BY_GATE_C_AND_D for scenario work.
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
    aggregate_scenarios,
    load_pdb_budget,
    read_direction_plans,
)

DEFAULT_BUDGET = ROOT / "data" / "risorse_tpl_pdb.csv"
DEFAULT_INPUT = ROOT / "outputs" / "gate_e_inputs.csv"
DEFAULT_OUTPUT = ROOT / "outputs" / "gate_e_service_math.csv"
DEFAULT_DETAIL_OUTPUT = ROOT / "outputs" / "gate_e_service_math_directions.csv"
DEFAULT_BUDGET_OUTPUT = ROOT / "outputs" / "gate_e_budget_benchmark.csv"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ServiceMathError(f"Refusing to write empty output: {path}")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_budget_benchmark(path: Path, budget: dict[str, float]) -> None:
    rows = [
        {"linea": "D184", "annual_bus_km": budget["D184"], "epistemic_status": "RECONSTRUCTED"},
        {"linea": "D185", "annual_bus_km": budget["D185"], "epistemic_status": "RECONSTRUCTED"},
        {
            "linea": "D184+D185",
            "annual_bus_km": budget["D184+D185"],
            "epistemic_status": "DERIVED",
        },
    ]
    write_csv(path, rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--detail-output", type=Path, default=DEFAULT_DETAIL_OUTPUT)
    p.add_argument("--budget-output", type=Path, default=DEFAULT_BUDGET_OUTPUT)
    p.add_argument("--benchmark-only", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        budget = load_pdb_budget(args.budget)
        write_budget_benchmark(args.budget_output, budget)
        print(f"RECONSTRUCTED/DERIVED benchmark written: {args.budget_output}")
        print(f"D184 + D185 annual bus-km = {budget['D184+D185']:.0f}")

        if args.benchmark_only:
            return 0
        if not args.input.exists():
            print(
                f"BLOCKED_BY_GATE_C_AND_D: missing validated integrated scenario input {args.input}. "
                "Gate E will not reuse legacy hardcoded route/service outputs.",
                file=sys.stderr,
            )
            return 2

        plans = read_direction_plans(args.input)
        detail_rows = [plan.metrics() for plan in plans]
        scenario_rows = aggregate_scenarios(plans, budget["D184+D185"])
        write_csv(args.detail_output, detail_rows)
        write_csv(args.output, scenario_rows)
        print(f"Gate E direction metrics written: {args.detail_output}")
        print(f"Gate E scenario metrics written: {args.output}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
