#!/usr/bin/env python3
"""Run Gate F only on provenance-complete upstream scenario metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.gate_f_pareto import DEFAULT_OBJECTIVES, build_tradeoffs, decision_summary, leave_one_objective_out_robustness

LEGACY_FORBIDDEN = {
    Path("outputs/route_variants.csv"),
    Path("outputs/pareto_frontier.csv"),
    Path("outputs/service_simulation_scenarios.csv"),
    Path("outputs/train_connections.csv"),
    Path("outputs/scenario_comparison.csv"),
}


def parse_gate_status(items: list[str]) -> dict[str, str]:
    result = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --gate-status value: {item}; use A=PASS")
        gate, status = item.split("=", 1)
        gate = gate.strip().upper().replace("GATE_", "").replace("GATE ", "")
        result[gate] = status.strip().upper()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="outputs/gate_f_scenario_metrics.csv")
    parser.add_argument("--output-dir", default="outputs/gate_f")
    parser.add_argument("--gate-status", action="append", default=[])
    args = parser.parse_args()

    input_path = Path(args.input)
    normalized = Path(input_path.as_posix())
    if normalized in LEGACY_FORBIDDEN:
        raise SystemExit(f"REFUSED: {normalized} is an INVALIDATED legacy/hardcoded output and cannot feed Gate F")
    if not input_path.exists():
        raise SystemExit(f"BLOCKED: upstream scenario table not found: {input_path}")

    gate_status = parse_gate_status(args.gate_status)
    df = pd.read_csv(input_path)
    pareto = leave_one_objective_out_robustness(df, DEFAULT_OBJECTIVES)
    tradeoffs = build_tradeoffs(pareto, DEFAULT_OBJECTIVES)
    summary = decision_summary(pareto, gate_status, DEFAULT_OBJECTIVES)

    blockers = summary["dependency_status"]
    row_status = "DERIVED" if not blockers else "PROVISIONAL/" + "+".join(blockers)
    pareto["gate_f_status"] = row_status
    tradeoffs["gate_f_status"] = row_status

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pareto.to_csv(output_dir / "pareto_frontier.csv", index=False)
    tradeoffs.to_csv(output_dir / "tradeoffs_vs_baseline.csv", index=False)
    (output_dir / "verdict.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
