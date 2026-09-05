#!/usr/bin/env python3
"""Execute RT-022 against one frozen real RT-021 bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.phase2_territorial_structural_search_v3 import run_rt022_orchestrator


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attachments", required=True, type=Path)
    parser.add_argument("--pair-manifest", required=True, type=Path)
    parser.add_argument("--pair-results", required=True, type=Path)
    parser.add_argument("--corridors", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/phase2/rt022_territorial_structural_search_v3"),
    )
    parser.add_argument("--min-edges", type=int, default=1)
    parser.add_argument("--max-edges", type=int)
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--max-structures", type=int, default=20_000)
    return parser.parse_args()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n")


def main() -> int:
    args = _parse_args()
    attachments = pd.read_csv(args.attachments)
    pair_manifest = pd.read_csv(args.pair_manifest)
    pair_results = pd.read_csv(args.pair_results)
    corridors = pd.read_csv(args.corridors)
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))

    result = run_rt022_orchestrator(
        attachments,
        pair_manifest,
        pair_results,
        corridors,
        metadata,
        require_real_rt021_pass=True,
        min_edges=args.min_edges,
        max_edges=args.max_edges,
        max_states=args.max_states,
        max_structures=args.max_structures,
    )

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "stop_attachments.csv": result["attachments"],
        "technical_pair_query_anchors.csv": result["anchors"],
        "directed_pair_manifest.csv": result["pair_manifest"],
        "pair_results.csv": result["pair_results"],
        "corridor_evidence.csv": result["corridors"],
        "corridor_stop_occurrences.csv": result["occurrences"],
        "elementary_corridor_classification.csv": result["classification"],
        "directional_elementary_availability.csv": result["directional_availability"],
        "elementary_corridors_for_reciprocity.csv": result[
            "elementary_corridors_for_reciprocity"
        ],
        "rt009_pair_audit.csv": result["rt009_pair_audit"],
        "reciprocal_structural_links.csv": result["structural_links"],
        "eligible_structural_links.csv": result["eligible_structural_links"],
        "topology_neutral_structure_universe.csv": result["structures"],
    }
    for filename, frame in outputs.items():
        _write_csv(frame, out / filename)

    audit = {
        "status": result["status"],
        "complete": bool(result["complete"]),
        "graph_epoch_id": result["graph_epoch_id"],
        "counts": {
            "stop_attachments": int(len(result["attachments"])),
            "technical_pair_query_anchors": int(len(result["anchors"])),
            "directed_pair_requests": int(len(result["pair_manifest"])),
            "corridor_alternatives": int(len(result["corridors"])),
            "stop_occurrences": int(len(result["occurrences"])),
            "reciprocal_elementary_structural_links": int(len(result["structural_links"])),
            "topology_neutral_structures": int(len(result["structures"])),
        },
        "digests": result["digests"],
        "frontier_metadata": result["frontier_metadata"],
        "guards": {
            "service_terminal_selected": False,
            "topology_prior_used": False,
            "primary_runner_up_selected": False,
            "municipality_used_as_routing_filter": False,
            "partial_cap_hit_pool_usable": False,
        },
    }
    (out / "rt022_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
