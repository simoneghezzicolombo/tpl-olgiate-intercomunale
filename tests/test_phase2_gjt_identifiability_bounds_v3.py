from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase2_build_gjt_identifiability_bounds_v3.py"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def fixtures(tmp_path: Path):
    journey = tmp_path / "journey.json"
    demand = tmp_path / "demand.json"
    feeder = tmp_path / "feeder.json"
    baseline = tmp_path / "baseline.json"
    matrix = tmp_path / "matrix.csv"
    validation = tmp_path / "validation.json"

    write_json(journey, {
        "contract": "PHASE2_PASSENGER_JOURNEY_UNIVERSE_V2",
        "source_resolution": "MUNICIPAL_OD",
        "demand_weight_sum": 1882.0,
        "full_gjt_ready": False,
        "spatial_allocation_performed": False,
        "fine_walking_access_combined_with_empirical_OD": False,
    })
    write_json(demand, {
        "source_scope": "ISTAT_2021_WORK_COMMUTING_ONLY",
        "s8_direct_workers": 1882,
        "outputs": {
            "outputs/phase2/od_2021_destinations_by_origin.csv": "a",
            "outputs/phase2/od_2021_corridor_summary.csv": "b",
        },
    })
    write_json(feeder, {
        "contract": "PHASE2_PRE_PHASE_FEEDER_GENERALIZED_ACCESS_V2",
        "full_gjt_calculated": False,
        "municipal_work_od_downscaled": False,
        "resident_population_is_passenger_demand": False,
        "exact_timetable_constructed": False,
        "exact_train_connection_wait_used": False,
    })
    write_json(baseline, {
        "contract": "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V3",
        "baseline_complete": False,
        "may_infer_true_current_total_coverage": False,
    })
    return journey, demand, feeder, baseline, matrix, validation


def run(tmp_path: Path, mutate=None):
    journey, demand, feeder, baseline, matrix, validation = fixtures(tmp_path)
    files = {"journey": journey, "demand": demand, "feeder": feeder, "baseline": baseline}
    if mutate:
        mutate(files)
    result = subprocess.run([
        sys.executable, str(SCRIPT),
        "--journey-validation", str(journey),
        "--demand-profile-validation", str(demand),
        "--feeder-validation", str(feeder),
        "--current-baseline-v3-validation", str(baseline),
        "--evidence-matrix", str(matrix),
        "--validation", str(validation),
    ], capture_output=True, text=True)
    return result, validation


def test_valid_audit_fail_closes_final_selection(tmp_path):
    result, validation = run(tmp_path)
    assert result.returncode == 0, result.stderr
    v = json.loads(validation.read_text())
    assert v["full_point_demand_weighted_gjt_identified"] is False
    assert v["full_point_gjt_improvement_vs_current_identified"] is False
    assert v["empirical_missed_connection_probability_identified"] is False
    assert v["candidate_set_bounds_constructible_after_exact_unit_cost_materialization"] is True
    assert v["candidate_set_bounds_would_authorize_final_selection"] is False
    assert v["resident_population_used_as_passenger_demand"] is False
    assert v["municipal_od_downscaled"] is False
    assert v["weighted_composite_score"] is False
    assert v["primary_selected"] is False
    assert v["runner_up_selected"] is False


def test_claimed_full_gjt_is_rejected(tmp_path):
    def mutate(files):
        p = json.loads(files["journey"].read_text())
        p["full_gjt_ready"] = True
        write_json(files["journey"], p)
    result, _ = run(tmp_path, mutate)
    assert result.returncode != 0
    assert "full GJT readiness" in result.stderr


def test_spatial_allocation_change_requires_contract_revisit(tmp_path):
    def mutate(files):
        p = json.loads(files["journey"].read_text())
        p["spatial_allocation_performed"] = True
        write_json(files["journey"], p)
    result, _ = run(tmp_path, mutate)
    assert result.returncode != 0
    assert "Unexpected spatial allocation" in result.stderr


def test_resident_population_as_demand_is_rejected(tmp_path):
    def mutate(files):
        p = json.loads(files["feeder"].read_text())
        p["resident_population_is_passenger_demand"] = True
        write_json(files["feeder"], p)
    result, _ = run(tmp_path, mutate)
    assert result.returncode != 0
    assert "Resident population semantics changed" in result.stderr


def test_complete_current_baseline_claim_is_rejected(tmp_path):
    def mutate(files):
        p = json.loads(files["baseline"].read_text())
        p["baseline_complete"] = True
        write_json(files["baseline"], p)
    result, _ = run(tmp_path, mutate)
    assert result.returncode != 0
    assert "unexpectedly claims completeness" in result.stderr


def test_temporal_demand_output_forces_reaudit(tmp_path):
    def mutate(files):
        p = json.loads(files["demand"].read_text())
        p["outputs"]["outputs/phase2/worker_departure_time_distribution.csv"] = "c"
        write_json(files["demand"], p)
    result, _ = run(tmp_path, mutate)
    assert result.returncode != 0
    assert "Unexpected temporal-demand output" in result.stderr
