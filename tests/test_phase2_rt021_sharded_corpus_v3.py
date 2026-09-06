import pandas as pd
import pytest

from src.phase2_complete_directed_pairs_v3 import (
    build_complete_directed_pair_manifest,
    directed_pair_id,
)
from scripts.phase2_rt021_sharded_corpus_v3 import (
    SHARD_COUNT,
    PAIRS_PER_SHARD,
    canonicalize_downstream_handoff,
    select_shard_manifest,
)


def _internal_manifest() -> pd.DataFrame:
    terminals = pd.DataFrame(
        {"routing_terminal_id": [f"STOP_PLACE::S{i:02d}" for i in range(SHARD_COUNT)]}
    )
    result = build_complete_directed_pair_manifest(terminals, max_directed_pairs=5000)
    assert result["complete"] is True
    return result["manifest"]


def test_source_shards_partition_complete_35x34_manifest():
    manifest = _internal_manifest()
    assert len(manifest) == SHARD_COUNT * PAIRS_PER_SHARD == 1190
    observed_pairs = set()
    observed_sources = set()
    for index in range(SHARD_COUNT):
        source, shard = select_shard_manifest(manifest, index)
        assert len(shard) == PAIRS_PER_SHARD
        assert shard["source_routing_terminal_id"].nunique() == 1
        assert shard["source_routing_terminal_id"].iloc[0] == source
        assert source not in observed_sources
        observed_sources.add(source)
        observed_pairs.update(shard["pair_id"].astype(str))
    assert len(observed_sources) == SHARD_COUNT
    assert observed_pairs == set(manifest["pair_id"].astype(str))


def test_invalid_shard_index_fails_closed():
    manifest = _internal_manifest()
    with pytest.raises(ValueError, match="shard_index"):
        select_shard_manifest(manifest, -1)
    with pytest.raises(ValueError, match="shard_index"):
        select_shard_manifest(manifest, SHARD_COUNT)


def test_canonicalization_restores_raw_rt010_identity_and_explicit_flags():
    pair_status = pd.DataFrame(
        [
            {
                "pair_id": "INTERNAL_PAIR",
                "source_routing_terminal_id": "STOP_PLACE::A",
                "target_routing_terminal_id": "STOP_PLACE::B",
                "source_stop_place_id": "A",
                "target_stop_place_id": "B",
                "source_graph_node_id": "N1",
                "target_graph_node_id": "N2",
                "status": "PASS_ROUTED_LOOPLESS_CORRIDOR_POOL",
                "corridor_count": 1,
                "certified_shortest_present": True,
                "certified_shortest_physical_loopless": True,
                "certified_state_path_representable": True,
                "certified_edge_sequence_matches_rt017": True,
                "certified_runtime_delta_vs_rt017_min": "0.000000000000",
                "certified_distance_delta_vs_rt017_m": "0.000000000",
                "raw_state_paths_examined": 3,
                "state_generator_exhausted": False,
                "tie_band_complete": True,
                "graph_epoch_id": "EPOCH",
            }
        ]
    )
    corridors = pd.DataFrame(
        [
            {
                "corridor_id": "INTERNAL_CORRIDOR",
                "pair_id": "INTERNAL_PAIR",
                "source_routing_terminal_id": "STOP_PLACE::A",
                "target_routing_terminal_id": "STOP_PLACE::B",
                "source_stop_place_id": "A",
                "target_stop_place_id": "B",
                "source_graph_node_id": "N1",
                "target_graph_node_id": "N2",
                "corridor_rank_by_running_time": 1,
                "running_minutes_model": "1.000000000",
                "distance_m": "100.000000",
                "edge_count": 2,
                "physical_node_count": 3,
                "path_edge_ids": "E1;E2",
                "path_node_ids": "N1;NX;N2",
                "path_geometry_sha256": "geom",
                "provenance": "TEST_FIXTURE",
                "is_exact_rt017_certified_shortest": "true",
                "certified_shortest_physical_loopless": "true",
                "physical_loopless": "true",
                "tie_band_complete": "true",
                "graph_epoch_id": "EPOCH",
                "decision_role": "TECHNICAL_CORRIDOR_POOL_NOT_NETWORK_OR_TERMINAL_SELECTION",
            }
        ]
    )

    pair_out, corridor_out = canonicalize_downstream_handoff(pair_status, corridors)

    expected_pair_id = directed_pair_id("A", "B")
    assert pair_out.loc[0, "source_routing_terminal_id"] == "A"
    assert pair_out.loc[0, "target_routing_terminal_id"] == "B"
    assert pair_out.loc[0, "pair_id"] == expected_pair_id
    assert bool(pair_out.loc[0, "gate_d_route_found"]) is True

    assert corridor_out.loc[0, "source_routing_terminal_id"] == "A"
    assert corridor_out.loc[0, "target_routing_terminal_id"] == "B"
    assert corridor_out.loc[0, "pair_id"] == expected_pair_id
    assert bool(corridor_out.loc[0, "admissible_for_corridor_pool"]) is True


def test_canonicalization_does_not_change_path_geometry_or_cost_evidence():
    pair_status = pd.DataFrame(
        [
            {
                "pair_id": "OLD",
                "source_routing_terminal_id": "STOP_PLACE::A",
                "target_routing_terminal_id": "STOP_PLACE::B",
                "corridor_count": 1,
            }
        ]
    )
    corridors = pd.DataFrame(
        [
            {
                "corridor_id": "OLD_CORRIDOR",
                "pair_id": "OLD",
                "source_routing_terminal_id": "STOP_PLACE::A",
                "target_routing_terminal_id": "STOP_PLACE::B",
                "path_edge_ids": "E1;E2;E3",
                "path_node_ids": "N1;N2;N3;N4",
                "path_geometry_sha256": "abc123",
                "running_minutes_model": "2.500000000",
                "distance_m": "321.000000",
                "graph_epoch_id": "EPOCH",
            }
        ]
    )
    original = corridors.loc[0, [
        "path_edge_ids",
        "path_node_ids",
        "path_geometry_sha256",
        "running_minutes_model",
        "distance_m",
        "graph_epoch_id",
    ]].to_dict()

    _, out = canonicalize_downstream_handoff(pair_status, corridors)
    observed = out.loc[0, list(original)].to_dict()
    assert observed == original


def test_canonicalization_rejects_noncanonical_internal_terminal_identity():
    pair_status = pd.DataFrame(
        [{
            "pair_id": "OLD",
            "source_routing_terminal_id": "A",
            "target_routing_terminal_id": "STOP_PLACE::B",
        }]
    )
    corridors = pd.DataFrame(
        [{
            "corridor_id": "C",
            "pair_id": "OLD",
            "source_routing_terminal_id": "STOP_PLACE::A",
            "target_routing_terminal_id": "STOP_PLACE::B",
            "path_edge_ids": "E1",
        }]
    )
    with pytest.raises(ValueError, match="internal RT-021 terminal identity"):
        canonicalize_downstream_handoff(pair_status, corridors)
