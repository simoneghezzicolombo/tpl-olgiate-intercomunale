"""Typed one-line and exact walking audit of second-Santa Arlate witnesses."""
import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
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


SOURCE_SHA256 = "3aeef2ae9b17da85ceaf1e1d6ef5be104e346fcd88b102e4cfcdf1acda302656"
THRESHOLDS = (5, 8, 10)


def selected_rows(source):
    if (source.get("contract") != "RT031_ARLATE_ROVAGNATE_SECOND_SANTA_PROBES_V3"
            or source.get("probe_count") != 9
            or source.get("under_reference_count") != 2
            or source.get("network_selected") is not False
            or source.get("primary_selection_authorised") is not False
            or source.get("runner_up_selection_authorised") is not False):
        raise ValueError("second-Santa physical probe contract drift")
    rows = [row for row in source["probes"]
            if row["within_conditional_reference_cap"]]
    if len(rows) != 2 or len({tuple(row["minimum_witness_realization_ids"])
                              for row in rows}) != 2:
        raise ValueError("two distinct under-reference physical paths required")
    if any(row["minimum_witness_retained_current_exact_stop_count"] < 7
           or not {"FROZEN::300782", "FROZEN::300805"} <= set(
               row["minimum_witness_available_stop_ids"])
           for row in rows):
        raise ValueError("second-Santa current-stop retention drift")
    return rows


def main(args):
    if (sha256_file(args.source) != SOURCE_SHA256
            or sha256_file(args.walk_matrix) != WALK_SHA256
            or sha256_file(CURRENT_PATH) != CURRENT_SHA256):
        raise ValueError("physical, walking, or current lineage drift")
    source = json.loads(args.source.read_text(encoding="utf-8"))
    rows = selected_rows(source)
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
        path = row["minimum_witness_realization_ids"]
        identity = "PATH_" + hashlib.sha256(";".join(path).encode()).hexdigest()[:20]
        physical = {
            "realization_ids": path,
            "available_stop_ids": row["minimum_witness_available_stop_ids"],
            "minimum_found_distance_m": row["minimum_distance_m"],
        }
        network = build_candidate(
            {"selected_witnesses": [physical],
             "minimum_found_total_distance_m": row["minimum_distance_m"]},
            catalog=catalog, boundary=boundary, oracle=scoped.oracle,
            bound=bound, profile_id="RT031_ARLATE_SECOND_SANTA::" + identity,
            design_evidence="RT031_ARLATE_SECOND_SANTA_PROBE_NOT_OBSERVED",
            terminate_cycle_seam=True)
        route = certify_single_public_line(
            network, public_route_id="RT031_ONE_LINE::" + identity)
        if route["single_recognizable_line_structure_certified"] is not True:
            raise AssertionError("one public line not certified")
        component = next(iter(network["payload"]["components"].values()))
        ordered = [event["source_visit"]["source_visit"]["source_occurrence"]
                   ["stop_place_id"] for event in component["events"]]
        if set(ordered) != set(physical["available_stop_ids"]):
            raise AssertionError("ordered service event stop union drift")
        typed.append({
            "path_id": identity,
            "required_current_exact_stop_ids":
                row["required_current_exact_stop_ids"],
            "required_santa_pair_stop_ids": row["required_santa_pair_stop_ids"],
            "public_route_id": route["public_route_id"],
            "single_recognizable_line_structure_certified": True,
            "passenger_service_continuity_scope":
                route["passenger_service_continuity_scope"],
            "ordered_service_stop_ids": ordered,
            "ordered_service_event_count": len(component["events"]),
            "available_stop_ids": physical["available_stop_ids"],
            "realization_ids": path,
            "distance_m": physical["minimum_found_distance_m"],
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
    frontier = exact_pareto_indices(benefits, costs)
    output = {
        "contract": "RT031_ARLATE_SECOND_SANTA_ONE_LINE_ACCESS_V3",
        "status": "PASS_PROBE_SCOPED_NON_DECISIONAL_PARETO",
        "input_sha256": {"second_santa_physical_probes": SOURCE_SHA256,
                         "walking_substrate": WALK_SHA256,
                         "current_exact_id_audit": CURRENT_SHA256,
                         "via_way_evidence": sha256_file(args.via_way_evidence),
                         **hashes},
        "typed_one_line_count": len(typed),
        "within_probe_pareto_path_ids": [typed[i]["path_id"] for i in frontier],
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
        "target_probes_are_not_exhaustive_access_frontier": True,
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
    args.output.write_bytes(canonical(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
