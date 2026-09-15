#!/usr/bin/env python3
"""Bind the exact H30/12h territorial access frontier to typed service events."""
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
from src.phase2_rt031_frequent_access_shortlist_v3 import (
    engineering_cycle_sensitivity,
    select_frequent_access_frontier,
)
from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences


FRONTIER_SHA256 = "8f396759214fe2587449e4b4ecb1a9de1b6e481c22408f37731106a426c240f7"
FRONTIER_AUDIT_SHA256 = "32990d94df7b3328d5c63db444fb758120bebe4e7dcc4e49cd83d131ba19874d"
HUB_POOL_SHA256 = "b86b27f791b0b36f0e30997a96388c5763f46822411ea990bfeed3351cd8a65c"
HUB = "FROZEN::L00407"
HEADWAY_MIN = 30
SPAN_MINUTES = 720
ANNUAL_DAYS = 260
DESIGN_EVIDENCE = "RT031_FREQUENT_ACCESS_SHORTLIST_CANDIDATE_DECLARATION_NOT_OBSERVED"


def main(args):
    expected = {
        args.frontier: FRONTIER_SHA256,
        args.frontier_audit: FRONTIER_AUDIT_SHA256,
        args.hub_pool: HUB_POOL_SHA256,
    }
    if any(sha256_file(path) != digest for path, digest in expected.items()):
        raise ValueError("pinned shortlist input lineage drift")
    frontier = json.loads(args.frontier.read_text(encoding="utf-8"))
    frontier_audit = json.loads(args.frontier_audit.read_text(encoding="utf-8"))
    if (frontier_audit.get("contract")
            != "RT031_NETWORK_CONNECTED_STOP_RETENTION_PREFERENCE_FRONTIER_V3"
            or frontier_audit.get("status")
            != "PASS_POOL_SCOPED_NON_DECISIONAL_FRONTIER"
            or frontier_audit.get("network_selected") is not False):
        raise ValueError("network-connected frontier contract drift")
    selection = select_frequent_access_frontier(
        frontier,
        current_exact_ratios=frontier_audit["current_exact_access_ratios"],
        headway_min=HEADWAY_MIN,
        span_minutes=SPAN_MINUTES,
    )
    if (selection["eligible_benchmark_improvement_count"] != 155
            or selection["access_equity_frontier_count"] != 5):
        raise AssertionError("certified frequent access frontier identity drift")

    pool = json.loads(args.hub_pool.read_text(encoding="utf-8"))
    if (pool.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
            or pool.get("required_root_stop_id") != HUB
            or pool.get("status") != "RESOURCE_LIMIT_INCOMPLETE"):
        raise ValueError("hub physical pool contract drift")
    hub_walks = {"hub::" + row["stop_set_id"]: row for row in pool["candidates"]}

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

    declarations = []
    for row in selection.pop("shortlist"):
        if row["movement_count"] != 2:
            raise AssertionError("unexpected movement count in frequent shortlist")
        try:
            witnesses = [hub_walks[identity] for identity in row["source_walk_ids"]]
        except KeyError as exc:
            raise ValueError("shortlist witness absent from pinned hub pool") from exc
        physical = {
            "selected_witnesses": witnesses,
            "minimum_found_total_distance_m": row["total_distance_m"],
        }
        if sum((Decimal(item["minimum_found_distance_m"])
                for item in witnesses), Decimal(0)) != Decimal(row["total_distance_m"]):
            raise AssertionError("portfolio distance does not equal source witnesses")
        profile_id = row["portfolio_id"] + "::H30_12H_260D"
        network = build_candidate(
            physical, catalog=catalog, boundary=boundary, oracle=scoped.oracle,
            bound=bound, profile_id=profile_id,
            design_evidence=DESIGN_EVIDENCE)
        components = []
        for component_id, component in sorted(network["payload"]["components"].items()):
            running = sum((Decimal(edge["source_edge"]["running_minutes_model"])
                           for edge in component["location_expansion"]["payload"]["carrier"]),
                          Decimal(0))
            stop_ids = [event["source_visit"]["source_visit"]["source_occurrence"]
                        ["stop_place_id"] for event in component["events"]]
            if HUB not in stop_ids or not running.is_finite() or running <= 0:
                raise AssertionError("component hub/runtime binding failed")
            components.append({
                "component_id": component_id,
                "running_minutes_source_model_excludes_dwell": str(running),
                "ordered_service_event_count": len(component["events"]),
                "nonhub_public_stop_event_count": sum(
                    stop_id != HUB for stop_id in stop_ids),
                "serves_olgiate_fs": True,
            })
        fleet = []
        for recovery in (5, 10, 15):
            bounds = [int(((Decimal(item["running_minutes_source_model_excludes_dwell"])
                           + recovery) / HEADWAY_MIN)
                          .to_integral_value(rounding=ROUND_CEILING))
                      for item in components]
            fleet.append({
                "recovery_min_design_sensitivity": recovery,
                "per_component_fleet_lower_bounds": bounds,
                "independently_operated_fleet_lower_bound_source_model": sum(bounds),
                "dwell_included": False,
                "vehicle_block_plan_certified": False,
            })
        context = next(item for item in row["service_surface"]
                       if item["uniform_headway_min_per_movement"] == HEADWAY_MIN
                       and item["span_minutes"] == SPAN_MINUTES)
        declarations.append({
            "profile_id": profile_id,
            "source_portfolio_id": row["portfolio_id"],
            "movement_count": row["movement_count"],
            "available_stop_ids": row["available_stop_ids"],
            "exact_access_ratios": row["exact_access_ratios"],
            "retained_current_exact_stop_count": row["retained_current_exact_stop_count"],
            "total_distance_m": row["total_distance_m"],
            "conditional_annual_bus_km": context["annual_bus_km"],
            "headway_min_design_context": HEADWAY_MIN,
            "span_minutes_design_context": SPAN_MINUTES,
            "annual_service_days_design_context": ANNUAL_DAYS,
            "typed_network": network,
            "operational_source_model_screen": {
                "components": components,
                "fleet_sensitivity": fleet,
                "inherited_stage_f_engineering_grid":
                    engineering_cycle_sensitivity(
                        components, headway_min=HEADWAY_MIN),
                "running_time_status": "SOURCE_MODEL_NOT_OBSERVED_EXCLUDES_DWELL",
            },
            "timetable_assigned": False,
            "vehicle_block_plan_assigned": False,
            "cross_component_transfer_inferred": False,
        })
    audit = {
        "contract": "RT031_FREQUENT_ACCESS_TYPED_DEVELOPMENT_SHORTLIST_V3",
        "status": "PASS_FIVE_TYPED_DEVELOPMENT_PROFILES_PENDING_OPERATIONS",
        **selection,
        "profile_count": len(declarations),
        "profiles": declarations,
        "selection_semantics": (
            "APPROVED_FREQUENT_CLASS_AND_HARD_CAP_THEN_EXACT_ACCESS_EQUITY_PARETO"),
        "directional_occurrences_bound": True,
        "ordered_service_events_bound": True,
        "every_component_serves_olgiate_fs": True,
        "dwell_inclusive_runtime_certified": False,
        "timetable_feasibility_certified": False,
        "s8_connection_retention_certified": False,
        "upstream_candidate_domain_complete": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "input_sha256": {
            **hashes, "stops": STOP_ATTACHMENTS_SHA256,
            "via_way": sha256_file(args.via_way_evidence),
            "frontier": FRONTIER_SHA256,
            "frontier_audit": FRONTIER_AUDIT_SHA256,
            "hub_pool": HUB_POOL_SHA256,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "frequent_access_typed_shortlist.json").write_bytes(
        canonical(audit))
    summary = {**audit, "profiles": [
        {key: value for key, value in row.items() if key != "typed_network"}
        for row in declarations]}
    (args.output_dir / "frequent_access_typed_shortlist_audit.json").write_bytes(
        canonical(summary))
    print(json.dumps(summary, sort_keys=True))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--frontier", type=Path, required=True)
    parser.add_argument("--frontier-audit", type=Path, required=True)
    parser.add_argument("--hub-pool", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
