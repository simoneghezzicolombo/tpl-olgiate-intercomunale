#!/usr/bin/env python3
"""Bind every within-cap municipal-frontier line to typed service events."""
from __future__ import annotations

import argparse
from decimal import Decimal
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
from src.phase2_rt031_frequent_access_shortlist_v3 import (
    engineering_cycle_sensitivity,
)
from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences
from src.phase2_rt031_single_line_binding_v3 import (
    certify_single_public_line,
    municipal_frontier_within_cap,
)


MUNICIPAL_FRONTIER_SHA256 = "0757d9513e21e1e68a7fc43c1732b45c4ccd83242e84d20ea8a324d0866bca26"
HUB = "FROZEN::L00407"
DESIGN_EVIDENCE = "RT031_MUNICIPAL_FRONTIER_CANDIDATE_DECLARATION_NOT_OBSERVED"


def main(args):
    if sha256_file(args.municipal_frontier) != MUNICIPAL_FRONTIER_SHA256:
        raise ValueError("pinned municipal frontier drift")
    source = json.loads(args.municipal_frontier.read_text(encoding="utf-8"))
    if (source.get("contract") != "RT031_SINGLE_LINE_MUNICIPAL_ACCESS_FRONTIER_V4"
            or source.get("status")
            != "PASS_POOL_SCOPED_NON_DECISIONAL_MUNICIPAL_FRONTIER"
            or source.get("frontier_count") != 778
            or source.get("municipality_non_regression_is_hard_filter") is not False
            or source.get("network_selected") is not False):
        raise ValueError("municipal frontier contract drift")
    cap = source["reference_resource_context"]["annual_bus_km_cap"]
    eligible = municipal_frontier_within_cap(
        source["frontier"], annual_bus_km_cap=cap)
    if (len(eligible) != 736
            or source["reference_resource_context"]
            ["frontier_within_cap_count"] != len(eligible)):
        raise ValueError("within-cap municipal frontier identity drift")

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
        identity = row["candidate_line_id"]
        profile_id = identity + "::MUNICIPAL_V4_20_DAILY_CYCLES"
        witness = {
            "realization_ids": row["realization_ids"],
            "available_stop_ids": row["available_stop_ids"],
            "minimum_found_distance_m": row["total_distance_m"],
        }
        network = build_candidate(
            {"selected_witnesses": [witness],
             "minimum_found_total_distance_m": row["total_distance_m"]},
            catalog=catalog, boundary=boundary, oracle=scoped.oracle,
            bound=bound, profile_id=profile_id,
            design_evidence=DESIGN_EVIDENCE, terminate_cycle_seam=True)
        route = certify_single_public_line(
            network, public_route_id="RT031_ONE_LINE::" + identity)
        component = next(iter(network["payload"]["components"].values()))
        running = sum((Decimal(edge["source_edge"]["running_minutes_model"])
                       for edge in component["location_expansion"]["payload"]
                       ["carrier"]), Decimal(0))
        stop_ids = [event["source_visit"]["source_visit"]["source_occurrence"]
                    ["stop_place_id"] for event in component["events"]]
        if not running.is_finite() or running <= 0 or HUB not in stop_ids:
            raise ValueError("invalid bound municipal candidate")
        screen = {
            "component_id": route["service_component_id"],
            "running_minutes_source_model_excludes_dwell": str(running),
            "ordered_service_event_count": len(component["events"]),
            "nonhub_public_stop_event_count": sum(stop != HUB for stop in stop_ids),
        }
        profiles.append({
            "profile_id": profile_id,
            "source_candidate_line_id": identity,
            "public_line_structure": route,
            "available_stop_ids": row["available_stop_ids"],
            "retained_current_exact_stop_count":
                row["retained_current_exact_stop_count"],
            "retained_current_exact_stop_ids":
                row["retained_current_exact_stop_ids"],
            "exact_total_coverage": row["exact_total_coverage"],
            "exact_municipality_coverage": row["exact_municipality_coverage"],
            "total_distance_m": row["total_distance_m"],
            "conditional_annual_bus_km_at_20_daily_cycles":
                row["conditional_annual_bus_km_at_20_daily_cycles"],
            "typed_network": network,
            "operational_source_model_screen": {
                **screen,
                "inherited_stage_f_engineering_grid":
                    engineering_cycle_sensitivity([screen], headway_min=30),
                "running_time_status":
                    "SOURCE_MODEL_NOT_OBSERVED_EXCLUDES_DWELL",
            },
            "timetable_assigned": False,
            "vehicle_block_plan_assigned": False,
        })

    audit = {
        "contract": "RT031_MUNICIPAL_FRONTIER_TYPED_BINDING_V4",
        "status": "PASS_FULL_WITHIN_CAP_FRONTIER_TYPED_PENDING_OPERATIONS",
        "municipal_frontier_candidate_count": source["frontier_count"],
        "within_cap_profile_count": len(profiles),
        "within_cap_frontier_binding_complete": True,
        "directional_occurrences_bound": True,
        "ordered_service_events_bound": True,
        "municipality_non_regression_used_as_filter": False,
        "current_stop_retention_used_as_filter": False,
        "observed_dwell_validation_complete": False,
        "upstream_candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {**hashes, "stops": STOP_ATTACHMENTS_SHA256,
                         "via_way": sha256_file(args.via_way_evidence),
                         "municipal_frontier": MUNICIPAL_FRONTIER_SHA256},
        "profiles": profiles,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "municipal_frontier_typed_binding_v4.json").write_bytes(
        canonical(audit))
    summary = {**audit, "profiles": [
        {key: value for key, value in row.items() if key != "typed_network"}
        for row in profiles]}
    (args.output_dir / "municipal_frontier_typed_binding_v4_audit.json").write_bytes(
        canonical(summary))
    print(json.dumps({key: value for key, value in summary.items()
                      if key != "profiles"}, sort_keys=True))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--municipal-frontier", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
