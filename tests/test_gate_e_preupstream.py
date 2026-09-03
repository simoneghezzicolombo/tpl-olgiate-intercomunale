from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import (  # noqa: E402
    GATE_E_V2_COLUMNS,
    ServiceMathError,
    annual_bus_km,
    combined_headway_rate_equivalent,
    cycle_minutes,
    minimum_vehicles_for_regular_headway,
)


def test_nonfinite_numbers_are_rejected():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ServiceMathError):
            annual_bus_km(value, 1, 1)
        with pytest.raises(ServiceMathError):
            minimum_vehicles_for_regular_headway(value, 60)


def test_zero_or_negative_headway_is_rejected():
    for value in (0, -1):
        with pytest.raises(ServiceMathError):
            combined_headway_rate_equivalent(60, value)


def test_zero_running_time_is_rejected_but_zero_dwell_recovery_are_valid():
    with pytest.raises(ServiceMathError):
        cycle_minutes(0, 0, 0)
    assert cycle_minutes(60, 0, 0) == 60


def test_schema_template_is_header_only_and_exact():
    path = ROOT / "schemas" / "gate_e_inputs_v2.csv"
    rows = list(csv.reader(path.open(encoding="utf-8")))
    assert len(rows) == 1
    assert tuple(rows[0]) == GATE_E_V2_COLUMNS


def test_sensitivity_script_requires_explicit_grid_inputs(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gate_e_sensitivity.py")],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode != 0
    assert "required" in proc.stderr.lower()


def test_sensitivity_outputs_are_never_labelled_project_results(tmp_path):
    budget_out = tmp_path / "budget.csv"
    fleet_out = tmp_path / "fleet.csv"
    proc = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "gate_e_sensitivity.py"),
            "--cycles-per-day-each-direction", "13",
            "--service-days", "303",
            "--cycle-minutes", "60",
            "--headways", "30,60",
            "--budget-output", str(budget_out),
            "--fleet-output", str(fleet_out),
        ],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    budget_rows = list(csv.DictReader(budget_out.open(encoding="utf-8")))
    fleet_rows = list(csv.DictReader(fleet_out.open(encoding="utf-8")))
    assert budget_rows[0]["result_status"] == "SENSITIVITY_ONLY_NOT_PROJECT_RESULT"
    assert budget_rows[0]["epistemic_status_cycles_per_day"] == "ASSUMPTION"
    assert fleet_rows[0]["result_status"] == "SENSITIVITY_ONLY_NOT_PROJECT_RESULT"
    assert {r["minimum_in_service_vehicles_CW_plus_CCW"] for r in fleet_rows} == {"2", "4"}


def test_sensitivity_break_even_uses_both_directions_in_cycle_count(tmp_path):
    budget_out = tmp_path / "budget.csv"
    fleet_out = tmp_path / "fleet.csv"
    subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "gate_e_sensitivity.py"),
            "--cycles-per-day-each-direction", "13",
            "--service-days", "303",
            "--cycle-minutes", "60",
            "--headways", "60",
            "--budget-output", str(budget_out),
            "--fleet-output", str(fleet_out),
        ], cwd=ROOT, check=True, text=True, capture_output=True,
    )
    row = next(csv.DictReader(budget_out.open(encoding="utf-8")))
    assert int(row["directional_cycles_year_total_CW_plus_CCW"]) == 13 * 303 * 2
    assert float(row["break_even_mean_route_km_per_directional_cycle"]) == pytest.approx(111419 / (13 * 303 * 2))


def write_rows(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def valid_handoff_rows():
    c, d = [], []
    for direction in ("CW", "CCW"):
        c.append({
            "scenario_id": "S", "service_day_group": "WEEKDAY", "band_id": "ALL", "direction": direction,
            "band_start_time": "06:00:00", "band_end_time": "19:00:00", "upstream_gate_c_status": "PASS",
            "gate_c_artifact": "c.csv", "gate_c_commit": "c123", "shared_stop_pattern_status": "CONFIRMED",
            "target_headway_min": "60", "target_headway_status": "DERIVED", "daily_cycles": "13",
            "daily_cycles_status": "DERIVED", "service_days_year": "300", "service_days_status": "DERIVED",
            "dwell_min": "5", "dwell_status": "DERIVED", "recovery_min": "5", "recovery_status": "DERIVED",
        })
        d.append({
            "scenario_id": "S", "service_day_group": "WEEKDAY", "band_id": "ALL", "direction": direction,
            "upstream_gate_d_status": "PASS", "gate_d_artifact": "d.csv", "gate_d_commit": "d123",
            "route_km": "10", "route_km_status": "DERIVED", "pure_running_min": "50", "pure_running_status": "DERIVED",
        })
    return c, d


def test_builder_joins_c_and_d_without_manual_result_transcription(tmp_path):
    from scripts.gate_e_build_input import C_COLUMNS, D_COLUMNS
    c, d = valid_handoff_rows()
    cp, dp, out = tmp_path / "c.csv", tmp_path / "d.csv", tmp_path / "e.csv"
    write_rows(cp, C_COLUMNS, c)
    write_rows(dp, D_COLUMNS, d)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gate_e_build_input.py"), "--gate-c", str(cp), "--gate-d", str(dp), "--output", str(out)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 2 and {r["direction"] for r in rows} == {"CW", "CCW"}
    assert all(r["gate_c_commit"] == "c123" and r["gate_d_commit"] == "d123" for r in rows)


def test_builder_rejects_unmatched_handoff_keys(tmp_path):
    from scripts.gate_e_build_input import C_COLUMNS, D_COLUMNS
    c, d = valid_handoff_rows()
    d.pop()
    cp, dp, out = tmp_path / "c.csv", tmp_path / "d.csv", tmp_path / "e.csv"
    write_rows(cp, C_COLUMNS, c)
    write_rows(dp, D_COLUMNS, d)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gate_e_build_input.py"), "--gate-c", str(cp), "--gate-d", str(dp), "--output", str(out)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 1
    assert "keys differ" in proc.stderr
    assert not out.exists()
