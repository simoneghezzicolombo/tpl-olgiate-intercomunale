from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_d_screen import screen_gate_d_metric_against_envelope  # noqa: E402
from src.service_math import ServiceMathError  # noqa: E402


def test_exact_threshold_is_compatible():
    row = screen_gate_d_metric_against_envelope(
        route_km=10, pure_running_min=50, maximum_route_km=10, maximum_pure_running_min=50
    )
    assert row["budget_distance_threshold_met"] is True
    assert row["runtime_threshold_met"] is True
    assert row["screen_classification"] == "WITHIN_ASSUMED_MATH_ENVELOPE"
    assert row["screen_status"] == "SENSITIVITY_ONLY_NOT_GATE_E_VERDICT"


def test_epsilon_over_runtime_threshold_fails_runtime_only():
    row = screen_gate_d_metric_against_envelope(
        route_km=9, pure_running_min=50.001, maximum_route_km=10, maximum_pure_running_min=50
    )
    assert row["budget_distance_threshold_met"] is True
    assert row["runtime_threshold_met"] is False
    assert row["screen_classification"] == "EXCEEDS_ASSUMED_RUNTIME_THRESHOLD"


def test_epsilon_over_budget_route_threshold_fails_budget_only():
    row = screen_gate_d_metric_against_envelope(
        route_km=10.001, pure_running_min=49, maximum_route_km=10, maximum_pure_running_min=50
    )
    assert row["budget_distance_threshold_met"] is False
    assert row["runtime_threshold_met"] is True
    assert row["screen_classification"] == "EXCEEDS_ASSUMED_BUDGET_ROUTE_THRESHOLD"


def test_exceeding_both_thresholds_is_distinct():
    row = screen_gate_d_metric_against_envelope(
        route_km=11, pure_running_min=51, maximum_route_km=10, maximum_pure_running_min=50
    )
    assert row["screen_classification"] == "EXCEEDS_ASSUMED_BUDGET_AND_RUNTIME_THRESHOLDS"


def test_screen_rejects_nonfinite_or_nonpositive_metrics():
    with pytest.raises(ServiceMathError):
        screen_gate_d_metric_against_envelope(
            route_km=float("nan"), pure_running_min=50, maximum_route_km=10, maximum_pure_running_min=50
        )
    with pytest.raises(ServiceMathError):
        screen_gate_d_metric_against_envelope(
            route_km=10, pure_running_min=0, maximum_route_km=10, maximum_pure_running_min=50
        )


def write_d(path):
    fields = [
        "scenario_id", "service_day_group", "band_id", "direction", "upstream_gate_d_status",
        "gate_d_artifact", "gate_d_commit", "route_km", "route_km_status", "pure_running_min",
        "pure_running_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerow({
            "scenario_id": "S", "service_day_group": "WEEKDAY", "band_id": "AM", "direction": "CW",
            "upstream_gate_d_status": "IN_PROGRESS", "gate_d_artifact": "d.csv", "gate_d_commit": "abc",
            "route_km": "9", "route_km_status": "DERIVED", "pure_running_min": "49",
            "pure_running_status": "MODEL OUTPUT",
        })


def write_env(path, status="ASSUMPTION"):
    fields = [
        "analysis_mode", "result_status", "headway_each_direction_min", "headway_status",
        "in_service_vehicles_each_direction", "vehicle_policy_status", "dwell_min", "dwell_status",
        "recovery_min", "recovery_status", "cycles_per_day_each_direction", "cycles_status",
        "service_days_year", "service_days_status", "maximum_pure_running_min_compatible_with_headway",
        "maximum_common_route_km_under_pdb_budget",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerow({
            "analysis_mode": "SENSITIVITY", "result_status": "SENSITIVITY_ONLY_NOT_PROJECT_RESULT",
            "headway_each_direction_min": "60", "headway_status": status,
            "in_service_vehicles_each_direction": "1", "vehicle_policy_status": status,
            "dwell_min": "4", "dwell_status": status, "recovery_min": "6", "recovery_status": status,
            "cycles_per_day_each_direction": "10", "cycles_status": status,
            "service_days_year": "300", "service_days_status": status,
            "maximum_pure_running_min_compatible_with_headway": "50",
            "maximum_common_route_km_under_pdb_budget": "10",
        })


def test_cli_cross_screen_is_explicitly_not_a_gate_e_verdict(tmp_path):
    d, env, out = tmp_path / "d.csv", tmp_path / "env.csv", tmp_path / "screen.csv"
    write_d(d); write_env(env)
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts/gate_e_screen_gate_d.py"),
        "--gate-d", str(d), "--envelope", str(env), "--output", str(out),
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["screen_status"] == "SENSITIVITY_ONLY_NOT_GATE_E_VERDICT"
    assert row["screen_classification"] == "WITHIN_ASSUMED_MATH_ENVELOPE"


def test_cli_rejects_envelope_that_hides_non_assumption_policy_input(tmp_path):
    d, env, out = tmp_path / "d.csv", tmp_path / "env.csv", tmp_path / "screen.csv"
    write_d(d); write_env(env, status="DERIVED")
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts/gate_e_screen_gate_d.py"),
        "--gate-d", str(d), "--envelope", str(env), "--output", str(out),
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 1
    assert "must be ASSUMPTION" in proc.stderr
    assert not out.exists()
