"""Pinned RT023 hub-split west/east physical probe; no public-line selection."""

import argparse
from decimal import Decimal
import json
from pathlib import Path

from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    load_inputs, validate_via_way_evidence, sha256_file, canonical,
    build_realization_catalog, build_boundary_catalog,
    FrozenRT017ViaNodeAdapter, RT023ScopedTransitionOracle,
    build_pairwise_compatibility,
)
from src.phase2_rt031_hub_split_physical_probe_v3 import shortest_hub_split_walk
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import (
    evaluate_realization_chain, LEGAL,
)


HUB = "FROZEN::L00407"
PROBES = {
    "WEST_ROVAGNATE_SANTA_EAST_CALCO_BRIVIO": {
        "west": (("FROZEN::300879",), ("FROZEN::300782", "FROZEN::300805")),
        "east": (("ASF::CALCO_VIA_GARIBALDI", "FROZEN::300634"), ("FROZEN::300063",)),
    },
    "ADD_PEREGO_ARLATE_BEVERATE": {
        "west": (("FROZEN::300879",), ("ASF::PEREGO_VIA_STATALE_79",),
                 ("FROZEN::300782", "FROZEN::300805")),
        "east": (("ASF::CALCO_VIA_GARIBALDI", "FROZEN::300634"),
                 ("ASF::ARLATE_CANTINA_PIROVANO", "ASF::ARLATE_BIVIO_PER_IL_PAESE"),
                 ("FROZEN::300063",),
                 ("ASF::BEVERATE_CARTELLO_PAESE", "FROZEN::300398")),
    },
    "ADD_MONTICELLO_SCARPONE": {
        "west": (("ASF::OLGIATE_MOLGORA_SCARPONE",), ("FROZEN::300879",),
                 ("ASF::PEREGO_VIA_STATALE_79",),
                 ("FROZEN::300782", "FROZEN::300805")),
        "east": (("ASF::CALCO_VIA_GARIBALDI", "FROZEN::300634"),
                 ("ASF::ARLATE_CANTINA_PIROVANO", "ASF::ARLATE_BIVIO_PER_IL_PAESE"),
                 ("FROZEN::300063",),
                 ("ASF::BEVERATE_CARTELLO_PAESE", "FROZEN::300398")),
    },
    "ORDERED_REQUESTED_CORE_WITH_VERIFIED_DOMAIN_STOPS": {
        "ordered": True,
        "west": (("ASF::OLGIATE_MOLGORA_SCARPONE",),
                 ("ASF::ROVAGNATE_STRADA_STATALE_AGIP",
                  "ASF::ROVAGNATE_SS_ANG_V_LOMBARDIA", "FROZEN::300879"),
                 ("ASF::PEREGO_VIA_STATALE_79",),
                 ("FROZEN::300782", "FROZEN::300805")),
        "east": (("ASF::CALCO_VIA_GARIBALDI", "FROZEN::300634"),
                 ("ASF::ARLATE_CANTINA_PIROVANO", "ASF::ARLATE_BIVIO_PER_IL_PAESE"),
                 ("FROZEN::300063",),
                 ("ASF::BEVERATE_CARTELLO_PAESE", "FROZEN::300398")),
    },
    "ORDERED_REVERSE_CORE_WITH_VERIFIED_DOMAIN_STOPS": {
        "ordered": True,
        "west": (("FROZEN::300782", "FROZEN::300805"),
                 ("ASF::PEREGO_VIA_STATALE_79",),
                 ("ASF::ROVAGNATE_STRADA_STATALE_AGIP",
                  "ASF::ROVAGNATE_SS_ANG_V_LOMBARDIA", "FROZEN::300879"),
                 ("ASF::OLGIATE_MOLGORA_SCARPONE",)),
        "east": (("ASF::BEVERATE_CARTELLO_PAESE", "FROZEN::300398"),
                 ("FROZEN::300063",),
                 ("ASF::ARLATE_CANTINA_PIROVANO", "ASF::ARLATE_BIVIO_PER_IL_PAESE"),
                 ("ASF::CALCO_VIA_GARIBALDI", "FROZEN::300634")),
    },
}


def main(inputs: Path, via_way_evidence: Path, output: Path):
    tables, hashes = load_inputs(inputs)
    validate_via_way_evidence(via_way_evidence)
    catalog, _ = build_realization_catalog(
        tables["patterns"], tables["corridors"], tables["edges"])
    boundary = build_boundary_catalog(
        tables["patterns"], tables["occurrences"],
        tables["corridors"], tables["edges"])
    adapter = FrozenRT017ViaNodeAdapter(
        tables["edges"], tables["rules"], unresolved_external_via_way_count=2)
    scoped = RT023ScopedTransitionOracle(
        adapter, sorted({e for r in catalog.values() for e in r["edge_ids"]}),
        successor_via_way_irrelevance_certified=True,
        evidence_id="RT031_SUCCESSOR_VIA_WAY::" + sha256_file(via_way_evidence))
    for row in catalog.values():
        if evaluate_realization_chain([row], boundary, scoped.oracle)["status"] != LEGAL:
            raise ValueError("atomic legality open")
    pairs = build_pairwise_compatibility(
        catalog, boundary, scoped.oracle, history_locality_certified=True)
    edges = {r["edge_id"]: r for r in tables["edges"]}
    weights = {
        rid: sum((Decimal(edges[e]["length_m"]) for e in row["edge_ids"]), Decimal(0))
        for rid, row in catalog.items()
    }
    stop_sets = {
        row["realization_id"]: row["ordered_passenger_stop_ids"].split(";")
        for row in tables["patterns"]
    }
    pattern_by_id = {row["realization_id"]: row for row in tables["patterns"]}
    corridor_by_id = {row["corridor_id"]: row for row in tables["corridors"]}

    def lobe_evidence(realization_ids):
        ordered = []
        for rid in realization_ids:
            for stop_id in stop_sets[rid]:
                if not ordered or ordered[-1] != stop_id:
                    ordered.append(stop_id)
        return {
            "distance_m": str(sum((weights[r] for r in realization_ids), Decimal(0))),
            "running_minutes_model_excluding_dwell_recovery": str(sum((
                Decimal(corridor_by_id[pattern_by_id[r]["corridor_id"]]["running_minutes_model"])
                for r in realization_ids), Decimal(0))),
            "ordered_available_stop_ids_not_service_events": ordered,
        }

    results = {}
    for name, groups in PROBES.items():
        result = shortest_hub_split_walk(
            catalog, pairs, weights, stop_sets, hub_stop_id=HUB,
            west_target_groups=groups["west"], east_target_groups=groups["east"],
            history_locality_certified=True, atomic_legality_certified=True,
            ordered_within_lobes=groups.get("ordered", False))
        path = result["west_realization_ids"] + result["east_realization_ids"]
        replay = None
        if path:
            selected = [catalog[rid] for rid in path]
            replay = evaluate_realization_chain(
                selected + [selected[0]], boundary, scoped.oracle)["status"]
        result.update(
            west_target_groups=[list(g) for g in groups["west"]],
            east_target_groups=[list(g) for g in groups["east"]],
            west_lobe=lobe_evidence(result["west_realization_ids"]),
            east_lobe=lobe_evidence(result["east_realization_ids"]),
            full_history_and_next_cycle_replay_status=replay,
            physical_cycle_witness_certified=(replay == LEGAL),
            no_witness_scope="ONLY_PINNED_RT023_288_ATOMIC_REALIZATIONS",
        )
        results[name] = result
    payload = {
        "contract": "RT031_HUB_SPLIT_PHYSICAL_DIAGNOSTIC_V3",
        "status": "NON_DECISIONAL_PINNED_PHYSICAL_PROBE",
        "input_sha256": hashes,
        "via_way_evidence_sha256": sha256_file(via_way_evidence),
        "hub_stop_id": HUB,
        "probes": results,
        "full_caller_itinerary_order_certified": False,
        "directional_reciprocity_certified": False,
        "passenger_service_continuity_certified": False,
        "timetable_certified": False,
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
        "distance_m": p["pairwise_graph_lower_bound_m"],
        "certified": p["physical_cycle_witness_certified"],
    } for name, p in results.items()}, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--via-way-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.inputs, args.via_way_evidence, args.output)
