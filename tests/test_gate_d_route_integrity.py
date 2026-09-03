from __future__ import annotations

import importlib.util
from pathlib import Path

import geopandas as gpd
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
                "highway": "residential",
                "other_tags": '"oneway"=>"yes","maxspeed"=>"30"',
                "geometry": LineString([(9.4000, 45.7300), (9.4010, 45.7300)]),
            },
            {
                "highway": "residential",
                "other_tags": '"maxspeed"=>"30"',
                "geometry": LineString([(9.4010, 45.7300), (9.4020, 45.7300)]),
            },
        ],
        crs=4326,
    )


def test_legacy_candidate_script_contains_no_precomputed_metrics_or_recommendation():
    text = Path("scripts/08_candidate_routes.py").read_text(encoding="utf-8")
    forbidden = [
        "pop_servita_5min",
        "od_flusso_intercettato",
        "runtime_ovest_min",
        "km_ovest",
        "PARETO-OTTIMALE",
        "(Raccomandata)",
    ]
    for token in forbidden:
        assert token not in text


def test_bus_graph_honours_oneway_and_uses_projected_metric_lengths():
    graph = gate_d.build_bus_graph(_toy_roads())
    assert graph.number_of_edges() == 3  # one directed + one bidirectional segment
    lengths = [d["length_m"] for _, _, d in graph.edges(data=True)]
    assert all(50 < x < 150 for x in lengths)
    assert all(d["running_minutes"] > 0 for _, _, d in graph.edges(data=True))


def test_explicit_access_restriction_is_excluded():
    row = pd.Series({"highway": "residential", "other_tags": '"access"=>"private"'})
    eligible, reasons = gate_d.bus_eligibility(row)
    assert not eligible
    assert "explicit_access_restriction" in reasons


def test_unknown_road_class_not_silently_routed():
    row = pd.Series({"highway": "footway", "other_tags": ""})
    eligible, reasons = gate_d.bus_eligibility(row)
    assert not eligible
    assert reasons == ["highway=footway"]


def test_missing_maxspeed_is_explicit_assumption_not_fact():
    speed, status = gate_d.parse_speed_kmh({}, "residential")
    assert speed == gate_d.DEFAULT_SPEED_KMH["residential"]
    assert status == "ASSUMPTION_BY_HIGHWAY_CLASS"


def test_osm_maxspeed_still_produces_model_output_not_observed_runtime():
    speed, status = gate_d.parse_speed_kmh({"maxspeed": "30"}, "residential")
    assert speed == pytest.approx(21.0)
    assert status == "MODEL OUTPUT_FROM_OSM_MAXSPEED"


def test_waypoint_schema_requires_epistemic_status_and_rejects_duplicates():
    good = pd.DataFrame(
        {
            "candidate_id": ["A", "A"],
            "sequence": [1, 2],
            "lat": [45.73, 45.731],
            "lon": [9.40, 9.41],
            "epistemic_status": ["ASSUMPTION", "FACT"],
        }
    )
    gate_d.validate_waypoints(good)
    bad = good.copy()
    bad.loc[1, "sequence"] = 1
    with pytest.raises(ValueError, match="Duplicate sequence"):
        gate_d.validate_waypoints(bad)


def test_no_random_generation_in_gate_d_pipeline():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "np.random" not in text
    assert ".random(" not in text
