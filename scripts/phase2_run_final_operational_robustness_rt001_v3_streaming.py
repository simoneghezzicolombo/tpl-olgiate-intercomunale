#!/usr/bin/env python3
"""Memory-bounded entrypoint for the Stage-E RT001 V3 adapter runner."""
from __future__ import annotations

import csv
import gzip
from pathlib import Path

import scripts.phase2_run_final_operational_robustness_rt001_v3 as runner


def streaming_rewrite_with_dual_identity(
    src: Path,
    dst: Path,
    parent_by_timetable: dict[str, str],
) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(src, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        if "stage_d_input_id" not in fields:
            raise ValueError(f"engine output lacks internal timetable identity: {src}")
        final_fields = ["selected_timetable_id", "stage_d_input_id"] + [
            field for field in fields if field != "stage_d_input_id"
        ]
        raw, text, writer = runner.deterministic_gzip_writer(dst, final_fields)
        try:
            for row in reader:
                timetable_id = str(row["stage_d_input_id"])
                parent_id = parent_by_timetable.get(timetable_id)
                if parent_id is None:
                    raise ValueError(
                        f"engine output references unknown selected timetable {timetable_id}"
                    )
                out = {
                    "selected_timetable_id": timetable_id,
                    "stage_d_input_id": parent_id,
                }
                out.update({key: value for key, value in row.items() if key != "stage_d_input_id"})
                writer.writerow(out)
        finally:
            runner.close_writer(raw, text)


def main() -> int:
    original = runner.rewrite_with_dual_identity
    try:
        runner.rewrite_with_dual_identity = streaming_rewrite_with_dual_identity
        return runner.main()
    finally:
        runner.rewrite_with_dual_identity = original


if __name__ == "__main__":
    raise SystemExit(main())
