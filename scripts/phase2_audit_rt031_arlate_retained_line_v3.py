"""Typed exact walking audit of all under-reference four-stop Arlate probes."""
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


PROBES_SHA256 = {
    3: "3cb560e4c99160acff586f07afd10f2c63a53e48076646fda45288d66982f4bc",
    4: "fbb68e4c1ffc04bd1b7421aff7dc9e490717b860bde3f945bf4268df2b0bba7a",
}
THRESHOLDS = (5, 8, 10)


def select_witnesses(source, subset_size=4):
    expected = {3: (22, "FROZEN::300879"), 4: (32, None)}
    if subset_size not in expected:
        raise ValueError("unknown retained-line probe size")
    count, required = expected[subset_size]
    if (source.get("contract") != "RT031_ARLATE_RETENTION_TARGET_PROBES_V3"
            or source.get("retention_subset_size") != subset_size
            or source.get("probe_count") != count
            or source.get("required_additional_current_stop_id") != required
            or source.get("candidate_domain_complete") is not False
            or source.get("network_selected") is not False
            or source.get("primary_selection_authorised") is not False
            or source.get("runner_up_selection_authorised") is not False):
        raise ValueError("four-stop probe contract drift")
    selected = [row for row in source["probes"]
                if row["additional_current_exact_stop_ids"]
                and row["within_conditional_reference_cap"]]
    by_path = {}
    for row in selected:
        if (row["arlate_stop_id"] not in row["minimum_witness_available_stop_ids"]
                or not set(row["additional_current_exact_stop_ids"]) <= set(
                    row["minimum_witness_available_stop_ids"])):
            raise ValueError("probe target absent from minimum witness")
        path = tuple(row["minimum_witness_realization_ids"])
        if not path:
            raise ValueError("within-cap probe has no physical witness")
        if path in by_path:
            previous = by_path[path]
            if (previous["minimum_distance_m"] != row["minimum_distance_m"]
                    or previous["minimum_witness_available_stop_ids"]
                    != row["minimum_witness_available_stop_ids"]):
                raise ValueError("same physical path has conflicting evidence")
            previous["probe_target_sets"].append(
                row["additional_current_exact_stop_ids"])
            if row["arlate_stop_id"] not in previous["arlate_target_stop_ids"]:
                previous["arlate_target_stop_ids"].append(row["arlate_stop_id"])
        else:
            by_path[path] = {**row,
                             "arlate_target_stop_ids": [row["arlate_stop_id"]],
                             "probe_target_sets": [
                                 row["additional_current_exact_stop_ids"]]}
    return [by_path[path] for path in sorted(by_path)]


def main(args):
    if (sha256_file(args.probes) != PROBES_SHA256[args.retention_subset_size]
            or sha256_file(args.walk_matrix) != WALK_SHA256
            or sha256_file(CURRENT_PATH) != CURRENT_SHA256):
        raise ValueError("probe, walking, or current lineage drift")
    source = json.loads(args.probes.read_text(encoding="utf-8"))
    witnesses = select_witnesses(source, args.retention_subset_size)
    if not witnesses:
        raise ValueError("no under-reference four-stop physical witnesses")

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
    for row in witnesses:
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
            bound=bound, profile_id="RT031_ARLATE_RETENTION::" + identity,
            design_evidence="RT031_ARLATE_RETENTION_PROBE_NOT_OBSERVED",
            terminate_cycle_seam=True)
        route = certify_single_public_line(
            network, public_route_id="RT031_ONE_LINE::" + identity)
        if route["single_recognizable_line_structure_certified"] is not True:
            raise AssertionError("single recognizable public line not certified")
        component = next(iter(network["payload"]["components"].values()))
        ordered = [event["source_visit"]["source_visit"]["source_occurrence"]
                   ["stop_place_id"] for event in component["events"]]
        if set(ordered) != set(physical["available_stop_ids"]):
            raise AssertionError("typed ordered service stop union drift")
        typed.append({
            "path_id": identity,
            "arlate_target_stop_ids": row["arlate_target_stop_ids"],
            "probe_target_sets": row["probe_target_sets"],
            "public_route_id": route["public_route_id"],
            "single_recognizable_line_structure_certified":
                route["single_recognizable_line_structure_certified"],
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
    frontier_indices = exact_pareto_indices(benefits, costs)
    output = {
        "contract": "RT031_ARLATE_RETAINED_ONE_LINE_ACCESS_FRONTIER_V3",
        "status": "PASS_PROBE_SCOPED_NON_DECISIONAL_PARETO",
        "input_sha256": {"retention_probes": PROBES_SHA256[args.retention_subset_size],
                         "walking_substrate": WALK_SHA256,
                         "current_exact_id_audit": CURRENT_SHA256,
                         "via_way_evidence": sha256_file(args.via_way_evidence),
                         **hashes},
        "under_reference_probe_count": sum(
            bool(row["additional_current_exact_stop_ids"])
            and row["within_conditional_reference_cap"]
            for row in source["probes"]),
        "retention_subset_size": args.retention_subset_size,
        "required_additional_current_stop_id":
            source.get("required_additional_current_stop_id"),
        "distinct_typed_path_count": len(typed),
        "single_recognizable_line_count": sum(
            row["single_recognizable_line_structure_certified"] for row in typed),
        "within_probe_pareto_count": len(frontier_indices),
        "within_probe_pareto_path_ids": [typed[i]["path_id"]
                                         for i in frontier_indices],
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
        "target_probes_are_not_exhaustive_access_frontier": True,
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
    parser.add_argument("--probes", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retention-subset-size", type=int, default=4,
                        choices=sorted(PROBES_SHA256))
    main(parser.parse_args())
