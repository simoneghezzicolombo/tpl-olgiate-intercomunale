#!/usr/bin/env python3
"""
01_download_sources.py
Acquisizione, estrazione e registrazione formale di tutte le fonti dati nel manifest.csv.
Calcola hash SHA256, traccia ente, URL, anno di riferimento e licenza.
"""

import os
import sys
import hashlib
import zipfile
import shutil
import csv
import pandas as pd
import requests

DATA_DIR = 'data'
RAW_DIR = os.path.join(DATA_DIR, 'raw')
MANIFEST_PATH = os.path.join(DATA_DIR, 'manifest.csv')

def sha256_file(filepath):
    """Calcola hash SHA256 di un file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def record_manifest(rows):
    """Scrive o aggiorna data/manifest.csv."""
    fieldnames = [
        'dataset_id', 'ente', 'url_or_origin', 'data_accesso',
        'anno_riferimento', 'licenza', 'file_locale', 'sha256', 'trasformazioni'
    ]
    with open(MANIFEST_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"Manifest registrato con successo in {MANIFEST_PATH} ({len(rows)} voci).")

def main():
    print("=== FASE 1: ACQUISIZIONE E CATALOGAZIONE FONTI DATI ===")
    manifest_entries = []

    # 1. ISTAT POSAS 2025 Microdati Lecco
    istat_zip_src = r"D:\Utente\Downloads\POSAS_2025_it_097_Lecco.zip"
    istat_dest_csv = os.path.join(RAW_DIR, 'istat', 'POSAS_2025_it_097_Lecco.csv')
    if os.path.exists(istat_zip_src):
        with zipfile.ZipFile(istat_zip_src) as z:
            z.extract('POSAS_2025_it_097_Lecco.csv', os.path.join(RAW_DIR, 'istat'))
        h = sha256_file(istat_dest_csv)
        manifest_entries.append({
            'dataset_id': 'istat_posas_2025_lecco',
            'ente': 'ISTAT',
            'url_or_origin': 'https://demo.istat.it/app/?l=it&a=2025&i=POS',
            'data_accesso': '2026-09-02',
            'anno_riferimento': '2025',
            'licenza': 'IODL 2.0 / Open Data ISTAT',
            'file_locale': istat_dest_csv,
            'sha256': h,
            'trasformazioni': 'Estrazione da archivio zip ufficiale ISTAT POSAS 2025 per la provincia di Lecco.'
        })
        print(f"[OK] ISTAT POSAS 2025 registrato ({h[:12]}...)")
    else:
        print(f"[WARN] File {istat_zip_src} non trovato direttamente.")

    # 2. Frequentazione SFR Stazioni Ferroviarie (2015-2025)
    sfr_src = r"D:\s8-analisi\data\processed\stazioni_s8_indice_2015_2025.csv"
    sfr_dest = os.path.join(RAW_DIR, 'sfr', 'stazioni_s8_indice_2015_2025.csv')
    if os.path.exists(sfr_src):
        shutil.copy2(sfr_src, sfr_dest)
        h = sha256_file(sfr_dest)
        manifest_entries.append({
            'dataset_id': 'sfr_stazioni_s8_2015_2025',
            'ente': 'Regione Lombardia / Trenord',
            'url_or_origin': 'dati.lombardia.it (Frequentazione stazioni SFR)',
            'data_accesso': '2026-09-02',
            'anno_riferimento': '2015-2025',
            'licenza': 'IODL 2.0',
            'file_locale': sfr_dest,
            'sha256': h,
            'trasformazioni': 'Serie storica passeggeri saliti per Olgiate-Calco-Brivio e stazioni Meratese.'
        })
        print(f"[OK] SFR Stazioni S8 registrato ({h[:12]}...)")

    # 3. Dati Isocrone e Snap Grafo WorldPop dal Progetto S8
    snap_src = r"data/station_coordinates_and_graph_snap.csv"
    if os.path.exists(snap_src):
        dest = os.path.join(RAW_DIR, 'osm', 'station_coordinates_and_graph_snap.csv')
        shutil.copy2(snap_src, dest)
        h = sha256_file(dest)
        manifest_entries.append({
            'dataset_id': 'isocrone_snap_s8',
            'ente': 'Elaborazione Progetto S8 / OSM / WorldPop',
            'url_or_origin': 'D:/Utente/Downloads/isochrone_s8_meratese_outputs.zip',
            'data_accesso': '2026-09-02',
            'anno_riferimento': '2020-2025',
            'licenza': 'ODbL / CC-BY 4.0',
            'file_locale': dest,
            'sha256': h,
            'trasformazioni': 'Snap dei nodi stazione sulla rete pedonale OSM.'
        })

    # 4. Programma di Bacino Agenzia TPL Como-Lecco-Varese
    pdb_src = r"D:\Archivio_Trasporti_6_5_26\Trasporti_pesante_2026-05-14\PdB Aggiornamento 2025 - Relazione generale.pdf"
    if os.path.exists(pdb_src):
        dest_pdf = os.path.join(DATA_DIR, 'external', 'PdB_Aggiornamento_2025_Relazione_generale.pdf')
        shutil.copy2(pdb_src, dest_pdf)
        h = sha256_file(dest_pdf)
        manifest_entries.append({
            'dataset_id': 'programma_bacino_tpl_como_lecco_varese_2025',
            'ente': 'Agenzia TPL Como, Lecco e Varese',
            'url_or_origin': 'https://www.agenziatpl.it/attivita/programma-di-bacino',
            'data_accesso': '2026-09-02',
            'anno_riferimento': '2025',
            'licenza': 'Documento istituzionale pubblico',
            'file_locale': dest_pdf,
            'sha256': h,
            'trasformazioni': 'Copia di riferimento per assegnazione bus-km D184 e D185.'
        })
        print(f"[OK] Programma di Bacino 2025 registrato ({h[:12]}...)")

    record_manifest(manifest_entries)

if __name__ == '__main__':
    main()
