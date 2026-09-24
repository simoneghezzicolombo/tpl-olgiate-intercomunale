import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_gate_b_bridge import evaluate_candidate_coverage


def _fixture(tmp_path, stop_status="MODEL OUTPUT"):
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    coords = [(9.405, 45.733), (9.415, 45.733)]
    xy = [transformer.transform(lon, lat) for lon, lat in coords]
    nodes = pd.DataFrame([
        {"node_id": 1, "x_utm32": xy[0][0], "y_utm32": xy[0][1], "in_giant_component": True},
        {"node_id": 2, "x_utm32": xy[1][0], "y_utm32": xy[1][1], "in_giant_component": True},
    ])
    edges = pd.DataFrame([
        {"u": 1, "v": 2, "walk_min_uv": 10.0, "walk_min_vu": 10.0, "in_giant_component": True},
    ])
    population = pd.DataFrame([
        {"cell_id": "C1", "PRO_COM_T": "001", "COMUNE": "One", "pop_calibrated_2025": 40.0, "nearest_graph_node_id": 1, "connector_walk_min": 0.0, "connector_within_limit": True},
        {"cell_id": "C2", "PRO_COM_T": "002", "COMUNE": "Two", "pop_calibrated_2025": 60.0, "nearest_graph_node_id": 2, "connector_walk_min": 0.0, "connector_within_limit": True},
    ])
    stops = pd.DataFrame([
        {"scenario_id": "A", "stop_id": "A1", "stop_lat": coords[0][1], "stop_lon": coords[0][0], "territory_id": "T1", "epistemic_status": stop_status, "source": "TEST_A"},
        {"scenario_id": "B", "stop_id": "B1", "stop_lat": coords[1][1], "stop_lon": coords[1][0], "territory_id": "T2", "epistemic_status": stop_status, "source": "TEST_B"},
    ])
    paths = {}
    for name, frame in [("nodes", nodes), ("edges", edges), ("population", population), ("stops", stops)]:
        path = tmp_path / f"{name}.csv"; frame.to_csv(path, index=False); paths[name] = path
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({
        "schema_version": 1, "comparison_id": "TEST_B", "threshold_min": 6,
        "max_stop_snap_m": 250, "walk_connector_kmh": 4.8,
        "territory_definition_id": "TEST_TERRITORIES",
    }), encoding="utf-8")
    paths["policy"] = policy
    return paths


def _run(paths):
    return evaluate_candidate_coverage(
        paths["stops"], paths["nodes"], paths["edges"], paths["population"], paths["policy"],
        gate_b_commit="b" * 40,
    ).set_index("scenario_id")


def test_candidate_coverage_reuses_network_not_euclidean_buffer(tmp_path):
    out = _run(_fixture(tmp_path))
    assert out.loc["A", "population_covered_pct"] == 40.0
    assert out.loc["B", "population_covered_pct"] == 60.0
    assert out.loc["A", "population_denominator"] == 100.0
    assert "threshold=6min" in out.loc["A", "population_covered_pct__comparison_basis"]


def test_territory_count_is_explicit_stop_territory_definition(tmp_path):
    out = _run(_fixture(tmp_path))
    assert out.loc["A", "territories_served_count"] == 1
    assert "TEST_TERRITORIES" in out.loc["A", "territories_served_count__comparison_basis"]


def test_assumption_candidate_stops_are_refused(tmp_path):
    with pytest.raises(ValueError, match="ASSUMPTION"):
        _run(_fixture(tmp_path, "ASSUMPTION"))
