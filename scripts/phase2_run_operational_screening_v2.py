#!/usr/bin/env python3
"""Materialise assumption-free Operational Screening V2 lower bounds.

Consumes only certified V2 structural/matrix outputs plus the already-declared
Phase 2 bus-km envelopes. It does not choose a headway, calendar, recovery,
fleet, extension share, timetable, stop set or topology.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_run_structural_search import load_reduced_path_matrix
from scripts.phase2_screen_structural_catalog import parse_routes, sha256_path
from src.phase2_operational_screening import (
    aggregate_route_lower_bounds,
    maximum_equal_pattern_sets_per_year,
    route_operational_lower_bound,
)


EXPECTED_FRACTIONS = (-0.2, -0.1, 0.0, 0.1, 0.2, 0.3)
CAPACITY_SUFFIX = {
    -0.2: "m20pct",
    -0.1: "m10pct",
    0.0: "reference",
    0.1: "p10pct",
    0.2: "p20pct",
    0.3: "p30pct",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_upstream_lineage(
    *,
    catalog_path: Path,
    catalog_validation_path: Path,
    screening_path: Path,
    screening_validation_path: Path,
    matrix_path: Path,
    matrix_validation_path: Path,
    anchor_path: Path,
) -> tuple[dict, dict, dict]:
    catalog = _load_json(catalog_validation_path)
    screening = _load_json(screening_validation_path)
    matrix = _load_json(matrix_validation_path)

    if catalog.get("status") != "PASS_STRUCTURAL_CATALOG_V2_BUILD":
        raise ValueError("Structural Catalog V2 upstream status is not PASS")
    if catalog.get("contract") != "PHASE2_BALANCED_STRUCTURAL_SEARCH_V2":
        raise ValueError("Unexpected Structural Catalog V2 contract")
    if int(catalog.get("generated_scenario_count", -1)) != 100_000:
        raise ValueError("Structural Catalog V2 must contain 100000 scenarios")
    if any(catalog.get(key) is not False for key in ("selects_topology", "selects_stops", "chooses_service_policy")):
        raise ValueError("Structural Catalog V2 contains a forbidden downstream selection")

    if screening.get("status") != "PASS_STRUCTURAL_SCREENING_V2_BUILD":
        raise ValueError("Structural Screening V2 upstream status is not PASS")
    if screening.get("contract") != "PHASE2_TOPOLOGY_NEUTRAL_STRUCTURAL_SCREENING_V2":
        raise ValueError("Unexpected Structural Screening V2 contract")
    if int(screening.get("scenario_count", -1)) != 100_000:
        raise ValueError("Structural Screening V2 must contain 100000 scenarios")
    for key in ("selects_topology", "ranks_topology_family", "selects_stops", "annualises_service", "chooses_service_policy"):
        if screening.get(key) is not False:
            raise ValueError(f"Structural Screening V2 flag {key} is not false")

    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD":
        raise ValueError("Reduced Path Matrix V2 upstream status is not PASS")
    if matrix.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Unexpected Reduced Path Matrix V2 contract")

    expected_actual = {
        "catalog": (catalog.get("lineage", {}).get("scenario_catalog_sha256"), sha256_path(catalog_path)),
        "catalog matrix": (catalog.get("lineage", {}).get("reduced_path_matrix_sha256"), sha256_path(matrix_path)),
        "catalog anchors": (catalog.get("lineage", {}).get("routing_anchor_universe_sha256"), sha256_path(anchor_path)),
        "screening output": (screening.get("lineage", {}).get("screening_output_sha256"), sha256_path(screening_path)),
        "screening catalog": (screening.get("lineage", {}).get("catalog_sha256"), sha256_path(catalog_path)),
        "screening matrix": (screening.get("lineage", {}).get("path_matrix_sha256"), sha256_path(matrix_path)),
        "screening anchors": (screening.get("lineage", {}).get("anchor_universe_sha256"), sha256_path(anchor_path)),
        "matrix": (matrix.get("lineage", {}).get("reduced_path_matrix_sha256"), sha256_path(matrix_path)),
        "matrix anchors": (matrix.get("lineage", {}).get("routing_anchor_universe_sha256"), sha256_path(anchor_path)),
    }
    for label, (expected, actual) in expected_actual.items():
        if expected != actual:
            raise ValueError(f"V2 upstream hash mismatch for {label}")
    epochs = {str(catalog.get("epoch_id")), str(screening.get("epoch_id")), str(matrix.get("epoch_id"))}
    if len(epochs) != 1:
        raise ValueError(f"Operational Screening V2 upstream epochs differ: {sorted(epochs)}")
    return catalog, screening, matrix


def load_budget_envelopes(csv_path: Path, validation_path: Path) -> tuple[list[tuple[float, float]], dict]:
    validation = _load_json(validation_path)
    if validation.get("status") != "PASS":
        raise ValueError("Budget-envelope validation is not PASS")
    if validation.get("not_a_service_plan") is not True:
        raise ValueError("Budget envelopes must remain explicitly not a service plan")
    if validation.get("budget_status") != "DERIVED_FROM_PDB_RECONSTRUCTED_LINE_TOTALS":
        raise ValueError("Unexpected budget reference epistemic status")
    if int(validation.get("envelope_count", -1)) != 6:
        raise ValueError("Expected six declared budget envelopes")

    rows: list[tuple[float, float]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            fraction = float(row["budget_change_fraction"])
            cap = float(row["annual_bus_km_cap"])
            if str(row["envelope_status"]) != "PHASE2_DECLARED_DESIGN_SEARCH_ENVELOPE":
                raise ValueError("Unexpected budget-envelope status")
            if str(row["reference_status"]) != "DERIVED_FROM_PDB_RECONSTRUCTED_LINE_TOTALS":
                raise ValueError("Unexpected budget reference status in CSV")
            rows.append((fraction, cap))
    rows.sort()
    fractions = tuple(f for f, _ in rows)
    if fractions != EXPECTED_FRACTIONS:
        raise ValueError(f"Unexpected budget fractions: {fractions}")
    json_fractions = tuple(float(v) for v in validation["declared_changes_fraction"])
    json_caps = tuple(float(v) for v in validation["annual_bus_km_caps"])
    if json_fractions != fractions:
        raise ValueError("Budget CSV fractions differ from validation JSON")
    for (_, cap), expected in zip(rows, json_caps):
        if not math.isclose(cap, expected, rel_tol=0.0, abs_tol=1e-8):
            raise ValueError("Budget CSV cap differs from validation JSON")
    return rows, validation


def load_anchor_meta(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            anchor_id = str(row.get("anchor_id", "")).strip()
            evidence = str(row.get("evidence_status", "")).strip()
            source_kind = str(row.get("source_kind", "")).strip().upper()
            if not anchor_id:
                raise ValueError(f"Empty routing anchor at line {line_no}")
            if anchor_id in result:
                raise ValueError(f"Duplicate routing anchor {anchor_id}")
            if evidence in {"PLACEHOLDER", "INVALIDATED", "FACT", "DERIVED"}:
                raise ValueError(f"Operational screening refuses degraded/forbidden evidence {evidence!r}")
            result[anchor_id] = {"evidence_status": evidence, "source_kind": source_kind}
    if not result:
        raise ValueError("Routing anchor universe is empty")
    return result


def _capacity_columns(prefix: str, cycle_distance: float | None, envelopes: list[tuple[float, float]]) -> dict[str, int | str]:
    out: dict[str, int | str] = {}
    for fraction, cap in envelopes:
        key = f"max_equal_{prefix}_pattern_sets_per_year_{CAPACITY_SUFFIX[fraction]}"
        out[key] = "" if cycle_distance is None else maximum_equal_pattern_sets_per_year(cap, cycle_distance)
    return out


def materialise(
    *,
    catalog_path: Path,
    screening_path: Path,
    matrix_path: Path,
    anchor_path: Path,
    envelopes: list[tuple[float, float]],
    output_path: Path,
) -> dict:
    matrix = load_reduced_path_matrix(matrix_path)
    anchor_meta = load_anchor_meta(anchor_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scenario_count = 0
    pass_count = 0
    fail_count = 0
    closure_scenario_count = 0
    family_counts: dict[str, int] = {}
    unique_public_legs: set[tuple[str, str]] = set()
    writer = None

    with catalog_path.open(encoding="utf-8-sig", newline="") as catalog_handle, \
         screening_path.open(encoding="utf-8-sig", newline="") as screening_handle, \
         output_path.open("w", encoding="utf-8", newline="") as output_handle:
        catalog_reader = csv.DictReader(catalog_handle)
        screening_reader = csv.DictReader(screening_handle)
        for line_no, (catalog_row, structural_row) in enumerate(zip(catalog_reader, screening_reader), start=2):
            scenario_id = str(catalog_row["scenario_id"])
            family = str(catalog_row["topology_family"])
            if scenario_id != str(structural_row["scenario_id"]) or family != str(structural_row["topology_family"]):
                raise ValueError(f"Catalog/screening row alignment mismatch at line {line_no}")
            public_routes = parse_routes(catalog_row["routes_json"], field="routes_json", line_no=line_no)
            extensions = parse_routes(
                catalog_row["optional_extensions_json"], field="optional_extensions_json", line_no=line_no
            )
            for route in public_routes:
                unique_public_legs.update(zip(route[:-1], route[1:]))
            public_bounds = [route_operational_lower_bound(matrix, route) for route in public_routes]
            public = aggregate_route_lower_bounds(public_bounds)
            extension_bounds = [route_operational_lower_bound(matrix, route) for route in extensions]
            extension = aggregate_route_lower_bounds(extension_bounds) if extension_bounds else None

            if not math.isclose(
                float(public["public_distance_km"]), float(structural_row["public_distance_km"]), rel_tol=0.0, abs_tol=1e-7
            ):
                raise ValueError(f"Public distance mismatch for {scenario_id}")
            if not math.isclose(
                float(public["public_runtime_min"]), float(structural_row["public_runtime_min"]), rel_tol=0.0, abs_tol=1e-7
            ):
                raise ValueError(f"Public runtime mismatch for {scenario_id}")

            explicit_public = {anchor for route in public_routes for anchor in route}
            missing = sorted(explicit_public - set(anchor_meta))
            if missing:
                raise ValueError(f"Scenario {scenario_id} references unknown anchors {missing[:5]}")
            proposed_count = sum(anchor_meta[a]["source_kind"] == "PROPOSED_STOP" for a in explicit_public)
            existing_count = sum(anchor_meta[a]["source_kind"] == "EXISTING_PHYSICAL_STOP_CLUSTER" for a in explicit_public)
            pending_count = sum(
                anchor_meta[a]["evidence_status"] == "PROPOSED_STOP/FIELD_CHECK_PENDING" for a in explicit_public
            )
            operational_pass = bool(public["all_return_closable"])
            status = "PASS_TO_SERVICE_POLICY_SEARCH" if operational_pass else "FAIL_UNCLOSABLE_PUBLIC_ROUTE"
            if operational_pass:
                pass_count += 1
            else:
                fail_count += 1
            if int(public["closure_added_route_count"]) > 0:
                closure_scenario_count += 1

            row = {
                "scenario_id": scenario_id,
                "topology_family": family,
                "public_route_count": int(public["route_count"]),
                "optional_extension_count": len(extensions),
                "public_open_route_count": int(public["open_route_count"]),
                "public_closure_added_route_count": int(public["closure_added_route_count"]),
                "all_public_routes_return_closable": str(bool(public["all_return_closable"])).lower(),
                "public_distance_km": f"{float(public['public_distance_km']):.9f}",
                "public_runtime_min": f"{float(public['public_runtime_min']):.9f}",
                "public_return_closure_distance_km": "" if public["return_closure_distance_km"] is None else f"{float(public['return_closure_distance_km']):.9f}",
                "public_return_closure_runtime_min": "" if public["return_closure_runtime_min"] is None else f"{float(public['return_closure_runtime_min']):.9f}",
                "public_equal_pattern_set_cycle_distance_km_lower_bound": "" if public["equal_pattern_set_cycle_distance_km_lower_bound"] is None else f"{float(public['equal_pattern_set_cycle_distance_km_lower_bound']):.9f}",
                "public_equal_pattern_set_cycle_runtime_min_lower_bound": "" if public["equal_pattern_set_cycle_runtime_min_lower_bound"] is None else f"{float(public['equal_pattern_set_cycle_runtime_min_lower_bound']):.9f}",
                "public_max_single_route_cycle_runtime_min_lower_bound": "" if public["max_single_route_cycle_runtime_min_lower_bound"] is None else f"{float(public['max_single_route_cycle_runtime_min_lower_bound']):.9f}",
                "public_operational_resolved_distance_km_lower_bound": "" if public["operational_resolved_distance_km_lower_bound"] is None else f"{float(public['operational_resolved_distance_km_lower_bound']):.9f}",
                "public_operational_quantified_distance_km_lower_bound": "" if public["operational_quantified_distance_km_lower_bound"] is None else f"{float(public['operational_quantified_distance_km_lower_bound']):.9f}",
                "public_operational_unknown_distance_km_lower_bound": "" if public["operational_unknown_distance_km_lower_bound"] is None else f"{float(public['operational_unknown_distance_km_lower_bound']):.9f}",
                "public_operational_unknown_distance_share_lower_bound": "" if public["operational_unknown_distance_share_lower_bound"] is None else f"{float(public['operational_unknown_distance_share_lower_bound']):.12f}",
                "all_extensions_return_closable": "" if extension is None else str(bool(extension["all_return_closable"])).lower(),
                "extension_equal_pattern_set_cycle_distance_km_lower_bound": "" if extension is None or extension["equal_pattern_set_cycle_distance_km_lower_bound"] is None else f"{float(extension['equal_pattern_set_cycle_distance_km_lower_bound']):.9f}",
                "extension_equal_pattern_set_cycle_runtime_min_lower_bound": "" if extension is None or extension["equal_pattern_set_cycle_runtime_min_lower_bound"] is None else f"{float(extension['equal_pattern_set_cycle_runtime_min_lower_bound']):.9f}",
                "public_explicit_proposed_stop_count": proposed_count,
                "public_explicit_existing_stop_count": existing_count,
                "public_explicit_field_check_pending_count": pending_count,
                "operational_screen_status": status,
                **_capacity_columns("public", public["equal_pattern_set_cycle_distance_km_lower_bound"], envelopes),
            }
            if extension is not None and public["equal_pattern_set_cycle_distance_km_lower_bound"] is not None and extension["equal_pattern_set_cycle_distance_km_lower_bound"] is not None:
                combined_distance = float(public["equal_pattern_set_cycle_distance_km_lower_bound"]) + float(extension["equal_pattern_set_cycle_distance_km_lower_bound"])
            else:
                combined_distance = None
            row.update(_capacity_columns("public_plus_all_extensions", combined_distance, envelopes))

            if writer is None:
                writer = csv.DictWriter(output_handle, fieldnames=list(row), lineterminator="\n")
                writer.writeheader()
            writer.writerow(row)
            scenario_count += 1
            family_counts[family] = family_counts.get(family, 0) + 1

        try:
            extra_catalog = next(catalog_reader)
        except StopIteration:
            extra_catalog = None
        try:
            extra_screening = next(screening_reader)
        except StopIteration:
            extra_screening = None
        if extra_catalog is not None or extra_screening is not None:
            raise ValueError("Catalog and structural screening row counts differ")

    if scenario_count == 0:
        raise ValueError("Operational screening produced no scenarios")
    return {
        "scenario_count": scenario_count,
        "operational_pass_count": pass_count,
        "operational_fail_count": fail_count,
        "return_closure_added_scenario_count": closure_scenario_count,
        "family_counts": dict(sorted(family_counts.items())),
        "unique_public_directed_legs_rechecked": len(unique_public_legs),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--catalog-validation", required=True, type=Path)
    parser.add_argument("--structural-screening", required=True, type=Path)
    parser.add_argument("--structural-screening-validation", required=True, type=Path)
    parser.add_argument("--path-matrix", required=True, type=Path)
    parser.add_argument("--matrix-validation", required=True, type=Path)
    parser.add_argument("--anchor-universe", required=True, type=Path)
    parser.add_argument("--budget-envelopes", required=True, type=Path)
    parser.add_argument("--budget-validation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    paths = [
        args.catalog, args.catalog_validation, args.structural_screening,
        args.structural_screening_validation, args.path_matrix, args.matrix_validation,
        args.anchor_universe, args.budget_envelopes, args.budget_validation,
    ]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    catalog_validation, screening_validation, matrix_validation = validate_upstream_lineage(
        catalog_path=args.catalog,
        catalog_validation_path=args.catalog_validation,
        screening_path=args.structural_screening,
        screening_validation_path=args.structural_screening_validation,
        matrix_path=args.path_matrix,
        matrix_validation_path=args.matrix_validation,
        anchor_path=args.anchor_universe,
    )
    envelopes, budget_validation = load_budget_envelopes(args.budget_envelopes, args.budget_validation)
    summary = materialise(
        catalog_path=args.catalog,
        screening_path=args.structural_screening,
        matrix_path=args.path_matrix,
        anchor_path=args.anchor_universe,
        envelopes=envelopes,
        output_path=args.output,
    )
    if summary["scenario_count"] != 100_000:
        raise RuntimeError(f"Expected 100000 operational-screening rows, got {summary['scenario_count']}")

    validation = {
        "status": "PASS_OPERATIONAL_SCREENING_V2_BUILD",
        "contract": "PHASE2_OPERATIONAL_LOWER_BOUND_SCREENING_V2",
        "evidence_label": "V2_OPERATIONAL_LOWER_BOUNDS_NOT_SERVICE_POLICY",
        "epoch_id": matrix_validation["epoch_id"],
        **summary,
        "budget_reference_annual_bus_km": float(budget_validation["reference_annual_bus_km"]),
        "budget_reference_status": budget_validation["budget_status"],
        "budget_envelope_count": len(envelopes),
        "budget_change_fractions": [fraction for fraction, _ in envelopes],
        "budget_caps_annual_bus_km": [cap for _, cap in envelopes],
        "headway_assumed": False,
        "calendar_assumed": False,
        "service_days_assumed": False,
        "recovery_assumed": False,
        "fleet_assumed": False,
        "extension_share_assumed": False,
        "service_policy_selected": False,
        "topology_ranked": False,
        "stop_set_selected": False,
        "annual_service_plan_produced": False,
        "computes_budget_capacity_upper_bounds": True,
        "budget_capacity_is_service_plan": False,
        "lineage": {
            "catalog_validation": str(args.catalog_validation),
            "catalog_validation_sha256": sha256_path(args.catalog_validation),
            "catalog": str(args.catalog),
            "catalog_sha256": sha256_path(args.catalog),
            "structural_screening_validation": str(args.structural_screening_validation),
            "structural_screening_validation_sha256": sha256_path(args.structural_screening_validation),
            "structural_screening": str(args.structural_screening),
            "structural_screening_sha256": sha256_path(args.structural_screening),
            "matrix_validation": str(args.matrix_validation),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "path_matrix": str(args.path_matrix),
            "path_matrix_sha256": sha256_path(args.path_matrix),
            "anchor_universe": str(args.anchor_universe),
            "anchor_universe_sha256": sha256_path(args.anchor_universe),
            "budget_envelopes": str(args.budget_envelopes),
            "budget_envelopes_sha256": sha256_path(args.budget_envelopes),
            "budget_validation": str(args.budget_validation),
            "budget_validation_sha256": sha256_path(args.budget_validation),
            "operational_screening": str(args.output),
            "operational_screening_sha256": sha256_path(args.output),
            "upstream_catalog_contract": catalog_validation["contract"],
            "upstream_structural_screening_contract": screening_validation["contract"],
            "upstream_matrix_contract": matrix_validation["contract"],
        },
        "epistemic_note": (
            "Operational cycle metrics are minimum closed-route lower bounds derived only from certified directed matrix legs. "
            "Budget-capacity values are floor(cap / minimum equal-pattern-set cycle km), so they are resource upper bounds, "
            "not departures, headways, calendars, frequencies, fleet requirements or service plans."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
