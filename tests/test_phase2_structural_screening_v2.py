from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase2_screen_structural_catalog import sha256_path
from scripts.phase2_screen_structural_catalog_v2 import validate_v2_lineage


def write_validation_files(tmp_path: Path):
    catalog = tmp_path / "catalog.csv"
    matrix = tmp_path / "matrix.csv"
    anchors = tmp_path / "anchors.csv"
    catalog_validation = tmp_path / "catalog_validation.json"
    matrix_validation = tmp_path / "matrix_validation.json"
    catalog.write_text("scenario_id,topology_family,routes_json,optional_extensions_json\n", encoding="utf-8")
    matrix.write_text("origin,destination,distance_km,runtime_min,uncertainty\n", encoding="utf-8")
    anchors.write_text("anchor_id,source_kind\n", encoding="utf-8")
    matrix_payload = {
        "status": "PASS_REDUCED_PATH_MATRIX_V2_BUILD",
        "contract": "PHASE2_REDUCED_STOP_PATH_MATRIX_V2",
        "epoch_id": "epoch-x",
        "lineage": {
            "reduced_path_matrix_sha256": sha256_path(matrix),
            "routing_anchor_universe_sha256": sha256_path(anchors),
        },
    }
    catalog_payload = {
        "status": "PASS_STRUCTURAL_CATALOG_V2_BUILD",
        "contract": "PHASE2_BALANCED_STRUCTURAL_SEARCH_V2",
        "epoch_id": "epoch-x",
        "generated_scenario_count": 100000,
        "selects_topology": False,
        "selects_stops": False,
        "chooses_service_policy": False,
        "lineage": {
            "scenario_catalog_sha256": sha256_path(catalog),
            "reduced_path_matrix_sha256": sha256_path(matrix),
            "routing_anchor_universe_sha256": sha256_path(anchors),
        },
    }
    matrix_validation.write_text(json.dumps(matrix_payload), encoding="utf-8")
    catalog_validation.write_text(json.dumps(catalog_payload), encoding="utf-8")
    return catalog, catalog_validation, matrix, matrix_validation, anchors


def test_v2_lineage_accepts_exact_certified_inputs(tmp_path: Path) -> None:
    args = write_validation_files(tmp_path)
    catalog_validation, matrix_validation = validate_v2_lineage(
        catalog_path=args[0],
        catalog_validation_path=args[1],
        matrix_path=args[2],
        matrix_validation_path=args[3],
        anchor_path=args[4],
    )
    assert catalog_validation["generated_scenario_count"] == 100000
    assert matrix_validation["epoch_id"] == "epoch-x"


def test_v2_lineage_rejects_catalog_tamper(tmp_path: Path) -> None:
    args = write_validation_files(tmp_path)
    args[0].write_text(args[0].read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    with pytest.raises(ValueError, match="scenario catalog"):
        validate_v2_lineage(
            catalog_path=args[0],
            catalog_validation_path=args[1],
            matrix_path=args[2],
            matrix_validation_path=args[3],
            anchor_path=args[4],
        )


def test_v2_lineage_rejects_upstream_selection(tmp_path: Path) -> None:
    args = write_validation_files(tmp_path)
    payload = json.loads(args[1].read_text(encoding="utf-8"))
    payload["selects_topology"] = True
    args[1].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="selects topology"):
        validate_v2_lineage(
            catalog_path=args[0],
            catalog_validation_path=args[1],
            matrix_path=args[2],
            matrix_validation_path=args[3],
            anchor_path=args[4],
        )
