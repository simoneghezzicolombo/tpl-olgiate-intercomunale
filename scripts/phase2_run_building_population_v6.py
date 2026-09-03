#!/usr/bin/env python3
"""Authoritative building-population runner with composite DBGT identity and piece points.

V5 fixes Regione Lombardia DBGT relational identity by scoping local ids to
COD_CONS. V6 additionally keeps the building-section intersection as the
spatial unit for walking catchments, boundary-sensitive diagnostics and the
core spatial export, while retaining unlinked active footprint rows as
provenance-only evidence.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import geopandas as gpd
import pandas as pd

import phase2_run_building_population_v5 as v5
from src import phase2_building_piece_access as piece
from src.phase2_dbgt_unlinked_footprints import (
    UNLINKED_STATUS,
    normalize_footprints as normalize_footprints_allow_unlinked,
)

impl = v5.impl
CORE_EXPORT_STATUS = "MODEL_OUTPUT_CORE_BUILDING_SECTION_PIECE_POINT"
CORE_EXPORT_FILE = "building_population_core_pieces.geojson"
LEGACY_CORE_BUILDING_FILE = "building_population_buildings_core.geojson"
FROZEN_GEOMETRY_FILE = "building_population_source_istat_R03_21.zip"
FROZEN_POSAS_FILE = "building_population_source_posas_2025.zip"

# v5.fetch_dbgt_footprints resolves this global at call time. Replace only the
# normalization stage: source acquisition and raw snapshot remain unchanged.
v5.normalize_footprints = normalize_footprints_allow_unlinked


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


def _write_core_piece_export(output_dir: Path) -> tuple[int, float]:
    """Write the core spatial layer at the same unit used by accounting/accessibility.

    A whole DBGT footprint may cross a municipal or core boundary. Selecting a
    whole building by one representative point is therefore not a valid core
    membership rule. The authoritative core GeoJSON is one representative point
    per allocated building-section intersection, carrying only the population of
    that piece. Whole-building geometry remains available in source provenance
    and the building CSV, but is not labelled as a core spatial allocation.
    """
    allocations_path = output_dir / "building_population_allocations.csv"
    if not allocations_path.is_file():
        raise RuntimeError("building allocation CSV missing before core piece export")
    allocations = pd.read_csv(
        allocations_path,
        dtype={
            "building_id": "string",
            "section_id": "string",
            "municipality_code": "string",
        },
    )
    required = {
        "building_id",
        "section_id",
        "municipality_code",
        "building_piece_population_model",
        "piece_x_utm32",
        "piece_y_utm32",
        "piece_point_epistemic_status",
    }
    if not required.issubset(allocations.columns):
        raise RuntimeError(f"core piece export columns missing: {required - set(allocations.columns)}")
    core = allocations.loc[allocations["municipality_code"].isin(impl.CORE_CODES)].copy()
    if core.empty:
        raise RuntimeError("core building-section allocation is empty")
    if core[["piece_x_utm32", "piece_y_utm32", "building_piece_population_model"]].isna().any().any():
        raise RuntimeError("core building-section export contains null coordinate/population")
    if core.duplicated(["building_id", "section_id"]).any():
        raise RuntimeError("duplicate building-section allocation in core spatial export")

    geometry = gpd.points_from_xy(core["piece_x_utm32"], core["piece_y_utm32"])
    gdf = gpd.GeoDataFrame(core, geometry=geometry, crs=32632).to_crs(4326)
    gdf["core_spatial_export_epistemic_status"] = CORE_EXPORT_STATUS
    output_path = output_dir / CORE_EXPORT_FILE
    gdf.to_file(output_path, driver="GeoJSON")

    legacy_path = output_dir / LEGACY_CORE_BUILDING_FILE
    if legacy_path.exists():
        legacy_path.unlink()

    population = float(pd.to_numeric(core["building_piece_population_model"], errors="raise").sum())
    return len(core), population


def _freeze_official_inputs(output_dir: Path, source_cache: Path, manifest: dict) -> dict:
    """Copy the modest official archives needed for a source-frozen replay.

    The 2023 census package is large, but the exact original regional workbook
    extracted from it is already staged by CI. Geometry 2021 and POSAS 2025 are
    small enough to carry as their original downloaded archives. Their bytes are
    verified against the hashes recorded during the live official-source build
    before being admitted to the evidence bundle.
    """
    specs = [
        (
            source_cache / "istat_R03_21.zip",
            output_dir / FROZEN_GEOMETRY_FILE,
            manifest["sources"]["istat_2021_geometry"]["sha256"],
            "ISTAT 2021 Lombardia territorial-bases archive",
        ),
        (
            source_cache / "POSAS_2025_it_Comuni.zip",
            output_dir / FROZEN_POSAS_FILE,
            manifest["sources"]["istat_posas_2025"]["sha256"],
            "ISTAT POSAS 2025 municipal archive",
        ),
    ]
    frozen = {}
    for source, destination, expected_sha, label in specs:
        if not source.is_file():
            raise RuntimeError(f"official source archive missing before evidence freeze: {source}")
        actual_sha = impl.sha256_file(source)
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"official source archive checksum changed before evidence freeze: "
                f"{label}: {actual_sha} != {expected_sha}"
            )
        shutil.copyfile(source, destination)
        copied_sha = impl.sha256_file(destination)
        if copied_sha != expected_sha:
            raise RuntimeError(f"copied official source archive checksum mismatch: {destination}")
        frozen[destination.name] = {
            "label": label,
            "sha256": copied_sha,
            "bytes": destination.stat().st_size,
            "epistemic_status": "FACT_OFFICIAL_SOURCE_ARCHIVE_FROZEN_FOR_REPLAY",
        }
    return frozen


def _postprocess_piece_outputs(output_dir: Path, source_cache: Path) -> None:
    validation_path = output_dir / "building_population_validation.json"
    manifest_path = output_dir / "building_population_source_manifest.json"
    if not validation_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("building-population validation/manifest missing before piece-point postprocess")

    core_feature_count, core_population = _write_core_piece_export(output_dir)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frozen_inputs = _freeze_official_inputs(output_dir, source_cache, manifest)
    fp = manifest["sources"]["lombardia_dbgt_footprints"]
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if abs(core_population - float(validation["core_building_population_located"])) > 1e-7:
        raise RuntimeError(
            "core piece spatial export population does not match authoritative located core population: "
            f"{core_population} != {validation['core_building_population_located']}"
        )
    validation.update({
        "building_section_piece_point_status": piece.PIECE_POINT_STATUS,
        "accessibility_spatial_unit": "BUILDING_SECTION_INTERSECTION",
        "accessibility_point_status": piece.PIECE_POINT_STATUS,
        "boundary_comparison_spatial_unit": "BUILDING_SECTION_INTERSECTION",
        "spatial_distribution_v2_spatial_unit": "BUILDING_SECTION_INTERSECTION",
        "core_spatial_export_status": CORE_EXPORT_STATUS,
        "core_spatial_export_file": CORE_EXPORT_FILE,
        "core_spatial_export_feature_count": int(core_feature_count),
        "core_spatial_export_population_model": core_population,
        "legacy_whole_building_core_geojson_emitted": False,
        "official_geometry_2021_archive_frozen": True,
        "official_posas_2025_archive_frozen": True,
        "dbgt_unlinked_active_footprints_excluded": int(fp["raw_active_footprints_without_classref_excluded"]),
        "dbgt_unlinked_active_footprint_area_m2_excluded": float(fp["raw_active_footprints_without_classref_excluded_area_m2"]),
        "dbgt_unlinked_footprint_status": UNLINKED_STATUS,
        "dbgt_unlinked_footprints_population_assigned": False,
    })
    validation["limitations"].append(
        "Walking accessibility, boundary-sensitive V2 diagnostics and the core spatial export use a DERIVED representative point of each DBGT-building × ISTAT-section intersection, not one whole-building point; whole-building representative points remain only for building-level diagnostic comparisons such as WorldPop-cell heterogeneity."
    )
    validation["limitations"].append(
        "A whole-building 'core' GeoJSON is intentionally not emitted because buildings can cross census, municipal and core boundaries. The authoritative core spatial layer is building_population_core_pieces.geojson and carries population only for each core building-section piece."
    )
    validation["limitations"].append(
        "Active DBGT footprint source rows with official COD_CONS but blank CLASSREF are preserved in raw provenance and excluded from building allocation because no auditable EDIFC/use/volume relation can be established; no synthetic identifier or proximity join is used."
    )
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest["building_section_piece_spatial_semantics"] = {
        "allocation_unit": "DBGT_BUILDING_X_ISTAT_SECTION_INTERSECTION",
        "piece_point_status": piece.PIECE_POINT_STATUS,
        "walking_accessibility_uses_piece_point": True,
        "boundary_diagnostics_use_piece_point": True,
        "whole_building_point_used_for_worldpop_cell_diagnostic_only": True,
    }
    manifest["core_spatial_export"] = {
        "file": CORE_EXPORT_FILE,
        "status": CORE_EXPORT_STATUS,
        "feature_unit": "DBGT_BUILDING_X_ISTAT_SECTION_INTERSECTION",
        "geometry": "DERIVED_REPRESENTATIVE_POINT_OF_INTERSECTION",
        "population_field": "building_piece_population_model",
        "feature_count": int(core_feature_count),
        "population_model_sum": core_population,
        "whole_building_core_membership_rule_used": False,
        "legacy_whole_building_core_geojson_emitted": False,
    }
    manifest["frozen_official_input_archives"] = frozen_inputs
    manifest["dbgt_unlinked_footprint_semantics"] = {
        "status": UNLINKED_STATUS,
        "population_assigned": False,
        "synthetic_id_created": False,
        "proximity_join_used": False,
        "count": int(fp["raw_active_footprints_without_classref_excluded"]),
        "area_m2": float(fp["raw_active_footprints_without_classref_excluded_area_m2"]),
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
    source_cache = Path("/tmp/building_population_sources")
    if "--source-cache" in sys.argv:
        source_cache = Path(sys.argv[sys.argv.index("--source-cache") + 1])
    v5._postprocess_outputs(output_dir)
    _postprocess_piece_outputs(output_dir, source_cache)
    sys.exit(result)
