from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import (  # noqa: E402
    DirectionPlan,
    ServiceMathError,
    aggregate_scenarios,
    combined_headway_rate_equivalent,
    cycle_minutes,
    load_pdb_budget,
    vehicles_required,
)


def test_real_pdb_budget_is_internally_consistent():
    budget = load_pdb_budget(ROOT / "data" / "risorse_tpl_pdb.csv")
    assert budget["D184"] == 52560.0
    assert budget["D185"] == 58859.0
    assert budget["D184+D185"] == 111419.0
    assert budget["D184"] + budget["D185"] == budget["D184+D185"]


def test_cycle_time_keeps_running_dwell_recovery_separate():
    assert cycle_minutes(50.0, 5.0, 5.0) == 60.0


def test_protocol_60_min_cycle_one_bus_each_direction_means_60_each_30_combined():
    cycle = cycle_minutes(50.0, 5.0, 5.0)
    assert vehicles_required(cycle, 60.0) == 1
    assert combined_headway_rate_equivalent(60.0, 60.0) == pytest.approx(30.0)


def test_30_min_each_direction_on_60_min_cycle_requires_four_buses_total():
    cycle = 60.0
    cw = vehicles_required(cycle, 30.0)
    ccw = vehicles_required(cycle, 30.0)
    assert cw == 2
    assert ccw == 2
    assert cw + ccw == 4
    assert combined_headway_rate_equivalent(30.0, 30.0) == pytest.approx(15.0)


def test_assumption_is_rejected_outside_sensitivity():
    p = DirectionPlan(
        "S", "CW", "ASSUMPTION", "PRODUCTION", "PASS", "PASS",
        1.0, 50.0, 5.0, 5.0, 60.0, 1, 1,
    )
    with pytest.raises(ServiceMathError, match="SENSITIVITY"):
        p.validate()


def test_negative_recovery_is_rejected():
    with pytest.raises(ServiceMathError, match="recovery_min"):
        cycle_minutes(50.0, 5.0, -1.0)


def test_upstream_nonpass_forces_provisional_gate_status():
    plans = [
        DirectionPlan("S", "CW", "ASSUMPTION", "SENSITIVITY", "IN_PROGRESS", "IN_PROGRESS", 1.0, 50, 5, 5, 60, 1, 1),
        DirectionPlan("S", "CCW", "ASSUMPTION", "SENSITIVITY", "IN_PROGRESS", "IN_PROGRESS", 1.0, 50, 5, 5, 60, 1, 1),
    ]
    row = aggregate_scenarios(plans, 111419.0)[0]
    assert row["gate_status"] == "PROVISIONAL/BLOCKED_BY_GATE_C_AND_GATE_D"
    assert row["headway_CW_min"] == 60.0
    assert row["headway_CCW_min"] == 60.0
    assert row["headway_combined_rate_equiv_min"] == pytest.approx(30.0)
    assert row["vehicles_required_total"] == 2


def test_service_script_has_no_embedded_scenario_or_recommendation_constants():
    text = (ROOT / "scripts" / "10_service_simulation.py").read_text(encoding="utf-8")
    forbidden = ["SCENARI_SIMULATI", "SOLUZIONE OTTIMALE", "Raccomandato", "111419.0"]
    for token in forbidden:
        assert token not in text


def test_benchmark_only_runs_from_real_resource_table(tmp_path):
    out = tmp_path / "budget.csv"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "10_service_simulation.py"), "--benchmark-only", "--budget-output", str(out)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    assert "111419" in out.read_text(encoding="utf-8")


def test_missing_gate_d_input_blocks_scenario_generation(tmp_path):
    out = tmp_path / "scenario.csv"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "10_service_simulation.py"),
            "--input",
            str(tmp_path / "missing.csv"),
            "--output",
            str(out),
            "--budget-output",
            str(tmp_path / "budget.csv"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 2
    assert "BLOCKED_BY_GATE_C_AND_D" in proc.stderr
    assert not out.exists()


def test_directional_cycles_are_not_silently_treated_as_pairs():
    plans = [
        DirectionPlan("S", "CW", "ASSUMPTION", "SENSITIVITY", "PASS", "PASS", 10.0, 50, 5, 5, 60, 13, 303),
        DirectionPlan("S", "CCW", "ASSUMPTION", "SENSITIVITY", "PASS", "PASS", 10.0, 50, 5, 5, 60, 13, 303),
    ]
    row = aggregate_scenarios(plans, 111419.0)[0]
    assert row["annual_bus_km"] == 10.0 * 13 * 303 * 2
    assert row["vehicles_required_total"] == 2


def test_placeholder_and_invalidated_inputs_are_rejected():
    for status in ("PLACEHOLDER", "INVALIDATED"):
        p = DirectionPlan("S", "CW", status, "SENSITIVITY", "PASS", "PASS", 1, 50, 5, 5, 60, 1, 1)
        with pytest.raises(ServiceMathError):
            p.validate()
