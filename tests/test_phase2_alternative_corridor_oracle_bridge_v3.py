from __future__ import annotations

import pandas as pd

from src.phase2_alternative_corridor_generator_v3 import generate_bounded_alternative_corridors
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index
from src.phase2_restriction_aware_ksp import (
    build_restriction_aware_state_context,
    k_shortest_loopless_paths,
)


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


def rule(relation_id, restriction, from_way, via, to_way):
    return {
        "relation_id": str(relation_id),
        "restriction": str(restriction),
        "from_osm_way_id": str(from_way),
        "via_node_id": str(via),
        "to_osm_way_id": str(to_way),
        "via_node_in_graph": "true",
    }


def efficient(edges, rules, source="A", target="D"):
    return generate_bounded_alternative_corridors(
        build_adjacency(edges),
        build_turn_rule_index(rules),
        source,
        target,
        max_alternatives=2,
        max_generation_rounds=8,
        penalty_increment=0.5,
        max_runtime_factor=2.0,
        max_shared_runtime_fraction_allowed=1.0,
    )


def test_bounded_generator_matches_exact_oracle_on_two_disjoint_paths():
    edges = pd.DataFrame(
        [
            edge("ab", "A", "B", 1.0),
            edge("bd", "B", "D", 1.0),
            edge("ac", "A", "C", 1.2),
            edge("cd", "C", "D", 1.2),
        ]
    )
    rules = empty_rules()
    oracle = k_shortest_loopless_paths(
        build_restriction_aware_state_context(edges, rules), "A", "D", k=2
    )
    bounded = efficient(edges, rules)

    oracle_edges = [tuple(path["edge_ids"]) for path in oracle["paths"]]
    bounded_edges = [path.edge_ids for path in bounded["corridors"]]
    assert bounded_edges == oracle_edges == [("ab", "bd"), ("ac", "cd")]
    assert [path.running_minutes_model for path in bounded["corridors"]] == [2.0, 2.4]


def test_bounded_generator_and_exact_oracle_agree_after_turn_restriction():
    edges = pd.DataFrame(
        [
            edge("ab", "A", "B", 1.0, "wAB"),
            edge("bd", "B", "D", 1.0, "wBD"),
            edge("ac", "A", "C", 2.0, "wAC"),
            edge("cd", "C", "D", 2.0, "wCD"),
            edge("bc", "B", "C", 1.2, "wBC"),
        ]
    )
    rules = pd.DataFrame([rule("r1", "no_left_turn", "wAB", "B", "wBD")])
    oracle = k_shortest_loopless_paths(
        build_restriction_aware_state_context(edges, rules), "A", "D", k=2
    )
    bounded = efficient(edges, rules)

    oracle_edges = [tuple(path["edge_ids"]) for path in oracle["paths"]]
    bounded_edges = [path.edge_ids for path in bounded["corridors"]]
    assert oracle_edges == [("ac", "cd"), ("ab", "bc", "cd")]
    assert bounded_edges == oracle_edges
    assert all(("ab", "bd") != path.edge_ids for path in bounded["generation_audit"])
