"""
src/gtfs_loader.py
Modulo per la gestione, costruzione e analisi dei dataset GTFS per il bacino di Olgiate Molgora.
Gestisce esplicitamente la separazione tra:
- network_structural: rete ordinaria e permanente (attraversamento ponte Adda a Brivio)
- network_2026_emergency: deviazione temporanea per cantiere ponte di Brivio via Olginate/Calolziocorte
"""

import os
import csv
import pandas as pd
from typing import Dict, List, Tuple

# Coordinate reali fermate chiave (WGS84 EPSG:4326)
STOPS_DATABASE = {
    # Olgiate Molgora
    "S_OLGIATE_FS": {"name": "Olgiate Molgora FS (Piazza Stazione)", "lat": 45.731450, "lon": 9.403210, "comune": "Olgiate Molgora", "zona": "Hub"},
    "S_OLGIATE_CENTRO": {"name": "Olgiate Molgora - Municipio / Via Sommi Picenardi", "lat": 45.733800, "lon": 9.401100, "comune": "Olgiate Molgora", "zona": "Centro"},
    "S_OLGIATE_SCARPONE": {"name": "Olgiate Molgora - Bivio Scarpone (SP342)", "lat": 45.736800, "lon": 9.388900, "comune": "Olgiate Molgora", "zona": "Ovest"},
    "S_MONDONICO": {"name": "Mondonico - Borgo / Villa Maria", "lat": 45.738500, "lon": 9.397200, "comune": "Olgiate Molgora", "zona": "Frazione Ovest"},
    "S_MONTICELLO_OLG": {"name": "Monticello di Olgiate - Via Belvedere", "lat": 45.742100, "lon": 9.392300, "comune": "Olgiate Molgora", "zona": "Frazione Ovest"},
    "S_SAN_ZENO": {"name": "San Zeno - Piazza San Zeno", "lat": 45.724800, "lon": 9.382100, "comune": "Olgiate Molgora", "zona": "Frazione Ovest"},
    
    # La Valletta Brianza
    "S_ROVAGNATE": {"name": "Rovagnate - Centro / Via Brianza", "lat": 45.738900, "lon": 9.369500, "comune": "La Valletta Brianza", "zona": "Core Ovest"},
    "S_PEREGO": {"name": "Perego - Municipio / Via Roma", "lat": 45.743200, "lon": 9.364200, "comune": "La Valletta Brianza", "zona": "Core Ovest"},
    "S_VALLETTA_SP342": {"name": "La Valletta - SP342 dir / Bivio S.Anna", "lat": 45.747100, "lon": 9.361800, "comune": "La Valletta Brianza", "zona": "Core Ovest"},
    
    # Santa Maria Hoè
    "S_SMARIA_CENTRO": {"name": "Santa Maria Hoè - Piazza Padre Fausto / Centro", "lat": 45.745600, "lon": 9.373400, "comune": "Santa Maria Hoè", "zona": "Core Ovest"},
    "S_SMARIA_TREB": {"name": "Santa Maria Hoè - Trebbia", "lat": 45.749200, "lon": 9.377100, "comune": "Santa Maria Hoè", "zona": "Core Ovest"},
    
    # Coda Ovest: Colle Brianza / Ravellino
    "S_GIOVENZANA": {"name": "Colle Brianza - Giovenzana", "lat": 45.762100, "lon": 9.365400, "comune": "Colle Brianza", "zona": "Coda Ovest"},
    "S_RAVELLINO": {"name": "Ravellino - Capolinea (Colle Brianza)", "lat": 45.768900, "lon": 9.371200, "comune": "Colle Brianza", "zona": "Coda Ovest"},

    # Calco
    "S_CALCO_NAZ": {"name": "Calco - Via Nazionale (SP342) / Municipio", "lat": 45.726200, "lon": 9.412400, "comune": "Calco", "zona": "Core Est"},
    "S_CALCO_CHIESA": {"name": "Calco - Chiesa Parrocchiale / Via Volta", "lat": 45.724500, "lon": 9.414800, "comune": "Calco", "zona": "Core Est"},
    "S_CALCO_SUP": {"name": "Calco Superiore - Borgo Alto", "lat": 45.728900, "lon": 9.419200, "comune": "Calco", "zona": "Frazione Est"},
    "S_ARLATE": {"name": "Arlate - San Colombano / Via San Gottardo", "lat": 45.716400, "lon": 9.432100, "comune": "Calco", "zona": "Frazione Est"},
    
    # Brivio
    "S_BEVERATE": {"name": "Beverate - Centro / Scuole Elementari", "lat": 45.735100, "lon": 9.424500, "comune": "Brivio", "zona": "Core Est"},
    "S_BRIVIO_CASTELLO": {"name": "Brivio - Castello / Piazza Frigerio", "lat": 45.744100, "lon": 9.444200, "comune": "Brivio", "zona": "Core Est"},
    "S_BRIVIO_PORTO": {"name": "Brivio - Lungo Adda / Alzaia", "lat": 45.742800, "lon": 9.445500, "comune": "Brivio", "zona": "Core Est"},
    "S_BRIVIO_PONTE": {"name": "Brivio - Testata Ponte Adda (SP342)", "lat": 45.746200, "lon": 9.448500, "comune": "Brivio", "zona": "Core Est"},
    
    # Coda Est: Sponda Bergamasca (Cisano / Caprino / Celana)
    "S_CISANO_SOSTA": {"name": "Cisano Bergamasco - Sosta / Piazza De Gasperi", "lat": 45.744800, "lon": 9.468200, "comune": "Cisano Bergamasco", "zona": "Coda Est"},
    "S_CAPRINO_CENTRO": {"name": "Caprino Bergamasco - Municipio / Via Roma", "lat": 45.749500, "lon": 9.482100, "comune": "Caprino Bergamasco", "zona": "Coda Est"},
    "S_CELANA": {"name": "Caprino Bergamasco - Collegio Celana", "lat": 45.753800, "lon": 9.493500, "comune": "Caprino Bergamasco", "zona": "Coda Est"},
    
    # Deviazione Emergenziale 2026 (Cantiere Ponte di Brivio)
    "S_OLGINATE_CAPIATE": {"name": "Olginate - Frazione Capiate (Deviazione Emergenza)", "lat": 45.772500, "lon": 9.423100, "comune": "Olginate", "zona": "Emergenza 2026"},
    "S_PONTE_CANTU": {"name": "Ponte Cesare Cantù (Olginate-Calolziocorte)", "lat": 45.783200, "lon": 9.421500, "comune": "Olginate", "zona": "Emergenza 2026"},
    "S_CALOLZIO_BISONE": {"name": "Calolziocorte - Frazione Bisone", "lat": 45.781100, "lon": 9.434200, "comune": "Calolziocorte", "zona": "Emergenza 2026"}
}

def export_gtfs_tables(out_dir: str, routes_data: list, trips_data: list, stop_times_data: list, is_emergency: bool = False):
    """Esporta tabelle GTFS standard in una cartella specifica."""
    os.makedirs(out_dir, exist_ok=True)
    
    # agency.txt
    with open(os.path.join(out_dir, "agency.txt"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang", "agency_phone"])
        writer.writerow(["ARRIVA_LC", "Arriva Italia - Bacino Lecco", "https://bergamo.arriva.it", "Europe/Rome", "it", "035289000"])
        writer.writerow(["LINEE_LC", "LineeLecco", "https://lineelecco.it", "Europe/Rome", "it", "0341359911"])
    
    # stops.txt
    with open(os.path.join(out_dir, "stops.txt"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["stop_id", "stop_name", "stop_lat", "stop_lon", "zone_id", "location_type"])
        for sid, sinfo in STOPS_DATABASE.items():
            if not is_emergency and "Emergenza 2026" in sinfo["zona"]:
                continue
            writer.writerow([sid, sinfo["name"], sinfo["lat"], sinfo["lon"], sinfo["comune"], 0])
            
    # routes.txt
    with open(os.path.join(out_dir, "routes.txt"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color", "route_text_color"])
        for r in routes_data:
            writer.writerow(r)
            
    # calendar.txt
    with open(os.path.join(out_dir, "calendar.txt"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"])
        writer.writerow(["FERIALE_LUN_VEN", 1, 1, 1, 1, 1, 0, 0, "20260101", "20261231"])
        writer.writerow(["FERIALE_LUN_SAB", 1, 1, 1, 1, 1, 1, 0, "20260101", "20261231"])
        writer.writerow(["SCOLASTICO", 1, 1, 1, 1, 1, 1, 0, "20260912", "20260608"])
        writer.writerow(["FESTIVO", 0, 0, 0, 0, 0, 0, 1, "20260101", "20261231"])
        
    # trips.txt
    with open(os.path.join(out_dir, "trips.txt"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["route_id", "service_id", "trip_id", "trip_headsign", "direction_id", "shape_id"])
        for t in trips_data:
            writer.writerow(t)
            
    # stop_times.txt
    with open(os.path.join(out_dir, "stop_times.txt"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "pickup_type", "drop_off_type"])
        for st in stop_times_data:
            writer.writerow(st)

    print(f"[GTFS] Esportato dataset GTFS in {out_dir} (is_emergency={is_emergency})")
