#!/usr/bin/env python3
"""Materialise the Phase-2 Reduced Path Matrix V2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.phase2_reduced_path_matrix_v2 import materialize_reduced_path_matrix_v2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-dir", default="outputs/phase2/frozen_gate_d")
    parser.add_argument(
        "--existing-stops",
        default="outputs/phase2/stop_universe_v2/existing_official_stops.csv",
    )
    parser.add_argument(
        "--proposed-stops",
        default="outputs/phase2/stop_universe_v2/proposed_stop_candidates.csv",
    )
    parser.add_argument(
        "--stop-universe-validation",
        default="outputs/phase2/stop_universe_v2/stop_universe_v2_validation.json",
    )
    parser.add_argument("--output-dir", default="outputs/phase2/reduced_path_matrix_v2")
    args = parser.parse_args()

    validation = materialize_reduced_path_matrix_v2(
        frozen_dir=Path(args.frozen_dir),
        existing_stops_path=Path(args.existing_stops),
        proposed_stops_path=Path(args.proposed_stops),
        stop_universe_validation_path=Path(args.stop_universe_validation),
        output_dir=Path(args.output_dir),
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
