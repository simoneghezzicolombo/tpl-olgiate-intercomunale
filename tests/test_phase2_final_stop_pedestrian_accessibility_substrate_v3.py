from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
    PedestrianGraph,
    RT028ContractError,
    SPECIAL_STOP_ID,
    build_atomic_walk_matrix,
    canonical_dataframe_sha256,
    parse_osm_pedestrian_graph,
)
from scripts.phase2_fetch_rt028_osm_pedestrian_snapshot_v3 import (
    canonicalize_overpass_osm_bytes,
)


def _stops() -> pd.DataFrame:
    rows = []
    for i in range(35):
        rows.append({
            "stop_place_id": f"STOP::{i:02d}",
            "stop_name": f"Stop {i}",
            "municipality": "A" if i % 2 == 0 else "B",
            "lat": 45.0000,
            "lon": 9.0010,
            "service_class": "CONVENTIONAL_TPL",
        })
    rows.append({
        "stop_place_id": SPECIAL_STOP_ID,
        "stop_name": "Casa di Comunità",
        "municipality": "A",
        "lat": 45.0000,
        "lon": 9.0010,
        "service_class": "SPECIAL_SERVICE",
    })
    return pd.DataFrame(rows)


def _population() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "unit_id": "P_CORE",
            "lat": 45.0000,
            "lon": 9.0000,
            "municipality_code": "001",
            "municipality_name": "A",
            "population_weight_2025": 10.0,
            "population_scope": "core",
        },
        {
            "unit_id": "P_EXT",
            "lat": 45.0000,
            "lon": 9.0000,
            "municipality_code": "002",
            "municipality_name": "B",
            "population_weight_2025": 5.0,
            "population_scope": "external",
        },
    ])


def _graph(disconnected: bool = False, obstacles=()) -> PedestrianGraph:
    node_ids = ("n1", "n2", "n3", "n4")
    latitudes = np.array([45.0, 45.0, 45.0010, 45.0010])
    longitudes = np.array([9.0, 9.0010, 9.0, 9.0010])
    if disconnected:
        adjacency = {
            "n1": [("n3", 111.2)],
            "n3": [("n1", 111.2)],
            "n2": [("n4", 111.2)],
            "n4": [("n2", 111.2)],
        }
    else:
        adjacency = {
            "n1": [("n3", 111.2)],
            "n3": [("n1", 111.2), ("n4", 78.6)],
            "n4": [("n3", 78.6), ("n2", 111.2)],
            "n2": [("n4", 111.2)],
        }
    reverse = {n: [] for n in node_ids}
    for u, edges in adjacency.items():
        for v, d in edges:
            reverse[v].append((u, d))
    return PedestrianGraph(
        node_ids=node_ids,
        latitudes=latitudes,
        longitudes=longitudes,
        adjacency=adjacency,
        reverse_adjacency=reverse,
        blocked_node_ids=frozenset(),
        obstacle_geometries=tuple(obstacles),
        osm_sha256="a" * 64,
        graph_digest="b" * 64,
    )


def test_graph_route_not_straight_line() -> None:
    matrix, audit = build_atomic_walk_matrix(
        graph=_graph(), population_units=_population().iloc[[0]], stops=_stops()
    )
    row = matrix[matrix.stop_place_id == "STOP::00"].iloc[0]
    assert row.reachability_status == "REACHABLE"
    assert row.walk_distance_m > 78.6 * 3
    assert audit["negative_assertions"]["uses_straight_line_as_routing_engine"] is False


def test_cross_municipality_pair_routes_without_border_filter() -> None:
    stops = _stops()
    stops.loc[stops.stop_place_id == "STOP::00", "municipality"] = "OTHER"
    matrix, audit = build_atomic_walk_matrix(
        graph=_graph(), population_units=_population().iloc[[0]], stops=stops
    )
    row = matrix[matrix.stop_place_id == "STOP::00"].iloc[0]
    assert row.population_municipality_name != row.stop_municipality
    assert row.reachability_status == "REACHABLE"
    assert audit["negative_assertions"]["treats_municipal_border_as_barrier"] is False


def test_barrier_aware_snap_rejects_connector_crossing_obstacle() -> None:
    obstacle = LineString([(8.9999, 44.9995), (8.9999, 45.0005)])
    snap = _graph(obstacles=(obstacle,)).snap(45.0, 8.9998, max_connector_m=50)
    assert snap.status == "UNREACHABLE"
    assert snap.reason == "CONNECTOR_BLOCKED_BY_BARRIER"


def test_explicit_unreachable_when_graph_components_disconnected() -> None:
    matrix, audit = build_atomic_walk_matrix(
        graph=_graph(disconnected=True), population_units=_population().iloc[[0]], stops=_stops()
    )
    row = matrix[matrix.stop_place_id == "STOP::00"].iloc[0]
    assert row.reachability_status == "UNREACHABLE"
    assert row.unreachable_reason == "GRAPH_DISCONNECTED"
    assert audit["unreachable_pair_count"] > 0


def test_connector_failure_is_explicit_not_euclidean_fallback() -> None:
    pop = _population().iloc[[0]].copy()
    pop["lon"] = 8.0
    matrix, _ = build_atomic_walk_matrix(graph=_graph(), population_units=pop, stops=_stops())
    assert set(matrix.reachability_status) == {"UNREACHABLE"}
    assert all(str(v).startswith("POPULATION_NO_ACCESSIBLE_NODE") for v in matrix.unreachable_reason)


def test_frozen_36_stop_contract_and_special_service_retained() -> None:
    matrix, audit = build_atomic_walk_matrix(
        graph=_graph(), population_units=_population().iloc[[0]], stops=_stops()
    )
    assert len(matrix) == 36
    assert audit["stop_count"] == 36
    assert audit["conventional_stop_count"] == 35
    assert audit["special_service_stop_count"] == 1
    special = matrix[matrix.stop_place_id == SPECIAL_STOP_ID]
    assert len(special) == 1
    assert special.iloc[0].stop_service_class == "SPECIAL_SERVICE"


def test_old_43_stop_universe_fails_closed() -> None:
    stops = pd.concat([_stops(), _stops().iloc[:7].assign(
        stop_place_id=[f"OLD::{i}" for i in range(7)]
    )], ignore_index=True)
    with pytest.raises(RT028ContractError, match="exactly 36"):
        build_atomic_walk_matrix(graph=_graph(), population_units=_population().iloc[[0]], stops=stops)


def test_population_core_external_identity_and_weight_preserved() -> None:
    matrix, audit = build_atomic_walk_matrix(graph=_graph(), population_units=_population(), stops=_stops())
    assert audit["population_unit_count"] == 2
    subset = matrix[["population_unit_id", "population_scope", "population_weight_2025"]].drop_duplicates()
    got = {tuple(x) for x in subset.itertuples(index=False, name=None)}
    assert ("P_CORE", "core", 10.0) in got
    assert ("P_EXT", "external", 5.0) in got


def test_input_order_invariance_and_deterministic_ids_digest() -> None:
    a, aa = build_atomic_walk_matrix(graph=_graph(), population_units=_population(), stops=_stops())
    b, bb = build_atomic_walk_matrix(
        graph=_graph(),
        population_units=_population().sample(frac=1, random_state=42),
        stops=_stops().sample(frac=1, random_state=43),
    )
    pd.testing.assert_frame_equal(a, b)
    assert aa["matrix_sha256"] == bb["matrix_sha256"]
    assert list(a.pair_id) == list(b.pair_id)


def test_candidate_selection_fields_fail_closed() -> None:
    pop = _population().copy()
    pop["candidate_id"] = "FORBIDDEN"
    with pytest.raises(RT028ContractError, match="forbidden"):
        build_atomic_walk_matrix(graph=_graph(), population_units=pop, stops=_stops())


def test_no_threshold_ranking_topology_or_winner_outputs() -> None:
    matrix, audit = build_atomic_walk_matrix(
        graph=_graph(), population_units=_population().iloc[[0]], stops=_stops()
    )
    cols = " ".join(matrix.columns).lower()
    for token in ("threshold", "rank", "score", "winner", "primary", "runner_up", "backbone"):
        assert token not in cols
    assert all(v is False for v in audit["negative_assertions"].values())


def test_canonical_digest_is_row_order_invariant() -> None:
    matrix, _ = build_atomic_walk_matrix(graph=_graph(), population_units=_population(), stops=_stops())
    d1 = canonical_dataframe_sha256(matrix, ["population_unit_id", "stop_place_id"])
    d2 = canonical_dataframe_sha256(
        matrix.sample(frac=1, random_state=7), ["population_unit_id", "stop_place_id"]
    )
    assert d1 == d2


def test_overpass_snapshot_canonicalization_removes_response_time_only() -> None:
    prefix = b'<osm version="0.6">\n<note>same entities</note>\n'
    suffix = b'\n<node id="1" lat="45.0" lon="9.0"/>\n</osm>\n'
    a = prefix + b'<meta osm_base="2026-09-06T14:05:18Z"/>' + suffix
    b = prefix + b'<meta osm_base="2026-09-06T14:18:36Z"/>' + suffix
    ca = canonicalize_overpass_osm_bytes(a)
    cb = canonicalize_overpass_osm_bytes(b)
    assert ca == cb
    assert b"osm_base" not in ca
    assert b'<node id="1" lat="45.0" lon="9.0"/>' in ca
    with pytest.raises(RuntimeError, match="exactly one volatile Overpass"):
        canonicalize_overpass_osm_bytes(prefix + suffix)


def test_osm_parser_honours_foot_no_and_barrier_node(tmp_path: Path) -> None:
    osm = tmp_path / "tiny.osm"
    osm.write_text("""<osm version="0.6">
      <node id="1" lat="45.0" lon="9.0"/>
      <node id="2" lat="45.0" lon="9.001"><tag k="barrier" v="block"/></node>
      <node id="3" lat="45.0" lon="9.002"/>
      <node id="4" lat="45.001" lon="9.0"/>
      <way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="footway"/></way>
      <way id="11"><nd ref="1"/><nd ref="4"/><tag k="highway" v="path"/><tag k="foot" v="no"/></way>
      <way id="12"><nd ref="1"/><nd ref="3"/><tag k="railway" v="rail"/></way>
    </osm>""", encoding="utf-8")
    with pytest.raises(RT028ContractError, match="no routable"):
        parse_osm_pedestrian_graph(osm)


def test_osm_parser_builds_network_and_obstacle_geometry(tmp_path: Path) -> None:
    osm = tmp_path / "tiny2.osm"
    osm.write_text("""<osm version="0.6">
      <node id="1" lat="45.0" lon="9.0"/>
      <node id="2" lat="45.0" lon="9.001"/>
      <node id="3" lat="45.001" lon="9.001"/>
      <node id="4" lat="44.9995" lon="9.0005"/>
      <node id="5" lat="45.0005" lon="9.0005"/>
      <way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/></way>
      <way id="12"><nd ref="4"/><nd ref="5"/><tag k="railway" v="rail"/></way>
    </osm>""", encoding="utf-8")
    graph = parse_osm_pedestrian_graph(osm)
    assert set(graph.node_ids) == {"1", "2", "3"}
    assert len(graph.obstacle_geometries) == 1
    assert len(graph.osm_sha256) == 64
    assert len(graph.graph_digest) == 64


def test_every_population_stop_pair_has_explicit_status() -> None:
    matrix, audit = build_atomic_walk_matrix(graph=_graph(), population_units=_population(), stops=_stops())
    assert len(matrix) == 72
    assert matrix.reachability_status.notna().all()
    unreachable = matrix.reachability_status == "UNREACHABLE"
    assert matrix.loc[unreachable, "unreachable_reason"].astype(str).ne("").all()
    assert audit["pair_count"] == 72
