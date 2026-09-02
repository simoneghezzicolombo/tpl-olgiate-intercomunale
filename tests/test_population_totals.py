"""
tests/test_population_totals.py
Verifica che la popolazione della griglia calibrata nei 5 comuni coincida esattamente
con i dati ufficiali ISTAT POSAS al 1° gennaio 2025 (22.914 residenti totali).
"""

import os
import pandas as pd
import pytest

DEMO_CSV = "data/processed/demografia_comunale_istat_2025.csv"
GRID_CSV = "data/processed/population_grid_calibrated.csv"

ISTAT_ATTESO = {
    "Olgiate Molgora": 6332,
    "Calco": 5460,
    "Brivio": 4357,
    "La Valletta Brianza": 4656,
    "Santa Maria Hoè": 2109
}
TOTALE_CORE_ATTESO = 22914

def test_demografia_comunale_quadratura():
    assert os.path.exists(DEMO_CSV), f"File {DEMO_CSV} non trovato!"
    df = pd.read_csv(DEMO_CSV)
    
    for comune, pop_attesa in ISTAT_ATTESO.items():
        sub = df[df["comune"] == comune]
        assert len(sub) == 1, f"Comune {comune} non presente o duplicato in {DEMO_CSV}"
        pop_calc = sub["pop_calibrated"].values[0]
        assert abs(pop_calc - pop_attesa) <= 1.0, f"Discrepanza per {comune}: {pop_calc} != {pop_attesa}"

def test_popolazione_totale_core():
    assert os.path.exists(GRID_CSV), f"File {GRID_CSV} non trovato!"
    df_grid = pd.read_csv(GRID_CSV)
    
    sub_core = df_grid[df_grid["comune"].isin(ISTAT_ATTESO.keys())]
    tot_calcolato = sub_core["pop_calibrated"].sum()
    assert abs(tot_calcolato - TOTALE_CORE_ATTESO) <= 1.0, f"Totale core errato: {tot_calcolato} != {TOTALE_CORE_ATTESO}"
