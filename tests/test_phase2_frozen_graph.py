from __future__ import annotations

import ast
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/phase2/frozen_gate_d/source"
OUT = ROOT / "outputs/phase2/frozen_gate_d"

EXPECTED_EPOCH = "gate-d-2026-09-03-834d5caa0bfd"
EXPECTED_SOURCE_SHA = {
    "osm_gate_d_context.json.gz": "d2e4c31c2269a8a0238e058a95851e964e7c71eb7d61cd37f4aec6766534ee54",
    "osm_gate_d_structural.geojson.gz": "001ca3fd752a8fb378d1769e6ec6d9cb49203ee38dbe812106d7cc8aca752620",
    "osm_turn_restrictions_routable.csv.gz": "22e91fd4a33e8fbd5809691c47cb347aba6926ccbd0de8c7ce003015b967c87d",
    "structural_anchor_evidence.csv": "c3ab598a43bfb83f31f086d6a14f29d92941969a349ef9087b5e6d87fe10b3d1",
}
EXPECTED_OUTPUT_SHA = {
    "graph_nodes.csv.gz": "d202eb930005bd71aa4c684f09041e34560484ebb4de711bcad45d95c23741c0",
    "graph_edges.csv.gz": "33c26371590a359b8673d4d0d56c1abfe7da32fdf8f6e8b98b4825628b5e86a8",
    "turn_rules.csv.gz": "cfe1be59d009c0091bb820493d2f43e70fc1f5175945f33795a0524cd9f53f8c",
    "anchor_universe.csv.gz": "4d4f5591a73d666cd5f5c7514c93cb4539d46aa51f176f0084b35d717525159b",
    "reduced_transfer_nodes.csv.gz": "4c6c2dc1d2d51e0f0a240a92b44ccda9a8018cedfd47462d7f55d581f7cc27cf",
    "reduced_transfer_seed_paths.csv.gz": "8cc0729e3b9fe603e6651d1b171c3f633835a56ceac484768f5e93c82e378f47",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def validation() -> dict:
    return json.loads((OUT / "graph_validation.json").read_text(encoding="utf-8"))


def test_gate_d_epoch_and_source_checksums_are_frozen(validation):
    assert validation["epoch_id"] == EXPECTED_EPOCH
    gate_d = validation["gate_d"]
    assert gate_d["gate_d_computational_commit"] == "7c220f7586d0f6e5cccd14a2d518be52eb1c4a55"
    assert gate_d["gate_d_artifact_id"] == 9891607118
    assert gate_d["gate_d_artifact_zip_sha256"] == "6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a"
    assert gate_d["raw_osm_sha256"] == "834d5caa0bfd6e9f4a1400ef5d2f5083ed0da60ba51c0331f59fcbcb5d4b097c"
    assert gate_d["structural_geojson_sha256"] == "9032fa1fa2f8a22fd5cfcf81ad7366269d062cb7c27ffbfd57bfba754a1b51ce"
    assert gate_d["live_osm_refresh_allowed"] is False
    for name, expected in EXPECTED_SOURCE_SHA.items():
        assert digest(SOURCE / name) == expected


def test_exact_gate_d_graph_cardinality_connectivity_and_checksum(validation):
    graph = validation["graph"]
    assert graph["graph_nodes"] == 104_071
    assert graph["graph_directed_edges"] == 199_217
    assert graph["highway_ways_input"] == 24_384
    assert graph["bus_eligible_ways"] == 15_872
    assert graph["bus_denied_ways"] == 8_512
    assert graph["weak_components"] == 183
    assert graph["largest_weak_component_nodes"] == 98_177
    assert graph["strong_components"] == 719
    assert graph["largest_strong_component_nodes"] == 97_722
    assert graph["directed_edges_without_reverse_match"] > 0
    for name, expected in EXPECTED_OUTPUT_SHA.items():
        assert digest(OUT / name) == expected


def test_edge_schema_preserves_gate_d_bus_semantics():
    edges = pd.read_csv(OUT / "graph_edges.csv.gz", compression="gzip", dtype=str, low_memory=False)
    required = {
        "edge_id", "u_node_id", "v_node_id", "osm_way_id", "length_m", "direction",
        "direction_source", "highway", "access", "vehicle", "motor_vehicle", "bus", "psv",
        "oneway", "oneway_bus", "oneway_psv", "junction", "maxspeed", "lanes", "width",
        "maxwidth", "maxheight", "maxweight", "eligibility_basis", "uncertainty_flags",
        "speed_kmh_model", "speed_status", "running_minutes_model", "epoch_id",
    }
    assert required <= set(edges.columns)
    assert (pd.to_numeric(edges["length_m"]) > 0).all()
    assert set(edges["direction"]) <= {"F", "R"}
    assert set(edges["epoch_id"]) == {EXPECTED_EPOCH}
    assert not edges["osm_way_id"].str.endswith(".0").any()
    assert edges["uncertainty_flags"].fillna("").str.len().gt(0).any()


def test_turn_restrictions_match_gate_d_loaded_structure(validation):
    info = validation["turn_restrictions"]
    assert info["bus_applicable_node_restrictions_source"] == 566
    assert info["rules_serialized_after_required_field_filter"] == 564
    assert info["distinct_rule_keys"] == 551
    assert info["rule_keys_on_graph"] == 535
    assert info["via_way_restrictions_not_approximated"] == 8
    assert info["missing_via_node_coordinates"] == 1
    rules = pd.read_csv(OUT / "turn_rules.csv.gz", compression="gzip", dtype=str)
    assert len(rules) == 564
    assert not rules["from_osm_way_id"].str.endswith(".0").any()
    assert not rules["to_osm_way_id"].str.endswith(".0").any()


def test_anchor_universe_is_source_grounded_and_no_stop_is_invented(validation):
    info = validation["anchors"]
    assert info["official_bus_stop_records_in_frozen_bbox"] == 581
    assert info["rail_anchors"] == 1
    assert info["gate_d_named_anchors"] == 15
    assert info["anchors_total"] == 597
    assert info["proposed_stops_present"] == 0
    assert info["anchors_outside_250m"] == 0
    assert info["reduced_unique_graph_nodes"] == 480
    assert info["reduced_nodes_in_largest_weak_component"] == 476
    assert info["reduced_nodes_outside_largest_weak_component"] == 4

    anchors = pd.read_csv(OUT / "anchor_universe.csv.gz", compression="gzip", dtype=str)
    rail = anchors[anchors["anchor_id"] == "rail:S01514"]
    assert len(rail) == 1
    assert rail.iloc[0]["source_name"] == "Olgiate-Calco-Brivio"
    assert rail.iloc[0]["epistemic_status"] == "FACT_OFFICIAL_TRENORD_GTFS_STATION_FROZEN_GATE_D"
    assert set(anchors["proposed_stop_status"]) == {"NOT_PROPOSED"}
    assumptions = anchors[anchors["anchor_class"] == "GATE_D_DESIGN_ANCHOR_ASSUMPTION"]
    assert set(assumptions["anchor_id"]) == {"gate_d:CALCO_SUPERIORE", "gate_d:MONDONICO", "gate_d:SAN_ZENO"}
    assert set(assumptions["epistemic_status"]) == {"ASSUMPTION"}


def test_seed_transfer_cache_is_complete_restriction_aware_and_directional(validation):
    info = validation["reduced_transfer_graph"]
    assert info["seed_anchor_records"] == 16
    assert info["seed_unique_graph_nodes"] == 16
    assert info["one_to_many_dijkstra_runs"] == 16
    assert info["ordered_seed_path_records"] == 240
    assert info["directionally_asymmetric_anchor_pairs"] == 118
    assert info["max_directional_distance_difference_m"] > 400

    paths = pd.read_csv(OUT / "reduced_transfer_seed_paths.csv.gz", compression="gzip", dtype=str)
    edge_ids = set(pd.read_csv(OUT / "graph_edges.csv.gz", compression="gzip", usecols=["edge_id"], dtype=str)["edge_id"])
    assert len(paths) == 16 * 15
    assert set(paths["turn_restrictions"]) == {"ENFORCED_GATE_D_VIA_NODE"}
    for path_ids in paths["path_edge_ids"]:
        assert path_ids
        assert set(path_ids.split(";")) <= edge_ids
    lookup = {(r.source_anchor_id, r.target_anchor_id): float(r.distance_m) for r in paths.itertuples(index=False)}
    assert abs(lookup[("gate_d:BEVERATE", "gate_d:SAN_ZENO")] - lookup[("gate_d:SAN_ZENO", "gate_d:BEVERATE")]) > 400


def test_all_seed_nodes_are_in_main_connected_component():
    reduced = pd.read_csv(OUT / "reduced_transfer_nodes.csv.gz", compression="gzip", dtype=str)
    seed = reduced[reduced["contains_seed_anchor"] == "true"]
    assert len(seed) == 16
    assert set(seed["in_largest_weak_component"]) == {"true"}


def test_materializer_has_no_live_osm_or_synthetic_generation_code():
    paths = [ROOT / "src/phase2_frozen_graph.py", ROOT / "scripts/phase2_materialize_frozen_gate_d_graph.py"]
    forbidden_import_roots = {"requests", "urllib", "httpx", "random"}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "np.random" not in text
        assert "numpy.random" not in text
        assert "overpass-api.de" not in text.lower()
        assert "overpass.private" not in text.lower()
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not ({alias.name.split(".")[0] for alias in node.names} & forbidden_import_roots)
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_import_roots


def test_validation_declares_prohibitions(validation):
    assert validation["prohibitions"] == {
        "headway_optimised": False,
        "live_overpass_used": False,
        "np_random_used": False,
        "synthetic_coordinates_used": False,
        "topology_selected": False,
    }
