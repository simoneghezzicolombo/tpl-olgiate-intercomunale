#!/usr/bin/env python3
"""Build Gate F v2 structural-road fragment from Gate D v2 handoff."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_gate_d_adapter import adapt_gate_d_handoff  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--gate-d-commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        frame = adapt_gate_d_handoff(args.input, gate_d_commit=args.gate_d_commit.lower())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"Gate F Gate D fragment rows: {len(frame)}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_GATE_D_ADAPTER_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
