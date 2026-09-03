from __future__ import annotations

import geopandas as gpd
from shapely.geometry import box

from src.phase2_dbgt_footprints import (
    NORMALIZED_GEOMETRY_STATUS,
    normalize_active_building_footprints,
)


def _gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=32632)


def test_exact_duplicate_source_rows_do_not_double_count_area():
    geom = box(0, 0, 10, 10)
    raw = _gdf([
        {"CLASSREF": "A", "geometry": geom},
        {"CLASSREF": "A", "geometry": geom},
    ])
    out, metrics = normalize_active_building_footprints(raw, box(-1, -1, 20, 20))
    assert len(out) == 1
    assert out.iloc[0].footprint_area_m2 == 100.0
    assert metrics["classref_with_multiple_active_footprint_parts"] == 1
    assert metrics["extra_active_footprint_rows_collapsed_by_union"] == 1


def test_disjoint_parts_of_same_building_are_preserved_by_union():
    raw = _gdf([
        {"CLASSREF": "A", "geometry": box(0, 0, 10, 10)},
        {"CLASSREF": "A", "geometry": box(20, 0, 25, 10)},
    ])
    out, _ = normalize_active_building_footprints(raw, box(-1, -1, 30, 20))
    assert len(out) == 1
    assert out.iloc[0].footprint_area_m2 == 150.0
    assert out.iloc[0].geometry.geom_type in {"MultiPolygon", "Polygon"}


def test_overlapping_parts_are_unioned_without_double_counting_overlap():
    raw = _gdf([
        {"CLASSREF": "A", "geometry": box(0, 0, 10, 10)},
        {"CLASSREF": "A", "geometry": box(5, 0, 15, 10)},
    ])
    out, _ = normalize_active_building_footprints(raw, box(-1, -1, 20, 20))
    assert out.iloc[0].footprint_area_m2 == 150.0


def test_blank_classref_is_excluded_and_accounted_not_merged_into_fake_building():
    raw = _gdf([
        {"CLASSREF": None, "geometry": box(0, 0, 2, 2)},
        {"CLASSREF": "", "geometry": box(3, 0, 5, 2)},
        {"CLASSREF": "A", "geometry": box(6, 0, 10, 2)},
    ])
    out, metrics = normalize_active_building_footprints(raw, box(-1, -1, 20, 20))
    assert out.CLASSREF.tolist() == ["A"]
    assert metrics["raw_active_footprints_without_classref_excluded"] == 2
    assert metrics["raw_linked_active_footprint_rows"] == 1


def test_outside_selected_geography_is_not_part_of_normalization():
    raw = _gdf([
        {"CLASSREF": "A", "geometry": box(0, 0, 5, 5)},
        {"CLASSREF": "B", "geometry": box(100, 100, 105, 105)},
    ])
    out, metrics = normalize_active_building_footprints(raw, box(-1, -1, 10, 10))
    assert out.CLASSREF.tolist() == ["A"]
    assert metrics["normalized_building_classref_count"] == 1


def test_geometry_status_is_explicitly_derived():
    raw = _gdf([{"CLASSREF": "A", "geometry": box(0, 0, 1, 1)}])
    _, metrics = normalize_active_building_footprints(raw, box(-1, -1, 2, 2))
    assert metrics["normalized_geometry_epistemic_status"] == NORMALIZED_GEOMETRY_STATUS
    assert NORMALIZED_GEOMETRY_STATUS.startswith("DERIVED_")
    assert metrics["random_used"] is False
    assert metrics["sampling_used"] is False
