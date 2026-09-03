#!/usr/bin/env python3
"""Gate D candidate grade diagnostics using the Gate B Copernicus DSM.

This is a terrain diagnostic, not an engineering road-grade survey. The validated
Gate B Copernicus GLO-30 source tile is median-filtered and bilinearly sampled along
routed candidate geometries. The full source tile is used rather than the five-core-
municipality clipped raster, because Gate D candidates extend to Ravellino and
Caprino/Celana and the clipped raster's outside-mask fill values are not terrain.
Results are labelled ESTIMATE_FROM_COPERNICUS_DSM and no bus-feasibility threshold
is imposed.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy.ndimage import median_filter

DEFAULT_ROUTES = Path("data/audit_gate_d/structural_candidate_geometry.geojson")
DEFAULT_DEM = Path("data/raw/dem/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif")
DEFAULT_OUT = Path("data/audit_gate_d/structural_candidate_slope_audit.csv")
UTM_EPSG = 32632
SAMPLE_SPACING_M = 60.0


def prepare_dem(path: Path):
    src = rasterio.open(path)
    if src.crs is None:
        src.close()
        raise ValueError("Copernicus DSM has no CRS")
    masked = src.read(1, masked=True)
    data = np.asarray(masked.filled(np.nan), dtype=float)
    finite = np.isfinite(data)
    if not finite.any():
        src.close()
        raise ValueError("Copernicus DSM has no finite cells")
    fill = float(np.nanmedian(data))
    filtered = median_filter(np.where(finite, data, fill), size=3, mode="nearest")
    valid = finite.astype(np.uint8)
    return src, filtered, valid


def bilinear_sample(src, arr: np.ndarray, valid: np.ndarray, x: float, y: float) -> float:
    col_corner, row_corner = (~src.transform) * (x, y)
    px = float(col_corner) - 0.5
    py = float(row_corner) - 0.5
    c0 = math.floor(px)
    r0 = math.floor(py)
    c1 = c0 + 1
    r1 = r0 + 1
    if r0 < 0 or c0 < 0 or r1 >= arr.shape[0] or c1 >= arr.shape[1]:
        return float("nan")
    if not valid[r0 : r1 + 1, c0 : c1 + 1].all():
        return float("nan")
    dx = px - c0
    dy = py - r0
    return float(
        arr[r0, c0] * (1.0 - dx) * (1.0 - dy)
        + arr[r0, c1] * dx * (1.0 - dy)
        + arr[r1, c0] * (1.0 - dx) * dy
        + arr[r1, c1] * dx * dy
    )


def sample_route_grade(geometry, src, arr: np.ndarray, valid: np.ndarray, spacing_m: float) -> dict:
    line = gpd.GeoSeries([geometry], crs=4326).to_crs(UTM_EPSG).iloc[0]
    length_m = float(line.length)
    if length_m <= 0:
        raise ValueError("Candidate route has zero length")
    distances = np.arange(0.0, length_m, spacing_m, dtype=float)
    if len(distances) == 0 or distances[-1] < length_m:
        distances = np.append(distances, length_m)
    points = [line.interpolate(float(distance)) for distance in distances]
    transformer = Transformer.from_crs(UTM_EPSG, src.crs, always_xy=True)
    dem_xy = [transformer.transform(point.x, point.y) for point in points]
    elevations = np.asarray(
        [bilinear_sample(src, arr, valid, x, y) for x, y in dem_xy],
        dtype=float,
    )
    segment_lengths = np.diff(distances)
    valid_segments = np.isfinite(elevations[:-1]) & np.isfinite(elevations[1:]) & (segment_lengths > 0)
    covered_m = float(segment_lengths[valid_segments].sum())
    grades = np.full(len(segment_lengths), np.nan, dtype=float)
    grades[valid_segments] = 100.0 * np.diff(elevations)[valid_segments] / segment_lengths[valid_segments]
    finite_grades = np.abs(grades[np.isfinite(grades)])
    coverage_pct = 100.0 * covered_m / length_m
    return {
        "route_length_km": length_m / 1000.0,
        "dem_profile_coverage_pct": coverage_pct,
        "sample_spacing_m": spacing_m,
        "valid_grade_segments": int(len(finite_grades)),
        "median_abs_grade_pct_60m": float(np.median(finite_grades)) if len(finite_grades) else np.nan,
        "p95_abs_grade_pct_60m": float(np.percentile(finite_grades, 95)) if len(finite_grades) else np.nan,
        "max_abs_grade_pct_60m": float(np.max(finite_grades)) if len(finite_grades) else np.nan,
        "epistemic_status": "ESTIMATE_FROM_COPERNICUS_DSM",
        "method_status": "MEDIAN3X3_BILINEAR_60M_PROFILE_FULL_GLO30_TILE",
        "feasibility_threshold_applied": False,
    }


def audit(routes_path: Path, dem_path: Path, spacing_m: float = SAMPLE_SPACING_M) -> pd.DataFrame:
    routes = gpd.read_file(routes_path).to_crs(4326)
    if "candidate_id" not in routes.columns:
        raise ValueError("Candidate geometry is missing candidate_id")
    src, arr, valid = prepare_dem(dem_path)
    try:
        rows = []
        for _, route in routes.iterrows():
            metrics = sample_route_grade(route.geometry, src, arr, valid, spacing_m)
            rows.append({"candidate_id": route["candidate_id"], **metrics})
    finally:
        src.close()
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", default=str(DEFAULT_ROUTES))
    parser.add_argument("--dem", default=str(DEFAULT_DEM))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--spacing-m", type=float, default=SAMPLE_SPACING_M)
    args = parser.parse_args()
    result = audit(Path(args.routes), Path(args.dem), args.spacing_m)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    print(result.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
