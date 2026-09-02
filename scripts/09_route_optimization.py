#!/usr/bin/env python3
"""
09_route_optimization.py
Analisi multi-obiettivo, identificazione della Frontiera di Pareto e Sensitivity Analysis
sulle 8 varianti di tracciato generate.
Salva:
- outputs/pareto_frontier.csv
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from src.multi_criteria import identify_pareto_frontier, sensitivity_analysis

VARIANTS_CSV = "outputs/route_variants.csv"
OUT_PARETO_CSV = "outputs/pareto_frontier.csv"

def main():
    print("=== 09: OTTIMIZZAZIONE MULTI-OBIETTIVO E PARETO FRONTIER ===")
    if not os.path.exists(VARIANTS_CSV):
        print(f"Errore: {VARIANTS_CSV} mancante! Esegui prima 08_candidate_routes.py.")
        sys.exit(1)
        
    df_var = pd.read_csv(VARIANTS_CSV)
    
    # 1. Calcolo Frontiera di Pareto
    # Obiettivi di massimizzazione: pop_servita_10min, poi_serviti, od_flusso_intercettato
    # Obiettivi di minimizzazione: km_totali, runtime_totale_min
    df_pareto = identify_pareto_frontier(
        df_var,
        maximize_cols=["pop_servita_10min", "poi_serviti", "od_flusso_intercettato"],
        minimize_cols=["km_totali", "runtime_totale_min"]
    )
    
    # 2. Sensitivity Analysis con diversi profili di priorità
    df_sens = sensitivity_analysis(df_pareto)
    
    df_sens.to_csv(OUT_PARETO_CSV, index=False)
    print(f"[OK] Salvata analisi Pareto e sensitivity in {OUT_PARETO_CSV}.")
    
    print("\n--- RISULTATI FRONTIERA DI PARETO ---")
    pareto_vars = df_sens[df_sens["pareto_optimal"] == True]
    print(pareto_vars[["variant_id", "nome", "km_totali", "runtime_totale_min", "pop_servita_10min", "pareto_optimal"]].to_string(index=False))
    
    print("\n--- SENSITIVITY ANALYSIS (SCORE PONDERATI 0-1) ---")
    print(df_sens[["variant_id", "score_copertura", "score_risorse_km", "score_velocita_tempo", "score_bilanciato"]].to_string(index=False))
    
    best_balanced = df_sens.loc[df_sens["score_bilanciato"].idxmax()]
    print(f"\nVariante con punteggio bilanciato più alto: {best_balanced['variant_id']} ({best_balanced['nome']}) con score {best_balanced['score_bilanciato']}")

if __name__ == "__main__":
    main()
