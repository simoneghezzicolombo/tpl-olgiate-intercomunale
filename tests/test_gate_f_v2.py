import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_gate_e_adapter import adapt_gate_e_outputs
from src.gate_f_v2 import V2_OBJECTIVES, decision_summary_v2, point_frontier_v2


def _metric_metadata(frame, metric, unit, semantics, basis, status="MODEL OUTPUT", source="TEST"):
    frame[f"{metric}__status"] = status
    frame[f"{metric}__source"] = source
    frame[f"{metric}__unit"] = unit
    frame[f"{metric}__semantics"] = semantics
    frame[f"{metric}__comparison_basis"] = basis


def _v2_frame(road_status="RESOLVED"):
    frame = pd.DataFrame([
        {
            "scenario_id": "BASE", "scenario_name": "Current", "topology_family": "CURRENT",
            "scenario_epistemic_status": "RECONSTRUCTED", "scenario_source": "TEST", "is_baseline": True,
            "road_feasible": True, "road_uncertainty_status": "RESOLVED", "road_uncertainty_source": "D",
            "population_covered_pct": 50.0, "headway_combined_min": 60.0, "annual_bus_km": 100000.0,
            "minimum_scheduled_vehicles": 2, "s8_useful_connection_pct": 50.0, "territories_served_count": 3,
        },
        {
            "scenario_id": "ALT", "scenario_name": "Alternative", "topology_family": "OTHER",
            "scenario_epistemic_status": "MODEL OUTPUT", "scenario_source": "TEST", "is_baseline": False,
            "road_feasible": True, "road_uncertainty_status": road_status, "road_uncertainty_source": "D",
            "population_covered_pct": 80.0, "headway_combined_min": 30.0, "annual_bus_km": 90000.0,
            "minimum_scheduled_vehicles": 1, "s8_useful_connection_pct": 90.0, "territories_served_count": 5,
        },
    ])
    specs = {
        "road_feasible": ("boolean", "STRUCTURAL_ROUTING_ELIGIBILITY_CONSTRAINT", "ROAD"),
        "population_covered_pct": ("%", "PERCENT_OF_DEFINED_POPULATION_DENOMINATOR", "POP"),
        "territories_served_count": ("count", "COUNT_OF_DEFINED_TERRITORIAL_UNITS", "TERR"),
        "s8_useful_connection_pct": ("%", "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR", "S8"),
        "headway_combined_min": ("min", "RATE_EQUIVALENT_NOT_MAX_GAP", "HEADWAY"),
        "annual_bus_km": ("bus-km/year", "ANNUAL_SCHEDULED_BUS_DISTANCE", "KM"),
        "minimum_scheduled_vehicles": (
            "vehicles",
            "THEORETICAL_IN_SERVICE_SCHEDULED_MINIMUM_EXCLUDES_DEADHEAD_RELIEFS_MAINTENANCE_SPARES",
            "FLEET",
        ),
    }
    for metric, (unit, semantics, basis) in specs.items():
        _metric_metadata(frame, metric, unit, semantics, basis)
    return frame


def test_v2_unique_winner_can_pass_when_road_uncertainty_resolved():
    frame = _v2_frame("RESOLVED")
    frontier = point_frontier_v2(frame)
    summary = decision_summary_v2(frontier, {g: "PASS" for g in "ABCDE"})
    assert summary["verdict"] == "PASS"
    assert summary["recommended_scenario_id"] == "ALT"
    assert [o.column for o in V2_OBJECTIVES].count("minimum_scheduled_vehicles") == 1


def test_v2_conditional_road_uncertainty_blocks_definitive_winner():
    frame = _v2_frame("QUANTIFIED")
    frontier = point_frontier_v2(frame)
    summary = decision_summary_v2(frontier, {g: "PASS" for g in "ABCDE"})
    assert summary["verdict"] == "PROVISIONAL"
    assert summary["recommended_scenario_id"] is None
    assert summary["conditional_road_scenario_ids"] == ["ALT"]


def test_v2_rejects_noninteger_minimum_scheduled_fleet():
    frame = _v2_frame()
    # Pandas 3 refuses lossy float assignment into an int64 column before our
    # validator can see it. Cast deliberately so the invalid value reaches the
    # Gate F validation layer being tested.
    frame["minimum_scheduled_vehicles"] = frame["minimum_scheduled_vehicles"].astype(float)
    frame.loc[frame["scenario_id"] == "ALT", "minimum_scheduled_vehicles"] = 1.5
    with pytest.raises(ValueError, match="integer"):
        point_frontier_v2(frame)


def _gate_e_files(tmp_path):
    scenario = pd.DataFrame([
        {"scenario_id": "BASE", "gate_status": "ELIGIBLE_FOR_GATE_E_VERDICT", "annual_bus_km": 100000, "assumption_present": False},
        {"scenario_id": "ALT", "gate_status": "ELIGIBLE_FOR_GATE_E_VERDICT", "annual_bus_km": 90000, "assumption_present": False},
    ])
    bands = pd.DataFrame([
        {"scenario_id": sid, "service_day_group": "WEEKDAY", "band_id": "AM", "gate_status": "ELIGIBLE_FOR_GATE_E_VERDICT", "headway_combined_rate_equiv_min": value, "combined_headway_applicability": "COMPUTED_SHARED_STOP_PATTERN_CONFIRMED"}
        for sid, value in [("BASE", 60), ("ALT", 30)]
    ])
    fleet = pd.DataFrame([
        {"scenario_id": sid, "service_day_group": "WEEKDAY", "fleet_evidence_status": "ELIGIBLE_FOR_GATE_E_SCHEDULED_FLEET_EVIDENCE", "minimum_scheduled_vehicles_direction_locked_total": locked, "minimum_scheduled_vehicles_hub_interlining_allowed": interlined, "fleet_scope": "THEORETICAL", "excluded_from_fleet_scope": "SPARES"}
        for sid, locked, interlined in [("BASE", 2, 2), ("ALT", 2, 1)]
    ])
    paths = {}
    for name, frame in [("scenario", scenario), ("bands", bands), ("fleet", fleet)]:
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    return paths


def _policy(tmp_path, fleet_measure="DIRECTION_LOCKED_TOTAL"):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "comparison_id": "TEST_COMPARISON",
        "service_day_group": "WEEKDAY",
        "headway_band_id": "AM",
        "fleet_measure": fleet_measure,
    }), encoding="utf-8")
    return path


def test_gate_e_adapter_requires_explicit_fleet_interpretation(tmp_path):
    paths = _gate_e_files(tmp_path)
    locked = adapt_gate_e_outputs(
        paths["scenario"], paths["bands"], paths["fleet"], _policy(tmp_path), gate_e_commit="a" * 40
    ).set_index("scenario_id")
    assert locked.loc["ALT", "minimum_scheduled_vehicles"] == 2
    assert "DIRECTION_LOCKED_TOTAL" in locked.loc["ALT", "minimum_scheduled_vehicles__comparison_basis"]

    interlined = adapt_gate_e_outputs(
        paths["scenario"], paths["bands"], paths["fleet"], _policy(tmp_path, "HUB_INTERLINING_ALLOWED"), gate_e_commit="a" * 40
    ).set_index("scenario_id")
    assert interlined.loc["ALT", "minimum_scheduled_vehicles"] == 1
    assert "HUB_INTERLINING_ALLOWED" in interlined.loc["ALT", "minimum_scheduled_vehicles__comparison_basis"]


def test_gate_e_adapter_rejects_unconfirmed_combined_headway(tmp_path):
    paths = _gate_e_files(tmp_path)
    bands = pd.read_csv(paths["bands"])
    bands.loc[bands["scenario_id"] == "ALT", "combined_headway_applicability"] = "NOT_COMPUTED_UNTIL_SHARED_STOP_PATTERN_CONFIRMED"
    bands.to_csv(paths["bands"], index=False)
    with pytest.raises(ValueError, match="confirmed shared stop pattern"):
        adapt_gate_e_outputs(
            paths["scenario"], paths["bands"], paths["fleet"], _policy(tmp_path), gate_e_commit="a" * 40
        )


def test_gate_e_adapter_refuses_assumption_rows(tmp_path):
    paths = _gate_e_files(tmp_path)
    scenario = pd.read_csv(paths["scenario"])
    scenario.loc[scenario["scenario_id"] == "ALT", "assumption_present"] = True
    scenario.to_csv(paths["scenario"], index=False)
    with pytest.raises(ValueError, match="assumption_present"):
        adapt_gate_e_outputs(
            paths["scenario"], paths["bands"], paths["fleet"], _policy(tmp_path), gate_e_commit="a" * 40
        )
