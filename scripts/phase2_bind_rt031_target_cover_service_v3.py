#!/usr/bin/env python3
"""Bind found target-cover physical witnesses to explicit candidate service events."""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_CEILING
import gzip
import csv
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
from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences, concatenate_available
from src.phase2_rt031_service_network_v3 import (
    MacroEdge,
    Movement,
    PublicPattern,
    ServiceComponent,
    ServiceEvent,
    build_service_network,
)


TARGET_SEARCH_SHA256 = "57f2079dd69decfe24571dbcaa032765496e5715410c440b2f964b5225e15f5f"
STOP_ATTACHMENTS_SHA256 = "30d64ff20e9b89c31f7878c415dd4c6bb5a0d10f51b24d041e4deb4d57e6571b"
DESIGN_EVIDENCE = "RT031_TARGET_COVER_CANDIDATE_SERVICE_DECLARATION_NOT_OBSERVED"


def read_rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_candidate(portfolio_row, *, catalog, boundary, oracle, bound, profile_id):
    macros, components, patterns, movements = [], [], [], []
    for component_index, witness in enumerate(portfolio_row["selected_witnesses"], start=1):
        rids = tuple(witness["realization_ids"])
        macro_id = f"{profile_id}::MACRO::{component_index}"
        component_id = f"{profile_id}::COMPONENT::{component_index}"
        macros.append(MacroEdge(
            macro_id,
            catalog[rids[0]]["source_stop_id"],
            catalog[rids[-1]]["target_stop_id"],
            rids,
        ))
        location = concatenate_available(bound, rids)
        events = []
        for event_index, visit in enumerate(location["payload"]["visits"], start=1):
            occurrence = visit["source_visit"]["source_occurrence"] if "source_visit" in visit else visit["source_occurrence"]
            events.append(ServiceEvent(
                event_id=f"{component_id}::EVENT::{event_index}",
                atom_slot=int(visit["slot"]),
                source_stop_sequence=int(occurrence["stop_sequence"]),
                event_kind="CANDIDATE_ORDINARY_PUBLIC_STOP",
                pickup=True,
                dropoff=True,
                passenger_through=True,
                vehicle_through=True,
                evidence_id=DESIGN_EVIDENCE,
            ))
        components.append(ServiceComponent(
            component_id=component_id,
            macro_edge_ids=(macro_id,),
            events=tuple(events),
            public_atoms=(True,) * len(rids),
            applicability=profile_id,
        ))
        patterns.append(PublicPattern(
            pattern_id=f"{profile_id}::PATTERN::{component_index}",
            component_id=component_id,
            event_ids=tuple(event.event_id for event in events),
            applicability=profile_id,
            evidence_id=DESIGN_EVIDENCE,
        ))
        movements.append(Movement(
            movement_id=f"{profile_id}::MOVEMENT::{component_index}",
            component_id=component_id,
            multiplicity=1,
            applicability=profile_id,
            evidence_id=DESIGN_EVIDENCE,
        ))
    network = build_service_network(
        tuple(macros), tuple(components), tuple(patterns), tuple(movements),
        bound=bound, catalog=catalog, boundary_rows=boundary,
        transition_oracle=oracle,
        evidence_scope_id="FROZEN_RT023_ATOMIC_DOMAIN_WITH_FULL_HISTORY_REPLAY",
        applicability=profile_id,
    )
    expected = Decimal(portfolio_row["minimum_found_total_distance_m"])
    if Decimal(network["declared_movement_traversal_distance_m"]) != expected:
        raise AssertionError("typed movement distance differs from target-cover witness")
    if not network["service_relations_complete"] or not network["movement_assignment_complete"]:
        raise AssertionError("candidate service binding incomplete")
    for component in network["payload"]["components"].values():
        stop_ids = {
            event["source_visit"]["source_visit"]["source_occurrence"]["stop_place_id"]
            for event in component["events"]
        }
        if "FROZEN::L00407" not in stop_ids:
            raise AssertionError("shortlisted component does not serve Olgiate FS")
    return network


def main(args):
    if sha256_file(args.target_search) != TARGET_SEARCH_SHA256:
        raise ValueError("target-cover search lineage drift")
    search = json.loads(args.target_search.read_text(encoding="utf-8"))
    if (search.get("status") != "TARGET_COVER_WITNESS_FOUND_IN_BOUNDED_SEARCH"
            or search.get("primary_selection_authorised") is not False
            or search.get("runner_up_selection_authorised") is not False):
        raise ValueError("target-cover contract not admissible")
    tables, hashes = load_inputs(args.inputs)
    validate_via_way_evidence(args.via_way_evidence)
    stop_path = args.inputs / "rt022" / "stop_attachments.csv"
    if sha256_file(stop_path) != STOP_ATTACHMENTS_SHA256:
        raise ValueError("stop attachment lineage drift")
    tables["stops"] = read_rows(stop_path)
    bound = bind_occurrences(
        patterns=tables["patterns"], occurrences=tables["occurrences"],
        corridors=tables["corridors"], edges=tables["edges"], stops=tables["stops"],
        epoch=EPOCH,
    )
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

    rows = {row["maximum_movement_count"]: row
            for row in search["all_movements_serve_olgiate_fs_portfolio"]["results"]}
    declarations = []
    for movement_count, headway in ((2, 60),):
        row = rows[movement_count]
        if not row["full_target_cover_found"]:
            raise ValueError("required target-cover witness absent")
        screen = next(item for item in row["service_class_screens"]
                      if item["uniform_movement_headway_min"] == headway)
        if screen["within_approved_cap"] is not True:
            raise ValueError("shortlisted service-class witness exceeds cap")
        profile_id = f"TARGET_COVER_{movement_count}M_H{headway}_16H_260D"
        network = build_candidate(
            row, catalog=catalog, boundary=boundary, oracle=scoped.oracle,
            bound=bound, profile_id=profile_id)
        component_runtime = []
        for component_id, component in sorted(network["payload"]["components"].items()):
            carrier = component["location_expansion"]["payload"]["carrier"]
            running = sum((Decimal(edge["source_edge"]["running_minutes_model"])
                           for edge in carrier), Decimal(0))
            if not running.is_finite() or running <= 0:
                raise ValueError("invalid source-model component running time")
            component_runtime.append({
                "component_id": component_id,
                "running_minutes_source_model_excludes_dwell": str(running),
                "ordered_service_event_count": len(component["events"]),
            })
        fleet_sensitivity = []
        for recovery in (5, 10, 15):
            per_component = [
                int(((Decimal(item["running_minutes_source_model_excludes_dwell"]) + recovery) / headway)
                    .to_integral_value(rounding=ROUND_CEILING))
                for item in component_runtime
            ]
            fleet_sensitivity.append({
                "recovery_min_design_sensitivity": recovery,
                "independently_operated_component_fleet_lower_bound_source_model": sum(per_component),
                "per_component_fleet_lower_bounds": per_component,
                "dwell_included": False,
                "vehicle_interlining_inferred": False,
                "vehicle_block_plan_certified": False,
            })
        declarations.append({
            "profile_id": profile_id,
            "movement_count": movement_count,
            "uniform_movement_headway_min_design_assumption": headway,
            "span_minutes_design_assumption": 960,
            "annual_service_days_design_assumption": 260,
            "conditional_annual_bus_km": screen["annual_bus_km"],
            "available_stop_ids": row["available_stop_ids"],
            "same_substrate_access_comparison": row["same_substrate_access_comparison"],
            "typed_network": network,
            "operational_source_model_screen": {
                "components": component_runtime,
                "fleet_sensitivity": fleet_sensitivity,
                "running_time_status": "SOURCE_MODEL_NOT_OBSERVED_EXCLUDES_DWELL",
            },
            "cycle_seam_passenger_through_inferred": False,
            "cycle_seam_vehicle_turn_inferred": False,
            "cross_component_transfer_inferred": False,
            "timetable_assigned": False,
            "vehicle_block_plan_assigned": False,
        })
    audit = {
        "contract": "RT031_TARGET_COVER_TYPED_SERVICE_SHORTLIST_V3",
        "status": "PASS_TYPED_CANDIDATE_SERVICE_BINDING_PENDING_OPERATIONS",
        "target_search_sha256": TARGET_SEARCH_SHA256,
        "input_sha256": {**hashes, "stops": STOP_ATTACHMENTS_SHA256,
                         "via_way": sha256_file(args.via_way_evidence)},
        "profiles": declarations,
        "service_event_semantics": "EXPLICIT_CANDIDATE_DESIGN_DECLARATION_NOT_OBSERVED_SERVICE",
        "directional_occurrences_bound": True,
        "ordered_service_events_bound": True,
        "passenger_and_vehicle_continuity_separate": True,
        "cross_component_transfers": None,
        "every_component_serves_olgiate_fs": True,
        "combined_hub_headway_inferred": False,
        "timetable_feasibility_certified": False,
        "s8_connection_retention_certified": False,
        "production_rt031_pass": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "target_cover_typed_service_shortlist.json").write_bytes(canonical(audit))
    summary = {**audit, "profiles": [{key: value for key, value in row.items()
                                      if key != "typed_network"} for row in declarations]}
    (args.output_dir / "target_cover_typed_service_audit.json").write_bytes(canonical(summary))
    print(json.dumps(summary, sort_keys=True))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--target-search", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    main(parser.parse_args())
