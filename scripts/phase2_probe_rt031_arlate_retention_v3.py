"""Target-specific lower bounds for preserving current stops via inner Arlate.

These probes are not an exhaustive access frontier or a route selection.
"""
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


HUB = "FROZEN::L00407"
BRIVIO = "FROZEN::300063"
SANTA = ("FROZEN::300782", "FROZEN::300805", "FROZEN::300873")
ARLATE = ("ASF::ARLATE_BIVIO_PER_IL_PAESE",
          "ASF::ARLATE_CANTINA_PIROVANO")
REFERENCE_CAP_KM = Decimal("111419")
DAILY_CYCLES = 20
DESIGN_DAYS = 260


def probe_targets(current_stops, subset_size=1, must_include_stop_id=None):
    """Separate exact-stop probes; no stop-retention admission filter."""
    extra = sorted(set(current_stops) - {HUB, BRIVIO} - set(SANTA))
    if not 1 <= subset_size <= len(extra):
        raise ValueError("retention subset size outside the available exact IDs")
    if must_include_stop_id is not None and must_include_stop_id not in extra:
        raise ValueError("required diagnostic stop is not an additional exact ID")
    return [(arlate, ()) for arlate in ARLATE] + [
        (arlate, stops) for arlate in ARLATE
        for stops in combinations(extra, subset_size)
        if must_include_stop_id is None or must_include_stop_id in stops]


def main(args):
    if sha256_file(CURRENT_PATH) != CURRENT_SHA256:
        raise ValueError("current exact-ID baseline lineage drift")
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    current_stops = current["current_exact_identity_subset"]["mapped_stop_place_ids"]
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
        tables["edges"], tables["rules"],
        unresolved_external_via_way_count=2)
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
    cap_m = REFERENCE_CAP_KM * 1000 / (DAILY_CYCLES * DESIGN_DAYS)
    probes = []
    for arlate, retained_stops in probe_targets(
            current_stops, args.retention_subset_size,
            args.must_include_current_stop_id):
        groups = ((arlate,),) + tuple((stop,) for stop in retained_stops)
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
            if not ({HUB, BRIVIO, arlate} <= set(stops)
                    and set(stops) & set(SANTA)
                    and set(retained_stops) <= set(stops)):
                raise AssertionError("target stop set drift")
        distance = result["minimum_joint_distance_m"]
        probes.append({
            "arlate_stop_id": arlate,
            "additional_current_exact_stop_ids": list(retained_stops),
            "minimum_distance_m": distance,
            "within_conditional_reference_cap":
                distance is not None and Decimal(distance) <= cap_m,
            "minimum_witness_realization_ids": path,
            "minimum_witness_available_stop_ids": stops,
            "minimum_witness_retained_current_exact_stop_ids": sorted(
                set(stops) & set(current_stops)),
            "minimum_witness_retained_current_exact_stop_count": len(
                set(stops) & set(current_stops)),
            "settled_target_states": result["settled_target_states"],
            "target_distance_optimality_certified":
                result["search_exhaustive_for_target"],
        })
    output = {
        "contract": "RT031_ARLATE_RETENTION_TARGET_PROBES_V3",
        "status": "PASS_TARGET_SCOPED_EXACT_DISTANCE_NO_SELECTION",
        "input_sha256": {**hashes,
                         "via_way_evidence": sha256_file(args.via_way_evidence),
                         "current_exact_id_audit": CURRENT_SHA256,
                         **PINNED},
        "scoped_domain": "PINNED_288_ATOMIC_REALIZATIONS_HUB_ROOTED_CLOSED_WALKS",
        "probe_count": len(probes),
        "retention_subset_size": args.retention_subset_size,
        "required_additional_current_stop_id":
            args.must_include_current_stop_id,
        "conditional_reference_cap_m_per_cycle": str(cap_m),
        "conditional_daily_cycles": DAILY_CYCLES,
        "conditional_annual_days": DESIGN_DAYS,
        "probes": probes,
        "additional_current_stop_is_diagnostic_target_not_candidate_admission_rule": True,
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
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retention-subset-size", type=int, default=1)
    parser.add_argument("--must-include-current-stop-id")
    main(parser.parse_args())
