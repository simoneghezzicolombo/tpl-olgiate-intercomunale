"""Neutral batch interface for Phase 2 V3 alternative road corridors.

The library deliberately does not decide which routing terminals should exist,
which settlements should be served, which passenger stops should be used or
which network topology should win. Upstream supplies an explicit terminal table
and an explicit pair table. This module only materialises legal, loopless road
corridor alternatives for those requested pairs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping

import pandas as pd

from src.phase2_alternative_corridor_generator_v3 import (
    CorridorPath,
    generate_bounded_alternative_corridors,
)


@dataclass(frozen=True)
class ExplorationSetting:
    setting_id: str
    penalty_increment: float
    max_runtime_factor: float
    max_overlap: float
    max_alternatives: int = 3
    max_generation_rounds: int = 10


def corridor_id(pair_id: str, edge_ids: tuple[str, ...]) -> str:
    payload = (str(pair_id) + "|" + ";".join(edge_ids)).encode("utf-8")
    return "CORRIDOR_" + hashlib.sha256(payload).hexdigest()[:16].upper()


def validate_terminal_and_pair_tables(
    terminals: pd.DataFrame,
    pairs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_terminals = {
        "routing_terminal_id",
        "graph_node_id",
        "terminal_source_kind",
        "terminal_evidence_status",
    }
    required_pairs = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    }
    missing_terminals = required_terminals - set(terminals.columns)
    missing_pairs = required_pairs - set(pairs.columns)
    if missing_terminals:
        raise ValueError(f"Terminal table missing columns: {sorted(missing_terminals)}")
    if missing_pairs:
        raise ValueError(f"Pair table missing columns: {sorted(missing_pairs)}")

    terminal_frame = terminals.copy().fillna("")
    pair_frame = pairs.copy().fillna("")
    for col in required_terminals:
        terminal_frame[col] = terminal_frame[col].astype(str).str.strip()
    for col in required_pairs:
        pair_frame[col] = pair_frame[col].astype(str).str.strip()

    if terminal_frame["routing_terminal_id"].eq("").any():
        raise ValueError("Blank routing_terminal_id")
    if terminal_frame["graph_node_id"].eq("").any():
        raise ValueError("Blank graph_node_id")
    if terminal_frame["routing_terminal_id"].duplicated().any():
        raise ValueError("routing_terminal_id must be unique")
    if pair_frame["pair_id"].eq("").any():
        raise ValueError("Blank pair_id")
    if pair_frame["pair_id"].duplicated().any():
        raise ValueError("pair_id must be unique")

    known = set(terminal_frame["routing_terminal_id"])
    unknown_sources = sorted(set(pair_frame["source_routing_terminal_id"]) - known)
    unknown_targets = sorted(set(pair_frame["target_routing_terminal_id"]) - known)
    if unknown_sources or unknown_targets:
        raise ValueError(
            f"Pair table references unknown terminals: sources={unknown_sources}, targets={unknown_targets}"
        )
    if pair_frame["source_routing_terminal_id"].eq(
        pair_frame["target_routing_terminal_id"]
    ).any():
        raise ValueError("Self-pairs are not allowed in corridor library input")

    return (
        terminal_frame.sort_values("routing_terminal_id", kind="mergesort").reset_index(drop=True),
        pair_frame.sort_values("pair_id", kind="mergesort").reset_index(drop=True),
    )


def validate_settings(settings: Iterable[ExplorationSetting]) -> tuple[ExplorationSetting, ...]:
    rows = tuple(settings)
    if not rows:
        raise ValueError("At least one exploration setting is required")
    ids = [str(setting.setting_id) for setting in rows]
    if any(not value.strip() for value in ids):
        raise ValueError("Blank setting_id")
    if len(ids) != len(set(ids)):
        raise ValueError("setting_id must be unique")
    for setting in rows:
        if setting.penalty_increment <= 0:
            raise ValueError("penalty_increment must be > 0")
        if setting.max_runtime_factor < 1:
            raise ValueError("max_runtime_factor must be >= 1")
        if not 0 <= setting.max_overlap <= 1:
            raise ValueError("max_overlap must be in [0,1]")
        if setting.max_alternatives < 1:
            raise ValueError("max_alternatives must be >= 1")
        if setting.max_generation_rounds < 0:
            raise ValueError("max_generation_rounds must be >= 0")
    return tuple(sorted(rows, key=lambda setting: setting.setting_id))


def _path_record(
    *,
    pair_id: str,
    source_terminal_id: str,
    target_terminal_id: str,
    path: CorridorPath,
) -> dict:
    cid = corridor_id(pair_id, path.edge_ids)
    return {
        "corridor_id": cid,
        "pair_id": pair_id,
        "source_routing_terminal_id": source_terminal_id,
        "target_routing_terminal_id": target_terminal_id,
        "source_graph_node_id": path.source,
        "target_graph_node_id": path.target,
        "path_edge_ids": ";".join(path.edge_ids),
        "path_node_ids": ";".join(path.node_ids),
        "running_minutes_model": path.running_minutes_model,
        "distance_m": path.distance_m,
        "runtime_factor_vs_gate_d_shortest": path.runtime_factor_vs_shortest,
        "provenance": path.provenance,
        "physical_node_loop": path.physical_node_loop,
        "admissible_for_corridor_pool": path.admissible_for_corridor_pool,
        "scope": "ROUTING_CORRIDOR_LIBRARY_NOT_NETWORK_OR_STOP_RECOMMENDATION",
    }


def generate_corridor_library(
    adjacency,
    rules,
    terminals: pd.DataFrame,
    pairs: pd.DataFrame,
    settings: Iterable[ExplorationSetting],
) -> dict[str, pd.DataFrame | dict]:
    """Generate a deduplicated union of admitted road corridors.

    The same path found under multiple technical settings is stored once in the
    library and separately represented in the appearance table. Appearance
    counts are descriptive search-stability metadata only.
    """
    terminal_frame, pair_frame = validate_terminal_and_pair_tables(terminals, pairs)
    setting_rows = validate_settings(settings)
    terminals_by_id = terminal_frame.set_index("routing_terminal_id", drop=False).to_dict("index")

    library: dict[tuple[str, str], dict] = {}
    appearance_rows: list[dict] = []
    pair_rows: list[dict] = []

    for pair in pair_frame.itertuples(index=False):
        pair_id = str(pair.pair_id)
        source_terminal_id = str(pair.source_routing_terminal_id)
        target_terminal_id = str(pair.target_routing_terminal_id)
        source = str(terminals_by_id[source_terminal_id]["graph_node_id"])
        target = str(terminals_by_id[target_terminal_id]["graph_node_id"])

        baseline_edges: tuple[str, ...] | None = None
        baseline_runtime: float | None = None
        baseline_distance: float | None = None
        baseline_loop: bool | None = None
        settings_with_any_admitted = 0
        settings_with_nonbaseline = 0

        for setting in setting_rows:
            result = generate_bounded_alternative_corridors(
                adjacency,
                rules,
                source,
                target,
                max_alternatives=setting.max_alternatives,
                max_generation_rounds=setting.max_generation_rounds,
                penalty_increment=setting.penalty_increment,
                max_runtime_factor=setting.max_runtime_factor,
                max_shared_runtime_fraction_allowed=setting.max_overlap,
            )
            baseline = result["baseline"]
            if baseline is None:
                continue

            if baseline_edges is None:
                baseline_edges = baseline.edge_ids
                baseline_runtime = baseline.running_minutes_model
                baseline_distance = baseline.distance_m
                baseline_loop = baseline.physical_node_loop
            else:
                if baseline.edge_ids != baseline_edges:
                    raise AssertionError(f"Gate-D baseline changed across settings for {pair_id}")
                if abs(baseline.running_minutes_model - float(baseline_runtime)) > 1e-9:
                    raise AssertionError(f"Gate-D baseline runtime changed across settings for {pair_id}")
                if abs(baseline.distance_m - float(baseline_distance)) > 1e-6:
                    raise AssertionError(f"Gate-D baseline distance changed across settings for {pair_id}")

            if result["corridors"]:
                settings_with_any_admitted += 1
            if any(path.provenance != "CERTIFIED_GATE_D_SHORTEST" for path in result["corridors"]):
                settings_with_nonbaseline += 1

            for rank, path in enumerate(result["corridors"], start=1):
                cid = corridor_id(pair_id, path.edge_ids)
                key = (pair_id, cid)
                if key not in library:
                    library[key] = {
                        **_path_record(
                            pair_id=pair_id,
                            source_terminal_id=source_terminal_id,
                            target_terminal_id=target_terminal_id,
                            path=path,
                        ),
                        "setting_ids": [],
                    }
                library[key]["setting_ids"].append(setting.setting_id)
                appearance_rows.append(
                    {
                        "pair_id": pair_id,
                        "corridor_id": cid,
                        "setting_id": setting.setting_id,
                        "rank_by_true_runtime_within_setting": rank,
                        "provenance": path.provenance,
                        "generation_round": path.generation_round,
                        "running_minutes_model": path.running_minutes_model,
                        "distance_m": path.distance_m,
                        "runtime_factor_vs_gate_d_shortest": path.runtime_factor_vs_shortest,
                        "max_shared_runtime_fraction_at_admission": path.max_shared_runtime_fraction,
                        "appearance_semantics": "DESCRIPTIVE_SEARCH_STABILITY_ONLY_NOT_SCORE_NOT_PROBABILITY",
                    }
                )

        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_routing_terminal_id": source_terminal_id,
                "target_routing_terminal_id": target_terminal_id,
                "source_graph_node_id": source,
                "target_graph_node_id": target,
                "gate_d_route_found": baseline_edges is not None,
                "gate_d_baseline_edge_ids": ";".join(baseline_edges or ()),
                "gate_d_baseline_runtime_min": baseline_runtime,
                "gate_d_baseline_distance_m": baseline_distance,
                "gate_d_baseline_physical_node_loop": baseline_loop,
                "settings_total": len(setting_rows),
                "settings_with_any_admitted_corridor": settings_with_any_admitted,
                "settings_with_nonbaseline_alternative": settings_with_nonbaseline,
                "pair_scope": "REQUESTED_ROUTING_PAIR_NOT_NETWORK_TOPOLOGY_DECISION",
            }
        )

    library_rows = []
    for key in sorted(library):
        row = dict(library[key])
        setting_ids = sorted(set(row.pop("setting_ids")))
        row["setting_appearance_count"] = len(setting_ids)
        row["setting_appearance_fraction"] = len(setting_ids) / len(setting_rows)
        row["setting_ids"] = "|".join(setting_ids)
        row["appearance_semantics"] = "DESCRIPTIVE_SEARCH_STABILITY_ONLY_NOT_SCORE_NOT_PROBABILITY"
        row["union_semantics"] = "DEDUPLICATED_UNION_ACROSS_TECHNICAL_SETTINGS_NOT_RANKED"
        library_rows.append(row)

    library_df = pd.DataFrame(library_rows)
    appearance_df = pd.DataFrame(appearance_rows)
    pair_df = pd.DataFrame(pair_rows)
    metadata = {
        "scope": "ROUTING_CORRIDOR_LIBRARY_INTERFACE_NOT_NETWORK_SELECTION",
        "terminal_semantics": "UPSTREAM_ROUTING_TERMINALS_NOT_ASSUMED_TO_BE_PASSENGER_STOPS",
        "pair_semantics": "UPSTREAM_REQUESTED_PAIRS_NOT_AUTOMATIC_TOPOLOGY",
        "setting_frequency_semantics": "DESCRIPTIVE_SEARCH_STABILITY_ONLY_NOT_SCORE_NOT_PROBABILITY",
        "union_semantics": "DEDUPLICATED_UNION_ACROSS_TECHNICAL_SETTINGS_NOT_RANKED",
        "network_winner_authorized": False,
        "passenger_stop_pattern_authorized": False,
        "automatic_pair_selection_performed": False,
        "terminal_count": len(terminal_frame),
        "pair_count": len(pair_frame),
        "setting_count": len(setting_rows),
        "corridor_count": len(library_df),
    }
    return {
        "corridors": library_df,
        "appearances": appearance_df,
        "pairs": pair_df,
        "metadata": metadata,
    }
