#!/usr/bin/env python3
"""Build scenario-specific S8 connection evidence for Gate F."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_s8_bridge import build_s8_fragment  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gate-c-s8", type=Path, required=True)
    p.add_argument("--bus-events", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        frame = build_s8_fragment(args.gate_c_s8, args.bus_events, args.policy)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"Gate F S8 connection rows: {len(frame)}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_S8_BRIDGE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
