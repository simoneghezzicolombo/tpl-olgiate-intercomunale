#!/usr/bin/env python3
"""Find minimum frozen-RT023 physical portfolios covering current exact-ID stops."""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    FrozenRT017ViaNodeAdapter,
    RT023ScopedTransitionOracle,
    build_boundary_catalog,
    build_pairwise_compatibility,
    build_realization_catalog,
    canonical,
    load_inputs,
    sha256_file,
    validate_via_way_evidence,
)
from scripts.phase2_compare_rt031_with_current_baseline_v4 import (
    FINAL_STOPS_SHA256,
    V4_CLUSTERS_LOGICAL_SHA256,
    V4_VALIDATION_LOGICAL_SHA256,
    WALK_SHA256,
    logical_sha256,
    read_csv,
)
from scripts.phase2_compare_rt031_movement_portfolios_v3 import threshold_vectors
from scripts.phase2_screen_rt031_resource_budget_v3 import PINNED
from src.phase2_rt031_current_baseline_comparison_v3 import exact_current_stop_subset
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import (
    LEGAL,
    evaluate_realization_chain,
)
from src.phase2_rt031_target_coverage_search_v3 import (
    minimum_cover_portfolios,
    search_target_closed_walks,
)


SPAN_MINUTES = 16 * 60
ANNUAL_DAYS = 260
HEADWAY_CLASSES = (30, 60)


def main(args):
    if sha256_file(args.final_stops) != FINAL_STOPS_SHA256:
        raise ValueError("RT028 final-stop lineage drift")
    if sha256_file(args.walk_matrix) != WALK_SHA256:
        raise ValueError("RT028 walk-matrix lineage drift")
    if logical_sha256(args.v4_clusters) != V4_CLUSTERS_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 cluster lineage drift")
    if logical_sha256(args.v4_validation) != V4_VALIDATION_LOGICAL_SHA256:
        raise ValueError("Current-Service V4 validation lineage drift")
    validation = json.loads(args.v4_validation.read_text(encoding="utf-8"))
    if (validation.get("status") != "PASS_PHASE2_CURRENT_SERVICE_ACCESS_BASELINE_V4"
            or validation.get("current_service_baseline_complete") is not False):
        raise ValueError("Current-Service V4 semantics are not admissible")
    for path, digest in PINNED.items():
        if sha256_file(Path(path)) != digest:
            raise ValueError("approved policy lineage drift")

    policy = json.loads(Path("config/phase2_final_policy_contract_v3.json").read_text())
    cap_km = Decimal(str(policy["human_policy_decisions"]["annual_bus_km_cap"]))
    bridge = exact_current_stop_subset(read_csv(args.v4_clusters), read_csv(args.final_stops))
    targets = bridge["mapped_stop_place_ids"]
    maximum_distance = cap_km * 1000 / (Decimal(SPAN_MINUTES) / 60 * ANNUAL_DAYS)

    tables, input_hashes = load_inputs(args.inputs)
    validate_via_way_evidence(args.via_way_evidence)
    catalog, _ = build_realization_catalog(tables["patterns"], tables["corridors"], tables["edges"])
    boundary = build_boundary_catalog(
        tables["patterns"], tables["occurrences"], tables["corridors"], tables["edges"])
    adapter = FrozenRT017ViaNodeAdapter(
        tables["edges"], tables["rules"], unresolved_external_via_way_count=2)
    scoped = RT023ScopedTransitionOracle(
        adapter,
        sorted({edge for row in catalog.values() for edge in row["edge_ids"]}),
        successor_via_way_irrelevance_certified=True,
        evidence_id="RT031_SUCCESSOR_VIA_WAY::" + sha256_file(args.via_way_evidence),
    )
    for row in catalog.values():
        if evaluate_realization_chain([row], boundary, scoped.oracle)["status"] != LEGAL:
            raise ValueError("atomic legality open")
    pairs = build_pairwise_compatibility(
        catalog, boundary, scoped.oracle, history_locality_certified=True)
    edge_rows = {row["edge_id"]: row for row in tables["edges"]}
    weights = {
        rid: sum((Decimal(edge_rows[edge]["length_m"]) for edge in row["edge_ids"]), Decimal(0))
        for rid, row in catalog.items()
    }
    stop_sets = {
        row["realization_id"]: row["ordered_passenger_stop_ids"].split(";")
        for row in tables["patterns"]
    }

    search = search_target_closed_walks(
        catalog, pairs, weights, stop_sets, targets,
        maximum_distance_m=maximum_distance,
        max_expansions=args.max_expansions,
        history_locality_certified=True,
        atomic_legality_certified=True,
    )
    for candidate in search["candidates"]:
        selected = [catalog[rid] for rid in candidate["realization_ids"]]
        if evaluate_realization_chain(selected + [selected[0]], boundary, scoped.oracle)["status"] != LEGAL:
            raise AssertionError("target-cover witness fails full-history seam replay")
        available = sorted(set().union(*(set(stop_sets[rid]) for rid in candidate["realization_ids"])))
        if set(candidate["target_stop_ids"]) != set(available) & set(targets):
            raise AssertionError("target-only search mask drift")
        candidate["available_stop_ids"] = available

    portfolio = minimum_cover_portfolios(
        search["candidates"], targets, max_movements=args.max_movements)
    raw_walk = pd.read_csv(args.walk_matrix, dtype={"population_weight_2025": str})
    weight_map = (raw_walk[["population_unit_id", "population_weight_2025"]]
                  .drop_duplicates().set_index("population_unit_id")["population_weight_2025"].to_dict())
    substrate = validate_walk_matrix(raw_walk)
    exact_weights = [weight_map[value] for value in substrate.population_meta["population_unit_id"]]
    baseline_vector = tuple(threshold_vectors([tuple(targets)], substrate, exact_weights)[0])
    dimensions = (
        "potential_core_share_5min", "potential_core_share_8min", "potential_core_share_10min",
        "potential_worst_municipality_share_5min",
        "potential_worst_municipality_share_8min",
        "potential_worst_municipality_share_10min",
    )
    for result in portfolio["results"]:
        result["selected_witnesses"] = [
            search["candidates"][index] for index in result["candidate_indices"]]
        if result["minimum_found_total_distance_m"] is None:
            result["service_class_screens"] = []
            result["available_stop_ids"] = []
            result["same_substrate_access_comparison"] = None
            continue
        available = sorted(set().union(*(
            set(search["candidates"][index]["available_stop_ids"])
            for index in result["candidate_indices"]
        )))
        vector = tuple(threshold_vectors([tuple(available)], substrate, exact_weights)[0])
        result["available_stop_ids"] = available
        result["same_substrate_access_comparison"] = {
            "dimensions": list(dimensions),
            "current_exact_ratios": [str(value) for value in baseline_vector],
            "portfolio_exact_ratios": [str(value) for value in vector],
            "current_display_shares": [float(value) for value in baseline_vector],
            "portfolio_display_shares": [float(value) for value in vector],
            "portfolio_no_worse_all_six": all(left >= right for left, right in zip(vector, baseline_vector)),
            "portfolio_strictly_better_any": any(left > right for left, right in zip(vector, baseline_vector)),
            "weighted_score": False,
        }
        distance = Decimal(result["minimum_found_total_distance_m"])
        screens = []
        for headway in HEADWAY_CLASSES:
            repetitions = Decimal(SPAN_MINUTES) / headway * ANNUAL_DAYS
            annual_km = distance * repetitions / 1000
            screens.append({
                "uniform_movement_headway_min": headway,
                "span_minutes": SPAN_MINUTES,
                "annual_service_days": ANNUAL_DAYS,
                "annual_bus_km": str(annual_km),
                "within_approved_cap": annual_km <= cap_km,
                "calendar_and_uniform_headway_are_design_assumptions": True,
            })
        result["service_class_screens"] = screens

    full_cover_results = [row for row in portfolio["results"] if row["full_target_cover_found"]]
    status = (
        "TARGET_COVER_WITNESS_FOUND_IN_BOUNDED_SEARCH"
        if full_cover_results else "NO_TARGET_COVER_WITNESS_FOUND_IN_INCOMPLETE_SEARCH"
    )
    audit = {
        "contract": "RT031_CURRENT_EXACT_TARGET_COVER_RESOURCE_SYMMETRY_V3",
        "status": status,
        "search": {key: value for key, value in search.items() if key != "candidates"},
        "portfolio": portfolio,
        "current_exact_identity_subset": bridge,
        "approved_annual_bus_km_cap": str(cap_km),
        "comparison_correction": (
            "SAME_STOP_IDENTITY_TARGET_AND_SAME_ANNUAL_RESOURCE_CAP;"
            "HEADWAY_CLASSES_REMAIN_SEPARATE_DESIGN_ASSUMPTIONS"
        ),
        "scope": "MINIMUM_FOUND_PHYSICAL_DISTANCE_TO_COVER_CURRENT_EXACT_ID_TARGETS_WITH_UP_TO_DECLARED_MOVEMENTS",
        "input_sha256": {
            **input_hashes,
            "via_way": sha256_file(args.via_way_evidence),
            "final_stops": FINAL_STOPS_SHA256,
            "v4_clusters_logical": V4_CLUSTERS_LOGICAL_SHA256,
            "v4_validation_logical": V4_VALIDATION_LOGICAL_SHA256,
            "walk_matrix": WALK_SHA256,
        },
        "full_history_replay_pass": True,
        "stop_identity_guarantee_only": True,
        "directional_occurrence_guaranteed": False,
        "ordered_service_event_guaranteed": False,
        "public_service_assigned": False,
        "weighted_score": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output = {
        **audit,
        "search_candidates": search["candidates"],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "current_exact_target_cover_search.json").write_bytes(canonical(output))
    (args.output_dir / "current_exact_target_cover_audit.json").write_bytes(canonical(audit))
    print(json.dumps(audit, sort_keys=True))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--final-stops", type=Path, required=True)
    parser.add_argument("--walk-matrix", type=Path, required=True)
    parser.add_argument("--v4-clusters", type=Path, required=True)
    parser.add_argument("--v4-validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-expansions", type=int, default=2_000_000)
    parser.add_argument("--max-movements", type=int, default=3)
    main(parser.parse_args())
