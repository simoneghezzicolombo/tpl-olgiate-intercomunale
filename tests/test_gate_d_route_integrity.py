from __future__ import annotations

import importlib.util
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
import pytest
from shapely.geometry import LineString

MODULE_PATH = Path("scripts/gate_d_route_integrity.py")
spec = importlib.util.spec_from_file_location("gate_d_route_integrity", MODULE_PATH)
gate_d = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate_d)


def _toy_roads():
    return gpd.GeoDataFrame(
        [
            {
                "osm_way_id": 1,
                "highway": "residential",
                "other_tags": '"oneway"=>"yes","maxspeed"=>"30"',
                "geometry": LineString([(9.4000, 45.7300), (9.4010, 45.7300)]),
            },
            {
                "osm_way_id": 2,
                "highway": "residential",
                "other_tags": '"maxspeed"=>"30"',
                "geometry": LineString([(9.4010, 45.7300), (9.4020, 45.7300)]),
            },
        ],
        crs=4326,
    )


def _edge(graph, u, v, way, minutes=1.0):
    graph.add_edge(
        u,
        v,
        osm_way_id=way,
        running_minutes=minutes,
        length_m=100.0,
        speed_status="MODEL_OUTPUT_FROM_OSM_MAXSPEED",
        uncertainty_flags="",
        geometry=LineString([u, v]),
    )


def test_legacy_candidate_script_contains_no_precomputed_metrics_or_recommendation():
    text = Path("scripts/08_candidate_routes.py").read_text(encoding="utf-8")
    forbidden = [
        "pop_servita_5min", "od_flusso_intercettato", "runtime_ovest_min",
        "km_ovest", "PARETO-OTTIMALE", "(Raccomandata)",
    ]
    for token in forbidden:
        assert token not in text


def test_bus_graph_honours_oneway_and_uses_projected_metric_lengths():
    graph = gate_d.build_bus_graph(_toy_roads())
    assert graph.number_of_edges() == 3
    lengths = [d["length_m"] for _, _, d in graph.edges(data=True)]
    assert all(50 < x < 150 for x in lengths)
    assert all(d["running_minutes"] > 0 for _, _, d in graph.edges(data=True))
    assert {d["osm_way_id"] for _, _, d in graph.edges(data=True)} == {1, 2}


def test_multivertex_osm_way_is_split_at_internal_vertices():
    roads = gpd.GeoDataFrame(
        [{
            "osm_way_id": 10,
            "highway": "residential",
            "other_tags": '"maxspeed"=>"30"',
            "geometry": LineString([
                (9.4000, 45.7300), (9.4010, 45.7300), (9.4020, 45.7300)
            ]),
        }],
        crs=4326,
    )
    graph = gate_d.build_bus_graph(roads)
    assert graph.number_of_edges() == 4
    assert graph.number_of_nodes() == 3


def test_oneway_minus_one_routes_only_reverse_direction():
    roads = gpd.GeoDataFrame(
        [{
            "osm_way_id": 10,
            "highway": "residential",
            "other_tags": '"oneway"=>"-1"',
            "geometry": LineString([(9.4000, 45.7300), (9.4010, 45.7300)]),
        }],
        crs=4326,
    )
    graph = gate_d.build_bus_graph(roads)
    assert graph.number_of_edges() == 1
    u, v = next(iter(graph.edges()))
    assert u[0] > v[0]


def test_roundabout_defaults_to_oneway_when_tag_missing():
    direction, warning = gate_d.oneway_direction({"junction": "roundabout"})
    assert direction == 1
    assert warning is None


def test_explicit_access_restriction_is_excluded_unless_bus_override_exists():
    row = pd.Series({"highway": "residential", "other_tags": '"access"=>"private"'})
    eligible, reasons = gate_d.bus_eligibility(row)
    assert not eligible
    assert "explicit_access_restriction" in reasons
    override = pd.Series({
        "highway": "residential",
        "other_tags": '"access"=>"private","bus"=>"yes"',
    })
    eligible, _ = gate_d.bus_eligibility(override)
    assert eligible


def test_explicit_bus_no_always_excluded():
    row = pd.Series({"highway": "residential", "other_tags": '"bus"=>"no"'})
    eligible, reasons = gate_d.bus_eligibility(row)
    assert not eligible
    assert "explicit_bus_restriction" in reasons


def test_unknown_road_class_not_silently_routed():
    row = pd.Series({"highway": "footway", "other_tags": ""})
    eligible, reasons = gate_d.bus_eligibility(row)
    assert not eligible
    assert reasons == ["highway=footway"]


def test_top_level_maxspeed_column_is_not_lost():
    row = pd.Series({"highway": "residential", "maxspeed": "30", "other_tags": ""})
    tags = gate_d.row_tags(row)
    speed, status = gate_d.parse_speed_kmh(tags, "residential")
    assert speed == pytest.approx(21.0)
    assert status == "MODEL_OUTPUT_FROM_OSM_MAXSPEED"


def test_missing_maxspeed_is_explicit_assumption_not_fact():
    speed, status = gate_d.parse_speed_kmh({}, "residential")
    assert speed == gate_d.DEFAULT_SPEED_KMH["residential"]
    assert status == "ASSUMPTION_BY_HIGHWAY_CLASS"


def test_osm_maxspeed_still_produces_model_output_not_observed_runtime():
    speed, status = gate_d.parse_speed_kmh({"maxspeed": "30"}, "residential")
    assert speed == pytest.approx(21.0)
    assert status == "MODEL_OUTPUT_FROM_OSM_MAXSPEED"


def test_no_turn_restriction_forces_legal_alternative_path():
    graph = nx.MultiDiGraph()
    start, via, dest, alt = (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 1.0)
    _edge(graph, start, via, 100, 1.0)
    _edge(graph, via, dest, 200, 1.0)
    _edge(graph, via, alt, 300, 1.1)
    _edge(graph, alt, dest, 400, 1.1)
    restrictions = {
        (via, 100): [{"restriction": "no_straight_on", "to_way": 200, "relation_id": 1}]
    }
    path = gate_d.shortest_bus_edges(graph, start, dest, restrictions)
    used_ways = [graph.get_edge_data(u, v, key)["osm_way_id"] for u, v, key in path]
    assert used_ways == [100, 300, 400]


def test_only_turn_restriction_forces_named_to_way():
    graph = nx.MultiDiGraph()
    start, via, dest, forbidden = (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 1.0)
    _edge(graph, start, via, 100, 1.0)
    _edge(graph, via, dest, 200, 2.0)
    _edge(graph, via, forbidden, 300, 0.1)
    _edge(graph, forbidden, dest, 400, 0.1)
    restrictions = {
        (via, 100): [{"restriction": "only_straight_on", "to_way": 200, "relation_id": 2}]
    }
    path = gate_d.shortest_bus_edges(graph, start, dest, restrictions)
    used_ways = [graph.get_edge_data(u, v, key)["osm_way_id"] for u, v, key in path]
    assert used_ways == [100, 200]


def test_no_u_turn_does_not_block_straight_continuation_on_same_osm_way():
    via, previous, straight = (1.0, 0.0), (0.0, 0.0), (2.0, 0.0)
    restrictions = {
        (via, 10): [{"restriction": "no_u_turn", "to_way": 10, "relation_id": 3}]
    }
    assert not gate_d.transition_allowed(restrictions, via, previous, 10, previous, 10)
    assert gate_d.transition_allowed(restrictions, via, previous, 10, straight, 10)


def test_waypoint_schema_requires_epistemic_status_and_rejects_duplicates():
    good = pd.DataFrame({
        "candidate_id": ["A", "A"], "sequence": [1, 2],
        "lat": [45.73, 45.731], "lon": [9.40, 9.41],
        "epistemic_status": ["ASSUMPTION", "FACT"],
    })
    gate_d.validate_waypoints(good)
    bad = good.copy()
    bad.loc[1, "sequence"] = 1
    with pytest.raises(ValueError, match="Duplicate sequence"):
        gate_d.validate_waypoints(bad)


def test_far_waypoint_fails_closed_instead_of_snapping_anywhere():
    graph = gate_d.build_bus_graph(_toy_roads())
    points = gpd.GeoDataFrame(
        {
            "candidate_id": ["A", "A"], "sequence": [1, 2],
            "epistemic_status": ["ASSUMPTION", "ASSUMPTION"],
        },
        geometry=gpd.points_from_xy([9.9, 9.901], [46.0, 46.001]),
        crs=4326,
    )
    with pytest.raises(ValueError, match="snap distance"):
        gate_d.route_candidate(graph, points, "A", max_snap_m=100.0)


def test_no_random_generation_in_gate_d_pipeline():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "np.random" not in text
    assert ".random(" not in text
