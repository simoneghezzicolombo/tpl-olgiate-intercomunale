#!/usr/bin/env python3
"""Run Gate F only on provenance-complete upstream scenario metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_pareto import (  # noqa: E402
    DEFAULT_OBJECTIVES,
    build_epistemic_audit,
    build_tradeoffs,
    decision_summary,
    dominance_pairs,
    identify_robust_pareto_frontier,
    leave_one_objective_out_robustness,
    objective_manifest,
    unbounded_estimate_metrics,
)
from src.gate_f_status import enforce_verified_status_evidence, load_gate_status_bundle  # noqa: E402

LEGACY_FORBIDDEN = {
    (ROOT / "outputs/route_variants.csv").resolve(),
    (ROOT / "outputs/pareto_frontier.csv").resolve(),
    (ROOT / "outputs/service_simulation_scenarios.csv").resolve(),
    (ROOT / "outputs/train_connections.csv").resolve(),
    (ROOT / "outputs/scenario_comparison.csv").resolve(),
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
    parser.add_argument("--gate-status-file", type=Path)
    args = parser.parse_args()

    if args.gate_status_file and args.gate_status:
        raise SystemExit("REFUSED: use either --gate-status-file or manual --gate-status, not both")

    input_path = Path(args.input)
    resolved_input = (input_path if input_path.is_absolute() else ROOT / input_path).resolve()
    if resolved_input in LEGACY_FORBIDDEN:
        display = resolved_input.relative_to(ROOT) if resolved_input.is_relative_to(ROOT) else resolved_input
        raise SystemExit(f"REFUSED: {display} is an INVALIDATED legacy/hardcoded output and cannot feed Gate F")
    if not resolved_input.exists():
        raise SystemExit(f"BLOCKED: upstream scenario table not found: {resolved_input}")

    verified_status_evidence = False
    if args.gate_status_file:
        status_path = args.gate_status_file
        if not status_path.is_absolute():
            status_path = ROOT / status_path
        try:
            gate_status, status_bundle = load_gate_status_bundle(status_path, ROOT)
        except ValueError as exc:
            raise SystemExit(f"REFUSED_GATE_STATUS_EVIDENCE: {exc}") from exc
        verified_status_evidence = True
    else:
        gate_status = parse_gate_status(args.gate_status)
        status_bundle = None

    df = pd.read_csv(resolved_input)
    pareto = leave_one_objective_out_robustness(df, DEFAULT_OBJECTIVES)
    tradeoffs = build_tradeoffs(pareto, DEFAULT_OBJECTIVES)
    summary = decision_summary(pareto, gate_status, DEFAULT_OBJECTIVES)
    summary = enforce_verified_status_evidence(summary, verified_status_evidence)
    pairs = dominance_pairs(df, DEFAULT_OBJECTIVES)
    epistemic = build_epistemic_audit(df, DEFAULT_OBJECTIVES)

    unbounded = unbounded_estimate_metrics(df, DEFAULT_OBJECTIVES)
    robust = None if unbounded else identify_robust_pareto_frontier(df, DEFAULT_OBJECTIVES)
    if robust is not None:
        pareto = pareto.merge(
            robust[["scenario_id", "robust_pareto_optimal", "robustly_dominated_by"]],
            on="scenario_id",
            how="left",
            validate="one_to_one",
        )
        tradeoffs = tradeoffs.merge(
            robust[["scenario_id", "robust_pareto_optimal", "robustly_dominated_by"]],
            on="scenario_id",
            how="left",
            validate="one_to_one",
        )

    blockers = summary["dependency_status"] + summary.get("evidence_status", [])
    row_status = "DERIVED" if not blockers else "PROVISIONAL/" + "+".join(blockers)
    pareto["gate_f_status"] = row_status
    tradeoffs["gate_f_status"] = row_status

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    pareto.to_csv(output_dir / "pareto_frontier.csv", index=False)
    tradeoffs.to_csv(output_dir / "tradeoffs_vs_baseline.csv", index=False)
    pairs.to_csv(output_dir / "dominance_pairs.csv", index=False)
    epistemic.to_csv(output_dir / "epistemic_audit.csv", index=False)
    (output_dir / "objectives.json").write_text(
        json.dumps(objective_manifest(DEFAULT_OBJECTIVES), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if status_bundle is not None:
        (output_dir / "verified_gate_status_bundle.json").write_text(
            json.dumps(status_bundle, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    (output_dir / "verdict.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
