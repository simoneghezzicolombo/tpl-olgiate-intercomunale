import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from src.phase2_dbgt_composite import (
    make_composite_id,
    normalize_edifc,
    normalize_footprints,
    normalize_volume_units,
    split_composite_id,
)


def test_composite_id_roundtrip():
    value = make_composite_id("20230310_163026", "3357")
    assert value == "20230310_163026::3357"
    assert split_composite_id(value) == ("20230310_163026", "3357")


def test_same_local_classref_different_delivery_stays_distinct():
    raw = gpd.GeoDataFrame([
        {"OBJECTID": 1, "CLASSREF": "1", "COD_CONS": "A", "geometry": box(0, 0, 10, 10)},
        {"OBJECTID": 2, "CLASSREF": "1", "COD_CONS": "B", "geometry": box(20, 0, 30, 10)},
    ], crs=32632)
    out, metrics = normalize_footprints(raw, box(-1, -1, 40, 20))
    assert set(out["building_id"]) == {"A::1", "B::1"}
    assert metrics["raw_unique_global_classref"] == 1
    assert metrics["normalized_composite_building_count"] == 2
    assert metrics["composite_buildings_with_multiple_active_footprint_parts"] == 0


def test_same_composite_footprint_parts_are_unioned():
    raw = gpd.GeoDataFrame([
        {"OBJECTID": 1, "CLASSREF": "1", "COD_CONS": "A", "geometry": box(0, 0, 10, 10)},
        {"OBJECTID": 2, "CLASSREF": "1", "COD_CONS": "A", "geometry": box(10, 0, 20, 10)},
    ], crs=32632)
    out, metrics = normalize_footprints(raw, box(-1, -1, 30, 20))
    assert len(out) == 1
    assert out.loc[0, "footprint_area_m2"] == pytest.approx(200.0)
    assert metrics["extra_active_footprint_rows_collapsed_by_composite_union"] == 1


def test_edifc_global_local_id_collision_is_not_conflict():
    raw = pd.DataFrame([
        {"COD_CONS": "A", "CLASSID": "1", "EDIFC_STAT": "03", "EDIFC_TY": "01"},
        {"COD_CONS": "B", "CLASSID": "1", "EDIFC_STAT": "03", "EDIFC_TY": "08"},
    ])
    out, metrics = normalize_edifc(raw)
    assert set(out["building_id"]) == {"A::1", "B::1"}
    assert metrics["composite_edifc_semantic_conflicts"] == 0


def test_edifc_duplicate_same_composite_same_semantics_collapses():
    raw = pd.DataFrame([
        {"COD_CONS": "A", "CLASSID": "1", "EDIFC_STAT": "03", "EDIFC_TY": "01"},
        {"COD_CONS": "A", "CLASSID": "1", "EDIFC_STAT": "03", "EDIFC_TY": "01"},
    ])
    out, metrics = normalize_edifc(raw)
    assert len(out) == 1
    assert out.loc[0, "active_edifc_source_row_count"] == 2
    assert metrics["extra_active_edifc_rows_collapsed"] == 1


def test_edifc_conflict_within_composite_fails_closed():
    raw = pd.DataFrame([
        {"COD_CONS": "A", "CLASSID": "1", "EDIFC_STAT": "03", "EDIFC_TY": "01"},
        {"COD_CONS": "A", "CLASSID": "1", "EDIFC_STAT": "03", "EDIFC_TY": "08"},
    ])
    with pytest.raises(RuntimeError, match="semantic conflict"):
        normalize_edifc(raw)


def test_volume_same_local_unit_different_delivery_stays_distinct():
    raw = pd.DataFrame([
        {"COD_CONS": "A", "CEDIUV": "1", "CLASSID": "77", "UN_VOL_AV": 3, "UN_VOL_EX": 3, "UN_VOL_QE": 3, "Shape_Area": 100},
        {"COD_CONS": "B", "CEDIUV": "1", "CLASSID": "77", "UN_VOL_AV": 4, "UN_VOL_EX": 4, "UN_VOL_QE": 4, "Shape_Area": 120},
    ])
    out, _ = normalize_volume_units(raw)
    assert set(out["volume_unit_id"]) == {"A::77", "B::77"}
    assert set(out["building_id"]) == {"A::1", "B::1"}


def test_volume_duplicate_same_composite_identical_numeric_collapses():
    raw = pd.DataFrame([
        {"COD_CONS": "A", "CEDIUV": "1", "CLASSID": "77", "UN_VOL_AV": 3, "UN_VOL_EX": 3, "UN_VOL_QE": 3, "Shape_Area": 100},
        {"COD_CONS": "A", "CEDIUV": "1", "CLASSID": "77", "UN_VOL_AV": 3, "UN_VOL_EX": 3, "UN_VOL_QE": 3, "Shape_Area": 100},
    ])
    out, metrics = normalize_volume_units(raw)
    assert len(out) == 1
    assert metrics["extra_active_volume_rows_collapsed"] == 1


def test_volume_numeric_conflict_within_composite_fails_closed():
    raw = pd.DataFrame([
        {"COD_CONS": "A", "CEDIUV": "1", "CLASSID": "77", "UN_VOL_AV": 3, "UN_VOL_EX": 3, "UN_VOL_QE": 3, "Shape_Area": 100},
        {"COD_CONS": "A", "CEDIUV": "1", "CLASSID": "77", "UN_VOL_AV": 4, "UN_VOL_EX": 3, "UN_VOL_QE": 3, "Shape_Area": 100},
    ])
    with pytest.raises(RuntimeError, match="numeric conflict"):
        normalize_volume_units(raw)
