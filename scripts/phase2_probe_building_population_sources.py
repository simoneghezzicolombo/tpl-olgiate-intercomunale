#!/usr/bin/env python3
"""Read-only schema probe for Phase 2 building-population official sources.

The probe verifies current official ISTAT census-section and Regione Lombardia
DBGT Edificato schemas on a clean runner. It produces no modelling output.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

ISTAT_GEOM_URL = "https://www.istat.it/storage/cartografia/basi_territoriali/2021/R03_21.zip"
ISTAT_DATA_2023_URL = "https://esploradati.istat.it/databrowser/DWL/PERMPOP/SUBCOM/Dati_regionali_2023.zip"
DBGT_BASE = "https://www.cartografia.servizirl.it/arcgis5/rest/services/BaseMap/DBGT_Tema0201_Edificato/MapServer"
CORE_CODES = {"097010", "097012", "097058", "097074", "097092"}
HEADERS = {
    "User-Agent": (
        "tpl-olgiate-building-population/1.0 "
        "(+https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"
    )
}


def get(url: str, *, params: dict | None = None, timeout: int = 180) -> requests.Response:
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def _normalise_code(series: pd.Series, width: int = 6) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(width)
    )


def _select_lombardia_2023_workbook(names: list[str]) -> str:
    candidates = []
    for name in names:
        low = name.lower()
        if not low.endswith(".xlsx"):
            continue
        if "r03" not in low or "2023" not in low:
            continue
        if "tracciato" in low:
            continue
        if "sez" in low or "indicator" in low:
            candidates.append(name)
    if len(candidates) != 1:
        raise RuntimeError(
            "Could not identify exactly one Lombardia 2023 section workbook; "
            f"candidates={candidates}; xlsx={[n for n in names if n.lower().endswith('.xlsx')]}"
        )
    return candidates[0]


def inspect_istat() -> dict:
    geom = get(ISTAT_GEOM_URL).content
    data = get(ISTAT_DATA_2023_URL).content
    out: dict = {"geometry_bytes": len(geom), "data_2023_bytes": len(data)}

    with zipfile.ZipFile(io.BytesIO(geom)) as z:
        out["geometry_members"] = z.namelist()
        z.extractall("/tmp/istat_geom")
    shp = next(Path("/tmp/istat_geom").rglob("*.shp"))
    gdf = gpd.read_file(shp)
    out["geometry_columns"] = list(gdf.columns)
    out["geometry_crs"] = str(gdf.crs)
    out["geometry_rows"] = int(len(gdf))

    code_col = next((c for c in ("PRO_COM_T", "PRO_COM") if c in gdf.columns), None)
    if code_col is None:
        raise RuntimeError(f"ISTAT geometry lacks municipal code: {list(gdf.columns)}")
    codes = _normalise_code(gdf[code_col])
    out["geometry_rows_province_097"] = int(codes.str.startswith("097").sum())
    out["geometry_rows_core"] = int(codes.isin(CORE_CODES).sum())
    core = gdf.loc[codes.isin(CORE_CODES)].copy().to_crs(7791)
    minx, miny, maxx, maxy = core.total_bounds
    out["core_bbox_epsg7791"] = [float(minx), float(miny), float(maxx), float(maxy)]

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        out["data_2023_members"] = names
        member = _select_lombardia_2023_workbook(names)
        out["data_2023_selected_member"] = member
        raw = z.read(member)
    xls = pd.ExcelFile(io.BytesIO(raw), engine="openpyxl")
    out["data_2023_sheets"] = xls.sheet_names

    sheet_summaries = []
    chosen_df = None
    chosen_sheet = None
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet, dtype=object)
        columns = [str(c) for c in df.columns]
        summary = {"sheet": sheet, "rows": int(len(df)), "columns": columns}
        sheet_summaries.append(summary)
        low_cols = {str(c).lower() for c in df.columns}
        if chosen_df is None and any("sez" in c for c in low_cols):
            chosen_df = df
            chosen_sheet = sheet
    out["data_2023_sheet_summaries"] = sheet_summaries
    if chosen_df is None:
        raise RuntimeError("No sheet with a section-like field found in Lombardia 2023 workbook")
    df = chosen_df
    out["data_2023_selected_sheet"] = chosen_sheet
    out["data_2023_columns"] = [str(c) for c in df.columns]
    out["data_2023_rows"] = int(len(df))
    out["data_2023_head"] = df.head(5).fillna("").astype(str).to_dict("records")

    section_candidates = [c for c in df.columns if "sez" in str(c).lower()]
    municipality_candidates = [
        c for c in df.columns
        if any(k in str(c).lower() for k in ("pro_com", "comune", "cod_com", "com_"))
    ]
    population_candidates = [
        c for c in df.columns
        if str(c).upper() in {"P1", "POP", "POP2023", "POP23", "POP_TOT"}
        or "popol" in str(c).lower()
    ]
    out["section_key_candidates"] = [str(c) for c in section_candidates]
    out["municipality_key_candidates"] = [str(c) for c in municipality_candidates]
    out["population_field_candidates"] = [str(c) for c in population_candidates]

    candidate_stats = {}
    for c in population_candidates:
        num = pd.to_numeric(df[c], errors="coerce")
        candidate_stats[str(c)] = {
            "numeric_non_null": int(num.notna().sum()),
            "numeric_sum": float(num.fillna(0).sum()),
        }
    out["population_candidate_stats"] = candidate_stats

    fake_stats = {}
    for c in section_candidates:
        s = df[c].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        fake = s.str.contains(r"(?:888888|999999)\d?$", regex=True, na=False)
        fake_stats[str(c)] = {
            "unique": int(s.nunique(dropna=True)),
            "fake_rows": int(fake.sum()),
            "sample": s.head(10).tolist(),
        }
    out["section_candidate_stats"] = fake_stats
    return out


def arc_query(layer: int, params: dict) -> dict:
    payload = get(f"{DBGT_BASE}/{layer}/query", params={"f": "json", **params}).json()
    if "error" in payload:
        raise RuntimeError(json.dumps(payload["error"], ensure_ascii=False))
    return payload


def inspect_dbgt(core_bbox: list[float]) -> dict:
    out: dict = {}
    service = get(DBGT_BASE, params={"f": "pjson"}).json()
    out["service_spatial_reference"] = service.get("spatialReference")
    for layer in (0, 3, 5, 22, 24):
        meta = get(f"{DBGT_BASE}/{layer}", params={"f": "pjson"}).json()
        out[f"layer_{layer}_name"] = meta.get("name")
        out[f"layer_{layer}_fields"] = [
            {"name": f.get("name"), "alias": f.get("alias"), "domain": f.get("domain")}
            for f in meta.get("fields", [])
        ]
        out[f"layer_{layer}_relationships"] = meta.get("relationships")

    minx, miny, maxx, maxy = core_bbox
    envelope = f"{minx-5000},{miny-5000},{maxx+5000},{maxy+5000}"
    id_payload = arc_query(3, {
        "where": "1=1",
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "7791",
        "spatialRel": "esriSpatialRelIntersects",
        "returnIdsOnly": "true",
    })
    object_ids = id_payload.get("objectIds") or []
    out["footprint_layer3_ids_5km_envelope"] = len(object_ids)
    sample_ids = object_ids[:20]
    if not sample_ids:
        return out

    sample = arc_query(3, {
        "objectIds": ",".join(map(str, sample_ids)),
        "outFields": "OBJECTID,CLASSREF,COD_CONS,DATA_FIN",
        "returnGeometry": "false",
    })
    attrs = [f["attributes"] for f in sample.get("features", [])]
    out["footprint_sample"] = attrs
    refs = [str(a["CLASSREF"]) for a in attrs if a.get("CLASSREF")]
    if not refs:
        return out
    safe = ",".join("'" + r.replace("'", "''") + "'" for r in refs)

    buildings = arc_query(22, {
        "where": f"CLASSID IN ({safe})",
        "outFields": "*",
        "returnGeometry": "false",
    })
    uses = arc_query(24, {
        "where": f"CLASSREF IN ({safe})",
        "outFields": "*",
        "returnGeometry": "false",
    })
    volumes = arc_query(0, {
        "where": f"CEDIUV IN ({safe})",
        "outFields": "CLASSID,CEDIUV,UN_VOL_AV,UN_VOL_EX,UN_VOL_QE,Shape_Area,DATA_FIN",
        "returnGeometry": "false",
    })
    out["building_table_sample"] = [f["attributes"] for f in buildings.get("features", [])]
    out["use_table_sample"] = [f["attributes"] for f in uses.get("features", [])]
    out["volume_unit_sample"] = [f["attributes"] for f in volumes.get("features", [])]
    return out


def main() -> None:
    istat = inspect_istat()
    bbox = istat.get("core_bbox_epsg7791")
    if not bbox:
        raise SystemExit("Could not derive core bbox from official ISTAT 2021 geometry")
    dbgt = inspect_dbgt(bbox)
    print(json.dumps({"istat": istat, "dbgt": dbgt}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
