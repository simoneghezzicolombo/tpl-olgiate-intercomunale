#!/usr/bin/env python3
"""Authoritative building-population runner with composite DBGT identity and piece points.

V5 fixes Regione Lombardia DBGT relational identity by scoping local ids to
COD_CONS.  V6 additionally keeps the building-section intersection as the
spatial unit for walking catchments and boundary-sensitive diagnostics.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import phase2_run_building_population_v5 as v5
from src import phase2_building_piece_access as piece

impl = v5.impl


def build_section_pieces(buildings, section_geometry):
    return piece.build_section_pieces(buildings, section_geometry)


def compute_accessibility(building_allocations, building_points, gate_b_dir):
    return piece.compute_accessibility(
        building_allocations,
        building_points,
        gate_b_dir,
        core_codes=impl.CORE_CODES,
        connector_max_m=impl.POP_CONNECTOR_MAX_M,
        connector_m_per_min=impl.CONNECTOR_M_PER_MIN,
    )


def boundary_comparison(building_allocations, building_points, gate_b_dir, core_boundaries_path):
    return piece.boundary_comparison(
        building_allocations,
        building_points,
        gate_b_dir,
        core_boundaries_path,
        core_codes=impl.CORE_CODES,
        boundary_band_m=impl.BOUNDARY_COMPARISON_BAND_M,
        normalise_municipality=impl.normalise_municipality,
    )


def spatial_distribution_comparison(building_allocations, building_points, gate_b_dir):
    return piece.spatial_distribution_comparison(
        building_allocations,
        building_points,
        gate_b_dir,
        core_codes=impl.CORE_CODES,
        normalise_municipality=impl.normalise_municipality,
    )


def _postprocess_piece_outputs(output_dir: Path) -> None:
    validation_path = output_dir / "building_population_validation.json"
    manifest_path = output_dir / "building_population_source_manifest.json"
    if not validation_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("building-population validation/manifest missing before piece-point postprocess")

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation.update({
        "building_section_piece_point_status": piece.PIECE_POINT_STATUS,
        "accessibility_spatial_unit": "BUILDING_SECTION_INTERSECTION",
        "accessibility_point_status": piece.PIECE_POINT_STATUS,
        "boundary_comparison_spatial_unit": "BUILDING_SECTION_INTERSECTION",
        "spatial_distribution_v2_spatial_unit": "BUILDING_SECTION_INTERSECTION",
    })
    validation["limitations"].append(
        "Walking accessibility and boundary-sensitive V2 diagnostics use a DERIVED representative point of each DBGT-building × ISTAT-section intersection, not one whole-building point; whole-building representative points remain only for building-level diagnostic exports such as WorldPop-cell heterogeneity."
    )
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["building_section_piece_spatial_semantics"] = {
        "allocation_unit": "DBGT_BUILDING_X_ISTAT_SECTION_INTERSECTION",
        "piece_point_status": piece.PIECE_POINT_STATUS,
        "walking_accessibility_uses_piece_point": True,
        "boundary_diagnostics_use_piece_point": True,
        "whole_building_point_used_for_worldpop_cell_diagnostic_only": True,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    impl.write_checksums(output_dir)


impl.build_section_pieces = build_section_pieces
impl.compute_accessibility = compute_accessibility
impl.boundary_comparison = boundary_comparison
impl.spatial_distribution_comparison = spatial_distribution_comparison


if __name__ == "__main__":
    result = impl.main()
    output_dir = Path("outputs/phase2")
    if "--output-dir" in sys.argv:
        output_dir = Path(sys.argv[sys.argv.index("--output-dir") + 1])
    v5._postprocess_outputs(output_dir)
    _postprocess_piece_outputs(output_dir)
    sys.exit(result)
