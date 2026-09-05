#!/usr/bin/env python3
"""Sensitivity audit for the bounded alternative-corridor generator V3.

The purpose is to avoid treating one arbitrary set of technical exploration
parameters as canonical. The audit runs a small deterministic parameter grid on
frozen Gate-D regression fixtures and materialises the *union* of legal,
loopless paths discovered across settings.

Path frequency across settings is descriptive only. It is not a quality score,
probability, vote or recommendation.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import time

import pandas as pd

from src.phase2_alternative_corridor_generator_v3 import (
    generate_bounded_alternative_corridors,
    path_to_record,
)
from src.phase2_frozen_graph import (
    build_adjacency,
    build_turn_rule_index,
    transition_allowed,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FROZEN = ROOT / "outputs/phase2/frozen_gate_d"
DEFAULT_BASE_AUDIT = (
    ROOT
    / "outputs/phase2/network_design_method_audit_v3/alternative_corridor_generator_v3"
)
DEFAULT_OUT = (
    ROOT
    / "outputs/phase2/network_design_method_audit_v3/alternative_corridor_sensitivity_v3"
)

PENALTY_INCREMENTS = (0.10, 0.20, 0.35)
MAX_RUNTIME_FACTORS = (1.25, 1.50)
MAX_OVERLAPS = (0.75, 0.90)
MAX_ALTERNATIVES = 3
MAX_GENERATION_ROUNDS = 10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_id(edge_ids: tuple[str, ...]) -> str:
    payload = ";".join(edge_ids).encode("utf-8")
    return "PATH_" + hashlib.sha256(payload).hexdigest()[:16].upper()


def build_edge_lookup(adjacency) -> dict[str, tuple[str, str, float, float, str]]:
    lookup = {}
    for u_node, outgoing in adjacency.items():
        for v_node, length_m, minutes, osm_way_id, edge_id in outgoing:
            edge_id = str(edge_id)
            record = (
                str(u_node),
                str(v_node),
                float(length_m),
                float(minutes),
                str(osm_way_id),
            )
            if edge_id in lookup and lookup[edge_id] != record:
                raise ValueError(f"Non-unique edge_id: {edge_id}")
            lookup[edge_id] = record
    return lookup


def turn_legal(edge_ids, source: str, target: str, lookup, rules) -> tuple[bool, str]:
    current = str(source)
    previous_node = None
    incoming_way = None
    for edge_id in edge_ids:
        edge_id = str(edge_id)
        if edge_id not in lookup:
            return False, f"UNKNOWN_EDGE:{edge_id}"
        u_node, v_node, _, _, outgoing_way = lookup[edge_id]
        if u_node != current:
            return False, f"NON_CONTIGUOUS:{edge_id}:{current}!={u_node}"
        if not transition_allowed(
            rules,
            current,
            previous_node,
            incoming_way,
            v_node,
            outgoing_way,
        ):
            return False, f"TURN_RESTRICTION_VIOLATION:{edge_id}"
        previous_node = current
        current = v_node
        incoming_way = outgoing_way
    if current != str(target):
        return False, f"WRONG_TARGET:{current}!={target}"
    return True, "PASS"


def config_grid() -> list[dict]:
    rows = []
    number = 0
    for penalty in PENALTY_INCREMENTS:
        for runtime_factor in MAX_RUNTIME_FACTORS:
            for overlap in MAX_OVERLAPS:
                number += 1
                rows.append(
                    {
                        "config_id": f"CFG_{number:02d}",
                        "penalty_increment": penalty,
                        "max_runtime_factor": runtime_factor,
                        "max_overlap": overlap,
                    }
                )
    return rows


def expected_baselines(base_generation: pd.DataFrame) -> dict[str, dict]:
    baseline = base_generation[
        base_generation["provenance"].eq("CERTIFIED_GATE_D_SHORTEST")
        & pd.to_numeric(base_generation["generation_round"], errors="raise").eq(0)
    ].copy()
    if baseline["fixture_id"].duplicated().any():
        raise ValueError("Base generator audit has multiple certified baselines per fixture")
    result = {}
    for row in baseline.itertuples(index=False):
        result[str(row.fixture_id)] = {
            "source": str(row.source_graph_node_id),
            "target": str(row.target_graph_node_id),
            "edge_ids": tuple(part for part in str(row.path_edge_ids).split(";") if part),
            "runtime": float(row.running_minutes_model),
            "distance": float(row.distance_m),
            "physical_node_loop": str(row.physical_node_loop).strip().lower() == "true",
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-dir", type=Path, default=DEFAULT_FROZEN)
    parser.add_argument("--base-audit-dir", type=Path, default=DEFAULT_BASE_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    edges_path = args.frozen_dir / "graph_edges.csv.gz"
    rules_path = args.frozen_dir / "turn_rules.csv.gz"
    fixture_path = args.base_audit_dir / "real_graph_fixture_audit_v3.csv"
    base_generation_path = args.base_audit_dir / "real_graph_generation_audit_v3.csv"
    base_validation_path = args.base_audit_dir / "alternative_corridor_generator_v3_validation.json"
    for path in (
        edges_path,
        rules_path,
        fixture_path,
        base_generation_path,
        base_validation_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    base_validation = json.loads(base_validation_path.read_text(encoding="utf-8"))
    if base_validation.get("status") != "PASS_ALTERNATIVE_CORRIDOR_GENERATOR_V3":
        raise ValueError("Sensitivity audit requires a PASS base generator audit")

    edges = pd.read_csv(edges_path, dtype=str)
    rules = pd.read_csv(rules_path, dtype=str).fillna("")
    fixtures = pd.read_csv(fixture_path, dtype=str).fillna("")
    base_generation = pd.read_csv(base_generation_path, dtype=str).fillna("")
    expected = expected_baselines(base_generation)

    if set(fixtures["fixture_id"]) != set(expected):
        raise ValueError("Fixture set and certified baseline set disagree")

    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    lookup = build_edge_lookup(adjacency)
    configs = config_grid()

    config_rows = []
    appearance_rows = []
    union_records: dict[tuple[str, str], dict] = {}
    fixture_first_alt: defaultdict[str, list[str]] = defaultdict(list)
    all_pass = True
    started_all = time.perf_counter()

    for config in configs:
        config_started = time.perf_counter()
        config_admitted = 0
        config_nonbaseline = 0
        config_examined = 0
        config_fixtures_with_alt = 0
        config_baseline_exact = True
        config_all_legal = True
        config_all_loopless = True
        config_all_not_faster = True

        for fixture in fixtures.sort_values("fixture_id", kind="mergesort").itertuples(index=False):
            fixture_id = str(fixture.fixture_id)
            reference = expected[fixture_id]
            result = generate_bounded_alternative_corridors(
                adjacency,
                rule_index,
                reference["source"],
                reference["target"],
                max_alternatives=MAX_ALTERNATIVES,
                max_generation_rounds=MAX_GENERATION_ROUNDS,
                penalty_increment=config["penalty_increment"],
                max_runtime_factor=config["max_runtime_factor"],
                max_shared_runtime_fraction_allowed=config["max_overlap"],
            )
            baseline = result["baseline"]
            if baseline is None:
                raise AssertionError(f"Lost baseline connectivity for {fixture_id}")

            baseline_exact = (
                baseline.edge_ids == reference["edge_ids"]
                and abs(baseline.running_minutes_model - reference["runtime"]) <= 1e-9
                and abs(baseline.distance_m - reference["distance"]) <= 1e-6
            )
            config_baseline_exact &= baseline_exact
            config_examined += len(result["generation_audit"])

            nonbaseline_paths = [
                path for path in result["corridors"]
                if path.provenance != "CERTIFIED_GATE_D_SHORTEST"
            ]
            if nonbaseline_paths:
                config_fixtures_with_alt += 1
                fixture_first_alt[fixture_id].append(path_id(nonbaseline_paths[0].edge_ids))

            for rank, corridor in enumerate(result["corridors"], start=1):
                legal, legal_reason = turn_legal(
                    corridor.edge_ids,
                    reference["source"],
                    reference["target"],
                    lookup,
                    rule_index,
                )
                loopless = not corridor.physical_node_loop
                not_faster = corridor.running_minutes_model + 1e-12 >= reference["runtime"]
                config_all_legal &= legal
                config_all_loopless &= loopless
                config_all_not_faster &= not_faster
                config_admitted += 1
                if corridor.provenance != "CERTIFIED_GATE_D_SHORTEST":
                    config_nonbaseline += 1

                pid = path_id(corridor.edge_ids)
                appearance_rows.append(
                    {
                        "config_id": config["config_id"],
                        "fixture_id": fixture_id,
                        "path_id": pid,
                        "rank_by_true_runtime_within_config": rank,
                        "provenance": corridor.provenance,
                        "running_minutes_model": corridor.running_minutes_model,
                        "distance_m": corridor.distance_m,
                        "runtime_factor_vs_gate_d_shortest": corridor.running_minutes_model / reference["runtime"] if reference["runtime"] > 0 else 1.0,
                        "max_shared_runtime_fraction_at_admission": corridor.max_shared_runtime_fraction,
                        "turn_legal": legal,
                        "turn_legality_reason": legal_reason,
                        "physical_node_loop": corridor.physical_node_loop,
                        "penalty_increment": config["penalty_increment"],
                        "max_runtime_factor": config["max_runtime_factor"],
                        "max_overlap": config["max_overlap"],
                        "scope": "PARAMETER_SENSITIVITY_APPEARANCE_NOT_RANKING_OR_RECOMMENDATION",
                    }
                )

                key = (fixture_id, pid)
                if key not in union_records:
                    record = path_to_record(corridor)
                    union_records[key] = {
                        **record,
                        "fixture_id": fixture_id,
                        "path_id": pid,
                        "gate_d_shortest_runtime_min": reference["runtime"],
                        "runtime_factor_vs_gate_d_shortest": corridor.running_minutes_model / reference["runtime"] if reference["runtime"] > 0 else 1.0,
                        "config_ids": [],
                        "penalty_increments_seen": [],
                        "runtime_envelopes_seen": [],
                        "overlap_envelopes_seen": [],
                        "provenances_seen": [],
                    }
                union = union_records[key]
                union["config_ids"].append(config["config_id"])
                union["penalty_increments_seen"].append(config["penalty_increment"])
                union["runtime_envelopes_seen"].append(config["max_runtime_factor"])
                union["overlap_envelopes_seen"].append(config["max_overlap"])
                union["provenances_seen"].append(corridor.provenance)

        elapsed = time.perf_counter() - config_started
        config_pass = (
            config_baseline_exact
            and config_all_legal
            and config_all_loopless
            and config_all_not_faster
        )
        all_pass &= config_pass
        config_rows.append(
            {
                **config,
                "fixture_count": len(fixtures),
                "admitted_corridor_appearances": config_admitted,
                "nonbaseline_alternative_appearances": config_nonbaseline,
                "fixtures_with_nonbaseline_alternative": config_fixtures_with_alt,
                "generation_paths_examined": config_examined,
                "baseline_exact_all_fixtures": config_baseline_exact,
                "all_admitted_turn_legal": config_all_legal,
                "all_admitted_physical_loopless": config_all_loopless,
                "all_admitted_not_faster_than_gate_d_shortest": config_all_not_faster,
                "elapsed_seconds": elapsed,
                "config_status": "PASS" if config_pass else "FAIL",
                "parameter_semantics": "TECHNICAL_EXPLORATION_SETTING_NOT_POLICY_WEIGHT_OR_RECOMMENDATION",
            }
        )

    union_rows = []
    for (fixture_id, pid), record in sorted(union_records.items()):
        row = dict(record)
        configs_seen = sorted(set(row.pop("config_ids")))
        penalties_seen = sorted(set(row.pop("penalty_increments_seen")))
        runtimes_seen = sorted(set(row.pop("runtime_envelopes_seen")))
        overlaps_seen = sorted(set(row.pop("overlap_envelopes_seen")))
        provenances_seen = sorted(set(row.pop("provenances_seen")))
        row.update(
            {
                "config_appearance_count": len(configs_seen),
                "config_appearance_fraction": len(configs_seen) / len(configs),
                "config_ids": "|".join(configs_seen),
                "penalty_increments_seen": "|".join(str(v) for v in penalties_seen),
                "runtime_envelopes_seen": "|".join(str(v) for v in runtimes_seen),
                "overlap_envelopes_seen": "|".join(str(v) for v in overlaps_seen),
                "provenances_seen": "|".join(provenances_seen),
                "appearance_semantics": "DESCRIPTIVE_SEARCH_STABILITY_ONLY_NOT_QUALITY_SCORE_NOT_PROBABILITY",
                "union_semantics": "UNION_ACROSS_TECHNICAL_EXPLORATION_SETTINGS_NOT_FREQUENCY_WEIGHTED_NOT_RANKED",
            }
        )
        union_rows.append(row)

    union_df = pd.DataFrame(union_rows)
    config_df = pd.DataFrame(config_rows)
    appearance_df = pd.DataFrame(appearance_rows)

    fixture_rows = []
    for fixture_id in sorted(expected):
        subset = union_df[union_df["fixture_id"].eq(fixture_id)]
        nonbaseline = subset[~subset["provenances_seen"].str.contains("CERTIFIED_GATE_D_SHORTEST", regex=False)]
        first_alt_variants = sorted(set(fixture_first_alt[fixture_id]))
        reference = expected[fixture_id]
        fixture_rows.append(
            {
                "fixture_id": fixture_id,
                "certified_baseline_physical_node_loop": reference["physical_node_loop"],
                "unique_admitted_paths_in_grid_union": len(subset),
                "unique_nonbaseline_paths_in_grid_union": len(nonbaseline),
                "unique_first_nonbaseline_path_variants_across_configs": len(first_alt_variants),
                "first_nonbaseline_path_ids_seen": "|".join(first_alt_variants),
                "configs_total": len(configs),
                "configs_with_nonbaseline_alternative": sum(
                    1
                    for config_id in config_df["config_id"]
                    if not appearance_df[
                        appearance_df["config_id"].eq(config_id)
                        & appearance_df["fixture_id"].eq(fixture_id)
                        & ~appearance_df["provenance"].eq("CERTIFIED_GATE_D_SHORTEST")
                    ].empty
                ),
                "sensitivity_semantics": "DESCRIPTIVE_ONLY_NO_PARAMETER_CONFIGURATION_SELECTED",
            }
        )
    fixture_df = pd.DataFrame(fixture_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config_out = args.output_dir / "parameter_grid_summary_v3.csv"
    appearance_out = args.output_dir / "path_appearances_by_config_v3.csv"
    union_out = args.output_dir / "parameter_grid_path_union_v3.csv"
    fixture_out = args.output_dir / "fixture_sensitivity_summary_v3.csv"
    config_df.to_csv(config_out, index=False)
    appearance_df.to_csv(appearance_out, index=False)
    union_df.to_csv(union_out, index=False)
    fixture_df.to_csv(fixture_out, index=False)

    total_seconds = time.perf_counter() - started_all
    validation = {
        "status": "PASS_ALTERNATIVE_CORRIDOR_SENSITIVITY_V3" if all_pass else "FAIL_ALTERNATIVE_CORRIDOR_SENSITIVITY_V3",
        "scope": "TECHNICAL_PARAMETER_SENSITIVITY_NOT_NETWORK_SELECTION",
        "issue": 22,
        "base_generator_status": base_validation.get("status"),
        "parameter_configurations": len(configs),
        "fixture_count": len(fixtures),
        "all_configurations_pass": bool(config_df["config_status"].eq("PASS").all()),
        "baseline_exact_across_grid": bool(config_df["baseline_exact_all_fixtures"].all()),
        "unique_admitted_fixture_paths_in_union": len(union_df),
        "unique_nonbaseline_fixture_paths_in_union": int(
            (~union_df["provenances_seen"].str.contains("CERTIFIED_GATE_D_SHORTEST", regex=False)).sum()
        ),
        "total_parameter_grid_seconds": total_seconds,
        "parameter_grid": {
            "penalty_increments": list(PENALTY_INCREMENTS),
            "max_runtime_factors": list(MAX_RUNTIME_FACTORS),
            "max_overlaps": list(MAX_OVERLAPS),
            "max_alternatives": MAX_ALTERNATIVES,
            "max_generation_rounds": MAX_GENERATION_ROUNDS,
            "semantics": "TECHNICAL_EXPLORATION_GRID_NOT_POLICY_WEIGHTS_OR_RECOMMENDATION",
        },
        "union_contract": "UNION_ACROSS_TECHNICAL_EXPLORATION_SETTINGS_NOT_FREQUENCY_WEIGHTED_NOT_RANKED",
        "appearance_frequency_contract": "DESCRIPTIVE_SEARCH_STABILITY_ONLY_NOT_QUALITY_SCORE_NOT_PROBABILITY",
        "parameter_selection_authorized": False,
        "recommended_corridor_authorized": False,
        "complete_k_shortest_claim_authorized": False,
        "stop_inventory_dependency": "NONE_FOR_THIS_SENSITIVITY_AUDIT",
        "inputs": {
            "graph_edges": {"path": str(edges_path.relative_to(ROOT)), "sha256": sha256(edges_path)},
            "turn_rules": {"path": str(rules_path.relative_to(ROOT)), "sha256": sha256(rules_path)},
            "base_fixture_audit": {"path": str(fixture_path.relative_to(ROOT)), "sha256": sha256(fixture_path)},
            "base_generation_audit": {"path": str(base_generation_path.relative_to(ROOT)), "sha256": sha256(base_generation_path)},
            "base_validation": {"path": str(base_validation_path.relative_to(ROOT)), "sha256": sha256(base_validation_path)},
        },
        "outputs": {
            "parameter_grid_summary_sha256": sha256(config_out),
            "path_appearances_sha256": sha256(appearance_out),
            "parameter_grid_union_sha256": sha256(union_out),
            "fixture_sensitivity_summary_sha256": sha256(fixture_out),
        },
    }
    validation_out = args.output_dir / "alternative_corridor_sensitivity_v3_validation.json"
    validation_out.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    if not all_pass:
        raise SystemExit("Alternative corridor sensitivity V3 failed")


if __name__ == "__main__":
    main()
