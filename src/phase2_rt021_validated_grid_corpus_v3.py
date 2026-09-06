from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import pandas as pd

from src import phase2_rt021_bounded_corpus_v3 as bounded
from src import phase2_rt021_territorial_corridor_corpus_v3 as core
from src.phase2_alternative_corridor_generator_v3 import (
    edge_lookup,
    has_physical_node_loop,
    materialize_path,
)
from src.phase2_complete_directed_pairs_v3 import audit_pair_execution_completeness
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index

# Exact RT-006 sensitivity grid certified in Issue #22 / run 33964236575.
# No configuration is selected or weighted. For a pair whose default RT-006
# pool is empty, the fallback object is the exact-edge-sequence UNION across
# this complete technical grid.
VALIDATED_RT006_GRID = tuple(
    {
        "config_id": f"CFG_{index:02d}",
        "penalty_increment": penalty,
        "max_runtime_factor": runtime_factor,
        "max_overlap": overlap,
    }
    for index, (penalty, runtime_factor, overlap) in enumerate(
        (
            (0.10, 1.25, 0.75),
            (0.10, 1.25, 0.90),
            (0.10, 1.50, 0.75),
            (0.10, 1.50, 0.90),
            (0.20, 1.25, 0.75),
            (0.20, 1.25, 0.90),
            (0.20, 1.50, 0.75),
            (0.20, 1.50, 0.90),
            (0.35, 1.25, 0.75),
            (0.35, 1.25, 0.90),
            (0.35, 1.50, 0.75),
            (0.35, 1.50, 0.90),
        ),
        start=1,
    )
)

DEFAULT_GRID_KEY = (
    bounded.RT006_PENALTY_INCREMENT,
    bounded.RT006_MAX_RUNTIME_FACTOR,
    bounded.RT006_MAX_OVERLAP,
)
EXPLICIT_GRID_FAILURE_REASON = (
    "NO_PHYSICAL_LOOPLESS_CORRIDOR_ADMITTED_WITHIN_VALIDATED_RT006_PARAMETER_GRID"
)
SENSITIVITY_PROVENANCE = "RT006_VALIDATED_SENSITIVITY_UNION"


def validated_grid_signature() -> list[dict]:
    return [dict(config) for config in VALIDATED_RT006_GRID]


def sensitivity_union_from_frozen_baseline(
    adjacency,
    rule_index,
    lookup,
    source,
    target,
    baseline_edge_ids,
    *,
    default_result: dict | None = None,
) -> dict:
    """Return the unranked exact-path union across the certified RT-006 grid.

    Appearance frequency is deliberately not retained as a score. If one exact
    edge sequence appears under multiple configurations, one deterministic
    representative is kept solely to materialise that path once.
    """
    representatives: dict[tuple[str, ...], dict] = {}
    configuration_ids_by_path: dict[tuple[str, ...], list[str]] = {}
    paths_examined = 0
    max_generation_round = 0

    for config in VALIDATED_RT006_GRID:
        key = (
            float(config["penalty_increment"]),
            float(config["max_runtime_factor"]),
            float(config["max_overlap"]),
        )
        if default_result is not None and key == DEFAULT_GRID_KEY:
            result = default_result
        else:
            result = bounded.generate_bounded_from_frozen_baseline(
                adjacency,
                rule_index,
                lookup,
                source,
                target,
                baseline_edge_ids,
                max_alternatives=bounded.RT006_MAX_ALTERNATIVES,
                max_generation_rounds=bounded.RT006_MAX_GENERATION_ROUNDS,
                penalty_increment=float(config["penalty_increment"]),
                max_runtime_factor=float(config["max_runtime_factor"]),
                max_overlap=float(config["max_overlap"]),
            )
        audit = list(result["generation_audit"])
        paths_examined += len(audit)
        if audit:
            max_generation_round = max(
                max_generation_round,
                max(int(path.get("generation_round", 0)) for path in audit),
            )
        for path in result["corridors"]:
            edge_key = tuple(str(value) for value in path["edge_ids"])
            configuration_ids_by_path.setdefault(edge_key, []).append(str(config["config_id"]))
            candidate = dict(path)
            candidate["provenance"] = SENSITIVITY_PROVENANCE
            candidate["sensitivity_representative_config_id"] = str(config["config_id"])
            previous = representatives.get(edge_key)
            if previous is None or str(config["config_id"]) < str(
                previous["sensitivity_representative_config_id"]
            ):
                representatives[edge_key] = candidate

    ordered = sorted(
        representatives.values(),
        key=lambda path: (
            float(path["running_minutes_model"]),
            float(path["distance_m"]),
            tuple(str(value) for value in path["edge_ids"]),
        ),
    )
    return {
        "corridors": ordered,
        "paths_examined": paths_examined,
        "max_generation_round": max_generation_round,
        "unique_edge_sequences": len(ordered),
        "configuration_count": len(VALIDATED_RT006_GRID),
        "configuration_ids_by_path": {
            ";".join(edge_ids): sorted(config_ids)
            for edge_ids, config_ids in sorted(configuration_ids_by_path.items())
        },
        "union_contract": (
            "UNION_ACROSS_TECHNICAL_EXPLORATION_SETTINGS_NOT_FREQUENCY_WEIGHTED_NOT_RANKED"
        ),
    }


def route_corpus(manifest, anchors, edges, rules, graph_nodes, reference_pairs, *, epoch_id):
    terminal_to_stop = dict(
        zip(anchors["routing_terminal_id"].astype(str), anchors["stop_place_id"].astype(str))
    )
    terminal_to_node = dict(
        zip(anchors["routing_terminal_id"].astype(str), anchors["graph_node_id"].astype(str))
    )
    node_xy = {
        str(row.node_id): (float(row.x), float(row.y))
        for row in graph_nodes[["node_id", "x", "y"]].itertuples(index=False)
    }
    references = core.rt017_reference_lookup(reference_pairs)
    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    lookup = edge_lookup(adjacency)

    corridor_rows = []
    pair_rows = []
    sensitivity_fallback_pair_count = 0
    sensitivity_recovered_pair_count = 0
    sensitivity_grid_explicit_failure_count = 0
    generation_paths_examined_total = 0

    for pair in manifest.itertuples(index=False):
        pair_id = str(pair.pair_id)
        source_terminal = str(pair.source_routing_terminal_id)
        target_terminal = str(pair.target_routing_terminal_id)
        source_stop = terminal_to_stop[source_terminal]
        target_stop = terminal_to_stop[target_terminal]
        source_node = terminal_to_node[source_terminal]
        target_node = terminal_to_node[target_terminal]
        if source_node == target_node:
            raise AssertionError(f"distinct anchors collide on graph node {source_node}")

        ref = references.get((source_stop, target_stop))
        if ref is None:
            raise AssertionError(f"missing RT-017 reference {source_stop}->{target_stop}")
        if str(ref["route_found"]).strip().lower() not in {"true", "1"}:
            raise AssertionError(f"RT-017 unexpectedly marks pair unreachable: {source_stop}->{target_stop}")
        if str(ref["source_graph_node_id"]) != source_node or str(ref["target_graph_node_id"]) != target_node:
            raise AssertionError(f"RT-018 rebind drifted from RT-017 for {source_stop}->{target_stop}")

        reference_edges = [value for value in str(ref["path_edge_ids"]).split(";") if value]
        legal, reason = bounded.validate_turn_legal_edge_sequence(
            source_node, target_node, reference_edges, lookup, rule_index
        )
        if not legal:
            raise AssertionError(f"RT-017 path lost turn legality {source_stop}->{target_stop}: {reason}")
        reference_nodes, reference_runtime, reference_distance = materialize_path(
            source_node, reference_edges, lookup
        )
        runtime_delta = reference_runtime - float(ref["running_minutes_model"])
        distance_delta = reference_distance - float(ref["distance_m"])
        if abs(runtime_delta) > 1e-9 or abs(distance_delta) > 1e-6:
            raise AssertionError(f"RT-017 frozen path metric drift for {source_stop}->{target_stop}")
        reference_loopless = not has_physical_node_loop(reference_nodes)

        default_result = bounded.generate_bounded_from_frozen_baseline(
            adjacency, rule_index, lookup, source_node, target_node, reference_edges
        )
        paths = list(default_result["corridors"])
        generation_paths_examined = len(default_result["generation_audit"])
        generation_rounds_attempted = max(
            [int(row.get("generation_round", 0)) for row in default_result["generation_audit"]],
            default=0,
        )
        sensitivity_used = False
        sensitivity_recovered = False

        if not paths:
            sensitivity_used = True
            sensitivity_fallback_pair_count += 1
            grid = sensitivity_union_from_frozen_baseline(
                adjacency,
                rule_index,
                lookup,
                source_node,
                target_node,
                reference_edges,
                default_result=default_result,
            )
            paths = list(grid["corridors"])
            # The default configuration is included in the 12-grid audit. Since
            # it was already evaluated above, avoid double-counting its audit.
            generation_paths_examined += int(grid["paths_examined"]) - len(
                default_result["generation_audit"]
            )
            generation_rounds_attempted = max(
                generation_rounds_attempted, int(grid["max_generation_round"])
            )
            sensitivity_recovered = bool(paths)
            if sensitivity_recovered:
                sensitivity_recovered_pair_count += 1
            else:
                sensitivity_grid_explicit_failure_count += 1

        seen = set()
        for rank, path in enumerate(paths, start=1):
            edge_key = tuple(str(value) for value in path["edge_ids"])
            if edge_key in seen:
                raise AssertionError(f"duplicate admitted edge sequence for {pair_id}")
            seen.add(edge_key)
            bounded._append_corridor(
                corridor_rows,
                pair_id=pair_id,
                source_terminal=source_terminal,
                target_terminal=target_terminal,
                source_stop=source_stop,
                target_stop=target_stop,
                source_node=source_node,
                target_node=target_node,
                epoch=epoch_id,
                node_xy=node_xy,
                path=path,
                rank=rank,
                reference_edges=reference_edges,
                reference_loopless=reference_loopless,
            )

        failure_reason = "" if paths else EXPLICIT_GRID_FAILURE_REASON
        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_routing_terminal_id": source_terminal,
                "target_routing_terminal_id": target_terminal,
                "source_stop_place_id": source_stop,
                "target_stop_place_id": target_stop,
                "source_graph_node_id": source_node,
                "target_graph_node_id": target_node,
                "status": (
                    "PASS_ROUTED_CORRIDOR_POOL"
                    if paths
                    else "EXPLICIT_NO_LOOPLESS_CORRIDOR_WITHIN_VALIDATED_RT006_GRID"
                ),
                "failure_reason": failure_reason,
                "corridor_count": len(paths),
                "certified_shortest_present": True,
                "certified_shortest_physical_loopless": reference_loopless,
                "certified_reference_turn_legal": True,
                "certified_edge_sequence_matches_rt017": True,
                "certified_runtime_delta_vs_rt017_min": f"{runtime_delta:.12f}",
                "certified_distance_delta_vs_rt017_m": f"{distance_delta:.9f}",
                "generation_paths_examined": generation_paths_examined,
                "generation_rounds_attempted": generation_rounds_attempted,
                "ksp_fallback_used": False,
                "generator_contract": bounded.RT006_CONTRACT,
                "completeness_claim": bounded.RT006_COMPLETENESS,
                "graph_epoch_id": str(epoch_id),
            }
        )
        generation_paths_examined_total += generation_paths_examined

    corridors = pd.DataFrame(corridor_rows, columns=bounded.CORRIDOR_COLUMNS)
    status = pd.DataFrame(pair_rows, columns=bounded.PAIR_STATUS_COLUMNS)
    execution = audit_pair_execution_completeness(manifest, status)
    if not execution["complete"]:
        raise AssertionError(execution)
    if len(status) != core.EXPECTED_DIRECTED_PAIRS:
        raise AssertionError(f"pair execution count changed: {len(status)}")
    if corridors.empty or corridors["corridor_id"].duplicated().any():
        raise AssertionError("corridor corpus empty or duplicate corridor IDs")
    if not (
        (status["corridor_count"].astype(int) > 0)
        | status["failure_reason"].astype(str).ne("")
    ).all():
        raise AssertionError("pair vanished without corridor or explicit failure reason")

    return corridors, status, {
        "pair_execution": execution,
        "graph_directed_edges": len(lookup),
        "turn_rules": len(rules),
        "generation_paths_examined_total": generation_paths_examined_total,
        "ksp_fallback_pair_count": 0,
        "sensitivity_fallback_pair_count": sensitivity_fallback_pair_count,
        "sensitivity_recovered_pair_count": sensitivity_recovered_pair_count,
        "sensitivity_grid_explicit_failure_count": sensitivity_grid_explicit_failure_count,
        "validated_grid_configurations": len(VALIDATED_RT006_GRID),
        "full_state_yen_production_used": False,
    }


def rewrite_validation(output_dir: Path) -> dict:
    validation_path = Path(output_dir) / "rt021_validation_v3.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    status = pd.read_csv(Path(output_dir) / "rt021_pair_execution_status_v3.csv", dtype=str).fillna("")
    with gzip.open(Path(output_dir) / "rt021_corridor_corpus_v3.csv.gz", "rt", encoding="utf-8") as handle:
        corpus = pd.read_csv(handle, dtype=str).fillna("")

    sensitivity_pairs = set(
        corpus.loc[corpus["provenance"].eq(SENSITIVITY_PROVENANCE), "pair_id"].astype(str)
    )
    explicit_failures = status[status["corridor_count"].astype(int).eq(0)].copy()
    if not explicit_failures["failure_reason"].eq(EXPLICIT_GRID_FAILURE_REASON).all():
        raise AssertionError("RT-021 zero-corridor pair lacks validated-grid explicit failure reason")
    if status["ksp_fallback_used"].astype(str).str.lower().isin({"true", "1"}).any():
        raise AssertionError("full-state Yen/KSP production fallback unexpectedly used")

    validation["corridor_corpus"].update(
        {
            "generator": "RT006_BOUNDED_DEFAULT_PLUS_VALIDATED_12_CONFIG_SENSITIVITY_UNION",
            "ksp_fallback_pair_count": 0,
            "full_state_yen_production_used": False,
            "sensitivity_grid": {
                "issue": 22,
                "certified_run": 33964236575,
                "configuration_count": len(VALIDATED_RT006_GRID),
                "configurations": validated_grid_signature(),
                "max_alternatives": bounded.RT006_MAX_ALTERNATIVES,
                "max_generation_rounds": bounded.RT006_MAX_GENERATION_ROUNDS,
                "union_contract": (
                    "UNION_ACROSS_TECHNICAL_EXPLORATION_SETTINGS_NOT_FREQUENCY_WEIGHTED_NOT_RANKED"
                ),
                "parameter_selection_authorized": False,
                "complete_k_shortest_claim_authorized": False,
            },
            "pairs_recovered_by_sensitivity_union": len(sensitivity_pairs),
            "pairs_with_explicit_no_loopless_within_validated_grid": len(explicit_failures),
        }
    )
    validation["pair_universe"]["explicit_failure_count"] = len(explicit_failures)
    validation["checks"].update(
        {
            "full_state_yen_production_not_used": True,
            "validated_grid_has_exactly_12_certified_configs": len(VALIDATED_RT006_GRID) == 12,
            "zero_corridor_pairs_are_explicit_validated_grid_statuses": bool(
                explicit_failures["failure_reason"].eq(EXPLICIT_GRID_FAILURE_REASON).all()
            ),
            "sensitivity_union_not_frequency_ranked": True,
        }
    )
    validation_path.write_bytes(core.canonical_json_bytes(validation))
    return validation


def output_dir_from_argv() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-dir", type=Path, required=True)
    args, _ = parser.parse_known_args()
    return args.output_dir
