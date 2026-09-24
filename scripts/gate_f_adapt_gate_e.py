#!/usr/bin/env python3
"""Build the Gate F v2 service fragment from validated Gate E V2 outputs."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_gate_e_adapter import adapt_gate_e_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--bands", type=Path, required=True)
    parser.add_argument("--fleet", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--gate-e-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        frame = adapt_gate_e_outputs(
            args.scenario,
            args.bands,
            args.fleet,
            args.policy,
            gate_e_commit=args.gate_e_commit.lower(),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"Gate F v2 Gate E fragment rows: {len(frame)}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_GATE_E_ADAPTER_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
