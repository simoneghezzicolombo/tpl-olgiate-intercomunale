#!/usr/bin/env python3
"""Materialise routing anchors and the directed Phase 2 stop/path matrix."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_reduced_path_matrix import materialize_reduced_path_matrix


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frozen-dir",
        type=Path,
        default=Path("outputs/phase2/frozen_gate_d"),
    )
    parser.add_argument(
        "--existing-stops",
        type=Path,
        default=Path("outputs/phase2/existing_official_stops.csv"),
    )
    parser.add_argument(
        "--proposed-stops",
        type=Path,
        default=Path("outputs/phase2/proposed_stop_candidates.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/phase2"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    validation = materialize_reduced_path_matrix(
        frozen_dir=args.frozen_dir,
        existing_stops_path=args.existing_stops,
        proposed_stops_path=args.proposed_stops,
        output_dir=args.output_dir,
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
