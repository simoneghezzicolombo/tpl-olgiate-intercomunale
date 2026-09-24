#!/usr/bin/env python3
"""Build Gate F population/territory fragment from validated Gate B artifacts."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_gate_b_bridge import evaluate_candidate_coverage  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stops", type=Path, required=True)
    p.add_argument("--graph-nodes", type=Path, required=True)
    p.add_argument("--graph-edges", type=Path, required=True)
    p.add_argument("--population-access", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--gate-b-commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        frame = evaluate_candidate_coverage(
            args.stops,
            args.graph_nodes,
            args.graph_edges,
            args.population_access,
            args.policy,
            gate_b_commit=args.gate_b_commit.lower(),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"Gate F Gate B coverage rows: {len(frame)}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_GATE_B_BRIDGE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
