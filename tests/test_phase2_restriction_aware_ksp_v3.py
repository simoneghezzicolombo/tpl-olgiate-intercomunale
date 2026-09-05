from __future__ import annotations

import pandas as pd
import pytest

from src.phase2_restriction_aware_ksp import (
    build_restriction_aware_state_context,
    k_shortest_loopless_paths,
)


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


def directed_cycle_edges(n=7):
    rows = []
    for u in range(n):
        v = (u + 1) % n
        rows.append(edge(f"e_{u}_{v}", u, v, 1.0))
        rows.append(edge(f"e_{v}_{u}", v, u, 1.0))
    return pd.DataFrame(rows)


def test_public_networkx_cycle_doc_fixture_path_order():
    """Replicate the public NetworkX shortest_simple_paths cycle_graph example.

    NetworkX documentation shows the two simple 0->3 paths on cycle_graph(7)
    as 0-1-2-3 and 0-6-5-4-3.  This is a public algorithm fixture, not project
    evidence or synthetic transport data.
    """
    context = build_restriction_aware_state_context(directed_cycle_edges(), empty_rules())
    result = k_shortest_loopless_paths(context, "0", "3", k=2)
    assert [p["physical_nodes"] for p in result["paths"]] == [
        ["0", "1", "2", "3"],
        ["0", "6", "5", "4", "3"],
    ]
    assert [p["running_minutes_model"] for p in result["paths"]] == [3.0, 4.0]
    assert result["certified_first_path_exact_edge_ids"] is True


def test_turn_restriction_changes_shortest_path_and_is_preserved():
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
    context = build_restriction_aware_state_context(edges, rules)
    result = k_shortest_loopless_paths(context, "A", "D", k=2)
    assert result["paths"][0]["edge_ids"] == ["ac", "cd"]
    assert result["paths"][0]["running_minutes_model"] == 4.0
    assert result["paths"][1]["edge_ids"] == ["ab", "bc", "cd"]
    assert context.stats["turn_transitions_rejected"] >= 1


def test_parallel_edge_identity_is_not_collapsed():
    edges = pd.DataFrame(
        [
            edge("ab_fast", "A", "B", 1.0, "wAB"),
            edge("ab_slow", "A", "B", 1.1, "wAB"),
            edge("bc", "B", "C", 1.0, "wBC"),
        ]
    )
    context = build_restriction_aware_state_context(edges, empty_rules())
    result = k_shortest_loopless_paths(context, "A", "C", k=2)
    assert context.stats["state_vertices"] == 3
    assert result["paths"][0]["edge_ids"] == ["ab_fast", "bc"]
    assert result["paths"][1]["edge_ids"] == ["ab_slow", "bc"]


def test_state_simple_but_physically_cyclic_path_is_filtered():
    edges = pd.DataFrame(
        [
            edge("st", "S", "T", 1.0, "wST"),
            edge("sa", "S", "A", 0.4, "wSA"),
            edge("ab", "A", "B", 0.4, "wAB"),
            edge("ba", "B", "A", 0.4, "wBA"),
            edge("at", "A", "T", 0.4, "wAT"),
            edge("sx", "S", "X", 1.5, "wSX"),
            edge("xt", "X", "T", 1.5, "wXT"),
        ]
    )
    # A->T is illegal when A was reached directly from S, but legal after the
    # B->A loop.  The 1.6-minute state-simple path S-A-B-A-T must therefore be
    # rejected because it repeats physical node A.
    rules = pd.DataFrame([rule("r2", "no_straight_on", "wSA", "A", "wAT")])
    context = build_restriction_aware_state_context(edges, rules)
    result = k_shortest_loopless_paths(context, "S", "T", k=2)
    assert [p["physical_nodes"] for p in result["paths"]] == [
        ["S", "T"],
        ["S", "X", "T"],
    ]
    assert result["raw_state_paths_examined"] >= 3


def test_certified_dijkstra_path_must_itself_be_physically_loopless():
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
    rules = pd.DataFrame([rule("r3", "no_straight_on", "wSA", "A", "wAT")])
    context = build_restriction_aware_state_context(edges, rules)
    with pytest.raises(ValueError, match="repeats a physical road node"):
        k_shortest_loopless_paths(context, "S", "T", k=2)


def test_repeated_queries_are_deterministic_and_leave_context_clean():
    context = build_restriction_aware_state_context(directed_cycle_edges(), empty_rules())
    nodes_before = context.graph.number_of_nodes()
    edges_before = context.graph.number_of_edges()
    first = k_shortest_loopless_paths(context, "0", "3", k=2)
    second = k_shortest_loopless_paths(context, "0", "3", k=2)
    assert first == second
    assert context.graph.number_of_nodes() == nodes_before
    assert context.graph.number_of_edges() == edges_before
