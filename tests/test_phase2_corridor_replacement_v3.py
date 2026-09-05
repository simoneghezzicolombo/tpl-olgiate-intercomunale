from __future__ import annotations

import pandas as pd

from src.phase2_corridor_replacement_v3 import (
    generate_way_replacement_corridors,
    restriction_aware_route_excluding_ways,
)
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index, restriction_aware_one_to_many


def edge(eid, u, v, minutes, way, length=100.0):
    return {
        "edge_id": eid,
        "u_node_id": u,
        "v_node_id": v,
        "running_minutes_model": minutes,
        "length_m": length,
        "osm_way_id": way,
    }


def empty_rules():
    return pd.DataFrame(
        columns=[
            "via_node_id",
            "from_osm_way_id",
            "to_osm_way_id",
            "via_node_in_graph",
            "restriction",
            "relation_id",
        ]
    )


def rule(rid, kind, incoming, via, outgoing):
    return {
        "relation_id": rid,
        "restriction": kind,
        "from_osm_way_id": incoming,
        "via_node_id": via,
        "to_osm_way_id": outgoing,
        "via_node_in_graph": "true",
    }


def test_empty_exclusion_exactly_matches_gate_d_dijkstra():
    edges = pd.DataFrame(
        [
            edge("sa", "S", "A", 1.0, "wSA"),
            edge("at", "A", "T", 1.0, "wAT"),
            edge("sb", "S", "B", 2.0, "wSB"),
            edge("bt", "B", "T", 2.0, "wBT"),
        ]
    )
    rules = empty_rules()
    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    certified = restriction_aware_one_to_many(adjacency, rule_index, "S", {"T"})["T"]
    observed = restriction_aware_route_excluding_ways(adjacency, rule_index, "S", "T", set())
    assert observed == certified


def test_single_baseline_way_exclusion_discovers_distinct_corridor():
    edges = pd.DataFrame(
        [
            edge("sa", "S", "A", 1.0, "wSA"),
            edge("at", "A", "T", 1.0, "wAT"),
            edge("sb", "S", "B", 1.5, "wSB"),
            edge("bt", "B", "T", 1.5, "wBT"),
        ]
    )
    result = generate_way_replacement_corridors(edges, empty_rules(), "S", "T")
    assert result["certified_baseline"]["edge_ids"] == ["sa", "at"]
    assert result["baseline_distinct_way_count"] == 2
    assert len(result["replacement_corridors"]) == 1
    alt = result["replacement_corridors"][0]
    assert alt["edge_ids"] == ["sb", "bt"]
    assert alt["excluded_baseline_osm_way_ids"] == ["wAT", "wSA"]
    assert alt["runtime_penalty_min"] == 1.0


def test_turn_restrictions_are_preserved_under_replacement():
    edges = pd.DataFrame(
        [
            edge("sa", "S", "A", 1.0, "wSA"),
            edge("at", "A", "T", 1.0, "wAT"),
            edge("sb", "S", "B", 1.2, "wSB"),
            edge("bt_bad", "B", "T", 1.0, "wBTbad"),
            edge("bc", "B", "C", 1.5, "wBC"),
            edge("ct", "C", "T", 1.5, "wCT"),
        ]
    )
    rules = pd.DataFrame([rule("r1", "no_straight_on", "wSB", "B", "wBTbad")])
    result = generate_way_replacement_corridors(edges, rules, "S", "T")
    assert result["replacement_corridors"][0]["edge_ids"] == ["sb", "bc", "ct"]
    assert "bt_bad" not in result["replacement_corridors"][0]["edge_ids"]


def test_unreachable_replacements_are_reported_not_invented():
    edges = pd.DataFrame(
        [
            edge("sa", "S", "A", 1.0, "wSA"),
            edge("at", "A", "T", 1.0, "wAT"),
        ]
    )
    result = generate_way_replacement_corridors(edges, empty_rules(), "S", "T")
    assert result["replacement_corridors"] == []
    assert result["replacement_queries_unreachable"] == 2
