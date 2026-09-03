from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.gate_e_normalize_gate_d import CONTRACT, normalize_rows  # noqa: E402
from src.service_math import ServiceMathError  # noqa: E402


def row(**overrides):
    value = {
        "contract_version": CONTRACT, "scenario_id": "S", "service_day_group": "WEEKDAY", "band_id": "AM",
        "direction": "CW", "analysis_mode": "PRODUCTION", "upstream_gate_d_status": "PASS",
        "gate_d_artifact": "outputs/gate_d/routes.csv", "gate_d_commit": "abc123",
        "candidate_geometry_id": "geom-1", "route_definition_status": "MODEL OUTPUT",
        "route_definition_basis": "algorithmic candidate from validated network inputs",
        "route_km": "10", "route_km_status": "DERIVED", "route_km_method": "OSM_ROUTED_GEOMETRY_EPSG32632",
        "pure_running_min": "30", "pure_running_status": "MODEL OUTPUT",
        "running_time_calibration_status": "CALIBRATED", "uncertain_road_km": "0.5",
        "road_uncertainty_status": "QUANTIFIED",
    }
    value.update(overrides)
    return value


def test_standard_derived_route_and_calibrated_runtime_normalize():
    out = normalize_rows([row()])
    assert out[0]["route_km_status"] == "DERIVED"
    assert out[0]["pure_running_status"] == "MODEL OUTPUT"


def test_nonstandard_derived_osm_status_is_rejected_not_silently_added_to_taxonomy():
    with pytest.raises(ServiceMathError, match="outside the project epistemic taxonomy"):
        normalize_rows([row(route_km_status="DERIVED_OSM")])


def test_assumed_route_definition_cannot_enter_production():
    with pytest.raises(ServiceMathError, match="allowed only in SENSITIVITY"):
        normalize_rows([row(route_definition_status="ASSUMPTION")])


def test_assumed_route_definition_propagates_to_distance_in_sensitivity():
    out = normalize_rows([row(
        analysis_mode="SENSITIVITY", route_definition_status="ASSUMPTION",
        route_km_status="DERIVED", upstream_gate_d_status="IN_PROGRESS",
    )])
    assert out[0]["route_km_status"] == "ASSUMPTION"


def test_uncalibrated_model_runtime_cannot_feed_passed_production_gate_d():
    with pytest.raises(ServiceMathError, match="UNCALIBRATED"):
        normalize_rows([row(running_time_calibration_status="UNCALIBRATED")])


def test_gate_d_pass_requires_lineage():
    with pytest.raises(ServiceMathError, match="artifact and commit"):
        normalize_rows([row(gate_d_commit="")])


def test_uncertain_road_km_cannot_exceed_route_length():
    with pytest.raises(ServiceMathError, match="within"):
        normalize_rows([row(route_km="10", uncertain_road_km="11")])


def test_duplicate_join_key_is_rejected():
    with pytest.raises(ServiceMathError, match="duplicate"):
        normalize_rows([row(), row()])


def test_cli_writes_existing_v1_shape_for_builder_compatibility(tmp_path):
    inp, out = tmp_path / "d-v2.csv", tmp_path / "d-v1.csv"
    header = list(row().keys())
    with inp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header); w.writeheader(); w.writerow(row())
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts/gate_e_normalize_gate_d.py"), "--input", str(inp), "--output", str(out)
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    result = next(csv.DictReader(out.open(encoding="utf-8")))
    assert result["route_km_status"] == "DERIVED"
    assert result["pure_running_status"] == "MODEL OUTPUT"
    assert "candidate_geometry_id" not in result
