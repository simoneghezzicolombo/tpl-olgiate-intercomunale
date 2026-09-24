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

from phase2_candidate_accessibility_pareto_v4 import readiness_audit


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Validate RT-029 E4+E5+E6 upstream compatibility without running Pareto before "
            "the certified passenger-stop realization artifact exists."
        )
    )
    ap.add_argument("--e4-structures", type=Path, required=True)
    ap.add_argument("--e5-structures", type=Path, required=True)
    ap.add_argument("--e6-structures", type=Path, required=True)
    ap.add_argument("--realizations", type=Path, required=True)
    ap.add_argument("--walk-matrix", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    inputs = {
        "rt022_e4_structures": args.e4_structures,
        "rt024_e5_structures": args.e5_structures,
        "rt025_e6_structures": args.e6_structures,
        "rt023_realization_catalog": args.realizations,
        "rt028_final_walk_matrix": args.walk_matrix,
    }
    lineage = {f"{name}_sha256": _sha256(path) for name, path in inputs.items()}
    audit = readiness_audit(
        structure_layers={
            4: pd.read_csv(args.e4_structures, encoding="utf-8"),
            5: pd.read_csv(args.e5_structures, encoding="utf-8"),
            6: pd.read_csv(args.e6_structures, encoding="utf-8"),
        },
        rt023_realizations=pd.read_csv(args.realizations, encoding="utf-8"),
        walk_matrix=pd.read_csv(args.walk_matrix, encoding="utf-8"),
        lineage=lineage,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
