import geopandas as gpd
import pytest
from shapely.geometry import box

from src.phase2_dbgt_unlinked_footprints import normalize_footprints


def test_blank_classref_is_excluded_not_invented():
    raw = gpd.GeoDataFrame([
        {"OBJECTID": 1, "CLASSREF": "1", "COD_CONS": "A", "geometry": box(0, 0, 10, 10)},
        {"OBJECTID": 2, "CLASSREF": None, "COD_CONS": "A", "geometry": box(20, 0, 30, 10)},
    ], crs=32632)
    out, metrics = normalize_footprints(raw, box(-1, -1, 40, 20))
    assert list(out["building_id"]) == ["A::1"]
    assert metrics["raw_selected_active_footprint_rows"] == 2
    assert metrics["raw_linked_active_footprint_rows"] == 1
    assert metrics["raw_active_footprints_without_classref_excluded"] == 1
    assert metrics["raw_active_footprints_without_classref_excluded_area_m2"] == pytest.approx(100.0)
    assert metrics["unlinked_footprints_population_assigned"] is False


def test_missing_delivery_scope_fails_closed():
    raw = gpd.GeoDataFrame([
        {"OBJECTID": 1, "CLASSREF": "1", "COD_CONS": None, "geometry": box(0, 0, 10, 10)},
    ], crs=32632)
    with pytest.raises(RuntimeError, match="lacks COD_CONS"):
        normalize_footprints(raw, box(-1, -1, 20, 20))


def test_all_unlinked_fails_closed():
    raw = gpd.GeoDataFrame([
        {"OBJECTID": 1, "CLASSREF": None, "COD_CONS": "A", "geometry": box(0, 0, 10, 10)},
    ], crs=32632)
    with pytest.raises(RuntimeError, match="no auditable building universe"):
        normalize_footprints(raw, box(-1, -1, 20, 20))
