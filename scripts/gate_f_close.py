#!/usr/bin/env python3
"""Close Gate F from verified A-E evidence and the complete Gate E scenario inventory."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_closure import build_scenario_inventory, close_gate_f_from_inventory  # noqa: E402
from src.gate_f_status import load_gate_status_bundle  # noqa: E402


def _repo_path(path: Path) -> Path:
    resolved = (path if path.is_absolute() else ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Gate F closure paths must stay inside repository: {resolved}") from exc
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paired", type=Path, required=True)
    parser.add_argument("--unpaired", type=Path, required=True)
    parser.add_argument("--status-bundle", type=Path, required=True)
    parser.add_argument("--inventory-output", type=Path, default=Path("outputs/gate_f/scenario_inventory.csv"))
    parser.add_argument("--verdict-output", type=Path, default=Path("outputs/gate_f/final_verdict.json"))
    args = parser.parse_args()

    try:
        paired = _repo_path(args.paired)
        unpaired = _repo_path(args.unpaired)
        bundle = _repo_path(args.status_bundle)
        inventory_out = _repo_path(args.inventory_output)
        verdict_out = _repo_path(args.verdict_output)

        statuses, status_payload = load_gate_status_bundle(bundle, ROOT)
        nonpass = {gate: status for gate, status in statuses.items() if status != "PASS"}
        inventory = build_scenario_inventory(paired, unpaired)
        closure = close_gate_f_from_inventory(inventory)
        payload = asdict(closure)
        payload["upstream_gate_statuses"] = statuses
        payload["status_bundle_integration_id"] = status_payload["integration_id"]
        payload["closure_semantics"] = (
            "PASS means Gate F completed its evidence-supported decision audit. It does not mean that a future topology "
            "was selected. A no-recommendation PASS is valid when the validated evidence cannot identify a unique or "
            "assumption-free winner without inventing future service inputs."
        )

        if nonpass:
            payload["verdict"] = "PROVISIONAL"
            payload["recommendation_status"] = "BLOCKED_BY_UPSTREAM_GATE"
            payload["definitive_pareto_eligible"] = False
            payload["reasons"] = list(payload["reasons"]) + [f"Non-PASS upstream gates: {nonpass}"]

        inventory_out.parent.mkdir(parents=True, exist_ok=True)
        verdict_out.parent.mkdir(parents=True, exist_ok=True)
        inventory.to_csv(inventory_out, index=False, lineterminator="\n")
        verdict_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_CLOSURE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
