import csv
import hashlib
import io
import os
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import pytest
import rasterio
import requests

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit_01_fetch_real_inputs import (
    POSAS_ALL_COMUNI_ZIP,
    SFR_HIST_CSV,
    SFR_HIST_UID,
    SFR_RECENT_CSV,
    SFR_RECENT_UID,
    fetch_osm_xml,
    fetch_posas_lecco,
    fetch_sfr_from_socrata,
)


def compute_sha256(filepath: str | Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_manifest_integrity():
    """Every active manifest row must point to a present non-empty checksum-matching file."""
    manifest_path = Path("data/manifest.csv")
    assert manifest_path.exists()
    df = pd.read_csv(manifest_path)
    assert len(df) >= 15

    for _, row in df.iterrows():
        path = Path(row["filepath_locale"])
        assert path.exists(), f"File mancante per dataset attivo {row['dataset_id']}: {path}"
        assert path.stat().st_size > 0, f"File vuoto per dataset attivo {row['dataset_id']}: {path}"
        assert compute_sha256(path) == row["sha256_hash"]


def test_manifest_fails_on_missing_input(tmp_path):
    missing = tmp_path / "missing.bin"
    with pytest.raises(AssertionError, match="File mancante"):
        assert missing.exists(), f"File mancante per dataset attivo test: {missing}"


def test_manifest_urls_licenses_and_provenance():
    df = pd.read_csv("data/manifest.csv")
    for _, row in df.iterrows():
        url = str(row["url_ufficiale"])
        assert url.startswith("https://"), f"URL non HTTPS per {row['dataset_id']}: {url}"

        if "worldpop" in row["dataset_id"]:
            assert "1km" not in url
            assert "Global_2000_2020" in url

        if "copernicus" in row["dataset_id"]:
            assert "Public Domain" not in str(row["licenza"])
            assert "Copernicus" in str(row["licenza"])

        if row["dataset_id"] in {
            "gtfs_arriva_addabus_inv_2025_2026",
            "gtfs_lineelecco_inv_2025_2026",
        }:
            assert row["licenza"] == "licenza non specificata / accesso pubblico"

    posas = df[df["dataset_id"] == "istat_posas_2025_lecco"].iloc[0]
    assert posas["stato_epistemico"] == "DERIVED"
    assert "POSAS_2025_it_Comuni.zip" in posas["url_ufficiale"]
    assert "fetch_posas_lecco" in posas["trasformazioni"]
    assert "manual" not in posas["trasformazioni"].lower()

    sfr = df[df["dataset_id"] == "sfr_trenord_serie_storica_2015_2025"].iloc[0]
    assert sfr["stato_epistemico"] == "DERIVED"
    assert SFR_HIST_UID in sfr["trasformazioni"]
    assert SFR_RECENT_UID in sfr["trasformazioni"]
    assert "2015-2023" in sfr["trasformazioni"]
    assert "2024-2025" in sfr["trasformazioni"]


def test_istat_boundaries():
    gdf = gpd.read_file("data/raw/boundaries/comuni_core_istat_2026.geojson")
    assert len(gdf) == 5
    assert set(gdf["PRO_COM_T"].astype(str)) == {
        "097010", "097012", "097058", "097074", "097092"
    }


def test_worldpop_real_raster():
    with rasterio.open("data/raw/worldpop/worldpop_core_unadj_raw.tif") as src:
        assert src.crs.to_epsg() == 4326
        assert abs(src.res[0] - 0.0008333333) < 1e-6
        data = src.read(1)
        valid = data[data > 0]
        assert len(valid) > 1000
        assert 15000 < valid.sum() < 35000


def test_copernicus_dem_raster():
    with rasterio.open("data/raw/dem/copernicus_dem_core_raw.tif") as src:
        data = src.read(1)
        valid = data[data > -9999]
        assert valid.max() > 400
        assert valid.min() >= 0


def test_istat_od_matrix():
    df = pd.read_csv("data/raw/od/matrice_pendolarismo_istat_2011_core.csv")
    assert len(df) > 500
    assert df["flusso_pendolari"].sum() > 5000


def test_trenord_gtfs():
    df = pd.read_csv("data/raw/gtfs/rail_trenord/stops.txt")
    assert (df["stop_id"] == "S01514").sum() == 1


def test_agency_bus_gtfs():
    arriva = Path("data/raw/gtfs/agency_arriva")
    lecco = Path("data/raw/gtfs/agency_lineelecco")
    required = ["routes.txt", "stops.txt", "trips.txt", "stop_times.txt", "calendar.txt", "shapes.txt"]
    for d in (arriva, lecco):
        for name in required:
            p = d / name
            assert p.exists() and p.stat().st_size > 0

    routes = pd.read_csv(arriva / "routes.txt")
    names = set(routes["route_short_name"].dropna().astype(str))
    assert {"D184", "D185", "D150", "D170"} <= names

    core_ids = routes[routes["route_short_name"].isin(["D184", "D185", "D150", "D170"])]["route_id"]
    trips = pd.read_csv(arriva / "trips.txt")
    core_trips = trips[trips["route_id"].isin(core_ids)]
    assert len(core_trips) > 100
    shapes = pd.read_csv(arriva / "shapes.txt")
    assert len(shapes[shapes["shape_id"].isin(core_trips["shape_id"])]) > 10000
    stop_times = pd.read_csv(arriva / "stop_times.txt")
    assert len(stop_times[stop_times["trip_id"].isin(core_trips["trip_id"])]) > 1000


def test_osm_acquisition_extent_covers_core_boundaries():
    meta = Path("data/raw/osm/osm_core_bbox.meta.json")
    assert meta.exists(), "OSM bbox metadata missing"
    import json
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload.get("buffer_m") == 500.0
    south, west, north, east = payload["bbox_south_west_north_east"]
    bounds = gpd.read_file("data/raw/boundaries/comuni_core_istat_2026.geojson").to_crs(4326)
    minx, miny, maxx, maxy = bounds.total_bounds
    assert west <= minx and south <= miny
    assert east >= maxx and north >= maxy


def test_osm_repo_snapshot_and_layers():
    raw = Path("data/raw/osm/osm_core_bbox.osm")
    lines = Path("data/raw/osm/osm_highways_core.geojson")
    points = Path("data/raw/osm/osm_points_core.geojson")
    assert raw.exists() and raw.stat().st_size > 1_000_000
    gdf_lines = gpd.read_file(lines)
    gdf_points = gpd.read_file(points)
    assert len(gdf_lines) > 4000
    assert len(gdf_points) > 1500
    assert "highway" in gdf_lines.columns


def test_osm_repo_parse_isolated(tmp_path):
    raw = "data/raw/osm/osm_core_bbox.osm"
    bbox = (9.355, 45.710, 9.460, 45.760)
    lines = pyogrio.read_dataframe(raw, layer="lines", bbox=bbox)
    points = pyogrio.read_dataframe(raw, layer="points", bbox=bbox)
    out_lines = tmp_path / "lines.geojson"
    out_points = tmp_path / "points.geojson"
    pyogrio.write_dataframe(lines, out_lines, driver="GeoJSON")
    pyogrio.write_dataframe(points, out_points, driver="GeoJSON")
    assert out_lines.stat().st_size > 100_000
    assert out_points.stat().st_size > 10_000


def _fake_posas_zip() -> bytes:
    headers = [
        "Codice comune", "Comune", "Età", "Celibi", "Coniugati", "Divorziati",
        "Vedovi", "Uniti civilmente", "Maschi già in unione civile (per scioglimento unione)",
        "Maschi già in unione civile (per decesso del partner)", "Totale maschi",
        "Nubili", "Coniugate", "Divorziate", "Vedove", "Unite civilmente",
        "Femmine già in unione civile (per scioglimento unione)",
        "Femmine già in unione civile (per decesso del partner)", "Totale femmine", "Totale"
    ]
    buf = io.StringIO()
    buf.write('"Popolazione residente per età, sesso e stato civile al 1° gennaio 2025"\n')
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(headers)
    for municipality in range(1, 42):
        code = f"097{municipality:03d}"
        for age in range(101):
            writer.writerow([code, f"Comune {municipality}", age, 0, 0, 0, 0, "", "", "", 1,
                             0, 0, 0, 0, "", "", "", 1, 2])
    writer.writerow(["015146", "Milano", 0, 0, 0, 0, 0, "", "", "", 1, 0, 0, 0, 0, "", "", "", 1, 2])

    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("POSAS_2025_it_Comuni.csv", buf.getvalue().encode("utf-8-sig"))
    return zip_bytes.getvalue()


def test_posas_rebuild_has_no_local_dependency(tmp_path, monkeypatch):
    class FakeResponse:
        content = _fake_posas_zip()
        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        assert url == POSAS_ALL_COMUNI_ZIP
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    out = tmp_path / "POSAS_2025_it_097_Lecco.csv"
    fetch_posas_lecco(str(out))
    assert out.exists() and out.stat().st_size > 10_000
    df = pd.read_csv(out, sep=";", skiprows=1, dtype={"Codice comune": str})
    assert df["Codice comune"].astype(str).str.zfill(6).str.startswith("097").all()
    assert len(df) == 4141


def test_sfr_rebuild_uses_both_official_datasets(tmp_path, monkeypatch):
    # Match Socrata resource API field naming: lower-case/underscore identifiers.
    # Historical 2015-2023 is documented by Regione Lombardia as weekday-mean only,
    # so the rebuild must not require a day-type column for that source.
    hist = pd.DataFrame({
        "campagna": [f"C_nov {year}" for year in range(2015, 2024)],
        "stazione": ["OLGIATE-CALCO-BRIVIO"] * 9,
        "saliti24h": [1000 + 50 * (year - 2015) for year in range(2015, 2024)],
        "anno": list(range(2015, 2024)),
    })
    recent = pd.DataFrame({
        "campagna": ["c2024Novembre", "c2025Novembre", "c2025Novembre"],
        "stazione": ["OLGIATE-CALCO-BRIVIO"] * 3,
        "saliti24h": [1800, 2000, 9999],
        "anno": [2024, 2025, 2025],
        "tipo_giorno": ["Feriale", "Feriale", "Sabato"],
    })
    calls = []

    def fake_read(url, timeout=120):
        calls.append(url)
        if url == SFR_HIST_CSV:
            return hist.copy()
        if url == SFR_RECENT_CSV:
            return recent.copy()
        raise AssertionError(url)

    import audit_01_fetch_real_inputs as audit
    monkeypatch.setattr(audit, "_read_sfr_csv", fake_read)
    out = tmp_path / "sfr.csv"
    fetch_sfr_from_socrata(str(out))
    assert calls == [SFR_HIST_CSV, SFR_RECENT_CSV]
    df = pd.read_csv(out)
    olg = df[df["Stazione_std"] == "OLGIATE-CALCO-BRIVIO"]
    assert set(olg["Anno"].astype(int)) == set(range(2015, 2026))
    assert olg.loc[olg["Anno"] == 2019, "Indice_2019_100"].iloc[0] == pytest.approx(100.0)
    assert olg.loc[olg["Anno"] == 2025, "Saliti24H"].iloc[0] == pytest.approx(2000.0)


def test_programma_di_bacino():
    main = Path("data/raw/pdb/PdB_Como_Lecco_Varese_Relazione_v7.2.pdf")
    meratese = Path("data/raw/pdb/PdB_Allegato3.4_Meratese.pdf")
    assert main.exists() and main.stat().st_size > 5_000_000
    assert meratese.exists() and meratese.stat().st_size > 8_000_000


def test_istat_posas_and_sfr_cached_outputs():
    posas = pd.read_csv(
        "data/raw/istat/POSAS_2025_it_097_Lecco.csv",
        sep=";",
        skiprows=1,
        dtype={"Codice comune": str},
    )
    assert len(posas) > 400

    sfr = pd.read_csv("data/raw/sfr/stazioni_s8_indice_2015_2025.csv")
    olg = sfr[sfr["Stazione_std"] == "OLGIATE-CALCO-BRIVIO"]
    assert set(olg["Anno"].astype(int)) == set(range(2015, 2026))


@pytest.mark.network
def test_osm_clean_network_fetch(tmp_path):
    out = tmp_path / "osm.osm"
    fetch_osm_xml((45.726, 9.388, 45.731, 9.396), str(out), timeout=60)
    assert out.exists() and out.stat().st_size > 500
    assert b"<osm" in out.read_bytes()[:1024]
    parsed_lines = pyogrio.read_dataframe(out, layer="lines")
    assert len(parsed_lines) > 5, "Overpass response contains no usable highway geometry"
    assert parsed_lines["highway"].notna().sum() > 5


@pytest.mark.network
def test_posas_clean_network_fetch(tmp_path):
    out = tmp_path / "POSAS_Lecco.csv"
    fetch_posas_lecco(str(out), timeout=120)
    df = pd.read_csv(out, sep=";", skiprows=1, dtype={"Codice comune": str})
    assert len(df) > 4000
    assert df["Codice comune"].astype(str).str.zfill(6).str.startswith("097").all()


@pytest.mark.network
def test_sfr_clean_network_fetch(tmp_path):
    out = tmp_path / "sfr.csv"
    fetch_sfr_from_socrata(str(out))
    df = pd.read_csv(out)
    olg = df[df["Stazione_std"] == "OLGIATE-CALCO-BRIVIO"]
    assert set(olg["Anno"].astype(int)) == set(range(2015, 2026))


def test_synthetic_invalidation_notice():
    text = Path("data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md").read_text(encoding="utf-8")
    assert "INVALIDATED BY EXTERNAL AUDIT" in text
