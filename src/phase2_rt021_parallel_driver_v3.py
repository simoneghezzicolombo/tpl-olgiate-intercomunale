from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from src import phase2_rt021_bounded_corpus_v3 as bounded
from src import phase2_rt021_territorial_corridor_corpus_v3 as core
from src import phase2_rt021_validated_grid_corpus_v3 as grid
from src.phase2_complete_directed_pairs_v3 import audit_pair_execution_completeness

# Capture the production RT-021 router before main() temporarily monkeypatches
# bounded.route_corpus to the parallel dispatcher. Workers must always execute
# the validated-grid implementation itself, never recurse into the dispatcher.
ORIGINAL_GRID_ROUTE_CORPUS = grid.route_corpus


def partition_manifest(manifest: pd.DataFrame, workers: int) -> list[pd.DataFrame]:
    """Partition complete directed pairs by whole source-anchor groups."""
    if workers < 1:
        raise ValueError("workers must be >= 1")
    source_column = "source_routing_terminal_id"
    sources = sorted(set(manifest[source_column].astype(str)))
    buckets: list[list[str]] = [[] for _ in range(min(workers, len(sources)))]
    for index, source in enumerate(sources):
        buckets[index % len(buckets)].append(source)
    parts = []
    for bucket in buckets:
        part = manifest[manifest[source_column].astype(str).isin(bucket)].copy()
        part = part.sort_values(
            ["source_routing_terminal_id", "target_routing_terminal_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        if not part.empty:
            parts.append(part)
    combined_ids = [pair_id for part in parts for pair_id in part["pair_id"].astype(str)]
    if len(combined_ids) != len(manifest) or len(set(combined_ids)) != len(manifest):
        raise AssertionError("parallel RT-021 partition lost or duplicated pair IDs")
    return parts


def _route_partition(payload):
    manifest, anchors, edges, rules, graph_nodes, reference_pairs, epoch_id = payload
    # Each worker validates its supplied complete sub-manifest. The project-wide
    # 1,190 cardinality is reasserted after deterministic merge.
    original_expected = core.EXPECTED_DIRECTED_PAIRS
    core.EXPECTED_DIRECTED_PAIRS = len(manifest)
    try:
        return ORIGINAL_GRID_ROUTE_CORPUS(
            manifest,
            anchors,
            edges,
            rules,
            graph_nodes,
            reference_pairs,
            epoch_id=epoch_id,
        )
    finally:
        core.EXPECTED_DIRECTED_PAIRS = original_expected


def parallel_route_corpus(
    manifest,
    anchors,
    edges,
    rules,
    graph_nodes,
    reference_pairs,
    *,
    epoch_id,
):
    worker_count = min(4, max(1, os.cpu_count() or 1), len(set(manifest["source_routing_terminal_id"])))
    parts = partition_manifest(manifest, worker_count)
    payloads = [
        (part, anchors, edges, rules, graph_nodes, reference_pairs, epoch_id)
        for part in parts
    ]
    if len(payloads) == 1:
        results = [_route_partition(payloads[0])]
    else:
        with ProcessPoolExecutor(max_workers=len(payloads)) as pool:
            results = list(pool.map(_route_partition, payloads))

    corridors = pd.concat([result[0] for result in results], ignore_index=True)
    status = pd.concat([result[1] for result in results], ignore_index=True)
    corridors = corridors.sort_values(
        ["pair_id", "corridor_rank_by_running_time", "corridor_id"], kind="mergesort"
    ).reset_index(drop=True)
    status = status.sort_values(
        ["source_routing_terminal_id", "target_routing_terminal_id"], kind="mergesort"
    ).reset_index(drop=True)

    execution = audit_pair_execution_completeness(manifest, status)
    if not execution["complete"]:
        raise AssertionError(execution)
    if len(status) != 1190 or status["pair_id"].astype(str).nunique() != 1190:
        raise AssertionError("parallel merge did not restore exactly 1,190 directed pair statuses")
    if corridors.empty or corridors["corridor_id"].astype(str).duplicated().any():
        raise AssertionError("parallel merge produced empty or duplicate corridor corpus")
    if not (
        (status["corridor_count"].astype(int) > 0)
        | status["failure_reason"].astype(str).ne("")
    ).all():
        raise AssertionError("parallel merge lost a pair without corridor or explicit failure")

    audits = [result[2] for result in results]
    return corridors, status, {
        "pair_execution": execution,
        "graph_directed_edges": audits[0]["graph_directed_edges"],
        "turn_rules": audits[0]["turn_rules"],
        "generation_paths_examined_total": sum(
            int(audit["generation_paths_examined_total"]) for audit in audits
        ),
        "ksp_fallback_pair_count": 0,
        "sensitivity_fallback_pair_count": sum(
            int(audit["sensitivity_fallback_pair_count"]) for audit in audits
        ),
        "sensitivity_recovered_pair_count": sum(
            int(audit["sensitivity_recovered_pair_count"]) for audit in audits
        ),
        "sensitivity_grid_explicit_failure_count": sum(
            int(audit["sensitivity_grid_explicit_failure_count"]) for audit in audits
        ),
        "validated_grid_configurations": len(grid.VALIDATED_RT006_GRID),
        "full_state_yen_production_used": False,
        "parallel_workers": len(parts),
        "parallel_partition_semantics": "WHOLE_SOURCE_ANCHOR_GROUPS_NO_PAIR_SAMPLING_OR_OMISSION",
    }


def main() -> int:
    original = bounded.route_corpus
    bounded.route_corpus = parallel_route_corpus
    output_dir = grid.output_dir_from_argv()
    try:
        result = bounded.main()
        grid.rewrite_validation(output_dir)
        return result
    finally:
        bounded.route_corpus = original
