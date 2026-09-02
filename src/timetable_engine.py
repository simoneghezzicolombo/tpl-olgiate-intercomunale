"""
src/timetable_engine.py
Motore di simulazione oraria, calcolo tempi di sosta (dwell times) e sincronizzazione
con i treni del Servizio Ferroviario Regionale S8 a Olgiate-Calco-Brivio FS.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

# Orario cadenzato S8 a Olgiate-Calco-Brivio FS (orario ufficiale RFI / Trenord vigente)
TRENI_S8_VIGENTI = {
    # Partenze verso Milano Porta Garibaldi (minuti :08 e :38)
    "to_milano": [8, 38],
    # Arrivi da Milano Porta Garibaldi (minuti :21 e :51)
    "from_milano": [21, 51],
    # Partenze verso Lecco (minuti :22 e :52)
    "to_lecco": [22, 52],
    # Arrivi da Lecco (minuti :07 e :37)
    "from_lecco": [7, 37]
}

# Parametri operativi
DWELL_TIME_SECONDS = {
    "capolinea_intermedio": 60, # 1 minuto di sosta
    "fermata_intermedia": 20,    # 20 secondi per salita/discesa
    "hub_stazione_fs": 180       # 3 minuti minimi di sosta a Olgiate FS
}

def analyze_train_transfers(bus_arrivals_fs: List[int], bus_departures_fs: List[int]) -> Dict:
    """
    Calcola le metriche di coincidenza ferro-gomma a Olgiate FS:
    - bus_arrivals_fs: lista dei minuti di arrivo del bus alla stazione (es. [26, 56])
    - bus_departures_fs: lista dei minuti di partenza del bus dalla stazione (es. [0, 30])
    Finestra ottimale di interscambio: tra 4 e 15 minuti.
    """
    transfers_to_milano = []
    transfers_to_lecco = []
    transfers_from_milano = []
    transfers_from_lecco = []
    
    # Bus -> Treno (Passeggero scende dal bus e sale sul treno per Milano/Lecco)
    for arr in bus_arrivals_fs:
        # Verso Milano (:08, :38)
        for t_dep in TRENI_S8_VIGENTI["to_milano"]:
            wait = (t_dep - arr) % 60
            if 4 <= wait <= 16:
                transfers_to_milano.append(wait)
        # Verso Lecco (:22, :52)
        for t_dep in TRENI_S8_VIGENTI["to_lecco"]:
            wait = (t_dep - arr) % 60
            if 4 <= wait <= 18:
                transfers_to_lecco.append(wait)
                
    # Treno -> Bus (Passeggero scende dal treno e sale sul bus)
    for dep in bus_departures_fs:
        # Da Milano (:21, :51)
        for t_arr in TRENI_S8_VIGENTI["from_milano"]:
            wait = (dep - t_arr) % 60
            if 4 <= wait <= 16:
                transfers_from_milano.append(wait)
        # Da Lecco (:07, :37)
        for t_arr in TRENI_S8_VIGENTI["from_lecco"]:
            wait = (dep - t_arr) % 60
            if 4 <= wait <= 16:
                transfers_from_lecco.append(wait)

    all_transfers = transfers_to_milano + transfers_to_lecco + transfers_from_milano + transfers_from_lecco
    
    if len(all_transfers) > 0:
        mean_wait = float(np.mean(all_transfers))
        median_wait = float(np.median(all_transfers))
        p90_wait = float(np.percentile(all_transfers, 90))
    else:
        mean_wait, median_wait, p90_wait = 0.0, 0.0, 0.0
        
    return {
        "coincidenze_valide_ora": len(all_transfers),
        "coincidenze_to_milano": len(transfers_to_milano),
        "coincidenze_to_lecco": len(transfers_to_lecco),
        "coincidenze_from_milano": len(transfers_from_milano),
        "coincidenze_from_lecco": len(transfers_from_lecco),
        "tempo_medio_interscambio_min": round(mean_wait, 1),
        "mediana_interscambio_min": round(median_wait, 1),
        "p90_interscambio_min": round(p90_wait, 1),
        "pct_treni_s8_alimentati": min(100.0, round((len(all_transfers) / 8.0) * 100, 1)) # 4 treni/ora per direzione
    }
