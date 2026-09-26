"""Typed, exact-rational, no-weight audit of 500k-found joint corridors."""
import argparse
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_real_occurrence_binding_v3 import EPOCH
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    FrozenRT017ViaNodeAdapter, RT023ScopedTransitionOracle,
    build_boundary_catalog, build_realization_catalog, canonical,
    load_inputs, sha256_file, validate_via_way_evidence)
from scripts.phase2_bind_rt031_target_cover_service_v3 import (
    STOP_ATTACHMENTS_SHA256, build_candidate, read_rows)
from scripts.phase2_build_rt031_municipal_access_frontier_v4 import (
    detailed_threshold_vectors, MUNICIPALITY_NAMES, WALK_SHA256)
from scripts.phase2_bind_rt031_joint_target_witness_v3 import (
    CURRENT_PATH, CURRENT_SHA256)
from src.phase2_rt031_municipal_access_frontier_v4 import exact_pareto_indices
from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences
from src.phase2_rt031_single_line_binding_v3 import certify_single_public_line


SEARCH_SHA256 = "11353efb3609cdd9d5c464a685697e34838a30f32d0f70e6a1fe71cbabe31c89"
JOINT_AUDIT_SHA256 = "987891ece8f520570a6ad8267aaa02ff4b751c09a1bc5de6f2880ec95d8e7f82"
HUB = "FROZEN::L00407"
BRIVIO = "FROZEN::300063"
SANTA = frozenset(("FROZEN::300782", "FROZEN::300805", "FROZEN::300873"))
THRESHOLDS = (5, 8, 10)


def main(args):
    if (sha256_file(args.search) != SEARCH_SHA256
            or sha256_file(args.joint_audit) != JOINT_AUDIT_SHA256
            or sha256_file(args.walk_matrix) != WALK_SHA256
            or sha256_file(CURRENT_PATH) != CURRENT_SHA256):
        raise ValueError("joint search or walking/current lineage drift")
    search = json.loads(args.search.read_text(encoding="utf-8"))
    audit = json.loads(args.joint_audit.read_text(encoding="utf-8"))
    if (search.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or search.get("exhaustive") is not False
            or search.get("expanded_states") != 500000
            or search.get("required_root_stop_id") != HUB
            or audit.get("joint_brivio_at_least_one_santa_maria_candidate_count") != 99
            or audit.get("search_exhaustive") is not False):
        raise ValueError("bounded discovery contract drift")
    found = {row["stop_set_id"]: row for row in search["candidates"]}
    ids = audit["joint_candidate_stop_set_ids"]
    if len(set(ids)) != 99 or not set(ids) <= set(found):
        raise ValueError("joint witness identity drift")
    rows = [found[identity] for identity in ids]
    if any(not ({HUB, BRIVIO} <= set(row["available_stop_ids"])
                and set(row["available_stop_ids"]) & SANTA) for row in rows):
        raise ValueError("joint physical target drift")

    tables, hashes = load_inputs(args.inputs)
    validate_via_way_evidence(args.via_way_evidence)
    stop_path = args.inputs / "rt022" / "stop_attachments.csv"
    if sha256_file(stop_path) != STOP_ATTACHMENTS_SHA256:
        raise ValueError("stop attachment lineage drift")
    tables["stops"] = read_rows(stop_path)
    bound = bind_occurrences(
        patterns=tables["patterns"], occurrences=tables["occurrences"],
        corridors=tables["corridors"], edges=tables["edges"],
        stops=tables["stops"], epoch=EPOCH)
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
    typed = []
    for row in rows:
        identity = row["stop_set_id"]
        profile = "RT031_JOINT_DISCOVERY::" + identity
        network = build_candidate(
            {"selected_witnesses": [row],
             "minimum_found_total_distance_m": row["minimum_found_distance_m"]},
            catalog=catalog, boundary=boundary, oracle=scoped.oracle,
            bound=bound, profile_id=profile,
            design_evidence="RT031_JOINT_DISCOVERY_CANDIDATE_NOT_OBSERVED",
            terminate_cycle_seam=True)
        route = certify_single_public_line(
            network, public_route_id="RT031_ONE_LINE::" + identity)
        component = next(iter(network["payload"]["components"].values()))
        stops = [event["source_visit"]["source_visit"]["source_occurrence"]
                 ["stop_place_id"] for event in component["events"]]
        if set(stops) != set(row["available_stop_ids"]):
            raise AssertionError("typed ordered event stop union drift")
        typed.append({
            "stop_set_id": identity,
            "public_route_id": route["public_route_id"],
            "single_recognizable_line_structure_certified":
                route["single_recognizable_line_structure_certified"],
            "passenger_service_continuity_scope":
                route["passenger_service_continuity_scope"],
            "ordered_service_stop_ids": stops,
            "ordered_service_event_count": len(component["events"]),
            "available_stop_ids": row["available_stop_ids"],
            "realization_ids": row["realization_ids"],
            "distance_m": row["minimum_found_distance_m"],
        })

    raw = pd.read_csv(args.walk_matrix,
                      dtype={"population_weight_2025": str})
    weight_map = (raw[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw)
    weights = [weight_map[value] for value in
               substrate.population_meta["population_unit_id"]]
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    current_stops = current["current_exact_identity_subset"]["mapped_stop_place_ids"]
    codes, totals, municipal = detailed_threshold_vectors(
        [row["available_stop_ids"] for row in typed] + [current_stops],
        substrate, weights)
    baseline = len(typed)
    benefits, costs = [], []
    for index, row in enumerate(typed):
        retention = sorted(set(row["available_stop_ids"]) & set(current_stops))
        row["retained_current_exact_stop_ids"] = retention
        row["retained_current_exact_stop_count"] = len(retention)
        row["exact_total_coverage"] = {
            str(t): str(totals[index, j]) for j, t in enumerate(THRESHOLDS)}
        row["exact_municipality_coverage"] = {
            code: {str(t): str(municipal[index, k, j])
                   for j, t in enumerate(THRESHOLDS)}
            for k, code in enumerate(codes)}
        benefits.append(tuple(totals[index])
                        + tuple(municipal[index].reshape(-1))
                        + (Fraction(len(retention), len(current_stops)),))
        costs.append(Decimal(row["distance_m"]))
    frontier_indices = exact_pareto_indices(benefits, costs)
    summary = {
        "contract": "RT031_JOINT_DISCOVERY_TYPED_FRONTIER_V3",
        "status": "PASS_POOL_SCOPED_NON_DECISIONAL_PARETO",
        "input_sha256": {"physical_search": SEARCH_SHA256,
                         "joint_audit": JOINT_AUDIT_SHA256,
                         "walking_substrate": WALK_SHA256,
                         "current_exact_id_audit": CURRENT_SHA256,
                         **hashes},
        "source_search_exhaustive": False,
        "candidate_count": len(typed),
        "typed_single_public_line_count": sum(
            row["single_recognizable_line_structure_certified"] for row in typed),
        "exact_within_found_set_pareto_count": len(frontier_indices),
        "exact_within_found_set_pareto_stop_set_ids": [
            typed[i]["stop_set_id"] for i in frontier_indices],
        "pareto_axes": ["total_potential_walk_5_8_10",
                        "each_municipality_potential_walk_5_8_10",
                        "current_exact_stop_retention_preference",
                        "physical_distance_cost"],
        "current_exact_id_structural_subset": {
            "total": {str(t): str(totals[baseline, j])
                      for j, t in enumerate(THRESHOLDS)},
            "municipal": {
                code: {"name": MUNICIPALITY_NAMES[code],
                       "coverage": {str(t): str(municipal[baseline, k, j])
                                    for j, t in enumerate(THRESHOLDS)}}
                for k, code in enumerate(codes)}},
        "candidates": typed,
        "coverage_is_potential_walking_not_observed_passenger_demand": True,
        "stop_retention_is_preference_not_filter": True,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "timetable_assigned": False,
        "vehicle_block_plan_assigned": False,
        "candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(summary))
    print(json.dumps({k: v for k, v in summary.items() if k != "candidates"},
                     sort_keys=True))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", type=Path, required=True)
    parser.add_argument("--joint-audit", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
