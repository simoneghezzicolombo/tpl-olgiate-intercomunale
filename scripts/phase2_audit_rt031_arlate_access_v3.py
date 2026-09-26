"""Exact potential walking comparison for two physical Arlate probes."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_bind_rt031_joint_target_witness_v3 import (
    CURRENT_PATH, CURRENT_SHA256)
from scripts.phase2_build_rt031_municipal_access_frontier_v4 import (
    detailed_threshold_vectors, MUNICIPALITY_NAMES, WALK_SHA256)


ARLATE_AUDIT_SHA256 = "a1404b6e963e4e05c0c34b5be22934c5e124076182b2585915c11885105b93ca"
THRESHOLDS = (5, 8, 10)


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def main(args):
    if (hashlib.sha256(args.arlate_audit.read_bytes()).hexdigest()
            != ARLATE_AUDIT_SHA256
            or hashlib.sha256(args.walk_matrix.read_bytes()).hexdigest()
            != WALK_SHA256
            or hashlib.sha256(CURRENT_PATH.read_bytes()).hexdigest()
            != CURRENT_SHA256):
        raise ValueError("Arlate or walking/current lineage drift")
    source = json.loads(args.arlate_audit.read_text(encoding="utf-8"))
    if (source.get("contract")
            != "RT031_ARLATE_VILLAGE_PHYSICAL_EXTENSION_AUDIT_V3"
            or len(source.get("alternatives", ())) != 2
            or source.get("network_selected") is not False):
        raise ValueError("Arlate physical target contract drift")
    alternatives = source["alternatives"]
    targets = {tuple(row["additional_any_stop_ids"]) for row in alternatives}
    if targets != {("ASF::ARLATE_BIVIO_PER_IL_PAESE",),
                   ("ASF::ARLATE_CANTINA_PIROVANO",)}:
        raise ValueError("Arlate target identity drift")
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    current_stops = current["current_exact_identity_subset"][
        "mapped_stop_place_ids"]
    raw = pd.read_csv(args.walk_matrix,
                      dtype={"population_weight_2025": str})
    weight_map = (raw[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")
                  ["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw)
    weights = [weight_map[value] for value in
               substrate.population_meta["population_unit_id"]]
    sets = [row["minimum_joint_available_stop_ids"]
            for row in alternatives] + [current_stops]
    codes, totals, municipal = detailed_threshold_vectors(
        sets, substrate, weights)
    baseline = len(alternatives)
    profiles = []
    for i, row in enumerate(alternatives):
        profiles.append({
            "additional_stop_id": row["additional_any_stop_ids"][0],
            "minimum_physical_distance_m": row["minimum_joint_distance_m"],
            "available_stop_ids": row["minimum_joint_available_stop_ids"],
            "retained_current_exact_stop_ids": sorted(
                set(row["minimum_joint_available_stop_ids"])
                & set(current_stops)),
            "exact_total_potential_walk": {
                str(t): str(totals[i, j]) for j, t in enumerate(THRESHOLDS)},
            "exact_municipal_potential_walk": {
                code: {str(t): str(municipal[i, k, j])
                       for j, t in enumerate(THRESHOLDS)}
                for k, code in enumerate(codes)},
        })
    output = {
        "contract": "RT031_ARLATE_PHYSICAL_WITNESS_ACCESS_AUDIT_V3",
        "status": "PASS_PHYSICAL_STOP_AVAILABILITY_ACCESS_DIAGNOSTIC",
        "input_sha256": {"arlate_physical_audit": ARLATE_AUDIT_SHA256,
                         "walking_substrate": WALK_SHA256,
                         "current_exact_id_audit": CURRENT_SHA256},
        "profiles": profiles,
        "current_exact_id_structural_subset": {
            "total": {str(t): str(totals[baseline, j])
                      for j, t in enumerate(THRESHOLDS)},
            "municipal": {
                code: {"name": MUNICIPALITY_NAMES[code],
                       "coverage": {
                           str(t): str(municipal[baseline, k, j])
                           for j, t in enumerate(THRESHOLDS)}}
                for k, code in enumerate(codes)}},
        "physical_stop_availability_is_public_service": False,
        "one_line_ordered_service_events_bound": False,
        "observed_passenger_demand_used": False,
        "candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(output))
    print(json.dumps(output, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arlate-audit", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
