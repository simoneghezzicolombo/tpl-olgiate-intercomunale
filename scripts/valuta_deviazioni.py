#!/usr/bin/env python3
"""
Valutatore di Rendimento Trasportistico delle Frazioni e Deviazioni
Formula: Rendimento = Delta_Popolazione_Servita / Delta_Minuti_Ciclo
Vincolo rigido: Ciclo totale <= 60 minuti.
"""

import csv
import sys

def valuta_deviazione(nome, pop_worldpop, delta_min, tempo_base_ciclo=55.0, is_anello=True):
    nuovo_ciclo = tempo_base_ciclo + delta_min
    margine_fs = 60.0 - nuovo_ciclo
    
    if delta_min == 0:
        rendimento = float('inf')
        rend_str = "Infinito (0 min di penalità)"
    else:
        rendimento = pop_worldpop / delta_min
        rend_str = f"{rendimento:.1f} ab./min"
        
    fattibile = nuovo_ciclo <= 60.0
    
    return {
        'nome': nome,
        'popolazione': pop_worldpop,
        'delta_min': delta_min,
        'tempo_ciclo': nuovo_ciclo,
        'margine_fs': margine_fs,
        'rendimento': rendimento,
        'rendimento_str': rend_str,
        'fattibile_60min': fattibile,
        'is_anello': is_anello
    }

def main():
    print("=== VALUTAZIONE SOCIO-ECONOMICA DEVIAZIONI E FRAZIONI ===")
    print("Formula: Rendimento = Popolazione WorldPop (5-10 min) / Minuti aggiuntivi al ciclo")
    print("Vincolo: Ciclo Totale <= 60 min (Tempo base Scenario 0 = 55 min, Buffer minimo = 5 min)\n")
    
    candidati = [
        ("Perego (La Valletta B.za)", 1850, 0.0, True),
        ("Beverate (Brivio)", 1600, 0.0, True),
        ("Mondonico / Monticello (Olgiate)", 920, 2.5, True),
        ("Arlate (Calco)", 1150, 3.5, True),
        ("Calco Superiore (Calco)", 580, 4.5, False),
        ("San Zeno (Olgiate)", 710, 7.5, False),
        ("Ravellino (Colle Brianza)", 520, 19.0, False),
        ("Caprino / Celana", 1400, 20.0, False)
    ]
    
    risultati = [valuta_deviazione(c[0], c[1], c[2], is_anello=c[3]) for c in candidati]
    # Ordina per rendimento decrescente
    risultati_ordinati = sorted(risultati, key=lambda x: x['rendimento'], reverse=True)
    
    print(f"{'Frazione / Variante':<28} | {'Pop. (ab)':<9} | {'Delta t':<8} | {'Ciclo Tot':<10} | {'Buffer FS':<9} | {'Rendimento':<18} | {'Fattibile'}")
    print("-" * 105)
    
    for r in risultati_ordinati:
        fatt_str = "SI (OK)" if r['fattibile_60min'] else "NO (Sfora 60')"
        print(f"{r['nome']:<28} | {r['popolazione']:<9} | {r['delta_min']:<8.1f} | {r['tempo_ciclo']:<10.1f} | {r['margine_fs']:<9.1f} | {r['rendimento_str']:<18} | {fatt_str}")

    print("\nConclusioni Analitiche:")
    print("1. Perego e Beverate: confermati a costo zero (rendimento infinito).")
    print("2. Mondonico e Arlate: rendimento altissimo (>300 ab./min) se inseriti come rami di chiusura ad anello.")
    print("3. San Zeno, Ravellino, Caprino: sforano il ciclo di 60 min, da servire con corse dedicate o TPL a chiamata.")

if __name__ == '__main__':
    main()
