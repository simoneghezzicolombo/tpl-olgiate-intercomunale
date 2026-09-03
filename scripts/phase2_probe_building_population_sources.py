#!/usr/bin/env python3
"""Read-only schema probe for Phase 2 building-population official sources.

This script does not produce modelling outputs. It verifies that the official ISTAT
2021 census-section packages and Regione Lombardia DBGT Edificato service can be
read on a clean runner before the production pipeline is specified.
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
ISTAT_DATA_URL = "https://esploradati.istat.it/databrowser/DWL/PERMPOP/SUBCOM/Dati_regionali_2021.zip"
DBGT_BASE = "https://www.cartografia.servizirl.it/arcgis5/rest/services/BaseMap/DBGT_Tema0201_Edificato/MapServer"
CORE_CODES = {"097010", "097012", "097058", "097074", "097092"}
HEADERS = {"User-Agent": "tpl-olgiate-building-population/1.0 (+https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"}


def get(url: str, *, params: dict | None = None, timeout: int = 180) -> requests.Response:
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def inspect_istat() -> dict:
    geom = get(ISTAT_GEOM_URL).content
    data = get(ISTAT_DATA_URL).content
    out: dict = {
        "geometry_bytes": len(geom),
        "data_bytes": len(data),
    }

    with zipfile.ZipFile(io.BytesIO(geom)) as z:
        out["geometry_members"] = z.namelist()
        z.extractall("/tmp/istat_geom")
    shp = next(Path("/tmp/istat_geom").rglob("*.shp"))
    gdf = gpd.read_file(shp)
    out["geometry_columns"] = list(gdf.columns)
    out["geometry_crs"] = str(gdf.crs)
    out["geometry_rows"] = int(len(gdf))
    for candidate in ("PRO_COM_T", "PRO_COM", "COMUNE", "COD_REG", "SEZ2021", "SEZIONE"):
        if candidate in gdf.columns:
            vals = gdf[candidate].astype(str)
            out[f"geometry_{candidate}_sample"] = vals.head(10).tolist()
    # Identify rows belonging to province 097 if a municipal code exists.
    code_col = next((c for c in ("PRO_COM_T", "PRO_COM") if c in gdf.columns), None)
    if code_col:
        codes = gdf[code_col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        out["geometry_rows_province_097"] = int(codes.str.startswith("097").sum())
        out["geometry_rows_core"] = int(codes.isin(CORE_CODES).sum())
        core = gdf.loc[codes.isin(CORE_CODES)].copy().to_crs(7791)
        if len(core):
            minx, miny, maxx, maxy = core.total_bounds
            out["core_bbox_epsg7791"] = [float(minx), float(miny), float(maxx), float(maxy)]

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        out["data_members"] = z.namelist()
        csv_members = [n for n in z.namelist() if n.lower().endswith((".csv", ".txt"))]
        inspected = []
        for name in csv_members[:30]:
            raw = z.read(name)
            text = None
            used_encoding = None
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    text = raw.decode(enc)
                    used_encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                continue
            first = text.splitlines()[:4]
            inspected.append({"name": name, "encoding": used_encoding, "first_lines": first})
        out["data_text_previews"] = inspected
    return out


def arc_query(layer: int, params: dict) -> dict:
    p = {"f": "json", **params}
    payload = get(f"{DBGT_BASE}/{layer}/query", params=p).json()
    if "error" in payload:
        raise RuntimeError(json.dumps(payload["error"], ensure_ascii=False))
    return payload


def inspect_dbgt(core_bbox: list[float]) -> dict:
    out: dict = {}
    service = get(DBGT_BASE, params={"f": "pjson"}).json()
    out["service_spatial_reference"] = service.get("spatialReference")
    out["service_layers"] = service.get("layers")
    for layer in (3, 5, 22, 24):
        meta = get(f"{DBGT_BASE}/{layer}", params={"f": "pjson"}).json()
        out[f"layer_{layer}_name"] = meta.get("name")
        out[f"layer_{layer}_fields"] = [
            {"name": f.get("name"), "alias": f.get("alias"), "domain": f.get("domain")}
            for f in meta.get("fields", [])
        ]
        out[f"layer_{layer}_relationships"] = meta.get("relationships")

    # Broad acquisition probe: the core bbox expanded by 5 km in the DBGT metric CRS.
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
    if sample_ids:
        sample = arc_query(3, {
            "objectIds": ",".join(map(str, sample_ids)),
            "outFields": "OBJECTID,CLASSREF,COD_CONS,DATA_FIN",
            "returnGeometry": "false",
        })
        attrs = [f["attributes"] for f in sample.get("features", [])]
        out["footprint_sample"] = attrs
        refs = [str(a["CLASSREF"]) for a in attrs if a.get("CLASSREF")]
        if refs:
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
            out["building_table_sample"] = [f["attributes"] for f in buildings.get("features", [])]
            out["use_table_sample"] = [f["attributes"] for f in uses.get("features", [])]
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
