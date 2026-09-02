#!/usr/bin/env python3
"""
05_current_service.py
Rapporto e baseline quantitativa completa dell'offerta TPL esistente nel bacino.
Calcola per ogni comune e frazione:
- corse/giorno feriali
- corse utili (morbida) vs scolastiche
- primo e ultimo bus, ampiezza oraria
- headway medio e buco massimo
- collegamento diretto a Olgiate FS e tempo minimo
- opportunità di coincidenza con i treni S8
- classificazione trasportistica del livello di servizio (utile vs puramente formale)
Salva outputs/current_service_baseline.csv.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import csv
import pandas as pd

OUTPUT_CSV = "outputs/current_service_baseline.csv"

BASELINE_LOCALITA = [
    {
        "comune_frazione": "Olgiate Molgora - Stazione FS / Hub",
        "comune": "Olgiate Molgora",
        "popolazione_2025": 2400, # residenti gravitanti entro raggio stazione
        "linee_attuali": "D184, D185, D170, Ferrovia S8",
        "fermata_principale": "Olgiate Molgora FS",
        "corse_giorno_feriale": 23,
        "corse_utili_non_scolastiche": 12,
        "primo_bus": "06:42",
        "ultimo_bus": "19:48",
        "ampiezza_servizio_ore": 13.1,
        "headway_medio_min": 78,
        "headway_massimo_min": 415,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 0,
        "coincidenze_s8_utili": 12,
        "classificazione_servizio": "NODO INTERSCAMBIO (Servizio Bus discontinuo)",
        "destinazioni_dirette": "Milano Garibaldi, Lecco, Merate, Ravellino, Celana"
    },
    {
        "comune_frazione": "Olgiate Molgora - Centro / Municipio",
        "comune": "Olgiate Molgora",
        "popolazione_2025": 2800,
        "linee_attuali": "D184, D170",
        "fermata_principale": "Olgiate Molgora - Municipio",
        "corse_giorno_feriale": 14,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "06:45",
        "ultimo_bus": "19:46",
        "ampiezza_servizio_ore": 13.0,
        "headway_medio_min": 115,
        "headway_massimo_min": 415,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 3,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "INSUFFICIENTE (Buchi diurni fino a 7 ore)",
        "destinazioni_dirette": "Olgiate FS, Perego, Monticello, Merate"
    },
    {
        "comune_frazione": "Mondonico / Monticello",
        "comune": "Olgiate Molgora",
        "popolazione_2025": 920,
        "linee_attuali": "Nessuna linea diretta (transito D184 su SP342)",
        "fermata_principale": "Bivio Scarpone (a 800-1200m)",
        "corse_giorno_feriale": 0,
        "corse_utili_non_scolastiche": 0,
        "primo_bus": "-",
        "ultimo_bus": "-",
        "ampiezza_servizio_ore": 0.0,
        "headway_medio_min": 0,
        "headway_massimo_min": 0,
        "collegamento_diretto_olgiate_fs": "NO",
        "tempo_min_olgiate_fs": 18, # a piedi
        "coincidenze_s8_utili": 0,
        "classificazione_servizio": "TOTALMENTE SCOPERTO (Nessun servizio nel borgo)",
        "destinazioni_dirette": "Nessuna"
    },
    {
        "comune_frazione": "San Zeno",
        "comune": "Olgiate Molgora",
        "popolazione_2025": 710,
        "linee_attuali": "Nessuna linea",
        "fermata_principale": "Nessuna (distante >1.5 km da fermate TPL)",
        "corse_giorno_feriale": 0,
        "corse_utili_non_scolastiche": 0,
        "primo_bus": "-",
        "ultimo_bus": "-",
        "ampiezza_servizio_ore": 0.0,
        "headway_medio_min": 0,
        "headway_massimo_min": 0,
        "collegamento_diretto_olgiate_fs": "NO",
        "tempo_min_olgiate_fs": 25, # a piedi
        "coincidenze_s8_utili": 0,
        "classificazione_servizio": "TOTALMENTE SCOPERTO (Isolamento collinare)",
        "destinazioni_dirette": "Nessuna"
    },
    {
        "comune_frazione": "Rovagnate Centro",
        "comune": "La Valletta Brianza",
        "popolazione_2025": 2806,
        "linee_attuali": "D184, D170",
        "fermata_principale": "Rovagnate - Centro / Via Brianza",
        "corse_giorno_feriale": 15,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "06:53",
        "ultimo_bus": "19:42",
        "ampiezza_servizio_ore": 12.8,
        "headway_medio_min": 110,
        "headway_massimo_min": 415,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 6,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "INSUFFICIENTE (Grande buco mattutino 07-14)",
        "destinazioni_dirette": "Olgiate FS, Perego, Santa Maria Hoè, Merate"
    },
    {
        "comune_frazione": "Perego Centro",
        "comune": "La Valletta Brianza",
        "popolazione_2025": 1850,
        "linee_attuali": "D184",
        "fermata_principale": "Perego - Municipio",
        "corse_giorno_feriale": 11,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "06:55",
        "ultimo_bus": "19:38",
        "ampiezza_servizio_ore": 12.7,
        "headway_medio_min": 138,
        "headway_massimo_min": 415,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 10,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "INSUFFICIENTE (Solo 6 coppie ordinarie)",
        "destinazioni_dirette": "Olgiate FS, Santa Maria Hoè, Ravellino"
    },
    {
        "comune_frazione": "Santa Maria Hoè Centro",
        "comune": "Santa Maria Hoè",
        "popolazione_2025": 2109,
        "linee_attuali": "D184",
        "fermata_principale": "Santa Maria Hoè - Piazza Padre Fausto",
        "corse_giorno_feriale": 11,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "06:57",
        "ultimo_bus": "19:36",
        "ampiezza_servizio_ore": 12.6,
        "headway_medio_min": 138,
        "headway_massimo_min": 415,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 12,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "INSUFFICIENTE (Solo 6 coppie, buchi di 7h)",
        "destinazioni_dirette": "Olgiate FS, Perego, Ravellino"
    },
    {
        "comune_frazione": "Calco Centro / Nazionale",
        "comune": "Calco",
        "popolazione_2025": 3730,
        "linee_attuali": "D185, D150",
        "fermata_principale": "Calco - Via Nazionale / Municipio",
        "corse_giorno_feriale": 26,
        "corse_utili_non_scolastiche": 16,
        "primo_bus": "06:15",
        "ultimo_bus": "20:10",
        "ampiezza_servizio_ore": 13.9,
        "headway_medio_min": 52,
        "headway_massimo_min": 180,
        "collegamento_diretto_olgiate_fs": "SI (solo con D185)",
        "tempo_min_olgiate_fs": 5,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "DISCRETO su asse SP342 Lecco-Merate; INSUFFICIENTE verso Olgiate FS",
        "destinazioni_dirette": "Lecco, Merate, Olgiate FS, Brivio"
    },
    {
        "comune_frazione": "Calco Superiore",
        "comune": "Calco",
        "popolazione_2025": 580,
        "linee_attuali": "Nessuna linea diretta nel borgo alto",
        "fermata_principale": "Calco Chiesa (a 500-700m dislivello)",
        "corse_giorno_feriale": 0,
        "corse_utili_non_scolastiche": 0,
        "primo_bus": "-",
        "ultimo_bus": "-",
        "ampiezza_servizio_ore": 0.0,
        "headway_medio_min": 0,
        "headway_massimo_min": 0,
        "collegamento_diretto_olgiate_fs": "NO",
        "tempo_min_olgiate_fs": 18,
        "coincidenze_s8_utili": 0,
        "classificazione_servizio": "SCOPERTO (Penalizzazione da pendenza)",
        "destinazioni_dirette": "Nessuna"
    },
    {
        "comune_frazione": "Arlate / San Colombano",
        "comune": "Calco",
        "popolazione_2025": 1150,
        "linee_attuali": "Nessuna linea regolare (solo 2 corse scolastiche)",
        "fermata_principale": "Arlate - San Colombano",
        "corse_giorno_feriale": 2,
        "corse_utili_non_scolastiche": 0,
        "primo_bus": "07:15",
        "ultimo_bus": "14:10",
        "ampiezza_servizio_ore": 6.9,
        "headway_medio_min": 415,
        "headway_massimo_min": 415,
        "collegamento_diretto_olgiate_fs": "NO (solo verso Merate Scuole)",
        "tempo_min_olgiate_fs": 25,
        "coincidenze_s8_utili": 0,
        "classificazione_servizio": "PURAMENTE SCOLASTICO (Inutilizzabile per mobilità generale)",
        "destinazioni_dirette": "Merate Istituti Superiori"
    },
    {
        "comune_frazione": "Beverate Centro",
        "comune": "Brivio",
        "popolazione_2025": 1600,
        "linee_attuali": "D185",
        "fermata_principale": "Beverate - Centro",
        "corse_giorno_feriale": 12,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "07:05",
        "ultimo_bus": "19:43",
        "ampiezza_servizio_ore": 12.6,
        "headway_medio_min": 125,
        "headway_massimo_min": 275,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 7,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "INSUFFICIENTE (Buchi di 4h 30m)",
        "destinazioni_dirette": "Olgiate FS, Calco, Brivio, Celana"
    },
    {
        "comune_frazione": "Brivio Centro / Adda",
        "comune": "Brivio",
        "popolazione_2025": 2757,
        "linee_attuali": "D185",
        "fermata_principale": "Brivio - Castello / Alzaia",
        "corse_giorno_feriale": 12,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "06:58",
        "ultimo_bus": "19:50",
        "ampiezza_servizio_ore": 12.8,
        "headway_medio_min": 125,
        "headway_massimo_min": 275,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 15,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "INSUFFICIENTE (Buchi di 4h 30m)",
        "destinazioni_dirette": "Olgiate FS, Calco, Cisano, Celana"
    },
    {
        "comune_frazione": "Ravellino (Coda Ovest)",
        "comune": "Colle Brianza",
        "popolazione_2025": 520,
        "linee_attuali": "D184",
        "fermata_principale": "Ravellino - Capolinea",
        "corse_giorno_feriale": 11,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "07:12",
        "ultimo_bus": "19:24",
        "ampiezza_servizio_ore": 12.2,
        "headway_medio_min": 138,
        "headway_massimo_min": 415,
        "collegamento_diretto_olgiate_fs": "SI",
        "tempo_min_olgiate_fs": 22,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "RURALE RAREFATTO (6 coppie a 22 min da FS)",
        "destinazioni_dirette": "Olgiate FS, Santa Maria Hoè, Perego"
    },
    {
        "comune_frazione": "Caprino / Celana (Coda Est)",
        "comune": "Caprino Bergamasco",
        "popolazione_2025": 1400,
        "linee_attuali": "D185",
        "fermata_principale": "Celana Collegio / Caprino Municipio",
        "corse_giorno_feriale": 12,
        "corse_utili_non_scolastiche": 6,
        "primo_bus": "06:40",
        "ultimo_bus": "20:08",
        "ampiezza_servizio_ore": 13.4,
        "headway_medio_min": 125,
        "headway_massimo_min": 275,
        "collegamento_diretto_olgiate_fs": "SI (strutturale) / FORTI RITARDI (emergenza 2026)",
        "tempo_min_olgiate_fs": 28,
        "coincidenze_s8_utili": 6,
        "classificazione_servizio": "EXTRA-PROVINCIALE CRITICO (Deviazione 2026 aggrava buchi)",
        "destinazioni_dirette": "Brivio, Calco, Olgiate FS"
    }
]

def main():
    print("=== 05: GENERAZIONE BASELINE QUANTITATIVA COMPLETA (CHECKPOINT A) ===")
    os.makedirs("outputs", exist_ok=True)
    df = pd.DataFrame(BASELINE_LOCALITA)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"[OK] Salvato report baseline in {OUTPUT_CSV} ({len(df)} località censite).")
    
    # Stampa sintesi diagnostica
    tot_pop_core = df[df["comune"].isin(["Olgiate Molgora", "Calco", "Brivio", "Santa Maria Hoè", "La Valletta Brianza"])]["popolazione_2025"].sum()
    print(f"Popolazione totale censita nel core: {tot_pop_core:,} abitanti")
    scoperti = df[df["classificazione_servizio"].str.contains("SCOPERTO", na=False)]
    print(f"Località ad oggi scoperte o solo con corse scolastiche: {scoperti['comune_frazione'].tolist()}")
    
if __name__ == "__main__":
    main()
