from __future__ import annotations

import importlib.util
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString

MODULE_PATH = Path("scripts/gate_d_structural_candidates.py")
spec = importlib.util.spec_from_file_location("gate_d_structural_candidates", MODULE_PATH)
gate_d_struct = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate_d_struct)


def test_candidate_definitions_use_named_source_anchors_not_manual_coordinates():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"lat": 45.' not in source
    assert '"lon": 9.' not in source
    for candidate in gate_d_struct.CANDIDATES:
        assert candidate["anchors"][0] == "FS"
        assert candidate["anchors"][-1] == "FS"
        for anchor_id in candidate["anchors"]:
            assert anchor_id in gate_d_struct.ANCHOR_SPECS


def test_structural_candidate_set_contains_no_recommendation_language():
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = ["PARETO-OTTIMALE", "Raccomandata", "recommended_variant", "winner"]
    for token in forbidden:
        assert token not in source


def test_brivio_construction_bridge_is_restored_only_with_d185_gtfs_evidence():
    roads = gpd.GeoDataFrame(
        [
            {
                "osm_way_id": 1,
                "highway": "construction",
                "maxweight": "7.5",
                "other_tags": '"bridge:name"=>"Ponte di Brivio","name"=>"Via Bergamo"',
                "geometry": LineString([(9.4480, 45.7420), (9.4500, 45.7420)]),
            },
            {
                "osm_way_id": 2,
                "highway": "primary",
                "maxweight": None,
                "other_tags": '"name"=>"Elsewhere"',
                "geometry": LineString([(9.4300, 45.7300), (9.4310, 45.7300)]),
            },
        ],
        crs=4326,
    )
    d185 = gpd.GeoDataFrame(
        [{
            "feed": "ARRIVA_ADDABUS",
            "route_short_name": "D185",
            "shape_id": "shape",
            "trip_count": 1,
            "geometry": LineString([(9.4475, 45.7420), (9.4505, 45.7420)]),
        }],
        crs=4326,
    )
    structural, detail = gate_d_struct.structuralize_brivio_bridge(roads, d185)
    assert structural.loc[structural["osm_way_id"] == 1, "highway"].iat[0] == "primary"
    assert structural.loc[structural["osm_way_id"] == 2, "highway"].iat[0] == "primary"
    assert detail["temporary_2026_closure_used_in_routing"] is False
    assert detail["restored_structural_way_ids"] == [1]
    assert detail["d185_gtfs_bridge_coverage_35m_pct"] >= 80.0


def test_bridge_reconstruction_fails_closed_without_matching_d185_geometry():
    roads = gpd.GeoDataFrame(
        [{
            "osm_way_id": 1,
            "highway": "construction",
            "maxweight": "7.5",
            "other_tags": '"bridge:name"=>"Ponte di Brivio"',
            "geometry": LineString([(9.4480, 45.7420), (9.4500, 45.7420)]),
        }],
        crs=4326,
    )
    far_d185 = gpd.GeoDataFrame(
        [{
            "feed": "ARRIVA_ADDABUS",
            "route_short_name": "D185",
            "shape_id": "shape",
            "trip_count": 1,
            "geometry": LineString([(9.40, 45.70), (9.41, 45.70)]),
        }],
        crs=4326,
    )
    with pytest.raises(AssertionError, match="D185 official GTFS"):
        gate_d_struct.structuralize_brivio_bridge(roads, far_d185)


def test_osm_named_anchor_is_explicit_assumption_and_requires_bus_eligible_road():
    roads = gpd.GeoDataFrame(
        [{
            "osm_way_id": 10,
            "highway": "unclassified",
            "width": None,
            "lanes": None,
            "other_tags": '"name"=>"Via Mondonico","access"=>"yes","motor_vehicle"=>"yes"',
            "geometry": LineString([(9.3900, 45.7300), (9.4000, 45.7300)]),
        }],
        crs=4326,
    )
    row = gate_d_struct.resolve_osm_road_anchor(
        "MONDONICO",
        {"type": "osm_named_road", "name": "Via Mondonico"},
        roads,
    )
    assert row["epistemic_status"] == "ASSUMPTION"
    assert row["source_type"] == "OSM_NAMED_ROAD_DESIGN_ANCHOR"
    assert row["official_routes_serving"] == ""


def test_summary_always_excludes_temporary_bridge_closure_from_structural_routing():
    metrics = pd.DataFrame(
        [
            {"candidate_id": "WEST_COMPACT_MONDONICO_CW", "route_km": 10.0, "pure_running_minutes": 20.0},
            {"candidate_id": "WEST_COMPACT_MONDONICO_CCW", "route_km": 10.1, "pure_running_minutes": 20.1},
            {"candidate_id": "EAST_COMPACT_ARLATE_CW", "route_km": 13.0, "pure_running_minutes": 28.0},
            {"candidate_id": "EAST_COMPACT_ARLATE_CCW", "route_km": 13.1, "pure_running_minutes": 28.1},
            {"candidate_id": "WEST_RAVELLINO_EXTENSION", "route_km": 18.0, "pure_running_minutes": 38.0},
            {"candidate_id": "EAST_CAPRINO_CELANA_EXTENSION", "route_km": 26.0, "pure_running_minutes": 50.0},
            {"candidate_id": "WEST_SAN_ZENO_SENSITIVITY", "route_km": 10.5, "pure_running_minutes": 21.0},
        ]
    )
    summary = gate_d_struct.build_summary(metrics, {}, {}, {})
    assert summary["analysis_network"] == "STRUCTURAL_NETWORK"
    assert summary["temporary_brivio_closure_used_in_candidate_routing"] is False
    assert summary["gate_b_status"] == "PASS"
    assert summary["verdict"] == "PROVISIONAL"


def test_no_random_generation_in_structural_pipeline():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "np.random" not in source
    assert ".random(" not in source
