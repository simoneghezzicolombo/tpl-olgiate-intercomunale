#!/usr/bin/env python3
"""Materialise source-closed building-population accessibility/equity V2.

Consumes the certified Structural Catalog V2, Stop Universe V2 and routing
anchor universe. The output is scenario-level access evidence only. It does not
use passenger demand, S8 phasing, service-policy feasibility or any ranking
rule.
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

from src.phase2_access_equity_v2 import (
    EXACT_THRESHOLDS_MIN,
    LOWER_BOUND_THRESHOLD_MIN,
    merge_anchor_sets,
    summarise_walk_coverage_thresholds,
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_gzip_text_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, gz, text


def load_population_units(path: Path):
    weights: dict[str, float] = {}
    municipalities: dict[str, str] = {}
    totals: dict[str, float] = {}
    municipality_codes: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            unit_id = str(row["population_unit_id"]).strip()
            municipality = str(row["COMUNE"]).strip()
            municipality_code = str(row["PRO_COM_T"]).strip()
            weight = float(row["building_piece_population_model"])
            if not unit_id or not municipality or not municipality_code:
                raise ValueError(f"Missing population-unit identity at line {line_no}")
            if unit_id in weights:
                raise ValueError(f"Duplicate population unit {unit_id!r}")
            if not math.isfinite(weight) or weight < 0:
                raise ValueError(f"Invalid population weight at line {line_no}")
            if municipality in municipality_codes and municipality_codes[municipality] != municipality_code:
                raise ValueError(f"Conflicting municipality code for {municipality!r}")
            weights[unit_id] = weight
            municipalities[unit_id] = municipality
            totals[municipality] = totals.get(municipality, 0.0) + weight
            municipality_codes[municipality] = municipality_code
    if not weights:
        raise ValueError("Population universe is empty")
    return weights, municipalities, totals, municipality_codes


def load_anchor_source_members(path: Path):
    members: dict[str, tuple[tuple[str, str], ...]] = {}
    kinds: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            anchor_id = str(row["anchor_id"]).strip()
            source_kind = str(row["source_kind"]).strip()
            if not anchor_id or not source_kind:
                raise ValueError(f"Missing anchor identity at line {line_no}")
            if anchor_id in members:
                raise ValueError(f"Duplicate routing anchor {anchor_id!r}")
            parsed: list[tuple[str, str]] = []
            if source_kind == "PROPOSED_STOP":
                parsed.append(("PROPOSED_STOP", anchor_id))
            elif source_kind == "EXISTING_PHYSICAL_STOP_CLUSTER":
                for token in str(row["source_members"]).split(";"):
                    token = token.strip()
                    if token.startswith("existing:"):
                        token = token[len("existing:"):]
                    if not token:
                        raise ValueError(f"Empty existing source member at line {line_no}")
                    parsed.append(("EXISTING_PHYSICAL_STOP_CLUSTER", token))
            elif source_kind == "HUB_RAIL":
                parsed = []
            else:
                raise ValueError(f"Unsupported source_kind {source_kind!r}")
            members[anchor_id] = tuple(parsed)
            kinds[anchor_id] = source_kind
    return members, kinds


def _append_walk(target: dict[str, dict[str, float]], stop_id: str, unit_id: str, walk_min: float) -> None:
    if not math.isfinite(walk_min) or walk_min < 0:
        raise ValueError("Catchment walk time must be finite and non-negative")
    previous = target.setdefault(stop_id, {}).get(unit_id)
    if previous is None or walk_min < previous:
        target[stop_id][unit_id] = walk_min


def load_stop_walks(proposed_path: Path, existing_path: Path, *, unit_weights: dict[str, float]):
    proposed: dict[str, dict[str, float]] = {}
    with proposed_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            stop_id = str(row["candidate_id"]).strip()
            unit_id = str(row["population_unit_id"]).strip()
            walk_min = float(row["walk_min_to_candidate"])
            row_weight = float(row["building_piece_population_model"])
            if unit_id not in unit_weights:
                raise ValueError(f"Unknown proposed catchment unit {unit_id!r}")
            if not math.isclose(row_weight, unit_weights[unit_id], rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"Proposed catchment population mismatch for {unit_id!r}")
            if walk_min > 10.0 + 1e-9:
                raise ValueError(f"Proposed catchment row exceeds certified 10-minute membership at line {line_no}")
            _append_walk(proposed, stop_id, unit_id, walk_min)

    existing: dict[str, dict[str, float]] = {}
    with existing_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            stop_id = str(row["physical_cluster_id"]).strip()
            unit_id = str(row["population_unit_id"]).strip()
            walk_min = float(row["walk_min_to_stop"])
            row_weight = float(row["building_piece_population_model"])
            if unit_id not in unit_weights:
                raise ValueError(f"Unknown existing catchment unit {unit_id!r}")
            if not math.isclose(row_weight, unit_weights[unit_id], rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"Existing catchment population mismatch for {unit_id!r}")
            if walk_min > 12.0 + 1e-9:
                raise ValueError(f"Existing catchment row exceeds certified 12-minute membership at line {line_no}")
            _append_walk(existing, stop_id, unit_id, walk_min)
    return proposed, existing


def build_anchor_walks(anchor_members, proposed_walks, existing_walks):
    out: dict[str, dict[str, float]] = {}
    for anchor_id, source_members in anchor_members.items():
        merged: dict[str, float] = {}
        for source_kind, stop_id in source_members:
            source = proposed_walks.get(stop_id, {}) if source_kind == "PROPOSED_STOP" else existing_walks.get(stop_id, {})
            for unit_id, walk_min in source.items():
                previous = merged.get(unit_id)
                if previous is None or walk_min < previous:
                    merged[unit_id] = walk_min
        out[anchor_id] = merged
    return out


def parse_routes(value: str, *, field: str, line_no: int) -> list[list[str]]:
    raw = json.loads(value)
    if not isinstance(raw, list):
        raise ValueError(f"{field} must be a list at line {line_no}")
    routes: list[list[str]] = []
    for route in raw:
        if not isinstance(route, list) or len(route) < 2 or any(not str(anchor).strip() for anchor in route):
            raise ValueError(f"Invalid route in {field} at line {line_no}")
        routes.append([str(anchor).strip() for anchor in route])
    return routes


def explicit_stop_anchors(routes: list[list[str]], *, anchor_kinds: dict[str, str]) -> frozenset[str]:
    anchors: set[str] = set()
    for route in routes:
        for anchor_id in route:
            if anchor_id not in anchor_kinds:
                raise ValueError(f"Scenario references unknown anchor {anchor_id!r}")
            if anchor_kinds[anchor_id] != "HUB_RAIL":
                anchors.add(anchor_id)
    return frozenset(anchors)


def fmt(value: float) -> str:
    return f"{value:.12f}"


def _summary_fields(prefix: str, municipality_codes_sorted: list[str]) -> list[str]:
    fields: list[str] = []
    for threshold in EXACT_THRESHOLDS_MIN:
        fields += [
            f"{prefix}_population_covered_{threshold}min",
            f"{prefix}_population_coverage_share_{threshold}min",
            f"{prefix}_worst_municipality_{threshold}min",
            f"{prefix}_worst_municipality_coverage_share_{threshold}min",
        ]
        fields += [
            f"{prefix}_municipality_{code}_coverage_share_{threshold}min"
            for code in municipality_codes_sorted
        ]
    fields += [
        f"{prefix}_population_covered_12min_conservative_lower_bound",
        f"{prefix}_population_coverage_share_12min_conservative_lower_bound",
        f"{prefix}_worst_municipality_12min_conservative_lower_bound",
        f"{prefix}_worst_municipality_coverage_share_12min_conservative_lower_bound",
    ]
    fields += [
        f"{prefix}_municipality_{code}_coverage_share_12min_conservative_lower_bound"
        for code in municipality_codes_sorted
    ]
    return fields


def _write_summary(row, *, prefix: str, summary_by_threshold, municipality_by_code) -> None:
    for threshold in EXACT_THRESHOLDS_MIN:
        summary = summary_by_threshold[threshold]
        row[f"{prefix}_population_covered_{threshold}min"] = fmt(summary.covered_population)
        row[f"{prefix}_population_coverage_share_{threshold}min"] = fmt(summary.coverage_share)
        row[f"{prefix}_worst_municipality_{threshold}min"] = summary.worst_municipality
        row[f"{prefix}_worst_municipality_coverage_share_{threshold}min"] = fmt(summary.worst_municipality_coverage_share)
        for code, municipality in municipality_by_code.items():
            row[f"{prefix}_municipality_{code}_coverage_share_{threshold}min"] = fmt(summary.municipality_coverage_share[municipality])
    summary12 = summary_by_threshold[12]
    row[f"{prefix}_population_covered_12min_conservative_lower_bound"] = fmt(summary12.covered_population)
    row[f"{prefix}_population_coverage_share_12min_conservative_lower_bound"] = fmt(summary12.coverage_share)
    row[f"{prefix}_worst_municipality_12min_conservative_lower_bound"] = summary12.worst_municipality
    row[f"{prefix}_worst_municipality_coverage_share_12min_conservative_lower_bound"] = fmt(summary12.worst_municipality_coverage_share)
    for code, municipality in municipality_by_code.items():
        row[f"{prefix}_municipality_{code}_coverage_share_12min_conservative_lower_bound"] = fmt(summary12.municipality_coverage_share[municipality])


def materialise(*, catalog_path, anchor_path, proposed_catchment_path, existing_catchment_path, population_path, scenario_output):
    unit_weights, unit_municipality, municipality_totals, municipality_codes = load_population_units(population_path)
    municipality_by_code = {municipality_codes[m]: m for m in sorted(municipality_totals)}
    municipality_codes_sorted = sorted(municipality_by_code)
    anchor_members, anchor_kinds = load_anchor_source_members(anchor_path)
    proposed_walks, existing_walks = load_stop_walks(proposed_catchment_path, existing_catchment_path, unit_weights=unit_weights)
    anchor_walks = build_anchor_walks(anchor_members, proposed_walks, existing_walks)
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
        "proposed_stop_12min_unit_memberships_exact", "passenger_demand_inferred",
        "topology_ranked", "service_policy_selected", "primary_selected", "runner_up_selected",
    ]

    raw, gz, text = deterministic_gzip_text_writer(scenario_output)
    try:
        writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        scenario_count = 0
        extension_scenario_count = 0
        max_public_coverage_10 = 0.0
        max_public_worst_share_10 = 0.0
        with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for line_no, source_row in enumerate(reader, start=2):
                scenario_id = str(source_row["scenario_id"]).strip()
                family = str(source_row["topology_family"]).strip()
                public_routes = parse_routes(source_row["routes_json"], field="routes_json", line_no=line_no)
                extension_routes = parse_routes(source_row["optional_extensions_json"], field="optional_extensions_json", line_no=line_no)
                public_anchors = explicit_stop_anchors(public_routes, anchor_kinds=anchor_kinds)
                extension_anchors = explicit_stop_anchors(extension_routes, anchor_kinds=anchor_kinds) if extension_routes else frozenset()
                public_summaries = cached_summaries(public_anchors)
                if extension_anchors:
                    extension_scenario_count += 1
                    extended_summaries = cached_summaries(merge_anchor_sets(public_anchors, extension_anchors))
                else:
                    extended_summaries = public_summaries

                row = {
                    "scenario_id": scenario_id,
                    "topology_family": family,
                    "public_explicit_stop_anchor_count": len(public_anchors),
                    "extension_explicit_stop_anchor_count": len(extension_anchors),
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
        try:
            gz.close()
        except Exception:
            pass
        try:
            raw.close()
        except Exception:
            pass

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
    }


def validate_upstream(*, catalog_path, catalog_validation_path, stop_validation_path, matrix_validation_path, anchor_path):
    catalog = read_json(catalog_validation_path)
    stop = read_json(stop_validation_path)
    matrix = read_json(matrix_validation_path)
    if catalog.get("status") != "PASS_STRUCTURAL_CATALOG_V2_BUILD":
        raise ValueError("Structural Catalog V2 is not PASS")
    if int(catalog.get("generated_scenario_count", -1)) != 100000:
        raise ValueError("Structural Catalog V2 must contain 100000 scenarios")
    if stop.get("status") != "PASS_STOP_UNIVERSE_V2_BUILD":
        raise ValueError("Stop Universe V2 is not PASS")
    if int(stop.get("population_units", -1)) != 4348:
        raise ValueError("Unexpected Stop Universe V2 population-unit count")
    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD":
        raise ValueError("Reduced Path Matrix V2 is not PASS")
    if matrix.get("lineage", {}).get("routing_anchor_universe_sha256") != sha256_path(anchor_path):
        raise ValueError("Routing anchor universe hash mismatch")
    if catalog.get("lineage", {}).get("scenario_catalog_sha256") != sha256_path(catalog_path):
        raise ValueError("Structural catalog hash mismatch")
    return catalog, stop, matrix


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-validation", type=Path, required=True)
    parser.add_argument("--stop-validation", type=Path, required=True)
    parser.add_argument("--matrix-validation", type=Path, required=True)
    parser.add_argument("--anchors", type=Path, required=True)
    parser.add_argument("--proposed-catchments", type=Path, required=True)
    parser.add_argument("--existing-catchments", type=Path, required=True)
    parser.add_argument("--population-units", type=Path, required=True)
    parser.add_argument("--scenario-output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()

    _, stop, matrix = validate_upstream(
        catalog_path=args.catalog,
        catalog_validation_path=args.catalog_validation,
        stop_validation_path=args.stop_validation,
        matrix_validation_path=args.matrix_validation,
        anchor_path=args.anchors,
    )
    stats = materialise(
        catalog_path=args.catalog,
        anchor_path=args.anchors,
        proposed_catchment_path=args.proposed_catchments,
        existing_catchment_path=args.existing_catchments,
        population_path=args.population_units,
        scenario_output=args.scenario_output,
    )
    if stats["scenario_count"] != 100000:
        raise AssertionError("Access/equity output must contain 100000 scenarios")
    if stats["population_unit_count"] != int(stop["population_units"]):
        raise AssertionError("Access/equity population universe differs from Stop Universe V2")
    if not math.isclose(stats["located_population"], float(stop["core_population_located_building_pieces"]), rel_tol=0.0, abs_tol=1e-8):
        raise AssertionError("Located population does not reconcile to Stop Universe V2")

    validation = {
        "status": "PASS_ACCESS_EQUITY_V2_BUILD",
        "contract": "PHASE2_BUILDING_CATCHMENT_ACCESS_EQUITY_V2",
        **stats,
        "exact_population_access_thresholds_min": list(EXACT_THRESHOLDS_MIN),
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
        "lineage": {
            "catalog_sha256": sha256_path(args.catalog),
            "catalog_validation_sha256": sha256_path(args.catalog_validation),
            "stop_validation_sha256": sha256_path(args.stop_validation),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "routing_anchor_universe_sha256": sha256_path(args.anchors),
            "proposed_catchments_sha256": sha256_path(args.proposed_catchments),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "population_units_sha256": sha256_path(args.population_units),
            "scenario_output_sha256": sha256_path(args.scenario_output),
            "epoch_id": matrix["epoch_id"],
        },
        "limitations": [
            "Building resident counts are model outputs, not observed residents by address.",
            "The 93.16-person core residual remains unlocated and is not assigned to any catchment.",
            "Proposed-stop unit memberships are certified only through 10 minutes in Stop Universe V2; 12-minute candidate coverage is therefore reported only as a conservative lower bound.",
            "Existing official stop evidence is reference-period GTFS evidence and is not promoted to exact current-service truth.",
            "No resident is treated as a passenger and no municipal OD is downscaled to a building or stop in this stage.",
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
