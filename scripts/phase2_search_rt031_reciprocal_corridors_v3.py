#!/usr/bin/env python3
"""Search reciprocal open physical corridors and test broad access feasibility."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    FrozenRT017ViaNodeAdapter, RT023ScopedTransitionOracle, build_boundary_catalog,
    build_pairwise_compatibility, build_realization_catalog, load_inputs,
    sha256_file, validate_via_way_evidence,
)
from scripts.phase2_compare_rt031_movement_portfolios_v3 import threshold_vectors
from scripts.phase2_compare_rt031_with_current_baseline_v4 import (
    FINAL_STOPS_SHA256, V4_CLUSTERS_LOGICAL_SHA256, V4_VALIDATION_LOGICAL_SHA256,
    WALK_SHA256, logical_sha256, read_csv,
)
from scripts.phase2_screen_rt031_resource_budget_v3 import PINNED
from src.phase2_rt031_current_baseline_comparison_v3 import (
    DIMENSIONS, compare_with_structural_subset, exact_current_stop_subset,
)
from src.phase2_rt031_reciprocal_corridor_search_v3 import (
    reciprocal_availability_envelope, search_open_paths,
)
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import LEGAL, evaluate_realization_chain


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def main(args):
    if sha256_file(args.walk_matrix) != WALK_SHA256 or sha256_file(args.final_stops) != FINAL_STOPS_SHA256:
        raise ValueError("RT028 input drift")
    if logical_sha256(args.v4_clusters) != V4_CLUSTERS_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 cluster drift")
    if logical_sha256(args.v4_validation) != V4_VALIDATION_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 validation drift")
    validation = json.loads(args.v4_validation.read_text(encoding="utf-8"))
    if (validation.get("status") != "PASS_PHASE2_CURRENT_SERVICE_ACCESS_BASELINE_V4"
            or validation.get("current_service_baseline_complete") is not False):
        raise ValueError("Current-Service V4 is not admissible")
    tables, input_hashes = load_inputs(args.inputs)
    validate_via_way_evidence(args.via_way_evidence)
    for path, digest in PINNED.items():
        if sha256_file(Path(path)) != digest:
            raise ValueError("approved policy lineage drift")
    policy = json.loads(Path("config/phase2_final_policy_contract_v3.json").read_text())
    cap = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))
    budget = cap * 1000 / (32 * 260)

    catalog, _ = build_realization_catalog(tables["patterns"], tables["corridors"], tables["edges"])
    boundary = build_boundary_catalog(tables["patterns"], tables["occurrences"],
                                      tables["corridors"], tables["edges"])
    adapter = FrozenRT017ViaNodeAdapter(tables["edges"], tables["rules"],
                                       unresolved_external_via_way_count=2)
    scoped = RT023ScopedTransitionOracle(
        adapter, sorted({e for row in catalog.values() for e in row["edge_ids"]}),
        successor_via_way_irrelevance_certified=True,
        evidence_id="RT031_SUCCESSOR_VIA_WAY::" + sha256_file(args.via_way_evidence),
    )
    for row in catalog.values():
        if evaluate_realization_chain([row], boundary, scoped.oracle)["status"] != LEGAL:
            raise ValueError("atomic legality open")
    pairs = build_pairwise_compatibility(catalog, boundary, scoped.oracle,
                                         history_locality_certified=True)
    edges = {row["edge_id"]: row for row in tables["edges"]}
    weights = {rid: sum((Decimal(edges[e]["length_m"]) for e in row["edge_ids"]), Decimal(0))
               for rid, row in catalog.items()}
    stop_sets = {row["realization_id"]: row["ordered_passenger_stop_ids"].split(";")
                 for row in tables["patterns"]}
    search = search_open_paths(
        catalog, pairs, weights, stop_sets, budget_m=budget,
        max_expansions=args.max_expansions, history_locality_certified=True,
        atomic_legality_certified=True,
    )
    for row in search["paths"]:
        selected = [catalog[x] for x in row["realization_ids"]]
        if evaluate_realization_chain(selected, boundary, scoped.oracle)["status"] != LEGAL:
            raise AssertionError("open-path witness fails full-history replay")
    envelope = reciprocal_availability_envelope(search["paths"], shared_budget_m=budget)
    summaries = envelope.pop("availability_summaries")
    if not summaries:
        raise ValueError("no reciprocal open corridor fits the shared budget")

    raw = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw)
    exact_weights = [weight_map[x] for x in substrate.population_meta["population_unit_id"]]
    bridge = exact_current_stop_subset(read_csv(args.v4_clusters), read_csv(args.final_stops))
    baseline = tuple(threshold_vectors(
        [tuple(bridge["mapped_stop_place_ids"])], substrate, exact_weights,
    )[0])
    vectors = threshold_vectors([x["available_stop_ids"] for x in summaries], substrate, exact_weights)
    comparison_rows, broad = [], []
    for summary, vector in zip(summaries, vectors):
        row = {**summary, "exact_threshold_ratios": json.dumps([str(x) for x in vector])}
        comparison_rows.append(row)
        if all(x >= y for x, y in zip(vector, baseline)) and any(x > y for x, y in zip(vector, baseline)):
            broad.append({**summary,
                          "conditional_annual_carrier_km": str(Decimal(summary["distance_m"]) * 32 * 260 / 1000),
                          "exact_threshold_ratios": [str(x) for x in vector],
                          "display_threshold_shares": [float(x) for x in vector],
                          "public_service_assigned": False})
    comparison = compare_with_structural_subset(comparison_rows, baseline)
    broad.sort(key=lambda x: (Decimal(x["distance_m"]), x["available_stop_ids"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases_path = args.output_dir / "conditional_broad_access_reciprocal_corridors.json"
    cases_path.write_text(json.dumps(broad, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    dimensions = []
    for field, current, maximum in zip(DIMENSIONS, baseline, comparison["candidate_componentwise_maxima"]):
        dimensions.append({"dimension": field, "current_share": format(float(current), ".15f"),
                           "reciprocal_pool_maximum_share": format(float(maximum), ".15f"),
                           "reciprocal_minus_current_percentage_points": format(float((maximum-current)*100), ".9f")})
    dimension_path = args.output_dir / "reciprocal_corridor_dimension_comparison.csv"
    write_csv(dimension_path, dimensions, list(dimensions[0]))

    search_audit = {k: v for k, v in search.items() if k != "paths"}
    status = ("CONDITIONAL_BROAD_ACCESS_RECIPROCAL_CORRIDORS_FOUND" if broad else
              "NO_BROAD_ACCESS_RECIPROCAL_CORRIDOR_IN_BOUNDED_POOL")
    payload = {
        "contract": "RT031_RECIPROCAL_OPEN_CORRIDOR_ACCESS_FEASIBILITY_V3",
        "status": status,
        "conclusion": ("RECIPROCAL_CORRIDORS_REQUIRE_TYPED_SERVICE_BINDING" if broad else
                       "BOUNDED_RECIPROCAL_CORRIDOR_POOL_DOES_NOT_ESTABLISH_REPLACEMENT"),
        "search": search_audit,
        "reciprocal_envelope": envelope,
        "unique_availability_set_count": len(summaries),
        "comparison": {k: (dict(zip(DIMENSIONS, map(str, value)))
                          if k == "candidate_componentwise_maxima" else value)
                       for k, value in comparison.items()},
        "conditional_broad_access_case_count": len(broad),
        "current_exact_identity_subset": bridge,
        "current_exact_threshold_ratios": dict(zip(DIMENSIONS, map(str, baseline))),
        "input_sha256": {**input_hashes, "via_way": sha256_file(args.via_way_evidence),
                         "walk_matrix": WALK_SHA256, "final_stops": FINAL_STOPS_SHA256,
                         "v4_clusters_logical": V4_CLUSTERS_LOGICAL_SHA256,
                         "v4_validation_logical": V4_VALIDATION_LOGICAL_SHA256},
        "output_sha256": {cases_path.name: sha256_file(cases_path),
                          dimension_path.name: sha256_file(dimension_path)},
        "candidate_coverage_semantics": "POTENTIAL_IF_STOPS_BECOME_PUBLICLY_SERVED",
        "restriction_composition_semantics": {
            "full_ordered_realization_witness_retained": True,
            "search_state_quotient_basis": "CERTIFIED_HISTORY_LOCALITY_FOR_FROZEN_RT023_ATOMIC_DOMAIN_ONLY",
            "every_retained_witness_full_history_replayed": True,
            "new_carrier_or_uncertified_restriction_domain_covered": False,
        },
        "stop_guarantee_semantics": {
            "stop_identity_availability_only": True,
            "directional_occurrence_guaranteed": False,
            "ordered_service_event_guaranteed": False,
            "passenger_journey_guaranteed": False,
        },
        "terminus_vehicle_continuity_inferred": False,
        "terminus_passenger_continuity_inferred": False,
        "weighted_score": False,
        "uncertainty_band_applied": False,
        "public_service_assigned": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    audit_path = args.output_dir / "reciprocal_corridor_access_audit.json"
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--final-stops", type=Path, required=True)
    parser.add_argument("--v4-clusters", type=Path, required=True)
    parser.add_argument("--v4-validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-expansions", type=int, default=250000)
    main(parser.parse_args())
