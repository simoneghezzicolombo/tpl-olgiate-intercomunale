#!/usr/bin/env python3
"""Rebuild Access/Equity V2 with the certified hub boarding catchment.

The original Access Equity V2 correctly evaluated explicit structural stop
anchors but omitted `rail:S01514` from walking access even though every public
Phase 2 route boards there. This source-closed correction attaches the already
certified walking catchment of the official Olgiate station bus-stop cluster to
the structural hub, without moving coordinates, changing routes, or asserting
current historical GTFS service.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_run_access_equity_v2 import (
    _summary_fields,
    _write_summary,
    build_anchor_walks,
    explicit_stop_anchors,
    load_anchor_source_members,
    load_population_units,
    load_stop_walks,
    parse_routes,
    read_json,
    sha256_path,
    validate_upstream,
)
from src.phase2_access_equity_v2 import merge_anchor_sets, summarise_walk_coverage_thresholds

HUB_ID = "rail:S01514"
STATUS = "PASS_ACCESS_EQUITY_V2_BUILD"
CONTRACT = "PHASE2_BUILDING_CATCHMENT_ACCESS_EQUITY_V2"


def deterministic_gzip_text_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, gz, text


def routes_contain_hub(routes: list[list[str]]) -> bool:
    return any(HUB_ID in route for route in routes)


def materialise(
    *, catalog_path: Path, anchor_path: Path, proposed_catchment_path: Path,
    existing_catchment_path: Path, population_path: Path, hub_bridge_path: Path,
    scenario_output: Path,
):
    bridge = read_json(hub_bridge_path)
    if bridge.get("status") != "PASS_HUB_ACCESS_BRIDGE_V2_BUILD" or bridge.get("contract") != "PHASE2_HUB_ACCESS_BRIDGE_V2":
        raise ValueError("Hub access bridge is not certified")
    if bridge.get("hub_anchor_id") != HUB_ID:
        raise ValueError("Unexpected hub access bridge anchor")
    hub_cluster = str(bridge["boarding_access_proxy_physical_cluster_id"]).strip()
    if not hub_cluster:
        raise ValueError("Hub access bridge lacks physical cluster")

    unit_weights, unit_municipality, municipality_totals, municipality_codes = load_population_units(population_path)
    municipality_by_code = {municipality_codes[m]: m for m in sorted(municipality_totals)}
    municipality_codes_sorted = sorted(municipality_by_code)
    anchor_members, anchor_kinds = load_anchor_source_members(anchor_path)
    if HUB_ID not in anchor_members or anchor_kinds.get(HUB_ID) != "HUB_RAIL":
        raise ValueError("Routing anchor universe lacks certified hub")
    proposed_walks, existing_walks = load_stop_walks(
        proposed_catchment_path, existing_catchment_path, unit_weights=unit_weights
    )
    if hub_cluster not in existing_walks:
        raise ValueError(f"Hub access cluster {hub_cluster} lacks certified existing-stop catchment")

    # The hub remains a rail routing anchor. Only its passenger walking-access
    # membership is bridged to the certified official station bus-stop cluster.
    anchor_members = dict(anchor_members)
    anchor_members[HUB_ID] = (("EXISTING_PHYSICAL_STOP_CLUSTER", hub_cluster),)
    anchor_walks = build_anchor_walks(anchor_members, proposed_walks, existing_walks)
    if not anchor_walks.get(HUB_ID):
        raise ValueError("Hub walking access bridge produced an empty catchment")

    coverage_cache: dict[frozenset[str], dict[int, object]] = {}
    def cached_summaries(stop_set: frozenset[str]):
        cached = coverage_cache.get(stop_set)
        if cached is None:
            cached = summarise_walk_coverage_thresholds(
                stop_set,
                walk_by_anchor=anchor_walks,
                unit_weights=unit_weights,
                unit_municipality=unit_municipality,
                municipality_totals=municipality_totals,
                thresholds=(5, 8, 10, 12),
            )
            coverage_cache[stop_set] = cached
        return cached

    fields = [
        "scenario_id", "topology_family",
        "public_explicit_stop_anchor_count", "extension_explicit_stop_anchor_count",
        *_summary_fields("public", municipality_codes_sorted),
        *_summary_fields("public_plus_extensions", municipality_codes_sorted),
        "hub_boarding_access_included", "hub_access_proxy_cluster_id",
        "proposed_stop_12min_unit_memberships_exact", "passenger_demand_inferred",
        "topology_ranked", "service_policy_selected", "primary_selected", "runner_up_selected",
    ]

    raw, gz, text = deterministic_gzip_text_writer(scenario_output)
    scenario_count = extension_scenario_count = 0
    scenarios_missing_hub = 0
    max_public_coverage_10 = max_public_worst_share_10 = 0.0
    try:
        writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for line_no, source_row in enumerate(reader, start=2):
                scenario_id = str(source_row["scenario_id"]).strip()
                family = str(source_row["topology_family"]).strip()
                public_routes = parse_routes(source_row["routes_json"], field="routes_json", line_no=line_no)
                extension_routes = parse_routes(source_row["optional_extensions_json"], field="optional_extensions_json", line_no=line_no)
                if not routes_contain_hub(public_routes):
                    scenarios_missing_hub += 1
                    raise ValueError(f"Structural public scenario {scenario_id} does not contain required hub")
                public_explicit = explicit_stop_anchors(public_routes, anchor_kinds=anchor_kinds)
                public_access = frozenset(set(public_explicit) | {HUB_ID})
                extension_explicit = (
                    explicit_stop_anchors(extension_routes, anchor_kinds=anchor_kinds)
                    if extension_routes else frozenset()
                )
                public_summaries = cached_summaries(public_access)
                if extension_explicit:
                    extension_scenario_count += 1
                    extended_summaries = cached_summaries(merge_anchor_sets(public_access, extension_explicit))
                else:
                    extended_summaries = public_summaries

                row = {
                    "scenario_id": scenario_id,
                    "topology_family": family,
                    "public_explicit_stop_anchor_count": len(public_explicit),
                    "extension_explicit_stop_anchor_count": len(extension_explicit),
                    "hub_boarding_access_included": "true",
                    "hub_access_proxy_cluster_id": hub_cluster,
                    "proposed_stop_12min_unit_memberships_exact": "false",
                    "passenger_demand_inferred": "false",
                    "topology_ranked": "false",
                    "service_policy_selected": "false",
                    "primary_selected": "false",
                    "runner_up_selected": "false",
                }
                _write_summary(row, prefix="public", summary_by_threshold=public_summaries, municipality_by_code=municipality_by_code)
                _write_summary(row, prefix="public_plus_extensions", summary_by_threshold=extended_summaries, municipality_by_code=municipality_by_code)
                writer.writerow(row)
                scenario_count += 1
                max_public_coverage_10 = max(max_public_coverage_10, public_summaries[10].coverage_share)
                max_public_worst_share_10 = max(max_public_worst_share_10, public_summaries[10].worst_municipality_coverage_share)
    finally:
        text.close()
        try: gz.close()
        except Exception: pass
        try: raw.close()
        except Exception: pass

    return {
        "scenario_count": scenario_count,
        "extension_scenario_count": extension_scenario_count,
        "unique_stop_set_count_evaluated": len(coverage_cache),
        "population_unit_count": len(unit_weights),
        "located_population": sum(unit_weights.values()),
        "municipality_count": len(municipality_totals),
        "municipalities": [
            {"code": code, "name": municipality_by_code[code], "located_population": municipality_totals[municipality_by_code[code]]}
            for code in municipality_codes_sorted
        ],
        "max_public_population_coverage_share_10min": max_public_coverage_10,
        "max_public_worst_municipality_coverage_share_10min": max_public_worst_share_10,
        "hub_boarding_access_included": True,
        "hub_access_proxy_cluster_id": hub_cluster,
        "scenarios_missing_required_hub": scenarios_missing_hub,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--catalog-validation", type=Path, required=True)
    p.add_argument("--stop-validation", type=Path, required=True)
    p.add_argument("--matrix-validation", type=Path, required=True)
    p.add_argument("--anchors", type=Path, required=True)
    p.add_argument("--proposed-catchments", type=Path, required=True)
    p.add_argument("--existing-catchments", type=Path, required=True)
    p.add_argument("--population-units", type=Path, required=True)
    p.add_argument("--hub-access-bridge", type=Path, required=True)
    p.add_argument("--scenario-output", type=Path, required=True)
    p.add_argument("--validation-output", type=Path, required=True)
    args = p.parse_args()

    _, stop, matrix = validate_upstream(
        catalog_path=args.catalog,
        catalog_validation_path=args.catalog_validation,
        stop_validation_path=args.stop_validation,
        matrix_validation_path=args.matrix_validation,
        anchor_path=args.anchors,
    )
    bridge = read_json(args.hub_access_bridge)
    if bridge.get("status") != "PASS_HUB_ACCESS_BRIDGE_V2_BUILD":
        raise ValueError("Hub bridge is not PASS")
    if bridge.get("lineage", {}).get("existing_catchments_sha256") != sha256_path(args.existing_catchments):
        raise ValueError("Hub bridge catchment lineage mismatch")
    if bridge.get("lineage", {}).get("matrix_validation_sha256") != sha256_path(args.matrix_validation):
        raise ValueError("Hub bridge matrix lineage mismatch")

    stats = materialise(
        catalog_path=args.catalog,
        anchor_path=args.anchors,
        proposed_catchment_path=args.proposed_catchments,
        existing_catchment_path=args.existing_catchments,
        population_path=args.population_units,
        hub_bridge_path=args.hub_access_bridge,
        scenario_output=args.scenario_output,
    )
    if stats["scenario_count"] != 100000 or stats["scenarios_missing_required_hub"] != 0:
        raise AssertionError("Corrected Access Equity V2 must cover 100000 hub-centred scenarios")
    if stats["population_unit_count"] != int(stop["population_units"]):
        raise AssertionError("Population universe mismatch")
    if not math.isclose(stats["located_population"], float(stop["core_population_located_building_pieces"]), rel_tol=0, abs_tol=1e-8):
        raise AssertionError("Located population mismatch")

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        **stats,
        "exact_population_access_thresholds_min": [5, 8, 10],
        "twelve_minute_candidate_access_exact": False,
        "twelve_minute_access_status": "CONSERVATIVE_LOWER_BOUND_PROPOSED_10MIN_PLUS_EXISTING_12MIN",
        "population_model_status": stop["population_model_status"],
        "unlocated_population_retained": float(stop["core_population_residual_unlocated"]),
        "passenger_demand_inferred": False,
        "s8_demand_used": False,
        "current_service_baseline_compared": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "stop_set_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "exact_timetable_constructed": False,
        "access_correction": "CERTIFIED_HUB_BOARDING_CATCHMENT_INCLUDED",
        "lineage": {
            "catalog_sha256": sha256_path(args.catalog),
            "catalog_validation_sha256": sha256_path(args.catalog_validation),
            "stop_validation_sha256": sha256_path(args.stop_validation),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "routing_anchor_universe_sha256": sha256_path(args.anchors),
            "proposed_catchments_sha256": sha256_path(args.proposed_catchments),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "population_units_sha256": sha256_path(args.population_units),
            "hub_access_bridge_sha256": sha256_path(args.hub_access_bridge),
            "scenario_output_sha256": sha256_path(args.scenario_output),
            "epoch_id": matrix["epoch_id"],
        },
        "limitations": [
            "Building resident counts are model outputs, not observed residents by address.",
            "The 93.16-person core residual remains unlocated and is not assigned to any catchment.",
            "Proposed-stop unit memberships are certified only through 10 minutes; 12-minute candidate coverage remains a conservative lower bound.",
            "The hub walking catchment is inherited from the uniquely identified official Olgiate station bus-stop cluster within 100 m; this is a boarding-access proxy, not a current-service activation claim.",
            "No resident is treated as a passenger and no municipal OD is downscaled to a building or stop."
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
