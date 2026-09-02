"""
src/spatial_network.py
Modulo per la costruzione del grafo pedonale, calcolo delle isocrone e correzione altimetrica (slope-adjusted).
Implementa la Tobler's Hiking Function calibrata su standard TPL:
v(s) = v0 * exp(-3.5 * |s + 0.05|)
con s = pendenza (dislivello / distanza).
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

# Velocità pedonale standard in piano (4.8 km/h = 80 m/min)
V_BASE_FLAT_MPM = 80.0 # metri al minuto

def tobler_walking_speed_mpm(slope: float, v_base: float = V_BASE_FLAT_MPM) -> float:
    """
    Calcola la velocità pedonale corretta per la pendenza (metri/minuto).
    slope = pendenza (es. +0.10 per salita 10%, -0.05 per leggera discesa).
    """
    # Tobler normalized: picco a -0.05 (leggera discesa), penalizzazione esponenziale per salita
    factor = np.exp(-3.5 * np.abs(slope + 0.05))
    # Normalizzato per avere factor=1 su s=0 (piano)
    factor_flat = np.exp(-3.5 * 0.05)
    normalized_factor = factor / factor_flat
    
    # Limiti fisici: non inferiore a 25 m/min (1.5 km/h) su pendenze estreme
    speed = np.clip(v_base * normalized_factor, 25.0, 105.0)
    return float(speed)

def compute_walk_time(dist_m: float, delta_elev_m: float) -> Tuple[float, float]:
    """
    Ritorna:
    - tempo standard (in piano a 4.8 km/h): dist_m / 80 m/min
    - tempo slope-adjusted con altimetria Tobler
    """
    t_std = dist_m / V_BASE_FLAT_MPM
    
    if dist_m < 5.0:
        return round(t_std, 2), round(t_std, 2)
        
    slope = delta_elev_m / dist_m
    v_slope = tobler_walking_speed_mpm(slope, V_BASE_FLAT_MPM)
    t_slope = dist_m / v_slope
    
    return round(t_std, 2), round(t_slope, 2)

def calculate_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza su rete (con coefficiente di tortuosità/detour factor 1.25 per strade locali)."""
    d_euclid = np.hypot((lat2 - lat1) * 111139.0, (lon2 - lon1) * 77700.0)
    # Detour factor pedonale standard (1.25 su griglia urbana/suburbana)
    d_network = d_euclid * 1.25
    return float(d_network)
