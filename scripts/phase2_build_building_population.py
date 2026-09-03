#!/usr/bin/env python3
"""Build Phase 2 building-level dasymetric residential population.

Source hierarchy:
1. ISTAT POSAS 2025 municipal totals: exact calibration FACT.
2. ISTAT 2023 census-section population on 2021 territorial bases: sub-municipal FACT.
3. Regione Lombardia DBGT Tema 0201 Edificato: primary building geometry/use FACT.
4. Gate B OSM walking graph: walking-access DERIVED infrastructure.
5. Gate B WorldPop/POSAS cells: V1 comparison only, never building truth.

The script is deterministic and fail-closed. It never uses synthetic or random data.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import time
import zipfile

import geopandas as gpd
import networkx as nx
import pandas as pd
import requests
from scipy.spatial import cKDTree
from shapely.geometry import Point, box

from src.phase2_building_population import (
    allocate_section_population,
    classify_building,
    derive_section_targets,
    is_fictitious_section,
    reconcile_municipal_population,
)

BASELINE_SHA = "147ad941579eb7ef17a5a54c19a5f820e5a226d4"
GATE_B_SHA = "55d726564e13acca55ce563cc911263ac513acb0"
GATE_B_ARTIFACT_ID = 9873385893
GATE_B_ARTIFACT_SHA256 = "aca8889c8f1a4148c252c3530a56e8c68fa3f33c8e6ddf81a9ed743c51c1cfd1"
WORLDPOP_SOURCE_SHA256 = "a9f9743a08f73e714722ecd54db5e9bb4968bec4a9f88d8f1782c6f7ba1dcea8"
ISTAT_GEOM_URL = "https://www.istat.it/storage/cartografia/basi_territoriali/2021/R03_21.zip"
ISTAT_SECTIONS_2023_URL = "https://esploradati.istat.it/databrowser/DWL/PERMPOP/SUBCOM/Dati_regionali_2023.zip"
POSAS_2025_URL = "https://demo.istat.it/data/posas/POSAS_2025_it_Comuni.zip"
DBGT_BASE = "https://www.cartografia.servizirl.it/arcgis5/rest/services/BaseMap/DBGT_Tema0201_Edificato/MapServer"
CORE_CODES = {"097010", "097012", "097058", "097074", "097092"}
CORE_POSAS_EXPECTED = {
    "097010": 4357.0,
    "097012": 5460.0,
    "097058": 6332.0,
    "097074": 2109.0,
    "097092": 4656.0,
}
ACQUISITION_BUFFER_M = 10_000.0
BOUNDARY_COMPARISON_BAND_M = 150.0
POP_CONNECTOR_MAX_M = 300.0
CONNECTOR_M_PER_MIN = 80.0  # 4.8 km/h, inherited from Gate B.
DBGT_REF_CHUNK = 180
DBGT_OBJECT_CHUNK = 500
DBGT_WORKERS = 8
HTTP_HEADERS = {
    "User-Agent": (
        "tpl-olgiate-building-population/1.0 "
        "(+https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"
    )
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, path: Path, *, timeout: int = 240) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    with requests.get(url, headers=HTTP_HEADERS, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    h.update(chunk)
                    size += len(chunk)
    if size <= 0:
        raise RuntimeError(f"empty download: {url}")
    return {"url": url, "path": str(path), "bytes": size, "sha256": h.hexdigest()}


def normalise_municipality(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def normalise_section(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if text.lower() in {"nan", "none", ""}:
        return ""
    # Join key deliberately ignores leading zero loss caused by spreadsheet typing.
    return text.lstrip("0") or "0"


def parse_number(value: object) -> float:
    if value is None:
        return math.nan
    text = str(value).strip()
    if text in {"", "nan", "None"}:
        return math.nan
    text = text.replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(text)


def _request_json(url: str, *, data: dict | None = None, timeout: int = 180) -> dict:
    last: Exception | None = None
    for attempt in range(4):
        try:
            if data is None:
                r = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
            else:
                r = requests.post(url, data=data, headers=HTTP_HEADERS, timeout=timeout)
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict) and "error" in payload:
                raise RuntimeError(json.dumps(payload["error"], ensure_ascii=False))
            return payload
        except Exception as exc:  # deterministic retries, no jitter/randomness.
            last = exc
            if attempt == 3:
                break
            time.sleep(2 ** attempt)
    raise RuntimeError(f"request failed after retries: {url}: {last}")


def arc_post(layer: int, payload: dict) -> dict:
    return _request_json(f"{DBGT_BASE}/{layer}/query", data={"f": "json", **payload})


def _quoted(values: list[str]) -> str:
    return ",".join("'" + v.replace("'", "''") + "'" for v in values)


def _chunks(values: list, size: int) -> list[list]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def load_istat_geography(source_dir: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    zip_path = source_dir / "istat_R03_21.zip"
    info = download(ISTAT_GEOM_URL, zip_path)
    extract = source_dir / "istat_geom_2021"
    if extract.exists():
        shutil.rmtree(extract)
    extract.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(extract)
    shp = next(extract.rglob("R03_21_WGS84.shp"))
    sections = gpd.read_file(shp).to_crs(32632)
    required = {"PRO_COM", "SEZ21_ID", "geometry"}
    if not required.issubset(sections.columns):
        raise RuntimeError(f"unexpected ISTAT geometry schema: {list(sections.columns)}")
    sections["municipality_code"] = sections["PRO_COM"].map(normalise_municipality)
    sections["section_id"] = sections["SEZ21_ID"].map(normalise_section)
    if sections["section_id"].duplicated().any():
        raise RuntimeError("duplicate ISTAT 2021 section geometry IDs")
    municipality = sections[["municipality_code", "geometry"]].dissolve(by="municipality_code", as_index=False)
    core = municipality.loc[municipality["municipality_code"].isin(CORE_CODES)].copy()
    if len(core) != 5:
        raise RuntimeError(f"expected 5 core municipalities in ISTAT 2021, got {len(core)}")
    core_union = core.geometry.union_all()
    required_buffer = core_union.buffer(ACQUISITION_BUFFER_M)
    selected_municipality = municipality.loc[municipality.intersects(required_buffer)].copy()
    selected_union = selected_municipality.geometry.union_all()
    uncovered = required_buffer.difference(selected_union).area
    if uncovered > 1.0:
        raise RuntimeError(f"selected whole-municipality geography leaves {uncovered:.3f} m2 hole in required buffer")
    selected_codes = set(selected_municipality["municipality_code"])
    selected_sections = sections.loc[sections["municipality_code"].isin(selected_codes)].copy()
    info.update({
        "epistemic_status": "FACT",
        "reference_year": 2021,
        "selected_municipalities": len(selected_codes),
        "selected_section_geometries": len(selected_sections),
        "acquisition_buffer_m_assumption": ACQUISITION_BUFFER_M,
        "acquisition_buffer_uncovered_area_m2": float(uncovered),
    })
    return selected_sections, selected_municipality, info


def load_istat_2023_sections(source_dir: Path, selected_codes: set[str]) -> tuple[pd.DataFrame, dict]:
    zip_path = source_dir / "istat_sections_2023.zip"
    info = download(ISTAT_SECTIONS_2023_URL, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        member = next(n for n in z.namelist() if n.lower().endswith("r03_indicatori_2023_sezioni.xlsx"))
        raw = z.read(member)
    xlsx_path = source_dir / "R03_indicatori_2023_sezioni.xlsx"
    xlsx_path.write_bytes(raw)
    df = pd.read_excel(io.BytesIO(raw), dtype=object, engine="openpyxl")
    section_col = next((c for c in ("SEZ21_ID", "SEZ2021_ID", "SEZIONE", "COD_SEZ") if c in df.columns), None)
    pop_col = next((c for c in ("P1", "POP2023", "POP23", "POP_TOT", "POP") if c in df.columns), None)
    muni_col = next((c for c in ("PRO_COM", "PRO_COM_T", "COD_COM", "CODICE_COMUNE") if c in df.columns), None)
    if section_col is None or pop_col is None:
        raise RuntimeError(f"cannot identify 2023 section/population fields: {list(df.columns)}")
    out = pd.DataFrame({
        "section_id_raw": df[section_col].astype(str),
        "section_id": df[section_col].map(normalise_section),
        "population_2023_fact": pd.to_numeric(df[pop_col], errors="coerce"),
    })
    if muni_col is not None:
        out["municipality_code"] = df[muni_col].map(normalise_municipality)
    else:
        # This path is intentionally strict because leading-zero municipality codes
        # cannot be recovered safely from arbitrary numeric section IDs.
        raise RuntimeError("2023 section data lacks an explicit municipality-code field")
    out = out.loc[out["municipality_code"].isin(selected_codes)].copy()
    if out["population_2023_fact"].isna().any() or (out["population_2023_fact"] < 0).any():
        raise RuntimeError("invalid ISTAT 2023 section population")
    if out["section_id"].duplicated().any():
        raise RuntimeError("duplicate ISTAT 2023 section IDs")
    missing_muni = selected_codes - set(out["municipality_code"])
    if missing_muni:
        raise RuntimeError(f"selected municipalities absent from ISTAT 2023 section data: {sorted(missing_muni)}")
    out["is_fictitious_section"] = out["section_id_raw"].map(is_fictitious_section)
    out["population_2023_epistemic_status"] = "FACT_ISTAT_CENSUS_SECTION_2023"
    info.update({
        "epistemic_status": "FACT",
        "reference_year": 2023,
        "regional_xlsx_sha256": hashlib.sha256(raw).hexdigest(),
        "regional_xlsx_bytes": len(raw),
        "section_id_field": str(section_col),
        "municipality_field": str(muni_col),
        "population_field": str(pop_col),
        "selected_rows": len(out),
        "selected_fictitious_rows": int(out["is_fictitious_section"].sum()),
    })
    return out, info


def load_posas_2025(source_dir: Path, selected_codes: set[str]) -> tuple[pd.DataFrame, dict]:
    zip_path = source_dir / "POSAS_2025_it_Comuni.zip"
    info = download(POSAS_2025_URL, zip_path)
    rows: list[pd.DataFrame] = []
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            if not member.lower().endswith(".csv"):
                continue
            raw = z.read(member)
            parsed = None
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    parsed = pd.read_csv(io.BytesIO(raw), sep=";", skiprows=1, dtype=str, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if parsed is None or "Codice comune" not in parsed.columns:
                continue
            parsed["municipality_code"] = parsed["Codice comune"].map(normalise_municipality)
            hit = parsed.loc[parsed["municipality_code"].isin(selected_codes)].copy()
            if len(hit):
                rows.append(hit)
    if not rows:
        raise RuntimeError("no selected municipality rows found in POSAS 2025")
    all_rows = pd.concat(rows, ignore_index=True)
    age = all_rows["Età"].astype(str).str.strip()
    totals = all_rows.loc[age.eq("999")].copy()
    if totals.empty:
        # Fail closed rather than summing age rows and risking duplicated aggregates.
        raise RuntimeError("POSAS 2025 aggregate age=999 rows not found")
    totals["population_2025_posas_fact"] = totals["Totale"].map(parse_number)
    out = totals[["municipality_code", "Comune", "population_2025_posas_fact"]].drop_duplicates()
    if out["municipality_code"].duplicated().any():
        raise RuntimeError("duplicate POSAS 2025 municipality aggregate")
    missing = selected_codes - set(out["municipality_code"])
    if missing:
        raise RuntimeError(f"selected municipalities absent from POSAS 2025: {sorted(missing)}")
    core = out.loc[out["municipality_code"].isin(CORE_CODES)].set_index("municipality_code")
    for code, expected in CORE_POSAS_EXPECTED.items():
        actual = float(core.loc[code, "population_2025_posas_fact"])
        if actual != expected:
            raise RuntimeError(f"Gate B POSAS lineage mismatch {code}: {actual} != {expected}")
    if float(core["population_2025_posas_fact"].sum()) != 22914.0:
        raise RuntimeError("Gate B core POSAS denominator mismatch")
    out["population_2025_epistemic_status"] = "FACT_ISTAT_POSAS_2025"
    info.update({"epistemic_status": "FACT", "reference_date": "2025-01-01", "selected_municipalities": len(out)})
    return out, info


def fetch_dbgt_footprints(selected_union_32632, source_dir: Path) -> tuple[gpd.GeoDataFrame, dict]:
    union_7791 = gpd.GeoSeries([selected_union_32632], crs=32632).to_crs(7791).iloc[0]
    minx, miny, maxx, maxy = union_7791.bounds
    ids_payload = arc_post(3, {
        "where": "DATA_FIN IS NULL",
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "7791",
        "spatialRel": "esriSpatialRelIntersects",
        "returnIdsOnly": "true",
    })
    ids = sorted(ids_payload.get("objectIds") or [])
    if not ids:
        raise RuntimeError("DBGT footprint query returned no IDs")

    def one(chunk: list[int]) -> dict:
        return _request_json(f"{DBGT_BASE}/3/query", data={
            "f": "geojson",
            "objectIds": ",".join(map(str, chunk)),
            "outFields": "OBJECTID,CLASSREF,COD_CONS,DATA_FIN",
            "returnGeometry": "true",
            "outSR": "4326",
        })

    chunks = _chunks(ids, DBGT_OBJECT_CHUNK)
    payloads: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=DBGT_WORKERS) as pool:
        futures = {pool.submit(one, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            payloads[futures[future]] = future.result()
    features = []
    for i in range(len(chunks)):
        features.extend(payloads[i].get("features", []))
    if not features:
        raise RuntimeError("DBGT footprint features empty")
    gdf = gpd.GeoDataFrame.from_features(features, crs=4326).to_crs(32632)
    if "CLASSREF" not in gdf.columns:
        raise RuntimeError(f"DBGT footprint missing CLASSREF: {list(gdf.columns)}")
    gdf = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf = gdf.loc[gdf.intersects(selected_union_32632)].copy()
    if gdf["CLASSREF"].duplicated().any():
        raise RuntimeError("active DBGT footprint CLASSREF is not one-to-one")
    gdf["footprint_area_m2"] = gdf.geometry.area
    gdf = gdf.loc[gdf["footprint_area_m2"] > 0].sort_values("CLASSREF").reset_index(drop=True)

    snap = source_dir / "dbgt_footprints_selected.geojson"
    gdf.to_crs(4326).to_file(snap, driver="GeoJSON")
    gz = source_dir / "dbgt_footprints_selected.geojson.gz"
    with snap.open("rb") as src, gzip.open(gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    snap.unlink()
    info = {
        "url": f"{DBGT_BASE}/3",
        "epistemic_status": "FACT",
        "query": "DATA_FIN IS NULL; bbox of selected whole-municipality acquisition geography; clipped to union",
        "bbox_candidate_object_ids": len(ids),
        "selected_active_footprints": len(gdf),
        "snapshot_path": str(gz),
        "snapshot_sha256": sha256_file(gz),
        "snapshot_bytes": gz.stat().st_size,
    }
    return gdf, info


def query_dbgt_table(layer: int, key: str, refs: list[str], fields: str) -> pd.DataFrame:
    refs = sorted(set(refs))
    chunks = _chunks(refs, DBGT_REF_CHUNK)

    def one(chunk: list[str]) -> list[dict]:
        payload = arc_post(layer, {
            "where": f"{key} IN ({_quoted(chunk)}) AND DATA_FIN IS NULL",
            "outFields": fields,
            "returnGeometry": "false",
        })
        return [f["attributes"] for f in payload.get("features", [])]

    results: dict[int, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=DBGT_WORKERS) as pool:
        futures = {pool.submit(one, chunk): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    rows: list[dict] = []
    for i in range(len(chunks)):
        rows.extend(results[i])
    return pd.DataFrame(rows)


def enrich_dbgt(footprints: gpd.GeoDataFrame, source_dir: Path) -> tuple[gpd.GeoDataFrame, dict]:
    refs = footprints["CLASSREF"].astype(str).tolist()
    edifc = query_dbgt_table(
        22, "CLASSID", refs,
        "OBJECTID,CLASSID,EDIFC_STAT,EDIFC_TY,FONTE,SCALA,COD_CONS,DATA_INI,DATA_FIN",
    )
    uses = query_dbgt_table(24, "CLASSREF", refs, "OBJECTID,CLASSREF,EDIFC_USO,COD_CONS,DATA_FIN")
    if len(edifc) and edifc["CLASSID"].duplicated().any():
        raise RuntimeError("multiple active EDIFC records for one CLASSID")
    use_map = (
        uses.groupby("CLASSREF")["EDIFC_USO"].apply(lambda s: sorted(set(s.dropna().astype(str)))).to_dict()
        if len(uses) else {}
    )
    metadata = edifc.set_index("CLASSID").to_dict("index") if len(edifc) else {}

    rows = []
    for ref in refs:
        meta = metadata.get(ref, {})
        cls = classify_building(
            status_code=meta.get("EDIFC_STAT"),
            type_code=meta.get("EDIFC_TY"),
            use_codes=use_map.get(ref, []),
        )
        rows.append({
            "CLASSREF": ref,
            "dbgt_status_fact": meta.get("EDIFC_STAT"),
            "dbgt_type_fact": meta.get("EDIFC_TY"),
            "dbgt_use_codes_fact": "|".join(use_map.get(ref, [])),
            "residential_plausibility": cls.plausibility,
            "eligible_primary": cls.eligible_primary,
            "eligible_fallback": cls.eligible_fallback,
            "residential_use_present": cls.residential_use_present,
            "mixed_use": cls.mixed_use,
            "classification_uncertainty_flags": "|".join(cls.uncertainty_flags),
            "classification_epistemic_status": "DERIVED_FROM_DBGT_STATUS_USAGE_TYPE",
        })
    classification = pd.DataFrame(rows)
    gdf = footprints.merge(classification, on="CLASSREF", how="left", validate="one_to_one")

    volume_refs = gdf.loc[gdf["eligible_primary"] | gdf["eligible_fallback"], "CLASSREF"].astype(str).tolist()
    volumes = query_dbgt_table(
        0, "CEDIUV", volume_refs,
        "OBJECTID,CLASSID,CEDIUV,UN_VOL_AV,UN_VOL_EX,UN_VOL_QE,Shape_Area,COD_CONS,DATA_FIN",
    ) if volume_refs else pd.DataFrame()
    volume_summary = {}
    if len(volumes):
        for ref, group in volumes.groupby("CEDIUV"):
            heights = pd.to_numeric(group["UN_VOL_AV"], errors="coerce")
            areas = pd.to_numeric(group["Shape_Area"], errors="coerce")
            complete = len(group) > 0 and heights.notna().all() and areas.notna().all() and (heights > 0).all() and (areas > 0).all()
            proxy = float((heights * areas).sum()) if complete else math.nan
            volume_summary[str(ref)] = (complete, proxy, len(group))
    gdf["dbgt_volume_units_count"] = gdf["CLASSREF"].map(lambda r: volume_summary.get(str(r), (False, math.nan, 0))[2])
    gdf["dbgt_volume_complete"] = gdf["CLASSREF"].map(lambda r: volume_summary.get(str(r), (False, math.nan, 0))[0])
    gdf["dbgt_volume_proxy_m3"] = gdf["CLASSREF"].map(lambda r: volume_summary.get(str(r), (False, math.nan, 0))[1])
    gdf["allocation_weight_basis"] = gdf["dbgt_volume_complete"].map(
        lambda complete: "DBGT_VOLUME_PROXY_COMPLETE" if complete else "DBGT_FOOTPRINT_AREA"
    )

    edifc_path = source_dir / "dbgt_edifc_selected.csv.gz"
    uses_path = source_dir / "dbgt_uses_selected.csv.gz"
    vol_path = source_dir / "dbgt_volume_units_selected.csv.gz"
    edifc.sort_values("CLASSID").to_csv(edifc_path, index=False, compression="gzip")
    uses.sort_values(["CLASSREF", "EDIFC_USO"]).to_csv(uses_path, index=False, compression="gzip")
    volumes.sort_values(["CEDIUV", "CLASSID"]).to_csv(vol_path, index=False, compression="gzip") if len(volumes) else pd.DataFrame().to_csv(vol_path, index=False, compression="gzip")
    info = {
        "edifc_url": f"{DBGT_BASE}/22",
        "uses_url": f"{DBGT_BASE}/24",
        "volume_url": f"{DBGT_BASE}/0",
        "epistemic_status": "FACT",
        "active_edifc_rows": len(edifc),
        "active_use_rows": len(uses),
        "active_volume_unit_rows": len(volumes),
        "volume_complete_buildings": int(gdf["dbgt_volume_complete"].sum()),
        "edifc_snapshot_sha256": sha256_file(edifc_path),
        "uses_snapshot_sha256": sha256_file(uses_path),
        "volume_snapshot_sha256": sha256_file(vol_path),
    }
    return gdf, info


def build_section_pieces(
    buildings: gpd.GeoDataFrame,
    section_geometry: gpd.GeoDataFrame,
) -> pd.DataFrame:
    eligible = buildings.loc[buildings["eligible_primary"] | buildings["eligible_fallback"], [
        "CLASSREF", "footprint_area_m2", "dbgt_volume_complete", "dbgt_volume_proxy_m3",
        "eligible_primary", "eligible_fallback", "allocation_weight_basis", "geometry",
    ]].copy()
    sec = section_geometry[["section_id", "municipality_code", "geometry"]].copy()
    joined = gpd.sjoin(eligible, sec, how="inner", predicate="intersects")
    sec_geom = sec.geometry.to_dict()
    rows = []
    for row in joined.itertuples():
        geom = row.geometry
        sgeom = sec_geom[row.index_right]
        inter = geom.intersection(sgeom)
        area = float(inter.area) if not inter.is_empty else 0.0
        if area <= 0:
            continue
        footprint_area = float(row.footprint_area_m2)
        if bool(row.dbgt_volume_complete) and pd.notna(row.dbgt_volume_proxy_m3) and footprint_area > 0:
            weight = float(row.dbgt_volume_proxy_m3) * area / footprint_area
            basis = "DBGT_VOLUME_PROXY_COMPLETE_PRORATED_BY_SECTION_INTERSECTION"
        else:
            weight = area
            basis = "DBGT_FOOTPRINT_SECTION_INTERSECTION_AREA"
        rows.append({
            "building_id": row.CLASSREF,
            "section_id": row.section_id,
            "municipality_code": row.municipality_code,
            "eligible_primary": bool(row.eligible_primary),
            "eligible_fallback": bool(row.eligible_fallback),
            "intersection_area_m2": area,
            "allocation_weight": weight,
            "allocation_weight_basis_piece": basis,
            "weight_epistemic_status": "DERIVED_FROM_DBGT_GEOMETRY_AND_AVAILABLE_VOLUME",
        })
    return pd.DataFrame(rows)


def build_gate_b_access(gate_b_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[int, float], cKDTree, list[int], list[tuple[float, float]]]:
    nodes = pd.read_csv(gate_b_dir / "walk_graph_nodes.csv")
    edges = pd.read_csv(gate_b_dir / "walk_graph_edges.csv")
    stops = pd.read_csv(gate_b_dir / "gtfs_core_stops.csv")
    nodes = nodes.loc[nodes["in_giant_component"].astype(bool)].copy()
    edges = edges.loc[edges["in_giant_component"].astype(bool)].copy()
    G = nx.DiGraph()
    for row in edges.itertuples(index=False):
        G.add_edge(int(row.u), int(row.v), weight=float(row.walk_min_uv))
        G.add_edge(int(row.v), int(row.u), weight=float(row.walk_min_vu))
    H = G.reverse(copy=True)
    super_source = -1
    H.add_node(super_source)
    valid_stops = stops.loc[stops["snap_ok"].astype(bool)].copy()
    for row in valid_stops.itertuples(index=False):
        H.add_edge(super_source, int(row.graph_node_id), weight=float(row.snap_distance_m) / CONNECTOR_M_PER_MIN)
    distance_to_stop = nx.single_source_dijkstra_path_length(H, super_source, weight="weight")
    node_ids = nodes["node_id"].astype(int).tolist()
    xy = list(zip(nodes["x_utm32"].astype(float), nodes["y_utm32"].astype(float)))
    tree = cKDTree(xy)
    return nodes, edges, stops, distance_to_stop, tree, node_ids, xy


def compute_accessibility(
    building_allocations: pd.DataFrame,
    building_points: pd.DataFrame,
    gate_b_dir: Path,
) -> pd.DataFrame:
    _, _, _, network_minutes, tree, node_ids, _ = build_gate_b_access(gate_b_dir)
    core_alloc = building_allocations.loc[building_allocations["municipality_code"].isin(CORE_CODES)].copy()
    core_alloc = core_alloc.merge(
        building_points[["building_id", "x_utm32", "y_utm32"]],
        on="building_id", how="left", validate="many_to_one",
    )
    if core_alloc[["x_utm32", "y_utm32"]].isna().any().any():
        raise RuntimeError("allocated core building lacks representative point")
    distances, indexes = tree.query(core_alloc[["x_utm32", "y_utm32"]].to_numpy(), k=1)
    core_alloc["nearest_graph_node_id"] = [node_ids[int(i)] for i in indexes]
    core_alloc["connector_distance_m"] = [float(v) for v in distances]
    core_alloc["connector_walk_min"] = core_alloc["connector_distance_m"] / CONNECTOR_M_PER_MIN
    core_alloc["connector_within_limit"] = core_alloc["connector_distance_m"] <= POP_CONNECTOR_MAX_M
    core_alloc["network_walk_min_to_gtfs_stop"] = core_alloc["nearest_graph_node_id"].map(network_minutes)
    core_alloc["walk_min_to_nearest_gtfs_stop"] = (
        core_alloc["network_walk_min_to_gtfs_stop"] + core_alloc["connector_walk_min"]
    )
    core_alloc.loc[~core_alloc["connector_within_limit"], "walk_min_to_nearest_gtfs_stop"] = math.nan
    for threshold in (5, 8, 10, 12):
        core_alloc[f"covered_{threshold}min"] = core_alloc["walk_min_to_nearest_gtfs_stop"].le(threshold).fillna(False)
    core_alloc["accessibility_epistemic_status"] = "MODEL_OUTPUT_GATE_B_WALK_GRAPH_BUILDING_REPRESENTATIVE_POINT"
    return core_alloc


def make_coverage_summary(
    accessibility: pd.DataFrame,
    municipal_targets: pd.DataFrame,
    residuals: pd.DataFrame,
) -> pd.DataFrame:
    core_targets = municipal_targets.loc[municipal_targets["municipality_code"].isin(CORE_CODES)].copy()
    res = residuals.merge(
        section_targets_global[["section_id", "municipality_code"]].drop_duplicates(),
        on="section_id", how="left", validate="one_to_one",
    )
    residual_muni = res.groupby("municipality_code")["unallocated_population"].sum().to_dict()
    rows = []
    for code, group in accessibility.groupby("municipality_code"):
        total = float(core_targets.loc[core_targets["municipality_code"] == code, "population_2025_posas_fact"].iloc[0])
        located = float(group["building_piece_population_model"].sum())
        for threshold in (5, 8, 10, 12):
            covered = float(group.loc[group[f"covered_{threshold}min"], "building_piece_population_model"].sum())
            rows.append({
                "scope": "municipality",
                "municipality_code": code,
                "threshold_min": threshold,
                "population_total_posas_2025": total,
                "population_located_buildings": located,
                "population_residual_unlocated": float(residual_muni.get(code, 0.0)),
                "population_covered_buildings": covered,
                "coverage_pct_total_posas": 100.0 * covered / total if total else math.nan,
                "coverage_pct_located_buildings": 100.0 * covered / located if located else math.nan,
                "epistemic_status": "MODEL_OUTPUT_BUILDING_POPULATION_ON_GATE_B_WALK_GRAPH",
            })
    total_target = float(core_targets["population_2025_posas_fact"].sum())
    located_total = float(accessibility["building_piece_population_model"].sum())
    residual_total = sum(float(residual_muni.get(c, 0.0)) for c in CORE_CODES)
    for threshold in (5, 8, 10, 12):
        covered = float(accessibility.loc[accessibility[f"covered_{threshold}min"], "building_piece_population_model"].sum())
        rows.append({
            "scope": "core_total",
            "municipality_code": "CORE_TOTAL",
            "threshold_min": threshold,
            "population_total_posas_2025": total_target,
            "population_located_buildings": located_total,
            "population_residual_unlocated": residual_total,
            "population_covered_buildings": covered,
            "coverage_pct_total_posas": 100.0 * covered / total_target,
            "coverage_pct_located_buildings": 100.0 * covered / located_total if located_total else math.nan,
            "epistemic_status": "MODEL_OUTPUT_BUILDING_POPULATION_ON_GATE_B_WALK_GRAPH",
        })
    return pd.DataFrame(rows)


def compare_v1_v2(coverage_v2: pd.DataFrame, gate_b_dir: Path) -> pd.DataFrame:
    v1 = pd.read_csv(gate_b_dir / "coverage_summary.csv")
    v1["municipality_code"] = v1["PRO_COM_T"].map(lambda x: normalise_municipality(x) if pd.notna(x) else "CORE_TOTAL")
    v1.loc[v1["scope"].eq("core_total"), "municipality_code"] = "CORE_TOTAL"
    v1 = v1.rename(columns={
        "population_total_2025": "v1_population_total_2025",
        "population_covered_2025": "v1_population_covered_2025",
        "coverage_pct": "v1_coverage_pct",
    })
    out = coverage_v2.merge(
        v1[["scope", "municipality_code", "threshold_min", "v1_population_total_2025", "v1_population_covered_2025", "v1_coverage_pct"]],
        on=["scope", "municipality_code", "threshold_min"], how="left", validate="one_to_one",
    )
    if out["v1_coverage_pct"].isna().any():
        raise RuntimeError("V1/V2 coverage comparison failed to match Gate B baseline")
    out["v2_minus_v1_coverage_pct_points"] = out["coverage_pct_total_posas"] - out["v1_coverage_pct"]
    out["comparison_epistemic_status"] = "MODEL_OUTPUT_COMPARISON_V1_WORLDPOP_V2_BUILDINGS"
    return out


def worldpop_heterogeneity(
    building_table: pd.DataFrame,
    gate_b_dir: Path,
) -> tuple[pd.DataFrame, dict]:
    cells = pd.read_csv(gate_b_dir / "population_cells_real.csv")
    cells["geometry"] = [
        box(
            float(r.lon) - float(r.cell_width_deg) / 2,
            float(r.lat) - float(r.cell_height_deg) / 2,
            float(r.lon) + float(r.cell_width_deg) / 2,
            float(r.lat) + float(r.cell_height_deg) / 2,
        ) for r in cells.itertuples(index=False)
    ]
    cells_gdf = gpd.GeoDataFrame(cells, geometry="geometry", crs=4326)
    positive = building_table.loc[
        (building_table["resident_population_model"] > 0)
        & building_table["representative_lon"].notna()
        & building_table["representative_lat"].notna()
        & building_table["representative_municipality_code"].isin(CORE_CODES)
    ].copy()
    pts = gpd.GeoDataFrame(
        positive,
        geometry=gpd.points_from_xy(positive["representative_lon"], positive["representative_lat"]),
        crs=4326,
    )
    joined = gpd.sjoin(pts, cells_gdf[["cell_id", "geometry"]], how="left", predicate="within")
    unmatched_pop = float(joined.loc[joined["cell_id"].isna(), "resident_population_model"].sum())
    matched = joined.loc[joined["cell_id"].notna()].copy().to_crs(32632)
    if len(matched):
        matched["rep_x"] = matched.geometry.x
        matched["rep_y"] = matched.geometry.y
        agg = matched.groupby("cell_id").agg(
            v2_building_count=("building_id", "nunique"),
            v2_population_at_building_representatives=("resident_population_model", "sum"),
            rep_x_min=("rep_x", "min"),
            rep_x_max=("rep_x", "max"),
            rep_y_min=("rep_y", "min"),
            rep_y_max=("rep_y", "max"),
        ).reset_index()
        agg["building_representative_bbox_diagonal_m"] = (
            (agg["rep_x_max"] - agg["rep_x_min"]) ** 2
            + (agg["rep_y_max"] - agg["rep_y_min"]) ** 2
        ) ** 0.5
    else:
        agg = pd.DataFrame(columns=["cell_id", "v2_building_count", "v2_population_at_building_representatives", "building_representative_bbox_diagonal_m"])
    out = cells.drop(columns="geometry").merge(agg, on="cell_id", how="left")
    out["v2_building_count"] = out["v2_building_count"].fillna(0).astype(int)
    out["v2_population_at_building_representatives"] = out["v2_population_at_building_representatives"].fillna(0.0)
    out["building_representative_bbox_diagonal_m"] = out["building_representative_bbox_diagonal_m"].fillna(0.0)
    out["v2_minus_v1_population_at_cell_representation"] = out["v2_population_at_building_representatives"] - out["pop_calibrated_2025"]
    out["comparison_epistemic_status"] = "DERIVED_REPRESENTATIVE_POINT_COMPARISON_NOT_REAL_BUILDING_OCCUPANCY"
    return out, {
        "v2_positive_building_population_not_inside_any_positive_v1_worldpop_cell": unmatched_pop,
        "v1_positive_cells_with_multiple_v2_buildings": int((out["v2_building_count"] >= 2).sum()),
    }


def boundary_comparison(
    building_allocations: pd.DataFrame,
    building_points: pd.DataFrame,
    gate_b_dir: Path,
    core_boundaries_path: Path,
) -> pd.DataFrame:
    boundaries = gpd.read_file(core_boundaries_path).to_crs(32632)
    boundaries["municipality_code"] = boundaries["PRO_COM_T"].map(normalise_municipality)
    boundary_map = boundaries.set_index("municipality_code").geometry.to_dict()

    cells = pd.read_csv(gate_b_dir / "population_cells_real.csv")
    cells["municipality_code"] = cells["PRO_COM_T"].map(normalise_municipality)
    cell_pts = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326).to_crs(32632)
    cell_pts["distance_to_municipal_boundary_m"] = [
        row.geometry.distance(boundary_map[row.municipality_code].boundary)
        for row in cell_pts.itertuples()
    ]
    v1_band = cell_pts.loc[cell_pts["distance_to_municipal_boundary_m"] <= BOUNDARY_COMPARISON_BAND_M]
    v1 = v1_band.groupby("municipality_code")["pop_calibrated_2025"].sum().to_dict()

    alloc = building_allocations.loc[building_allocations["municipality_code"].isin(CORE_CODES)].merge(
        building_points[["building_id", "x_utm32", "y_utm32"]], on="building_id", how="left", validate="many_to_one"
    )
    alloc["distance_to_municipal_boundary_m"] = [
        Point(float(r.x_utm32), float(r.y_utm32)).distance(boundary_map[r.municipality_code].boundary)
        for r in alloc.itertuples()
    ]
    v2_band = alloc.loc[alloc["distance_to_municipal_boundary_m"] <= BOUNDARY_COMPARISON_BAND_M]
    v2 = v2_band.groupby("municipality_code")["building_piece_population_model"].sum().to_dict()
    return pd.DataFrame([
        {
            "municipality_code": code,
            "boundary_band_m_assumption": BOUNDARY_COMPARISON_BAND_M,
            "v1_worldpop_population_near_boundary": float(v1.get(code, 0.0)),
            "v2_building_population_near_boundary": float(v2.get(code, 0.0)),
            "v2_minus_v1_population_near_boundary": float(v2.get(code, 0.0) - v1.get(code, 0.0)),
            "epistemic_status": "MODEL_OUTPUT_SPATIAL_COMPARISON",
        }
        for code in sorted(CORE_CODES)
    ])


def spatial_distribution_comparison(
    building_allocations: pd.DataFrame,
    building_points: pd.DataFrame,
    gate_b_dir: Path,
) -> pd.DataFrame:
    cells = pd.read_csv(gate_b_dir / "population_cells_real.csv")
    cells["municipality_code"] = cells["PRO_COM_T"].map(normalise_municipality)
    cells_gdf = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.lon, cells.lat), crs=4326).to_crs(32632)
    cells_gdf["x"] = cells_gdf.geometry.x
    cells_gdf["y"] = cells_gdf.geometry.y
    alloc = building_allocations.loc[building_allocations["municipality_code"].isin(CORE_CODES)].merge(
        building_points[["building_id", "x_utm32", "y_utm32"]], on="building_id", how="left", validate="many_to_one"
    )
    rows = []
    for code in sorted(CORE_CODES) + ["CORE_TOTAL"]:
        v1 = cells_gdf if code == "CORE_TOTAL" else cells_gdf.loc[cells_gdf["municipality_code"] == code]
        v2 = alloc if code == "CORE_TOTAL" else alloc.loc[alloc["municipality_code"] == code]
        w1 = v1["pop_calibrated_2025"].astype(float)
        w2 = v2["building_piece_population_model"].astype(float)
        x1 = float((v1["x"] * w1).sum() / w1.sum())
        y1 = float((v1["y"] * w1).sum() / w1.sum())
        x2 = float((v2["x_utm32"] * w2).sum() / w2.sum()) if w2.sum() else math.nan
        y2 = float((v2["y_utm32"] * w2).sum() / w2.sum()) if w2.sum() else math.nan
        shift = math.hypot(x2 - x1, y2 - y1) if math.isfinite(x2) else math.nan
        rows.append({
            "municipality_code": code,
            "v1_worldpop_weighted_centroid_x_utm32": x1,
            "v1_worldpop_weighted_centroid_y_utm32": y1,
            "v2_building_weighted_centroid_x_utm32": x2,
            "v2_building_weighted_centroid_y_utm32": y2,
            "weighted_centroid_shift_m": shift,
            "epistemic_status": "DERIVED_SPATIAL_DISTRIBUTION_COMPARISON",
        })
    return pd.DataFrame(rows)


def write_checksums(output_dir: Path) -> Path:
    files = sorted(
        p for p in output_dir.iterdir()
        if p.is_file() and p.name != "building_population_checksums.sha256"
        and p.name.startswith("building_population")
    )
    path = output_dir / "building_population_checksums.sha256"
    path.write_text("".join(f"{sha256_file(p)}  {p.name}\n" for p in files), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate-b-dir", required=True, type=Path)
    parser.add_argument("--core-boundaries", default="data/raw/boundaries/comuni_core_istat_2026.geojson", type=Path)
    parser.add_argument("--output-dir", default="outputs/phase2", type=Path)
    parser.add_argument("--source-cache", default="/tmp/building_population_sources", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.source_cache.mkdir(parents=True, exist_ok=True)

    for required in ("population_cells_real.csv", "coverage_summary.csv", "walk_graph_nodes.csv", "walk_graph_edges.csv", "gtfs_core_stops.csv"):
        if not (args.gate_b_dir / required).is_file():
            raise FileNotFoundError(args.gate_b_dir / required)

    sections_geom, selected_muni_geom, geom_source = load_istat_geography(args.source_cache)
    selected_codes = set(selected_muni_geom["municipality_code"])
    section_data, sections_source = load_istat_2023_sections(args.source_cache, selected_codes)
    posas, posas_source = load_posas_2025(args.source_cache, selected_codes)
    selected_union = selected_muni_geom.geometry.union_all()

    global section_targets_global
    section_targets_global = derive_section_targets(section_data, posas)
    geom_keys = set(sections_geom["section_id"])
    ordinary = section_targets_global.loc[~section_targets_global["is_fictitious_section"]].copy()
    missing_geom = ordinary.loc[~ordinary["section_id"].isin(geom_keys)]
    if len(missing_geom) and float(missing_geom["section_population_2025_derived"].sum()) > 1e-7:
        raise RuntimeError(
            "positive ordinary ISTAT 2023 population lacks 2021 section geometry: "
            f"rows={len(missing_geom)} population={missing_geom['section_population_2025_derived'].sum()}"
        )
    section_geometry_model = sections_geom.merge(
        ordinary[["section_id", "population_2023_fact", "section_population_2025_derived"]],
        on="section_id", how="inner", validate="one_to_one",
    )

    footprints, footprint_source = fetch_dbgt_footprints(selected_union, args.source_cache)
    buildings, dbgt_source = enrich_dbgt(footprints, args.source_cache)
    pieces = build_section_pieces(buildings, section_geometry_model)
    ordinary_targets_for_allocation = ordinary.loc[ordinary["section_id"].isin(set(section_geometry_model["section_id"]))].copy()
    allocations, ordinary_residuals = allocate_section_population(pieces, ordinary_targets_for_allocation)

    fake_residuals = section_targets_global.loc[section_targets_global["is_fictitious_section"], ["section_id", "section_population_2025_derived"]].copy()
    fake_residuals["allocated_population"] = 0.0
    fake_residuals["unallocated_population"] = fake_residuals["section_population_2025_derived"]
    fake_residuals["allocation_tier"] = "NONSPATIAL_FICTITIOUS_SECTION"
    missing_zero = missing_geom[["section_id", "section_population_2025_derived"]].copy()
    missing_zero["allocated_population"] = 0.0
    missing_zero["unallocated_population"] = missing_zero["section_population_2025_derived"]
    missing_zero["allocation_tier"] = "UNALLOCATED_ORDINARY_SECTION_WITHOUT_GEOMETRY"
    residuals = pd.concat([ordinary_residuals, fake_residuals, missing_zero], ignore_index=True)
    if residuals["section_id"].duplicated().any():
        raise RuntimeError("duplicate section residual accounting")

    reconciliation = reconcile_municipal_population(
        building_allocations=allocations,
        section_targets=section_targets_global,
        section_residuals=residuals,
        municipal_targets=posas,
    )

    # Building representative points are DERIVED from official footprint geometry.
    reps = buildings.geometry.representative_point()
    reps_wgs = gpd.GeoSeries(reps, crs=32632).to_crs(4326)
    buildings["building_id"] = buildings["CLASSREF"].astype(str)
    buildings["x_utm32"] = reps.x
    buildings["y_utm32"] = reps.y
    buildings["representative_lon"] = reps_wgs.x
    buildings["representative_lat"] = reps_wgs.y
    agg = allocations.groupby("building_id").agg(
        resident_population_model=("building_piece_population_model", "sum"),
        allocated_section_count=("section_id", "nunique"),
    ).reset_index() if len(allocations) else pd.DataFrame(columns=["building_id", "resident_population_model", "allocated_section_count"])
    buildings = buildings.merge(agg, on="building_id", how="left", validate="one_to_one")
    buildings["resident_population_model"] = buildings["resident_population_model"].fillna(0.0)
    buildings["allocated_section_count"] = buildings["allocated_section_count"].fillna(0).astype(int)
    buildings["resident_estimate_epistemic_status"] = "MODEL_OUTPUT_DASYMETRIC_BUILDING_POPULATION"
    buildings["geometry_epistemic_status"] = "FACT_DBGT_BUILDING_FOOTPRINT"
    buildings["representative_point_epistemic_status"] = "DERIVED_FROM_DBGT_FOOTPRINT"

    # Representative municipality is display/context only; accounting remains by section allocation.
    rep_points_gdf = gpd.GeoDataFrame(
        buildings[["building_id", "x_utm32", "y_utm32", "representative_lon", "representative_lat"]].copy(),
        geometry=gpd.points_from_xy(buildings["x_utm32"], buildings["y_utm32"]), crs=32632,
    )
    rep_join = gpd.sjoin(rep_points_gdf, selected_muni_geom[["municipality_code", "geometry"]], how="left", predicate="within")
    rep_muni = rep_join.drop_duplicates("building_id").set_index("building_id")["municipality_code"].to_dict()
    buildings["representative_municipality_code"] = buildings["building_id"].map(rep_muni)

    allocations = allocations.merge(
        section_targets_global[["section_id", "municipality_code"]].drop_duplicates(),
        on="section_id", how="left", suffixes=("", "_target"), validate="many_to_one",
    )
    if "municipality_code_target" in allocations.columns:
        mismatch = allocations["municipality_code"] != allocations["municipality_code_target"]
        if mismatch.any():
            raise RuntimeError("building-section allocation municipality mismatch")
        allocations = allocations.drop(columns="municipality_code_target")

    building_points = buildings[["building_id", "x_utm32", "y_utm32", "representative_lon", "representative_lat"]].copy()
    accessibility = compute_accessibility(allocations, building_points, args.gate_b_dir)
    coverage = make_coverage_summary(accessibility, posas, residuals)
    v1_v2 = compare_v1_v2(coverage, args.gate_b_dir)
    heterogeneity, heterogeneity_summary = worldpop_heterogeneity(
        buildings[["building_id", "resident_population_model", "representative_lon", "representative_lat", "representative_municipality_code"]],
        args.gate_b_dir,
    )
    boundary = boundary_comparison(allocations, building_points, args.gate_b_dir, args.core_boundaries)
    spatial_compare = spatial_distribution_comparison(allocations, building_points, args.gate_b_dir)

    # Persist broad acquisition coverage and selected municipalities.
    coverage_geom = selected_muni_geom.to_crs(4326).copy()
    coverage_geom["acquisition_buffer_m_assumption"] = ACQUISITION_BUFFER_M
    coverage_geom["epistemic_status"] = "FACT_ISTAT2021_GEOMETRY_SELECTED_BY_ASSUMPTION_BUFFER"
    coverage_geom.to_file(args.output_dir / "building_population_acquisition_coverage.geojson", driver="GeoJSON")

    section_output = section_targets_global.merge(
        sections_geom[["section_id", "municipality_code"]].assign(has_geometry_2021=True),
        on=["section_id", "municipality_code"], how="left",
    )
    section_output["has_geometry_2021"] = section_output["has_geometry_2021"].fillna(False)
    section_output.to_csv(args.output_dir / "building_population_sections.csv", index=False)
    residuals.to_csv(args.output_dir / "building_population_residuals.csv", index=False)
    reconciliation.to_csv(args.output_dir / "building_population_municipal_reconciliation.csv", index=False)
    allocations.to_csv(args.output_dir / "building_population_allocations.csv", index=False)
    accessibility.to_csv(args.output_dir / "building_population_accessibility.csv", index=False)
    coverage.to_csv(args.output_dir / "building_population_coverage_summary.csv", index=False)
    v1_v2.to_csv(args.output_dir / "building_population_v1_v2_catchment_comparison.csv", index=False)
    heterogeneity.to_csv(args.output_dir / "building_population_worldpop_heterogeneity.csv", index=False)
    boundary.to_csv(args.output_dir / "building_population_boundary_comparison.csv", index=False)
    spatial_compare.to_csv(args.output_dir / "building_population_spatial_distribution_comparison.csv", index=False)

    building_columns = [
        "building_id", "representative_municipality_code", "representative_lon", "representative_lat",
        "x_utm32", "y_utm32", "footprint_area_m2", "dbgt_status_fact", "dbgt_type_fact",
        "dbgt_use_codes_fact", "residential_plausibility", "eligible_primary", "eligible_fallback",
        "mixed_use", "classification_uncertainty_flags", "classification_epistemic_status",
        "dbgt_volume_units_count", "dbgt_volume_complete", "dbgt_volume_proxy_m3",
        "allocation_weight_basis", "resident_population_model", "allocated_section_count",
        "resident_estimate_epistemic_status", "geometry_epistemic_status", "representative_point_epistemic_status",
    ]
    buildings[building_columns].to_csv(args.output_dir / "building_population_buildings.csv", index=False)
    core_positive = buildings.loc[
        (buildings["resident_population_model"] > 0)
        & buildings["representative_municipality_code"].isin(CORE_CODES)
    ].copy().to_crs(4326)
    core_positive[building_columns + ["geometry"]].to_file(
        args.output_dir / "building_population_buildings_core.geojson", driver="GeoJSON"
    )

    source_manifest = {
        "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_phase2_optimizer_core": BASELINE_SHA,
        "gate_b_commit": GATE_B_SHA,
        "gate_b_artifact_id": GATE_B_ARTIFACT_ID,
        "gate_b_artifact_zip_sha256_expected": GATE_B_ARTIFACT_SHA256,
        "worldpop_2020_national_sha256_gate_b": WORLDPOP_SOURCE_SHA256,
        "sources": {
            "istat_2021_geometry": geom_source,
            "istat_2023_sections": sections_source,
            "istat_posas_2025": posas_source,
            "lombardia_dbgt_footprints": footprint_source,
            "lombardia_dbgt_attributes": dbgt_source,
        },
        "source_hierarchy": [
            "FACT ISTAT POSAS 2025 municipal calibration totals",
            "FACT ISTAT 2023 census-section population on 2021 territorial bases",
            "FACT Regione Lombardia DBGT building footprints/status/use/available volumetric units",
            "DERIVED Gate B OSM walking graph for accessibility only",
            "Gate B WorldPop/POSAS V1 retained only for comparison/sensitivity",
        ],
    }
    (args.output_dir / "building_population_source_manifest.json").write_text(
        json.dumps(source_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    core_recon = reconciliation.loc[reconciliation["municipality_code"].isin(CORE_CODES)]
    core_coverage = coverage.loc[coverage["scope"].eq("core_total")].set_index("threshold_min")
    validation = {
        "status": "PASS_BUILDING_POPULATION_BUILD",
        "scope": "BUILDING_DASYMETRIC_POPULATION_NOT_STOP_RANKING_NOT_NETWORK_SELECTION",
        "baseline_sha": BASELINE_SHA,
        "gate_b_commit": GATE_B_SHA,
        "gate_b_artifact_id": GATE_B_ARTIFACT_ID,
        "acquisition_buffer_m_assumption": ACQUISITION_BUFFER_M,
        "selected_whole_municipalities": len(selected_codes),
        "selected_section_records_2023": len(section_targets_global),
        "selected_dbgt_buildings": len(buildings),
        "explicit_residential_buildings": int((buildings["residential_plausibility"] == "EXPLICIT_RESIDENTIAL").sum()),
        "mixed_residential_buildings": int((buildings["residential_plausibility"] == "MIXED_RESIDENTIAL").sum()),
        "unknown_use_fallback_buildings": int((buildings["residential_plausibility"] == "UNKNOWN_OR_OTHER_USE").sum()),
        "explicit_nonresidential_buildings": int((buildings["residential_plausibility"] == "EXPLICIT_NONRESIDENTIAL").sum()),
        "volume_complete_buildings": int(buildings["dbgt_volume_complete"].sum()),
        "allocated_building_section_pieces": len(allocations),
        "core_posas_2025_total": float(core_recon["population_2025_posas_fact"].sum()),
        "core_building_population_located": float(core_recon["building_population_model"].sum()),
        "core_population_residual_unlocated": float(core_recon["section_residual_population"].sum()),
        "all_selected_municipalities_reconcile_exactly": bool(reconciliation["reconciliation_pass"].all()),
        "max_abs_reconciliation_error": float(reconciliation["reconciliation_error"].abs().max()),
        "core_v2_coverage_pct_total_posas": {
            str(t): float(core_coverage.loc[t, "coverage_pct_total_posas"]) for t in (5, 8, 10, 12)
        },
        "core_v1_coverage_pct_worldpop_posas": {
            str(t): float(v1_v2.loc[(v1_v2["scope"] == "core_total") & (v1_v2["threshold_min"] == t), "v1_coverage_pct"].iloc[0])
            for t in (5, 8, 10, 12)
        },
        "heterogeneity": heterogeneity_summary,
        "final_stop_ranking_produced": False,
        "final_network_selected": False,
        "headway_modified": False,
        "timetable_modified": False,
        "budget_modified": False,
        "random_used": False,
        "legacy_synthetic_population_used": False,
        "building_resident_estimates_observed": False,
        "building_resident_estimate_status": "MODEL_OUTPUT_DASYMETRIC_BUILDING_POPULATION",
        "limitations": [
            "ISTAT 2023 section counts are rescaled within municipality to POSAS 2025 totals; derived 2025 section targets are not observed 2025 section counts.",
            "Fictitious ISTAT sections 888888x/999999x remain nonspatial residuals and are never placed into buildings.",
            "Sections with population but no plausible residential/fallback building remain unallocated residuals rather than being forced into nonresidential structures.",
            "Mixed-use DBGT records have no observed residential floor-area share; full available area/volume is an allocation proxy with an explicit uncertainty flag.",
            "Gate B walking graph covers the five-core audit universe; V2 catchment comparison is therefore computed for the five core municipalities only.",
            "WorldPop cell comparison assigns V2 building totals by representative point for diagnostic comparison only and is not the population allocation method.",
        ],
    }
    if validation["core_posas_2025_total"] != 22914.0:
        raise RuntimeError("core POSAS total changed from Gate B lineage")
    if not validation["all_selected_municipalities_reconcile_exactly"]:
        raise RuntimeError("selected municipalities failed exact calibration")
    (args.output_dir / "building_population_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    checksums = write_checksums(args.output_dir)
    validation["checksums_file_sha256"] = sha256_file(checksums)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


section_targets_global = pd.DataFrame()

if __name__ == "__main__":
    main()
