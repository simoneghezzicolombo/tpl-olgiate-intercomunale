from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fleet_audit import minimum_fleet_from_intervals, scheduled_fleet_from_directional_cycles  # noqa: E402
from src.service_math import GATE_E_V2_COLUMNS, ServiceMathError  # noqa: E402


def test_half_open_intervals_allow_same_instant_turnaround_without_double_count():
    assert minimum_fleet_from_intervals([(0, 60), (60, 120)]) == 1


def test_overlapping_cycles_require_multiple_vehicles():
    assert minimum_fleet_from_intervals([(0, 60), (30, 90), (60, 120)]) == 2


def test_invalid_cycle_interval_is_rejected():
    with pytest.raises(ServiceMathError):
        minimum_fleet_from_intervals([(60, 60)])


def test_actual_hourly_each_direction_with_60_min_cycle_needs_two_direction_locked():
    result = scheduled_fleet_from_directional_cycles(
        ["06:00:00", "07:00:00", "08:00:00"], 60,
        ["06:30:00", "07:30:00", "08:30:00"], 60,
    )
    assert result["minimum_scheduled_vehicles_CW_direction_locked"] == 1
    assert result["minimum_scheduled_vehicles_CCW_direction_locked"] == 1
    assert result["minimum_scheduled_vehicles_direction_locked_total"] == 2
    assert result["minimum_scheduled_vehicles_hub_interlining_allowed"] == 2


def test_actual_30min_each_direction_with_60min_cycle_needs_four_even_if_interlined():
    result = scheduled_fleet_from_directional_cycles(
        ["06:00:00", "06:30:00", "07:00:00", "07:30:00"], 60,
        ["06:15:00", "06:45:00", "07:15:00", "07:45:00"], 60,
    )
    assert result["minimum_scheduled_vehicles_direction_locked_total"] == 4
    assert result["minimum_scheduled_vehicles_hub_interlining_allowed"] == 4


def test_non_overlapping_directional_cycles_can_create_interlining_saving():
    # One vehicle can alternate CW and CCW because every next departure is at
    # or after the previous 50-minute cycle returns to the hub. Each direction
    # considered in isolation still needs one vehicle, so direction-locking
    # would require two.
    result = scheduled_fleet_from_directional_cycles(
        ["06:00:00", "07:40:00"], 50,
        ["06:50:00", "08:30:00"], 50,
    )
    assert result["minimum_scheduled_vehicles_direction_locked_total"] == 2
    assert result["minimum_scheduled_vehicles_hub_interlining_allowed"] == 1
    assert result["potential_interlining_saving_vs_direction_locked"] == 1


def test_overlapping_cross_direction_cycles_do_not_claim_false_interlining_saving():
    result = scheduled_fleet_from_directional_cycles(
        ["06:00:00", "07:00:00"], 50,
        ["06:50:00", "07:50:00"], 50,
    )
    assert result["minimum_scheduled_vehicles_direction_locked_total"] == 2
    assert result["minimum_scheduled_vehicles_hub_interlining_allowed"] == 2
    assert result["potential_interlining_saving_vs_direction_locked"] == 0


def write_gate_e(path, cycles=3):
    rows = []
    for direction in ("CW", "CCW"):
        row = {column: "" for column in GATE_E_V2_COLUMNS}
        row.update({
            "contract_version": "GATE_E_V2", "scenario_id": "S", "service_day_group": "WEEKDAY",
            "band_id": "AM", "band_start_time": "06:00:00", "band_end_time": "09:00:00",
            "direction": direction, "analysis_mode": "PRODUCTION", "upstream_gate_c_status": "PASS",
            "upstream_gate_d_status": "PASS", "gate_c_artifact": "c.csv", "gate_c_commit": "c123",
            "gate_d_artifact": "d.csv", "gate_d_commit": "d123", "shared_stop_pattern_status": "CONFIRMED",
            "route_km": "10", "route_km_status": "DERIVED", "pure_running_min": "50",
            "pure_running_status": "DERIVED", "dwell_min": "5", "dwell_status": "DERIVED",
            "recovery_min": "5", "recovery_status": "DERIVED", "target_headway_min": "60",
            "target_headway_status": "DERIVED", "daily_cycles": str(cycles), "daily_cycles_status": "DERIVED",
            "service_days_year": "300", "service_days_status": "DERIVED",
        })
        rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GATE_E_V2_COLUMNS); w.writeheader(); w.writerows(rows)


def write_departures(path, n=3):
    header = [
        "scenario_id", "service_day_group", "band_id", "stop_id", "direction", "departure_time",
        "analysis_mode", "epistemic_status", "upstream_gate_c_status", "gate_c_artifact",
        "gate_c_commit", "shared_stop_pattern_status",
    ]
    times = {
        "CW": ["06:00:00", "07:00:00", "08:00:00"][:n],
        "CCW": ["06:30:00", "07:30:00", "08:30:00"][:n],
    }
    rows = []
    for direction in ("CW", "CCW"):
        for t in times[direction]:
            rows.append({
                "scenario_id": "S", "service_day_group": "WEEKDAY", "band_id": "AM", "stop_id": "HUB",
                "direction": direction, "departure_time": t, "analysis_mode": "PRODUCTION",
                "epistemic_status": "DERIVED", "upstream_gate_c_status": "PASS",
                "gate_c_artifact": "c.csv", "gate_c_commit": "c123", "shared_stop_pattern_status": "CONFIRMED",
            })
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header); w.writeheader(); w.writerows(rows)


def test_fleet_runner_uses_actual_hub_departures_and_validated_cycle(tmp_path):
    gate_e, deps, out = tmp_path / "e.csv", tmp_path / "deps.csv", tmp_path / "fleet.csv"
    write_gate_e(gate_e, cycles=3); write_departures(deps, n=3)
    proc = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts/gate_e_fleet_audit.py"), "--gate-e-input", str(gate_e),
            "--departures", str(deps), "--hub-stop-id", "HUB", "--output", str(out),
        ], cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["fleet_evidence_status"] == "ELIGIBLE_FOR_GATE_E_SCHEDULED_FLEET_EVIDENCE"
    assert row["minimum_scheduled_vehicles_direction_locked_total"] == "2"
    assert row["minimum_scheduled_vehicles_hub_interlining_allowed"] == "2"


def test_fleet_runner_rejects_departure_count_daily_cycle_mismatch(tmp_path):
    gate_e, deps, out = tmp_path / "e.csv", tmp_path / "deps.csv", tmp_path / "fleet.csv"
    write_gate_e(gate_e, cycles=3); write_departures(deps, n=2)
    proc = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts/gate_e_fleet_audit.py"), "--gate-e-input", str(gate_e),
            "--departures", str(deps), "--hub-stop-id", "HUB", "--output", str(out),
        ], cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 1
    assert "does not match daily_cycles" in proc.stderr
    assert not out.exists()
