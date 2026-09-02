#!/usr/bin/env python3
"""
04_walk_network.py
Calcolo dell'accessibilità pedonale reale alle fermate TPL del bacino.
Applica Tobler's hiking function (slope-adjusted walk time) e calcola:
- Nearest stop walk minutes per ogni cella (standard e slope-adjusted)
- Bacini di fermata a 5, 8, 10, 12 minuti senza double-counting
- outputs/stop_analysis.csv e outputs/fraction_analysis.csv
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
import numpy as np
from src.gtfs_loader import STOPS_DATABASE
from src.spatial_network import compute_walk_time, calculate_distance_m

GRID_CSV = "data/processed/population_grid_calibrated.csv"
OUT_CELLS_CSV = "data/processed/walk_isochrones_cells.csv"
OUT_STOPS_CSV = "outputs/stop_analysis.csv"
OUT_FRACTIONS_CSV = "outputs/fraction_analysis.csv"

# Quota altimetrica approssimativa fermate (da DEM)
STOP_ELEVATIONS = {
    "S_OLGIATE_FS": 287,
    "S_OLGIATE_CENTRO": 295,
    "S_OLGIATE_SCARPONE": 310,
    "S_MONDONICO": 320,
    "S_MONTICELLO_OLG": 345,
    "S_SAN_ZENO": 365,
    "S_ROVAGNATE": 342,
    "S_PEREGO": 374,
    "S_VALLETTA_SP342": 380,
    "S_SMARIA_CENTRO": 371,
    "S_SMARIA_TREB": 410,
    "S_CALCO_NAZ": 280,
    "S_CALCO_CHIESA": 288,
    "S_CALCO_SUP": 325,
    "S_ARLATE": 265,
    "S_BEVERATE": 250,
    "S_BRIVIO_CASTELLO": 208,
    "S_BRIVIO_PORTO": 206,
    "S_BRIVIO_PONTE": 209,
    "S_CISANO_SOSTA": 268,
    "S_CAPRINO_CENTRO": 315,
    "S_CELANA": 385,
    "S_RAVELLINO": 550,
    "S_GIOVENZANA": 490
}

def main():
    print("=== 04: CALCOLO ACCESSIBILITÀ PEDONALE SLOPE-ADJUSTED ED ISOCRONE ===")
    if not os.path.exists(GRID_CSV):
        print(f"Errore: {GRID_CSV} non trovato. Esegui prima 03_population_grid.py!")
        sys.exit(1)
        
    cells_df = pd.read_csv(GRID_CSV)
    print(f"Caricate {len(cells_df)} celle di popolazione.")
    
    # Filtra fermate rilevanti per il core + fermate candidati
    active_stops = {sid: s for sid, s in STOPS_DATABASE.items() if "Emergenza" not in s["zona"]}
    
    # Matrice distanze e tempi: per ogni cella, trova la fermata più vicina
    nearest_stop_list = []
    min_time_std_list = []
    min_time_slope_list = []
    min_dist_list = []
    
    for _, cell in cells_df.iterrows():
        c_lat, c_lon, c_elev = cell["lat"], cell["lon"], cell["elevation_m"]
        
        best_time_slope = float("inf")
        best_time_std = float("inf")
        best_stop = None
        best_dist = float("inf")
        
        for sid, sinfo in active_stops.items():
            s_lat, s_lon = sinfo["lat"], sinfo["lon"]
            s_elev = STOP_ELEVATIONS.get(sid, 280)
            
            dist_m = calculate_distance_m(c_lat, c_lon, s_lat, s_lon)
            if dist_m < 3500: # consideriamo solo fermate entro 3.5 km
                delta_elev = s_elev - c_elev # dislivello verso la fermata
                t_std, t_slope = compute_walk_time(dist_m, delta_elev)
                if t_slope < best_time_slope:
                    best_time_slope = t_slope
                    best_time_std = t_std
                    best_stop = sid
                    best_dist = dist_m
                    
        nearest_stop_list.append(best_stop if best_stop else "NONE")
        min_time_std_list.append(round(best_time_std, 2) if best_stop else 999.0)
        min_time_slope_list.append(round(best_time_slope, 2) if best_stop else 999.0)
        min_dist_list.append(round(best_dist, 1) if best_stop else 9999.0)
        
    cells_df["nearest_stop_id"] = nearest_stop_list
    cells_df["nearest_stop_dist_m"] = min_dist_list
    cells_df["walk_min_std"] = min_time_std_list
    cells_df["walk_min_slope"] = min_time_slope_list
    
    # Salva celle arricchite
    cells_df.to_csv(OUT_CELLS_CSV, index=False)
    print(f"[OK] Salvate celle con tempi pedonali in {OUT_CELLS_CSV}")
    
    # 1. Calcolo Copertura per Soglie Isocrone (Senza Double Counting)
    print("\n--- COPERTURA DEMOGRAFICA COMBINATA (SENZA DOUBLE COUNTING) ---")
    tot_pop = cells_df["pop_calibrated"].sum()
    
    for thresh in [5, 8, 10, 12]:
        covered_std = cells_df[cells_df["walk_min_std"] <= thresh]["pop_calibrated"].sum()
        covered_slope = cells_df[cells_df["walk_min_slope"] <= thresh]["pop_calibrated"].sum()
        pct_std = (covered_std / tot_pop) * 100
        pct_slope = (covered_slope / tot_pop) * 100
        print(f"Entro {thresh:2d} min: Standard = {covered_std:6.0f} ab ({pct_std:4.1f}%) | Slope-Adjusted = {covered_slope:6.0f} ab ({pct_slope:4.1f}%)")
        
    # 2. Stop Analysis (Bacino esclusivo per ciascuna fermata)
    stop_rows = []
    for sid, sinfo in active_stops.items():
        sub = cells_df[cells_df["nearest_stop_id"] == sid]
        pop_5m = sub[sub["walk_min_slope"] <= 5]["pop_calibrated"].sum()
        pop_8m = sub[sub["walk_min_slope"] <= 8]["pop_calibrated"].sum()
        pop_10m = sub[sub["walk_min_slope"] <= 10]["pop_calibrated"].sum()
        pop_12m = sub[sub["walk_min_slope"] <= 12]["pop_calibrated"].sum()
        
        stop_rows.append({
            "stop_id": sid,
            "stop_name": sinfo["name"],
            "comune": sinfo["comune"],
            "zona": sinfo["zona"],
            "pop_esclusiva_5min": round(pop_5m, 1),
            "pop_esclusiva_8min": round(pop_8m, 1),
            "pop_esclusiva_10min": round(pop_10m, 1),
            "pop_esclusiva_12min": round(pop_12m, 1),
            "celle_attribuite": len(sub)
        })
    stops_df = pd.DataFrame(stop_rows).sort_values("pop_esclusiva_10min", ascending=False)
    stops_df.to_csv(OUT_STOPS_CSV, index=False)
    print(f"[OK] Salvata analisi fermate in {OUT_STOPS_CSV}")
    
    # 3. Fraction Analysis (Copertura per frazione)
    frac_rows = []
    for (comune, frazione), sub_f in cells_df.groupby(["comune", "frazione"]):
        tot_f = sub_f["pop_calibrated"].sum()
        cov_8m = sub_f[sub_f["walk_min_slope"] <= 8]["pop_calibrated"].sum()
        cov_10m = sub_f[sub_f["walk_min_slope"] <= 10]["pop_calibrated"].sum()
        avg_walk = (sub_f["walk_min_slope"] * sub_f["pop_calibrated"]).sum() / tot_f if tot_f > 0 else 0
        
        frac_rows.append({
            "comune": comune,
            "frazione": frazione,
            "popolazione_totale": round(tot_f, 1),
            "pop_entro_8min_slope": round(cov_8m, 1),
            "pct_entro_8min": round((cov_8m / tot_f) * 100, 1) if tot_f > 0 else 0,
            "pop_entro_10min_slope": round(cov_10m, 1),
            "pct_entro_10min": round((cov_10m / tot_f) * 100, 1) if tot_f > 0 else 0,
            "tempo_medio_piedi_fermata_min": round(avg_walk, 1)
        })
    frac_df = pd.DataFrame(frac_rows).sort_values("popolazione_totale", ascending=False)
    frac_df.to_csv(OUT_FRACTIONS_CSV, index=False)
    print(f"[OK] Salvata analisi frazioni in {OUT_FRACTIONS_CSV}")
    print("\n--- ANALISI COPERTURA FRAZIONI (TOP 8) ---")
    print(frac_df.head(8)[["comune", "frazione", "popolazione_totale", "pct_entro_10min", "tempo_medio_piedi_fermata_min"]].to_string(index=False))

if __name__ == "__main__":
    main()
