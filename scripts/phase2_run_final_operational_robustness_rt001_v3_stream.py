#!/usr/bin/env python3
"""Memory-safe entry point for the Stage-E RT001 V3 adapter.

Only the legacy-output identity-column relabelling is replaced.  Rows are
streamed one at a time; the certified Stage-E engine and all robustness
calculations are untouched.
"""
from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path

import scripts.phase2_run_final_operational_robustness_rt001_v3 as target


def rewrite_engine_outputs_streaming(temp_out: Path, final_out: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for source_name, final_name in target.FINAL_FILES.items():
        source = temp_out / source_name
        destination = final_out / final_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as src:
            reader = csv.DictReader(src)
            fields = list(reader.fieldnames or [])
            if "stage_d_input_id" not in fields:
                raise ValueError(f"legacy Stage-E output lacks exact-unit identity: {source_name}")
            new_fields = ["selected_timetable_id" if f == "stage_d_input_id" else f for f in fields]
            with destination.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
                    with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                        writer = csv.DictWriter(text, fieldnames=new_fields, lineterminator="\n", extrasaction="raise")
                        writer.writeheader()
                        for row in reader:
                            writer.writerow({
                                "selected_timetable_id" if field == "stage_d_input_id" else field: row[field]
                                for field in fields
                            })
                            row_count += 1
        if row_count == 0:
            raise ValueError(f"empty Stage-E engine output {source_name}")
        hashes[final_name] = target.sha256_path(destination)
    return hashes


def main() -> int:
    original = target.rewrite_engine_outputs
    target.rewrite_engine_outputs = rewrite_engine_outputs_streaming
    try:
        return target.main()
    finally:
        target.rewrite_engine_outputs = original


if __name__ == "__main__":
    raise SystemExit(main())
