from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.phase2_run_balanced_structural_search_v2 import (
    HUB_ID,
    load_v2_anchor_universe,
    validate_upstream_matrix_contract,
)
from scripts.phase2_run_structural_search import sha256_path


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["anchor_id", "evidence_status", "enabled", "source_kind", "epoch_id"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def test_v2_anchor_loader_preserves_specific_epistemic_states(tmp_path: Path) -> None:
    path = tmp_path / "anchors.csv"
    write_csv(path, [
        {
            "anchor_id": HUB_ID,
            "evidence_status": "FACT_FROZEN_GATE_D_RAIL_ANCHOR",
            "enabled": "true",
            "source_kind": "HUB_RAIL",
            "epoch_id": "epoch-x",
        },
        {
            "anchor_id": "E1",
            "evidence_status": "DERIVED_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID",
            "enabled": "true",
            "source_kind": "EXISTING_PHYSICAL_STOP_CLUSTER",
            "epoch_id": "epoch-x",
        },
        {
            "anchor_id": "P1",
            "evidence_status": "PROPOSED_STOP/FIELD_CHECK_PENDING",
            "enabled": "true",
            "source_kind": "PROPOSED_STOP",
            "epoch_id": "epoch-x",
        },
    ])
    anchors, evidence, kinds, epoch = load_v2_anchor_universe(path)
    assert anchors == ["E1", "P1", HUB_ID]
    assert evidence["FACT_FROZEN_GATE_D_RAIL_ANCHOR"] == 1
    assert evidence["DERIVED_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID"] == 1
    assert evidence["PROPOSED_STOP/FIELD_CHECK_PENDING"] == 1
    assert kinds == {"EXISTING_PHYSICAL_STOP_CLUSTER": 1, "HUB_RAIL": 1, "PROPOSED_STOP": 1}
    assert epoch == "epoch-x"


def test_v2_anchor_loader_rejects_generic_fact_degradation(tmp_path: Path) -> None:
    path = tmp_path / "anchors.csv"
    write_csv(path, [{
        "anchor_id": HUB_ID,
        "evidence_status": "FACT",
        "enabled": "true",
        "source_kind": "HUB_RAIL",
        "epoch_id": "epoch-x",
    }])
    with pytest.raises(ValueError, match="unsupported/degraded evidence state"):
        load_v2_anchor_universe(path)


def test_v2_anchor_loader_rejects_evidence_source_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "anchors.csv"
    write_csv(path, [{
        "anchor_id": HUB_ID,
        "evidence_status": "PROPOSED_STOP/FIELD_CHECK_PENDING",
        "enabled": "true",
        "source_kind": "HUB_RAIL",
        "epoch_id": "epoch-x",
    }])
    with pytest.raises(ValueError, match="evidence/source mismatch"):
        load_v2_anchor_universe(path)


def test_upstream_matrix_contract_is_hash_closed(tmp_path: Path) -> None:
    anchors = tmp_path / "anchors.csv"
    matrix = tmp_path / "matrix.csv"
    validation = tmp_path / "validation.json"
    anchors.write_text("anchor_id,evidence_status,enabled,source_kind,epoch_id\n", encoding="utf-8")
    matrix.write_text("origin,destination,distance_km,runtime_min,uncertainty\n", encoding="utf-8")
    payload = {
        "status": "PASS_REDUCED_PATH_MATRIX_V2_BUILD",
        "contract": "PHASE2_REDUCED_STOP_PATH_MATRIX_V2",
        "hub_anchor_id": HUB_ID,
        "epoch_id": "epoch-x",
        "prohibitions": {
            "live_osm_used": False,
            "random_generation_used": False,
            "topology_selected": False,
            "proposed_stop_physically_certified": False,
            "context_gtfs_centroid_promoted_to_exact_fact_coordinate": False,
            "headway_or_timetable_selected": False,
            "budget_modified": False,
        },
        "lineage": {
            "routing_anchor_universe_sha256": sha256_path(anchors),
            "reduced_path_matrix_sha256": sha256_path(matrix),
        },
    }
    validation.write_text(json.dumps(payload), encoding="utf-8")
    assert validate_upstream_matrix_contract(validation, anchor_path=anchors, matrix_path=matrix)["epoch_id"] == "epoch-x"
    matrix.write_text(matrix.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    with pytest.raises(ValueError, match="matrix hash"):
        validate_upstream_matrix_contract(validation, anchor_path=anchors, matrix_path=matrix)
