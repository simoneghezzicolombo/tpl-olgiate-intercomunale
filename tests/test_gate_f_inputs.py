import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_inputs import assemble_gate_f_inputs


def _write_fragments(tmp_path, *, infeasible_alt=False, omit_ineligible_metrics=False):
    catalog = pd.DataFrame([
        {"scenario_id": "BASE", "scenario_name": "Current network", "topology_family": "CURRENT", "is_baseline": "True", "scenario_epistemic_status": "RECONSTRUCTED", "scenario_source": "TEST_CATALOG"},
        {"scenario_id": "ALT", "scenario_name": "Alternative topology", "topology_family": "OTHER", "is_baseline": "False", "scenario_epistemic_status": "MODEL OUTPUT", "scenario_source": "TEST_CATALOG"},
    ])
    d = pd.DataFrame([
        {"scenario_id": "BASE", "road_feasible": "True", "road_feasible__status": "DERIVED", "road_feasible__source": "TEST_D", "road_feasible__unit": "boolean", "road_feasible__semantics": "HARD_ELIGIBILITY_CONSTRAINT", "road_feasible__comparison_basis": "ROAD_RULESET_V1"},
        {"scenario_id": "ALT", "road_feasible": "False" if infeasible_alt else "True", "road_feasible__status": "DERIVED", "road_feasible__source": "TEST_D", "road_feasible__unit": "boolean", "road_feasible__semantics": "HARD_ELIGIBILITY_CONSTRAINT", "road_feasible__comparison_basis": "ROAD_RULESET_V1"},
    ])
    ids = ["BASE"] if infeasible_alt and omit_ineligible_metrics else ["BASE", "ALT"]
    b = pd.DataFrame([
        {"scenario_id": sid, "population_covered_pct": 50 + idx, "population_covered_pct__status": "MODEL OUTPUT", "population_covered_pct__source": "TEST_B", "population_covered_pct__unit": "%", "population_covered_pct__semantics": "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR", "population_covered_pct__comparison_basis": "POP_ACCESS_BASIS", "territories_served_count": 2 + idx, "territories_served_count__status": "DERIVED", "territories_served_count__source": "TEST_B", "territories_served_count__unit": "count", "territories_served_count__semantics": "COUNT_OF_DEFINED_TERRITORIAL_UNITS", "territories_served_count__comparison_basis": "TERRITORY_UNIVERSE_V1"}
        for idx, sid in enumerate(ids)
    ])
    c = pd.DataFrame([
        {"scenario_id": sid, "s8_useful_connection_pct": 60 + idx, "s8_useful_connection_pct__status": "MODEL OUTPUT", "s8_useful_connection_pct__source": "TEST_C", "s8_useful_connection_pct__unit": "%", "s8_useful_connection_pct__semantics": "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR", "s8_useful_connection_pct__comparison_basis": "S8_CONNECTION_BASIS"}
        for idx, sid in enumerate(ids)
    ])
    e = pd.DataFrame([
        {"scenario_id": sid, "headway_combined_min": 60 - idx * 10, "headway_combined_min__status": "MODEL OUTPUT", "headway_combined_min__source": "TEST_E", "headway_combined_min__unit": "min", "headway_combined_min__semantics": "RATE_EQUIVALENT_NOT_MAX_GAP", "headway_combined_min__comparison_basis": "CORE_SERVICE_WINDOW_V1", "annual_bus_km": 100000 + idx * 1000, "annual_bus_km__status": "MODEL OUTPUT", "annual_bus_km__source": "TEST_E", "annual_bus_km__unit": "bus-km/year", "annual_bus_km__semantics": "ANNUAL_SCHEDULED_BUS_DISTANCE", "annual_bus_km__comparison_basis": "ANNUAL_PRODUCTION_V1", "peak_buses_required": 2 + idx, "peak_buses_required__status": "MODEL OUTPUT", "peak_buses_required__source": "TEST_E", "peak_buses_required__unit": "vehicles", "peak_buses_required__semantics": "SIMULTANEOUS_PEAK_VEHICLES", "peak_buses_required__comparison_basis": "PEAK_VEHICLE_RULE_V1"}
        for idx, sid in enumerate(ids)
    ])
    paths = {}
    for name, frame in {"catalog": catalog, "b": b, "c": c, "d": d, "e": e}.items():
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    return paths


def _assemble(paths):
    return assemble_gate_f_inputs(paths["catalog"], paths["b"], paths["c"], paths["d"], paths["e"])


def test_valid_fragments_assemble_without_silent_row_loss(tmp_path):
    eligible, excluded = _assemble(_write_fragments(tmp_path))
    assert eligible["scenario_id"].tolist() == ["ALT", "BASE"]
    assert excluded.empty
    assert eligible.loc[eligible["scenario_id"] == "BASE", "is_baseline"].item() == True


def test_string_false_road_feasibility_is_not_truthy(tmp_path):
    eligible, excluded = _assemble(_write_fragments(tmp_path, infeasible_alt=True))
    assert eligible["scenario_id"].tolist() == ["BASE"]
    assert excluded["scenario_id"].tolist() == ["ALT"]
    assert excluded["gate_f_exclusion_reason"].item() == "ROAD_INFEASIBLE_GATE_D"


def test_infeasible_scenario_may_be_absent_from_metric_fragments(tmp_path):
    eligible, excluded = _assemble(_write_fragments(tmp_path, infeasible_alt=True, omit_ineligible_metrics=True))
    assert eligible["scenario_id"].tolist() == ["BASE"]
    assert excluded["scenario_id"].tolist() == ["ALT"]


def test_missing_eligible_scenario_fails_closed(tmp_path):
    paths = _write_fragments(tmp_path)
    b = pd.read_csv(paths["b"])
    b = b[b["scenario_id"] != "ALT"]
    b.to_csv(paths["b"], index=False)
    with pytest.raises(ValueError, match="missing eligible scenarios"):
        _assemble(paths)


def test_unknown_scenario_in_fragment_is_rejected(tmp_path):
    paths = _write_fragments(tmp_path)
    b = pd.read_csv(paths["b"])
    rogue = b.iloc[[0]].copy()
    rogue["scenario_id"] = "ROGUE"
    pd.concat([b, rogue], ignore_index=True).to_csv(paths["b"], index=False)
    with pytest.raises(ValueError, match="unknown scenario"):
        _assemble(paths)


def test_duplicate_scenario_id_is_rejected(tmp_path):
    paths = _write_fragments(tmp_path)
    e = pd.read_csv(paths["e"])
    pd.concat([e, e.iloc[[0]]], ignore_index=True).to_csv(paths["e"], index=False)
    with pytest.raises(ValueError, match="duplicate scenario_id"):
        _assemble(paths)


def test_baseline_cannot_be_road_infeasible(tmp_path):
    paths = _write_fragments(tmp_path)
    d = pd.read_csv(paths["d"])
    d.loc[d["scenario_id"] == "BASE", "road_feasible"] = False
    d.to_csv(paths["d"], index=False)
    with pytest.raises(ValueError, match="baseline scenario BASE is marked road-infeasible"):
        _assemble(paths)


def test_road_feasibility_requires_traceable_source(tmp_path):
    paths = _write_fragments(tmp_path)
    d = pd.read_csv(paths["d"])
    d.loc[d["scenario_id"] == "ALT", "road_feasible__source"] = ""
    d.to_csv(paths["d"], index=False)
    with pytest.raises(ValueError, match="must be traceable"):
        _assemble(paths)


def test_wrong_bus_km_unit_is_rejected(tmp_path):
    paths = _write_fragments(tmp_path)
    e = pd.read_csv(paths["e"])
    e["annual_bus_km__unit"] = "km/day"
    e.to_csv(paths["e"], index=False)
    with pytest.raises(ValueError, match="canonical unit"):
        _assemble(paths)


def test_rate_equivalent_cannot_be_mislabeled_as_max_gap(tmp_path):
    paths = _write_fragments(tmp_path)
    e = pd.read_csv(paths["e"])
    e["headway_combined_min__semantics"] = "GUARANTEED_MAX_GAP"
    e.to_csv(paths["e"], index=False)
    with pytest.raises(ValueError, match="RATE_EQUIVALENT_NOT_MAX_GAP"):
        _assemble(paths)


def test_different_s8_denominators_are_rejected(tmp_path):
    paths = _write_fragments(tmp_path)
    c = pd.read_csv(paths["c"])
    c.loc[c["scenario_id"] == "ALT", "s8_useful_connection_pct__comparison_basis"] = "OTHER_DENOMINATOR"
    c.to_csv(paths["c"], index=False)
    with pytest.raises(ValueError, match="comparison bases differ"):
        _assemble(paths)
