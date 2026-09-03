#!/usr/bin/env python3
"""Materialise a family-balanced real Phase 2 structural catalog.

Inputs are the validated routing-anchor universe and directed reduced path
matrix. An anchor is structurally eligible only when both hub→anchor and
anchor→hub directed paths exist. No geographic ranking is applied.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_run_structural_search import (
    load_anchor_universe,
    load_reduced_path_matrix,
    sha256_path,
    write_catalog,
)
from src.phase2_balanced_structural_search import generate_balanced_structural_scenarios


def hub_bidirectional_anchor_filter(*, hub: str, anchors: list[str], matrix) -> tuple[list[str], list[str]]:
    if hub not in anchors:
        raise ValueError(f"Hub {hub!r} is not in the enabled routing-anchor universe")
    kept = [hub]
    excluded: list[str] = []
    for anchor in sorted(a for a in anchors if a != hub):
        if matrix.has_leg(hub, anchor) and matrix.has_leg(anchor, hub):
            kept.append(anchor)
        else:
            excluded.append(anchor)
    if len(kept) < 4:
        raise ValueError("Fewer than three non-hub anchors are bidirectionally reachable from hub")
    return kept, excluded


def write_balanced_validation(
    path: Path,
    *,
    hub: str,
    anchor_path: Path,
    matrix_path: Path,
    output_path: Path,
    source_anchors: list[str],
    structural_anchors: list[str],
    excluded_anchors: list[str],
    result,
    max_scenarios: int,
    max_loop_intermediate_anchors: int,
) -> None:
    payload = {
        "status": "PASS",
        "contract": "PHASE2_BALANCED_STRUCTURAL_SEARCH_V1",
        "hub_anchor_id": hub,
        "source_routing_anchor_count": len(source_anchors),
        "hub_bidirectional_structural_anchor_count": len(structural_anchors),
        "hub_bidirectional_nonhub_anchor_count": len(structural_anchors) - 1,
        "excluded_non_bidirectional_anchor_count": len(excluded_anchors),
        "excluded_non_bidirectional_anchor_ids": excluded_anchors,
        "max_scenarios": max_scenarios,
        "max_loop_intermediate_anchors": max_loop_intermediate_anchors,
        "allocation_rule": result.allocation_rule,
        "valid_single_radial_count": result.valid_radial_count,
        "family_targets": dict(result.family_targets),
        "family_counts": dict(result.family_counts),
        "exhausted_families": list(result.exhausted_families),
        "generated_scenario_count": len(result.scenarios),
        "deterministic": True,
        "uses_live_osm": False,
        "uses_random_generation": False,
        "uses_legacy_candidate_routes": False,
        "uses_topology_preference_score": False,
        "search_allocation_is_decision_weight": False,
        "lineage": {
            "routing_anchor_universe": str(anchor_path),
            "routing_anchor_universe_sha256": sha256_path(anchor_path),
            "reduced_path_matrix": str(matrix_path),
            "reduced_path_matrix_sha256": sha256_path(matrix_path),
            "scenario_catalog": str(output_path),
            "scenario_catalog_sha256": sha256_path(output_path),
        },
        "epistemic_note": (
            "Equal-family allocation controls structural search coverage only. "
            "It does not express a preference among topology families."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub", required=True)
    parser.add_argument("--anchors", required=True, type=Path)
    parser.add_argument("--path-matrix", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--max-scenarios", required=True, type=int)
    parser.add_argument("--max-loop-intermediate-anchors", required=True, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_anchors = load_anchor_universe(args.anchors)
    matrix = load_reduced_path_matrix(args.path_matrix)
    structural_anchors, excluded = hub_bidirectional_anchor_filter(
        hub=args.hub,
        anchors=source_anchors,
        matrix=matrix,
    )
    result = generate_balanced_structural_scenarios(
        hub=args.hub,
        anchors=structural_anchors,
        matrix=matrix,
        max_scenarios=args.max_scenarios,
        max_loop_intermediate_anchors=args.max_loop_intermediate_anchors,
    )
    if not result.scenarios:
        raise RuntimeError("Balanced structural search generated no scenarios")
    write_catalog(args.output, result.scenarios)
    write_balanced_validation(
        args.validation,
        hub=args.hub,
        anchor_path=args.anchors,
        matrix_path=args.path_matrix,
        output_path=args.output,
        source_anchors=source_anchors,
        structural_anchors=structural_anchors,
        excluded_anchors=excluded,
        result=result,
        max_scenarios=args.max_scenarios,
        max_loop_intermediate_anchors=args.max_loop_intermediate_anchors,
    )
    print(
        f"generated {len(result.scenarios)} family-balanced scenarios from "
        f"{len(structural_anchors)} hub-bidirectional anchors -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
