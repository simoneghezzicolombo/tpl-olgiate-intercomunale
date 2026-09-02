#!/usr/bin/env python3
"""
Simulatore di Esercizio e Bilancio Chilometrico - Linea 8 Olgiate Molgora
Supporta simulazione a 1 Bus, 2 Bus (Merate Style Bidirezionale) e Ibrido Punta/Morbida.
"""

import csv
import json
import os

PDB_BUDGET_TOTALE = 111419.0
PDB_BUDGET_MORBIDA = 77010.0
PDB_BUDGET_PUNTA = 34408.0
GIORNI_ESERCIZIO = 303

# Treni S8 a Olgiate-Calco-Brivio
TRENI_S8 = {
    'to_milano': [8, 38],    # minuti di partenza
    'from_milano': [21, 51], # minuti di arrivo
    'to_lecco': [22, 52],    # minuti di partenza
    'from_lecco': [7, 37]     # minuti di arrivo
}

def genera_orario_scenario_0():
    """Genera orario per Scenario 0 (1 Bus, 13 cicli, percorsi attuali)"""
    corse = []
    # Dalle 06:30 alle 19:30
    for hour in range(6, 20):
        # Ramo Ovest a :30
        partenza_ovest = f"{hour:02d}:30"
        arrivo_sm = f"{hour:02d}:43"
        ritorno_fs_ovest = f"{hour:02d}:55"
        corse.append({
            'ora_slot': hour,
            'ramo': 'Ovest',
            'verso': 'Spola A/R',
            'percorso': 'FS -> Perego -> S.Maria Hoè -> FS',
            'partenza_fs': partenza_ovest,
            'giro_boa': arrivo_sm,
            'arrivo_fs': ritorno_fs_ovest,
            'tempo_min': 25,
            'km': 10.4,
            'coincidenza_s8_milano': f"{hour:02d}:08 / {(hour+1):02d}:08",
            'coincidenza_s8_lecco': f"{hour:02d}:22 / {hour:02d}:52"
        })
        
        # Ramo Est a :00 (dalle 07:00 alle 19:00)
        if hour < 19:
            partenza_est = f"{(hour+1):02d}:00"
            arrivo_brivio = f"{(hour+1):02d}:15"
            ritorno_fs_est = f"{(hour+1):02d}:30"
            corse.append({
                'ora_slot': hour,
                'ramo': 'Est',
                'verso': 'Spola A/R',
                'percorso': 'FS -> Calco -> Beverate -> Brivio -> FS',
                'partenza_fs': partenza_est,
                'giro_boa': arrivo_brivio,
                'arrivo_fs': ritorno_fs_est,
                'tempo_min': 30,
                'km': 12.0,
                'coincidenza_s8_milano': f"{(hour+1):02d}:38",
                'coincidenza_s8_lecco': f"{(hour+1):02d}:52"
            })
    return corse

def genera_orario_bidirezionale_merate(num_bus=2):
    """
    Genera orario in stile Merate (D201 / D202):
    Bus 1 = Senso Orario continuo (CW)
    Bus 2 = Senso Antiorario continuo (CCW)
    """
    corse = []
    km_anello = 19.8  # con Mondonico e Arlate
    
    for hour in range(6, 20):
        # BUS 1: Senso Orario (CW)
        # 06:30 Ovest Orario (FS -> Rovagnate -> Perego -> SM -> Mondonico -> FS: 26 min)
        # 07:00 Est Orario (FS -> Calco -> Beverate -> Brivio -> Arlate -> FS: 29 min)
        corse.append({
            'ora_slot': hour,
            'bus_id': 'Bus 1 (Orario CW)',
            'verso': 'Senso Orario (CW)',
            'tratta_1': f"{hour:02d}:30 FS -> Perego -> S.Maria -> Mondonico -> {hour:02d}:56 FS",
            'tratta_2': f"{(hour+1):02d}:00 FS -> Calco -> Beverate -> Brivio -> Arlate -> {(hour+1):02d}:29 FS",
            'km_ciclo': km_anello,
            'tempo_totale_min': 55
        })
        
        if num_bus == 2:
            # BUS 2: Senso Antiorario (CCW)
            # 06:30 Est Antiorario (FS -> Arlate -> Brivio -> Beverate -> Calco -> FS: 29 min)
            # 07:00 Ovest Antiorario (FS -> Mondonico -> SM -> Perego -> Rovagnate -> FS: 26 min)
            corse.append({
                'ora_slot': hour,
                'bus_id': 'Bus 2 (Antiorario CCW)',
                'verso': 'Senso Antiorario (CCW)',
                'tratta_1': f"{hour:02d}:30 FS -> Arlate -> Brivio -> Beverate -> Calco -> {hour:02d}:59 FS",
                'tratta_2': f"{(hour+1):02d}:00 FS -> Mondonico -> S.Maria -> Perego -> Rovagnate -> {(hour+1):02d}:26 FS",
                'km_ciclo': km_anello,
                'tempo_totale_min': 55
            })
            
    return corse

def calcola_bilancio(km_ciclo, cicli_giorno):
    cicli_anno = cicli_giorno * GIORNI_ESERCIZIO
    km_anno = cicli_anno * km_ciclo
    
    # Valutazione semaforo
    soglia_verde = PDB_BUDGET_MORBIDA / (13 * GIORNI_ESERCIZIO) # 19.55 km
    soglia_gialla = PDB_BUDGET_TOTALE / (13 * GIORNI_ESERCIZIO) # 28.29 km
    
    delta_totale = km_anno - PDB_BUDGET_TOTALE
    delta_pct = (delta_totale / PDB_BUDGET_TOTALE) * 100
    
    if km_anno <= PDB_BUDGET_MORBIDA:
        stato = 'VERDE'
        descrizione = 'Coperto al 100% dalla sola morbida; preservate tutte le corse di punta.'
    elif km_anno <= PDB_BUDGET_TOTALE:
        stato = 'GIALLO'
        descrizione = 'Coperto dal budget complessivo D184+D185 a saldo zero o con risparmio.'
    else:
        stato = 'ROSSO'
        descrizione = f'Richiede risorse integrative ({delta_totale:+,.1f} km/anno, {delta_pct:+.1f}%).'
        
    return {
        'km_ciclo': km_ciclo,
        'cicli_giorno': cicli_giorno,
        'cicli_anno': cicli_anno,
        'km_anno': round(km_anno, 1),
        'budget_pdb_totale': PDB_BUDGET_TOTALE,
        'budget_pdb_morbida': PDB_BUDGET_MORBIDA,
        'delta_km_vs_pdb': round(delta_totale, 1),
        'delta_pct_vs_pdb': round(delta_pct, 2),
        'stato_semaforo': stato,
        'giudizio': descrizione
    }

def main():
    print("=== SIMULAZIONE ESERCIZIO LINEA 8 OLGIATE MOLGORA ===")
    
    # 1. Bilancio Scenario 0
    scen0_bil = calcola_bilancio(km_ciclo=22.4, cicli_giorno=13)
    print("\n--- SCENARIO 0 (Baseline 1 Bus, 13 cicli) ---")
    print(f"Km per ciclo: {scen0_bil['km_ciclo']} km")
    print(f"Cicli/anno: {scen0_bil['cicli_anno']}")
    print(f"Km/anno prodotti: {scen0_bil['km_anno']} km")
    print(f"Semaforo: {scen0_bil['stato_semaforo']} - {scen0_bil['giudizio']}")
    
    # 2. Bilancio Anello Ottimizzato 1 Bus
    opt1_bil = calcola_bilancio(km_ciclo=19.8, cicli_giorno=13)
    print("\n--- SCENARIO 1 (Anello con Mondonico e Arlate, 1 Bus, 13 cicli) ---")
    print(f"Km per ciclo: {opt1_bil['km_ciclo']} km")
    print(f"Km/anno prodotti: {opt1_bil['km_anno']} km")
    print(f"Semaforo: {opt1_bil['stato_semaforo']} - {opt1_bil['giudizio']}")
    
    # 3. Bilancio Stile Merate 2 Bus Contemporanei (Orario + Antiorario continuo)
    merate2_bil = calcola_bilancio(km_ciclo=19.8, cicli_giorno=26)
    print("\n--- SCENARIO 2 (Full Merate Style: 2 Bus Orario + Antiorario Continuo, 26 cicli) ---")
    print(f"Km per ciclo: {merate2_bil['km_ciclo']} km")
    print(f"Km/anno prodotti: {merate2_bil['km_anno']} km")
    print(f"Semaforo: {merate2_bil['stato_semaforo']} - {merate2_bil['giudizio']}")
    
    # 4. Bilancio Scenario C Ibrido (2 Bus in punta 6h + 1 Bus in morbida 7h = 19 cicli/giorno)
    ibrido_bil = calcola_bilancio(km_ciclo=19.5, cicli_giorno=19)
    print("\n--- SCENARIO C (Ibrido Ottimizzato: 2 Bus in punta + 1 Bus in morbida = 19 cicli/giorno) ---")
    print(f"Km per ciclo: {ibrido_bil['km_ciclo']} km")
    print(f"Km/anno prodotti: {ibrido_bil['km_anno']} km")
    print(f"Semaforo: {ibrido_bil['stato_semaforo']} - {ibrido_bil['giudizio']}")
    
    # Esporta risultati in data/simulazione_scenari.json
    scenari = {
        'scenario_0_baseline': scen0_bil,
        'scenario_1_anello_ottimizzato_1bus': opt1_bil,
        'scenario_2_full_merate_2bus': merate2_bil,
        'scenario_3_ibrido_punta_morbida': ibrido_bil
    }
    with open('data/simulazione_scenari.json', 'w', encoding='utf-8') as f:
        json.dump(scenari, f, indent=2)
    print("\nRisultati salvati con successo in data/simulazione_scenari.json!")

if __name__ == '__main__':
    main()
