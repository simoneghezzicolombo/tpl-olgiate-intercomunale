#!/usr/bin/env python3
"""Canonicalize one completed RT-021 RT-006 corpus for RT-022.

The RT-021 builders deliberately use ``STOP_PLACE::`` technical query IDs
internally. RT-010/RT-022 use the frozen raw stop-place IDs. This finalizer is
identity-only: it does not change paths, costs, admissibility, routing status,
turn rules, stop attachments, or the RT-006 alternative-generation contract.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import pandas as pd

from src import phase2_rt021_territorial_corridor_corpus_v3 as core
from src.phase2_complete_directed_pairs_v3 import (
    audit_pair_execution_completeness,
    build_complete_directed_pair_manifest,
    directed_pair_id,
)

PREFIX = "STOP_PLACE::"


def strip_internal_terminal(value: object) -> str:
    text = str(value).strip()
    if not text.startswith(PREFIX) or len(text) <= len(PREFIX):
        raise ValueError(f"unexpected internal RT-021 terminal identity: {text!r}")
    return text[len(PREFIX):]


def canonicalize_frames(
    pair_status: pd.DataFrame,
    corridors: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = pair_status.copy()
    c = corridors.copy()
    required_pair = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "corridor_count",
    }
    required_corridor = {
        "corridor_id",
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "path_edge_ids",
    }
    if missing := sorted(required_pair - set(p.columns)):
        raise ValueError(f"pair status missing columns: {missing}")
    if missing := sorted(required_corridor - set(c.columns)):
        raise ValueError(f"corridor corpus missing columns: {missing}")

    for frame in (p, c):
        frame["source_routing_terminal_id"] = frame["source_routing_terminal_id"].map(
            strip_internal_terminal
        )
        frame["target_routing_terminal_id"] = frame["target_routing_terminal_id"].map(
            strip_internal_terminal
        )
        frame["pair_id"] = [
            directed_pair_id(source, target)
            for source, target in zip(
                frame["source_routing_terminal_id"],
                frame["target_routing_terminal_id"],
            )
        ]

    # Gate-D/RT-017 road reachability is distinct from RT-006 corridor
    # admissibility. All 35x34 technical pairs were certified reachable by
    # RT-017; a pair may still have an explicit RT-006 no-loopless-corridor
    # reason after the complete validated sensitivity grid.
    p["gate_d_route_found"] = True

    c["corridor_id"] = [
        core.corridor_id(
            pair_id,
            [part for part in str(edge_ids).split(";") if part],
        )
        for pair_id, edge_ids in zip(c["pair_id"], c["path_edge_ids"])
    ]
    c["admissible_for_corridor_pool"] = True

    if p["pair_id"].duplicated().any():
        raise AssertionError("canonical pair IDs are not unique")
    if c["corridor_id"].duplicated().any():
        raise AssertionError("canonical corridor IDs are not unique")
    return p, c


def canonical_manifest_from_attachments(attachments: pd.DataFrame) -> pd.DataFrame:
    required = {"stop_place_id", "service_class"}
    if missing := sorted(required - set(attachments.columns)):
        raise ValueError(f"stop attachments missing columns: {missing}")
    conventional = attachments[
        attachments["service_class"].astype(str).eq("CONVENTIONAL_TPL")
    ].copy()
    if len(conventional) != 35:
        raise AssertionError(f"expected 35 conventional stop places, got {len(conventional)}")
    if conventional["stop_place_id"].astype(str).duplicated().any():
        raise AssertionError("conventional stop_place_id values are not unique")
    anchors = pd.DataFrame(
        {"routing_terminal_id": conventional["stop_place_id"].astype(str)}
    )
    result = build_complete_directed_pair_manifest(anchors, max_directed_pairs=5000)
    if not result["complete"]:
        raise AssertionError(result)
    manifest = result["manifest"].copy()
    if len(manifest) != 1190:
        raise AssertionError(f"canonical RT-010 manifest has {len(manifest)} rows")
    return manifest


def finalize(output_dir: Path) -> dict:
    out = Path(output_dir)
    paths = {
        "attachments": out / "rt021_stop_attachments_v3.csv",
        "manifest": out / "rt021_complete_directed_pair_manifest_v3.csv",
        "pairs": out / "rt021_pair_execution_status_v3.csv",
        "corridors": out / "rt021_corridor_corpus_v3.csv.gz",
        "validation": out / "rt021_validation_v3.json",
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    attachments = pd.read_csv(paths["attachments"]).fillna("")
    pair_status = pd.read_csv(paths["pairs"]).fillna("")
    with gzip.open(paths["corridors"], "rt", encoding="utf-8") as handle:
        corridors = pd.read_csv(handle).fillna("")
    validation = json.loads(paths["validation"].read_text(encoding="utf-8"))
    if str(validation.get("status", "")) != "PASS_RT021_FROZEN_TERRITORIAL_CORRIDOR_CORPUS_V3":
        raise AssertionError("canonicalization requires a PASS RT-021 corpus")

    manifest = canonical_manifest_from_attachments(attachments)
    pair_status, corridors = canonicalize_frames(pair_status, corridors)

    execution = audit_pair_execution_completeness(manifest, pair_status)
    if not execution["complete"]:
        raise AssertionError(execution)
    if len(pair_status) != 1190 or pair_status["pair_id"].nunique() != 1190:
        raise AssertionError("canonical pair execution must contain exactly 1,190 rows")

    counts = pd.to_numeric(pair_status["corridor_count"], errors="raise").astype(int)
    if "failure_reason" not in pair_status.columns:
        pair_status["failure_reason"] = ""
    explicit_failure = pair_status["failure_reason"].astype(str).str.strip().ne("")
    if not ((counts > 0) | explicit_failure).all():
        raise AssertionError("pair vanished without corridor or explicit failure")
    corridor_pair_ids = set(corridors["pair_id"].astype(str))
    expected_corridor_pairs = set(pair_status.loc[counts.gt(0), "pair_id"].astype(str))
    if corridor_pair_ids != expected_corridor_pairs:
        raise AssertionError("canonical corridor pair coverage differs from positive pair statuses")

    manifest_sha = core.write_csv(
        paths["manifest"],
        manifest,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
    )
    pair_sha = core.write_csv(
        paths["pairs"],
        pair_status,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
    )
    corpus_bytes = core.canonical_csv_bytes(
        corridors,
        sort_by=["pair_id", "corridor_rank_by_running_time", "corridor_id"],
    )
    corpus_uncompressed_sha = core.sha256_bytes(corpus_bytes)
    corpus_gzip_sha = core.write_deterministic_gzip(paths["corridors"], corpus_bytes)

    validation["pair_universe"]["pair_manifest_sha256"] = manifest_sha
    validation["pair_universe"]["pair_execution_status_sha256"] = pair_sha
    validation["pair_universe"]["explicit_failure_count"] = int(explicit_failure.sum())
    validation["corridor_corpus"]["corridor_count"] = int(len(corridors))
    validation["corridor_corpus"]["corridor_corpus_uncompressed_sha256"] = corpus_uncompressed_sha
    validation["corridor_corpus"]["corridor_corpus_gzip_sha256"] = corpus_gzip_sha
    validation["canonical_downstream_handoff"] = {
        "status": "PASS_CANONICAL_RT010_RT022_IDENTITY_HANDOFF",
        "identity_only": True,
        "raw_stop_place_terminal_ids": True,
        "canonical_rt010_pair_ids": True,
        "gate_d_route_found_explicit": True,
        "admissible_for_corridor_pool_explicit": True,
        "path_geometry_or_cost_changed": False,
        "routing_or_rt006_semantics_changed": False,
    }
    # RT-022 optional top-level digest checks use a different dataframe-level
    # canonicalization. Do not leave stale file-level aliases at top level.
    for key in (
        "stop_attachment_sha256",
        "attachment_sha256",
        "pair_manifest_sha256",
        "corridor_corpus_sha256",
        "corridors_sha256",
    ):
        validation.pop(key, None)
    paths["validation"].write_bytes(core.canonical_json_bytes(validation))
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    validation = finalize(args.output_dir)
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
