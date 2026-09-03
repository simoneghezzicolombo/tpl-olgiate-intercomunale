import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from src.phase2_building_piece_access import (
    PIECE_POINT_STATUS,
    _stop_seed_walk_minutes,
    build_section_pieces,
)


def _buildings():
    return gpd.GeoDataFrame([
        {
            "CLASSREF": "DELIVERY::1",
            "footprint_area_m2": 200.0,
            "dbgt_volume_complete": False,
            "dbgt_volume_proxy_m3": float("nan"),
            "eligible_primary": True,
            "eligible_fallback": False,
            "geometry": box(0, 0, 20, 10),
        }
    ], crs=32632)


def _sections():
    return gpd.GeoDataFrame([
        {"section_id": "S1", "municipality_code": "097010", "geometry": box(-5, -5, 10, 15)},
        {"section_id": "S2", "municipality_code": "097012", "geometry": box(10, -5, 25, 15)},
    ], crs=32632)


def test_cross_boundary_building_has_one_piece_point_per_section():
    pieces = build_section_pieces(_buildings(), _sections()).sort_values("section_id").reset_index(drop=True)
    assert len(pieces) == 2
    assert pieces["building_id"].nunique() == 1
    assert set(pieces["section_id"]) == {"S1", "S2"}
    assert pieces["intersection_area_m2"].sum() == pytest.approx(200.0)
    assert pieces["allocation_weight"].sum() == pytest.approx(200.0)
    assert pieces.loc[0, "piece_x_utm32"] < 10
    assert pieces.loc[1, "piece_x_utm32"] >= 10
    assert set(pieces["piece_point_epistemic_status"]) == {PIECE_POINT_STATUS}


def test_piece_point_is_inside_its_section_intersection():
    pieces = build_section_pieces(_buildings(), _sections())
    section_map = _sections().set_index("section_id").geometry.to_dict()
    building_geom = _buildings().geometry.iloc[0]
    for row in pieces.itertuples(index=False):
        point = gpd.GeoSeries.from_xy([row.piece_x_utm32], [row.piece_y_utm32], crs=32632).iloc[0]
        intersection = building_geom.intersection(section_map[row.section_id])
        assert intersection.covers(point)


def test_complete_volume_proxy_is_prorated_by_intersection_area():
    buildings = _buildings()
    buildings["dbgt_volume_complete"] = True
    buildings["dbgt_volume_proxy_m3"] = 1000.0
    pieces = build_section_pieces(buildings, _sections()).sort_values("section_id")
    assert list(pieces["allocation_weight"]) == pytest.approx([500.0, 500.0])
    assert set(pieces["allocation_weight_basis_piece"]) == {
        "DBGT_VOLUME_PROXY_COMPLETE_PRORATED_BY_SECTION_INTERSECTION"
    }


def test_noneligible_building_produces_no_piece():
    buildings = _buildings()
    buildings["eligible_primary"] = False
    buildings["eligible_fallback"] = False
    pieces = build_section_pieces(buildings, _sections())
    assert pieces.empty


def test_duplicate_stop_snap_same_node_uses_minimum_independent_of_row_order():
    stops = pd.DataFrame([
        {"graph_node_id": 20422, "snap_distance_m": 6.616963, "snap_ok": True},
        {"graph_node_id": 20422, "snap_distance_m": 38.834751, "snap_ok": True},
        {"graph_node_id": 25624, "snap_distance_m": 31.562315, "snap_ok": True},
        {"graph_node_id": 25624, "snap_distance_m": 6.906021, "snap_ok": True},
        {"graph_node_id": 99999, "snap_distance_m": 1.0, "snap_ok": False},
    ])
    forward = _stop_seed_walk_minutes(stops, 80.0)
    reversed_rows = _stop_seed_walk_minutes(stops.iloc[::-1].reset_index(drop=True), 80.0)
    assert forward == reversed_rows
    assert forward[20422] == pytest.approx(6.616963 / 80.0)
    assert forward[25624] == pytest.approx(6.906021 / 80.0)
    assert 99999 not in forward
