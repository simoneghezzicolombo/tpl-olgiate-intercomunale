from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_build_stop_universe_v2.py"
spec = importlib.util.spec_from_file_location("phase2_stop_universe_v2", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _write_fixture(tmp_path: Path, *, duplicate_identity: bool = False) -> Path:
    codes = ["097010", "097012", "097058", "097074", "097092"]
    building_ids = [f"B{i}" for i in range(5)]
    section_ids = [f"S{i}" for i in range(5)]
    if duplicate_identity:
        building_ids[1] = building_ids[0]
        section_ids[1] = section_ids[0]
    accessibility = pd.DataFrame(
        {
            "building_id": building_ids,
            "section_id": section_ids,
            "municipality_code": codes,
            "piece_x_utm32": [533000.0 + i for i in range(5)],
            "piece_y_utm32": [5064000.0 + i for i in range(5)],
            "building_piece_population_model": [10.0] * 5,
            "nearest_graph_node_id": [100 + i for i in range(5)],
            "connector_walk_min": [0.1] * 5,
            "connector_within_limit": [True] * 5,
            "covered_5min": [True, False, True, False, True],
            "covered_8min": [True] * 5,
            "covered_10min": [True] * 5,
            "covered_12min": [True] * 5,
            "resident_estimate_epistemic_status": ["MODEL_OUTPUT_DASYMETRIC_BUILDING_POPULATION"] * 5,
            "accessibility_epistemic_status": ["MODEL_OUTPUT_GATE_B_WALK_GRAPH_BUILDING_SECTION_PIECE_REPRESENTATIVE_POINT"] * 5,
        }
    )
    accessibility.to_csv(tmp_path / "building_population_accessibility.csv", index=False)
    reconciliation = pd.DataFrame(
        {
            "municipality_code": codes,
            "population_2025_posas_fact": [11.0] * 5,
            "building_population_model": [10.0] * 5,
            "section_residual_population": [1.0] * 5,
            "accounted_population": [11.0] * 5,
            "reconciliation_error": [0.0] * 5,
            "reconciliation_pass": [True] * 5,
        }
    )
    reconciliation.to_csv(tmp_path / "building_population_municipal_reconciliation.csv", index=False)
    validation = {
        "status": "PASS_BUILDING_POPULATION_BUILD",
        "scope": "BUILDING_DASYMETRIC_POPULATION_NOT_STOP_RANKING_NOT_NETWORK_SELECTION",
        "final_network_selected": False,
        "final_stop_ranking_produced": False,
        "core_v2_coverage_pct_total_posas": {"5": 1.0, "8": 2.0, "10": 3.0, "12": 4.0},
    }
    (tmp_path / "building_population_validation.json").write_text(json.dumps(validation), encoding="utf-8")
    return tmp_path


def test_truthy_parser_is_explicit():
    parsed = module._truthy(pd.Series([True, False, "true", "1", "false", "0", "yes"]))
    assert parsed.tolist() == [True, False, True, True, False, False, False]


def test_building_population_adapter_preserves_core_accounting(tmp_path: Path):
    building_dir = _write_fixture(tmp_path)
    inverse = Transformer.from_crs(32632, 4326, always_xy=True)
    units, metadata = module._load_building_population_units(building_dir, inverse)
    assert len(units) == 5
    assert units["population_unit_id"].is_unique
    assert set(units["PRO_COM_T"]) == module.CORE_CODES
    assert units["population_unit_type"].eq("BUILDING_SECTION_INTERSECTION").all()
    assert metadata["population_located_building_pieces"] == 50.0
    assert metadata["population_residual_unlocated"] == 5.0
    assert metadata["population_total_posas_2025"] == 55.0


def test_building_population_adapter_rejects_duplicate_piece_identity(tmp_path: Path):
    building_dir = _write_fixture(tmp_path, duplicate_identity=True)
    inverse = Transformer.from_crs(32632, 4326, always_xy=True)
    with pytest.raises(ValueError, match="identity is not unique"):
        module._load_building_population_units(building_dir, inverse)
