#!/usr/bin/env python3
"""Compare two persisted Stage-D RT001 V3 implementations semantically."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

from src.phase2_stage_d_v3_cross_audit import Dataset, compare_datasets


def read_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    kwargs = {"mode": "rt", "encoding": "utf-8", "newline": ""} if path.suffix == ".gz" else {"mode": "r", "encoding": "utf-8", "newline": ""}
    with opener(path, **kwargs) as handle:
        return list(csv.DictReader(handle))


def add_dataset_args(parser, prefix: str) -> None:
    parser.add_argument(f"--{prefix}-label", required=True)
    parser.add_argument(f"--{prefix}-validation", type=Path, required=True)
    parser.add_argument(f"--{prefix}-contexts", type=Path, required=True)
    parser.add_argument(f"--{prefix}-timetables", type=Path, required=True)
    parser.add_argument(f"--{prefix}-trips", type=Path, required=True)


def load_dataset(args, prefix: str) -> Dataset:
    validation = getattr(args, f"{prefix}_validation")
    contexts = getattr(args, f"{prefix}_contexts")
    timetables = getattr(args, f"{prefix}_timetables")
    trips = getattr(args, f"{prefix}_trips")
    for path in (validation, contexts, timetables, trips):
        if not path.is_file():
            raise FileNotFoundError(path)
    return Dataset(
        label=getattr(args, f"{prefix}_label"),
        validation=json.loads(validation.read_text(encoding="utf-8")),
        contexts=read_rows(contexts),
        timetables=read_rows(timetables),
        trips=read_rows(trips),
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_dataset_args(p, "a")
    add_dataset_args(p, "b")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--require-equivalent", action="store_true")
    args = p.parse_args()

    result = compare_datasets(load_dataset(args, "a"), load_dataset(args, "b"))
    result.update({
        "status": "PASS_PHASE2_STAGE_D_V3_CROSS_IMPLEMENTATION_EQUIVALENCE" if result["equivalent"] else "FAIL_PHASE2_STAGE_D_V3_CROSS_IMPLEMENTATION_EQUIVALENCE",
        "contract": "PHASE2_STAGE_D_RT001_V3_INDEPENDENT_SEMANTIC_EQUIVALENCE_AUDIT",
        "weighted_composite_score": False,
        "primary_selected": False,
        "runner_up_selected": False,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_equivalent and not result["equivalent"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
