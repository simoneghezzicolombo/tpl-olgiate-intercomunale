#!/usr/bin/env python3
"""Topology-neutral structural screening for the validated Phase 2 V2 catalog.

The numerical screening engine is the already-audited generic implementation in
`phase2_screen_structural_catalog.py`. This wrapper adds V2 lineage closure and
refuses to run unless the persisted Structural Catalog V2 and Reduced Path Matrix
V2 hashes match their PASS validation records.

No topology, stop set, headway, timetable or service policy is selected here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_screen_structural_catalog import screen_catalog, sha256_path


CATALOG_STATUS = "PASS_STRUCTURAL_CATALOG_V2_BUILD"
CATALOG_CONTRACT = "PHASE2_BALANCED_STRUCTURAL_SEARCH_V2"
MATRIX_STATUS = "PASS_REDUCED_PATH_MATRIX_V2_BUILD"
MATRIX_CONTRACT = "PHASE2_REDUCED_STOP_PATH_MATRIX_V2"


def validate_v2_lineage(
    *,
    catalog_path: Path,
    catalog_validation_path: Path,
    matrix_path: Path,
    matrix_validation_path: Path,
    anchor_path: Path,
) -> tuple[dict, dict]:
    catalog_validation = json.loads(catalog_validation_path.read_text(encoding="utf-8"))
    matrix_validation = json.loads(matrix_validation_path.read_text(encoding="utf-8"))

    if catalog_validation.get("status") != CATALOG_STATUS:
        raise ValueError("Structural Catalog V2 upstream status is not PASS")
    if catalog_validation.get("contract") != CATALOG_CONTRACT:
        raise ValueError("Unexpected Structural Catalog V2 contract")
    if int(catalog_validation.get("generated_scenario_count", -1)) != 100_000:
        raise ValueError("Structural Catalog V2 is not the certified 100,000-scenario catalog")
    if catalog_validation.get("selects_topology") is not False:
        raise ValueError("Structural Catalog V2 unexpectedly selects topology")
    if catalog_validation.get("selects_stops") is not False:
        raise ValueError("Structural Catalog V2 unexpectedly selects stops")
    if catalog_validation.get("chooses_service_policy") is not False:
        raise ValueError("Structural Catalog V2 unexpectedly chooses service policy")

    if matrix_validation.get("status") != MATRIX_STATUS:
        raise ValueError("Reduced Path Matrix V2 upstream status is not PASS")
    if matrix_validation.get("contract") != MATRIX_CONTRACT:
        raise ValueError("Unexpected Reduced Path Matrix V2 contract")

    catalog_lineage = catalog_validation.get("lineage", {})
    matrix_lineage = matrix_validation.get("lineage", {})
    checks = {
        "scenario catalog": (
            catalog_lineage.get("scenario_catalog_sha256"),
            sha256_path(catalog_path),
        ),
        "catalog matrix": (
            catalog_lineage.get("reduced_path_matrix_sha256"),
            sha256_path(matrix_path),
        ),
        "catalog anchor universe": (
            catalog_lineage.get("routing_anchor_universe_sha256"),
            sha256_path(anchor_path),
        ),
        "matrix file": (
            matrix_lineage.get("reduced_path_matrix_sha256"),
            sha256_path(matrix_path),
        ),
        "matrix anchor universe": (
            matrix_lineage.get("routing_anchor_universe_sha256"),
            sha256_path(anchor_path),
        ),
    }
    for label, (expected, actual) in checks.items():
        if expected != actual:
            raise ValueError(f"V2 lineage hash mismatch for {label}")

    if catalog_validation.get("epoch_id") != matrix_validation.get("epoch_id"):
        raise ValueError("Structural catalog and matrix use different frozen epochs")
    return catalog_validation, matrix_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--catalog-validation", required=True, type=Path)
    parser.add_argument("--path-matrix", required=True, type=Path)
    parser.add_argument("--matrix-validation", required=True, type=Path)
    parser.add_argument("--anchor-universe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--on-path-abs-tol-km", required=True, type=float)
    parser.add_argument("--on-path-rel-tol", required=True, type=float)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    for path in (
        args.catalog,
        args.catalog_validation,
        args.path_matrix,
        args.matrix_validation,
        args.anchor_universe,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    catalog_validation, matrix_validation = validate_v2_lineage(
        catalog_path=args.catalog,
        catalog_validation_path=args.catalog_validation,
        matrix_path=args.path_matrix,
        matrix_validation_path=args.matrix_validation,
        anchor_path=args.anchor_universe,
    )
    rows, family_counts, cached_legs = screen_catalog(
        catalog_path=args.catalog,
        matrix_path=args.path_matrix,
        anchor_path=args.anchor_universe,
        output_path=args.output,
        abs_tol_km=args.on_path_abs_tol_km,
        rel_tol=args.on_path_rel_tol,
    )
    if rows != 100_000:
        raise RuntimeError(f"Structural Screening V2 expected 100000 rows, got {rows}")

    payload = {
        "status": "PASS_STRUCTURAL_SCREENING_V2_BUILD",
        "contract": "PHASE2_TOPOLOGY_NEUTRAL_STRUCTURAL_SCREENING_V2",
        "evidence_label": "V2_STRUCTURAL_SCREENING_NOT_RECOMMENDATION",
        "epoch_id": matrix_validation["epoch_id"],
        "scenario_count": rows,
        "family_counts": family_counts,
        "unique_directed_scenario_legs_screened": cached_legs,
        "on_path_test": "d(A,C)+d(C,B) approximately equals d(A,B)",
        "on_path_abs_tol_km": args.on_path_abs_tol_km,
        "on_path_rel_tol": args.on_path_rel_tol,
        "uses_live_osm": False,
        "uses_random_generation": False,
        "uses_legacy_candidate_routes": False,
        "selects_topology": False,
        "ranks_topology_family": False,
        "selects_stops": False,
        "annualises_service": False,
        "chooses_service_policy": False,
        "lineage": {
            "catalog_validation": str(args.catalog_validation),
            "catalog_validation_sha256": sha256_path(args.catalog_validation),
            "catalog": str(args.catalog),
            "catalog_sha256": sha256_path(args.catalog),
            "matrix_validation": str(args.matrix_validation),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "path_matrix": str(args.path_matrix),
            "path_matrix_sha256": sha256_path(args.path_matrix),
            "anchor_universe": str(args.anchor_universe),
            "anchor_universe_sha256": sha256_path(args.anchor_universe),
            "screening_output": str(args.output),
            "screening_output_sha256": sha256_path(args.output),
            "upstream_catalog_contract": catalog_validation["contract"],
            "upstream_matrix_contract": matrix_validation["contract"],
        },
        "epistemic_note": (
            "These are topology-neutral structural skeleton metrics on the certified V2 catalog. "
            "Intercepted anchors indicate shortest-path structural potential only, not operational "
            "stop calls, service frequency, passenger utility or a network recommendation."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"screened {rows} V2 scenarios across {cached_legs} unique directed legs -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
