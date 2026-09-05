#!/usr/bin/env python3
"""Controlled RT-010 audit for complete directed-pair coverage semantics."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.phase2_complete_directed_pairs_v3 import (
    audit_pair_execution_completeness,
    build_complete_directed_pair_manifest,
)

OUT = Path(
    "outputs/phase2/complete_directed_pairs_v3/"
    "complete_directed_pairs_v3_validation.json"
)


def main() -> None:
    terminals = pd.DataFrame({"routing_terminal_id": ["E", "C", "A", "D", "B"]})
    built = build_complete_directed_pair_manifest(terminals, max_directed_pairs=100)
    manifest = built["manifest"]
    if built["status"] != "PASS_COMPLETE_DIRECTED_PAIR_MANIFEST":
        raise SystemExit(f"unexpected manifest status: {built['status']}")
    if len(manifest) != 20 or built["unordered_pair_count"] != 10:
        raise SystemExit("N=5 complete directed-pair count failed")

    complete_results = manifest[[
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ]].copy()
    complete_results["gate_d_route_found"] = [index % 3 != 0 for index in range(len(complete_results))]
    execution = audit_pair_execution_completeness(manifest, complete_results)
    if execution["status"] != "PASS_COMPLETE_PAIR_EXECUTION":
        raise SystemExit(f"complete execution should pass: {execution}")

    missing_results = complete_results.iloc[:-1].copy()
    missing_audit = audit_pair_execution_completeness(manifest, missing_results)
    if missing_audit["complete"] or len(missing_audit["missing_result_pair_ids"]) != 1:
        raise SystemExit("missing-result fail-closed audit failed")

    capped = build_complete_directed_pair_manifest(terminals, max_directed_pairs=19)
    if capped["complete"] or not capped["manifest"].empty:
        raise SystemExit("pair-manifest cap did not fail closed")

    payload = {
        "status": "PASS_RT010_COMPLETE_DIRECTED_PAIR_COVERAGE_V3",
        "issue": "RT-010",
        "fixture_semantics": "CONTROLLED_ABSTRACT_FIXTURE_NOT_TERRITORIAL_DATA",
        "terminal_count": built["terminal_count"],
        "directed_pair_count": built["directed_pair_count"],
        "unordered_pair_count": built["unordered_pair_count"],
        "expected_formula": "N_TIMES_N_MINUS_1",
        "complete_execution_pass": True,
        "missing_output_is_incomplete_not_no_route": True,
        "cap_fail_closed_without_partial_manifest": True,
        "pair_selection_filter": False,
        "random_search": False,
        "weighted_composite_score": False,
        "territorial_candidate_claim": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
