"""
src/population_raster.py
Modulo per la gestione e calibrazione della griglia demografica ad alta risoluzione (WorldPop ~100m)
sui totali ufficiali comunali ISTAT 2025.
"""

import os
import pandas as pd
import numpy as np

# Totali ufficiali ISTAT al 1° gennaio 2025 (POSAS microdati)
ISTAT_TOTALS_2025 = {
    "Olgiate Molgora": 6332,
    "Calco": 5460,
    "Brivio": 4357,
    "La Valletta Brianza": 4656,
    "Santa Maria Hoè": 2109,
    # Esterni
    "Colle Brianza": 1720,
    "Cisano Bergamasco": 6190,
    "Caprino Bergamasco": 3080
}

def calibrate_population_grid(cells_df: pd.DataFrame) -> pd.DataFrame:
    """
    Riscala le celle di ciascun comune affinché la somma dei residenti stimati
    coincida esattamente con il totale ufficiale ISTAT 2025.
    Mantiene sia 'pop_raw' sia 'pop_calibrated'.
    """
    df = cells_df.copy()
    df["pop_calibrated"] = df["pop_raw"]
    
    for comune, istat_tot in ISTAT_TOTALS_2025.items():
        mask = df["comune"] == comune
        raw_sum = df.loc[mask, "pop_raw"].sum()
        if raw_sum > 0:
            factor = istat_tot / raw_sum
            df.loc[mask, "pop_calibrated"] = df.loc[mask, "pop_raw"] * factor
        else:
            print(f"[WARN] Nessuna cella trovata per {comune}!")
            
    df["pop_calibrated"] = df["pop_calibrated"].round(2)
    return df
