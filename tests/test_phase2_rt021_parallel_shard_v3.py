from __future__ import annotations

import pandas as pd

import scripts.phase2_rt021_parallel_shard_v3 as parallel
import src.phase2_rt021_territorial_corridor_corpus_v3 as rt


def _fixture():
    anchors = pd.DataFrame(
        [
            {"routing_terminal_id": "STOP_PLACE::S_A", "stop_place_id": "S_A", "graph_node_id": "A"},
            {"routing_terminal_id": "STOP_PLACE::S_B", "stop_place_id": "S_B", "graph_node_id": "B"},
        ]
    )
    manifest = pd.DataFrame(
        [
            {
                "pair_id": "PAIR_AB",
                "source_routing_terminal_id": "STOP_PLACE::S_A",
                "target_routing_terminal_id": "STOP_PLACE::S_B",
                "reverse_pair_id": "PAIR_BA",
            },
            {
                "pair_id": "PAIR_BA",
                "source_routing_terminal_id": "STOP_PLACE::S_B",
                "target_routing_terminal_id": "STOP_PLACE::S_A",
                "reverse_pair_id": "PAIR_AB",
            },
        ]
    )
    edges = pd.DataFrame(
        [
            {"edge_id": "ab", "u_node_id": "A", "v_node_id": "B", "osm_way_id": "w_ab", "length_m": 100.0, "running_minutes_model": 1.0},
            {"edge_id": "ba", "u_node_id": "B", "v_node_id": "A", "osm_way_id": "w_ba", "length_m": 100.0, "running_minutes_model": 1.0},
            {"edge_id": "ac", "u_node_id": "A", "v_node_id": "C", "osm_way_id": "w_ac", "length_m": 70.0, "running_minutes_model": 0.7},
            {"edge_id": "cb", "u_node_id": "C", "v_node_id": "B", "osm_way_id": "w_cb", "length_m": 70.0, "running_minutes_model": 0.7},
            {"edge_id": "bc", "u_node_id": "B", "v_node_id": "C", "osm_way_id": "w_bc", "length_m": 70.0, "running_minutes_model": 0.7},
            {"edge_id": "ca", "u_node_id": "C", "v_node_id": "A", "osm_way_id": "w_ca", "length_m": 70.0, "running_minutes_model": 0.7},
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
    nodes = pd.DataFrame(
        [
            {"node_id": "A", "x": 0.0, "y": 0.0},
            {"node_id": "B", "x": 100.0, "y": 0.0},
            {"node_id": "C", "x": 50.0, "y": 50.0},
        ]
    )
    reference_pairs = pd.DataFrame(
        [
            {
                "source_routing_terminal_id": "STOP_PROBE::S_A",
                "target_routing_terminal_id": "STOP_PROBE::S_B",
                "source_graph_node_id": "A",
                "target_graph_node_id": "B",
                "route_found": "true",
                "path_edge_ids": "ab",
                "running_minutes_model": "1.0",
                "distance_m": "100.0",
            },
            {
                "source_routing_terminal_id": "STOP_PROBE::S_B",
                "target_routing_terminal_id": "STOP_PROBE::S_A",
                "source_graph_node_id": "B",
                "target_graph_node_id": "A",
                "route_found": "true",
                "path_edge_ids": "ba",
                "running_minutes_model": "1.0",
                "distance_m": "100.0",
            },
        ]
    )
    return manifest, anchors, edges, rules, nodes, reference_pairs


def _canonical(frame: pd.DataFrame, sort_by: list[str]) -> bytes:
    return rt.canonical_csv_bytes(frame, sort_by=sort_by)


def test_parallel_workers_preserve_exact_rt021_pair_and_corridor_semantics():
    manifest, anchors, edges, rules, nodes, reference_pairs = _fixture()

    sequential_corridors, sequential_pairs, _ = rt.route_corpus(
        manifest,
        anchors,
        edges,
        rules,
        nodes,
        reference_pairs,
        epoch_id="EPOCH",
        k=2,
        max_raw_state_paths=100,
    )
    parallel_corridors, parallel_pairs, _ = parallel.route_corpus_parallel(
        manifest,
        anchors,
        edges,
        rules,
        nodes,
        reference_pairs,
        epoch_id="EPOCH",
        k=2,
        max_raw_state_paths=100,
        workers=2,
    )

    assert _canonical(
        sequential_pairs,
        ["source_routing_terminal_id", "target_routing_terminal_id"],
    ) == _canonical(
        parallel_pairs,
        ["source_routing_terminal_id", "target_routing_terminal_id"],
    )
    assert _canonical(
        sequential_corridors,
        ["pair_id", "corridor_rank_by_running_time", "corridor_id"],
    ) == _canonical(
        parallel_corridors,
        ["pair_id", "corridor_rank_by_running_time", "corridor_id"],
    )
