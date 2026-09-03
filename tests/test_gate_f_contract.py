import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_contract import METRIC_CONTRACT, metric_contract_manifest, validate_gate_f_metric_contract


def _frame():
    data = {}
    values = {
        "road_feasible": True,
        "population_covered_pct": 50.0,
        "territories_served_count": 3,
        "s8_useful_connection_pct": 60.0,
        "headway_combined_min": 30.0,
        "annual_bus_km": 100000.0,
        "peak_buses_required": 2,
    }
    for metric, spec in METRIC_CONTRACT.items():
        data[metric] = [values[metric], values[metric]]
        data[f"{metric}__unit"] = [spec["unit"], spec["unit"]]
        data[f"{metric}__semantics"] = [spec["semantics"], spec["semantics"]]
    return pd.DataFrame(data)


def test_canonical_contract_passes():
    validate_gate_f_metric_contract(_frame())


def test_missing_unit_column_fails_closed():
    df = _frame().drop(columns=["annual_bus_km__unit"])
    with pytest.raises(ValueError, match="missing unit column"):
        validate_gate_f_metric_contract(df)


def test_seconds_cannot_masquerade_as_minutes():
    df = _frame()
    df["headway_combined_min__unit"] = "seconds"
    with pytest.raises(ValueError, match="canonical unit 'min'"):
        validate_gate_f_metric_contract(df)


def test_rate_equivalent_semantics_are_mandatory():
    df = _frame()
    df["headway_combined_min__semantics"] = "MAX_GAP"
    with pytest.raises(ValueError, match="RATE_EQUIVALENT_NOT_MAX_GAP"):
        validate_gate_f_metric_contract(df)


def test_contract_manifest_is_data_free_and_declares_all_metrics():
    manifest = metric_contract_manifest()
    assert set(manifest) == set(METRIC_CONTRACT)
    assert manifest["annual_bus_km"]["unit"] == "bus-km/year"
    assert manifest["headway_combined_min"]["semantics"] == "RATE_EQUIVALENT_NOT_MAX_GAP"
