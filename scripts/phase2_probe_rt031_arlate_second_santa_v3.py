"""Exact second-Santa-stop physical probe for Arlate/Rovagnate witnesses."""
import argparse
from decimal import Decimal
from itertools import combinations
import json
from pathlib import Path

from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    FrozenRT017ViaNodeAdapter, RT023ScopedTransitionOracle,
    build_boundary_catalog, build_pairwise_compatibility,
    build_realization_catalog, canonical, load_inputs, sha256_file,
    validate_via_way_evidence)
from scripts.phase2_bind_rt031_joint_target_witness_v3 import (
    CURRENT_PATH, CURRENT_SHA256)
from scripts.phase2_screen_rt031_resource_budget_v3 import PINNED
from src.phase2_rt031_joint_target_shortest_cycle_v3 import shortest_joint_cycle
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import (
    evaluate_realization_chain, LEGAL)


SOURCE_SHA256 = "3cb560e4c99160acff586f07afd10f2c63a53e48076646fda45288d66982f4bc"
HUB = "FROZEN::L00407"
BRIVIO = "FROZEN::300063"
SANTA = ("FROZEN::300782", "FROZEN::300805", "FROZEN::300873")
ARLATE = "ASF::ARLATE_CANTINA_PIROVANO"
ROVAGNATE = "FROZEN::300879"
CAP_M = Decimal("111419") * 1000 / (20 * 260)


def target_sets(source):
    if (source.get("contract") != "RT031_ARLATE_RETENTION_TARGET_PROBES_V3"
            or source.get("retention_subset_size") != 3
            or source.get("required_additional_current_stop_id") != ROVAGNATE
            or source.get("probe_count") != 22
            or source.get("network_selected") is not False):
        raise ValueError("Rovagnate retention source drift")
    selected = [row for row in source["probes"]
                if row["arlate_stop_id"] == ARLATE
                and len(row["additional_current_exact_stop_ids"]) == 3
                and row["within_conditional_reference_cap"]]
    if len(selected) != 3:
        raise ValueError("three under-reference Cantina/Rovagnate target sets required")
    sets = sorted({tuple(row["additional_current_exact_stop_ids"])
                   for row in selected})
    if len(sets) != 3 or any(ROVAGNATE not in stops for stops in sets):
        raise ValueError("under-reference target identity drift")
    return sets


def main(args):
    if (sha256_file(args.source) != SOURCE_SHA256
            or sha256_file(CURRENT_PATH) != CURRENT_SHA256):
        raise ValueError("second-Santa probe lineage drift")
    source = json.loads(args.source.read_text(encoding="utf-8"))
    sets = target_sets(source)
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    current_stops = set(current["current_exact_identity_subset"]["mapped_stop_place_ids"])
    tables, hashes = load_inputs(args.inputs)
    validate_via_way_evidence(args.via_way_evidence)
    for path, digest in PINNED.items():
        if sha256_file(Path(path)) != digest:
            raise ValueError("approved policy lineage changed")
    catalog, _ = build_realization_catalog(
        tables["patterns"], tables["corridors"], tables["edges"])
    boundary = build_boundary_catalog(
        tables["patterns"], tables["occurrences"],
        tables["corridors"], tables["edges"])
    adapter = FrozenRT017ViaNodeAdapter(
        tables["edges"], tables["rules"], unresolved_external_via_way_count=2)
    scoped = RT023ScopedTransitionOracle(
        adapter, sorted({edge for row in catalog.values()
                         for edge in row["edge_ids"]}),
        successor_via_way_irrelevance_certified=True,
        evidence_id="RT031_SUCCESSOR_VIA_WAY::"
        + sha256_file(args.via_way_evidence))
    for row in catalog.values():
        if evaluate_realization_chain([row], boundary, scoped.oracle)["status"] != LEGAL:
            raise ValueError("atomic legality open")
    pairs = build_pairwise_compatibility(
        catalog, boundary, scoped.oracle, history_locality_certified=True)
    edges = {row["edge_id"]: row for row in tables["edges"]}
    weights = {
        rid: sum((Decimal(edges[edge]["length_m"])
                  for edge in row["edge_ids"]), Decimal(0))
        for rid, row in catalog.items()}
    stop_sets = {row["realization_id"]:
                 row["ordered_passenger_stop_ids"].split(";")
                 for row in tables["patterns"]}
    probes = []
    for retained in sets:
        for santa_pair in combinations(SANTA, 2):
            groups = ((ARLATE,),) + tuple((stop,) for stop in retained)
            groups += tuple((stop,) for stop in santa_pair)
            result = shortest_joint_cycle(
                catalog, pairs, weights, stop_sets,
                hub_stop_id=HUB, brivio_stop_id=BRIVIO,
                santa_maria_stop_ids=SANTA,
                additional_target_groups=groups,
                history_locality_certified=True,
                atomic_legality_certified=True)
            path = result["minimum_joint_realization_ids"]
            stops = sorted(set().union(*(set(stop_sets[rid]) for rid in path))) if path else []
            if path:
                selected = [catalog[rid] for rid in path]
                if evaluate_realization_chain(
                        selected + [selected[0]], boundary, scoped.oracle)["status"] != LEGAL:
                    raise AssertionError("physical cycle fails full-history replay")
                if not ({HUB, BRIVIO, ARLATE} | set(retained) | set(santa_pair)) <= set(stops):
                    raise AssertionError("second-Santa target drift")
            distance = result["minimum_joint_distance_m"]
            probes.append({
                "required_current_exact_stop_ids": list(retained),
                "required_santa_pair_stop_ids": list(santa_pair),
                "minimum_distance_m": distance,
                "within_conditional_reference_cap":
                    distance is not None and Decimal(distance) <= CAP_M,
                "minimum_witness_realization_ids": path,
                "minimum_witness_available_stop_ids": stops,
                "minimum_witness_retained_current_exact_stop_count":
                    len(set(stops) & current_stops),
                "settled_target_states": result["settled_target_states"],
                "target_distance_optimality_certified":
                    result["search_exhaustive_for_target"],
            })
    output = {
        "contract": "RT031_ARLATE_ROVAGNATE_SECOND_SANTA_PROBES_V3",
        "status": "PASS_TARGET_SCOPED_EXACT_DISTANCE_NO_SELECTION",
        "input_sha256": {"rovagnate_retention_probes": SOURCE_SHA256,
                         "current_exact_id_audit": CURRENT_SHA256,
                         "via_way_evidence": sha256_file(args.via_way_evidence),
                         **hashes, **PINNED},
        "conditional_reference_cap_m_per_cycle": str(CAP_M),
        "probe_count": len(probes),
        "under_reference_count": sum(row["within_conditional_reference_cap"]
                                     for row in probes),
        "probes": probes,
        "target_sets_are_diagnostic_not_candidate_admission_rule": True,
        "probe_family_is_exhaustive_access_frontier": False,
        "stop_identity_is_ordered_service_event_guarantee": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
