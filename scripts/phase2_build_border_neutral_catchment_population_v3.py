#!/usr/bin/env python3
"""Build a border-neutral population universe for Phase 2 V3 catchment evaluation.

This materializer preserves the validated Gate B core population cells exactly and
adds only real WorldPop/POSAS-calibrated cells outside the five core municipalities.
Neighbouring municipalities are discovered from geometry; no neighbour list is
hard-coded. The default 960 m envelope corresponds to 12 minutes at 4.8 km/h.

Important scope note: a buffer around the five-municipality service area is exact
for catchments of stops located inside the core. If a future candidate includes a
passenger stop outside the core, rebuild the envelope from the explicit stop/service
geometry using the same contract rather than silently extrapolating this artifact.
"""

from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
import requests
from shapely.geometry import mapping

from src.phase2_border_neutral_catchment_population_v3 import (
    DEFAULT_CORE_CODES,
    max_walk_distance_metres,
    municipality_calibration_factor,
    split_discovered_municipalities,
)


BOUNDARY_ZIP = Path("data/raw/boundaries/Limiti01012026.zip")
CORE_BOUNDARIES = Path("data/raw/boundaries/comuni_core_istat_2026.geojson")
WORLDPOP_NATIONAL = Path("data/raw/worldpop/ita_ppp_2020_UNadj.tif")
CORE_CELLS = Path("data/audit_gate_b/population_cells_real.csv")
POSAS_ARCHIVE = Path("data/raw/istat/POSAS_2025_it_Comuni.zip")
POSAS_URL = "https://demo.istat.it/data/posas/POSAS_2025_it_Comuni.zip"

OUT_DIR = Path("outputs/phase2/border_neutral_catchment_population_v3")
OUT_CSV = OUT_DIR / "border_neutral_population_units_v3.csv"
OUT_SUMMARY = OUT_DIR / "border_neutral_population_units_v3_summary.json"

UTM_EPSG = 32632
CORE_CODES = frozenset(DEFAULT_CORE_CODES)


def _require_local_inputs() -> None:
    missing = [
        str(path)
        for path in (BOUNDARY_ZIP, CORE_BOUNDARIES, WORLDPOP_NATIONAL, CORE_CELLS)
        if not path.exists() or path.stat().st_size == 0
    ]
    if missing:
        raise FileNotFoundError(
            "RT-016 requires the validated Gate A/B real-data inputs first; missing: "
            + ", ".join(missing)
        )


def _load_all_municipalities() -> gpd.GeoDataFrame:
    with zipfile.ZipFile(BOUNDARY_ZIP) as archive, tempfile.TemporaryDirectory() as tmp:
        members = [name for name in archive.namelist() if name.startswith("Com01012026/")]
        if not members:
            raise ValueError("ISTAT boundary archive does not contain Com01012026")
        archive.extractall(tmp, members)
        shp = Path(tmp) / "Com01012026" / "Com01012026_WGS84.shp"
        if not shp.exists():
            raise FileNotFoundError("ISTAT municipal shapefile missing inside archive")
        municipalities = gpd.read_file(shp).to_crs(4326)
    municipalities["PRO_COM_T"] = municipalities["PRO_COM_T"].astype(str).str.zfill(6)
    if municipalities["PRO_COM_T"].duplicated().any():
        raise ValueError("ISTAT municipality codes must be unique")
    return municipalities


def _derive_envelope_and_municipalities(
    all_municipalities: gpd.GeoDataFrame,
) -> tuple[object, gpd.GeoDataFrame, dict[str, tuple[str, ...]]]:
    core = gpd.read_file(CORE_BOUNDARIES).to_crs(UTM_EPSG)
    core["PRO_COM_T"] = core["PRO_COM_T"].astype(str).str.zfill(6)
    if set(core["PRO_COM_T"]) != set(CORE_CODES):
        raise ValueError("core boundary artifact does not contain the frozen five municipalities")

    buffer_m = max_walk_distance_metres()
    service_area = core.geometry.union_all()
    envelope_utm = service_area.buffer(buffer_m)

    all_utm = all_municipalities.to_crs(UTM_EPSG)
    discovered = all_utm[all_utm.geometry.intersects(envelope_utm)].copy()
    split = split_discovered_municipalities(
        discovered["PRO_COM_T"].tolist(), core_codes=CORE_CODES
    )
    envelope_wgs84 = gpd.GeoSeries([envelope_utm], crs=UTM_EPSG).to_crs(4326).iloc[0]
    return envelope_wgs84, discovered.to_crs(4326), split


def _download_posas_if_needed() -> None:
    if POSAS_ARCHIVE.exists() and POSAS_ARCHIVE.stat().st_size > 0:
        return
    POSAS_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        POSAS_URL,
        headers={"User-Agent": "tpl-olgiate-research/RT-016"},
        timeout=120,
    )
    response.raise_for_status()
    POSAS_ARCHIVE.write_bytes(response.content)
    if POSAS_ARCHIVE.stat().st_size == 0:
        raise IOError("POSAS archive download produced an empty file")


def _load_posas_totals() -> dict[str, float]:
    _download_posas_if_needed()
    with zipfile.ZipFile(POSAS_ARCHIVE) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if name.lower().endswith("posas_2025_it_comuni.csv")
        ]
        if not candidates:
            candidates = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(candidates) != 1:
            raise ValueError(f"expected one POSAS municipalities CSV, found {candidates}")
        raw_text = archive.read(candidates[0]).decode("utf-8-sig")

    df = pd.read_csv(
        io.StringIO(raw_text),
        sep=";",
        skiprows=1,
        dtype={"Codice comune": str},
        low_memory=False,
    )
    required = {"Codice comune", "Totale"}
    if not required.issubset(df.columns):
        raise ValueError(f"POSAS schema changed; missing={required - set(df.columns)}")
    df["Codice comune"] = (
        df["Codice comune"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    )
    df["Totale"] = pd.to_numeric(df["Totale"], errors="coerce")
    totals = df.groupby("Codice comune")["Totale"].sum(min_count=1)
    if totals.isna().any():
        raise ValueError("POSAS contains non-numeric municipality totals")
    return {str(code): float(value) for code, value in totals.items()}


def _positive_raw_sum_for_geometry(src: rasterio.io.DatasetReader, geometry) -> float:
    image, _ = rasterio.mask.mask(src, [mapping(geometry)], crop=True, filled=False)
    arr = image[0]
    data = np.asarray(arr.filled(np.nan), dtype=float)
    valid = (~np.ma.getmaskarray(arr)) & np.isfinite(data) & (data > 0)
    total = float(data[valid].sum())
    if not np.isfinite(total) or total <= 0:
        raise ValueError("municipality has no positive WorldPop mass for calibration")
    return total


def _extract_external_envelope_cells(
    envelope_wgs84,
    discovered: gpd.GeoDataFrame,
    external_codes: tuple[str, ...],
    posas_totals: dict[str, float],
) -> pd.DataFrame:
    if not external_codes:
        return pd.DataFrame(
            columns=[
                "unit_id",
                "lat",
                "lon",
                "municipality_code",
                "municipality_name",
                "worldpop_2020_raw",
                "calibration_factor_2025",
                "population_weight_2025",
                "population_scope",
            ]
        )

    external = discovered[discovered["PRO_COM_T"].isin(external_codes)].copy()
    names = dict(zip(external["PRO_COM_T"], external["COMUNE"]))

    with rasterio.open(WORLDPOP_NATIONAL) as src:
        if src.crs is None or src.crs.to_epsg() != 4326:
            raise ValueError(f"unexpected WorldPop CRS: {src.crs}")

        factors: dict[str, float] = {}
        for row in external.itertuples():
            code = str(row.PRO_COM_T)
            if code not in posas_totals:
                raise ValueError(f"missing POSAS total for discovered municipality {code}")
            full_raw_sum = _positive_raw_sum_for_geometry(src, row.geometry)
            factors[code] = municipality_calibration_factor(
                official_population_total=posas_totals[code],
                full_municipality_worldpop_raw_sum=full_raw_sum,
            )

        image, transform = rasterio.mask.mask(
            src,
            [mapping(envelope_wgs84)],
            crop=True,
            filled=False,
        )
        arr = image[0]
        data = np.asarray(arr.filled(np.nan), dtype=float)
        valid = (~np.ma.getmaskarray(arr)) & np.isfinite(data) & (data > 0)
        rows, cols = np.where(valid)
        values = data[rows, cols]
        xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")

    cells = gpd.GeoDataFrame(
        {
            "lon": np.asarray(xs, dtype=float),
            "lat": np.asarray(ys, dtype=float),
            "worldpop_2020_raw": np.asarray(values, dtype=float),
        },
        geometry=gpd.points_from_xy(xs, ys),
        crs=4326,
    )
    joined = gpd.sjoin(
        cells,
        external[["PRO_COM_T", "COMUNE", "geometry"]],
        how="inner",
        predicate="within",
    ).drop(columns=["index_right"])

    joined["calibration_factor_2025"] = joined["PRO_COM_T"].map(factors)
    joined["population_weight_2025"] = (
        joined["worldpop_2020_raw"] * joined["calibration_factor_2025"]
    )
    joined["population_scope"] = "external"
    joined["municipality_code"] = joined["PRO_COM_T"].astype(str)
    joined["municipality_name"] = joined["municipality_code"].map(names)
    joined["unit_id"] = [
        f"WP_EXT_{code}_{lat:.6f}_{lon:.6f}"
        for code, lat, lon in zip(joined["municipality_code"], joined["lat"], joined["lon"])
    ]
    if joined["unit_id"].duplicated().any():
        raise ValueError("external WorldPop unit IDs are not unique")

    return joined[
        [
            "unit_id",
            "lat",
            "lon",
            "municipality_code",
            "municipality_name",
            "worldpop_2020_raw",
            "calibration_factor_2025",
            "population_weight_2025",
            "population_scope",
        ]
    ].sort_values("unit_id")


def _load_validated_core_cells() -> pd.DataFrame:
    core = pd.read_csv(CORE_CELLS, dtype={"PRO_COM_T": str})
    required = {
        "cell_id",
        "lat",
        "lon",
        "PRO_COM_T",
        "COMUNE",
        "worldpop_2020_raw",
        "calibration_factor_2025",
        "pop_calibrated_2025",
    }
    if not required.issubset(core.columns):
        raise ValueError(f"Gate B core-cell schema changed; missing={required - set(core.columns)}")
    core["PRO_COM_T"] = core["PRO_COM_T"].astype(str).str.zfill(6)
    if set(core["PRO_COM_T"]) != set(CORE_CODES):
        raise ValueError("Gate B core population no longer matches the frozen five municipalities")
    out = pd.DataFrame(
        {
            "unit_id": core["cell_id"].astype(str),
            "lat": core["lat"].astype(float),
            "lon": core["lon"].astype(float),
            "municipality_code": core["PRO_COM_T"].astype(str),
            "municipality_name": core["COMUNE"].astype(str),
            "worldpop_2020_raw": core["worldpop_2020_raw"].astype(float),
            "calibration_factor_2025": core["calibration_factor_2025"].astype(float),
            "population_weight_2025": core["pop_calibrated_2025"].astype(float),
            "population_scope": "core",
        }
    )
    if out["unit_id"].duplicated().any():
        raise ValueError("Gate B core unit IDs are not unique")
    return out.sort_values("unit_id")


def main() -> None:
    _require_local_inputs()
    all_municipalities = _load_all_municipalities()
    envelope_wgs84, discovered, split = _derive_envelope_and_municipalities(all_municipalities)
    posas_totals = _load_posas_totals()

    core = _load_validated_core_cells()
    external = _extract_external_envelope_cells(
        envelope_wgs84,
        discovered,
        split["external"],
        posas_totals,
    )
    combined = pd.concat([core, external], ignore_index=True)
    if combined["unit_id"].duplicated().any():
        raise ValueError("combined population universe contains duplicate unit IDs")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    combined.sort_values(["population_scope", "municipality_code", "unit_id"]).to_csv(
        OUT_CSV, index=False
    )

    summary = {
        "schema_version": "RT016_V3",
        "max_walk_minutes": 12.0,
        "walk_speed_kmh": 4.8,
        "catchment_buffer_metres": max_walk_distance_metres(),
        "core_codes": list(split["core"]),
        "external_codes_discovered": list(split["external"]),
        "all_codes_discovered": list(split["all"]),
        "core_population_units": int(len(core)),
        "external_population_units_in_envelope": int(len(external)),
        "core_population_2025": float(core["population_weight_2025"].sum()),
        "external_population_2025_in_envelope": float(
            external["population_weight_2025"].sum() if len(external) else 0.0
        ),
        "total_population_units": int(len(combined)),
        "method": (
            "Gate B core cells preserved; external municipalities discovered by a 960 m "
            "metric buffer; external WorldPop cells calibrated with full-municipality "
            "WorldPop sums and official ISTAT POSAS 2025 totals"
        ),
        "scope_note": (
            "Exact for catchments of stops located inside the five-municipality core; "
            "future passenger stops outside the core require rematerialization from their "
            "explicit service/stop geometry."
        ),
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
