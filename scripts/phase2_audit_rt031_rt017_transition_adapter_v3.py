#!/usr/bin/env python3
"""Pinned real audit for safe RT-017 via-node rejection in RT-031.

This certifies only exact rejection under frozen represented RT-017 via-node
semantics. Successor envelopes contain via-way evidence whose relevance to
arbitrary future compositions remains unresolved, so non-rejected movements are
not promoted to globally certified legal compositions.
"""
import argparse
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter

EXPECTED = {
    "edges": ("rt017/frozen_graph_edges.csv.gz", "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19"),
    "rules": ("rt017/frozen_turn_rules.csv.gz", "954865ad8972bd20d819e3eb6c4d548102609a4de07b7006ac7e42a61e14ed3a"),
    "levels": ("rt017/envelope_expansion_audit_v3.csv", "9d6cc8d2c23d26db3ba3cd8526a061953322b1fd034cf80430a2aef845aa3fb0"),
    "validation": ("rt017/rt017_validation.json", "7a35b647051c7ff625b61ede2f68a9c1240db592e7c44d5d8842a9d6cd6d2b84"),
    "corridors": ("rt022/elementary_corridors_for_reciprocity.csv", "7798f41b238dc818c76f4a440b4fc16203f4bb1e710f40394816399b39adf76c"),
    "patterns": ("rt030/rt030_realization_passenger_stop_patterns.csv", "44fd5d95717ea99d8bee205fa1949c978b44074af4134420ac59bc8a0769684e"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def run(root: Path, out: Path):
    tables, hashes = {}, {}
    for key, (relative, expected) in EXPECTED.items():
        path = root / relative
        observed = sha(path)
        if observed != expected:
            raise ValueError(f"{key} SHA mismatch")
        hashes[key] = observed
        tables[key] = json.loads(path.read_text()) if key == "validation" else read_csv(path)

    validation = tables["validation"]
    if validation["status"] != "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3":
        raise ValueError("RT-017 not PASS")
    frozen = int(validation["frozen_level"])
    levels = sorted(tables["levels"], key=lambda row: int(row["level"]))
    frozen_row = next(row for row in levels if int(row["level"]) == frozen)
    if int(frozen_row["bus_applicable_via_node_rules_observed"]) != 58:
        raise AssertionError("frozen observed rules changed")
    if int(frozen_row["rules_with_via_node_in_graph"]) != 52:
        raise AssertionError("frozen active rules changed")
    if int(frozen_row["via_way_restrictions_not_approximated"]) != 0:
        raise AssertionError("frozen via-way count changed")
    successor_via_way = max(
        int(row["via_way_restrictions_not_approximated"])
        for row in levels if int(row["level"]) > frozen
    )
    if successor_via_way != 2:
        raise AssertionError("successor via-way evidence changed")

    adapter = FrozenRT017ViaNodeAdapter(
        tables["edges"], tables["rules"], unresolved_external_via_way_count=successor_via_way)
    if adapter.audit.global_transition_completeness:
        raise AssertionError("global transition completeness must remain false")
    if not adapter.audit.represented_via_node_semantics_complete:
        raise AssertionError("frozen via-node semantics unsupported")

    outgoing = defaultdict(list)
    for edge in tables["edges"]:
        outgoing[str(edge["u_node_id"])].append(str(edge["edge_id"]))
    graph_transition_count = known_rejected = 0
    for edge_id, edge in adapter.edges.items():
        for next_edge in outgoing[edge["v"]]:
            graph_transition_count += 1
            if adapter.oracle((edge_id,), next_edge) is False:
                known_rejected += 1

    corridors = {row["corridor_id"]: row for row in tables["corridors"]}
    patterns = sorted(tables["patterns"], key=lambda row: row["realization_id"])
    realization = {}
    internal_governed = 0
    internally_rejected = []
    realization_touch = set()
    for pattern in patterns:
        corridor = corridors[pattern["corridor_id"]]
        edge_ids = corridor["path_edge_ids"].split(";")
        if not edge_ids:
            raise AssertionError("empty carrier")
        for left, right in zip(edge_ids[:-1], edge_ids[1:]):
            prior = adapter.edges[left]
            if (prior["v"], prior["way"]) in adapter.rules:
                internal_governed += 1
                realization_touch.add(pattern["realization_id"])
            if adapter.oracle((left,), right) is False:
                internally_rejected.append([pattern["realization_id"], left, right])
        realization[pattern["realization_id"]] = {
            "source_stop": pattern["source_endpoint_stop_id"],
            "target_stop": pattern["target_endpoint_stop_id"],
            "first": edge_ids[0],
            "last": edge_ids[-1],
        }
    if internally_rejected:
        raise AssertionError("certified atomic carrier violates frozen RT-017 rule")

    boundary = []
    realization_ids = sorted(realization)
    for left_id in realization_ids:
        left = realization[left_id]
        left_edge = adapter.edges[left["last"]]
        for right_id in realization_ids:
            if left_id == right_id:
                continue
            right = realization[right_id]
            right_edge = adapter.edges[right["first"]]
            if left_edge["v"] != right_edge["u"]:
                continue
            if left["target_stop"] != right["source_stop"]:
                raise AssertionError("carrier-contiguous boundary without shared structural stop")
            decision = adapter.decision((left["last"],), right["first"])
            boundary.append({
                "left_realization_id": left_id,
                "right_realization_id": right_id,
                "boundary_stop_id": left["target_stop"],
                "via_node_id": left_edge["v"],
                "incoming_osm_way_id": left_edge["way"],
                "outgoing_osm_way_id": right_edge["way"],
                "known_via_node_allowed": decision["allowed"],
                "known_via_node_status": decision["status"],
                "matched_relation_ids": ";".join(item["relation_id"] for item in decision["matched_rules"]),
            })
    rejected = [row for row in boundary if row["known_via_node_allowed"] is False]
    if len(boundary) != 2881 or len(rejected) != 6:
        raise AssertionError(f"boundary oracle changed: {len(boundary)}/{len(rejected)}")

    out.mkdir(parents=True, exist_ok=True)
    with (out / "known_forbidden_atomic_boundaries.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rejected[0]))
        writer.writeheader()
        writer.writerows(rejected)
    audit = {
        "status": "PASS_RT031_FROZEN_VIA_NODE_SAFE_REJECTION_NOT_GLOBAL_COMPOSITION_PASS",
        "input_hashes": hashes,
        "frozen_level": frozen,
        "frozen_via_way_not_approximated": 0,
        "successor_levels_max_via_way_not_approximated": successor_via_way,
        "frozen_rules_observed": adapter.audit.rule_count_observed,
        "frozen_rules_active_in_graph": adapter.audit.active_rule_count,
        "frozen_rules_inactive_outside_graph": adapter.audit.inactive_rule_count,
        "active_rule_types": list(adapter.audit.active_rule_types),
        "represented_via_node_semantics_complete": adapter.audit.represented_via_node_semantics_complete,
        "global_transition_completeness": False,
        "global_incompleteness_reason": "SUCCESSOR_RT017_ENVELOPES_CONTAIN_2_VIA_WAY_RESTRICTIONS_WHOSE_RELEVANCE_TO_ARBITRARY_FUTURE_COMPOSITIONS_IS_NOT_YET_CERTIFIED",
        "graph_transition_count_censused": graph_transition_count,
        "graph_transitions_known_rejected_by_frozen_rules": known_rejected,
        "rt030_pattern_count": len(patterns),
        "atomic_internal_rule_governed_transition_occurrences": internal_governed,
        "atomic_realizations_touching_frozen_rule_keys": len(realization_touch),
        "atomic_internal_known_rejections": 0,
        "carrier_contiguous_atomic_boundary_pairs": len(boundary),
        "known_forbidden_atomic_boundary_pairs": len(rejected),
        "known_forbidden_boundary_stop_ids": sorted({row["boundary_stop_id"] for row in rejected}),
        "safe_use": "KNOWN_FROZEN_VIA_NODE_REJECTIONS_MAY_PRUNE; OTHERWISE_KEEP_COMPOSITION_LEGALITY_UNKNOWN",
        "territorial_search_performed": False,
        "network_selected": False,
        "production_rt031_pass": False,
    }
    (out / "rt017_transition_adapter_audit.json").write_bytes(canonical(audit))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.inputs, args.out), indent=2))
