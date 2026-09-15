#!/usr/bin/env python3
"""Bind the eight H30/10h one-line frontier candidates to typed service events."""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path

from scripts.phase2_audit_rt031_real_occurrence_binding_v3 import EPOCH
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    FrozenRT017ViaNodeAdapter,
    RT023ScopedTransitionOracle,
    build_boundary_catalog,
    build_realization_catalog,
    canonical,
    load_inputs,
    sha256_file,
    validate_via_way_evidence,
)
from scripts.phase2_bind_rt031_target_cover_service_v3 import (
    STOP_ATTACHMENTS_SHA256,
    build_candidate,
    read_rows,
)
from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences
from src.phase2_rt031_frequent_access_shortlist_v3 import (
    engineering_cycle_sensitivity,
)
from src.phase2_rt031_single_line_binding_v3 import (
    certify_single_public_line,
    eligible_h30_10h_candidates,
)


FRONTIER_SHA256 = "c92e8de08eb249a3e840f2eddaefe49d228bd37fb09dc292edae24d460a263b0"
FRONTIER_AUDIT_SHA256 = "433ea63276f30fac92b42fbb548687c4461cfa88a1bdca911c72cee72a1b48a4"
CURRENT_AUDIT_SHA256 = "c164e047326c26a318851af86cf091c83aae345bcc39303d2ee46d92490fd0f1"
H30_POOL_SHA256 = "a055296ef62aea3c57ce73648349e83a03d160df6895babeff53fcd0a9222ecc"
HUB = "FROZEN::L00407"
HEADWAY_MIN = 30
SPAN_MINUTES = 600
ANNUAL_DAYS = 260
DESIGN_EVIDENCE = "RT031_SINGLE_LINE_H30_CONTEXT_CANDIDATE_DECLARATION_NOT_OBSERVED"


def main(args):
    expected = {
        args.frontier: FRONTIER_SHA256,
        args.frontier_audit: FRONTIER_AUDIT_SHA256,
        args.current_audit: CURRENT_AUDIT_SHA256,
        args.h30_pool: H30_POOL_SHA256,
    }
    if any(sha256_file(path) != digest for path, digest in expected.items()):
        raise ValueError("pinned single-line input lineage drift")
    frontier = json.loads(args.frontier.read_text(encoding="utf-8"))
    frontier_audit = json.loads(args.frontier_audit.read_text(encoding="utf-8"))
    current = json.loads(args.current_audit.read_text(encoding="utf-8"))
    if (frontier_audit.get("contract")
            != "RT031_SINGLE_RECOGNIZABLE_LINE_DISCOVERY_FRONTIER_V3"
            or frontier_audit.get("status")
            != "PASS_POOL_SCOPED_NON_DECISIONAL_SINGLE_LINE_FRONTIER"
            or frontier_audit.get("network_selected") is not False
            or frontier_audit.get("primary_selection_authorised") is not False
            or frontier_audit.get("runner_up_selection_authorised") is not False):
        raise ValueError("single-line frontier contract drift")
    current_ratios = current["all_movements_serve_olgiate_fs_portfolio"][
        "results"][1]["same_substrate_access_comparison"]["current_exact_ratios"]
    eligible = eligible_h30_10h_candidates(
        frontier, current_exact_ratios=current_ratios)
    if len(eligible) != 8:
        raise AssertionError("certified H30/10h one-line candidate identity drift")

    pool = json.loads(args.h30_pool.read_text(encoding="utf-8"))
    if (pool.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or pool.get("status") != "RESOURCE_LIMIT_INCOMPLETE"
            or pool.get("required_root_stop_id") != HUB
            or pool.get("search_priority_mode") != "preferred_stop_count"
            or pool.get("candidate_generation_priority_is_normative_selection") is not False):
        raise ValueError("H30 physical witness pool contract drift")
    witnesses = {tuple(row["realization_ids"]): row
                 for row in pool["candidates"]}

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
        tables["patterns"], tables["occurrences"], tables["corridors"],
        tables["edges"])
    adapter = FrozenRT017ViaNodeAdapter(
        tables["edges"], tables["rules"], unresolved_external_via_way_count=2)
    scoped = RT023ScopedTransitionOracle(
        adapter, sorted({edge for row in catalog.values()
                         for edge in row["edge_ids"]}),
        successor_via_way_irrelevance_certified=True,
        evidence_id="RT031_SUCCESSOR_VIA_WAY::"
        + sha256_file(args.via_way_evidence))

    profiles = []
    for row in eligible:
        path = tuple(row["realization_ids"])
        if path not in witnesses:
            raise ValueError("eligible ordered witness absent from pinned H30 pool")
        witness = witnesses[path]
        if (Decimal(witness["minimum_found_distance_m"])
                != Decimal(row["total_distance_m"])
                or sorted(witness["available_stop_ids"])
                != sorted(row["available_stop_ids"])):
            raise ValueError("frontier/witness semantics drift")
        profile_id = row["candidate_line_id"] + "::H30_10H_260D"
        network = build_candidate(
            {"selected_witnesses": [witness],
             "minimum_found_total_distance_m": row["total_distance_m"]},
            catalog=catalog, boundary=boundary, oracle=scoped.oracle,
            bound=bound, profile_id=profile_id,
            design_evidence=DESIGN_EVIDENCE, terminate_cycle_seam=True)
        route = certify_single_public_line(
            network, public_route_id="RT031_ONE_LINE::" + row["candidate_line_id"])
        component = next(iter(network["payload"]["components"].values()))
        running = sum((Decimal(edge["source_edge"]["running_minutes_model"])
                       for edge in component["location_expansion"]["payload"]["carrier"]),
                      Decimal(0))
        if not running.is_finite() or running <= 0:
            raise ValueError("invalid source-model running time")
        stop_ids = [event["source_visit"]["source_visit"]["source_occurrence"]
                    ["stop_place_id"] for event in component["events"]]
        if HUB not in stop_ids:
            raise ValueError("typed single line does not serve Olgiate FS")
        context = next(item for item in row["service_surface"]
                       if item["uniform_headway_min_per_movement"] == HEADWAY_MIN
                       and item["span_minutes"] == SPAN_MINUTES)
        fleet = [{
            "recovery_min_design_sensitivity": recovery,
            "fleet_lower_bound_source_model": int(
                ((running + recovery) / HEADWAY_MIN).to_integral_value(
                    rounding=ROUND_CEILING)),
            "dwell_included": False,
            "vehicle_block_plan_certified": False,
        } for recovery in (5, 10, 15)]
        component_screen = {
            "component_id": route["service_component_id"],
            "running_minutes_source_model_excludes_dwell": str(running),
            "ordered_service_event_count": len(component["events"]),
            "nonhub_public_stop_event_count": sum(
                stop_id != HUB for stop_id in stop_ids),
        }
        profiles.append({
            "profile_id": profile_id,
            "source_candidate_line_id": row["candidate_line_id"],
            "public_line_structure": route,
            "available_stop_ids": row["available_stop_ids"],
            "retained_current_exact_stop_count": row[
                "retained_current_exact_stop_count"],
            "retained_current_exact_stop_ids": row[
                "retained_current_exact_stop_ids"],
            "exact_access_ratios": row["exact_access_ratios"],
            "total_distance_m": row["total_distance_m"],
            "conditional_annual_bus_km": context["annual_bus_km"],
            "headway_min_design_context": HEADWAY_MIN,
            "span_minutes_design_context": SPAN_MINUTES,
            "annual_service_days_design_context": ANNUAL_DAYS,
            "typed_network": network,
            "operational_source_model_screen": {
                **component_screen,
                "fleet_sensitivity": fleet,
                "inherited_stage_f_engineering_grid":
                    engineering_cycle_sensitivity(
                        [component_screen], headway_min=HEADWAY_MIN),
                "running_time_status": "SOURCE_MODEL_NOT_OBSERVED_EXCLUDES_DWELL",
            },
            "timetable_assigned": False,
            "vehicle_block_plan_assigned": False,
        })
    audit = {
        "contract": "RT031_SINGLE_LINE_H30_10H_TYPED_CONTEXT_V3",
        "status": "PASS_EIGHT_TYPED_SINGLE_LINE_CANDIDATES_PENDING_OPERATIONS",
        "profile_count": len(profiles),
        "profiles": profiles,
        "public_route_identity_count_per_candidate": 1,
        "physical_movement_count_per_candidate": 1,
        "single_recognizable_line_structure_certified": True,
        "directional_occurrences_bound": True,
        "ordered_service_events_bound": True,
        "passenger_service_continuity_scope": "WITHIN_ORDERED_PATTERN_ONLY",
        "cycle_seam_passenger_through": False,
        "vehicle_continuity_used_as_passenger_continuity": False,
        "current_stop_retention_required": False,
        "current_stop_retention_remains_pareto_preference": True,
        "service_context_is_final_selection": False,
        "dwell_inclusive_runtime_certified": False,
        "timetable_feasibility_certified": False,
        "s8_connection_retention_certified": False,
        "municipal_od_spatially_downscaled": False,
        "demand_weighted_gjt_computed": False,
        "empirical_missed_connection_probability_computed": False,
        "upstream_candidate_domain_complete": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            **hashes, "stops": STOP_ATTACHMENTS_SHA256,
            "via_way": sha256_file(args.via_way_evidence),
            "frontier": FRONTIER_SHA256,
            "frontier_audit": FRONTIER_AUDIT_SHA256,
            "current_audit": CURRENT_AUDIT_SHA256,
            "h30_pool": H30_POOL_SHA256,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "single_line_h30_typed_context.json").write_bytes(
        canonical(audit))
    summary = {**audit, "profiles": [
        {key: value for key, value in row.items() if key != "typed_network"}
        for row in profiles]}
    (args.output_dir / "single_line_h30_typed_context_audit.json").write_bytes(
        canonical(summary))
    print(json.dumps(summary, sort_keys=True))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--frontier", type=Path, required=True)
    parser.add_argument("--frontier-audit", type=Path, required=True)
    parser.add_argument("--current-audit", type=Path, required=True)
    parser.add_argument("--h30-pool", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
