from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pandas as pd

from src.phase2_adaptive_routing_envelope_v3 import (
    BOUNDARY_GUARD_M,
    choose_smallest_converged_level,
    compare_pair_results,
    derive_levels,
    segment_in_bounds,
)
from src.phase2_alternative_corridor_generator_v3 import generate_bounded_alternative_corridors
from src.phase2_complete_directed_pairs_v3 import build_complete_directed_pair_manifest
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index, restriction_aware_one_to_many

ROOT = Path(__file__).resolve().parents[1]
STOPS = ROOT / "outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.csv"
EXPECTED_STOP_BLOB_SHA1 = "8d3a4368a6f62bbdf8fe18ee99482aff18e38fe5"


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.value.casefold().strip()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def edge(edge_id, u, v, minutes, length, way):
    return {
        "edge_id": edge_id,
        "u_node_id": u,
        "v_node_id": v,
        "running_minutes_model": minutes,
        "length_m": length,
        "osm_way_id": str(way),
    }


def route(edges: pd.DataFrame, source: str, target: str, rules: pd.DataFrame | None = None):
    adjacency = build_adjacency(edges)
    if rules is None:
        rules = pd.DataFrame(columns=["relation_id", "restriction", "from_osm_way_id", "via_node_id", "to_osm_way_id", "via_node_in_graph"])
    index = build_turn_rule_index(rules)
    return restriction_aware_one_to_many(adjacency, index, source, {target}).get(target)


def test_frozen_36_stop_dependency_is_bit_for_bit_unchanged():
    assert STOPS.exists()
    assert git_blob_sha1(STOPS) == EXPECTED_STOP_BLOB_SHA1
    df = pd.read_csv(STOPS)
    assert len(df) == 36
    assert df["stop_place_id"].nunique() == 36


def test_expansion_schedule_is_deterministic_and_has_no_municipality_semantics():
    points = [(0.0, 0.0), (1000.0, 2000.0)]
    a = derive_levels(points, max_levels=5)
    b = derive_levels(list(reversed(points)), max_levels=5)
    assert a == b
    assert [level.margin_m for level in a] == [500.0, 1000.0, 2000.0, 4000.0, 8000.0]
    literals = string_literals(ROOT / "src/phase2_adaptive_routing_envelope_v3.py")
    literals += string_literals(ROOT / "scripts/phase2_rt017_adaptive_border_neutral_routing_envelope_v3.py")
    forbidden_names = {
        "olgiate molgora",
        "calco",
        "brivio",
        "santa maria hoè",
        "la valletta brianza",
        "merate",
        "airuno",
        "imbersago",
        "olginate",
    }
    for forbidden_name in forbidden_names:
        assert forbidden_name not in literals


def test_better_route_that_temporarily_leaves_core_is_found_after_expansion():
    xy = {"A": (0.0, 0.0), "C": (5.0, 0.0), "B": (10.0, 0.0), "X": (5.0, 2.0)}
    rows = [
        edge("a-c", "A", "C", 5.0, 500.0, 1),
        edge("c-b", "C", "B", 5.0, 500.0, 2),
        edge("a-x", "A", "X", 2.0, 250.0, 3),
        edge("x-b", "X", "B", 2.0, 250.0, 4),
    ]
    core_bounds = (-1.0, -1.0, 11.0, 1.0)
    expanded_bounds = (-1.0, -3.0, 11.0, 3.0)
    core = pd.DataFrame([r for r in rows if segment_in_bounds(xy[r["u_node_id"]], xy[r["v_node_id"]], core_bounds)])
    expanded = pd.DataFrame([r for r in rows if segment_in_bounds(xy[r["u_node_id"]], xy[r["v_node_id"]], expanded_bounds)])
    core_result = route(core, "A", "B")
    expanded_result = route(expanded, "A", "B")
    assert core_result is not None and expanded_result is not None
    assert core_result["edge_ids"] == ["a-c", "c-b"]
    assert expanded_result["edge_ids"] == ["a-x", "x-b"]
    assert expanded_result["running_minutes_model"] < core_result["running_minutes_model"]


def test_artificial_core_clip_can_lose_an_external_route_completely():
    xy = {"A": (0.0, 0.0), "B": (10.0, 0.0), "X": (5.0, 2.0)}
    rows = [edge("a-x", "A", "X", 2.0, 250.0, 3), edge("x-b", "X", "B", 2.0, 250.0, 4)]
    core_bounds = (-1.0, -1.0, 11.0, 1.0)
    expanded_bounds = (-1.0, -3.0, 11.0, 3.0)
    core = pd.DataFrame([r for r in rows if segment_in_bounds(xy[r["u_node_id"]], xy[r["v_node_id"]], core_bounds)], columns=pd.DataFrame(rows).columns)
    expanded = pd.DataFrame([r for r in rows if segment_in_bounds(xy[r["u_node_id"]], xy[r["v_node_id"]], expanded_bounds)])
    assert core.empty
    assert route(expanded, "A", "B") is not None


def test_far_external_road_does_not_change_route():
    base = pd.DataFrame([edge("a-b", "A", "B", 3.0, 300.0, 1)])
    expanded = pd.concat([base, pd.DataFrame([edge("far", "Y", "Z", 0.1, 10.0, 999)])], ignore_index=True)
    assert route(base, "A", "B")["edge_ids"] == ["a-b"]
    assert route(expanded, "A", "B")["edge_ids"] == ["a-b"]


def test_directional_turn_restriction_is_preserved():
    edges = pd.DataFrame([
        edge("a-v", "A", "V", 1.0, 100.0, 10),
        edge("v-b", "V", "B", 1.0, 100.0, 20),
        edge("b-v", "B", "V", 1.0, 100.0, 20),
        edge("v-a", "V", "A", 1.0, 100.0, 10),
    ])
    rules = pd.DataFrame([{
        "relation_id": "r1",
        "restriction": "no_right_turn",
        "from_osm_way_id": "10",
        "via_node_id": "V",
        "to_osm_way_id": "20",
        "via_node_in_graph": "true",
    }])
    assert route(edges, "A", "B", rules) is None
    assert route(edges, "B", "A", rules) is not None


def test_rt006_alternative_generator_remains_compatible_with_rt017_graph_contract():
    edges = pd.DataFrame([
        edge("a-b", "A", "B", 2.0, 200.0, 1),
        edge("a-c", "A", "C", 1.5, 150.0, 2),
        edge("c-b", "C", "B", 1.5, 150.0, 3),
    ])
    adjacency = build_adjacency(edges)
    rules = build_turn_rule_index(pd.DataFrame(columns=["relation_id", "restriction", "from_osm_way_id", "via_node_id", "to_osm_way_id", "via_node_in_graph"]))
    result = generate_bounded_alternative_corridors(adjacency, rules, "A", "B", max_alternatives=2, max_generation_rounds=4)
    assert result["baseline"] is not None
    assert result["baseline"].edge_ids == ("a-b",)
    assert result["contract"] == "ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION"


def test_complete_directed_pair_manifest_remains_complete():
    terminals = pd.DataFrame({"routing_terminal_id": ["A", "B", "C", "D"]})
    result = build_complete_directed_pair_manifest(terminals)
    assert result["complete"] is True
    assert result["directed_pair_count"] == 12
    assert set(zip(result["manifest"].source_routing_terminal_id, result["manifest"].target_routing_terminal_id)) == {(a, b) for a in "ABCD" for b in "ABCD" if a != b}


def pair_frame(edge_id="e1", digest="g1", runtime=1.0, distance=100.0):
    return pd.DataFrame([{
        "pair_id": "p",
        "route_found": True,
        "path_edge_ids": edge_id,
        "path_geometry_sha256": digest,
        "running_minutes_model": runtime,
        "distance_m": distance,
    }])


def test_pair_comparison_detects_material_improvement_and_exact_stability():
    stable = compare_pair_results(pair_frame(), pair_frame())
    assert stable["stable"] is True
    improved = compare_pair_results(pair_frame(runtime=2.0, distance=200.0), pair_frame(edge_id="e2", digest="g2", runtime=1.0, distance=100.0))
    assert improved["stable"] is False
    assert improved["material_improvement_count"] == 1


def test_two_successive_expansions_are_required_before_freeze():
    levels = [
        {"level": 0, "all_pairs_routable": True, "boundary_sensitive_pair_count": 0},
        {"level": 1, "all_pairs_routable": True, "boundary_sensitive_pair_count": 0},
        {"level": 2, "all_pairs_routable": True, "boundary_sensitive_pair_count": 0},
    ]
    one = [{"from_level": 0, "to_level": 1, "stable": True}]
    assert choose_smallest_converged_level(levels[:2], one).converged is False
    two = one + [{"from_level": 1, "to_level": 2, "stable": True}]
    decision = choose_smallest_converged_level(levels, two)
    assert decision.converged is True
    assert decision.frozen_level == 0


def test_boundary_sensitive_level_forces_further_expansion():
    levels = [
        {"level": 0, "all_pairs_routable": True, "boundary_sensitive_pair_count": 1},
        {"level": 1, "all_pairs_routable": True, "boundary_sensitive_pair_count": 0},
        {"level": 2, "all_pairs_routable": True, "boundary_sensitive_pair_count": 0},
        {"level": 3, "all_pairs_routable": True, "boundary_sensitive_pair_count": 0},
    ]
    transitions = [
        {"from_level": 0, "to_level": 1, "stable": True},
        {"from_level": 1, "to_level": 2, "stable": True},
        {"from_level": 2, "to_level": 3, "stable": True},
    ]
    decision = choose_smallest_converged_level(levels, transitions)
    assert decision.converged is True
    assert decision.frozen_level == 1
    assert BOUNDARY_GUARD_M == 250.0
