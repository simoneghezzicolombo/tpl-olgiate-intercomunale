from __future__ import annotations

import pandas as pd
import pytest

from src.phase2_frozen_graph import EPOCH_ID
from src.phase2_reduced_path_matrix import (
    HUB_ID,
    build_path_matrix,
    build_source_anchor_records,
    collapse_routing_anchors,
)


def test_collapse_same_graph_node_prefers_hub_then_existing_then_proposed() -> None:
    source = pd.DataFrame([
        {
            "source_anchor_id": HUB_ID,
            "source_kind": "HUB_RAIL",
            "graph_node_id": "n:H",
            "snap_distance_m": 0.0,
            "evidence_status": "FACT",
            "municipality": "Olgiate Molgora",
            "route_ready": True,
        },
        {
            "source_anchor_id": "existing:EX_001",
            "source_kind": "EXISTING_PHYSICAL_STOP_CLUSTER",
            "graph_node_id": "n:H",
            "snap_distance_m": 3.0,
            "evidence_status": "FACT",
            "municipality": "Olgiate Molgora",
            "route_ready": True,
        },
        {
            "source_anchor_id": "P2S_0001",
            "source_kind": "PROPOSED_STOP",
            "graph_node_id": "n:H",
            "snap_distance_m": 2.0,
            "evidence_status": "PROPOSED_STOP/FIELD_CHECK_PENDING",
            "municipality": "Olgiate Molgora",
            "route_ready": True,
        },
        {
            "source_anchor_id": "P2S_0002",
            "source_kind": "PROPOSED_STOP",
            "graph_node_id": "n:A",
            "snap_distance_m": 2.0,
            "evidence_status": "PROPOSED_STOP/FIELD_CHECK_PENDING",
            "municipality": "Calco",
            "route_ready": True,
        },
    ])
    routing, membership = collapse_routing_anchors(source)
    assert set(routing["anchor_id"]) == {HUB_ID, "P2S_0002"}
    hub_row = routing.loc[routing["anchor_id"] == HUB_ID].iloc[0]
    assert hub_row["source_member_count"] == 3
    collapsed = membership.loc[membership["graph_node_id"] == "n:H"]
    assert set(collapsed["routing_anchor_id"]) == {HUB_ID}
    assert set(collapsed["collapse_reason"]) == {"COLLAPSED_SAME_FROZEN_GRAPH_NODE"}


def _edges_fixture() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "edge_id": "e1", "u_node_id": "n:H", "v_node_id": "n:A",
            "length_m": "1000", "running_minutes_model": "2", "osm_way_id": "1",
            "uncertainty_flags": "missing_width", "highway": "primary",
        },
        {
            "edge_id": "e2", "u_node_id": "n:A", "v_node_id": "n:H",
            "length_m": "1300", "running_minutes_model": "3", "osm_way_id": "2",
            "uncertainty_flags": "conditional_access=destination", "highway": "service",
        },
        {
            "edge_id": "e3", "u_node_id": "n:A", "v_node_id": "n:B",
            "length_m": "500", "running_minutes_model": "1", "osm_way_id": "3",
            "uncertainty_flags": "", "highway": "secondary",
        },
        {
            "edge_id": "e4", "u_node_id": "n:B", "v_node_id": "n:A",
            "length_m": "600", "running_minutes_model": "1.2", "osm_way_id": "4",
            "uncertainty_flags": "", "highway": "secondary",
        },
        {
            "edge_id": "e5", "u_node_id": "n:B", "v_node_id": "n:H",
            "length_m": "900", "running_minutes_model": "2", "osm_way_id": "5",
            "uncertainty_flags": "", "highway": "secondary",
        },
        {
            "edge_id": "e6", "u_node_id": "n:H", "v_node_id": "n:B",
            "length_m": "1100", "running_minutes_model": "2.4", "osm_way_id": "6",
            "uncertainty_flags": "", "highway": "secondary",
        },
    ])


def test_path_matrix_is_directed_and_propagates_uncertainty() -> None:
    anchors = pd.DataFrame([
        {"anchor_id": HUB_ID, "graph_node_id": "n:H"},
        {"anchor_id": "A", "graph_node_id": "n:A"},
        {"anchor_id": "B", "graph_node_id": "n:B"},
    ])
    rules = pd.DataFrame(columns=[
        "via_node_in_graph", "via_node_id", "from_osm_way_id", "restriction",
        "to_osm_way_id", "relation_id",
    ])
    matrix, info = build_path_matrix(routing_anchors=anchors, edges=_edges_fixture(), rules=rules)
    lookup = {(r.origin, r.destination): r for r in matrix.itertuples(index=False)}
    assert float(lookup[(HUB_ID, "A")].distance_km) == pytest.approx(1.0)
    assert float(lookup[("A", HUB_ID)].distance_km) == pytest.approx(1.3)
    assert lookup[(HUB_ID, "A")].uncertainty == "QUANTIFIED"
    assert lookup[("A", HUB_ID)].uncertainty == "UNKNOWN"
    assert int(lookup[("A", HUB_ID)].service_road_edge_count) == 1
    assert info["path_matrix_completeness"] == 1.0
    assert info["directionally_asymmetric_unordered_pairs"] >= 1


def test_non_route_ready_source_is_not_promoted() -> None:
    source = pd.DataFrame([
        {
            "source_anchor_id": HUB_ID,
            "source_kind": "HUB_RAIL",
            "graph_node_id": "n:H",
            "snap_distance_m": 0.0,
            "evidence_status": "FACT",
            "municipality": "Olgiate Molgora",
            "route_ready": True,
        },
        {
            "source_anchor_id": "P2S_REVIEW",
            "source_kind": "PROPOSED_STOP",
            "graph_node_id": "n:A",
            "snap_distance_m": 80.0,
            "evidence_status": "PROPOSED_STOP/FIELD_CHECK_PENDING",
            "municipality": "Calco",
            "route_ready": False,
        },
    ])
    routing, membership = collapse_routing_anchors(source)
    assert list(routing["anchor_id"]) == [HUB_ID]
    review = membership.loc[membership["source_anchor_id"] == "P2S_REVIEW"].iloc[0]
    assert review["routing_anchor_id"] == ""
    assert review["collapse_reason"] == "NOT_ROUTE_READY"


def test_source_builder_rejects_promoted_proposed_stop_status() -> None:
    nodes = pd.DataFrame([
        {"node_id": "n:0.00:0.00", "x_m_epsg32632": 0.0, "y_m_epsg32632": 0.0},
    ])
    frozen = pd.DataFrame([
        {
            "anchor_id": HUB_ID, "graph_node_id": "n:0.00:0.00", "snap_distance_m": 0.0,
            "included_in_reduced_graph": "true", "lon": 9.4, "lat": 45.7,
        }
    ])
    existing = pd.DataFrame(columns=[
        "stop_id", "stop_name", "stop_lat", "stop_lon", "physical_cluster_id",
        "epistemic_status", "COMUNE",
    ])
    proposed = pd.DataFrame([
        {
            "candidate_id": "BAD", "lat": 45.7, "lon": 9.4,
            "epistemic_status": "FACT", "physical_status": "FIELD_CHECK_PENDING",
            "candidate_status": "HYPOTHESIS_NOT_RECOMMENDATION", "COMUNE": "Calco",
            "highway": "residential", "road_uncertainty_flags": "missing_width",
        }
    ])
    with pytest.raises(ValueError, match="lost field-check epistemic status"):
        build_source_anchor_records(
            nodes=nodes,
            frozen_anchors=frozen,
            existing_stops=existing,
            proposed_stops=proposed,
        )
