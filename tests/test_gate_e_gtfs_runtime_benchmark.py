from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.gate_e_gtfs_runtime_benchmark import (  # noqa: E402
    aggregate_runtimes,
    derive_trip_runtimes,
    percentile,
)
from src.service_math import ServiceMathError  # noqa: E402


def trips_fixture():
    return [
        {"route_id": "D184", "trip_id": "a", "trip_headsign": "Ravellino", "direction_id": "0"},
        {"route_id": "D184", "trip_id": "b", "trip_headsign": "Ravellino", "direction_id": "0"},
        {"route_id": "D185", "trip_id": "c", "trip_headsign": "Olgiate", "direction_id": "1"},
        {"route_id": "OTHER", "trip_id": "x", "trip_headsign": "X", "direction_id": "0"},
    ]


def stop_times_fixture():
    rows = []
    for tid, start, end, origin, destination in (
        ("a", "06:00:00", "06:30:00", "O", "R"),
        ("b", "07:00:00", "07:40:00", "O", "R"),
        ("c", "23:50:00", "24:25:00", "C", "O"),
    ):
        rows.extend([
            {"trip_id": tid, "arrival_time": start, "departure_time": start, "stop_id": origin, "stop_sequence": "1"},
            {"trip_id": tid, "arrival_time": end, "departure_time": end, "stop_id": destination, "stop_sequence": "2"},
        ])
    return rows


def test_derives_endpoint_runtime_and_supports_after_midnight_gtfs_time():
    rows = derive_trip_runtimes(trips_fixture(), stop_times_fixture())
    by_id = {r["trip_id"]: r for r in rows}
    assert by_id["a"]["scheduled_runtime_min"] == 30
    assert by_id["b"]["scheduled_runtime_min"] == 40
    assert by_id["c"]["scheduled_runtime_min"] == 35
    assert "x" not in by_id


def test_aggregation_keeps_endpoint_pattern_separate():
    trip_rows = derive_trip_runtimes(trips_fixture(), stop_times_fixture())
    rows = aggregate_runtimes(
        trip_rows, source_commit="abc", trips_artifact="trips.txt", stop_times_artifact="stop_times.txt"
    )
    d184 = next(r for r in rows if r["route_id"] == "D184")
    assert d184["n_gtfs_trips"] == 2
    assert d184["scheduled_runtime_min_min"] == 30
    assert d184["scheduled_runtime_min_median"] == 35
    assert d184["scheduled_runtime_min_max"] == 40
    assert d184["epistemic_status"] == "DERIVED"
    assert "NOT_OBSERVED" in d184["runtime_semantics"]


def test_percentile_is_deterministic_and_interpolated():
    assert percentile([10, 20, 30], 0.5) == 20
    assert percentile([10, 20], 0.5) == 15


def test_nonpositive_trip_runtime_is_rejected():
    bad = stop_times_fixture()
    bad[1] = {**bad[1], "arrival_time": "05:59:00", "departure_time": "05:59:00"}
    with pytest.raises(ServiceMathError, match="non-positive"):
        derive_trip_runtimes(trips_fixture(), bad)


def test_aggregation_requires_source_commit_lineage():
    rows = derive_trip_runtimes(trips_fixture(), stop_times_fixture())
    with pytest.raises(ServiceMathError, match="commit"):
        aggregate_runtimes(rows, source_commit="", trips_artifact="t", stop_times_artifact="s")


def write_fixtures(trips_path, stop_path):
    with trips_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["route_id", "trip_id", "trip_headsign", "direction_id"])
        w.writeheader(); w.writerows(trips_fixture())
    with stop_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])
        w.writeheader(); w.writerows(stop_times_fixture())


def test_cli_writes_calibration_reference_not_observed_runtime_claim(tmp_path):
    trips, stops, out = tmp_path / "trips.txt", tmp_path / "stop_times.txt", tmp_path / "runtime.csv"
    write_fixtures(trips, stops)
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts/gate_e_gtfs_runtime_benchmark.py"),
        "--trips", str(trips), "--stop-times", str(stops), "--source-commit", "abc123", "--output", str(out),
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows
    assert all(r["calibration_use"] == "REFERENCE_DISTRIBUTION_FOR_GATE_D_MODEL_CALIBRATION" for r in rows)
    assert all("NOT_OBSERVED" in r["runtime_semantics"] for r in rows)
