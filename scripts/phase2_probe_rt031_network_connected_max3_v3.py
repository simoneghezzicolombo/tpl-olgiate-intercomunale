#!/usr/bin/env python3
"""Deterministic domain probe for a three-movement hub-connected network."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_network_connected_portfolios_v3 import (
    enumerate_network_connected_portfolios,
)

HUB_POOL_SHA256 = "b86b27f791b0b36f0e30997a96388c5763f46822411ea990bfeed3351cd8a65c"
GENERIC_POOL_SHA256 = "273109c45f899cb3c3170bd272a2d8e6aa00d4cb4e3a747caf3205e786cd5703"
HUB = "FROZEN::L00407"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(payload) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def load_pool(path: Path, expected_sha: str, expected_root):
    if sha256(path) != expected_sha:
        raise ValueError("pinned physical-pool lineage drift")
    pool = json.loads(path.read_text(encoding="utf-8"))
    if (pool.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or pool.get("status") != "RESOURCE_LIMIT_INCOMPLETE"
            or pool.get("required_root_stop_id") != expected_root):
        raise ValueError("unexpected physical-pool contract boundary")
    return pool


def main(args):
    hub_pool = load_pool(args.hub_pool, HUB_POOL_SHA256, HUB)
    generic_pool = load_pool(args.generic_pool, GENERIC_POOL_SHA256, None)
    candidates = []
    for prefix, pool in (("hub", hub_pool), ("generic", generic_pool)):
        for raw in pool["candidates"]:
            row = dict(raw)
            row["candidate_id"] = prefix + "::" + str(raw["stop_set_id"])
            candidates.append(row)

    result = enumerate_network_connected_portfolios(
        candidates, hub_stop_id=HUB, max_movements=3,
        materialize_portfolios=False, pareto_prune_final_states=True)
    if result["portfolios"] or not result["portfolio_materialization_skipped"]:
        raise AssertionError("diagnostic run unexpectedly materialized portfolios")
    if not result[
            "within_supplied_pool_pareto_complete_for_monotone_stop_union_objectives"]:
        raise AssertionError("safe-pruning Pareto-completeness contract failed")
    if not result["final_pareto_preprune_applied"]:
        raise AssertionError("final Pareto pre-prune was not applied")
    before = result["final_state_count_before_pareto_preprune"]
    after = result["final_state_count_after_pareto_preprune"]
    pruned = result["objective_dominated_final_state_count_pruned"]
    if before is None or after is None or before - after != pruned:
        raise AssertionError("final-state pre-prune accounting mismatch")

    payload = {
        "contract": "RT031_NETWORK_CONNECTED_MAX3_DOMAIN_PROBE_V3",
        "status": "PASS_DETERMINISTIC_DOMAIN_AND_FINAL_PARETO_PREPRUNE_PROBE",
        **{
            key: value for key, value in result.items()
            if key not in {"portfolios", "compact_final_states", "stop_universe"}
        },
        "purpose": (
            "COMPUTATIONAL_TRACTABILITY_AND_EXACT_FINAL_PREPRUNE_COUNTS_ONLY_NOT_ACCESS_FRONTIER_OR_SERVICE_SELECTION"),
        "access_metrics_computed": False,
        "service_surface_computed": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            "hub_physical_pool": HUB_POOL_SHA256,
            "generic_physical_pool": GENERIC_POOL_SHA256,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(payload))
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub-pool", type=Path, required=True)
    parser.add_argument("--generic-pool", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
