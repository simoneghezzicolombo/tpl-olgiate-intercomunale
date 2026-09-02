"""
tests/test_cycle_times.py
Verifica che i tempi di marcia, i tempi di ciclo e i buffer di recupero
rispettino i vincoli progettuali dichiarati (runtime 55 min per la variante raccomandata,
buffer >= 5 min, rispetto del vincolo di 60 min per le varianti fattibili).
"""

import os
import pandas as pd
import pytest

VARIANTS_CSV = "outputs/route_variants.csv"
SCENARIOS_CSV = "outputs/scenario_comparison.csv"

def test_raccomandata_cycle_time():
    assert os.path.exists(VARIANTS_CSV), f"{VARIANTS_CSV} mancante!"
    df = pd.read_csv(VARIANTS_CSV)
    
    var4 = df[df["variant_id"] == "VAR_04_DOPPIO_ANELLO_INTEGRATO"]
    assert len(var4) == 1, "VAR_04 non trovata in route_variants.csv!"
    
    runtime = var4["runtime_totale_min"].values[0]
    buffer_min = var4["buffer_recupero_fs_min"].values[0]
    ciclo = var4["ciclo_programmato_min"].values[0]
    
    assert runtime == 55.0, f"Runtime VAR_04 deve essere esattamente 55.0 min (trovato {runtime})"
    assert buffer_min >= 5.0, f"Buffer a FS deve essere >= 5.0 min (trovato {buffer_min})"
    assert runtime + buffer_min == ciclo, f"Somma runtime + buffer ({runtime + buffer_min}) diversa da ciclo ({ciclo})"
    assert ciclo == 60.0, f"Ciclo programmato deve essere esattamente 60 min (trovato {ciclo})"

def test_bocciate_exceed_cycle():
    df = pd.read_csv(VARIANTS_CSV)
    
    # San Zeno, Ravellino e Caprino devono sforare i 60 minuti
    var6 = df[df["variant_id"] == "VAR_06_DOPPIO_ANELLO_SAN_ZENO"].iloc[0]
    var7 = df[df["variant_id"] == "VAR_07_DOPPIO_ANELLO_CODA_RAVELLINO"].iloc[0]
    var8 = df[df["variant_id"] == "VAR_08_DOPPIO_ANELLO_CODA_CAPRINO"].iloc[0]
    
    assert var6["runtime_totale_min"] > 60.0, f"VAR_06 doveva sforare 60 min (trovato {var6['runtime_totale_min']})"
    assert var7["runtime_totale_min"] > 60.0, f"VAR_07 doveva sforare 60 min (trovato {var7['runtime_totale_min']})"
    assert var8["runtime_totale_min"] > 60.0, f"VAR_08 doveva sforare 60 min (trovato {var8['runtime_totale_min']})"
