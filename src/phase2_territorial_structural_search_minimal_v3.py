"""Scoped RT-022 runner for exact minimum-edge topology-neutral backbones."""
from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from src import phase2_territorial_structural_search_v3 as base
from src.phase2_minimum_policy_backbone_v3 import (
    enumerate_exact_minimum_policy_backbones,
)
from src.phase2_territorial_structural_search_rt006_compat_v3 import (
    run_rt022_orchestrator_rt006_compatible,
)

REAL_PASS_STATUS = "PASS_EXACT_MINIMUM_TOPOLOGY_NEUTRAL_TERRITORIAL_BACKBONE_UNIVERSE"
FIXTURE_PASS_STATUS = "PASS_CONTROLLED_EXACT_MINIMUM_BACKBONE_EXECUTION"
SEARCH_SCOPE = "EXACT_MINIMUM_POLICY_BACKBONES_ONLY"


def run_rt022_exact_minimum_backbones(
    attachments: pd.DataFrame,
    pair_manifest: pd.DataFrame,
    pair_results: pd.DataFrame,
    corridors: pd.DataFrame,
    metadata: Mapping[str, object] | None = None,
    *,
    require_real_rt021_pass: bool = False,
    required_policy_groups: Sequence[str] = base.CORE_POLICY_GROUPS,
) -> dict[str, object]:
    """Run the frozen RT-022 pipeline but replace unbounded RT-008 expansion with an exact minimal scope."""

    def exact_adapter(
        links,
        *,
        required_terminal_ids=(),
        required_policy_groups=(),
        terminal_policy_groups=None,
        min_edges=1,
        max_edges=None,
        max_states=100_000,
        max_structures=20_000,
    ):
        if tuple(required_terminal_ids):
            raise ValueError("exact minimum-policy RT-022 scope does not accept required terminal IDs")
        result = enumerate_exact_minimum_policy_backbones(
            links,
            required_policy_groups=required_policy_groups,
            terminal_policy_groups=terminal_policy_groups or {},
        )
        derived = int(result["derived_minimum_edge_count"])
        if int(min_edges) > derived:
            raise ValueError("min_edges exceeds the logically derived minimum-backbone edge count")
        if max_edges is not None and int(max_edges) < derived:
            raise ValueError("max_edges is below the logically derived minimum-backbone edge count")
        return result

    previous = base.enumerate_connected_structures_frontier
    base.enumerate_connected_structures_frontier = exact_adapter
    try:
        result = run_rt022_orchestrator_rt006_compatible(
            attachments,
            pair_manifest,
            pair_results,
            corridors,
            metadata,
            require_real_rt021_pass=require_real_rt021_pass,
            required_policy_groups=required_policy_groups,
        )
    finally:
        base.enumerate_connected_structures_frontier = previous

    if result.get("complete"):
        result["status"] = REAL_PASS_STATUS if require_real_rt021_pass else FIXTURE_PASS_STATUS
        result["frontier_metadata"]["search_scope"] = SEARCH_SCOPE
        result["frontier_metadata"]["larger_edge_counts_enumerated"] = False
        result["frontier_metadata"]["larger_structures_may_be_staged_later"] = True
        result["frontier_metadata"]["territorial_winner_selected"] = False
    return result
