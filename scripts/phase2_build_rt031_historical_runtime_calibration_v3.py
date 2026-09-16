#!/usr/bin/env python3
"""Build a bounded historical scheduled-speed calibration audit."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_historical_runtime_calibration_v3 import (
    candidate_component_speed_audit,
    historical_scheduled_metrics,
)

TYPED_FULL_SHA256 = "a221b2e467d7266f1aaf615f62ca8c76177ddcc83626da454be5743da59f61bc"
GTFS_HASHES = {
    "routes.txt": "a59e48ac22ba0d71215be926818e368bb37a58531256b1b74850b6b9e2624583",
    "trips.txt": "ff3005d3831bf14ce1a7965b3d746c278f3392d67b163d6be61a28a9644903bb",
    "stop_times.txt": "c5b4a6f98935893c916281b58f1a7384e500ffe3800dac11f68550043cea5709",
    "feed_info.txt": "a45d751ea105ab23122d928eeb96e885b71dc18b680b0763825cbb7c20a63030",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def main(args):
    if sha256(args.typed_full) != TYPED_FULL_SHA256:
        raise ValueError("pinned typed full evidence drift")
    for name, digest in GTFS_HASHES.items():
        if sha256(args.gtfs_dir / name) != digest:
            raise ValueError(f"pinned historical GTFS drift: {name}")
    feed = read_csv(args.gtfs_dir / "feed_info.txt")
    if len(feed) != 1 or feed[0]["feed_end_date"] != "20260608":
        raise ValueError("historical GTFS validity boundary changed")
    typed = json.loads(args.typed_full.read_text(encoding="utf-8"))
    if typed.get("profile_count") != 5 or typed.get("network_selected") is not False:
        raise ValueError("typed development evidence changed")
    historical = historical_scheduled_metrics(
        read_csv(args.gtfs_dir / "trips.txt"),
        read_csv(args.gtfs_dir / "stop_times.txt"))
    components = candidate_component_speed_audit(typed["profiles"], historical)
    if historical["trip_count"] != 42 or historical["stop_time_occurrence_count"] != 541:
        raise ValueError("historical D184/D185 inventory changed")
    output = {
        "contract": "RT031_HISTORICAL_SCHEDULED_RUNTIME_CALIBRATION_V3",
        "status": "PASS_SCHEDULED_SPEED_PLAUSIBILITY_DWELL_UNRESOLVED",
        "historical_feed_valid_to": "2026-06-08",
        "historical_feed_role": "BOUNDED_SCHEDULED_CALIBRATION_NOT_CURRENT_SERVICE_OR_OBSERVED_RUNTIME",
        "historical": historical,
        "candidate_component_count": len(components),
        "candidate_components": components,
        "all_candidate_source_model_speeds_within_historical_scheduled_envelope": all(
            row["within_historical_comparable_scheduled_speed_envelope"]
            for row in components),
        "dwell_calibration_available": historical["dwell_calibration_available"],
        "arrival_equals_departure_may_be_interpreted_as_observed_zero_dwell": False,
        "observed_runtime_available": False,
        "empirical_reliability_available": False,
        "may_replace_source_model_runtime_with_historical_median": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {"typed_full": TYPED_FULL_SHA256, **GTFS_HASHES},
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "rt031_historical_runtime_calibration_v3.json"
    path.write_bytes(canonical(output))
    audit = {key: value for key, value in output.items()
             if key not in {"historical", "candidate_components"}}
    audit["result_sha256"] = sha256(path)
    (args.output_dir / "rt031_historical_runtime_calibration_v3_audit.json").write_bytes(
        canonical(audit))
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--typed-full", type=Path, required=True)
    parser.add_argument("--gtfs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
