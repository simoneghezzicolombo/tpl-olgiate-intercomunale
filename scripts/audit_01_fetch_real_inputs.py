#!/usr/bin/env python3
"""
audit_01_fetch_real_inputs.py

Gate A provenance pipeline for the Olgiate intermunicipal TPL project.
Only real, traceable sources are admitted. Synthetic legacy artifacts are quarantined.

Primary sources:
1. ISTAT administrative boundaries 2026
2. WorldPop 2020 100 m
3. Copernicus DEM GLO-30
4. ISTAT commuting matrix 2011
5. Trenord GTFS
6. Agenzia TPL Como-Lecco-Varese GTFS
7. OpenStreetMap via Overpass
8. ISTAT POSAS 2025
9. Regione Lombardia SFR station counts 2015-2025
10. Programma di Bacino Como-Lecco-Varese rev. 7.2
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import rasterio.mask
import requests

BBOX_CORE = {"south": 45.710, "north": 45.760, "west": 9.355, "east": 9.460}
MANIFEST_ROWS: list[dict] = []
HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; tpl-olgiate-research/1.0; "
        "+https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"
    )
}

ISTAT_BOUNDARIES_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    "non_generalizzati/2026/Limiti01012026.zip"
)
ISTAT_OD_URL = (
    "https://www.istat.it/storage/cartografia/matrici_pendolarismo/"
    "matrici_pendolarismo_2011.zip"
)
WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2000_2020/"
    "2020/ITA/ita_ppp_2020_UNadj.tif"
)
COPERNICUS_DEM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_N45_00_E009_00_DEM/"
    "Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif"
)
TRENORD_GTFS_DOWNLOAD = "https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip"
TRENORD_GTFS_PERMALINK = (
    "https://dati.lombardia.it/Mobilit-e-trasporti/"
    "Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9"
)
AGENCY_ARRIVA_GTFS = (
    "https://www.tplcomoleccovarese.it/atpcolc/images/"
    "File%20GTFS%20inv.%202025-2026/"
    "GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip"
)
AGENCY_LECCO_GTFS = (
    "https://www.tplcomoleccovarese.it/atpcolc/images/"
    "File%20GTFS%20inv.%202025-2026/"
    "GTFS%20invernale%202025-2026%20Linee%20Lecco.zip"
)
POSAS_PAGE = "https://demo.istat.it/app/?l=it&a=2025&i=POS"
POSAS_ALL_COMUNI_ZIP = "https://demo.istat.it/data/posas/POSAS_2025_it_Comuni.zip"

SFR_STORY = "https://dati.lombardia.it/stories/s/SFR-dati-di-frequentazione/52uy-dgwp/"
SFR_HIST_UID = "m2u2-frtq"
SFR_RECENT_UID = "ut63-s688"
SFR_HIST_CSV = f"https://www.dati.lombardia.it/resource/{SFR_HIST_UID}.csv?$limit=5000000"
SFR_RECENT_CSV = f"https://www.dati.lombardia.it/resource/{SFR_RECENT_UID}.csv?$limit=5000000"

PDB_MAIN_URL = (
    "https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/"
    "Rev7.2/programma%20di%20bacino%20del%20trasporto%20pubblico%20locale"
    "%20-%20v7.2_def.pdf"
)
PDB_MERATESE_URL = (
    "https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/"
    "Rev7.2/Allegato3.4_PdB_SchedaAmbito_Meratese.pdf"
)

# Public global Overpass instances currently listed by the OpenStreetMap Wiki.
# private.coffee is the successor of the former kumi.systems instance.
OVERPASS_URL = "https://overpass.private.coffee/api/interpreter"
OVERPASS_FALLBACKS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

CORE_CODES = {"097010", "097012", "097058", "097074", "097092"}

S8_DISPLAY = {
    "MILANOPORTAGARIBALDI": "MILANO PORTA GARIBALDI",
    "MILANOGRECOPIRELLI": "MILANO GRECO PIRELLI",
    "MONZA": "MONZA",
    "ARCORE": "ARCORE",
    "CARNATEUSMATE": "CARNATE USMATE",
    "OSNAGO": "OSNAGO",
    "CERNUSCOMERATE": "CERNUSCO-MERATE",
    "OLGIATECALCOBRIVIO": "OLGIATE-CALCO-BRIVIO",
    "AIRUNO": "AIRUNO",
    "CALOLZIOCORTEOLGINATE": "CALOLZIOCORTE-OLGINATE",
    "LECCO": "LECCO",
}


def compute_sha256(filepath: str | Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file_if_missing(
    url: str,
    target_path: str | Path,
    *,
    timeout: int = 120,
    fallback_local: str | Path | None = None,
) -> str:
    target = Path(target_path)
    if target.exists() and target.stat().st_size > 0:
        return str(target)

    if fallback_local:
        fallback = Path(fallback_local)
        if fallback.exists() and fallback.stat().st_size > 0:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fallback, target)
            return str(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[download] {url} -> {target}")
    with requests.get(url, headers=HEADERS_HTTP, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with target.open("wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    if not target.exists() or target.stat().st_size == 0:
        raise IOError(f"Download produced no data: {target}")
    return str(target)


def record_manifest(
    dataset_id: str,
    ente: str,
    url: str,
    anno: str,
    licenza: str,
    filepath: str | Path,
    *,
    trasformazioni: str = "Nessuna (fonte primaria grezza)",
    stato_epistemico: str = "FACT",
    note: str = "",
) -> None:
    path = Path(filepath)
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Active manifest input {dataset_id} is missing or empty: {path}"
        )
    MANIFEST_ROWS.append(
        {
            "dataset_id": dataset_id,
            "ente_fonte": ente,
            "url_ufficiale": url,
            "data_accesso": "2026-09-03",
            "anno_riferimento": anno,
            "licenza": licenza,
            "filepath_locale": path.as_posix(),
            "sha256_hash": compute_sha256(path),
            "dimensione_bytes": path.stat().st_size,
            "stato_epistemico": stato_epistemico,
            "trasformazioni": trasformazioni,
            "note_provenance": note,
        }
    )


def step_1_istat_boundaries() -> gpd.GeoDataFrame:
    print("\n--- STEP 1: ISTAT boundaries 2026 ---")
    out_dir = Path("data/raw/boundaries")
    zip_path = out_dir / "Limiti01012026.zip"
    geojson_out = out_dir / "comuni_core_istat_2026.geojson"
    download_file_if_missing(ISTAT_BOUNDARIES_URL, zip_path)

    if not geojson_out.exists():
        with zipfile.ZipFile(zip_path) as z:
            members = [m for m in z.namelist() if m.startswith("Com01012026/")]
            z.extractall(out_dir, members)
        shp_path = out_dir / "Com01012026" / "Com01012026_WGS84.shp"
        gdf = gpd.read_file(shp_path)
        core = gdf[gdf["PRO_COM_T"].astype(str).isin(CORE_CODES)].copy().to_crs(4326)
        if len(core) != 5:
            raise ValueError(f"Expected 5 core municipalities, got {len(core)}")
        core.to_file(geojson_out, driver="GeoJSON")
        core.to_file(out_dir / "comuni_core_istat_2026.shp")
        shutil.rmtree(out_dir / "Com01012026", ignore_errors=True)
    core = gpd.read_file(geojson_out)

    record_manifest(
        "istat_limiti_comunali_2026",
        "ISTAT",
        ISTAT_BOUNDARIES_URL,
        "2026",
        "CC BY 3.0 IT",
        geojson_out,
        trasformazioni=(
            "Filtro deterministico sui codici PRO_COM_T dei 5 comuni core; "
            "esportazione WGS84 EPSG:4326"
        ),
        stato_epistemico="FACT",
    )
    return core


def step_2_worldpop_raster(boundaries: gpd.GeoDataFrame) -> None:
    print("\n--- STEP 2: WorldPop 2020 100 m ---")
    out_dir = Path("data/raw/worldpop")
    raw = out_dir / "ita_ppp_2020_UNadj.tif"
    clipped = out_dir / "worldpop_core_unadj_raw.tif"
    download_file_if_missing(WORLDPOP_URL, raw)

    if not clipped.exists():
        with rasterio.open(raw) as src:
            image, transform = rasterio.mask.mask(src, boundaries.geometry, crop=True)
            meta = src.meta.copy()
            meta.update(
                driver="GTiff",
                height=image.shape[1],
                width=image.shape[2],
                transform=transform,
            )
            with rasterio.open(clipped, "w", **meta) as dest:
                dest.write(image)

    record_manifest(
        "worldpop_ita_2020_unadj_national",
        "WorldPop (University of Southampton)",
        WORLDPOP_URL,
        "2020",
        "CC BY 4.0",
        raw,
        note="National 100 m unconstrained UN-adjusted raster; nominal 3 arc-second grid.",
    )
    record_manifest(
        "worldpop_core_unadj_clipped",
        "WorldPop / ISTAT boundaries",
        WORLDPOP_URL,
        "2020",
        "CC BY 4.0",
        clipped,
        trasformazioni="rasterio.mask clip on the five official ISTAT municipal polygons",
        stato_epistemico="DERIVED",
    )


def step_3_copernicus_dem(boundaries: gpd.GeoDataFrame) -> None:
    print("\n--- STEP 3: Copernicus DEM GLO-30 ---")
    out_dir = Path("data/raw/dem")
    raw = out_dir / "Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif"
    clipped = out_dir / "copernicus_dem_core_raw.tif"
    download_file_if_missing(COPERNICUS_DEM_URL, raw)

    if not clipped.exists():
        with rasterio.open(raw) as src:
            image, transform = rasterio.mask.mask(src, boundaries.geometry, crop=True)
            meta = src.meta.copy()
            meta.update(
                driver="GTiff",
                height=image.shape[1],
                width=image.shape[2],
                transform=transform,
            )
            with rasterio.open(clipped, "w", **meta) as dest:
                dest.write(image)

    licence = (
        "Copernicus DEM Licence; attribution: Produced using Copernicus WorldDEM-30 "
        "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPE-GSP-EOPG-TN-15-0005"
    )
    record_manifest(
        "copernicus_dem_glo30_tile_n45_e009",
        "Copernicus / ESA",
        COPERNICUS_DEM_URL,
        "2021",
        licence,
        raw,
    )
    record_manifest(
        "copernicus_dem_core_clipped",
        "Copernicus / ISTAT boundaries",
        COPERNICUS_DEM_URL,
        "2021",
        licence,
        clipped,
        trasformazioni="rasterio.mask clip on the five official ISTAT municipal polygons",
        stato_epistemico="DERIVED",
    )


def step_4_istat_commuting_matrix() -> None:
    print("\n--- STEP 4: ISTAT commuting matrix 2011 ---")
    out_dir = Path("data/raw/od")
    zip_path = out_dir / "matrici_pendolarismo_2011.zip"
    out_csv = out_dir / "matrice_pendolarismo_istat_2011_core.csv"
    download_file_if_missing(ISTAT_OD_URL, zip_path)

    if not out_csv.exists():
        names = {
            "010": "Brivio",
            "012": "Calco",
            "058": "Olgiate Molgora",
            "074": "Santa Maria Hoè",
            "067": "Perego",
            "072": "Rovagnate",
        }
        rows = []
        with zipfile.ZipFile(zip_path) as z:
            member = "MATRICE PENDOLARISMO 2011/matrix_pendo2011_10112014.txt"
            with z.open(member) as f:
                for raw_line in f:
                    line = raw_line.decode("latin-1")
                    if not line or line[0] != "S":
                        continue
                    prov_o, com_o = line[4:7], line[8:11]
                    prov_d, com_d = line[18:21], line[22:25]
                    if not (
                        (prov_o == "097" and com_o in names)
                        or (prov_d == "097" and com_d in names)
                    ):
                        continue
                    rows.append(
                        {
                            "prov_orig": prov_o,
                            "com_orig": com_o,
                            "comune_orig": names.get(com_o, f"Prov_{prov_o}_Com_{com_o}"),
                            "prov_dest": prov_d,
                            "com_dest": com_d,
                            "comune_dest": names.get(com_d, f"Prov_{prov_d}_Com_{com_d}"),
                            "sesso": "M" if line[12] == "1" else "F",
                            "motivo": "Studio" if line[14] == "1" else "Lavoro",
                            "tipo_luogo": line[16],
                            "flusso_pendolari": float(line[40:50].strip()),
                        }
                    )
        pd.DataFrame(rows).to_csv(out_csv, index=False)

    record_manifest(
        "istat_matrice_pendolarismo_2011_core",
        "ISTAT (15° Censimento Generale Popolazione)",
        ISTAT_OD_URL,
        "2011",
        "IODL 2.0",
        out_csv,
        trasformazioni=(
            "Estrazione dei record S con origine o destinazione nei comuni core "
            "dal tracciato fisso censuario 2011"
        ),
        stato_epistemico="FACT",
    )


def _extract_gtfs(zip_path: Path, out_dir: Path) -> None:
    required = ["routes.txt", "stops.txt", "trips.txt", "stop_times.txt"]
    if not all((out_dir / name).exists() for name in required):
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(out_dir)


def step_5_trenord_gtfs() -> None:
    print("\n--- STEP 5: Trenord GTFS ---")
    out_dir = Path("data/raw/gtfs/rail_trenord")
    zip_path = out_dir / "trenord_gtfs.zip"
    download_file_if_missing(TRENORD_GTFS_DOWNLOAD, zip_path)
    _extract_gtfs(zip_path, out_dir)
    record_manifest(
        "trenord_gtfs_ufficiale_lombardia",
        "Regione Lombardia / Trenord",
        TRENORD_GTFS_PERMALINK,
        "2026",
        "CC BY 4.0",
        zip_path,
        trasformazioni="Download official GTFS and extraction of published tables",
    )


def step_6_agency_gtfs() -> None:
    print("\n--- STEP 6: Agenzia TPL GTFS ---")
    specs = [
        (
            "gtfs_arriva_addabus_inv_2025_2026",
            "Agenzia TPL Como-Lecco-Varese / Arriva Italia",
            AGENCY_ARRIVA_GTFS,
            Path("data/raw/gtfs/agency_arriva"),
            "GTFS_invernale_2025-2026_-_Arriva_Italia_e_Addabus.zip",
        ),
        (
            "gtfs_lineelecco_inv_2025_2026",
            "Agenzia TPL Como-Lecco-Varese / Linee Lecco",
            AGENCY_LECCO_GTFS,
            Path("data/raw/gtfs/agency_lineelecco"),
            "GTFS_invernale_2025-2026_Linee_Lecco.zip",
        ),
    ]
    for dataset_id, ente, url, out_dir, filename in specs:
        zip_path = out_dir / filename
        download_file_if_missing(url, zip_path)
        _extract_gtfs(zip_path, out_dir)
        record_manifest(
            dataset_id,
            ente,
            url,
            "2025-2026",
            "licenza non specificata / accesso pubblico",
            zip_path,
            trasformazioni="Download feed GTFS ufficiale ed estrazione tabelle",
        )

    routes = pd.read_csv("data/raw/gtfs/agency_arriva/routes.txt")
    found = set(routes["route_short_name"].dropna().astype(str))
    missing = {"D184", "D185", "D150", "D170"} - found
    if missing:
        raise AssertionError(f"Core routes missing in official Arriva GTFS: {sorted(missing)}")


def fetch_osm_xml(
    bbox: tuple[float, float, float, float],
    out_path: str,
    overpass_url: str = OVERPASS_URL,
    timeout: int = 90,
) -> str:
    """Fetch raw OSM XML into an arbitrary clean output path."""
    south, west, north, east = bbox
    query = (
        f"[out:xml][timeout:{timeout}];\n"
        "(\n"
        f'  way["highway"]({south},{west},{north},{east});\n'
        f'  node["highway"="bus_stop"]({south},{west},{north},{east});\n'
        f'  node["public_transport"]({south},{west},{north},{east});\n'
        f'  node["amenity"]({south},{west},{north},{east});\n'
        f'  node["shop"]({south},{west},{north},{east});\n'
        f'  node["leisure"]({south},{west},{north},{east});\n'
        ");\n"
        "(._;>;);\n"
        "out meta;"
    )
    endpoints = [overpass_url] + [x for x in OVERPASS_FALLBACKS if x != overpass_url]
    last_exc: Exception | None = None
    response = None
    for endpoint in endpoints:
        try:
            r = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS_HTTP,
                # Fail over quickly when a public mirror blocks cloud ranges.
                timeout=(10, min(timeout, 45)),
            )
            if r.status_code in (406, 429, 503, 504):
                last_exc = requests.HTTPError(
                    f"{r.status_code} from {endpoint}", response=r
                )
                continue
            r.raise_for_status()
            response = r
            break
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last_exc = exc
    if response is None:
        raise last_exc or requests.HTTPError("All Overpass endpoints failed")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    if out.stat().st_size < 200:
        raise IOError(f"OSM response unexpectedly small: {out.stat().st_size} bytes")
    return str(out)


def _fetch_overpass_json(query: str, out_path: Path, timeout: int = 60) -> None:
    if out_path.exists() and out_path.stat().st_size > 0:
        return
    last_exc = None
    for endpoint in [OVERPASS_URL, *OVERPASS_FALLBACKS]:
        try:
            r = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS_HTTP,
                timeout=(10, min(timeout, 45)),
            )
            r.raise_for_status()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(r.text, encoding="utf-8")
            return
        except (requests.RequestException, OSError) as exc:
            last_exc = exc
    raise last_exc or RuntimeError("Overpass JSON acquisition failed")


def step_7_osm_real_data(boundaries: gpd.GeoDataFrame) -> None:
    print("\n--- STEP 7: OpenStreetMap / Overpass ---")
    out_dir = Path("data/raw/osm")
    raw = out_dir / "osm_core_bbox.osm"
    lines_file = out_dir / "osm_highways_core.geojson"
    points_file = out_dir / "osm_points_core.geojson"
    stops_file = out_dir / "osm_bus_stops_core.json"
    pois_file = out_dir / "osm_pois_core.json"
    bbox_meta_file = out_dir / "osm_core_bbox.meta.json"

    # Gate B spatial-integrity prerequisite: derive the acquisition extent from the
    # full official municipal geometry rather than from a hand-written bbox. A
    # small buffer preserves road-network continuity just outside administrative
    # borders. This matters especially for northern Brivio, which extended beyond
    # the earlier 45.760 N cutoff.
    minx, miny, maxx, maxy = boundaries.to_crs(4326).total_bounds
    bbox_pad_deg = 0.002
    bbox = (
        float(miny - bbox_pad_deg),
        float(minx - bbox_pad_deg),
        float(maxy + bbox_pad_deg),
        float(maxx + bbox_pad_deg),
    )
    bbox_meta = {
        "bbox_south_west_north_east": [round(x, 8) for x in bbox],
        "derived_from": "ISTAT 2026 five-core-municipality total_bounds + 0.002 degree buffer",
    }

    cached_bbox_matches = False
    if bbox_meta_file.exists():
        try:
            cached_bbox_matches = json.loads(
                bbox_meta_file.read_text(encoding="utf-8")
            ) == bbox_meta
        except (json.JSONDecodeError, OSError):
            cached_bbox_matches = False

    if (
        not raw.exists()
        or raw.stat().st_size == 0
        or not cached_bbox_matches
    ):
        # Invalidate derivatives tied to the former/manual extent before fetching.
        for stale in (raw, lines_file, points_file, stops_file, pois_file):
            stale.unlink(missing_ok=True)
        fetch_osm_xml(bbox, str(raw))
        bbox_meta_file.write_text(
            json.dumps(bbox_meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    ogr_bbox = (bbox[1], bbox[0], bbox[3], bbox[2])
    lines = pyogrio.read_dataframe(raw, layer="lines", bbox=ogr_bbox)
    points = pyogrio.read_dataframe(raw, layer="points", bbox=ogr_bbox)
    pyogrio.write_dataframe(lines, lines_file, driver="GeoJSON")
    pyogrio.write_dataframe(points, points_file, driver="GeoJSON")

    stops_query = f"""[out:json][timeout:30];
(
 node["highway"="bus_stop"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
 node["public_transport"="platform"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out body;"""
    pois_query = f"""[out:json][timeout:30];
(
 node["amenity"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
 way["amenity"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
 node["shop"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
 node["leisure"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out center;"""
    _fetch_overpass_json(stops_query, stops_file)
    _fetch_overpass_json(pois_query, pois_file)

    raw_url = OVERPASS_URL
    record_manifest(
        "osm_core_bbox_extract",
        "OpenStreetMap contributors / Overpass",
        raw_url,
        "2026",
        "ODbL 1.0",
        raw,
        trasformazioni=(
            "Raw XML snapshot generated by fetch_osm_xml using explicit highway, "
            "public_transport, amenity, shop and leisure selectors for the core bbox"
        ),
        stato_epistemico="FACT",
        note=(
            f"Access date 2026-09-03; bbox={bbox}; extent derived from the full "
            "ISTAT core-municipality geometry with 0.002 degree buffer; raw snapshot "
            "checksum recorded here."
        ),
    )
    record_manifest(
        "osm_highways_core_geojson",
        "OpenStreetMap / pyogrio",
        raw_url,
        "2026",
        "ODbL 1.0",
        lines_file,
        trasformazioni="pyogrio lines extraction from committed/raw Overpass XML snapshot",
        stato_epistemico="DERIVED",
    )
    record_manifest(
        "osm_points_core_geojson",
        "OpenStreetMap / pyogrio",
        raw_url,
        "2026",
        "ODbL 1.0",
        points_file,
        trasformazioni="pyogrio points extraction from committed/raw Overpass XML snapshot",
        stato_epistemico="DERIVED",
    )
    record_manifest(
        "osm_bus_stops_overpass",
        "OpenStreetMap contributors / Overpass",
        raw_url,
        "2026",
        "ODbL 1.0",
        stops_file,
        trasformazioni="Overpass query for bus_stop and public_transport=platform",
        stato_epistemico="FACT_OSM_OBSERVATION",
        note="GTFS stops.txt remains the primary institutional stop source.",
    )
    record_manifest(
        "osm_pois_overpass",
        "OpenStreetMap contributors / Overpass",
        raw_url,
        "2026",
        "ODbL 1.0",
        pois_file,
        trasformazioni="Overpass query for amenity/shop/leisure demand generators",
        stato_epistemico="FACT_OSM_OBSERVATION",
    )


def fetch_posas_lecco(
    posas_file: str,
    source_url: str = POSAS_ALL_COMUNI_ZIP,
    timeout: int = 120,
) -> str:
    """Rebuild the Lecco POSAS extract from ISTAT's official 2025 Comuni ZIP."""
    print(f"[POSAS] Download official all-municipalities archive: {source_url}")
    r = requests.get(source_url, headers=HEADERS_HTTP, timeout=timeout)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        candidates = [
            n for n in z.namelist()
            if n.lower().endswith("posas_2025_it_comuni.csv")
        ]
        if not candidates:
            candidates = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(candidates) != 1:
            raise ValueError(
                f"Expected one POSAS municipalities CSV in archive, found {candidates}"
            )
        raw_text = z.read(candidates[0]).decode("utf-8-sig")

    df = pd.read_csv(
        io.StringIO(raw_text),
        sep=";",
        skiprows=1,
        dtype={"Codice comune": str},
        low_memory=False,
    )
    if "Codice comune" not in df.columns:
        raise ValueError(f"POSAS schema changed; columns={list(df.columns)}")
    codes = df["Codice comune"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    lecco = df[codes.str.startswith("097")].copy()
    lecco["Codice comune"] = codes[codes.str.startswith("097")].values
    if len(lecco) < 4000:
        raise ValueError(f"Unexpectedly few Lecco POSAS rows: {len(lecco)}")

    out = Path(posas_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    title = '"Popolazione residente per età, sesso e stato civile al 1° gennaio 2025"\n'
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        f.write(title)
        lecco.to_csv(
            f,
            sep=";",
            index=False,
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\n",
        )
    return str(out)


def step_8_istat_posas() -> None:
    print("\n--- STEP 8: ISTAT POSAS 2025 ---")
    posas_file = Path("data/raw/istat/POSAS_2025_it_097_Lecco.csv")
    if not posas_file.exists() or posas_file.stat().st_size == 0:
        fetch_posas_lecco(str(posas_file))

    df = pd.read_csv(
        posas_file,
        sep=";",
        skiprows=1,
        encoding="utf-8-sig",
        dtype={"Codice comune": str},
        low_memory=False,
    )
    codes = df["Codice comune"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    core = df[codes.isin(CORE_CODES)]
    if len(core) < 400:
        raise ValueError(f"POSAS core extraction unexpectedly small: {len(core)} rows")

    record_manifest(
        "istat_posas_2025_lecco",
        "ISTAT",
        POSAS_ALL_COMUNI_ZIP,
        "2025",
        "IODL 2.0",
        posas_file,
        trasformazioni=(
            "Deterministic province-097 extraction from ISTAT official "
            "POSAS_2025_it_Comuni.zip; fetch_posas_lecco() recreates the file "
            "without pre-existing local files or interactive acquisition"
        ),
        stato_epistemico="DERIVED",
        note=f"Official download page: {POSAS_PAGE}; five core municipality codes: {sorted(CORE_CODES)}.",
    )


def _norm_station(value: object) -> str:
    s = str(value).upper().strip()
    return re.sub(r"[^A-Z0-9]", "", s)


def _month_is_november(value: object) -> bool:
    return "nov" in str(value).lower()


def _day_is_weekday(value: object) -> bool:
    return "fer" in str(value).lower()


def _read_sfr_csv(url: str, timeout: int = 120) -> pd.DataFrame:
    r = requests.get(url, headers=HEADERS_HTTP, timeout=timeout)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), thousands=".", low_memory=False)


def fetch_sfr_from_socrata(
    sfr_file: str,
    hist_url: str = SFR_HIST_CSV,
    recent_url: str = SFR_RECENT_CSV,
) -> str:
    """Rebuild S8 2015-2025 using the two official Regione Lombardia datasets."""
    print(f"[SFR] historical 2015-2023: {hist_url}")
    hist = _read_sfr_csv(hist_url)
    print(f"[SFR] recent 2024-2025: {recent_url}")
    recent = _read_sfr_csv(recent_url)

    def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Map Socrata API field names and display labels to one stable schema."""
        aliases = {
            "campagna": "Campagna",
            "stazione": "Stazione",
            "saliti24h": "Saliti24H",
            "anno": "Anno",
            "tipogiorno": "TipoGiorno",
        }
        rename = {}
        for col in df.columns:
            key = re.sub(r"[^a-z0-9]", "", str(col).lower())
            if key in aliases:
                rename[col] = aliases[key]
        return df.rename(columns=rename)

    def prepare(
        df: pd.DataFrame,
        source_label: str,
        min_year: int,
        max_year: int,
        *,
        filter_weekday: bool,
    ) -> pd.DataFrame:
        d = canonicalize_columns(df.copy())
        required = {"Campagna", "Stazione", "Saliti24H", "Anno"}
        if filter_weekday:
            required.add("TipoGiorno")
        missing = required - set(d.columns)
        if missing:
            raise ValueError(
                f"SFR schema changed; missing {sorted(missing)}; "
                f"available={list(d.columns)}"
            )

        d["Anno"] = pd.to_numeric(d["Anno"], errors="coerce")
        d["Saliti24H"] = pd.to_numeric(d["Saliti24H"], errors="coerce")
        d["_station_key"] = d["Stazione"].map(_norm_station)
        d["Stazione_std"] = d["_station_key"].map(S8_DISPLAY)

        mask = (
            d["Stazione_std"].notna()
            & d["Anno"].between(min_year, max_year)
            & d["Campagna"].map(_month_is_november)
        )
        # Regione Lombardia documents 2015-2023 as weekday-mean only.
        # From 2024 onward the dataset distinguishes weekday/Saturday/holiday.
        if filter_weekday:
            mask &= d["TipoGiorno"].map(_day_is_weekday)

        d = d[mask].copy()
        d["Fonte_periodo"] = source_label
        return d[["Anno", "Stazione_std", "Saliti24H", "Fonte_periodo"]]

    hist_s8 = prepare(
        hist,
        "Flussi Stazioni Ferroviarie (2015-2023; m2u2-frtq)",
        2015,
        2023,
        filter_weekday=False,
    )
    recent_s8 = prepare(
        recent,
        "Frequentazione stazioni SFR (2024-2025; ut63-s688)",
        2024,
        2025,
        filter_weekday=True,
    )
    combined = pd.concat([hist_s8, recent_s8], ignore_index=True)
    combined = (
        combined.groupby(["Anno", "Stazione_std", "Fonte_periodo"], as_index=False)["Saliti24H"]
        .mean()
    )
    base = (
        combined[combined["Anno"] == 2019]
        .set_index("Stazione_std")["Saliti24H"]
        .rename("Base2019")
    )
    combined = combined.merge(base, on="Stazione_std", how="left")
    combined["Indice_2019_100"] = combined["Saliti24H"] / combined["Base2019"] * 100
    combined["Stazione"] = combined["Stazione_std"]

    olgiate_years = set(
        combined.loc[
            combined["Stazione_std"] == "OLGIATE-CALCO-BRIVIO", "Anno"
        ].astype(int)
    )
    if olgiate_years != set(range(2015, 2026)):
        raise ValueError(
            f"Olgiate SFR series is incomplete: years={sorted(olgiate_years)}"
        )

    out_cols = [
        "Anno",
        "Stazione_std",
        "Stazione",
        "Saliti24H",
        "Indice_2019_100",
        "Fonte_periodo",
    ]
    out = Path(sfr_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    combined[out_cols].sort_values(["Stazione_std", "Anno"]).to_csv(out, index=False)
    return str(out)


def step_9_sfr_station_series() -> None:
    print("\n--- STEP 9: Regione Lombardia SFR station counts 2015-2025 ---")
    sfr_file = Path("data/raw/sfr/stazioni_s8_indice_2015_2025.csv")
    if not sfr_file.exists() or sfr_file.stat().st_size == 0:
        fetch_sfr_from_socrata(str(sfr_file))

    df = pd.read_csv(sfr_file)
    olg = df[df["Stazione_std"].astype(str) == "OLGIATE-CALCO-BRIVIO"]
    years = set(pd.to_numeric(olg["Anno"], errors="coerce").dropna().astype(int))
    if years != set(range(2015, 2026)):
        raise ValueError(
            "Committed/cached SFR derivative does not contain a complete "
            f"2015-2025 Olgiate series: {sorted(years)}"
        )

    record_manifest(
        "sfr_trenord_serie_storica_2015_2025",
        "Regione Lombardia D.G. Trasporti / Trenord",
        SFR_STORY,
        "2015-2025",
        "IODL 2.0",
        sfr_file,
        trasformazioni=(
            f"DERIVED from two official Socrata datasets: {SFR_HIST_UID} "
            f"(2015-2023, {SFR_HIST_CSV}) and {SFR_RECENT_UID} "
            f"(2024-2025, {SFR_RECENT_CSV}). Filter November campaigns; "
            "2015-2023 is already weekday-mean in the official source, while from "
            "2024 TipoGiorno is filtered to weekday. Harmonize station names and "
            "Saliti24H, then compute Indice_2019_100. "
            "Rebuild function: fetch_sfr_from_socrata()."
        ),
        stato_epistemico="DERIVED",
        note=(
            "The split between historical 2015-2023 and recent 2024-2025 follows "
            "Regione Lombardia's SFR data documentation. The source change must be "
            "kept explicit when interpreting the time series."
        ),
    )


def step_10_programma_di_bacino() -> None:
    print("\n--- STEP 10: Programma di Bacino rev. 7.2 ---")
    out_dir = Path("data/raw/pdb")
    main_path = out_dir / "PdB_Como_Lecco_Varese_Relazione_v7.2.pdf"
    meratese_path = out_dir / "PdB_Allegato3.4_Meratese.pdf"
    download_file_if_missing(PDB_MAIN_URL, main_path)
    download_file_if_missing(PDB_MERATESE_URL, meratese_path)

    record_manifest(
        "pdb_como_lecco_varese_relazione_v7_2",
        "Agenzia TPL Como-Lecco-Varese",
        PDB_MAIN_URL,
        "2025",
        "Atto pubblico di pianificazione",
        main_path,
    )
    record_manifest(
        "pdb_allegato_3_4_meratese",
        "Agenzia TPL Como-Lecco-Varese",
        PDB_MERATESE_URL,
        "2025",
        "Atto pubblico di pianificazione",
        meratese_path,
    )


def step_11_archive_synthetic_legacy() -> None:
    legacy = Path("data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        "# SYNTHETIC PLACEHOLDER ARCHIVE - DO NOT USE\n\n"
        "## STATUS: INVALIDATED BY EXTERNAL AUDIT - SYNTHETIC INPUTS\n\n"
        "Legacy outputs built from manual fractions, random values, Euclidean "
        "approximations or hard-coded OD/GTFS assumptions are INVALIDATED. "
        "They are retained only for audit history and must not feed any reviewed result.\n",
        encoding="utf-8",
    )


def main() -> None:
    print("=" * 80)
    print("AUDIT CHECKPOINT 1: REAL-SOURCE PROVENANCE (GATE A)")
    print("=" * 80)
    MANIFEST_ROWS.clear()

    boundaries = step_1_istat_boundaries()
    step_2_worldpop_raster(boundaries)
    step_3_copernicus_dem(boundaries)
    step_4_istat_commuting_matrix()
    step_5_trenord_gtfs()
    step_6_agency_gtfs()
    step_7_osm_real_data(boundaries)
    step_8_istat_posas()
    step_9_sfr_station_series()
    step_10_programma_di_bacino()
    step_11_archive_synthetic_legacy()

    manifest = pd.DataFrame(MANIFEST_ROWS)
    manifest_path = Path("data/manifest.csv")
    manifest.to_csv(manifest_path, index=False)
    print(f"[OK] wrote {manifest_path} with {len(manifest)} active datasets")


if __name__ == "__main__":
    main()
