#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phase2_candidate_accessibility_pareto_v3 import compile_rt029, write_outputs


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Evaluate the 88 frozen RT-022 structures on certified RT-023/RT-028 evidence."
    )
    ap.add_argument("--structures", type=Path, required=True)
    ap.add_argument("--structure-link-manifest", type=Path, required=True)
    ap.add_argument("--realizations", type=Path, required=True)
    ap.add_argument("--walk-matrix", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--expected-structures", type=int, default=88)
    ap.add_argument("--expected-core-municipalities", type=int, default=5)
    args = ap.parse_args()

    inputs = {
        "rt022_structures": args.structures,
        "rt023_structure_link_manifest": args.structure_link_manifest,
        "rt023_realization_catalog": args.realizations,
        "rt028_walk_matrix": args.walk_matrix,
    }
    lineage = {f"{name}_sha256": _sha256(path) for name, path in inputs.items()}

    result = compile_rt029(
        structures=pd.read_csv(args.structures),
        structure_link_manifest=pd.read_csv(args.structure_link_manifest),
        realizations=pd.read_csv(args.realizations),
        walk_matrix=pd.read_csv(args.walk_matrix),
        expected_structure_count=args.expected_structures,
        expected_core_municipality_count=args.expected_core_municipalities,
        lineage=lineage,
    )
    write_outputs(result, args.output_dir)
    print(json.dumps(result.audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
