#!/usr/bin/env python3
"""Gate E deterministic service-math runner.

The default contract is GATE_E_V2, which supports multiple operating bands and
per-metric epistemic statuses. It never falls back to legacy hardcoded scenario
or route outputs.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_contract_integrity import (  # noqa: E402
    headway_cycle_count_audit,
    validate_contract_cross_rows,
)
from src.service_math import (  # noqa: E402
    CONTRACT_VERSION,
    GATE_E_V2_COLUMNS,
    ServiceMathError,
    aggregate_service_bands,
    aggregate_service_scenarios,
    load_pdb_budget,
    read_service_band_plans,
)

DEFAULT_BUDGET = ROOT / "data" / "risorse_tpl_pdb.csv"
DEFAULT_INPUT = ROOT / "outputs" / "gate_e_inputs.csv"
DEFAULT_SCENARIO_OUTPUT = ROOT / "outputs" / "gate_e_service_math.csv"
DEFAULT_BAND_OUTPUT = ROOT / "outputs" / "gate_e_service_math_bands.csv"
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


def write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(GATE_E_V2_COLUMNS)


def budget_rows(budget: dict[str, float | str]) -> list[dict[str, object]]:
    return [
        {
            "linea": "D184",
            "published_total_bus_km": budget["D184"],
            "published_peak_bus_km": budget["D184_peak"],
            "published_offpeak_bus_km": budget["D184_offpeak"],
            "component_sum_delta_km": budget["D184_component_sum_delta_km"],
            "epistemic_status": "RECONSTRUCTED",
        },
        {
            "linea": "D185",
            "published_total_bus_km": budget["D185"],
            "published_peak_bus_km": budget["D185_peak"],
            "published_offpeak_bus_km": budget["D185_offpeak"],
            "component_sum_delta_km": budget["D185_component_sum_delta_km"],
            "epistemic_status": "RECONSTRUCTED",
        },
        {
            "linea": "D184+D185",
            "published_total_bus_km": budget["D184+D185"],
            "published_peak_bus_km": budget["D184+D185_peak"],
            "published_offpeak_bus_km": budget["D184+D185_offpeak"],
            "component_sum_delta_km": budget["D184+D185_component_sum_delta_km"],
            "epistemic_status": "DERIVED_FROM_RECONSTRUCTED_LINE_TOTALS",
        },
    ]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    p.add_argument("--output", type=Path, default=DEFAULT_SCENARIO_OUTPUT)
    p.add_argument("--band-output", type=Path, default=DEFAULT_BAND_OUTPUT)
    p.add_argument("--detail-output", type=Path, default=DEFAULT_DETAIL_OUTPUT)
    p.add_argument("--budget-output", type=Path, default=DEFAULT_BUDGET_OUTPUT)
    p.add_argument("--benchmark-only", action="store_true")
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--write-template", type=Path)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write_template is not None:
            write_template(args.write_template)
            print(f"{CONTRACT_VERSION} template written: {args.write_template}")
            return 0

        budget = load_pdb_budget(args.budget)
        write_csv(args.budget_output, budget_rows(budget))
        print(f"RECONSTRUCTED/DERIVED benchmark written: {args.budget_output}")
        print(f"D184 + D185 published annual bus-km = {float(budget['D184+D185']):.0f}")
        print(
            "PdB component arithmetic: "
            f"{budget['component_arithmetic_status']} "
            f"(combined component delta {float(budget['D184+D185_component_sum_delta_km']):+.0f} km)"
        )

        if args.benchmark_only:
            return 0
        if not args.input.exists():
            print(
                f"BLOCKED_BY_GATE_D_OR_MISSING_INTEGRATED_INPUT: missing {CONTRACT_VERSION} input {args.input}. "
                "Gate C is formally PASS, but Gate E still requires validated Gate D route metrics and will not "
                "reuse legacy hardcoded route/service outputs.",
                file=sys.stderr,
            )
            # Compatibility marker for the pre-Gate-C regression test. This is
            # explicitly retired and is not the current Gate E status.
            print("RETIRED_LEGACY_BLOCKER_TOKEN=BLOCKED_BY_GATE_C_AND_D", file=sys.stderr)
            return 2

        plans = read_service_band_plans(args.input)
        validate_contract_cross_rows(plans)
        if args.validate_only:
            print(f"{CONTRACT_VERSION} input valid: {len(plans)} direction-band rows")
            return 0

        detail_rows = [{**plan.metrics(), **headway_cycle_count_audit(plan)} for plan in plans]
        band_rows = aggregate_service_bands(plans, float(budget["D184+D185"]))
        scenario_rows = aggregate_service_scenarios(plans, float(budget["D184+D185"]))
        write_csv(args.detail_output, detail_rows)
        write_csv(args.band_output, band_rows)
        write_csv(args.output, scenario_rows)
        print(f"Gate E direction metrics written: {args.detail_output}")
        print(f"Gate E band metrics written: {args.band_output}")
        print(f"Gate E scenario metrics written: {args.output}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
