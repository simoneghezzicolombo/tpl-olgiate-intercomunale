from __future__ import annotations

import pandas as pd
import pytest

from src.phase2_alternative_corridor_generator_v3 import generate_bounded_alternative_corridors
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index
from src.phase2_rt021_bounded_corpus_v3 import generate_bounded_from_frozen_baseline
from src.phase2_rt021_territorial_corridor_corpus_v3 import (
    EXPECTED_DIRECTED_PAIRS,
    adapt_rt017_nodes_for_rt018,
    build_rt021_pair_manifest,
    canonical_csv_bytes,
    conventional_anchor_universe,
    corridor_id,
)


def attachment_fixture() -> pd.DataFrame:
    rows = []
    for i in range(35):
        rows.append(
            {
                "stop_place_id": f"S{i:02d}",
                "stop_name": f"Stop {i:02d}",
                "service_class": "CONVENTIONAL_TPL",
                "route_ready": True,
                "graph_node_id": f"N{i:02d}",
                "attachment_distance_m": float(i) / 2.0,
                "attachment_status": "ROUTE_READY_LE_75M",
            }
        )
    rows.append(
        {
            "stop_place_id": "SPECIAL",
            "stop_name": "Special",
            "service_class": "SPECIAL_SERVICE",
            "route_ready": True,
            "graph_node_id": "NSPECIAL",
            "attachment_distance_m": 1.0,
            "attachment_status": "ROUTE_READY_LE_75M",
        }
    )
    return pd.DataFrame(rows)


def test_35_conventional_anchors_exclude_special_and_make_1190_pairs():
    anchors = conventional_anchor_universe(attachment_fixture())
    assert len(anchors) == 35
    assert "SPECIAL" not in set(anchors["stop_place_id"])
    manifest = build_rt021_pair_manifest(anchors)
    assert len(manifest) == EXPECTED_DIRECTED_PAIRS == 1190
    assert len(set(manifest["pair_id"])) == 1190
    assert set(manifest["source_routing_terminal_id"]) == set(anchors["routing_terminal_id"])
    assert set(manifest["target_routing_terminal_id"]) == set(anchors["routing_terminal_id"])


def test_pair_manifest_is_input_order_invariant():
    fixture = attachment_fixture()
    a = build_rt021_pair_manifest(conventional_anchor_universe(fixture))
    b = build_rt021_pair_manifest(
        conventional_anchor_universe(fixture.sample(frac=1.0, random_state=7))
    )
    assert canonical_csv_bytes(
        a,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
    ) == canonical_csv_bytes(
        b,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
    )


def test_attachment_over_75m_fails_closed_for_conventional_stop():
    fixture = attachment_fixture()
    fixture.loc[fixture["stop_place_id"].eq("S03"), "route_ready"] = False
    fixture.loc[fixture["stop_place_id"].eq("S03"), "attachment_distance_m"] = 80.0
    fixture.loc[fixture["stop_place_id"].eq("S03"), "attachment_status"] = "REVIEW_75_250M"
    with pytest.raises(AssertionError, match="exceed automatic threshold"):
        conventional_anchor_universe(fixture)


def test_distinct_stop_places_may_not_collapse_to_same_graph_node():
    fixture = attachment_fixture()
    fixture.loc[fixture["stop_place_id"].eq("S04"), "graph_node_id"] = "N03"
    with pytest.raises(AssertionError, match="collide on one RT-017 graph node"):
        conventional_anchor_universe(fixture)


def test_rt017_node_adapter_preserves_identity_and_adds_single_epoch():
    nodes = pd.DataFrame(
        [
            {"node_id": "B", "x": 2.0, "y": 4.0},
            {"node_id": "A", "x": 1.0, "y": 3.0},
        ]
    )
    adapted = adapt_rt017_nodes_for_rt018(nodes, "EPOCH")
    assert list(adapted["node_id"]) == ["A", "B"]
    assert list(adapted["x_m_epsg32632"]) == [1.0, 2.0]
    assert list(adapted["y_m_epsg32632"]) == [3.0, 4.0]
    assert set(adapted["epoch_id"]) == {"EPOCH"}


def test_corridor_id_depends_on_directed_pair_and_exact_edge_sequence():
    a = corridor_id("PAIR_A", ["e1", "e2"])
    b = corridor_id("PAIR_A", ["e1", "e2"])
    c = corridor_id("PAIR_A", ["e2", "e1"])
    d = corridor_id("PAIR_B", ["e1", "e2"])
    assert a == b
    assert len({a, c, d}) == 3


def test_frozen_baseline_wrapper_matches_rt006_post_oracle_generation():
    edges = pd.DataFrame(
        [
            {"edge_id": "ab", "u_node_id": "A", "v_node_id": "B", "osm_way_id": "w1", "length_m": 100, "running_minutes_model": 1.0},
            {"edge_id": "bd", "u_node_id": "B", "v_node_id": "D", "osm_way_id": "w2", "length_m": 100, "running_minutes_model": 1.0},
            {"edge_id": "ac", "u_node_id": "A", "v_node_id": "C", "osm_way_id": "w3", "length_m": 110, "running_minutes_model": 1.1},
            {"edge_id": "cd", "u_node_id": "C", "v_node_id": "D", "osm_way_id": "w4", "length_m": 110, "running_minutes_model": 1.1},
            {"edge_id": "be", "u_node_id": "B", "v_node_id": "E", "osm_way_id": "w5", "length_m": 70, "running_minutes_model": 0.7},
            {"edge_id": "ed", "u_node_id": "E", "v_node_id": "D", "osm_way_id": "w6", "length_m": 70, "running_minutes_model": 0.7},
        ]
    )
    rules = pd.DataFrame(
        columns=[
            "relation_id",
            "restriction",
            "from_osm_way_id",
            "via_node_id",
            "to_osm_way_id",
            "via_node_in_graph",
        ]
    )
    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    original = generate_bounded_alternative_corridors(
        adjacency,
        rule_index,
        "A",
        "D",
        max_alternatives=3,
        max_generation_rounds=10,
        penalty_increment=0.20,
        max_runtime_factor=1.50,
        max_shared_runtime_fraction_allowed=0.90,
    )
    wrapped = generate_bounded_from_frozen_baseline(
        adjacency,
        rule_index,
        __import__("src.phase2_alternative_corridor_generator_v3", fromlist=["edge_lookup"]).edge_lookup(adjacency),
        "A",
        "D",
        list(original["baseline"].edge_ids),
    )
    assert [tuple(path.edge_ids) for path in original["corridors"]] == [
        tuple(path["edge_ids"]) for path in wrapped["corridors"]
    ]
    assert [path.running_minutes_model for path in original["corridors"]] == [
        path["running_minutes_model"] for path in wrapped["corridors"]
    ]
    assert [path.distance_m for path in original["corridors"]] == [
        path["distance_m"] for path in wrapped["corridors"]
    ]
    assert original["contract"] == wrapped["contract"]
    assert original["completeness_claim"] == wrapped["completeness_claim"]
