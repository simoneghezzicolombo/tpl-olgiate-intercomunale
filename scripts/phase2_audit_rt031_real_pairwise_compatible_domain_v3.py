#!/usr/bin/env python3
"""Pinned real RT-031 physical compatibility audit over the frozen RT-023 atoms.

This runner is deliberately narrower than production RT-031.  It proves exact
physical carrier compatibility only for ordered compositions of the 288 certified
RT-023 atomic realizations, and only after a separately certified historical
successor-via-way evidence file establishes history locality for that exact atomic
carrier universe.  No public-service, passenger-continuity, vehicle-run, timetable,
territorial-search or network-selection semantics are inferred.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_boundary_correspondence_v3 import build_boundary_catalog
from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import build_realization_catalog
from src.phase2_rt031_rt023_scoped_transition_v3 import RT023ScopedTransitionOracle, SCOPE
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import (
    build_pairwise_compatibility,
    exact_slot_sequence_count,
    LEGAL,
    ILLEGAL,
    UNKNOWN,
)

EXPECTED = {
    "edges": ("rt017/frozen_graph_edges.csv.gz", "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19"),
    "rules": ("rt017/frozen_turn_rules.csv.gz", "954865ad8972bd20d819e3eb6c4d548102609a4de07b7006ac7e42a61e14ed3a"),
    "corridors": ("rt022/elementary_corridors_for_reciprocity.csv", "7798f41b238dc818c76f4a440b4fc16203f4bb1e710f40394816399b39adf76c"),
    "patterns": ("rt030/rt030_realization_passenger_stop_patterns.csv", "44fd5d95717ea99d8bee205fa1949c978b44074af4134420ac59bc8a0769684e"),
    "occurrences": ("rt030/rt030_realization_stop_occurrences.csv", "124494b69713a7fe1792d241415d3437d2e87414752eb74603e5ec6aaf8bda37"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def load_inputs(root: Path):
    tables, hashes = {}, {}
    for key, (relative, expected) in EXPECTED.items():
        path = root / relative
        observed = sha256_file(path)
        if observed != expected:
            raise ValueError(f"{key} SHA mismatch: {observed}")
        hashes[key] = observed
        tables[key] = read_csv(path)
    return tables, hashes


def validate_via_way_evidence(path: Path) -> dict:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence.get("status") != "PASS_RT031_SUCCESSOR_VIA_WAY_IRRELEVANT_TO_RT023_COMPOSED_DOMAIN":
        raise ValueError("successor via-way irrelevance is not certified PASS")
    if evidence.get("claim_scope") != SCOPE:
        raise ValueError("via-way evidence scope mismatch")
    if evidence.get("successor_via_way_relation_count") != 2:
        raise ValueError("successor via-way relation universe changed")
    if evidence.get("rt023_realization_count") != 288:
        raise ValueError("via-way evidence RT023 realization count changed")
    if evidence.get("rt023_carrier_directed_edge_count") != 5205:
        raise ValueError("via-way evidence carrier-edge universe changed")
    if evidence.get("rt023_carrier_osm_way_count") != 394:
        raise ValueError("via-way evidence carrier-way universe changed")
    if evidence.get("all_successor_via_way_irrelevant_to_rt023_composed_domain") is not True:
        raise ValueError("successor via-way relevance remains unresolved")
    if evidence.get("future_new_carrier_search_covered") is not False:
        raise ValueError("via-way evidence overclaims future carrier search")
    if evidence.get("global_osm_restriction_completeness_claimed") is not False:
        raise ValueError("via-way evidence overclaims global OSM completeness")
    for relation in evidence.get("successor_via_way_relations", []):
        if relation.get("relevant_to_any_rt023_composition") is not False:
            raise ValueError("a successor via-way relation is relevant to RT023")
        if relation.get("via_way_overlap_with_rt023") not in ([], ()):
            raise ValueError("successor via-way relation overlaps RT023 carrier")
    return evidence


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(root: Path, via_way_evidence: Path, out: Path) -> dict:
    tables, hashes = load_inputs(root)
    via_way = validate_via_way_evidence(via_way_evidence)
    if len(tables["patterns"]) != 288 or len(tables["occurrences"]) != 597:
        raise AssertionError("RT030 corpus cardinality changed")

    catalog, by_slot = build_realization_catalog(
        tables["patterns"], tables["corridors"], tables["edges"])
    if len(catalog) != 288 or len(by_slot) != 220:
        raise AssertionError(f"realization/slot universe changed: {len(catalog)}/{len(by_slot)}")

    boundary = build_boundary_catalog(
        tables["patterns"], tables["occurrences"], tables["corridors"], tables["edges"])
    if len(boundary) != 2881:
        raise AssertionError(f"boundary universe changed: {len(boundary)}")
    if any(r["boundary_location_status"] != "CERTIFIED_SAME_BOUNDARY_LOCATION" for r in boundary):
        raise AssertionError("real boundary location correspondence is not complete")

    base_adapter = FrozenRT017ViaNodeAdapter(
        tables["edges"], tables["rules"], unresolved_external_via_way_count=2)
    if base_adapter.audit.global_transition_completeness:
        raise AssertionError("global RT017 completeness must remain false")
    atomic_edges = sorted({eid for r in catalog.values() for eid in r["edge_ids"]})
    if len(atomic_edges) != 5205:
        raise AssertionError("atomic carrier directed-edge universe changed")
    scoped = RT023ScopedTransitionOracle(
        base_adapter,
        atomic_edges,
        successor_via_way_irrelevance_certified=True,
        evidence_id="RT031_SUCCESSOR_VIA_WAY::" + sha256_file(via_way_evidence),
    )
    if not scoped.audit.scoped_transition_completeness:
        raise AssertionError("RT023-scoped transition completeness did not close")
    if scoped.audit.global_transition_completeness_claimed:
        raise AssertionError("scoped oracle promoted global completeness")

    pairwise = build_pairwise_compatibility(
        catalog, boundary, scoped.oracle, history_locality_certified=True)
    counts = Counter(r["status"] for r in pairwise)
    if len(pairwise) != 2881:
        raise AssertionError(f"pairwise realization boundary count changed: {len(pairwise)}")
    expected_counts = {LEGAL: 2875, ILLEGAL: 6, UNKNOWN: 0}
    observed_counts = {key: counts.get(key, 0) for key in expected_counts}
    if observed_counts != expected_counts:
        raise AssertionError(f"real pairwise status counts changed: {observed_counts}")

    # Exhaust every endpoint-compatible ordered pair of structural slots.  The DP
    # must account for exactly the same 2,881 atomic boundary alternatives without
    # materializing any larger product.
    slots = sorted(by_slot)
    slot_pairs = []
    pair_product = pair_compatible = pair_zero = 0
    for left in slots:
        for right in slots:
            if by_slot[left][0]["target_stop_id"] != by_slot[right][0]["source_stop_id"]:
                continue
            result = exact_slot_sequence_count([left, right], by_slot, pairwise)
            if not result["exact"]:
                raise AssertionError(f"pair slot domain unexpectedly UNKNOWN: {left}->{right}")
            product_size = len(by_slot[left]) * len(by_slot[right])
            compatible = int(result["compatible_sequence_count"])
            pair_product += product_size
            pair_compatible += compatible
            pair_zero += int(compatible == 0)
            slot_pairs.append({
                "left_structural_link_id": left[0],
                "left_direction": left[1],
                "right_structural_link_id": right[0],
                "right_direction": right[1],
                "boundary_stop_id": by_slot[left][0]["target_stop_id"],
                "alternative_product_size": product_size,
                "compatible_sequence_count": compatible,
            })
    if (len(slot_pairs), pair_product, pair_compatible, pair_zero) != (1666, 2881, 2875, 4):
        raise AssertionError(
            "two-slot aggregate changed: " +
            repr((len(slot_pairs), pair_product, pair_compatible, pair_zero)))

    # Exhaust every endpoint-compatible ordered THREE-slot decomposition using the
    # exact DP.  This is the first real multi-link propagation check beyond one
    # boundary, while remaining a composition audit rather than a territorial search.
    next_slots = {}
    for left in slots:
        next_slots[left] = [right for right in slots
                            if by_slot[left][0]["target_stop_id"] == by_slot[right][0]["source_stop_id"]]
    triple_count = triple_product = triple_compatible = triple_zero = triple_affected = 0
    for first in slots:
        for second in next_slots[first]:
            for third in next_slots[second]:
                triple_count += 1
                product_size = len(by_slot[first]) * len(by_slot[second]) * len(by_slot[third])
                result = exact_slot_sequence_count([first, second, third], by_slot, pairwise)
                if not result["exact"]:
                    raise AssertionError(f"three-slot domain unexpectedly UNKNOWN: {first}->{second}->{third}")
                compatible = int(result["compatible_sequence_count"])
                triple_product += product_size
                triple_compatible += compatible
                triple_zero += int(compatible == 0)
                triple_affected += int(compatible < product_size)
    expected_triples = (13042, 30034, 29951, 40, 76)
    observed_triples = (triple_count, triple_product, triple_compatible, triple_zero, triple_affected)
    if observed_triples != expected_triples:
        raise AssertionError(f"three-slot aggregate changed: {observed_triples}")

    out.mkdir(parents=True, exist_ok=True)
    pairwise_rows = []
    for row in pairwise:
        pairwise_rows.append({
            "left_realization_id": row["left_realization_id"],
            "right_realization_id": row["right_realization_id"],
            "boundary_stop_id": row["boundary_stop_id"],
            "status": row["status"],
            "failure_reasons": ";".join(row["failure_reasons"]),
            "boundary_correspondence_id": row["boundary_correspondence_id"] or "",
        })
    write_csv(out / "real_pairwise_physical_compatibility.csv", pairwise_rows,
              ["left_realization_id", "right_realization_id", "boundary_stop_id", "status",
               "failure_reasons", "boundary_correspondence_id"])
    write_csv(out / "real_two_slot_domain_summary.csv", slot_pairs,
              ["left_structural_link_id", "left_direction", "right_structural_link_id",
               "right_direction", "boundary_stop_id", "alternative_product_size",
               "compatible_sequence_count"])

    audit = {
        "status": "PASS_RT031_EXACT_PHYSICAL_COMPATIBLE_DOMAIN_FOR_FROZEN_RT023_ATOMS",
        "claim_scope": SCOPE,
        "input_hashes": hashes,
        "successor_via_way_evidence_sha256": sha256_file(via_way_evidence),
        "successor_via_way_relation_count": via_way["successor_via_way_relation_count"],
        "rt023_realization_count": len(catalog),
        "rt023_structural_direction_slot_count": len(by_slot),
        "rt023_atomic_carrier_directed_edge_count": len(atomic_edges),
        "real_boundary_location_count": len(boundary),
        "pairwise_physical_compatibility_count": len(pairwise),
        "pairwise_status_counts": observed_counts,
        "ordered_two_slot_sequence_count": len(slot_pairs),
        "two_slot_conceptual_atomic_product_count": pair_product,
        "two_slot_compatible_atomic_sequence_count": pair_compatible,
        "two_slot_sequences_with_zero_compatible_realizations": pair_zero,
        "ordered_three_slot_sequence_count": triple_count,
        "three_slot_conceptual_atomic_product_count": triple_product,
        "three_slot_compatible_atomic_sequence_count": triple_compatible,
        "three_slot_sequences_with_zero_compatible_realizations": triple_zero,
        "three_slot_sequences_affected_by_physical_rejection": triple_affected,
        "pairwise_history_locality_certified": True,
        "pairwise_history_locality_basis": "FROZEN_VIA_NODE_RULES_PLUS_CERTIFIED_SUCCESSOR_VIA_WAY_IRRELEVANCE_WITHIN_RT023_ATOMIC_CARRIER_SCOPE",
        "global_rt017_transition_completeness_claimed": False,
        "future_new_carrier_search_covered": False,
        "service_semantics_assigned": False,
        "vehicle_continuity_inferred": False,
        "passenger_continuity_inferred": False,
        "pickup_dropoff_inferred": False,
        "territorial_search_performed": False,
        "network_selected": False,
        "production_rt031_pass": False,
    }
    (out / "rt031_real_pairwise_compatible_domain_audit.json").write_bytes(canonical(audit))
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.inputs, args.via_way_evidence, args.out)
