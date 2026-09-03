from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_closure import build_scenario_inventory, close_gate_f_from_inventory  # noqa: E402


def _paired(tmp_path: Path, statuses=("ASSUMPTION", "ASSUMPTION")) -> Path:
    frame = pd.DataFrame(
        [
            {
                "route_id": f"P{i}",
                "route_type": "GATE_D_DIRECTIONAL_PAIR",
                "component_families": f"F{i}",
                "route_definition_status": status,
                "route_definition_basis": "GATE_D_HYPOTHESIS_NOT_RECOMMENDATION",
                "service_math_status": "SENSITIVITY_ONLY_ROUTE_DEFINITION_IS_ASSUMPTION",
                "paired_directional_cycle_km": 20 + i,
                "paired_pure_running_min": 40 + i,
                "budget_bus_km_year": 111419,
                "max_equal_CW_CCW_cycles_year_under_budget": 5000 - i,
                "annual_bus_km_at_max_equal_pairs": 111400 + i,
                "budget_margin_km_at_max_equal_pairs": 19 - i,
            }
            for i, status in enumerate(statuses)
        ]
    )
    path = tmp_path / "paired.csv"
    frame.to_csv(path, index=False)
    return path


def _unpaired(tmp_path: Path) -> Path:
    frame = pd.DataFrame(
        [
            {
                "candidate_id": "U1",
                "family": "UF",
                "direction": "SENSITIVITY",
                "route_km": 25.0,
                "pure_running_min": 48.0,
                "gate_e_pairing_status": "UNPAIRED_NOT_ELIGIBLE_FOR_FULL_BIDIRECTIONAL_SERVICE_MATH",
                "candidate_status": "HYPOTHESIS_NOT_RECOMMENDATION",
            }
        ]
    )
    path = tmp_path / "unpaired.csv"
    frame.to_csv(path, index=False)
    return path


def test_inventory_keeps_every_upstream_alternative_without_preference(tmp_path):
    inventory = build_scenario_inventory(_paired(tmp_path), _unpaired(tmp_path))
    assert set(inventory["scenario_id"]) == {"P0", "P1", "U1"}
    assert "preferred" not in inventory.columns
    assert "recommended" not in inventory.columns
    assert inventory["scenario_id"].is_unique


def test_assumption_only_pairable_set_closes_with_no_definitive_recommendation(tmp_path):
    inventory = build_scenario_inventory(_paired(tmp_path), _unpaired(tmp_path))
    result = close_gate_f_from_inventory(inventory)
    assert result.verdict == "PASS"
    assert result.recommendation_status == "NO_DEFINITIVE_RECOMMENDATION_SUPPORTED_BY_CURRENT_EVIDENCE"
    assert result.assumption_free_pairable_alternatives == 0
    assert result.definitive_pareto_eligible is False


def test_two_assumption_free_pairable_alternatives_require_definitive_pareto(tmp_path):
    inventory = build_scenario_inventory(_paired(tmp_path, statuses=("DERIVED", "FACT")), _unpaired(tmp_path))
    result = close_gate_f_from_inventory(inventory)
    assert result.verdict == "READY_FOR_DEFINITIVE_PARETO"
    assert result.recommendation_status == "DEFINITIVE_PARETO_REQUIRED"
    assert result.assumption_free_pairable_alternatives == 2
    assert result.definitive_pareto_eligible is True


def test_single_assumption_free_alternative_is_not_a_comparison(tmp_path):
    inventory = build_scenario_inventory(_paired(tmp_path, statuses=("DERIVED", "ASSUMPTION")), _unpaired(tmp_path))
    result = close_gate_f_from_inventory(inventory)
    assert result.verdict == "PASS"
    assert result.assumption_free_pairable_alternatives == 1
    assert result.definitive_pareto_eligible is False


def test_duplicate_upstream_ids_fail_closed(tmp_path):
    path = _paired(tmp_path)
    frame = pd.read_csv(path)
    frame.loc[1, "route_id"] = frame.loc[0, "route_id"]
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate route_id"):
        build_scenario_inventory(path, _unpaired(tmp_path))
