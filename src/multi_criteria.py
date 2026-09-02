"""
src/multi_criteria.py
Modulo per l'analisi multi-obiettivo e la determinazione della Pareto Frontier.
Evita formule con pesi arbitrari a priori: identifica le soluzioni dominanti e non-dominate
su trade-off dimensionali:
- Massimizzare: Copertura Popolazione, POI, Domanda OD, Equità
- Minimizzare: Runtime di ciclo, Km/ciclo, Mezzi richiesti, Rischio viario
"""

import pandas as pd
import numpy as np
from typing import List, Dict

def identify_pareto_frontier(variants_df: pd.DataFrame, 
                             maximize_cols: List[str] = ["pop_servita_10min", "poi_serviti", "od_flusso_intercettato"],
                             minimize_cols: List[str] = ["km_totali", "runtime_totale_min"]) -> pd.DataFrame:
    """
    Identifica le varianti che appartengono alla Frontiera di Pareto.
    Una variante A domina B se è >= su tutti gli obiettivi di massimizzazione,
    <= su tutti gli obiettivi di minimizzazione, e strettamente migliore su almeno uno.
    """
    df = variants_df.copy()
    n = len(df)
    is_dominated = [False] * n
    
    for i in range(n):
        for j in range(n):
            if i != j:
                # Controlla se j domina i
                j_better_or_equal = True
                j_strictly_better = False
                
                # Massimizzazione
                for col in maximize_cols:
                    val_i = df.iloc[i][col]
                    val_j = df.iloc[j][col]
                    if val_j < val_i:
                        j_better_or_equal = False
                        break
                    elif val_j > val_i:
                        j_strictly_better = True
                        
                if not j_better_or_equal:
                    continue
                    
                # Minimizzazione
                for col in minimize_cols:
                    val_i = df.iloc[i][col]
                    val_j = df.iloc[j][col]
                    if val_j > val_i:
                        j_better_or_equal = False
                        break
                    elif val_j < val_i:
                        j_strictly_better = True
                        
                if j_better_or_equal and j_strictly_better:
                    is_dominated[i] = True
                    break
                    
    df["pareto_optimal"] = [not d for d in is_dominated]
    return df

def sensitivity_analysis(variants_df: pd.DataFrame) -> pd.DataFrame:
    """
    Esegue una sensitivity analysis variando i pesi per testare la robustezza delle soluzioni:
    - Profilo 1: Focus Massima Copertura Demografica
    - Profilo 2: Focus Minimo Costo Chilometrico / Risorse
    - Profilo 3: Focus Massima Velocità / Minimo Tempo Ciclo
    - Profilo 4: Equità Territoriale e Bilanciamento
    """
    df = variants_df.copy()
    
    # Normalizzazione min-max 0-1
    def norm(col, invert=False):
        c = df[col].astype(float)
        min_v, max_v = c.min(), c.max()
        if max_v == min_v:
            return pd.Series(1.0, index=df.index)
        res = (c - min_v) / (max_v - min_v)
        return 1.0 - res if invert else res

    pop_n = norm("pop_servita_10min", invert=False)
    km_n = norm("km_totali", invert=True)
    time_n = norm("runtime_totale_min", invert=True)
    poi_n = norm("poi_serviti", invert=False)

    df["score_copertura"] = (pop_n * 0.5 + poi_n * 0.3 + km_n * 0.1 + time_n * 0.1).round(3)
    df["score_risorse_km"] = (km_n * 0.5 + time_n * 0.3 + pop_n * 0.2).round(3)
    df["score_velocita_tempo"] = (time_n * 0.5 + km_n * 0.3 + pop_n * 0.2).round(3)
    df["score_bilanciato"] = (pop_n * 0.3 + km_n * 0.25 + time_n * 0.25 + poi_n * 0.2).round(3)
    
    return df
