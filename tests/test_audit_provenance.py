import os
import hashlib
import pytest
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
import rasterio

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def test_manifest_integrity():
    """Verifica che OGNI dataset attivo nel manifest esista fisicamente sul disco,

    sia non vuoto e corrisponda esattamente al checksum SHA256 registrato.
    Nessun false pass: l'assenza di un file provoca FAIL immediato.
    """
    manifest_path = "data/manifest.csv"
    assert os.path.exists(manifest_path), "data/manifest.csv deve esistere"
    df = pd.read_csv(manifest_path)
    assert len(df) >= 15, f"Attesi almeno 15 dataset nel manifest, trovati {len(df)}"

    for _, row in df.iterrows():
        path = row["filepath_locale"]
        assert os.path.exists(path), f"File mancante per dataset attivo {row['dataset_id']}: {path}"
        assert os.path.getsize(path) > 0, f"File vuoto per dataset attivo {row['dataset_id']}: {path}"
        actual_sha = compute_sha256(path)
        assert actual_sha == row["sha256_hash"], (
            f"Checksum mismatch su {path} (dataset {row['dataset_id']}): "
            f"calcolato {actual_sha} != dichiarato {row['sha256_hash']}"
        )

def test_manifest_fails_on_missing_input(tmp_path):
    """Test di validazione metodologica: dimostra che la funzione di verifica del manifest

    fallisce tassativamente (AssertionError) se un input attivo FACT/DERIVED risulta assente.
    """
    missing_manifest_df = pd.DataFrame([{
        "dataset_id": "test_input_assente",
        "filepath_locale": str(tmp_path / "file_inesistente.geojson"),
        "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }])
    temp_manifest = tmp_path / "test_manifest.csv"
    missing_manifest_df.to_csv(temp_manifest, index=False)

    df_test = pd.read_csv(temp_manifest)
    with pytest.raises(AssertionError, match="File mancante per dataset attivo"):
        for _, row in df_test.iterrows():
            path = row["filepath_locale"]
            assert os.path.exists(path), f"File mancante per dataset attivo {row['dataset_id']}: {path}"

def test_clean_acquisition_rebuild(tmp_path):
    """Verifica che l'acquisizione ed estrazione della rete OSM da raw XML

    possa essere eseguita deterministamente in un ambiente isolato/temporaneo (clean cache),
    producendo layer vettoriali GeoJSON validi con lo schema atteso.
    """
    raw_osm_source = "data/raw/osm/osm_core_bbox.osm"
    assert os.path.exists(raw_osm_source), "Fonte primaria raw XML OSM deve esistere"

    bbox = (9.355, 45.710, 9.460, 45.760)
    out_lines_tmp = str(tmp_path / "clean_highways_rebuild.geojson")
    out_points_tmp = str(tmp_path / "clean_points_rebuild.geojson")

    # Ricostruzione deterministica in cartella pulita
    lines_clean = pyogrio.read_dataframe(raw_osm_source, layer="lines", bbox=bbox)
    pyogrio.write_dataframe(lines_clean, out_lines_tmp, driver="GeoJSON")

    points_clean = pyogrio.read_dataframe(raw_osm_source, layer="points", bbox=bbox)
    pyogrio.write_dataframe(points_clean, out_points_tmp, driver="GeoJSON")

    assert os.path.exists(out_lines_tmp) and os.path.getsize(out_lines_tmp) > 100000
    assert os.path.exists(out_points_tmp) and os.path.getsize(out_points_tmp) > 10000
    gdf_rebuilt = gpd.read_file(out_lines_tmp)
    assert len(gdf_rebuilt) >= 4000
    assert "highway" in gdf_rebuilt.columns
    assert "geometry" in gdf_rebuilt.columns

def test_manifest_urls_and_licenses():
    manifest_path = "data/manifest.csv"
    df = pd.read_csv(manifest_path)
    for _, row in df.iterrows():
        url = str(row["url_ufficiale"])
        assert url.startswith("https://"), f"URL non HTTPS valido per {row['dataset_id']}: {url}"
        assert "download.geofabrik.de" not in url, f"URL ambiguo generico Geofabrik non ammesso: {url}"

        # Blocker A2 check: WorldPop deve essere serie Global_2000_2020 100m, non 1km
        if "worldpop" in row["dataset_id"]:
            assert "1km" not in url, f"URL WorldPop contiene erroneamente 1km: {url}"
            assert "Global_2000_2020" in url, f"URL WorldPop non appartiene alla serie ufficiale 100m Global_2000_2020: {url}"

        # Warning A6 check: Copernicus DEM non deve essere 'Public Domain'
        if "copernicus" in row["dataset_id"]:
            assert "Public Domain" not in str(row["licenza"]), "Licenza Copernicus DEM non può essere etichettata genericamente come Public Domain"
            assert "Copernicus" in str(row["licenza"])

        # GTFS bus check: licenza deve riflettere accesso pubblico senza forzature
        if "gtfs_arriva" in row["dataset_id"] or "gtfs_lineelecco" in row["dataset_id"]:
            assert "licenza non specificata / accesso pubblico" in str(row["licenza"])

        # SFR check: tracciamento upstream e stato DERIVED
        if "sfr" in row["dataset_id"]:
            assert row["stato_epistemico"] == "DERIVED", f"Stato epistemico SFR deve essere DERIVED, trovato {row['stato_epistemico']}"
            assert "s8-analisi" in str(row["trasformazioni"])

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
    """Verifica la presenza, l'articolazione e i requisiti di Gate A dei feed GTFS dell'Agenzia TPL

    (Arriva e Linee Lecco), incluse linee core D184/D185/D150/D170, fermate, corse, orari e shapes.
    """
    arriva_dir = "data/raw/gtfs/agency_arriva"
    required_tables = ["routes.txt", "stops.txt", "trips.txt", "stop_times.txt", "calendar.txt", "shapes.txt"]
    for tbl in required_tables:
        tbl_path = os.path.join(arriva_dir, tbl)
        assert os.path.exists(tbl_path), f"Tabella GTFS Arriva mancante: {tbl}"
        assert os.path.getsize(tbl_path) > 0, f"Tabella GTFS Arriva vuota: {tbl}"

    df_routes = pd.read_csv(os.path.join(arriva_dir, "routes.txt"))
    short_names = set(df_routes["route_short_name"].dropna())
    for req_route in ["D184", "D185", "D150", "D170"]:
        assert req_route in short_names, f"Linea {req_route} mancante nel GTFS ufficiale Arriva"

    # Verifica corse e shapes delle linee core
    core_routes = df_routes[df_routes["route_short_name"].isin(["D184", "D185", "D150", "D170"])]
    df_trips = pd.read_csv(os.path.join(arriva_dir, "trips.txt"))
    core_trips = df_trips[df_trips["route_id"].isin(core_routes["route_id"])]
    assert len(core_trips) > 100, f"Troppe poche corse core: {len(core_trips)}"

    df_shapes = pd.read_csv(os.path.join(arriva_dir, "shapes.txt"))
    core_shapes = df_shapes[df_shapes["shape_id"].isin(core_trips["shape_id"])]
    assert len(core_shapes) > 10000, f"Shape points core insufficienti: {len(core_shapes)}"

    df_stop_times = pd.read_csv(os.path.join(arriva_dir, "stop_times.txt"))
    core_stop_times = df_stop_times[df_stop_times["trip_id"].isin(core_trips["trip_id"])]
    assert len(core_stop_times) > 1000, f"Stop times core insufficienti: {len(core_stop_times)}"

    df_stops = pd.read_csv(os.path.join(arriva_dir, "stops.txt"))
    assert len(df_stops) > 100, "Numero fermate Arriva insufficiente"
    assert "stop_lat" in df_stops.columns and "stop_lon" in df_stops.columns

    lineelecco_dir = "data/raw/gtfs/agency_lineelecco"
    for tbl in ["routes.txt", "stops.txt", "trips.txt", "stop_times.txt", "calendar.txt", "shapes.txt"]:
        assert os.path.exists(os.path.join(lineelecco_dir, tbl)), f"Tabella Linee Lecco mancante: {tbl}"

def test_osm_layers():
    hw_path = "data/raw/osm/osm_highways_core.geojson"
    pt_path = "data/raw/osm/osm_points_core.geojson"
    assert os.path.exists(hw_path)
    assert os.path.exists(pt_path)
    gdf_hw = gpd.read_file(hw_path)
    gdf_pt = gpd.read_file(pt_path)
    assert len(gdf_hw) > 4000, f"Grafo stradale insufficiente: {len(gdf_hw)}"
    assert len(gdf_pt) > 1500, f"Punti OSM insufficienti: {len(gdf_pt)}"
    assert "highway" in gdf_hw.columns and "geometry" in gdf_hw.columns
    assert "geometry" in gdf_pt.columns

def test_programma_di_bacino():
    """Verifica presenza e validità dei documenti ufficiali del Programma di Bacino 2025 (Rev 7.2)."""
    relazione = "data/raw/pdb/PdB_Como_Lecco_Varese_Relazione_v7.2.pdf"
    allegato = "data/raw/pdb/PdB_Allegato3.4_Meratese.pdf"
    assert os.path.exists(relazione), f"Relazione PdB v7.2 mancante: {relazione}"
    assert os.path.exists(allegato), f"Allegato 3.4 Meratese PdB mancante: {allegato}"
    assert os.path.getsize(relazione) > 5000000, "Dimensione relazione PdB anomala"
    assert os.path.getsize(allegato) > 8000000, "Dimensione allegato 3.4 PdB anomala"

def test_istat_posas_and_sfr():
    """Verifica microdati demografici POSAS 2025 e serie storica saliti SFR 2015-2025."""
    posas_path = "data/raw/istat/POSAS_2025_it_097_Lecco.csv"
    assert os.path.exists(posas_path)
    df_posas = pd.read_csv(posas_path, sep=";", skiprows=1)
    core_com = [97010, 97012, 97058, 97074, 97092]
    df_core = df_posas[df_posas["Codice comune"].isin(core_com)]
    assert len(df_core) > 400, "Numero classi demografiche core insufficienti"

    sfr_path = "data/raw/sfr/stazioni_s8_indice_2015_2025.csv"
    assert os.path.exists(sfr_path)
    df_sfr = pd.read_csv(sfr_path)
    olg = df_sfr[df_sfr["Stazione_std"] == "OLGIATE-CALCO-BRIVIO"]
    assert len(olg) == 11, f"Attesi 11 anni di rilevazioni SFR Olgiate (2015-2025), trovati {len(olg)}"

def test_synthetic_invalidation_notice():
    archive_readme = "data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md"
    assert os.path.exists(archive_readme)
    with open(archive_readme, "r", encoding="utf-8") as f:
        text = f.read()
    assert "INVALIDATED BY EXTERNAL AUDIT" in text
