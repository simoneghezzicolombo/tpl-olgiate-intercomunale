import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_gate_d_adapter import adapt_gate_d_handoff


def _handoff(tmp_path, uncertainties=("RESOLVED", "QUANTIFIED"), status="PASS"):
    commit = "d" * 40
    rows = []
    for direction, uncertainty in zip(("CW", "CCW"), uncertainties):
        rows.append({
            "contract_version": "GATE_D_TO_E_V2",
            "scenario_id": "ALT",
            "service_day_group": "WEEKDAY",
            "band_id": "AM",
            "direction": direction,
            "analysis_mode": "PRODUCTION",
            "upstream_gate_d_status": status,
            "gate_d_artifact": "outputs/gate_d_route_metrics.csv",
            "gate_d_commit": commit,
            "candidate_geometry_id": f"ALT_{direction}",
            "route_definition_status": "MODEL OUTPUT",
            "route_definition_basis": "TEST",
            "route_km": 10.0,
            "route_km_status": "MODEL OUTPUT",
            "route_km_method": "OSM",
            "pure_running_min": 20.0,
            "pure_running_status": "MODEL OUTPUT",
            "running_time_calibration_status": "CALIBRATED",
            "uncertain_road_km": 1.0,
            "road_uncertainty_status": uncertainty,
        })
    path = tmp_path / "d.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path, commit


def test_structural_route_success_is_not_mislabelled_physical_certainty(tmp_path):
    path, commit = _handoff(tmp_path)
    out = adapt_gate_d_handoff(path, gate_d_commit=commit).iloc[0]
    assert bool(out["road_feasible"])
    assert out["road_feasible__semantics"] == "STRUCTURAL_ROUTING_ELIGIBILITY_CONSTRAINT"
    assert out["road_uncertainty_status"] == "QUANTIFIED"


def test_unknown_uncertainty_propagates_conservatively(tmp_path):
    path, commit = _handoff(tmp_path, ("RESOLVED", "UNKNOWN"))
    out = adapt_gate_d_handoff(path, gate_d_commit=commit).iloc[0]
    assert out["road_uncertainty_status"] == "UNKNOWN"


def test_nonpass_gate_d_handoff_is_refused(tmp_path):
    path, commit = _handoff(tmp_path, status="PROVISIONAL")
    with pytest.raises(ValueError, match="non-PASS"):
        adapt_gate_d_handoff(path, gate_d_commit=commit)


def test_commit_lineage_mismatch_is_refused(tmp_path):
    path, commit = _handoff(tmp_path)
    with pytest.raises(ValueError, match="commit lineage"):
        adapt_gate_d_handoff(path, gate_d_commit="e" * 40)
