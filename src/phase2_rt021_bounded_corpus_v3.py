from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from src import phase2_rt021_territorial_corridor_corpus_v3 as core
from src.phase2_alternative_corridor_generator_v3 import (
    edge_lookup,
    has_physical_node_loop,
    materialize_path,
    max_shared_runtime_fraction,
    restriction_aware_penalized_shortest_path,
)
from src.phase2_complete_directed_pairs_v3 import audit_pair_execution_completeness
from src.phase2_final_stop_materialization_v3 import (
    attach_stop_places_to_graph,
    validate_final_stop_places,
)
from src.phase2_frozen_graph import (
    build_adjacency,
    build_turn_rule_index,
    transition_allowed,
)
from src.phase2_restriction_aware_ksp import (
    build_restriction_aware_state_context,
    k_shortest_loopless_paths,
)

RT006_MAX_ALTERNATIVES = 3
RT006_MAX_GENERATION_ROUNDS = 10
RT006_PENALTY_INCREMENT = 0.20
RT006_MAX_RUNTIME_FACTOR = 1.50
RT006_MAX_OVERLAP = 0.90
RT006_CONTRACT = "ALTERNATIVE_POOL_NOT_NETWORK_RECOMMENDATION"
RT006_COMPLETENESS = "NO_K_SHORTEST_COMPLETENESS_CLAIM"

CORRIDOR_COLUMNS = [
    "corridor_id",
    "pair_id",
    "source_routing_terminal_id",
    "target_routing_terminal_id",
    "source_stop_place_id",
    "target_stop_place_id",
    "source_graph_node_id",
    "target_graph_node_id",
    "corridor_rank_by_running_time",
    "running_minutes_model",
    "distance_m",
    "edge_count",
    "physical_node_count",
    "path_edge_ids",
    "path_node_ids",
    "path_geometry_sha256",
    "provenance",
    "generation_round",
    "runtime_factor_vs_shortest",
    "max_shared_runtime_fraction",
    "is_exact_rt017_certified_shortest",
    "certified_shortest_physical_loopless",
    "physical_loopless",
    "generator_contract",
    "completeness_claim",
    "graph_epoch_id",
    "decision_role",
]
PAIR_STATUS_COLUMNS = [
    "pair_id",
    "source_routing_terminal_id",
    "target_routing_terminal_id",
    "source_stop_place_id",
    "target_stop_place_id",
    "source_graph_node_id",
    "target_graph_node_id",
    "status",
    "failure_reason",
    "corridor_count",
    "certified_shortest_present",
    "certified_shortest_physical_loopless",
    "certified_reference_turn_legal",
    "certified_edge_sequence_matches_rt017",
    "certified_runtime_delta_vs_rt017_min",
    "certified_distance_delta_vs_rt017_m",
    "generation_paths_examined",
    "generation_rounds_attempted",
    "ksp_fallback_used",
    "generator_contract",
    "completeness_claim",
    "graph_epoch_id",
]


def validate_turn_legal_edge_sequence(source, target, edge_ids, lookup, rule_index):
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
            rule_index,
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


def generate_bounded_from_frozen_baseline(
    adjacency,
    rule_index,
    lookup,
    source,
    target,
    baseline_edge_ids,
    *,
    max_alternatives=RT006_MAX_ALTERNATIVES,
    max_generation_rounds=RT006_MAX_GENERATION_ROUNDS,
    penalty_increment=RT006_PENALTY_INCREMENT,
    max_runtime_factor=RT006_MAX_RUNTIME_FACTOR,
    max_overlap=RT006_MAX_OVERLAP,
):
    """Mirror RT-006 after its shortest-path oracle, reusing frozen RT-017 evidence."""
    source = str(source)
    target = str(target)
    baseline_edges = tuple(str(value) for value in baseline_edge_ids)
    baseline_nodes, baseline_runtime, baseline_distance = materialize_path(
        source, baseline_edges, lookup
    )
    if not baseline_nodes or baseline_nodes[-1] != target:
        raise AssertionError("RT-017 baseline does not terminate at requested target")
    baseline_loop = has_physical_node_loop(baseline_nodes)
    baseline = {
        "edge_ids": baseline_edges,
        "node_ids": baseline_nodes,
        "running_minutes_model": baseline_runtime,
        "distance_m": baseline_distance,
        "provenance": "CERTIFIED_RT017_SHORTEST",
        "generation_round": 0,
        "physical_node_loop": baseline_loop,
        "runtime_factor_vs_shortest": 1.0,
        "max_shared_runtime_fraction": 0.0,
        "admissible_for_corridor_pool": not baseline_loop,
        "rejection_reason": "" if not baseline_loop else "PHYSICAL_NODE_LOOP",
    }
    admitted = [] if baseline_loop else [baseline]
    audit = [baseline]
    seen_paths = {baseline_edges}
    penalty_counts = Counter(baseline_edges)

    for generation_round in range(1, max_generation_rounds + 1):
        if len(admitted) >= max_alternatives:
            break
        raw = restriction_aware_penalized_shortest_path(
            adjacency,
            rule_index,
            source,
            target,
            penalty_counts,
            penalty_increment,
        )
        if raw is None:
            break
        edges = tuple(str(value) for value in raw["edge_ids"])
        nodes, runtime, distance = materialize_path(source, edges, lookup)
        loop = has_physical_node_loop(nodes)
        runtime_factor = runtime / baseline_runtime if baseline_runtime > 1e-12 else 1.0
        overlap = max_shared_runtime_fraction(
            edges,
            [path["edge_ids"] for path in admitted],
            lookup,
        )
        reasons = []
        if edges in seen_paths:
            reasons.append("DUPLICATE_EDGE_SEQUENCE")
        if loop:
            reasons.append("PHYSICAL_NODE_LOOP")
        if runtime_factor > max_runtime_factor + 1e-12:
            reasons.append("ABOVE_TECHNICAL_RUNTIME_ENVELOPE")
        if admitted and overlap > max_overlap + 1e-12:
            reasons.append("ABOVE_TECHNICAL_OVERLAP_ENVELOPE")
        candidate = {
            "edge_ids": edges,
            "node_ids": nodes,
            "running_minutes_model": runtime,
            "distance_m": distance,
            "provenance": "BOUNDED_PENALTY_ALTERNATIVE",
            "generation_round": generation_round,
            "physical_node_loop": loop,
            "runtime_factor_vs_shortest": runtime_factor,
            "max_shared_runtime_fraction": overlap,
            "admissible_for_corridor_pool": not reasons,
            "rejection_reason": "|".join(reasons),
        }
        audit.append(candidate)
        seen_paths.add(edges)
        penalty_counts.update(edges)
        if not reasons:
            admitted.append(candidate)

    admitted = sorted(
        admitted,
        key=lambda path: (
            float(path["running_minutes_model"]),
            float(path["distance_m"]),
            tuple(path["edge_ids"]),
            int(path["generation_round"]),
        ),
    )
    return {
        "baseline": baseline,
        "corridors": admitted,
        "generation_audit": audit,
        "contract": RT006_CONTRACT,
        "completeness_claim": RT006_COMPLETENESS,
    }


def _append_corridor(
    rows,
    *,
    pair_id,
    source_terminal,
    target_terminal,
    source_stop,
    target_stop,
    source_node,
    target_node,
    epoch,
    node_xy,
    path,
    rank,
    reference_edges,
    reference_loopless,
):
    edge_ids = [str(value) for value in path["edge_ids"]]
    node_ids = [str(value) for value in path["node_ids"]]
    if has_physical_node_loop(node_ids):
        raise AssertionError(f"physical loop survived corridor filter for {pair_id}")
    rows.append(
        {
            "corridor_id": core.corridor_id(pair_id, edge_ids),
            "pair_id": pair_id,
            "source_routing_terminal_id": source_terminal,
            "target_routing_terminal_id": target_terminal,
            "source_stop_place_id": source_stop,
            "target_stop_place_id": target_stop,
            "source_graph_node_id": source_node,
            "target_graph_node_id": target_node,
            "corridor_rank_by_running_time": rank,
            "running_minutes_model": f"{float(path['running_minutes_model']):.9f}",
            "distance_m": f"{float(path['distance_m']):.6f}",
            "edge_count": len(edge_ids),
            "physical_node_count": len(node_ids),
            "path_edge_ids": ";".join(edge_ids),
            "path_node_ids": ";".join(node_ids),
            "path_geometry_sha256": core.path_geometry_sha256(node_ids, node_xy),
            "provenance": str(path["provenance"]),
            "generation_round": int(path.get("generation_round", 0)),
            "runtime_factor_vs_shortest": f"{float(path.get('runtime_factor_vs_shortest', 1.0)):.9f}",
            "max_shared_runtime_fraction": f"{float(path.get('max_shared_runtime_fraction', 0.0)):.9f}",
            "is_exact_rt017_certified_shortest": str(edge_ids == reference_edges).lower(),
            "certified_shortest_physical_loopless": str(reference_loopless).lower(),
            "physical_loopless": "true",
            "generator_contract": RT006_CONTRACT,
            "completeness_claim": RT006_COMPLETENESS,
            "graph_epoch_id": str(epoch),
            "decision_role": "TECHNICAL_CORRIDOR_POOL_NOT_NETWORK_OR_TERMINAL_SELECTION",
        }
    )


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
    ksp_context = None

    corridor_rows = []
    pair_rows = []
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
        legal, reason = validate_turn_legal_edge_sequence(
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

        result = generate_bounded_from_frozen_baseline(
            adjacency, rule_index, lookup, source_node, target_node, reference_edges
        )
        paths = list(result["corridors"])
        fallback_used = False
        if not paths:
            if ksp_context is None:
                ksp_context = build_restriction_aware_state_context(edges, rules)
            fallback = k_shortest_loopless_paths(
                ksp_context, source_node, target_node, k=1, max_raw_state_paths=20000
            )
            if fallback["paths"]:
                p = fallback["paths"][0]
                paths = [
                    {
                        "edge_ids": tuple(p["edge_ids"]),
                        "node_ids": tuple(p["physical_nodes"]),
                        "running_minutes_model": p["running_minutes_model"],
                        "distance_m": p["distance_m"],
                        "provenance": "KSP_FALLBACK_NO_RT006_LOOPLESS",
                        "generation_round": -1,
                        "runtime_factor_vs_shortest": (
                            float(p["running_minutes_model"]) / reference_runtime
                            if reference_runtime > 1e-12 else 1.0
                        ),
                        "max_shared_runtime_fraction": 0.0,
                    }
                ]
                fallback_used = True

        seen = set()
        for rank, path in enumerate(paths, start=1):
            key = tuple(str(value) for value in path["edge_ids"])
            if key in seen:
                raise AssertionError(f"duplicate admitted edge sequence for {pair_id}")
            seen.add(key)
            _append_corridor(
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

        failure_reason = "" if paths else "NO_LOOPLESS_CORRIDOR_AFTER_RT006_AND_KSP_FALLBACK"
        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_routing_terminal_id": source_terminal,
                "target_routing_terminal_id": target_terminal,
                "source_stop_place_id": source_stop,
                "target_stop_place_id": target_stop,
                "source_graph_node_id": source_node,
                "target_graph_node_id": target_node,
                "status": "PASS_ROUTED_CORRIDOR_POOL" if paths else "EXPLICIT_NO_LOOPLESS_CORRIDOR",
                "failure_reason": failure_reason,
                "corridor_count": len(paths),
                "certified_shortest_present": True,
                "certified_shortest_physical_loopless": reference_loopless,
                "certified_reference_turn_legal": True,
                "certified_edge_sequence_matches_rt017": True,
                "certified_runtime_delta_vs_rt017_min": f"{runtime_delta:.12f}",
                "certified_distance_delta_vs_rt017_m": f"{distance_delta:.9f}",
                "generation_paths_examined": len(result["generation_audit"]),
                "generation_rounds_attempted": max(
                    [int(row["generation_round"]) for row in result["generation_audit"]], default=0
                ),
                "ksp_fallback_used": fallback_used,
                "generator_contract": RT006_CONTRACT,
                "completeness_claim": RT006_COMPLETENESS,
                "graph_epoch_id": str(epoch_id),
            }
        )

    corridors = pd.DataFrame(corridor_rows, columns=CORRIDOR_COLUMNS)
    status = pd.DataFrame(pair_rows, columns=PAIR_STATUS_COLUMNS)
    execution = audit_pair_execution_completeness(manifest, status)
    if not execution["complete"]:
        raise AssertionError(execution)
    if len(status) != core.EXPECTED_DIRECTED_PAIRS:
        raise AssertionError(f"pair execution count changed: {len(status)}")
    if corridors.empty or corridors["corridor_id"].duplicated().any():
        raise AssertionError("corridor corpus empty or duplicate corridor IDs")
    return corridors, status, {
        "pair_execution": execution,
        "graph_directed_edges": len(lookup),
        "turn_rules": len(rules),
        "generation_paths_examined_total": int(status["generation_paths_examined"].sum()),
        "ksp_fallback_pair_count": int(status["ksp_fallback_used"].astype(bool).sum()),
    }


def build_rt021(*, rt017_dir: Path, stops_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = rt017_dir / "frozen_routing_envelope_metadata_v3.json"
    nodes_path = rt017_dir / "frozen_graph_nodes.csv.gz"
    edges_path = rt017_dir / "frozen_graph_edges.csv.gz"
    rules_path = rt017_dir / "frozen_turn_rules.csv.gz"
    reference_pairs_path = rt017_dir / "frozen_pair_results_v3.csv"
    for path in [metadata_path, nodes_path, edges_path, rules_path, reference_pairs_path, stops_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") != "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3":
        raise AssertionError("RT-021 requires certified PASS RT-017 metadata")
    expected_digests = metadata["digests"]
    actual_graph_digests = {
        "frozen_graph_nodes_gz_sha256": core.sha256_file(nodes_path),
        "frozen_graph_edges_gz_sha256": core.sha256_file(edges_path),
        "frozen_turn_rules_gz_sha256": core.sha256_file(rules_path),
        "frozen_pair_results_sha256": core.sha256_file(reference_pairs_path),
    }
    for key, actual in actual_graph_digests.items():
        if actual != str(expected_digests[key]):
            raise AssertionError(f"RT-017 digest mismatch: {key}")
    stop_sha = core.sha256_file(stops_path)
    if stop_sha != str(metadata["frozen_stop_sha256"]):
        raise AssertionError("frozen 36-stop dependency changed")

    stops = validate_final_stop_places(pd.read_csv(stops_path))
    nodes = pd.read_csv(nodes_path, compression="gzip")
    edges = pd.read_csv(edges_path, compression="gzip", dtype=str)
    rules = pd.read_csv(rules_path, compression="gzip", dtype=str).fillna("")
    reference_pairs = pd.read_csv(reference_pairs_path, dtype=str).fillna("")
    epoch = core.graph_epoch_id(metadata)
    attachments = attach_stop_places_to_graph(
        stops, core.adapt_rt017_nodes_for_rt018(nodes, epoch)
    )
    anchors = core.conventional_anchor_universe(attachments)
    manifest = core.build_rt021_pair_manifest(anchors)
    corridors, pair_status, routing_audit = route_corpus(
        manifest, anchors, edges, rules, nodes, reference_pairs, epoch_id=epoch
    )

    attachments_out = attachments.copy()
    for column in ["route_ready", "service_class_automatic", "automatic_materialization_eligible"]:
        attachments_out[column] = attachments_out[column].map(lambda value: str(bool(value)).lower())
    attachment_sha = core.write_csv(
        output_dir / "rt021_stop_attachments_v3.csv", attachments_out, sort_by=["stop_place_id"]
    )
    manifest_sha = core.write_csv(
        output_dir / "rt021_complete_directed_pair_manifest_v3.csv",
        manifest,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
        columns=core.PAIR_COLUMNS,
    )
    status_sha = core.write_csv(
        output_dir / "rt021_pair_execution_status_v3.csv",
        pair_status,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
        columns=PAIR_STATUS_COLUMNS,
    )
    corpus_bytes = core.canonical_csv_bytes(
        corridors,
        sort_by=["pair_id", "corridor_rank_by_running_time", "corridor_id"],
        columns=CORRIDOR_COLUMNS,
    )
    corpus_sha = core.sha256_bytes(corpus_bytes)
    corpus_gzip_sha = core.write_deterministic_gzip(
        output_dir / "rt021_corridor_corpus_v3.csv.gz", corpus_bytes
    )

    conventional_max = float(
        pd.to_numeric(
            attachments.loc[
                attachments["service_class"].astype(str).eq("CONVENTIONAL_TPL"),
                "attachment_distance_m",
            ],
            errors="raise",
        ).max()
    )
    counts = pair_status["corridor_count"].astype(int)
    runtime = pd.to_numeric(corridors["running_minutes_model"], errors="raise")
    distance = pd.to_numeric(corridors["distance_m"], errors="raise")
    explicit_failures = int(counts.eq(0).sum())
    checks = {
        "exactly_36_stop_places": len(attachments) == 36,
        "exactly_35_conventional_plus_1_special": (
            int(attachments["service_class"].astype(str).eq("CONVENTIONAL_TPL").sum()) == 35
            and int(attachments["service_class"].astype(str).eq("SPECIAL_SERVICE").sum()) == 1
        ),
        "all_35_conventional_route_ready_le_75m": conventional_max <= 75.0,
        "exactly_1190_directed_pairs": len(manifest) == core.EXPECTED_DIRECTED_PAIRS,
        "pair_execution_complete_no_omission": bool(routing_audit["pair_execution"]["complete"]),
        "every_pair_has_corridor_or_explicit_failure": bool(
            ((counts > 0) | pair_status["failure_reason"].astype(str).ne("")).all()
        ),
        "all_certified_reference_paths_turn_legal": bool(
            pair_status["certified_reference_turn_legal"].astype(bool).all()
        ),
        "all_certified_paths_match_rt017": bool(
            pair_status["certified_edge_sequence_matches_rt017"].astype(bool).all()
        ),
        "all_corridors_physical_loopless": bool(
            corridors["physical_loopless"].astype(str).eq("true").all()
        ),
        "rt006_contract_preserved": bool(
            corridors["generator_contract"].astype(str).eq(RT006_CONTRACT).all()
            and corridors["completeness_claim"].astype(str).eq(RT006_COMPLETENESS).all()
        ),
        "municipal_boundaries_not_used_as_routing_rules": (
            metadata.get("municipal_boundaries_used_as_routing_rules") is False
        ),
        "stop_discovery_not_performed": metadata.get("stop_discovery_performed") is False,
    }
    validation = {
        "status": "PASS_RT021_FROZEN_TERRITORIAL_CORRIDOR_CORPUS_V3",
        "contract": core.CONTRACT,
        "issue": 55,
        "graph_epoch_id": epoch,
        "rt017": {
            "status": metadata["status"],
            "osm_snapshot_timestamp": metadata["osm_snapshot_timestamp"],
            "frozen_level": metadata["frozen_level"],
            "frozen_margin_m": metadata["frozen_margin_m"],
            "input_digests": actual_graph_digests,
        },
        "stop_layer": {
            "frozen_stop_sha256": stop_sha,
            "stop_place_count": len(attachments),
            "conventional_tpl_count": 35,
            "special_service_count": 1,
            "conventional_max_attachment_distance_m": conventional_max,
            "all_conventional_route_ready_le_75m": conventional_max <= 75.0,
            "special_service_excluded_from_pair_universe": True,
            "attachment_identity_sha256": attachment_sha,
        },
        "pair_universe": {
            "technical_anchor_semantics": "35_CONVENTIONAL_STOP_PLACES_AS_PAIR_QUERY_ANCHORS_NOT_SERVICE_TERMINI",
            "directed_pair_count": len(manifest),
            "unordered_pair_count": len(manifest) // 2,
            "complete_execution_count": len(pair_status),
            "explicit_failure_count": explicit_failures,
            "pair_manifest_sha256": manifest_sha,
            "pair_execution_status_sha256": status_sha,
        },
        "corridor_corpus": {
            "generator": "RT006_BOUNDED_PENALTY_V3_WITH_FROZEN_RT017_BASELINE_AND_RARE_KSP_FALLBACK",
            "generator_contract": RT006_CONTRACT,
            "completeness_claim": RT006_COMPLETENESS,
            "technical_parameters": {
                "max_alternatives": RT006_MAX_ALTERNATIVES,
                "max_generation_rounds": RT006_MAX_GENERATION_ROUNDS,
                "penalty_increment": RT006_PENALTY_INCREMENT,
                "max_runtime_factor": RT006_MAX_RUNTIME_FACTOR,
                "max_shared_runtime_fraction_allowed": RT006_MAX_OVERLAP,
                "semantics": "TECHNICAL_EXPLORATION_CONTROLS_NOT_POLICY_WEIGHTS_OR_RECOMMENDATION",
            },
            "corridor_count": len(corridors),
            "pairs_with_1_corridor": int((counts == 1).sum()),
            "pairs_with_2_corridors": int((counts == 2).sum()),
            "pairs_with_3_corridors": int((counts == 3).sum()),
            "pairs_with_no_admitted_corridor": explicit_failures,
            "ksp_fallback_pair_count": routing_audit["ksp_fallback_pair_count"],
            "runtime_min_min": float(runtime.min()),
            "runtime_min_median": float(runtime.median()),
            "runtime_min_max": float(runtime.max()),
            "distance_m_min": float(distance.min()),
            "distance_m_median": float(distance.median()),
            "distance_m_max": float(distance.max()),
            "generation_paths_examined_total": routing_audit["generation_paths_examined_total"],
            "corridor_corpus_uncompressed_sha256": corpus_sha,
            "corridor_corpus_gzip_sha256": corpus_gzip_sha,
            "all_paths_physical_loopless": True,
            "all_certified_shortest_sequences_match_rt017": True,
            "external_municipality_traversal": "NOT_DERIVED_GRAPH_HAS_NO_MUNICIPALITY_LABEL_AND_NO_BOUNDARY_FILTER_IS_ALLOWED",
        },
        "routing_engine": {
            "graph_directed_edges": routing_audit["graph_directed_edges"],
            "turn_rules": routing_audit["turn_rules"],
            "baseline_semantics": "REUSE_FROZEN_RT017_CERTIFIED_SHORTEST_AFTER_EDGE_AND_TURN_LEGALITY_VALIDATION",
        },
        "checks": checks,
        "claims_not_authorized": [
            "COMPLETE_K_SHORTEST_ENUMERATION",
            "NETWORK_RECOMMENDATION",
            "TOPOLOGY_WINNER",
            "SERVICE_TERMINUS_SELECTION",
            "PRIMARY",
            "RUNNER_UP",
            "FIGURE_EIGHT_PRESCRIPTION",
            "NEW_STOP_HYPOTHESIS",
        ],
    }
    if not all(checks.values()):
        validation["status"] = "FAIL_RT021_VALIDATION_CHECK"
        (output_dir / "rt021_validation_v3.json").write_bytes(core.canonical_json_bytes(validation))
        raise AssertionError(checks)
    (output_dir / "rt021_validation_v3.json").write_bytes(core.canonical_json_bytes(validation))
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rt017-dir", type=Path, required=True)
    parser.add_argument("--stops", type=Path, default=core.STOP_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--k", type=int, default=3, help="legacy compatibility; must remain 3")
    parser.add_argument("--max-raw-state-paths", type=int, default=20000, help="legacy compatibility")
    args = parser.parse_args()
    if args.k != 3:
        raise ValueError("RT-021 frozen RT-006 contract requires --k 3 compatibility value")
    validation = build_rt021(
        rt017_dir=args.rt017_dir,
        stops_path=args.stops,
        output_dir=args.output_dir,
    )
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0
