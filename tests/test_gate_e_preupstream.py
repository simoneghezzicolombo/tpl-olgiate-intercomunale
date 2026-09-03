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
