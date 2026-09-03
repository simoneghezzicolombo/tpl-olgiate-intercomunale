#!/usr/bin/env python3
"""Derive scheduled runtime distributions for D184/D185 from official GTFS.

This is calibration evidence for Gate D/E. It does not claim observed traffic
running time and it does not use legacy manually authored runtime constants.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import ServiceMathError, parse_gtfs_time_to_minutes  # noqa: E402

ROUTES = {"D184", "D185"}
TRIPS_REQUIRED = {"route_id", "trip_id", "trip_headsign", "direction_id"}
STOP_TIMES_REQUIRED = {"trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"}


def read_dicts(path: Path, required: set[str], label: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"{label} missing columns: {sorted(missing)}")
        rows = [dict(row) for row in reader]
    if not rows:
        raise ServiceMathError(f"{label} contains no rows")
    return rows


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ServiceMathError("cannot compute percentile of empty values")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    fraction = position - lo
    return ordered[lo] * (1 - fraction) + ordered[hi] * fraction


def derive_trip_runtimes(trips: list[dict[str, str]], stop_times: list[dict[str, str]]) -> list[dict[str, object]]:
    trip_meta = {
        r["trip_id"].strip(): r for r in trips
        if r["route_id"].strip() in ROUTES and r["trip_id"].strip()
    }
    if not trip_meta:
        raise ServiceMathError("no D184/D185 trips found")
    by_trip: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stop_times:
        tid = row["trip_id"].strip()
        if tid in trip_meta:
            by_trip[tid].append(row)

    out: list[dict[str, object]] = []
    for trip_id, meta in sorted(trip_meta.items()):
        rows = by_trip.get(trip_id, [])
        if len(rows) < 2:
            continue
        try:
            ordered = sorted(rows, key=lambda r: int(r["stop_sequence"]))
        except ValueError as exc:
            raise ServiceMathError(f"{trip_id}: non-integer stop_sequence") from exc
        first, last = ordered[0], ordered[-1]
        start_raw = first["departure_time"].strip() or first["arrival_time"].strip()
        end_raw = last["arrival_time"].strip() or last["departure_time"].strip()
        start = parse_gtfs_time_to_minutes(start_raw)
        end = parse_gtfs_time_to_minutes(end_raw)
        runtime = end - start
        if runtime <= 0:
            raise ServiceMathError(f"{trip_id}: non-positive scheduled runtime {runtime}")
        out.append({
            "route_id": meta["route_id"].strip(),
            "direction_id": meta["direction_id"].strip(),
            "trip_headsign": meta["trip_headsign"].strip(),
            "trip_id": trip_id,
            "origin_stop_id": first["stop_id"].strip(),
            "destination_stop_id": last["stop_id"].strip(),
            "scheduled_runtime_min": runtime,
        })
    if not out:
        raise ServiceMathError("no complete D184/D185 trip runtimes could be derived")
    return out


def aggregate_runtimes(trip_rows: list[dict[str, object]], *, source_commit: str, trips_artifact: str, stop_times_artifact: str) -> list[dict[str, object]]:
    if not source_commit.strip():
        raise ServiceMathError("source commit lineage is required")
    grouped: dict[tuple[str, str, str, str, str], list[float]] = defaultdict(list)
    for row in trip_rows:
        key = (
            str(row["route_id"]), str(row["direction_id"]), str(row["trip_headsign"]),
            str(row["origin_stop_id"]), str(row["destination_stop_id"]),
        )
        grouped[key].append(float(row["scheduled_runtime_min"]))
    result = []
    for key, values in sorted(grouped.items()):
        result.append({
            "route_id": key[0], "direction_id": key[1], "trip_headsign": key[2],
            "origin_stop_id": key[3], "destination_stop_id": key[4],
            "n_gtfs_trips": len(values),
            "scheduled_runtime_min_min": min(values),
            "scheduled_runtime_min_p10": percentile(values, 0.10),
            "scheduled_runtime_min_median": statistics.median(values),
            "scheduled_runtime_min_p90": percentile(values, 0.90),
            "scheduled_runtime_min_max": max(values),
            "scheduled_runtime_min_mean": statistics.fmean(values),
            "epistemic_status": "DERIVED",
            "runtime_semantics": "SCHEDULED_GTFS_ENDPOINT_TO_ENDPOINT_NOT_OBSERVED_TRAFFIC_TIME",
            "calibration_use": "REFERENCE_DISTRIBUTION_FOR_GATE_D_MODEL_CALIBRATION",
            "source_commit": source_commit,
            "trips_artifact": trips_artifact,
            "stop_times_artifact": stop_times_artifact,
        })
    return result


def write(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ServiceMathError("refusing to write empty runtime benchmark")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trips", type=Path, required=True)
    p.add_argument("--stop-times", type=Path, required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        trips = read_dicts(args.trips, TRIPS_REQUIRED, "trips.txt")
        stop_times = read_dicts(args.stop_times, STOP_TIMES_REQUIRED, "stop_times.txt")
        trip_rows = derive_trip_runtimes(trips, stop_times)
        rows = aggregate_runtimes(
            trip_rows, source_commit=args.source_commit,
            trips_artifact=str(args.trips), stop_times_artifact=str(args.stop_times),
        )
        write(args.output, rows)
        print(f"GTFS runtime calibration groups: {len(rows)}")
        print(f"GTFS complete D184/D185 trips: {len(trip_rows)}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_GTFS_RUNTIME_BENCHMARK_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
