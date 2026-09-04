#!/usr/bin/env python3
"""Memory-safe, contract-preserving entry point for Stage-E RT001 V3.

The certified Stage-E robustness calculations are untouched.  This entry point
only performs two interface operations required by the repaired Stage-D V3
contract:

1. public BUS->RAIL return events are retained only inside the declared service
   span, matching the Stage-D V3 START_INCLUSIVE_END_EXCLUSIVE semantics;
2. legacy engine output identity is relabelled from its internal
   ``stage_d_input_id`` alias to the real ``selected_timetable_id`` in a
   streaming, memory-safe pass.
"""
from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path

import scripts.phase2_run_final_operational_robustness_rt001_v3 as target


def _deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    return raw, text, writer


def materialise_compatibility_inputs_in_span(args, temp: Path, stage_d):
    """Reuse the tested V3 schema adapter, then enforce Stage-D span semantics."""
    summary_path, trip_path, tables, context_count = target.materialise_compatibility_inputs(
        args, temp, stage_d
    )

    span_by_exact: dict[str, tuple[float, float]] = {
        tid: (float(row["span_start_min"]), float(row["span_end_min"]))
        for tid, row in tables.items()
    }
    rewritten = temp / "stage_e_normalized_exact_trips_in_span.csv.gz"
    row_count = 0
    with gzip.open(trip_path, "rt", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        fields = list(reader.fieldnames or [])
        raw, text, writer = _deterministic_gzip_writer(rewritten, fields)
        try:
            for row in reader:
                exact_id = str(row["stage_d_input_id"])
                if exact_id not in span_by_exact:
                    raise ValueError(f"normalized trip references unknown exact timetable {exact_id!r}")
                public_return = str(row.get("public_hub_return_min", "")).strip()
                if public_return:
                    value = float(public_return)
                    start, end = span_by_exact[exact_id]
                    if not (start <= value < end):
                        row["public_hub_return_min"] = ""
                writer.writerow(row)
                row_count += 1
        finally:
            text.flush()
            text.close()
            raw.close()
    if row_count == 0:
        raise ValueError("normalized Stage-D V3 trip input is empty")
    return summary_path, rewritten, tables, context_count


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
            raw, text, writer = _deterministic_gzip_writer(destination, new_fields)
            try:
                for row in reader:
                    writer.writerow({
                        "selected_timetable_id" if field == "stage_d_input_id" else field: row[field]
                        for field in fields
                    })
                    row_count += 1
            finally:
                text.flush()
                text.close()
                raw.close()
        if row_count == 0:
            raise ValueError(f"empty Stage-E engine output {source_name}")
        hashes[final_name] = target.sha256_path(destination)
    return hashes


def main() -> int:
    original_rewrite = target.rewrite_engine_outputs
    original_materialise = target.materialise_compatibility_inputs
    target.rewrite_engine_outputs = rewrite_engine_outputs_streaming
    # The wrapper calls target.materialise_compatibility_inputs internally, so
    # preserve the original through a closure to avoid recursion.
    def materialise(args, temp, stage_d):
        target.materialise_compatibility_inputs = original_materialise
        try:
            return materialise_compatibility_inputs_in_span(args, temp, stage_d)
        finally:
            target.materialise_compatibility_inputs = materialise

    target.materialise_compatibility_inputs = materialise
    try:
        return target.main()
    finally:
        target.rewrite_engine_outputs = original_rewrite
        target.materialise_compatibility_inputs = original_materialise


if __name__ == "__main__":
    raise SystemExit(main())
