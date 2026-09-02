#!/usr/bin/env python3
"""
07_poi_analysis.py
Mappatura, categorizzazione e attribuzione pesi dei generatori di domanda (POI)
nel territorio core dei 5 comuni (Olgiate, Calco, Brivio, La Valletta, Santa Maria Hoè).
Include scuole, sanità, RSA, municipi, commercio, industria, sport e servizi civici.
Salva data/processed/poi_dataset.csv e outputs/poi_summary_by_category.csv.
"""

import os
import sys
import pandas as pd

OUT_POI_CSV = "data/processed/poi_dataset.csv"
OUT_SUMMARY_CSV = "outputs/poi_summary_by_category.csv"

# Database strutturato dei POI del bacino con pesi gerarchici
POIS = [
    # SCUOLE E ISTRUZIONE (Peso 10 - attrattività oraria e picchi)
    {"nome": "Scuola Media Statale E. Ghezzi", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Istruzione", "peso": 10, "lat": 45.7335, "lon": 9.4005},
    {"nome": "Scuola Primaria Olgiate Molgora", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Istruzione", "peso": 8, "lat": 45.7342, "lon": 9.4018},
    {"nome": "Scuola Primaria di Calco", "comune": "Calco", "frazione": "Calco Centro", "categoria": "Istruzione", "peso": 8, "lat": 45.7258, "lon": 9.4132},
    {"nome": "Scuola Primaria di Beverate", "comune": "Brivio", "frazione": "Beverate", "categoria": "Istruzione", "peso": 8, "lat": 45.7355, "lon": 9.4252},
    {"nome": "Scuola Primaria di Brivio", "comune": "Brivio", "frazione": "Brivio Centro", "categoria": "Istruzione", "peso": 8, "lat": 45.7435, "lon": 9.4430},
    {"nome": "Scuola Primaria La Valletta Brianza", "comune": "La Valletta Brianza", "frazione": "Perego", "categoria": "Istruzione", "peso": 8, "lat": 45.7428, "lon": 9.3638},
    {"nome": "Scuola Primaria Santa Maria Hoè", "comune": "Santa Maria Hoè", "frazione": "Santa Maria Hoè Centro", "categoria": "Istruzione", "peso": 7, "lat": 45.7460, "lon": 9.3742},
    {"nome": "Asilo Nido e Infanzia Sommi Picenardi", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Istruzione", "peso": 6, "lat": 45.7328, "lon": 9.4022},

    # SANITÀ, RSA E ASSISTENZA (Peso 9 - mobilità debole, anziani, visite)
    {"nome": "RSA Casa Famiglia di Olgiate Molgora", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Sanita_Assistenza", "peso": 9, "lat": 45.7312, "lon": 9.3985},
    {"nome": "Poliambulatorio e Medici di Medicina Generale Calco", "comune": "Calco", "frazione": "Calco Centro", "categoria": "Sanita_Assistenza", "peso": 8, "lat": 45.7265, "lon": 9.4120},
    {"nome": "Farmacia Comunale Olgiate Molgora (FS)", "comune": "Olgiate Molgora", "frazione": "Olgiate Stazione", "categoria": "Sanita_Assistenza", "peso": 7, "lat": 45.7318, "lon": 9.4028},
    {"nome": "Farmacia di Brivio Centro", "comune": "Brivio", "frazione": "Brivio Centro", "categoria": "Sanita_Assistenza", "peso": 7, "lat": 45.7442, "lon": 9.4445},
    {"nome": "Farmacia di Rovagnate", "comune": "La Valletta Brianza", "frazione": "Rovagnate", "categoria": "Sanita_Assistenza", "peso": 7, "lat": 45.7392, "lon": 9.3688},
    {"nome": "Farmacia Santa Maria Hoè", "comune": "Santa Maria Hoè", "frazione": "Santa Maria Hoè Centro", "categoria": "Sanita_Assistenza", "peso": 7, "lat": 45.7452, "lon": 9.3738},
    {"nome": "Centro Prelievi e Assistenza Brivio", "comune": "Brivio", "frazione": "Brivio Centro", "categoria": "Sanita_Assistenza", "peso": 8, "lat": 45.7438, "lon": 9.4428},

    # ISTITUZIONI E SERVIZI PUBBLICI (Peso 8 - pratiche, anagrafe, cultura)
    {"nome": "Municipio di Olgiate Molgora", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Istituzioni", "peso": 8, "lat": 45.7338, "lon": 9.4011},
    {"nome": "Municipio di Calco", "comune": "Calco", "frazione": "Calco Centro", "categoria": "Istituzioni", "peso": 8, "lat": 45.7260, "lon": 9.4126},
    {"nome": "Municipio di Brivio", "comune": "Brivio", "frazione": "Brivio Centro", "categoria": "Istituzioni", "peso": 8, "lat": 45.7445, "lon": 9.4439},
    {"nome": "Municipio di La Valletta Brianza", "comune": "La Valletta Brianza", "frazione": "Perego", "categoria": "Istituzioni", "peso": 8, "lat": 45.7430, "lon": 9.3645},
    {"nome": "Municipio di Santa Maria Hoè", "comune": "Santa Maria Hoè", "frazione": "Santa Maria Hoè Centro", "categoria": "Istituzioni", "peso": 8, "lat": 45.7455, "lon": 9.3735},
    {"nome": "Biblioteca Comunale Olgiate Molgora", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Istituzioni", "peso": 6, "lat": 45.7340, "lon": 9.4015},
    {"nome": "Ufficio Postale Olgiate Molgora", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Istituzioni", "peso": 7, "lat": 45.7325, "lon": 9.4020},
    {"nome": "Ufficio Postale Brivio", "comune": "Brivio", "frazione": "Brivio Centro", "categoria": "Istituzioni", "peso": 7, "lat": 45.7440, "lon": 9.4435},
    {"nome": "Ufficio Postale Rovagnate", "comune": "La Valletta Brianza", "frazione": "Rovagnate", "categoria": "Istituzioni", "peso": 7, "lat": 45.7390, "lon": 9.3692},

    # COMMERCIO E AREE COMMERCIALI (Peso 7 - shopping quotidiano, alimentari)
    {"nome": "Supermercato Conad Olgiate Molgora", "comune": "Olgiate Molgora", "frazione": "Olgiate Stazione", "categoria": "Commercio", "peso": 8, "lat": 45.7305, "lon": 9.4045},
    {"nome": "Supermercato Bennet Calco", "comune": "Calco", "frazione": "Calco Nazionale", "categoria": "Commercio", "peso": 9, "lat": 45.7235, "lon": 9.4095},
    {"nome": "Centro Commerciale / Negozi SP342 Calco", "comune": "Calco", "frazione": "Calco Nazionale", "categoria": "Commercio", "peso": 7, "lat": 45.7250, "lon": 9.4110},
    {"nome": "Negozi e Botteghe Brivio Lungo Adda", "comune": "Brivio", "frazione": "Brivio Centro", "categoria": "Commercio", "peso": 6, "lat": 45.7432, "lon": 9.4450},
    {"nome": "Mercato Settimanale Olgiate Molgora (Martedì)", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Commercio", "peso": 8, "lat": 45.7332, "lon": 9.4010},
    {"nome": "Mercato Settimanale Brivio (Sabato)", "comune": "Brivio", "frazione": "Brivio Porto", "categoria": "Commercio", "peso": 8, "lat": 45.7425, "lon": 9.4460},

    # AREE PRODUTTIVE E OCCUPAZIONALI (Peso 8 - spostamenti lavoro in entrata)
    {"nome": "Area Industriale / Artigianale Calco Sud (SP342)", "comune": "Calco", "frazione": "Calco Sud", "categoria": "Attivita_Produttive", "peso": 8, "lat": 45.7210, "lon": 9.4080},
    {"nome": "Polo Produttivo Beverate - Brivio Est", "comune": "Brivio", "frazione": "Beverate", "categoria": "Attivita_Produttive", "peso": 7, "lat": 45.7380, "lon": 9.4320},
    {"nome": "Zona Industriale Fornace Rovagnate", "comune": "La Valletta Brianza", "frazione": "Rovagnate", "categoria": "Attivita_Produttive", "peso": 7, "lat": 45.7350, "lon": 9.3620},
    {"nome": "Polo Artigianale Olgiate Molgora - Pilata", "comune": "Olgiate Molgora", "frazione": "Pilata", "categoria": "Attivita_Produttive", "peso": 7, "lat": 45.7280, "lon": 9.4070},

    # IMPIANTI SPORTIVI E TEMPO LIBERO (Peso 6)
    {"nome": "Centro Sportivo Comunale Olgiate Molgora", "comune": "Olgiate Molgora", "frazione": "Olgiate Centro", "categoria": "Sport_TempoLibero", "peso": 6, "lat": 45.7345, "lon": 9.3980},
    {"nome": "Impianti Sportivi e Palestra Calco", "comune": "Calco", "frazione": "Calco Centro", "categoria": "Sport_TempoLibero", "peso": 6, "lat": 45.7270, "lon": 9.4140},
    {"nome": "Centro Sportivo Comunale Brivio", "comune": "Brivio", "frazione": "Beverate", "categoria": "Sport_TempoLibero", "peso": 6, "lat": 45.7360, "lon": 9.4280},
    {"nome": "Pista Ciclopedonale e Alzaia del Fiume Adda", "comune": "Brivio", "frazione": "Brivio Porto", "categoria": "Sport_TempoLibero", "peso": 7, "lat": 45.7420, "lon": 9.4458},
    {"nome": "Oasi WWF di Brivio / Palude dell'Adda", "comune": "Brivio", "frazione": "Brivio Sud", "categoria": "Sport_TempoLibero", "peso": 6, "lat": 45.7380, "lon": 9.4480}
]

def main():
    print("=== 07: MAPPATURA E ANALISI DEI GENERATORI DI DOMANDA (POI) ===")
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    df = pd.DataFrame(POIS)
    df.to_csv(OUT_POI_CSV, index=False)
    print(f"[OK] Salvato layer POI in {OUT_POI_CSV} ({len(df)} poli di attrazione censiti).")
    
    # Sintesi per categoria
    summary = df.groupby("categoria").agg(
        num_poi=("nome", "count"),
        peso_cumulativo=("peso", "sum")
    ).reset_index()
    summary.to_csv(OUT_SUMMARY_CSV, index=False)
    print("\n--- DISTRIBUZIONE DEI GENERATORI DI DOMANDA PER CATEGORIA ---")
    print(summary.to_string(index=False))

if __name__ == "__main__":
    main()
