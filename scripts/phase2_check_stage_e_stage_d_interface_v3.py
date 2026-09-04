#!/usr/bin/env python3
"""Validate that an exact Stage-D output is unambiguous for Stage E consumption."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

from src.phase2_stage_e_stage_d_interface_v3 import validate_exact_interface


def _read_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    kwargs = {"mode": "rt", "encoding": "utf-8", "newline": ""} if path.suffix == ".gz" else {"mode": "r", "encoding": "utf-8", "newline": ""}
    with opener(path, **kwargs) as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    return fields, rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--validation", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--trips", type=Path, required=True)
    p.add_argument("--contexts", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--input-role", default="UNSPECIFIED_STAGE_D_INPUT_ROLE")
    args = p.parse_args()

    for path in (args.validation, args.summary, args.trips):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.contexts is not None and not args.contexts.is_file():
        raise FileNotFoundError(args.contexts)

    validation = json.loads(args.validation.read_text(encoding="utf-8"))
    summary_fields, summary_rows = _read_rows(args.summary)
    trip_fields, trip_rows = _read_rows(args.trips)
    context_fields = None
    context_rows = None
    if args.contexts is not None:
        context_fields, context_rows = _read_rows(args.contexts)

    report = validate_exact_interface(
        validation,
        summary_rows,
        trip_rows,
        summary_fields=summary_fields,
        trip_fields=trip_fields,
        context_rows=context_rows,
        context_fields=context_fields,
    )
    report.update({
        "status": "PASS_PHASE2_STAGE_E_STAGE_D_INTERFACE_V3_READINESS",
        "contract": "PHASE2_STAGE_E_EXACT_TIMETABLE_INTERFACE_NO_CONTEXT_COLLAPSE_V3",
        "input_role": args.input_role,
        "stage_e_algorithm_changed": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "weighted_composite_score": False,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
