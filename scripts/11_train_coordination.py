#!/usr/bin/env python3
"""
11_train_coordination.py
Analisi della sincronizzazione intermodale treno-bus alla stazione Olgiate-Calco-Brivio FS.
Valuta per ciascun scenario:
- Partenze e arrivi S8 vigenti (Milano :08/:38 e :21/:51; Lecco :22/:52 e :07/:37)
- Tempo medio di interscambio, mediana, 90° percentile (P90)
- % dei treni S8 utilmente alimentati dal TPL su gomma
- % dei bus con coincidenza utile (finestra 4-16 min)
Salva outputs/train_connections.csv.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
from src.timetable_engine import analyze_train_transfers, TRENI_S8_VIGENTI

OUT_TRAIN_CSV = "outputs/train_connections.csv"

# Configurazioni orarie degli scenari alla stazione di Olgiate FS (minuti all'ora)
CONFIGURAZIONI_NODO = [
    {
        "scenario": "SCENARIO_0 (Attuale)",
        "desc": "Transiti irregolari con buchi fino a 7 ore",
        "arrivi_bus_fs": [24, 45], # solo in alcune ore
        "partenze_bus_fs": [35, 37],
        "ore_coperte": 6,
        "coincidenze_giorno": 24
    },
    {
        "scenario": "SCENARIO_1 (1 Bus Anello Integrato)",
        "desc": "1 bus continuo: transito a FS ogni 30 min alternando Ovest ed Est",
        "arrivi_bus_fs": [26, 56], # :26 dall'ovest, :56 dall'est
        "partenze_bus_fs": [0, 30], # :00 per l'est, :30 per l'ovest
        "ore_coperte": 13,
        "coincidenze_giorno": 52
    },
    {
        "scenario": "SCENARIO_2 (2 Bus Full Merate CW+CCW)",
        "desc": "2 bus continui nei due versi: transiti a FS ogni 15 minuti",
        "arrivi_bus_fs": [12, 26, 42, 56],
        "partenze_bus_fs": [0, 15, 30, 45],
        "ore_coperte": 13,
        "coincidenze_giorno": 104
    },
    {
        "scenario": "SCENARIO_3 (Core 60' + Code 120')",
        "desc": "Transiti core a :26/:56 più partenze code a :00",
        "arrivi_bus_fs": [26, 55],
        "partenze_bus_fs": [0, 30],
        "ore_coperte": 13,
        "coincidenze_giorno": 64
    },
    {
        "scenario": "SCENARIO_4 (Ibrido di Punta CW+CCW Raccomandato)",
        "desc": "Transiti a :12, :26, :42, :56 in punta; :26 e :56 in morbida",
        "arrivi_bus_fs": [12, 26, 42, 56],
        "partenze_bus_fs": [0, 15, 30, 45],
        "ore_coperte": 13,
        "coincidenze_giorno": 88
    }
]

def main():
    print("=== 11: ANALISI SINCRONIZZAZIONE CON SERVIZIO FERROVIARIO S8 ===")
    os.makedirs("outputs", exist_ok=True)
    
    results = []
    for cfg in CONFIGURAZIONI_NODO:
        metrics = analyze_train_transfers(cfg["arrivi_bus_fs"], cfg["partenze_bus_fs"])
        
        # Stima del rail connection score globale (0-100)
        # Basato su % treni alimentati, tempo medio di attesa e frequenza
        score = min(100.0, (metrics["pct_treni_s8_alimentati"] * 0.6) + (max(0, 18 - metrics["tempo_medio_interscambio_min"]) * 2.5))
        
        results.append({
            "scenario": cfg["scenario"],
            "descrizione_transiti_fs": cfg["desc"],
            "minuti_arrivo_bus_fs": str(cfg["arrivi_bus_fs"]),
            "minuti_partenza_bus_fs": str(cfg["partenze_bus_fs"]),
            "tempo_medio_interscambio_min": metrics["tempo_medio_interscambio_min"],
            "mediana_interscambio_min": metrics["mediana_interscambio_min"],
            "p90_interscambio_min": metrics["p90_interscambio_min"],
            "coincidenze_utili_ora": metrics["coincidenze_valide_ora"],
            "coincidenze_utili_giorno": cfg["coincidenze_giorno"],
            "pct_treni_s8_alimentati": metrics["pct_treni_s8_alimentati"],
            "pct_bus_con_coincidenza_milano": round((metrics["coincidenze_to_milano"] / max(1, len(cfg["arrivi_bus_fs"]))) * 100, 1),
            "pct_bus_con_coincidenza_lecco": round((metrics["coincidenze_to_lecco"] / max(1, len(cfg["arrivi_bus_fs"]))) * 100, 1),
            "rail_connection_score": round(score, 1)
        })
        
    df_res = pd.DataFrame(results)
    df_res.to_csv(OUT_TRAIN_CSV, index=False)
    print(f"[OK] Salvate metriche interscambio S8 in {OUT_TRAIN_CSV}.")
    
    print("\n--- PERFORMANCE DI INTERSCAMBIO FERRO-GOMMA A OLGIATE FS ---")
    cols_show = ["scenario", "tempo_medio_interscambio_min", "mediana_interscambio_min", "p90_interscambio_min", "pct_treni_s8_alimentati", "rail_connection_score"]
    print(df_res[cols_show].to_string(index=False))

if __name__ == "__main__":
    main()
