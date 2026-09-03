import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_inputs_v2 import assemble_gate_f_inputs_v2


def _meta(row, metric, value, unit, semantics, basis, status="MODEL OUTPUT"):
    row[metric] = value
    row[f"{metric}__status"] = status
    row[f"{metric}__source"] = "TEST"
    row[f"{metric}__unit"] = unit
    row[f"{metric}__semantics"] = semantics
    row[f"{metric}__comparison_basis"] = basis


def _files(tmp_path, alt_feasible=True, alt_uncertainty="QUANTIFIED"):
    catalog = pd.DataFrame([
        {"scenario_id": "BASE", "scenario_name": "Current", "topology_family": "CURRENT", "is_baseline": True, "scenario_epistemic_status": "RECONSTRUCTED", "scenario_source": "TEST"},
        {"scenario_id": "ALT", "scenario_name": "Alternative", "topology_family": "OTHER", "is_baseline": False, "scenario_epistemic_status": "MODEL OUTPUT", "scenario_source": "TEST"},
        {"scenario_id": "BAD", "scenario_name": "Structurally impossible", "topology_family": "OTHER", "is_baseline": False, "scenario_epistemic_status": "MODEL OUTPUT", "scenario_source": "TEST"},
    ])
    drows = []
    for sid, feasible, uncertainty in [("BASE", True, "RESOLVED"), ("ALT", alt_feasible, alt_uncertainty), ("BAD", False, "UNKNOWN")]:
        row = {"scenario_id": sid, "road_uncertainty_status": uncertainty, "road_uncertainty_source": "TEST_D"}
        _meta(row, "road_feasible", feasible, "boolean", "STRUCTURAL_ROUTING_ELIGIBILITY_CONSTRAINT", "ROAD", "DERIVED")
        drows.append(row)
    d = pd.DataFrame(drows)

    eligible = ["BASE"] + (["ALT"] if alt_feasible else [])
    brows = []; crows = []; erows = []
    for idx, sid in enumerate(eligible):
        b = {"scenario_id": sid}
        _meta(b, "population_covered_pct", 50 + idx * 10, "%", "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR", "POP")
        _meta(b, "territories_served_count", 3 + idx, "count", "COUNT_OF_DEFINED_TERRITORIAL_UNITS", "TERR", "DERIVED")
        brows.append(b)
        c = {"scenario_id": sid}
        _meta(c, "s8_useful_connection_pct", 60 + idx * 10, "%", "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR", "S8")
        crows.append(c)
        e = {"scenario_id": sid}
        _meta(e, "headway_combined_min", 60 - idx * 10, "min", "RATE_EQUIVALENT_NOT_MAX_GAP", "HEADWAY")
        _meta(e, "annual_bus_km", 100000 + idx * 1000, "bus-km/year", "ANNUAL_SCHEDULED_BUS_DISTANCE", "KM")
        _meta(e, "minimum_scheduled_vehicles", 2 + idx, "vehicles", "THEORETICAL_IN_SERVICE_SCHEDULED_MINIMUM_EXCLUDES_DEADHEAD_RELIEFS_MAINTENANCE_SPARES", "FLEET")
        erows.append(e)
    frames = {"catalog": catalog, "b": pd.DataFrame(brows), "c": pd.DataFrame(crows), "d": d, "e": pd.DataFrame(erows)}
    paths = {}
    for name, frame in frames.items():
        path = tmp_path / f"{name}.csv"; frame.to_csv(path, index=False); paths[name] = path
    return paths


def _assemble(paths):
    return assemble_gate_f_inputs_v2(paths["catalog"], paths["b"], paths["c"], paths["d"], paths["e"])


def test_v2_keeps_conditional_road_scenario_in_comparison(tmp_path):
    eligible, excluded = _assemble(_files(tmp_path))
    assert set(eligible["scenario_id"]) == {"BASE", "ALT"}
    assert eligible.set_index("scenario_id").loc["ALT", "road_uncertainty_status"] == "QUANTIFIED"
    assert excluded["scenario_id"].tolist() == ["BAD"]


def test_v2_structural_false_is_excluded_before_metrics(tmp_path):
    paths = _files(tmp_path, alt_feasible=False)
    with pytest.raises(ValueError, match="at least two"):
        _assemble(paths)


def test_v2_rejects_old_peak_buses_field_instead_of_scheduled_minimum(tmp_path):
    paths = _files(tmp_path)
    e = pd.read_csv(paths["e"])
    e = e.rename(columns={"minimum_scheduled_vehicles": "peak_buses_required"})
    e.to_csv(paths["e"], index=False)
    with pytest.raises(ValueError, match="minimum_scheduled_vehicles"):
        _assemble(paths)
