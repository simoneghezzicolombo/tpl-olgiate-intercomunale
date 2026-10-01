"""Non-decisional typed one-line and exact walking audit of a physical witness."""
import argparse
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
from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences
from src.phase2_rt031_single_line_binding_v3 import certify_single_public_line


WITNESS_SHA256 = "f10f87c4c78f3f39ac5d80615e049acc84a0822ac02d991425b418da980f692c"
CURRENT_SHA256 = "3abd5a2c5bb4a8419b4e65cfb2ce63cb6a855fe30087a4c57f4a560ae50c30f5"
CURRENT_PATH = Path("outputs/phase2/rt031_expanded_pool_current_v4_v3/expanded_pool_current_v4_audit.json")
PROFILE = "RT031_JOINT_TARGET_MIN_PHYSICAL_CANDIDATE_V3"


def main(args):
    if sha256_file(args.witness) != WITNESS_SHA256:
        raise ValueError("joint physical witness lineage drift")
    if sha256_file(args.walk_matrix) != WALK_SHA256:
        raise ValueError("walking substrate lineage drift")
    if sha256_file(CURRENT_PATH) != CURRENT_SHA256:
        raise ValueError("current exact-identity baseline lineage drift")
    physical = json.loads(args.witness.read_text(encoding="utf-8"))
    if (physical.get("contract") != "RT031_JOINT_TARGET_SHORTEST_PHYSICAL_CYCLE_V3"
            or physical.get("joint_physical_cycle_within_reference_cap_exists") is not True
            or physical.get("public_service_certified") is not False
            or physical.get("network_selected") is not False):
        raise ValueError("joint physical witness contract drift")
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
    witness = {
        "realization_ids": physical["minimum_joint_realization_ids"],
        "available_stop_ids": physical["minimum_joint_available_stop_ids"],
        "minimum_found_distance_m": physical["minimum_joint_distance_m"],
    }
    network = build_candidate(
        {"selected_witnesses": [witness],
         "minimum_found_total_distance_m": physical["minimum_joint_distance_m"]},
        catalog=catalog, boundary=boundary, oracle=scoped.oracle,
        bound=bound, profile_id=PROFILE,
        design_evidence="RT031_JOINT_TARGET_CANDIDATE_DECLARATION_NOT_OBSERVED",
        terminate_cycle_seam=True)
    route = certify_single_public_line(
        network, public_route_id="RT031_ONE_LINE::JOINT_TARGET_MIN_PHYSICAL_V3")
    component = next(iter(network["payload"]["components"].values()))
    ordered_stops = [event["source_visit"]["source_visit"]["source_occurrence"]
                     ["stop_place_id"] for event in component["events"]]
    if set(ordered_stops) != set(witness["available_stop_ids"]):
        raise AssertionError("typed service event stop union differs from physical witness")

    raw_walk = pd.read_csv(args.walk_matrix,
                           dtype={"population_weight_2025": str})
    weight_map = (raw_walk[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw_walk)
    weights = [weight_map[value] for value in
               substrate.population_meta["population_unit_id"]]
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    current_stops = current["current_exact_identity_subset"]["mapped_stop_place_ids"]
    codes, totals, municipal = detailed_threshold_vectors(
        (witness["available_stop_ids"], current_stops), substrate, weights)
    thresholds = (5, 8, 10)
    comparison = {
        "total": {
            str(t): {"candidate": str(totals[0, i]),
                     "current_exact_id_structural_subset": str(totals[1, i])}
            for i, t in enumerate(thresholds)},
        "municipal": {
            code: {"name": MUNICIPALITY_NAMES[code],
                   "thresholds": {
                       str(t): {"candidate": str(municipal[0, j, i]),
                                "current_exact_id_structural_subset":
                                    str(municipal[1, j, i])}
                       for i, t in enumerate(thresholds)}}
            for j, code in enumerate(codes)},
    }
    output = {
        "contract": "RT031_JOINT_TARGET_TYPED_ACCESS_DIAGNOSTIC_V3",
        "status": "PASS_NON_DECISIONAL_TYPED_CANDIDATE_DIAGNOSTIC",
        "input_sha256": {"physical_witness": WITNESS_SHA256,
                         "walking_substrate": WALK_SHA256,
                         "current_exact_id_audit": CURRENT_SHA256,
                         **hashes},
        "public_line_structure": route,
        "ordered_service_stop_ids": ordered_stops,
        "ordered_service_event_count": len(component["events"]),
        "available_stop_ids": witness["available_stop_ids"],
        "retained_current_exact_stop_ids": sorted(
            set(witness["available_stop_ids"]) & set(current_stops)),
        "potential_walking_access_same_substrate": comparison,
        "typed_network": network,
        "timetable_assigned": False,
        "vehicle_block_plan_assigned": False,
        "observed_dwell_available": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(output))
    print(json.dumps({k: v for k, v in output.items() if k != "typed_network"},
                     sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
