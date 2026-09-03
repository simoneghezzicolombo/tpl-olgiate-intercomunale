#!/usr/bin/env python3
"""Run Gate F v2 on real-upstream aligned scenario metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_assembly import enforce_verified_assembly_evidence, verify_assembly_manifest  # noqa: E402
from src.gate_f_contract_v2 import metric_contract_manifest_v2, validate_metric_contract_v2  # noqa: E402
from src.gate_f_pareto import (  # noqa: E402
    build_epistemic_audit,
    build_tradeoffs,
    dominance_pairs,
    identify_robust_pareto_frontier,
    leave_one_objective_out_robustness,
    objective_manifest,
    unbounded_estimate_metrics,
)
from src.gate_f_status import enforce_verified_status_evidence, load_gate_status_bundle  # noqa: E402
from src.gate_f_v2 import V2_OBJECTIVES, decision_summary_v2, validate_v2_scenarios  # noqa: E402

LEGACY_FORBIDDEN = {
    (ROOT / "outputs/route_variants.csv").resolve(),
    (ROOT / "outputs/pareto_frontier.csv").resolve(),
    (ROOT / "outputs/service_simulation_scenarios.csv").resolve(),
    (ROOT / "outputs/train_connections.csv").resolve(),
    (ROOT / "outputs/scenario_comparison.csv").resolve(),
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=Path("outputs/gate_f_v2/scenario_metrics.csv"))
    p.add_argument("--assembly-manifest", type=Path, default=Path("outputs/gate_f_v2/assembly_manifest.json"))
    p.add_argument("--gate-status-file", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("outputs/gate_f_v2/result"))
    args = p.parse_args()

    resolved_input = (args.input if args.input.is_absolute() else ROOT / args.input).resolve()
    if resolved_input in LEGACY_FORBIDDEN:
        raise SystemExit("REFUSED: INVALIDATED legacy/hardcoded output cannot feed Gate F v2")
    if not resolved_input.is_file():
        raise SystemExit(f"BLOCKED: Gate F v2 input not found: {resolved_input}")
    assembly = (args.assembly_manifest if args.assembly_manifest.is_absolute() else ROOT / args.assembly_manifest).resolve()
    status_file = (args.gate_status_file if args.gate_status_file.is_absolute() else ROOT / args.gate_status_file).resolve()
    try:
        assembly_payload = verify_assembly_manifest(assembly, ROOT, resolved_input)
        if assembly_payload.get("gate_f_contract_version") != "V2_REAL_UPSTREAM":
            raise ValueError("assembly manifest is not Gate F V2_REAL_UPSTREAM")
        gate_status, status_payload = load_gate_status_bundle(status_file, ROOT)
    except ValueError as exc:
        raise SystemExit(f"REFUSED_GATE_F_V2_EVIDENCE: {exc}") from exc

    frame = pd.read_csv(resolved_input)
    validate_metric_contract_v2(frame)
    validate_v2_scenarios(frame)
    pareto = leave_one_objective_out_robustness(frame, V2_OBJECTIVES)
    summary = decision_summary_v2(pareto, gate_status)
    summary = enforce_verified_status_evidence(summary, True)
    summary = enforce_verified_assembly_evidence(summary, True)
    tradeoffs = build_tradeoffs(pareto, V2_OBJECTIVES)
    pairs = dominance_pairs(frame, V2_OBJECTIVES)
    epistemic = build_epistemic_audit(frame, V2_OBJECTIVES)
    unbounded = unbounded_estimate_metrics(frame, V2_OBJECTIVES)
    robust = None if unbounded else identify_robust_pareto_frontier(frame, V2_OBJECTIVES)
    if robust is not None:
        columns = ["scenario_id", "robust_pareto_optimal", "robustly_dominated_by"]
        pareto = pareto.merge(robust[columns], on="scenario_id", validate="one_to_one")
        tradeoffs = tradeoffs.merge(robust[columns], on="scenario_id", validate="one_to_one")

    blockers = list(summary.get("dependency_status") or []) + list(summary.get("evidence_status") or [])
    row_status = "DERIVED" if not blockers else "PROVISIONAL/" + "+".join(blockers)
    pareto["gate_f_status"] = row_status
    tradeoffs["gate_f_status"] = row_status

    output = (args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    pareto.to_csv(output / "pareto_frontier.csv", index=False)
    tradeoffs.to_csv(output / "tradeoffs_vs_baseline.csv", index=False)
    pairs.to_csv(output / "dominance_pairs.csv", index=False)
    epistemic.to_csv(output / "epistemic_audit.csv", index=False)
    (output / "objectives.json").write_text(json.dumps(objective_manifest(V2_OBJECTIVES), indent=2) + "\n", encoding="utf-8")
    (output / "metric_contract.json").write_text(json.dumps(metric_contract_manifest_v2(), indent=2) + "\n", encoding="utf-8")
    (output / "verified_assembly_manifest.json").write_text(json.dumps(assembly_payload, indent=2) + "\n", encoding="utf-8")
    (output / "verified_gate_status_bundle.json").write_text(json.dumps(status_payload, indent=2) + "\n", encoding="utf-8")
    (output / "verdict.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0 if summary["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
