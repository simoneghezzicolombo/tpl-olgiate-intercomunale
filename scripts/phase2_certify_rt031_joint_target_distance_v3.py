"""Reproducible minimum-distance physical co-presence certificate, not selection."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    load_inputs, validate_via_way_evidence, sha256_file, canonical,
    build_realization_catalog, build_boundary_catalog,
    FrozenRT017ViaNodeAdapter, RT023ScopedTransitionOracle,
    build_pairwise_compatibility)
from scripts.phase2_screen_rt031_resource_budget_v3 import PINNED
from src.phase2_rt031_joint_target_shortest_cycle_v3 import shortest_joint_cycle
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import (
    evaluate_realization_chain, LEGAL)


HUB = "FROZEN::L00407"
BRIVIO = "FROZEN::300063"
SANTA = ("FROZEN::300782", "FROZEN::300805", "FROZEN::300873")
REFERENCE_CAP_KM = Decimal("111419")
DAILY_CYCLES = 20
DESIGN_DAYS = 260


def main(inputs, evidence, output):
    tables, hashes = load_inputs(inputs)
    validate_via_way_evidence(evidence)
    for path, digest in PINNED.items():
        if sha256_file(Path(path)) != digest:
            raise ValueError("approved policy lineage changed")
    cat, _ = build_realization_catalog(
        tables["patterns"], tables["corridors"], tables["edges"])
    boundary = build_boundary_catalog(
        tables["patterns"], tables["occurrences"],
        tables["corridors"], tables["edges"])
    adapter = FrozenRT017ViaNodeAdapter(
        tables["edges"], tables["rules"],
        unresolved_external_via_way_count=2)
    scoped = RT023ScopedTransitionOracle(
        adapter, sorted({e for r in cat.values() for e in r["edge_ids"]}),
        successor_via_way_irrelevance_certified=True,
        evidence_id="RT031_SUCCESSOR_VIA_WAY::" + sha256_file(evidence))
    for row in cat.values():
        if evaluate_realization_chain([row], boundary, scoped.oracle)["status"] != LEGAL:
            raise ValueError("atomic legality open")
    pairs = build_pairwise_compatibility(
        cat, boundary, scoped.oracle, history_locality_certified=True)
    edges = {r["edge_id"]: r for r in tables["edges"]}
    weights = {rid: sum((Decimal(edges[e]["length_m"])
                         for e in row["edge_ids"]), Decimal(0))
               for rid, row in cat.items()}
    stop_sets = {r["realization_id"]:
                 r["ordered_passenger_stop_ids"].split(";")
                 for r in tables["patterns"]}
    result = shortest_joint_cycle(
        cat, pairs, weights, stop_sets,
        hub_stop_id=HUB, brivio_stop_id=BRIVIO,
        santa_maria_stop_ids=SANTA,
        history_locality_certified=True, atomic_legality_certified=True)
    path = result["minimum_joint_realization_ids"]
    available_stops = sorted(set().union(*(set(stop_sets[r]) for r in path))) if path else []
    if path:
        selected = [cat[r] for r in path]
        if evaluate_realization_chain(
                selected + [selected[0]], boundary, scoped.oracle)["status"] != LEGAL:
            raise AssertionError("minimum cycle fails independent full-history replay")
        if not ({HUB, BRIVIO} <= set(available_stops)
                and set(available_stops) & set(SANTA)):
            raise AssertionError("minimum cycle target coverage drift")
    cap_m = REFERENCE_CAP_KM * 1000 / (DAILY_CYCLES * DESIGN_DAYS)
    minimum = result["minimum_joint_distance_m"]
    result.update(
        status="PASS_TARGETED_PHYSICAL_DISTANCE_CERTIFICATE_NO_SELECTION",
        scoped_domain="PINNED_288_ATOMIC_REALIZATIONS_HUB_ROOTED_CLOSED_WALKS",
        input_sha256=hashes,
        via_way_evidence_sha256=sha256_file(evidence),
        policy_sha256=PINNED,
        hub_stop_id=HUB, brivio_stop_id=BRIVIO,
        santa_maria_stop_ids=list(SANTA),
        minimum_joint_available_stop_ids=available_stops,
        reference_cap_km=str(REFERENCE_CAP_KM),
        design_daily_cycles=DAILY_CYCLES,
        design_annual_days=DESIGN_DAYS,
        implied_per_cycle_cap_m=str(cap_m),
        joint_physical_cycle_within_reference_cap_exists=(
            minimum is not None and Decimal(minimum) <= cap_m),
        stop_identity_is_ordered_service_event_guarantee=False,
        candidate_domain_complete=False,
        primary_selection_authorised=False,
        runner_up_selection_authorised=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(result))
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.inputs, args.via_way_evidence, args.output)
