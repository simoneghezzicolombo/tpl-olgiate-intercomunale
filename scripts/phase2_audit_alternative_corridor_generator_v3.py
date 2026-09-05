#!/usr/bin/env python3
"""Audit the bounded alternative-corridor generator against frozen Gate D.

The frozen reduced transfer seed paths are used only as routing regression
fixtures. They are not a passenger-stop universe and do not prescribe future
corridors, settlements, topology or service design.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import pandas as pd

from src.phase2_alternative_corridor_generator_v3 import (
    edge_lookup,
    generate_bounded_alternative_corridors,
    path_to_record,
)
from src.phase2_frozen_graph import build_adjacency, build_turn_rule_index, transition_allowed

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FROZEN = ROOT / "outputs/phase2/frozen_gate_d"
DEFAULT_OUT = ROOT / "outputs/phase2/network_design_method_audit_v3/alternative_corridor_generator_v3"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_fixtures(seed: pd.DataFrame, count: int) -> pd.DataFrame:
    frame = seed.copy()
    frame["edge_count_num"] = pd.to_numeric(frame["edge_count"], errors="raise").astype(int)
    frame = frame[
        frame["source_graph_node_id"].ne(frame["target_graph_node_id"])
        & frame["edge_count_num"].ge(2)
        & frame["path_edge_ids"].fillna("").ne("")
    ].copy()
    frame = frame.sort_values(
        ["edge_count_num", "source_graph_node_id", "target_graph_node_id", "source_anchor_id", "target_anchor_id"],
        kind="mergesort",
    )
    frame = frame.drop_duplicates(
        ["source_graph_node_id", "target_graph_node_id"], keep="first"
    ).reset_index(drop=True)
    if len(frame) < count:
        raise ValueError(f"Only {len(frame)} eligible unique Gate-D fixture pairs for requested {count}")
    if count == 1:
        positions = [len(frame) // 2]
    else:
        positions = sorted({round(i * (len(frame) - 1) / (count - 1)) for i in range(count)})
    selected = frame.iloc[positions].copy().reset_index(drop=True)
    if len(selected) != count:
        raise AssertionError("Fixture quantile selection did not produce requested count")
    selected["fixture_id"] = [f"FIXTURE_{index + 1:02d}" for index in range(len(selected))]
    return selected


def validate_turn_legality(path_edge_ids, source, target, lookup, rules) -> tuple[bool, str]:
    current = str(source)
    previous_node = None
    incoming_way = None
    for edge_id in path_edge_ids:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-dir", type=Path, default=DEFAULT_FROZEN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fixture-count", type=int, default=5)
    parser.add_argument("--max-alternatives", type=int, default=3)
    parser.add_argument("--max-generation-rounds", type=int, default=10)
    parser.add_argument("--penalty-increment", type=float, default=0.20)
    parser.add_argument("--max-runtime-factor", type=float, default=1.50)
    parser.add_argument("--max-overlap", type=float, default=0.90)
    args = parser.parse_args()

    edges_path = args.frozen_dir / "graph_edges.csv.gz"
    rules_path = args.frozen_dir / "turn_rules.csv.gz"
    seed_path = args.frozen_dir / "reduced_transfer_seed_paths.csv.gz"
    validation_path = args.frozen_dir / "graph_validation.json"
    for path in (edges_path, rules_path, seed_path, validation_path):
        if not path.exists():
            raise FileNotFoundError(path)

    frozen_validation = json.loads(validation_path.read_text(encoding="utf-8"))
    edges = pd.read_csv(edges_path, dtype=str)
    rules = pd.read_csv(rules_path, dtype=str).fillna("")
    seed = pd.read_csv(seed_path, dtype=str).fillna("")
    fixtures = select_fixtures(seed, args.fixture_count)

    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    lookup = edge_lookup(adjacency)

    fixture_records = []
    corridor_records = []
    generation_records = []
    all_pass = True
    audit_started = time.perf_counter()

    for fixture in fixtures.itertuples(index=False):
        source = str(fixture.source_graph_node_id)
        target = str(fixture.target_graph_node_id)
        frozen_edges = tuple(part for part in str(fixture.path_edge_ids).split(";") if part)
        started = time.perf_counter()
        result = generate_bounded_alternative_corridors(
            adjacency,
            rule_index,
            source,
            target,
            max_alternatives=args.max_alternatives,
            max_generation_rounds=args.max_generation_rounds,
            penalty_increment=args.penalty_increment,
            max_runtime_factor=args.max_runtime_factor,
            max_shared_runtime_fraction_allowed=args.max_overlap,
        )
        elapsed = time.perf_counter() - started
        baseline = result["baseline"]
        if baseline is None:
            raise AssertionError(f"Gate-D fixture lost routing connectivity: {fixture.fixture_id}")

        baseline_exact = baseline.edge_ids == frozen_edges
        runtime_delta = baseline.running_minutes_model - float(fixture.running_minutes_model)
        distance_delta = baseline.distance_m - float(fixture.distance_m)
        baseline_legal, baseline_legality_reason = validate_turn_legality(
            baseline.edge_ids, source, target, lookup, rule_index
        )

        corridor_legal = True
        corridor_loopless = True
        corridor_shortest_lower_bound = True
        for rank, corridor in enumerate(result["corridors"], start=1):
            legal, reason = validate_turn_legality(
                corridor.edge_ids, source, target, lookup, rule_index
            )
            corridor_legal &= legal
            corridor_loopless &= not corridor.physical_node_loop
            corridor_shortest_lower_bound &= (
                corridor.running_minutes_model + 1e-12 >= baseline.running_minutes_model
            )
            record = path_to_record(corridor)
            record.update(
                {
                    "fixture_id": fixture.fixture_id,
                    "corridor_rank_by_true_runtime": rank,
                    "turn_legality": legal,
                    "turn_legality_reason": reason,
                    "frozen_epoch_id": str(fixture.epoch_id),
                }
            )
            corridor_records.append(record)

        for generated in result["generation_audit"]:
            legal, reason = validate_turn_legality(
                generated.edge_ids, source, target, lookup, rule_index
            )
            record = path_to_record(generated)
            record.update(
                {
                    "fixture_id": fixture.fixture_id,
                    "turn_legality": legal,
                    "turn_legality_reason": reason,
                    "frozen_epoch_id": str(fixture.epoch_id),
                }
            )
            generation_records.append(record)

        fixture_pass = (
            baseline_exact
            and abs(runtime_delta) <= 1e-9
            and abs(distance_delta) <= 1e-6
            and baseline_legal
            and corridor_legal
            and corridor_loopless
            and corridor_shortest_lower_bound
            and result["contract"] == "ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION"
            and result["completeness_claim"] == "NO_K_SHORTEST_COMPLETENESS_CLAIM"
        )
        all_pass &= fixture_pass
        fixture_records.append(
            {
                "fixture_id": fixture.fixture_id,
                "source_anchor_id_fixture_only": fixture.source_anchor_id,
                "target_anchor_id_fixture_only": fixture.target_anchor_id,
                "source_graph_node_id": source,
                "target_graph_node_id": target,
                "frozen_edge_count": int(fixture.edge_count_num),
                "frozen_runtime_min": float(fixture.running_minutes_model),
                "frozen_distance_m": float(fixture.distance_m),
                "baseline_exact_edge_sequence": baseline_exact,
                "baseline_runtime_delta_min": runtime_delta,
                "baseline_distance_delta_m": distance_delta,
                "baseline_turn_legal": baseline_legal,
                "baseline_legality_reason": baseline_legality_reason,
                "baseline_physical_node_loop": baseline.physical_node_loop,
                "corridors_admitted": len(result["corridors"]),
                "generation_paths_examined": len(result["generation_audit"]),
                "all_admitted_corridors_turn_legal": corridor_legal,
                "all_admitted_corridors_physical_loopless": corridor_loopless,
                "all_admitted_corridors_not_faster_than_gate_d_shortest": corridor_shortest_lower_bound,
                "fixture_generation_seconds": elapsed,
                "fixture_status": "PASS" if fixture_pass else "FAIL",
                "epoch_id": str(fixture.epoch_id),
            }
        )

    total_seconds = time.perf_counter() - audit_started

    # One real-graph repeat is sufficient as a determinism regression without
    # doubling the entire performance audit.
    first_fixture = fixtures.iloc[0]
    deterministic_a = generate_bounded_alternative_corridors(
        adjacency,
        rule_index,
        str(first_fixture.source_graph_node_id),
        str(first_fixture.target_graph_node_id),
        max_alternatives=args.max_alternatives,
        max_generation_rounds=args.max_generation_rounds,
        penalty_increment=args.penalty_increment,
        max_runtime_factor=args.max_runtime_factor,
        max_shared_runtime_fraction_allowed=args.max_overlap,
    )
    deterministic_b = generate_bounded_alternative_corridors(
        adjacency,
        rule_index,
        str(first_fixture.source_graph_node_id),
        str(first_fixture.target_graph_node_id),
        max_alternatives=args.max_alternatives,
        max_generation_rounds=args.max_generation_rounds,
        penalty_increment=args.penalty_increment,
        max_runtime_factor=args.max_runtime_factor,
        max_shared_runtime_fraction_allowed=args.max_overlap,
    )
    determinism_pass = deterministic_a == deterministic_b
    all_pass &= determinism_pass

    args.output_dir.mkdir(parents=True, exist_ok=True)
    fixture_df = pd.DataFrame(fixture_records)
    corridor_df = pd.DataFrame(corridor_records)
    generation_df = pd.DataFrame(generation_records)
    fixture_out = args.output_dir / "real_graph_fixture_audit_v3.csv"
    corridor_out = args.output_dir / "real_graph_corridor_pool_v3.csv"
    generation_out = args.output_dir / "real_graph_generation_audit_v3.csv"
    fixture_df.to_csv(fixture_out, index=False)
    corridor_df.to_csv(corridor_out, index=False)
    generation_df.to_csv(generation_out, index=False)

    validation = {
        "status": "PASS_ALTERNATIVE_CORRIDOR_GENERATOR_V3" if all_pass else "FAIL_ALTERNATIVE_CORRIDOR_GENERATOR_V3",
        "scope": "ALGORITHM_AND_ROUTING_AUDIT_NOT_NETWORK_RECOMMENDATION",
        "issue": 22,
        "frozen_gate_d_status": frozen_validation.get("status"),
        "fixture_source_semantics": "FROZEN_GATE_D_SEED_PATHS_USED_ONLY_AS_ROUTING_REGRESSION_FIXTURES",
        "fixture_count": len(fixture_df),
        "fixtures_passing": int(fixture_df["fixture_status"].eq("PASS").sum()),
        "baseline_exact_edge_sequence_all": bool(fixture_df["baseline_exact_edge_sequence"].all()),
        "admitted_corridors_total": len(corridor_df),
        "generation_paths_examined_total": len(generation_df),
        "real_graph_determinism_pass": determinism_pass,
        "audit_total_seconds_excluding_repeat_check": total_seconds,
        "max_fixture_generation_seconds": float(fixture_df["fixture_generation_seconds"].max()),
        "technical_parameters": {
            "max_alternatives": args.max_alternatives,
            "max_generation_rounds": args.max_generation_rounds,
            "penalty_increment": args.penalty_increment,
            "max_runtime_factor": args.max_runtime_factor,
            "max_shared_runtime_fraction_allowed": args.max_overlap,
            "semantics": "TECHNICAL_EXPLORATION_PARAMETERS_NOT_POLICY_WEIGHTS_OR_THRESHOLDS",
        },
        "claims_not_authorized": [
            "COMPLETE_K_SHORTEST_ENUMERATION",
            "OPTIMAL_NETWORK",
            "RECOMMENDED_CORRIDOR",
            "PASSENGER_STOP_PATTERN",
            "TOPOLOGY_WINNER",
            "HEADWAY_WINNER",
            "PRIMARY",
            "RUNNER_UP",
        ],
        "stop_inventory_dependency": "NONE_FOR_THIS_AUDIT; MULTI_OPERATOR_STOP_INVENTORY_REMAINS_SEPARATE_UPSTREAM_WORK",
        "inputs": {
            "graph_edges": {"path": str(edges_path.relative_to(ROOT)), "sha256": sha256(edges_path)},
            "turn_rules": {"path": str(rules_path.relative_to(ROOT)), "sha256": sha256(rules_path)},
            "seed_paths_fixture_source": {"path": str(seed_path.relative_to(ROOT)), "sha256": sha256(seed_path)},
            "graph_validation": {"path": str(validation_path.relative_to(ROOT)), "sha256": sha256(validation_path)},
        },
        "outputs": {
            "fixture_audit_sha256": sha256(fixture_out),
            "corridor_pool_sha256": sha256(corridor_out),
            "generation_audit_sha256": sha256(generation_out),
        },
    }
    validation_out = args.output_dir / "alternative_corridor_generator_v3_validation.json"
    validation_out.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(validation, indent=2, sort_keys=True))
    if not all_pass:
        raise SystemExit("Alternative corridor generator V3 audit failed")


if __name__ == "__main__":
    main()
