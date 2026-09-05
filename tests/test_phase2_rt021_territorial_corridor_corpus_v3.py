from __future__ import annotations

import pandas as pd
import pytest

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
