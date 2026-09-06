#!/usr/bin/env python3
"""Parallel, semantics-preserving source-shard executor for RT-021.

Each worker evaluates one directed OD pair with the exact existing
`k_shortest_loopless_paths` function. On Linux the immutable restriction-aware
state graph and frozen lookup tables are inherited by fork, while each worker
gets a private copy before the KSP routine temporarily adds its query nodes.
Results are canonically sorted in the parent, so worker completion order cannot
change corpus identity.

This module changes execution only. It does not change K, graph data, turn
rules, stop attachment, path admissibility, corridor ranking, or downstream
identity semantics.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import pandas as pd

import src.phase2_rt021_territorial_corridor_corpus_v3 as rt
import scripts.phase2_rt021_sharded_corpus_v3 as shard_base


_WORKER_CONTEXT = None
_WORKER_TERMINAL_TO_STOP: dict[str, str] = {}
_WORKER_TERMINAL_TO_NODE: dict[str, str] = {}
_WORKER_NODE_XY: dict[str, tuple[float, float]] = {}
_WORKER_REFERENCE: dict[tuple[str, str], dict] = {}
_WORKER_EPOCH = ""
_WORKER_K = 0
_WORKER_MAX_RAW = 0


def _configure_worker_state(
    *,
    anchors: pd.DataFrame,
    edges: pd.DataFrame,
    rules: pd.DataFrame,
    graph_nodes: pd.DataFrame,
    reference_pairs: pd.DataFrame,
    epoch_id: str,
    k: int,
    max_raw_state_paths: int,
) -> dict:
    global _WORKER_CONTEXT
    global _WORKER_TERMINAL_TO_STOP
    global _WORKER_TERMINAL_TO_NODE
    global _WORKER_NODE_XY
    global _WORKER_REFERENCE
    global _WORKER_EPOCH
    global _WORKER_K
    global _WORKER_MAX_RAW

    _WORKER_TERMINAL_TO_STOP = dict(
        zip(anchors["routing_terminal_id"].astype(str), anchors["stop_place_id"].astype(str))
    )
    _WORKER_TERMINAL_TO_NODE = dict(
        zip(anchors["routing_terminal_id"].astype(str), anchors["graph_node_id"].astype(str))
    )
    _WORKER_NODE_XY = {
        str(row.node_id): (float(row.x), float(row.y))
        for row in graph_nodes[["node_id", "x", "y"]].itertuples(index=False)
    }
    _WORKER_REFERENCE = rt.rt017_reference_lookup(reference_pairs)
    _WORKER_CONTEXT = rt.build_restriction_aware_state_context(edges, rules)
    _WORKER_EPOCH = str(epoch_id)
    _WORKER_K = int(k)
    _WORKER_MAX_RAW = int(max_raw_state_paths)
    return dict(_WORKER_CONTEXT.stats)


def _route_pair_worker(pair: dict[str, Any]) -> tuple[list[dict], dict]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("parallel RT-021 worker context not configured")

    pair_id = str(pair["pair_id"])
    source_terminal = str(pair["source_routing_terminal_id"])
    target_terminal = str(pair["target_routing_terminal_id"])
    source_stop = _WORKER_TERMINAL_TO_STOP[source_terminal]
    target_stop = _WORKER_TERMINAL_TO_STOP[target_terminal]
    source_node = _WORKER_TERMINAL_TO_NODE[source_terminal]
    target_node = _WORKER_TERMINAL_TO_NODE[target_terminal]
    if source_node == target_node:
        raise AssertionError(
            f"distinct conventional anchors share RT-017 graph node: "
            f"{source_stop}->{target_stop} at {source_node}"
        )

    ref = _WORKER_REFERENCE.get((source_stop, target_stop))
    if ref is None:
        raise AssertionError(f"missing RT-017 reference probe pair: {source_stop}->{target_stop}")
    if str(ref["route_found"]).strip().lower() not in {"true", "1"}:
        raise AssertionError(
            f"RT-017 certified graph said conventional pair was unreachable: "
            f"{source_stop}->{target_stop}"
        )
    if (
        str(ref["source_graph_node_id"]) != source_node
        or str(ref["target_graph_node_id"]) != target_node
    ):
        raise AssertionError(
            "RT-018 reattachment drifted from RT-017 certified probe attachment: "
            f"{source_stop}->{target_stop}"
        )

    result = rt.k_shortest_loopless_paths(
        _WORKER_CONTEXT,
        source_node,
        target_node,
        k=_WORKER_K,
        max_raw_state_paths=_WORKER_MAX_RAW,
    )
    if not result["certified_shortest_present"]:
        raise AssertionError(f"KSP lost RT-017 certified reachability for {source_stop}->{target_stop}")
    if not result["certified_state_path_representable"]:
        raise AssertionError(
            f"certified path is not state-representable for {source_stop}->{target_stop}"
        )
    if not result["tie_band_complete"]:
        raise AssertionError(
            f"deterministic KSP tie band incomplete for {source_stop}->{target_stop}"
        )
    certified = result["certified_path"]
    if certified is None:
        raise AssertionError("certified_shortest_present without certified_path")

    reference_edges = [part for part in str(ref["path_edge_ids"]).split(";") if part]
    certified_edges = [str(value) for value in certified["edge_ids"]]
    edge_exact = certified_edges == reference_edges
    runtime_delta = float(certified["running_minutes_model"]) - float(ref["running_minutes_model"])
    distance_delta = float(certified["distance_m"]) - float(ref["distance_m"])
    if not edge_exact or abs(runtime_delta) > 1e-9 or abs(distance_delta) > 1e-6:
        raise AssertionError(
            "KSP certified shortest differs from frozen RT-017 pair evidence: "
            f"{source_stop}->{target_stop}, edge_exact={edge_exact}, "
            f"runtime_delta={runtime_delta}, distance_delta={distance_delta}"
        )

    paths = list(result["paths"])
    if not paths:
        raise AssertionError(
            f"no physically loopless corridor admitted for certified reachable pair "
            f"{source_stop}->{target_stop}"
        )

    corridor_rows: list[dict] = []
    seen_edge_sequences: set[tuple[str, ...]] = set()
    for path in paths:
        edge_ids = [str(value) for value in path["edge_ids"]]
        physical_nodes = [str(value) for value in path["physical_nodes"]]
        key = tuple(edge_ids)
        if key in seen_edge_sequences:
            raise AssertionError(f"duplicate corridor edge sequence within pair {pair_id}")
        seen_edge_sequences.add(key)
        if not bool(path["physical_loopless"]):
            raise AssertionError(f"physical loop survived KSP corridor filter for {pair_id}")
        is_certified = edge_ids == certified_edges
        corridor_rows.append(
            {
                "corridor_id": rt.corridor_id(pair_id, edge_ids),
                "pair_id": pair_id,
                "source_routing_terminal_id": source_terminal,
                "target_routing_terminal_id": target_terminal,
                "source_stop_place_id": source_stop,
                "target_stop_place_id": target_stop,
                "source_graph_node_id": source_node,
                "target_graph_node_id": target_node,
                "corridor_rank_by_running_time": int(path["rank"]),
                "running_minutes_model": f"{float(path['running_minutes_model']):.9f}",
                "distance_m": f"{float(path['distance_m']):.6f}",
                "edge_count": len(edge_ids),
                "physical_node_count": len(physical_nodes),
                "path_edge_ids": ";".join(edge_ids),
                "path_node_ids": ";".join(physical_nodes),
                "path_geometry_sha256": rt.path_geometry_sha256(physical_nodes, _WORKER_NODE_XY),
                "provenance": str(path["provenance"]),
                "is_exact_rt017_certified_shortest": str(is_certified).lower(),
                "certified_shortest_physical_loopless": str(
                    bool(result["certified_shortest_physical_loopless"])
                ).lower(),
                "physical_loopless": "true",
                "tie_band_complete": "true",
                "graph_epoch_id": _WORKER_EPOCH,
                "decision_role": "TECHNICAL_CORRIDOR_POOL_NOT_NETWORK_OR_TERMINAL_SELECTION",
            }
        )

    pair_row = {
        "pair_id": pair_id,
        "source_routing_terminal_id": source_terminal,
        "target_routing_terminal_id": target_terminal,
        "source_stop_place_id": source_stop,
        "target_stop_place_id": target_stop,
        "source_graph_node_id": source_node,
        "target_graph_node_id": target_node,
        "status": "PASS_ROUTED_LOOPLESS_CORRIDOR_POOL",
        "corridor_count": len(paths),
        "certified_shortest_present": True,
        "certified_shortest_physical_loopless": bool(
            result["certified_shortest_physical_loopless"]
        ),
        "certified_state_path_representable": True,
        "certified_edge_sequence_matches_rt017": edge_exact,
        "certified_runtime_delta_vs_rt017_min": f"{runtime_delta:.12f}",
        "certified_distance_delta_vs_rt017_m": f"{distance_delta:.9f}",
        "raw_state_paths_examined": int(result["raw_state_paths_examined"]),
        "state_generator_exhausted": bool(result["state_generator_exhausted"]),
        "tie_band_complete": True,
        "graph_epoch_id": _WORKER_EPOCH,
    }
    return corridor_rows, pair_row


def route_corpus_parallel(
    manifest: pd.DataFrame,
    anchors: pd.DataFrame,
    edges: pd.DataFrame,
    rules: pd.DataFrame,
    graph_nodes: pd.DataFrame,
    reference_pairs: pd.DataFrame,
    *,
    epoch_id: str,
    k: int,
    max_raw_state_paths: int,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if k < 2:
        raise ValueError("RT-021 alternative corridor corpus requires k >= 2")
    if workers < 1:
        raise ValueError("workers must be >= 1")

    state_stats = _configure_worker_state(
        anchors=anchors,
        edges=edges,
        rules=rules,
        graph_nodes=graph_nodes,
        reference_pairs=reference_pairs,
        epoch_id=epoch_id,
        k=k,
        max_raw_state_paths=max_raw_state_paths,
    )
    records = manifest.sort_values(
        ["source_routing_terminal_id", "target_routing_terminal_id"], kind="mergesort"
    ).to_dict("records")

    if workers == 1:
        routed = [_route_pair_worker(record) for record in records]
    else:
        # GitHub's RT-021 workflow is Linux-only. Fork keeps the large immutable
        # state graph copy-on-write and isolates temporary KSP query mutations.
        context = mp.get_context("fork")
        with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
            routed = list(pool.map(_route_pair_worker, records, chunksize=1))

    corridor_rows: list[dict] = []
    pair_rows: list[dict] = []
    for corridors_for_pair, pair_row in routed:
        corridor_rows.extend(corridors_for_pair)
        pair_rows.append(pair_row)

    corridors = pd.DataFrame(corridor_rows, columns=rt.CORRIDOR_COLUMNS).sort_values(
        ["pair_id", "corridor_rank_by_running_time", "corridor_id"], kind="mergesort"
    ).reset_index(drop=True)
    pair_status = pd.DataFrame(pair_rows, columns=rt.PAIR_STATUS_COLUMNS).sort_values(
        ["source_routing_terminal_id", "target_routing_terminal_id"], kind="mergesort"
    ).reset_index(drop=True)

    execution = rt.audit_pair_execution_completeness(manifest, pair_status)
    if not execution["complete"]:
        raise AssertionError(execution)
    if len(pair_status) != len(manifest):
        raise AssertionError(f"pair status count changed: {len(pair_status)} != {len(manifest)}")
    if pair_status["corridor_count"].astype(int).lt(1).any():
        raise AssertionError("at least one directed pair has no admitted corridor")
    if corridors.empty or corridors["corridor_id"].duplicated().any():
        raise AssertionError("corridor corpus is empty or corridor_id is not unique")
    return corridors, pair_status, {"state_graph": state_stats, "pair_execution": execution}


def build_parallel_shard(
    *,
    rt017_dir: Path,
    stops_path: Path,
    output_dir: Path,
    shard_index: int,
    k: int,
    max_raw_state_paths: int,
    workers: int,
) -> dict:
    common = shard_base._load_common(rt017_dir, stops_path)
    source, shard_manifest = shard_base.select_shard_manifest(
        common["manifest_internal"], shard_index
    )
    corridors, pair_status, routing_audit = route_corpus_parallel(
        shard_manifest,
        common["anchors_internal"],
        common["edges"],
        common["rules"],
        common["nodes"],
        common["reference_pairs"],
        epoch_id=common["epoch"],
        k=k,
        max_raw_state_paths=max_raw_state_paths,
        workers=workers,
    )

    if len(pair_status) != shard_base.PAIRS_PER_SHARD:
        raise AssertionError("parallel shard pair execution count mismatch")

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
        "parallel_workers": int(workers),
        "semantics": "PERFORMANCE_PARALLELISM_ONLY_EXACT_EXISTING_KSP_PER_DIRECTED_PAIR",
    }
    (output_dir / f"{stem}_metadata.json").write_bytes(rt.canonical_json_bytes(metadata))
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rt017-dir", type=Path, required=True)
    parser.add_argument("--stops", type=Path, default=rt.STOP_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--k", type=int, default=rt.KSP_K)
    parser.add_argument("--max-raw-state-paths", type=int, default=rt.KSP_MAX_RAW_STATE_PATHS)
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    args = parser.parse_args()
    result = build_parallel_shard(
        rt017_dir=args.rt017_dir,
        stops_path=args.stops,
        output_dir=args.output_dir,
        shard_index=args.shard_index,
        k=args.k,
        max_raw_state_paths=args.max_raw_state_paths,
        workers=args.workers,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
