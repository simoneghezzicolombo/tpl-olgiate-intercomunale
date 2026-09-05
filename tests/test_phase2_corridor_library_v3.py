from __future__ import annotations

import pandas as pd

from src.phase2_corridor_library_v3 import (
    ExplorationSetting,
    generate_corridor_library,
    validate_terminal_and_pair_tables,
)
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index


def edge(edge_id, u, v, minutes, way=None):
    return {
        "edge_id": str(edge_id),
        "u_node_id": str(u),
        "v_node_id": str(v),
        "osm_way_id": str(way or f"w_{u}_{v}"),
        "running_minutes_model": float(minutes),
        "length_m": float(minutes * 100.0),
    }


def empty_rules():
    return pd.DataFrame(
        columns=[
            "relation_id",
            "restriction",
            "from_osm_way_id",
            "via_node_id",
            "to_osm_way_id",
            "via_node_in_graph",
        ]
    )


def terminals():
    return pd.DataFrame(
        [
            {
                "routing_terminal_id": "T_A",
                "graph_node_id": "A",
                "terminal_source_kind": "TEST_FIXTURE",
                "terminal_evidence_status": "TEST_ONLY",
            },
            {
                "routing_terminal_id": "T_D",
                "graph_node_id": "D",
                "terminal_source_kind": "TEST_FIXTURE",
                "terminal_evidence_status": "TEST_ONLY",
            },
        ]
    )


def pairs():
    return pd.DataFrame(
        [
            {
                "pair_id": "PAIR_AD",
                "source_routing_terminal_id": "T_A",
                "target_routing_terminal_id": "T_D",
            }
        ]
    )


def settings():
    return [
        ExplorationSetting("S1", 0.2, 1.5, 0.9, 3, 8),
        ExplorationSetting("S2", 0.5, 1.5, 0.9, 3, 8),
    ]


def test_library_deduplicates_same_paths_across_settings_without_scoring_frequency():
    edge_frame = pd.DataFrame(
        [
            edge("ab", "A", "B", 1.0),
            edge("bd", "B", "D", 1.0),
            edge("ac", "A", "C", 1.2),
            edge("cd", "C", "D", 1.2),
        ]
    )
    result = generate_corridor_library(
        build_adjacency(edge_frame),
        build_turn_rule_index(empty_rules()),
        terminals(),
        pairs(),
        settings(),
    )
    corridors = result["corridors"]
    assert len(corridors) == 2
    assert set(corridors["path_edge_ids"]) == {"ab;bd", "ac;cd"}
    assert corridors["physical_node_loop"].eq(False).all()
    assert corridors["admissible_for_corridor_pool"].eq(True).all()
    assert corridors["appearance_semantics"].eq(
        "DESCRIPTIVE_SEARCH_STABILITY_ONLY_NOT_SCORE_NOT_PROBABILITY"
    ).all()
    assert corridors["union_semantics"].eq(
        "DEDUPLICATED_UNION_ACROSS_TECHNICAL_SETTINGS_NOT_RANKED"
    ).all()
    assert result["metadata"]["automatic_pair_selection_performed"] is False
    assert result["metadata"]["passenger_stop_pattern_authorized"] is False


def test_cyclic_gate_d_baseline_is_reported_but_not_inserted_as_corridor():
    edges = pd.DataFrame(
        [
            edge("sa", "S", "A", 0.4, "wSA"),
            edge("ab", "A", "B", 0.4, "wAB"),
            edge("ba", "B", "A", 0.4, "wBA"),
            edge("at", "A", "T", 0.4, "wAT"),
            edge("sx", "S", "X", 2.0, "wSX"),
            edge("xt", "X", "T", 2.0, "wXT"),
        ]
    )
    rules = pd.DataFrame(
        [
            {
                "relation_id": "r1",
                "restriction": "no_straight_on",
                "from_osm_way_id": "wSA",
                "via_node_id": "A",
                "to_osm_way_id": "wAT",
                "via_node_in_graph": "true",
            }
        ]
    )
    terminal_frame = pd.DataFrame(
        [
            {
                "routing_terminal_id": "S",
                "graph_node_id": "S",
                "terminal_source_kind": "TEST_FIXTURE",
                "terminal_evidence_status": "TEST_ONLY",
            },
            {
                "routing_terminal_id": "T",
                "graph_node_id": "T",
                "terminal_source_kind": "TEST_FIXTURE",
                "terminal_evidence_status": "TEST_ONLY",
            },
        ]
    )
    pair_frame = pd.DataFrame(
        [
            {
                "pair_id": "ST",
                "source_routing_terminal_id": "S",
                "target_routing_terminal_id": "T",
            }
        ]
    )
    result = generate_corridor_library(
        build_adjacency(edges),
        build_turn_rule_index(rules),
        terminal_frame,
        pair_frame,
        [ExplorationSetting("S1", 0.5, 3.0, 1.0, 2, 8)],
    )
    assert result["pairs"].iloc[0]["gate_d_baseline_physical_node_loop"] == True
    assert "sa;ab;ba;at" not in set(result["corridors"]["path_edge_ids"])
    assert "sx;xt" in set(result["corridors"]["path_edge_ids"])


def test_library_is_deterministic():
    edges = pd.DataFrame(
        [
            edge("ab", "A", "B", 1.0),
            edge("bd", "B", "D", 1.0),
            edge("ac", "A", "C", 1.2),
            edge("cd", "C", "D", 1.2),
        ]
    )
    adjacency = build_adjacency(edges)
    rules = build_turn_rule_index(empty_rules())
    first = generate_corridor_library(adjacency, rules, terminals(), pairs(), settings())
    second = generate_corridor_library(adjacency, rules, terminals(), pairs(), settings())
    pd.testing.assert_frame_equal(first["corridors"], second["corridors"])
    pd.testing.assert_frame_equal(first["appearances"], second["appearances"])
    pd.testing.assert_frame_equal(first["pairs"], second["pairs"])
    assert first["metadata"] == second["metadata"]


def test_terminal_and_pair_contract_fails_closed_on_unknown_or_self_pair():
    bad_unknown = pd.DataFrame(
        [
            {
                "pair_id": "BAD",
                "source_routing_terminal_id": "T_A",
                "target_routing_terminal_id": "UNKNOWN",
            }
        ]
    )
    try:
        validate_terminal_and_pair_tables(terminals(), bad_unknown)
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown terminal should fail closed")

    bad_self = pd.DataFrame(
        [
            {
                "pair_id": "BAD2",
                "source_routing_terminal_id": "T_A",
                "target_routing_terminal_id": "T_A",
            }
        ]
    )
    try:
        validate_terminal_and_pair_tables(terminals(), bad_self)
    except ValueError:
        pass
    else:
        raise AssertionError("Self-pair should fail closed")
