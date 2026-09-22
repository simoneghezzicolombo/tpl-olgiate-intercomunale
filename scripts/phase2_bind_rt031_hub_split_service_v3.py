"""Bind two pinned hub-split physical witnesses to typed one-line design events.

The binding declares a candidate service pattern; it does not assign a
timetable, prove operating reliability, or select a network.
"""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.phase2_audit_rt031_real_occurrence_binding_v3 import EPOCH
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    FrozenRT017ViaNodeAdapter, RT023ScopedTransitionOracle,
    build_boundary_catalog, build_realization_catalog, canonical,
    load_inputs, sha256_file, validate_via_way_evidence,
)
from scripts.phase2_bind_rt031_target_cover_service_v3 import (
    STOP_ATTACHMENTS_SHA256, build_candidate, read_rows,
)
from src.phase2_rt031_occurrence_binding_v3 import bind_occurrences
from src.phase2_rt031_single_line_binding_v3 import certify_single_public_line


SOURCE_SHA256 = "358a45e1de5cddfea56acec4bb4ee335b6f1e210a1d2a5e1ed84b8a47651b57f"
HUB = "FROZEN::L00407"
SHARED_PUBLIC_ROUTE_ID = "RT031_FIG8_DESIGN_ONE_PUBLIC_LINE"
PROBE_NAMES = (
    "ORDERED_REQUESTED_CORE_WITH_VERIFIED_DOMAIN_STOPS",
    "ORDERED_REVERSE_CORE_WITH_VERIFIED_DOMAIN_STOPS",
    "ORDERED_REQUESTED_PLUS_OLGIATE_VIA_STATALE",
    "ORDERED_REVERSE_PLUS_OLGIATE_VIA_STATALE",
)


def main(source_path: Path, inputs: Path, via_way_evidence: Path, output: Path):
    if sha256_file(source_path) != SOURCE_SHA256:
        raise ValueError("hub-split physical source digest drift")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if (source.get("contract") != "RT031_HUB_SPLIT_PHYSICAL_DIAGNOSTIC_V3"
            or source.get("network_selected") is not False
            or source.get("primary_selection_authorised") is not False
            or source.get("runner_up_selection_authorised") is not False):
        raise ValueError("hub-split physical contract drift")
    tables, hashes = load_inputs(inputs)
    validate_via_way_evidence(via_way_evidence)
    stop_path = inputs / "rt022" / "stop_attachments.csv"
    if sha256_file(stop_path) != STOP_ATTACHMENTS_SHA256:
        raise ValueError("stop attachment lineage drift")
    bound = bind_occurrences(
        patterns=tables["patterns"], occurrences=tables["occurrences"],
        corridors=tables["corridors"], edges=tables["edges"],
        stops=read_rows(stop_path), epoch=EPOCH)
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
        evidence_id="RT031_SUCCESSOR_VIA_WAY::" + sha256_file(via_way_evidence))
    results = {}
    for name in PROBE_NAMES:
        probe = source["probes"][name]
        if (probe["physical_cycle_witness_certified"] is not True
                or probe["ordered_physical_target_presence_certified"] is not True):
            raise ValueError("ordered physical witness not certified")
        west = probe["west_realization_ids"]
        east = probe["east_realization_ids"]
        path = west + east
        if (not west or not east or catalog[west[0]]["source_stop_id"] != HUB
                or catalog[west[-1]]["target_stop_id"] != HUB
                or catalog[east[0]]["source_stop_id"] != HUB
                or catalog[east[-1]]["target_stop_id"] != HUB):
            raise ValueError("three hub-boundary passages required")
        identity = "HUB8_" + hashlib.sha256(";".join(path).encode()).hexdigest()[:20]
        physical = {
            "realization_ids": path,
            "available_stop_ids": sorted(set(
                probe["west_lobe"]["ordered_available_stop_ids_not_service_events"]
                + probe["east_lobe"]["ordered_available_stop_ids_not_service_events"])),
        }
        network = build_candidate(
            {"selected_witnesses": [physical],
             "minimum_found_total_distance_m": probe["pairwise_graph_lower_bound_m"]},
            catalog=catalog, boundary=boundary, oracle=scoped.oracle,
            bound=bound, profile_id="RT031_HUB_SPLIT::" + identity,
            design_evidence="RT031_HUB_SPLIT_DESIGN_DECLARATION_NOT_OBSERVED",
            terminate_cycle_seam=True)
        route = certify_single_public_line(
            network, public_route_id=SHARED_PUBLIC_ROUTE_ID)
        component = next(iter(network["payload"]["components"].values()))
        events = component["events"]
        ordered = [event["source_visit"]["source_visit"]["source_occurrence"]
                   ["stop_place_id"] for event in events]
        hub_indices = [i for i, stop_id in enumerate(ordered) if stop_id == HUB]
        if (len(hub_indices) < 3 or hub_indices[0] != 0
                or hub_indices[-1] != len(events) - 1
                or not any(0 < i < len(events) - 1 for i in hub_indices)):
            raise AssertionError("typed intermediate FS event missing")
        if any(events[i]["event"]["passenger_through"] is not True
               for i in hub_indices[1:-1]):
            raise AssertionError("intermediate FS through-service not declared")
        results[name] = {
            "candidate_line_id": identity,
            "public_route_id": route["public_route_id"],
            "single_recognizable_line_structure_certified":
                route["single_recognizable_line_structure_certified"],
            "passenger_service_continuity_scope":
                route["passenger_service_continuity_scope"],
            "ordered_service_stop_ids": ordered,
            "hub_service_event_indices_zero_based": hub_indices,
            "intermediate_hub_passenger_through_declared": True,
            "available_stop_ids": physical["available_stop_ids"],
            "realization_ids": path,
            "distance_m": probe["pairwise_graph_lower_bound_m"],
            "west_running_minutes_model_excluding_dwell_recovery":
                probe["west_lobe"]["running_minutes_model_excluding_dwell_recovery"],
            "east_running_minutes_model_excluding_dwell_recovery":
                probe["east_lobe"]["running_minutes_model_excluding_dwell_recovery"],
        }
    payload = {
        "contract": "RT031_HUB_SPLIT_TYPED_ONE_LINE_V3",
        "status": "PASS_TYPED_DESIGN_ONLY_NO_TIMETABLE_OR_SELECTION",
        "source_sha256": SOURCE_SHA256,
        "input_sha256": {**hashes, "stops": STOP_ATTACHMENTS_SHA256,
                         "via_way_evidence": sha256_file(via_way_evidence)},
        "directional_patterns": results,
        "shared_public_route_identity_declared": SHARED_PUBLIC_ROUTE_ID,
        "two_directions_in_one_public_route_identity_certified": False,
        "timetable_assigned": False,
        "observed_dwell_available": False,
        "candidate_domain_complete": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(payload))
    print(json.dumps({name: {
        "event_count": len(result["ordered_service_stop_ids"]),
        "hub_indices": result["hub_service_event_indices_zero_based"],
    } for name, result in results.items()}, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.source, args.inputs, args.via_way_evidence, args.output)
