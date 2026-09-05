from __future__ import annotations

import pandas as pd

from src.phase2_alternative_corridor_generator_v3 import (
    edge_lookup,
    generate_bounded_alternative_corridors,
    has_physical_node_loop,
    materialize_path,
    restriction_aware_penalized_shortest_path,
    shared_runtime_fraction,
)
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index


def edge(edge_id, u, v, minutes, way=None, length_m=None):
    return {
        "edge_id": str(edge_id),
        "u_node_id": str(u),
        "v_node_id": str(v),
        "osm_way_id": str(way or f"w_{u}_{v}"),
        "running_minutes_model": float(minutes),
        "length_m": float(length_m if length_m is not None else minutes * 100.0),
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


def context(rows, rules=None):
    edge_frame = pd.DataFrame(rows)
    rule_frame = empty_rules() if rules is None else pd.DataFrame(rules)
    return build_adjacency(edge_frame), build_turn_rule_index(rule_frame)


def test_penalty_search_finds_distinct_route_without_changing_true_runtime():
    adjacency, rules = context(
        [
            edge("ab", "A", "B", 1.0),
            edge("bd", "B", "D", 1.0),
            edge("ac", "A", "C", 1.2),
            edge("cd", "C", "D", 1.2),
        ]
    )
    result = restriction_aware_penalized_shortest_path(
        adjacency,
        rules,
        "A",
        "D",
        {"ab": 1, "bd": 1},
        0.5,
    )
    assert result is not None
    assert result["edge_ids"] == ["ac", "cd"]
    assert result["running_minutes_model"] == 2.4
    assert result["distance_m"] == 240.0
    assert result["penalized_cost"] == 2.4


def test_generator_preserves_gate_d_baseline_and_emits_diverse_alternative():
    adjacency, rules = context(
        [
            edge("ab", "A", "B", 1.0),
            edge("bd", "B", "D", 1.0),
            edge("ac", "A", "C", 1.2),
            edge("cd", "C", "D", 1.2),
        ]
    )
    result = generate_bounded_alternative_corridors(
        adjacency,
        rules,
        "A",
        "D",
        max_alternatives=2,
        max_generation_rounds=4,
        penalty_increment=0.5,
        max_runtime_factor=1.5,
        max_shared_runtime_fraction_allowed=0.9,
    )
    assert result["status"] == "PASS_BOUNDED_ALTERNATIVE_GENERATION"
    assert result["baseline"].edge_ids == ("ab", "bd")
    assert result["baseline"].provenance == "CERTIFIED_GATE_D_SHORTEST"
    assert [path.edge_ids for path in result["corridors"]] == [
        ("ab", "bd"),
        ("ac", "cd"),
    ]
    assert result["corridors"][1].provenance == "BOUNDED_PENALTY_ALTERNATIVE"
    assert result["contract"] == "ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION"
    assert result["completeness_claim"] == "NO_K_SHORTEST_COMPLETENESS_CLAIM"


def test_turn_restrictions_are_enforced_in_penalized_search():
    adjacency, rules = context(
        [
            edge("ab", "A", "B", 1.0, "wAB"),
            edge("bd", "B", "D", 1.0, "wBD"),
            edge("ac", "A", "C", 2.0, "wAC"),
            edge("cd", "C", "D", 2.0, "wCD"),
            edge("bc", "B", "C", 1.2, "wBC"),
        ],
        [rule("r1", "no_left_turn", "wAB", "B", "wBD")],
    )
    result = generate_bounded_alternative_corridors(
        adjacency,
        rules,
        "A",
        "D",
        max_alternatives=2,
        max_generation_rounds=8,
        penalty_increment=0.5,
        max_runtime_factor=1.2,
        max_shared_runtime_fraction_allowed=1.0,
    )
    assert result["baseline"].edge_ids == ("ac", "cd")
    assert any(path.edge_ids == ("ab", "bc", "cd") for path in result["corridors"])
    assert all(path.edge_ids != ("ab", "bd") for path in result["generation_audit"])


def test_cyclic_gate_d_shortest_remains_evidence_but_not_corridor():
    adjacency, rules = context(
        [
            edge("sa", "S", "A", 0.4, "wSA"),
            edge("ab", "A", "B", 0.4, "wAB"),
            edge("ba", "B", "A", 0.4, "wBA"),
            edge("at", "A", "T", 0.4, "wAT"),
            edge("sx", "S", "X", 2.0, "wSX"),
            edge("xt", "X", "T", 2.0, "wXT"),
        ],
        [rule("r2", "no_straight_on", "wSA", "A", "wAT")],
    )
    result = generate_bounded_alternative_corridors(
        adjacency,
        rules,
        "S",
        "T",
        max_alternatives=1,
        max_generation_rounds=8,
        penalty_increment=0.5,
        max_runtime_factor=3.0,
        max_shared_runtime_fraction_allowed=1.0,
    )
    assert result["baseline"].edge_ids == ("sa", "ab", "ba", "at")
    assert result["baseline"].node_ids == ("S", "A", "B", "A", "T")
    assert result["baseline"].physical_node_loop is True
    assert result["baseline"].admissible_for_corridor_pool is False
    assert result["baseline"].rejection_reason == "PHYSICAL_NODE_LOOP"
    assert [path.edge_ids for path in result["corridors"]] == [("sx", "xt")]


def test_overlap_filter_is_a_separate_technical_guard_not_a_score():
    adjacency, rules = context(
        [
            edge("ab", "A", "B", 1.0),
            edge("bc", "B", "C", 1.0),
            edge("cd", "C", "D", 1.0),
            edge("bx", "B", "X", 1.1),
            edge("xd", "X", "D", 1.1),
        ]
    )
    result = generate_bounded_alternative_corridors(
        adjacency,
        rules,
        "A",
        "D",
        max_alternatives=2,
        max_generation_rounds=6,
        penalty_increment=0.5,
        max_runtime_factor=1.5,
        max_shared_runtime_fraction_allowed=0.2,
    )
    assert len(result["corridors"]) == 1
    assert result["corridors"][0].edge_ids == ("ab", "bc", "cd")
    rejected = [
        path for path in result["generation_audit"]
        if "ABOVE_TECHNICAL_OVERLAP_ENVELOPE" in path.rejection_reason
    ]
    assert rejected
    assert rejected[0].max_shared_runtime_fraction > 0.2


def test_materialization_overlap_and_loop_helpers_are_explicit():
    adjacency, _ = context(
        [
            edge("ab", "A", "B", 1.0),
            edge("bc", "B", "C", 2.0),
            edge("bd", "B", "D", 3.0),
        ]
    )
    lookup = edge_lookup(adjacency)
    nodes, runtime, distance = materialize_path("A", ["ab", "bc"], lookup)
    assert nodes == ("A", "B", "C")
    assert runtime == 3.0
    assert distance == 300.0
    assert has_physical_node_loop(("A", "B", "A")) is True
    assert shared_runtime_fraction(["ab", "bc"], ["ab", "bd"], lookup) == 0.25


def test_generation_is_deterministic():
    adjacency, rules = context(
        [
            edge("ab", "A", "B", 1.0),
            edge("bd", "B", "D", 1.0),
            edge("ac", "A", "C", 1.2),
            edge("cd", "C", "D", 1.2),
            edge("ae", "A", "E", 1.3),
            edge("ed", "E", "D", 1.3),
        ]
    )
    kwargs = dict(
        max_alternatives=3,
        max_generation_rounds=8,
        penalty_increment=0.5,
        max_runtime_factor=1.5,
        max_shared_runtime_fraction_allowed=1.0,
    )
    first = generate_bounded_alternative_corridors(adjacency, rules, "A", "D", **kwargs)
    second = generate_bounded_alternative_corridors(adjacency, rules, "A", "D", **kwargs)
    assert first == second


def test_invalid_exploration_parameters_fail_closed():
    adjacency, rules = context([edge("ab", "A", "B", 1.0)])
    for kwargs in [
        {"max_alternatives": 0},
        {"max_generation_rounds": -1},
        {"penalty_increment": 0.0},
        {"max_runtime_factor": 0.9},
        {"max_shared_runtime_fraction_allowed": 1.1},
    ]:
        try:
            generate_bounded_alternative_corridors(adjacency, rules, "A", "B", **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for {kwargs}")
