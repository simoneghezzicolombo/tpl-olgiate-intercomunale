"""
tests/test_gtfs_integrity.py
Verifica l'integrità referenziale e la completezza delle tabelle GTFS relazionali:
- network_structural
- network_2026_emergency
Controlla presenza di agency, routes, trips, stop_times, stops, calendar e coerenza delle foreign keys.
"""

import os
import pandas as pd
import pytest

GTFS_DIRS = [
    "data/raw/gtfs/network_structural",
    "data/raw/gtfs/network_2026_emergency"
]

GTFS_FILES = ["agency.txt", "routes.txt", "trips.txt", "stop_times.txt", "stops.txt", "calendar.txt"]

@pytest.mark.parametrize("gtfs_dir", GTFS_DIRS)
def test_gtfs_files_exist(gtfs_dir):
    for fname in GTFS_FILES:
        fpath = os.path.join(gtfs_dir, fname)
        assert os.path.exists(fpath), f"Manca il file obbligatorio {fname} in {gtfs_dir}"
        assert os.path.getsize(fpath) > 0, f"Il file {fname} in {gtfs_dir} è vuoto!"

@pytest.mark.parametrize("gtfs_dir", GTFS_DIRS)
def test_gtfs_referential_integrity(gtfs_dir):
    stops_df = pd.read_csv(os.path.join(gtfs_dir, "stops.txt"))
    trips_df = pd.read_csv(os.path.join(gtfs_dir, "trips.txt"))
    routes_df = pd.read_csv(os.path.join(gtfs_dir, "routes.txt"))
    stimes_df = pd.read_csv(os.path.join(gtfs_dir, "stop_times.txt"))

    # Verifica route_id in trips esiste in routes
    valid_routes = set(routes_df["route_id"])
    assert set(trips_df["route_id"]).issubset(valid_routes), f"Trip con route_id non valido in {gtfs_dir}"

    # Verifica trip_id in stop_times esiste in trips
    valid_trips = set(trips_df["trip_id"])
    assert set(stimes_df["trip_id"]).issubset(valid_trips), f"Stop_time con trip_id non valido in {gtfs_dir}"

    # Verifica stop_id in stop_times esiste in stops
    valid_stops = set(stops_df["stop_id"])
    assert set(stimes_df["stop_id"]).issubset(valid_stops), f"Stop_time con stop_id non valido in {gtfs_dir}"

    # Coordinate geografiche WGS84 plausibili per la Brianza (lat ~45.7, lon ~9.4)
    assert ((stops_df["stop_lat"] >= 45.6) & (stops_df["stop_lat"] <= 45.9)).all(), "Latitudini non valide in stops.txt"
    assert ((stops_df["stop_lon"] >= 9.2) & (stops_df["stop_lon"] <= 9.6)).all(), "Longitudini non valide in stops.txt"
