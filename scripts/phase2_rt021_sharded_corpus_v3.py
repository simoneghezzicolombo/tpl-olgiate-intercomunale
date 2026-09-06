#!/usr/bin/env python3
"""Deterministic source-sharded executor and merger for RT-021.

This is a performance-only execution layer around the already tested RT-021
routing semantics. Each shard contains all 34 directed targets for exactly one
of the 35 conventional technical query anchors. Shards are independent and may
run in parallel. The merge stage restores the canonical downstream RT-010
identity contract expected by RT-022: raw stop_place_id terminal IDs, exact
RT-010 pair IDs, explicit gate_d_route_found, and explicit
admissible_for_corridor_pool.

No road geometry, stop identity, restriction rule, corridor ranking, topology,
service terminus, timetable, or policy weighting is changed here.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

import src.phase2_rt021_territorial_corridor_corpus_v3 as rt
from src.phase2_complete_directed_pairs_v3 import (
    audit_pair_execution_completeness,
    build_complete_directed_pair_manifest,
    directed_pair_id,
)
from src.phase2_final_stop_materialization_v3 import (
    attach_stop_places_to_graph,
    validate_final_stop_places,
)

SHARD_COUNT = 35
PAIRS_PER_SHARD = 34

DOWNSTREAM_PAIR_STATUS_COLUMNS = rt.PAIR_STATUS_COLUMNS + ["gate_d_route_found"]
DOWNSTREAM_CORRIDOR_COLUMNS = rt.CORRIDOR_COLUMNS + ["admissible_for_corridor_pool"]


def _load_common(rt017_dir: Path, stops_path: Path) -> dict:
    metadata_path = rt017_dir / "frozen_routing_envelope_metadata_v3.json"
    nodes_path = rt017_dir / "frozen_graph_nodes.csv.gz"
    edges_path = rt017_dir / "frozen_graph_edges.csv.gz"
    rules_path = rt017_dir / "frozen_turn_rules.csv.gz"
    reference_pairs_path = rt017_dir / "frozen_pair_results_v3.csv"
    for path in [metadata_path, nodes_path, edges_path, rules_path, reference_pairs_path, stops_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") != "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3":
        raise AssertionError("RT-021 sharded build requires certified PASS RT-017 metadata")

    expected = metadata["digests"]
    actual = {
        "frozen_graph_nodes_gz_sha256": rt.sha256_file(nodes_path),
        "frozen_graph_edges_gz_sha256": rt.sha256_file(edges_path),
        "frozen_turn_rules_gz_sha256": rt.sha256_file(rules_path),
        "frozen_pair_results_sha256": rt.sha256_file(reference_pairs_path),
    }
    for key, value in actual.items():
        if value != str(expected[key]):
            raise AssertionError(f"RT-017 frozen input digest mismatch {key}: {value} != {expected[key]}")
    stop_sha = rt.sha256_file(stops_path)
    if stop_sha != str(metadata["frozen_stop_sha256"]):
        raise AssertionError("frozen 36-stop dependency changed")

    stops = validate_final_stop_places(pd.read_csv(stops_path))
    nodes = pd.read_csv(nodes_path, compression="gzip")
    edges = pd.read_csv(edges_path, compression="gzip", dtype=str)
    rules = pd.read_csv(rules_path, compression="gzip", dtype=str).fillna("")
    reference_pairs = pd.read_csv(reference_pairs_path, dtype=str).fillna("")
    epoch = rt.graph_epoch_id(metadata)
    rt018_nodes = rt.adapt_rt017_nodes_for_rt018(nodes, epoch)
    attachments = attach_stop_places_to_graph(stops, rt018_nodes)
    anchors_internal = rt.conventional_anchor_universe(attachments)
    manifest_internal = rt.build_rt021_pair_manifest(anchors_internal)

    source_ids = sorted(manifest_internal["source_routing_terminal_id"].astype(str).unique())
    if len(source_ids) != SHARD_COUNT:
        raise AssertionError(f"expected {SHARD_COUNT} source anchors, got {len(source_ids)}")

    return {
        "metadata": metadata,
        "actual_graph_digests": actual,
        "stop_sha": stop_sha,
        "nodes": nodes,
        "edges": edges,
        "rules": rules,
        "reference_pairs": reference_pairs,
        "epoch": epoch,
        "attachments": attachments,
        "anchors_internal": anchors_internal,
        "manifest_internal": manifest_internal,
        "source_ids": source_ids,
    }


def select_shard_manifest(manifest: pd.DataFrame, shard_index: int) -> tuple[str, pd.DataFrame]:
    sources = sorted(manifest["source_routing_terminal_id"].astype(str).unique())
    if len(sources) != SHARD_COUNT:
        raise AssertionError(f"expected {SHARD_COUNT} source anchors, got {len(sources)}")
    if not 0 <= int(shard_index) < SHARD_COUNT:
        raise ValueError(f"shard_index must be in [0,{SHARD_COUNT - 1}]")
    source = sources[int(shard_index)]
    shard = manifest[manifest["source_routing_terminal_id"].astype(str).eq(source)].copy()
    shard = shard.sort_values(
        ["source_routing_terminal_id", "target_routing_terminal_id"], kind="mergesort"
    ).reset_index(drop=True)
    if len(shard) != PAIRS_PER_SHARD:
        raise AssertionError(f"source shard {source} has {len(shard)} pairs, expected {PAIRS_PER_SHARD}")
    return source, shard


def build_shard(
    *,
    rt017_dir: Path,
    stops_path: Path,
    output_dir: Path,
    shard_index: int,
    k: int,
    max_raw_state_paths: int,
) -> dict:
    common = _load_common(rt017_dir, stops_path)
    source, shard_manifest = select_shard_manifest(common["manifest_internal"], shard_index)

    old_expected = rt.EXPECTED_DIRECTED_PAIRS
    rt.EXPECTED_DIRECTED_PAIRS = len(shard_manifest)
    try:
        corridors, pair_status, routing_audit = rt.route_corpus(
            shard_manifest,
            common["anchors_internal"],
            common["edges"],
            common["rules"],
            common["nodes"],
            common["reference_pairs"],
            epoch_id=common["epoch"],
            k=k,
            max_raw_state_paths=max_raw_state_paths,
        )
    finally:
        rt.EXPECTED_DIRECTED_PAIRS = old_expected

    if len(pair_status) != PAIRS_PER_SHARD:
        raise AssertionError("shard pair execution count mismatch")
    if pair_status["corridor_count"].astype(int).lt(1).any():
        raise AssertionError("shard contains a directed pair without admitted corridor")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"rt021_shard_{int(shard_index):02d}"
    pair_sha = rt.write_csv(
        output_dir / f"{stem}_pair_status.csv",
        pair_status,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
        columns=rt.PAIR_STATUS_COLUMNS,
    )
    corridor_bytes = rt.canonical_csv_bytes(
        corridors,
        sort_by=["pair_id", "corridor_rank_by_running_time", "corridor_id"],
        columns=rt.CORRIDOR_COLUMNS,
    )
    corridor_sha = rt.sha256_bytes(corridor_bytes)
    corridor_gzip_sha = rt.write_deterministic_gzip(
        output_dir / f"{stem}_corridors.csv.gz", corridor_bytes
    )
    metadata = {
        "status": "PASS_RT021_SOURCE_SHARD_V3",
        "contract": rt.CONTRACT,
        "shard_index": int(shard_index),
        "source_routing_terminal_id": source,
        "graph_epoch_id": common["epoch"],
        "directed_pair_count": len(pair_status),
        "corridor_count": len(corridors),
        "pair_status_sha256": pair_sha,
        "corridor_uncompressed_sha256": corridor_sha,
        "corridor_gzip_sha256": corridor_gzip_sha,
        "state_graph": routing_audit["state_graph"],
        "semantics": "PERFORMANCE_SHARD_ONLY_NO_ROUTING_OR_TOPOLOGY_CHANGE",
    }
    (output_dir / f"{stem}_metadata.json").write_bytes(rt.canonical_json_bytes(metadata))
    return metadata


def _strip_internal_terminal(value: object) -> str:
    text = str(value)
    prefix = "STOP_PLACE::"
    if not text.startswith(prefix) or len(text) <= len(prefix):
        raise ValueError(f"unexpected internal RT-021 terminal identity: {text}")
    return text[len(prefix):]


def canonicalize_downstream_handoff(
    pair_status: pd.DataFrame,
    corridors: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert internal prefixed query IDs to the canonical RT-010/RT-022 contract."""
    p = pair_status.copy()
    c = corridors.copy()

    for frame in (p, c):
        frame["source_routing_terminal_id"] = frame["source_routing_terminal_id"].map(
            _strip_internal_terminal
        )
        frame["target_routing_terminal_id"] = frame["target_routing_terminal_id"].map(
            _strip_internal_terminal
        )

    p["pair_id"] = [
        directed_pair_id(source, target)
        for source, target in zip(
            p["source_routing_terminal_id"], p["target_routing_terminal_id"]
        )
    ]
    p["gate_d_route_found"] = True

    c["pair_id"] = [
        directed_pair_id(source, target)
        for source, target in zip(
            c["source_routing_terminal_id"], c["target_routing_terminal_id"]
        )
    ]
    c["corridor_id"] = [
        rt.corridor_id(pair_id, [part for part in str(edge_ids).split(";") if part])
        for pair_id, edge_ids in zip(c["pair_id"], c["path_edge_ids"])
    ]
    c["admissible_for_corridor_pool"] = True

    if p["pair_id"].duplicated().any():
        raise AssertionError("canonical downstream pair IDs are not unique")
    if c["corridor_id"].duplicated().any():
        raise AssertionError("canonical downstream corridor IDs are not unique")
    return p, c


def _read_shards(shard_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    meta_paths = sorted(shard_dir.glob("rt021_shard_*_metadata.json"))
    if len(meta_paths) != SHARD_COUNT:
        raise AssertionError(f"expected {SHARD_COUNT} shard metadata files, got {len(meta_paths)}")
    metas = [json.loads(path.read_text(encoding="utf-8")) for path in meta_paths]
    indexes = sorted(int(meta["shard_index"]) for meta in metas)
    if indexes != list(range(SHARD_COUNT)):
        raise AssertionError(f"shard index coverage mismatch: {indexes}")
    sources = [str(meta["source_routing_terminal_id"]) for meta in metas]
    if len(set(sources)) != SHARD_COUNT:
        raise AssertionError("source routing terminal shard coverage is not unique")
    epochs = {str(meta["graph_epoch_id"]) for meta in metas}
    if len(epochs) != 1:
        raise AssertionError(f"shards do not share one graph epoch: {sorted(epochs)}")
    if not all(meta.get("status") == "PASS_RT021_SOURCE_SHARD_V3" for meta in metas):
        raise AssertionError("one or more source shards are not PASS")

    pair_frames = []
    corridor_frames = []
    for meta in metas:
        idx = int(meta["shard_index"])
        stem = f"rt021_shard_{idx:02d}"
        pair_path = shard_dir / f"{stem}_pair_status.csv"
        corridor_path = shard_dir / f"{stem}_corridors.csv.gz"
        if rt.sha256_file(pair_path) != str(meta["pair_status_sha256"]):
            raise AssertionError(f"shard {idx} pair-status digest mismatch")
        if rt.sha256_file(corridor_path) != str(meta["corridor_gzip_sha256"]):
            raise AssertionError(f"shard {idx} corridor gzip digest mismatch")
        pair_frames.append(pd.read_csv(pair_path))
        with gzip.open(corridor_path, "rt", encoding="utf-8") as handle:
            corridor_frames.append(pd.read_csv(handle))

    pair_status = pd.concat(pair_frames, ignore_index=True)
    corridors = pd.concat(corridor_frames, ignore_index=True)
    return pair_status, corridors, metas


def merge_shards(
    *,
    rt017_dir: Path,
    stops_path: Path,
    shard_dir: Path,
    output_dir: Path,
    k: int,
    max_raw_state_paths: int,
    deterministic_replay_verified: bool,
) -> dict:
    common = _load_common(rt017_dir, stops_path)
    pair_internal, corridors_internal, metas = _read_shards(shard_dir)
    if len(pair_internal) != rt.EXPECTED_DIRECTED_PAIRS:
        raise AssertionError(f"merged pair count {len(pair_internal)} != {rt.EXPECTED_DIRECTED_PAIRS}")

    pair_status, corridors = canonicalize_downstream_handoff(
        pair_internal, corridors_internal
    )

    conventional = common["attachments"][
        common["attachments"]["service_class"].astype(str).eq("CONVENTIONAL_TPL")
    ].copy()
    canonical_anchor_frame = pd.DataFrame(
        {"routing_terminal_id": conventional["stop_place_id"].astype(str)}
    )
    canonical_manifest_result = build_complete_directed_pair_manifest(
        canonical_anchor_frame, max_directed_pairs=5000
    )
    if not canonical_manifest_result["complete"]:
        raise AssertionError(canonical_manifest_result)
    manifest = canonical_manifest_result["manifest"].copy()
    if len(manifest) != rt.EXPECTED_DIRECTED_PAIRS:
        raise AssertionError("canonical RT-010 manifest does not contain 1,190 directed pairs")

    execution = audit_pair_execution_completeness(manifest, pair_status)
    if not execution["complete"]:
        raise AssertionError(execution)
    if pair_status["corridor_count"].astype(int).lt(1).any():
        raise AssertionError("merged handoff contains a pair without admitted corridor")

    attachment_out = common["attachments"].copy()
    for column in ["route_ready", "service_class_automatic", "automatic_materialization_eligible"]:
        attachment_out[column] = attachment_out[column].map(lambda value: str(bool(value)).lower())

    output_dir.mkdir(parents=True, exist_ok=True)
    attachment_sha = rt.write_csv(
        output_dir / "rt021_stop_attachments_v3.csv",
        attachment_out,
        sort_by=["stop_place_id"],
    )
    manifest_sha = rt.write_csv(
        output_dir / "rt021_complete_directed_pair_manifest_v3.csv",
        manifest,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
    )
    pair_status_sha = rt.write_csv(
        output_dir / "rt021_pair_execution_status_v3.csv",
        pair_status,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
        columns=DOWNSTREAM_PAIR_STATUS_COLUMNS,
    )
    corpus_bytes = rt.canonical_csv_bytes(
        corridors,
        sort_by=["pair_id", "corridor_rank_by_running_time", "corridor_id"],
        columns=DOWNSTREAM_CORRIDOR_COLUMNS,
    )
    corpus_uncompressed_sha = rt.sha256_bytes(corpus_bytes)
    corpus_gzip_sha = rt.write_deterministic_gzip(
        output_dir / "rt021_corridor_corpus_v3.csv.gz", corpus_bytes
    )

    conventional_attachment_max = float(
        pd.to_numeric(
            common["attachments"].loc[
                common["attachments"]["service_class"].astype(str).eq("CONVENTIONAL_TPL"),
                "attachment_distance_m",
            ],
            errors="raise",
        ).max()
    )
    corridor_counts = pair_status["corridor_count"].astype(int)
    runtime_values = pd.to_numeric(corridors["running_minutes_model"], errors="raise")
    distance_values = pd.to_numeric(corridors["distance_m"], errors="raise")
    graph_stats = metas[0]["state_graph"]
    validation = {
        "status": "PASS_RT021_FROZEN_TERRITORIAL_CORRIDOR_CORPUS_V3",
        "contract": rt.CONTRACT,
        "issue": 55,
        "graph_epoch_id": common["epoch"],
        "execution_mode": "35_SOURCE_SHARDS_DETERMINISTIC_MERGE",
        "rt017": {
            "status": common["metadata"]["status"],
            "osm_snapshot_timestamp": common["metadata"]["osm_snapshot_timestamp"],
            "frozen_level": common["metadata"]["frozen_level"],
            "frozen_margin_m": common["metadata"]["frozen_margin_m"],
            "input_digests": common["actual_graph_digests"],
        },
        "stop_layer": {
            "frozen_stop_sha256": common["stop_sha"],
            "stop_place_count": len(common["attachments"]),
            "conventional_tpl_count": int(common["attachments"]["service_class"].astype(str).eq("CONVENTIONAL_TPL").sum()),
            "special_service_count": int(common["attachments"]["service_class"].astype(str).eq("SPECIAL_SERVICE").sum()),
            "conventional_max_attachment_distance_m": conventional_attachment_max,
            "all_conventional_route_ready_le_75m": conventional_attachment_max <= 75.0,
            "special_service_excluded_from_pair_universe": True,
            "attachment_identity_sha256": attachment_sha,
        },
        "pair_universe": {
            "technical_anchor_semantics": "35_CONVENTIONAL_STOP_PLACES_AS_PAIR_QUERY_ANCHORS_NOT_SERVICE_TERMINI",
            "terminal_id_semantics": "RAW_STOP_PLACE_ID_CANONICAL_RT010_DOWNSTREAM_CONTRACT",
            "directed_pair_count": len(manifest),
            "unordered_pair_count": len(manifest) // 2,
            "complete_execution_count": len(pair_status),
            "pair_manifest_sha256": manifest_sha,
            "pair_execution_status_sha256": pair_status_sha,
            "gate_d_route_found_explicit": True,
        },
        "corridor_corpus": {
            "generator": "RESTRICTION_AWARE_EDGE_STATE_YEN_KSP_V3",
            "k_exploration_depth": int(k),
            "k_semantics": "AUDITED_TECHNICAL_EXPLORATION_DEPTH_NOT_SERVICE_RANK_OR_COMPLETENESS_CLAIM",
            "max_raw_state_paths_per_pair": int(max_raw_state_paths),
            "corridor_count": len(corridors),
            "pairs_with_1_corridor": int((corridor_counts == 1).sum()),
            "pairs_with_2_corridors": int((corridor_counts == 2).sum()),
            "pairs_with_3_corridors": int((corridor_counts == 3).sum()),
            "min_corridors_per_pair": int(corridor_counts.min()),
            "max_corridors_per_pair": int(corridor_counts.max()),
            "runtime_min_min": float(runtime_values.min()),
            "runtime_min_median": float(runtime_values.median()),
            "runtime_min_max": float(runtime_values.max()),
            "distance_m_min": float(distance_values.min()),
            "distance_m_median": float(distance_values.median()),
            "distance_m_max": float(distance_values.max()),
            "corridor_corpus_uncompressed_sha256": corpus_uncompressed_sha,
            "corridor_corpus_gzip_sha256": corpus_gzip_sha,
            "admissible_for_corridor_pool_explicit": True,
            "all_paths_physical_loopless": bool(corridors["physical_loopless"].astype(str).eq("true").all()),
            "all_pair_tie_bands_complete": bool(pair_status["tie_band_complete"].astype(bool).all()),
            "all_certified_shortest_sequences_match_rt017": bool(pair_status["certified_edge_sequence_matches_rt017"].astype(bool).all()),
            "external_municipality_traversal": "NOT_DERIVED_RT021_GRAPH_HAS_NO_MUNICIPALITY_LABEL_AND_NO_BOUNDARY_FILTER_IS_ALLOWED",
        },
        "sharded_execution": {
            "source_shard_count": SHARD_COUNT,
            "pairs_per_source_shard": PAIRS_PER_SHARD,
            "deterministic_replay_verified_per_shard": bool(deterministic_replay_verified),
        },
        "state_graph": graph_stats,
        "checks": {
            "exactly_36_stop_places": len(common["attachments"]) == 36,
            "exactly_35_conventional_plus_1_special": (
                int(common["attachments"]["service_class"].astype(str).eq("CONVENTIONAL_TPL").sum()) == 35
                and int(common["attachments"]["service_class"].astype(str).eq("SPECIAL_SERVICE").sum()) == 1
            ),
            "all_35_conventional_route_ready_le_75m": conventional_attachment_max <= 75.0,
            "exactly_1190_directed_pairs": len(manifest) == rt.EXPECTED_DIRECTED_PAIRS,
            "pair_execution_complete_no_omission": bool(execution["complete"]),
            "all_pairs_have_at_least_one_corridor": bool(corridor_counts.ge(1).all()),
            "all_ksp_tie_bands_complete": bool(pair_status["tie_band_complete"].astype(bool).all()),
            "all_certified_paths_match_rt017": bool(pair_status["certified_edge_sequence_matches_rt017"].astype(bool).all()),
            "all_corridors_physical_loopless": bool(corridors["physical_loopless"].astype(str).eq("true").all()),
            "canonical_rt010_terminal_and_pair_identity": bool(execution["complete"]),
            "gate_d_route_found_explicit": bool(pair_status["gate_d_route_found"].astype(bool).all()),
            "admissible_for_corridor_pool_explicit": bool(corridors["admissible_for_corridor_pool"].astype(bool).all()),
            "deterministic_replay_verified_per_shard": bool(deterministic_replay_verified),
            "municipal_boundaries_not_used_as_routing_rules": common["metadata"].get("municipal_boundaries_used_as_routing_rules") is False,
            "stop_discovery_not_performed": common["metadata"].get("stop_discovery_performed") is False,
        },
        "claims_not_authorized": [
            "NETWORK_RECOMMENDATION",
            "TOPOLOGY_WINNER",
            "SERVICE_TERMINUS_SELECTION",
            "PRIMARY",
            "RUNNER_UP",
            "FIGURE_EIGHT_PRESCRIPTION",
            "NEW_STOP_HYPOTHESIS",
        ],
    }
    if not all(validation["checks"].values()):
        validation["status"] = "FAIL_RT021_VALIDATION_CHECK"
        (output_dir / "rt021_validation_v3.json").write_bytes(rt.canonical_json_bytes(validation))
        raise AssertionError(validation["checks"])
    (output_dir / "rt021_validation_v3.json").write_bytes(rt.canonical_json_bytes(validation))
    return validation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    shard = sub.add_parser("shard")
    shard.add_argument("--rt017-dir", type=Path, required=True)
    shard.add_argument("--stops", type=Path, default=rt.STOP_PATH)
    shard.add_argument("--output-dir", type=Path, required=True)
    shard.add_argument("--shard-index", type=int, required=True)
    shard.add_argument("--k", type=int, default=rt.KSP_K)
    shard.add_argument("--max-raw-state-paths", type=int, default=rt.KSP_MAX_RAW_STATE_PATHS)

    merge = sub.add_parser("merge")
    merge.add_argument("--rt017-dir", type=Path, required=True)
    merge.add_argument("--stops", type=Path, default=rt.STOP_PATH)
    merge.add_argument("--shard-dir", type=Path, required=True)
    merge.add_argument("--output-dir", type=Path, required=True)
    merge.add_argument("--k", type=int, default=rt.KSP_K)
    merge.add_argument("--max-raw-state-paths", type=int, default=rt.KSP_MAX_RAW_STATE_PATHS)
    merge.add_argument("--deterministic-replay-verified", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.mode == "shard":
        result = build_shard(
            rt017_dir=args.rt017_dir,
            stops_path=args.stops,
            output_dir=args.output_dir,
            shard_index=args.shard_index,
            k=args.k,
            max_raw_state_paths=args.max_raw_state_paths,
        )
    else:
        result = merge_shards(
            rt017_dir=args.rt017_dir,
            stops_path=args.stops,
            shard_dir=args.shard_dir,
            output_dir=args.output_dir,
            k=args.k,
            max_raw_state_paths=args.max_raw_state_paths,
            deterministic_replay_verified=args.deterministic_replay_verified,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
