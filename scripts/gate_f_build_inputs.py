#!/usr/bin/env python3
"""Build the canonical Gate F scenario table from upstream gate fragments."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gate_f_inputs import assemble_gate_f_inputs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--gate-b", required=True, type=Path)
    parser.add_argument("--gate-c", required=True, type=Path)
    parser.add_argument("--gate-d", required=True, type=Path)
    parser.add_argument("--gate-e", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/gate_f_scenario_metrics.csv"))
    parser.add_argument("--exclusions-output", type=Path, default=Path("outputs/gate_f/excluded_scenarios.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        eligible, excluded = assemble_gate_f_inputs(
            args.catalog, args.gate_b, args.gate_c, args.gate_d, args.gate_e
        )
    except (OSError, ValueError) as exc:
        print(f"GATE_F_INPUT_FAIL: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    eligible.to_csv(args.output, index=False)
    args.exclusions_output.parent.mkdir(parents=True, exist_ok=True)
    excluded.to_csv(args.exclusions_output, index=False)
    print(f"Gate F canonical scenario table written: {args.output} ({len(eligible)} eligible)")
    print(f"Gate F exclusions written: {args.exclusions_output} ({len(excluded)} excluded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
