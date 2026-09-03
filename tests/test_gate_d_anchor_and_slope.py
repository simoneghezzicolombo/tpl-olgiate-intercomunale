from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ANCHOR_PATH = Path("scripts/gate_d_structural_candidates_v2.py")
SLOPE_PATH = Path("scripts/gate_d_slope_audit.py")

anchor_spec = importlib.util.spec_from_file_location("gate_d_structural_candidates_v2", ANCHOR_PATH)
anchor = importlib.util.module_from_spec(anchor_spec)
assert anchor_spec.loader is not None
anchor_spec.loader.exec_module(anchor)

slope_spec = importlib.util.spec_from_file_location("gate_d_slope_audit", SLOPE_PATH)
slope = importlib.util.module_from_spec(slope_spec)
assert slope_spec.loader is not None
slope_spec.loader.exec_module(slope)


def test_structural_fs_anchor_is_official_trenord_stop_not_bus_centroid():
    assert anchor.base.ANCHOR_SPECS["FS"] == {
        "type": "rail_gtfs_stop",
        "stop_id": "S01514",
    }
    source = ANCHOR_PATH.read_text(encoding="utf-8")
    assert "OFFICIAL_TRENORD_GTFS_STATION" in source
    assert "mean()" not in source


def test_rail_anchor_is_read_from_source_file_not_hardcoded_coordinates(tmp_path, monkeypatch):
    source = tmp_path / "stops.txt"
    source.write_text(
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "S01514,Olgiate-Calco-Brivio,45.72918776556806,9.403662947256066\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(anchor, "RAIL_STOPS", source)
    row = anchor.resolve_rail_station_anchor("FS", {"stop_id": "S01514"})
    assert row["source_ids"] == "S01514"
    assert row["source_type"] == "OFFICIAL_TRENORD_GTFS_STATION"
    assert row["epistemic_status"] == "FACT"
    assert row["lat"] == pytest.approx(45.72918776556806)
    assert row["lon"] == pytest.approx(9.403662947256066)


def test_slope_audit_never_converts_dsm_estimate_into_feasibility_rule():
    source = SLOPE_PATH.read_text(encoding="utf-8")
    assert "ESTIMATE_FROM_COPERNICUS_DSM" in source
    assert '"feasibility_threshold_applied": False' in source
    forbidden = ["BUS_MAX_GRADE", "infeasible_if_grade", "feasible_if_grade"]
    for token in forbidden:
        assert token not in source


def test_slope_profile_spacing_is_explicit_and_positive():
    assert slope.SAMPLE_SPACING_M == 60.0
    assert slope.SAMPLE_SPACING_M > 0
