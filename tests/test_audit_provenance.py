import os
import hashlib
import pytest
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def test_manifest_integrity():
    manifest_path = "data/manifest.csv"
    assert os.path.exists(manifest_path), "data/manifest.csv deve esistere"
    df = pd.read_csv(manifest_path)
    assert len(df) >= 15, f"Attesi almeno 15 dataset nel manifest, trovati {len(df)}"
    
    # Verifica che per ogni record locale il file esista e il checksum coincida
    for _, row in df.iterrows():
        path = row["filepath_locale"]
        if os.path.exists(path):
            actual_sha = compute_sha256(path)
            assert actual_sha == row["sha256_hash"], f"Checksum mismatch su {path}: calcolato {actual_sha} != dichiarato {row['sha256_hash']}"

def test_manifest_urls_and_licenses():
    manifest_path = "data/manifest.csv"
    df = pd.read_csv(manifest_path)
    for _, row in df.iterrows():
        url = str(row["url_ufficiale"])
        assert url.startswith("https://") or "download.geofabrik.de" in url, f"URL non valido per {row['dataset_id']}: {url}"
        
        # Blocker A2 check: WorldPop deve essere serie Global_2000_2020 100m, non 1km
        if "worldpop" in row["dataset_id"]:
            assert "1km" not in url, f"URL WorldPop contiene erroneamente 1km: {url}"
            assert "Global_2000_2020" in url, f"URL WorldPop non appartiene alla serie ufficiale 100m Global_2000_2020: {url}"
            
        # Warning A6 check: Copernicus DEM non deve essere 'Public Domain'
        if "copernicus" in row["dataset_id"]:
            assert "Public Domain" not in str(row["licenza"]), "Licenza Copernicus DEM non può essere etichettata genericamente come Public Domain"
            assert "Copernicus" in str(row["licenza"])

def test_istat_boundaries():
    geojson_path = "data/raw/boundaries/comuni_core_istat_2026.geojson"
    assert os.path.exists(geojson_path)
    gdf = gpd.read_file(geojson_path)
    assert len(gdf) == 5, f"Attesi 5 comuni core ISTAT, trovati {len(gdf)}"
    codes = set(gdf["PRO_COM_T"])
    expected_codes = {"097010", "097012", "097058", "097074", "097092"}
    assert codes == expected_codes, f"Codici non coincidenti: {codes} vs {expected_codes}"

def test_worldpop_real_raster():
    tif_path = "data/raw/worldpop/worldpop_core_unadj_raw.tif"
    assert os.path.exists(tif_path)
    with rasterio.open(tif_path) as src:
        assert src.crs.to_epsg() == 4326
        # Risoluzione angolare deve essere 3 arc-second (~0.000833 deg), tipica del raster 100m
        assert abs(src.res[0] - 0.0008333333) < 1e-6, f"Risoluzione angolare inattesa: {src.res[0]}"
        # Risoluzione al suolo a lat 45.7N: ~65m lon x ~93m lat (~100m nominale)
        res_lat_m = src.res[1] * 111139
        res_lon_m = src.res[0] * 111139 * np.cos(np.radians(45.73))
        assert 50 < res_lon_m < 80, f"Risoluzione lon al suolo inattesa: {res_lon_m}"
        assert 80 < res_lat_m < 110, f"Risoluzione lat al suolo inattesa: {res_lat_m}"
        
        data = src.read(1)
        valid = data[data > 0]
        assert len(valid) > 1000, f"Troppe poche celle WorldPop: {len(valid)}"
        assert 15000 < valid.sum() < 35000, f"Popolazione grezza inattesa: {valid.sum()}"

def test_copernicus_dem_raster():
    dem_path = "data/raw/dem/copernicus_dem_core_raw.tif"
    assert os.path.exists(dem_path)
    with rasterio.open(dem_path) as src:
        data = src.read(1)
        valid = data[data > -9999]
        assert valid.max() > 400.0, "Altitudine massima deve superare 400m per le colline della Brianza"
        assert valid.min() >= 0.0, "Altitudine minima non deve essere negativa"

def test_istat_od_matrix():
    od_path = "data/raw/od/matrice_pendolarismo_istat_2011_core.csv"
    assert os.path.exists(od_path)
    df = pd.read_csv(od_path)
    assert len(df) > 500, f"Attesi oltre 500 flussi OD reali, trovati {len(df)}"
    assert df["flusso_pendolari"].sum() > 5000, "Somma pendolari reale deve essere significativa"

def test_trenord_gtfs():
    stops_file = "data/raw/gtfs/rail_trenord/stops.txt"
    assert os.path.exists(stops_file)
    df = pd.read_csv(stops_file)
    olg = df[df["stop_id"] == "S01514"]
    assert len(olg) == 1, "Stazione S01514 Olgiate-Calco-Brivio deve essere presente nel GTFS Trenord"

def test_agency_bus_gtfs():
    """Verifica la presenza e la corretta articolazione dei feed GTFS dell'Agenzia TPL (Arriva e Linee Lecco)."""
    arriva_dir = "data/raw/gtfs/agency_arriva"
    assert os.path.exists(os.path.join(arriva_dir, "routes.txt")), "routes.txt di Arriva deve esistere"
    assert os.path.exists(os.path.join(arriva_dir, "stops.txt")), "stops.txt di Arriva deve esistere"
    
    df_routes = pd.read_csv(os.path.join(arriva_dir, "routes.txt"))
    short_names = set(df_routes["route_short_name"].dropna())
    for req_route in ["D184", "D185", "D150", "D170"]:
        assert req_route in short_names, f"Linea {req_route} mancante nel GTFS ufficiale Arriva"
        
    df_stops = pd.read_csv(os.path.join(arriva_dir, "stops.txt"))
    assert len(df_stops) > 100, "Numero fermate Arriva insufficiente"
    assert "stop_lat" in df_stops.columns and "stop_lon" in df_stops.columns

    lineelecco_dir = "data/raw/gtfs/agency_lineelecco"
    assert os.path.exists(os.path.join(lineelecco_dir, "routes.txt")), "routes.txt di Linee Lecco deve esistere"

def test_osm_layers():
    hw_path = "data/raw/osm/osm_highways_core.geojson"
    pt_path = "data/raw/osm/osm_points_core.geojson"
    assert os.path.exists(hw_path)
    assert os.path.exists(pt_path)
    gdf_hw = gpd.read_file(hw_path)
    gdf_pt = gpd.read_file(pt_path)
    assert len(gdf_hw) > 1000, f"Grafo stradale insufficiente: {len(gdf_hw)}"
    assert len(gdf_pt) > 500, f"Punti OSM insufficienti: {len(gdf_pt)}"

def test_synthetic_invalidation_notice():
    archive_readme = "data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md"
    assert os.path.exists(archive_readme)
    with open(archive_readme, "r", encoding="utf-8") as f:
        text = f.read()
    assert "INVALIDATED BY EXTERNAL AUDIT" in text
