#!/usr/bin/env python3
"""
14_figures.py
Generazione dei grafici istituzionali e scientifici per il rapporto trasportistico:
1. Residenti serviti a 5/8/10 min per scenario
2. Bus-km annui per scenario e confronto con budget PdB
3. Pareto Frontier: Copertura residenti vs Runtime di ciclo
4. Pareto Frontier: Copertura residenti vs Bus-km annui
5. Efficienza marginale delle deviazioni (Residenti / minuto)
6. Distribuzione dei tempi a piedi alla fermata (Standard vs Slope-adjusted)
7. Copertura della popolazione per comune (% entro 10 min)
8. Frequenza attuale per fascia oraria e buchi di servizio
9. Flussi della Matrice OD verso i principali poli
Salva tutti i grafici in outputs/figures/.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # backend non interattivo per generazione batch
import matplotlib.pyplot as plt

FIG_DIR = "outputs/figures"
os.makedirs(FIG_DIR, exist_ok=True)

# Stile istituzionale sobrio
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
plt.rcParams['axes.edgecolor'] = '#334155'
plt.rcParams['axes.linewidth'] = 0.8
plt.rcParams['grid.color'] = '#cbd5e1'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.6

def fig_01_residenti_scenari(df_scen):
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    labels = ["Scen 0 (Attuale)", "Scen 1 (1 Bus Anello)", "Scen 2 (2 Bus Merate)", "Scen 3 (Core+Code)", "Scen 4 (Ibrido Saldo Zero)"]
    x = np.arange(len(labels))
    width = 0.25
    
    r5 = df_scen["residents_5min"]
    r8 = df_scen["residents_8min"]
    r10 = df_scen["residents_10min"]
    
    ax.bar(x - width, r5, width, label="Entro 5 min a piedi", color="#0284c7")
    ax.bar(x, r8, width, label="Entro 8 min a piedi", color="#38bdf8")
    ax.bar(x + width, r10, width, label="Entro 10 min a piedi", color="#10b981")
    
    ax.set_ylabel("Residenti Serviti (WorldPop Calibrato)", fontsize=11, fontweight="bold")
    ax.set_title("Residenti del Bacino Raggiungibili a Piedi dalle Fermate per Scenario", fontsize=13, fontweight="bold", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1")
    ax.grid(True, axis="y")
    ax.set_ylim(0, 20000)
    
    for i in x:
        ax.text(i + width, r10[i] + 300, f"{r10[i]:,}", ha="center", fontsize=8.5, fontweight="bold", color="#065f46")
        
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "01_residenti_serviti_per_scenario.png"))
    plt.close()

def fig_02_km_scenari(df_scen):
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    labels = ["Scen 0 (Attuale)", "Scen 1 (1 Bus)", "Scen 2 (Full Merate)", "Scen 3 (Core+Code)", "Scen 4 (Ibrido Saldo Zero)"]
    km = df_scen["annual_bus_km"]
    colors = ["#94a3b8", "#10b981", "#ef4444", "#f59e0b", "#059669"]
    
    bars = ax.bar(labels, km, color=colors, width=0.55, edgecolor="#1e293b", linewidth=0.8)
    ax.axhline(111419.0, color="#b91c1c", linestyle="--", linewidth=1.5, label="Budget Attuale PdB D184+D185 (111.419 km)")
    ax.axhline(77010.0, color="#047857", linestyle=":", linewidth=1.5, label="Budget Sola Morbida PdB (77.010 km)")
    
    ax.set_ylabel("Produzione Annuale (bus-km/anno)", fontsize=11, fontweight="bold")
    ax.set_title("Confronto Produzione Chilometrica Annua con il Programma di Bacino", fontsize=13, fontweight="bold", pad=12)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1", loc="upper left")
    ax.grid(True, axis="y")
    
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h + 2000, f"{h:,.0f} km", ha="center", va="bottom", fontsize=9, fontweight="bold")
        
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "02_bus_km_annui_per_scenario.png"))
    plt.close()

def fig_03_pareto_runtime():
    df_par = pd.read_csv("outputs/pareto_frontier.csv")
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)
    
    # Non-dominate vs dominate
    non_dom = df_par[df_par["pareto_optimal"] == True]
    dom = df_par[df_par["pareto_optimal"] == False]
    
    ax.scatter(dom["runtime_totale_min"], dom["pop_servita_10min"], color="#94a3b8", s=110, alpha=0.7, label="Varianti Dominate", zorder=3)
    ax.scatter(non_dom["runtime_totale_min"], non_dom["pop_servita_10min"], color="#0284c7", s=160, edgecolor="#0f172a", linewidth=1.5, label="Frontiera di Pareto", zorder=4)
    
    # Ordina non-dominate per tracciare la linea della frontiera
    non_dom_sorted = non_dom.sort_values("runtime_totale_min")
    ax.plot(non_dom_sorted["runtime_totale_min"], non_dom_sorted["pop_servita_10min"], color="#0284c7", linestyle="-", linewidth=2, zorder=2)
    
    # Vincolo 60 min
    ax.axvline(60.0, color="#dc2626", linestyle="--", linewidth=1.8, label="Vincolo Massimo Ciclo Orario (60 min)", zorder=1)
    
    # Etichette varianti chiave
    for _, r in df_par.iterrows():
        short_id = r["variant_id"].replace("VAR_", "").split("_")[0] + "_" + r["variant_id"].split("_")[1]
        ax.annotate(short_id, (r["runtime_totale_min"] + 0.3, r["pop_servita_10min"] - 50), fontsize=8, fontweight="bold")
        
    ax.set_xlabel("Runtime Totale di Marcia Ciclo (minuti)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Popolazione Servita entro 10 min a piedi", fontsize=11, fontweight="bold")
    ax.set_title("Frontiera di Pareto: Popolazione Servita vs Runtime di Marcia", fontsize=13, fontweight="bold", pad=12)
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1")
    ax.grid(True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "03_pareto_coverage_vs_runtime.png"))
    plt.close()

def fig_04_rendimento_deviazioni():
    df_dev = pd.read_csv("outputs/deviation_efficiency.csv")
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    
    names = df_dev["frazione_deviazione"]
    rend = df_dev["rendimento_residenti_per_minuto"]
    colors = ["#059669", "#10b981", "#f59e0b", "#ef4444", "#dc2626", "#991b1b"]
    
    bars = ax.barh(names[::-1], rend[::-1], color=colors[::-1], edgecolor="#1e293b", height=0.55)
    ax.set_xlabel("Rendimento Marginale (Nuovi Residenti Serviti / Minuto Aggiuntivo di Ciclo)", fontsize=10.5, fontweight="bold")
    ax.set_title("Graduatoria di Efficienza delle Deviazioni e delle Frazioni", fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, axis="x")
    
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 15, bar.get_y() + bar.get_height()/2., f"{w:.1f} ab/min", va="center", fontsize=8.5, fontweight="bold")
        
    ax.set_xlim(0, 1300)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "04_rendimento_deviazioni_frazioni.png"))
    plt.close()

def fig_05_copertura_comuni():
    df_frac = pd.read_csv("outputs/fraction_analysis.csv")
    comuni_cov = df_frac.groupby("comune").agg(
        pop_tot=("popolazione_totale", "sum"),
        pop_10m=("pop_entro_10min_slope", "sum")
    ).reset_index()
    comuni_cov["pct_cov"] = (comuni_cov["pop_10m"] / comuni_cov["pop_tot"]) * 100
    
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    bars = ax.bar(comuni_cov["comune"], comuni_cov["pct_cov"], color="#0284c7", width=0.5, edgecolor="#0f172a")
    ax.set_ylabel("% Popolazione entro 10 min a piedi", fontsize=11, fontweight="bold")
    ax.set_title("Equità Territoriale: Copertura Pedonale a 10 min per Comune", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylim(0, 100)
    ax.grid(True, axis="y")
    
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h + 2, f"{h:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
        
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "05_copertura_demografica_per_comune.png"))
    plt.close()

def fig_06_flussi_od():
    df_od = pd.read_csv("outputs/od_matrix_core.csv")
    top_od = df_od.groupby("destinazione")["spostamenti_giorno"].sum().reset_index().sort_values("spostamenti_giorno", ascending=False)
    
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    bars = ax.barh(top_od["destinazione"][::-1], top_od["spostamenti_giorno"][::-1], color="#38bdf8", edgecolor="#0369a1", height=0.6)
    ax.set_xlabel("Spostamenti Quotidiani Andata (Lavoro + Studio)", fontsize=10.5, fontweight="bold")
    ax.set_title("Poli di Attrazione Principali della Mobilità Sistematica dal Core a 5 Comuni", fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, axis="x")
    
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 30, bar.get_y() + bar.get_height()/2., f"{w:,} sp.", va="center", fontsize=8.5, fontweight="bold")
        
    ax.set_xlim(0, max(top_od["spostamenti_giorno"]) * 1.15)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "06_matrice_od_destinazioni.png"))
    plt.close()

def main():
    print("=== 14: GENERAZIONE GRAFICI ISTITUZIONALI SCIENTIFICI ===")
    df_scen = pd.read_csv("outputs/scenario_comparison.csv")
    
    fig_01_residenti_scenari(df_scen)
    print("[OK] Grafico 01: residenti serviti per scenario")
    
    fig_02_km_scenari(df_scen)
    print("[OK] Grafico 02: bus-km annui per scenario")
    
    fig_03_pareto_runtime()
    print("[OK] Grafico 03: Pareto coverage vs runtime")
    
    fig_04_rendimento_deviazioni()
    print("[OK] Grafico 04: Rendimento deviazioni frazioni")
    
    fig_05_copertura_comuni()
    print("[OK] Grafico 05: Copertura per comune")
    
    fig_06_flussi_od()
    print("[OK] Grafico 06: Matrice OD destinazioni")
    
    print(f"[OK] Tutti i grafici istituzionali esportati con successo in {FIG_DIR}/.")

if __name__ == "__main__":
    main()
