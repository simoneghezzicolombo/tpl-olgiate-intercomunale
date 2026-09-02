# PROGRESS.md - Avanzamento Progetto TPL Olgiate Intercomunale

**Nome Progetto**: `tpl-olgiate-intercomunale`  
**Branch di Lavoro Attivo**: `audit-fix-real-data`  
**Data Inizio**: 02 Settembre 2026  
**Ultimo Aggiornamento**: 02 Settembre 2026 (Audit metodologico e transizione a fonti reali)  
**Stato Generale**: ⚠️ IN FASE DI AUDIT E SOSTITUZIONE INTEGRALE DEI DATI REALI (Checkpoint B-F archiviati e invalidati)

---

## AVVISO DI REVISIONE ESTERNA E STATO METODOLOGICO

> [!WARNING]
> **STATUS: CHECKPOINTS B-F PRECEDENTI INVALIDATI DA AUDIT ESTERNO - SYNTHETIC INPUTS**
> A seguito dell'audit metodologico esterno del 02 Settembre 2026, i dataset intermedi, i percorsi e le matrici OD generati mediante modelli sintetici (pesi manuali per frazioni, `np.random`, decadimento esponenziale simulato, approssimazione euclidea $d \times 1,25$, matrici OD hard-coded) sono stati **formalmente INVALIDATI** e segregati in `data/legacy_synthetic/`.
> Il lavoro procede sul branch `audit-fix-real-data` con la sostituzione integrale dei dati sintetici con fonti reali primarie istituzionali (WorldPop 2020 GeoTIFF, Copernicus DEM GLO-30, ISTAT Limiti 2026, ISTAT Matrice Pendolarismo 2011, Trenord GTFS, OpenStreetMap PBF).

---

## 1. Stato dei Nuovi Checkpoint di Audit

| Checkpoint di Audit | Obiettivo | Stato | Output Principali |
| :--- | :--- | :---: | :--- |
| **AUDIT_CHECKPOINT_1_REAL_INPUTS** | Acquisizione fonti reali, manifest e verifica crittografica SHA256 | ✅ **COMPLETATO** | `data/manifest.csv`, `data/raw/worldpop/`, `data/raw/dem/`, `data/raw/boundaries/`, `data/raw/od/`, `data/raw/gtfs/rail_trenord/`, `data/raw/osm/`, `tests/test_audit_provenance.py` (8/8 passed) |
| **AUDIT_CHECKPOINT_2_REAL_SPATIAL** | WorldPop reale + DEM reale + network walking reale OSM | ⏳ IN ATTESA DI REVISIONE AUDIT-1 | Griglia di popolazione WorldPop clipped e calibrata, elevazione reale campionata da Copernicus DEM, isocrone su grafo stradale pedonale OSM |
| **AUDIT_CHECKPOINT_3_REAL_TRANSIT** | Baseline TPL reale, GTFS reale Trenord e orari ufficiali | ⏳ DA AVVIARE | Baseline oggettiva da orari ufficiali Arriva/LineeLecco, fermate reali OSM, separazione FACT vs RECONSTRUCTED |
| **AUDIT_CHECKPOINT_4_REAL_ROUTING** | Geometrie e runtime reali delle alternative su rete stradale | ⏳ DA AVVIARE | Routing reale su grafo viario OSM (distanze e tempi effettivi senza assunzioni di neutralità a priori) |
| **AUDIT_CHECKPOINT_5_RECOMPUTED_RESULTS** | Ricalcolo completo: coverage, OD reale, Pareto, scenari corretti | ⏳ DA AVVIARE | Matrice OD ISTAT reale, modello di frequenze corretto (4 bus per 30' per senso con ciclo 60'), Pareto frontier e rapporto finale |

---

## 2. Dettaglio AUDIT CHECKPOINT 1: REAL INPUTS (Completato)

### 1. Risultati Principali
- **WorldPop 2020 Reale**:
  - Acquisito il raster nazionale unconstrained 100m UN-adjusted `ita_ppp_2020_UNadj.tif` (160.705.122 bytes, SHA256: `a9f9743a08f73e714722ecd54db5e9bb4968bec4a9f88d8f1782c6f7ba1dcea8`).
  - Eseguito il clipping rigoroso mediante poligoni ISTAT 2026 sui 5 comuni core in `data/raw/worldpop/worldpop_core_unadj_raw.tif` (56.293 bytes, 4.283 celle popolate, somma uncalibrated 25.127,76 ab, SHA256: `a441578ca49c2e55fba8e6c474301cb91e78e3bf6bc0aca97cf425e698ea3db2`). Nessun generatore artificiale o decadimento sintetico.
- **Copernicus DEM GLO-30 Reale**:
  - Scaricato il tile reale AWS Open Data `Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif` a 30m di risoluzione (44.155.932 bytes, SHA256: `fb357e36d4f0ebea0c96cec7793c686506bb6aaeb34b92d464b46f05889f824d`).
  - Ritagliato sui 5 comuni core in `data/raw/dem/copernicus_dem_core_raw.tif` (491.980 bytes, quota min 0m, max 699,5m s.l.m., media 119,9m, SHA256: `14bbb5eb6cca940426f27bd65732600f20a911418237e890b3677d6ff8186398`).
- **Confini Amministrativi Ufficiali ISTAT 2026**:
  - Estratti i confini WGS84 non generalizzati dal rilascio ISTAT 01/01/2026 per i 5 comuni (Brivio 097010, Calco 097012, Olgiate Molgora 097058, Santa Maria Hoè 097074, La Valletta Brianza 097092) in `data/raw/boundaries/comuni_core_istat_2026.geojson` (79.275 bytes, SHA256: `7008e5380b28c865bf2e503b605700700a6d2959925f91fdde2b1435e00033f9`).
- **Matrice Pendolarismo ISTAT 2011 Reale**:
  - Estratti 1.575 record OD reali individuali dal file ufficiale ISTAT `matrix_pendo2011_10112014.txt` in `data/raw/od/matrice_pendolarismo_istat_2011_core.csv` (94.380 bytes, SHA256: `131cc7e5070aecb7c362eb241c1d3454d72b161a899b5d80ac72f55bb4413075`). Totale pendolari: Brivio 2.567, Calco 3.020, Olgiate Molgora 3.329, La Valletta Brianza 2.235, Santa Maria Hoè 1.282.
- **GTFS Trenord Reale (Open Data Regione Lombardia)**:
  - Scaricato il feed ufficiale `trenord_gtfs.zip` (dataset `3z4k-mxz9`, 1.660.043 bytes, SHA256: `b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6`) in `data/raw/gtfs/rail_trenord/`, verificando la presenza della stazione hub Olgiate-Calco-Brivio (`S01514`).
- **OpenStreetMap Rete e Fermate Reali**:
  - Estratti dal planet PBF `planet_8.872,45.469_9.833,45.883.osm.pbf` (103.234.768 bytes, SHA256: `8c9e469581ef5df195b376eaf86236d7ba816f3c8ab09b3e00d3e06f7266ad83`):
    - `data/raw/osm/osm_highways_core.geojson`: 4.477 segmenti stradali e pedonali reali con geometrie e attributi (SHA256: `e45b893bedd1c2e9606352b2406614c6aebbaea2bc528b29764df844084ffc23`).
    - `data/raw/osm/osm_points_core.geojson`: 1.762 punti reali (SHA256: `1ca6fd819ce781b0992dccc89b79ad67e98c31c8edc9d6aacb9dd0c949e11fb5`).
    - `data/raw/osm/osm_bus_stops_core.json`: 37 fermate e piazzole bus reali con operatore Arriva Italia (SHA256: `464c818c08e73ea06607afc696a34bb940dc6f25010165c6ccfa6ab215bb4748`).
    - `data/raw/osm/osm_pois_core.json`: 585 POI reali georeferenziati (SHA256: `df5369b5f96d1c245b07db921d2cd364fa8489292dfe8dc217d92d323efd2696`).
- **Manifest e Unit Test**:
  - Compilato `data/manifest.csv` con 16 dataset tracciati, completi di metadati, licenze, date di accesso e hash crittografici SHA256.
  - Implementata la suite di test `tests/test_audit_provenance.py` (8 test superati con successo in 1.88s).

### 2. File da Revisionare
- [`data/manifest.csv`](file:///d:/linea_8_olgiate/data/manifest.csv) (registro completo di tutte le fonti reali e relativi SHA256)
- [`docs/fonti.md`](file:///d:/linea_8_olgiate/docs/fonti.md) (documentazione estesa della provenienza e dello status dei dati)
- [`data/raw/boundaries/comuni_core_istat_2026.geojson`](file:///d:/linea_8_olgiate/data/raw/boundaries/comuni_core_istat_2026.geojson)
- [`data/raw/worldpop/worldpop_core_unadj_raw.tif`](file:///d:/linea_8_olgiate/data/raw/worldpop/worldpop_core_unadj_raw.tif)
- [`data/raw/dem/copernicus_dem_core_raw.tif`](file:///d:/linea_8_olgiate/data/raw/dem/copernicus_dem_core_raw.tif)
- [`data/raw/od/matrice_pendolarismo_istat_2011_core.csv`](file:///d:/linea_8_olgiate/data/raw/od/matrice_pendolarismo_istat_2011_core.csv)
- [`data/raw/gtfs/rail_trenord/`](file:///d:/linea_8_olgiate/data/raw/gtfs/rail_trenord/)
- [`data/raw/osm/osm_highways_core.geojson`](file:///d:/linea_8_olgiate/data/raw/osm/osm_highways_core.geojson)
- [`data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md`](file:///d:/linea_8_olgiate/data/legacy_synthetic/README_SYNTHETIC_ARCHIVE.md)
- [`tests/test_audit_provenance.py`](file:///d:/linea_8_olgiate/tests/test_audit_provenance.py)
- [`scripts/audit_01_fetch_real_inputs.py`](file:///d:/linea_8_olgiate/scripts/audit_01_fetch_real_inputs.py)

### 3. Assunzioni Utilizzate
- **Perimetro di studio**: Bounding box geografico $[45.710^\circ \text{N}, 9.355^\circ \text{E}] \times [45.760^\circ \text{N}, 9.460^\circ \text{E}]$ intersecato con i confini comunali ISTAT 2026 dei 5 comuni core.
- **Risoluzione raster**: WorldPop a 100m (~3 arc-sec), Copernicus DEM GLO-30 a 30m.
- **Assenza di perturbazioni sintetiche**: Nessun seed casuale, nessun peso manuale a priori assegnato alle singole frazioni.

### 4. Dati Mancanti o Indisponibili (Dichiarazione di Trasparenza)
- **Feed GTFS Open Data Agenzia TPL Como-Lecco-Varese**: Attualmente **NON disponibile** come dataset open data pubblico (a differenza di altre agenzie come Milano). Come prescritto, i fatti del servizio su gomma (linee D184, D185, D150, D170) derivano esclusivamente dagli orari ufficiali di esercizio feriali/festivi Arriva Italia / LineeLecco e dalle fermate reali geocodificate in OSM. La modellazione GTFS della rete su gomma è pertanto classificata esplicitamente come `RECONSTRUCTED NETWORK FROM OFFICIAL TIMETABLES & OSM STOPS` e NON come "feed GTFS ufficiale dell'Agenzia".

### 5. Anomalie o Risultati Inattesi
- La somma della popolazione WorldPop 2020 grezza non calibrata sui 5 comuni risulta pari a 25.127,76 ab (rispetto ai 22.914 ab censiti da ISTAT al 1° gennaio 2025). Lo scostamento è coerente con la natura del modello WorldPop globale non vincolato pre-calibrazione comunale.
- Il rilievo altimetrico reale Copernicus DEM evidenzia quote che raggiungono quasi 700 m s.l.m. nella parte nord-occidentale (rilievi di Santa Maria Hoè / Colle Brianza), confermando l'importanza di non usare la distanza euclidea pura per il calcolo dell'accessibilità pedonale.

### 6. Decisioni che Richiedono Revisione Umana
- Conferma dell'approvazione delle fonti reali acquisite e del manifest crittografico prima di avviare l'elaborazione di `AUDIT_CHECKPOINT_2_REAL_SPATIAL`.

---

## 3. Archivio Storico dei Risultati Precedenti (INVALIDATED BY EXTERNAL AUDIT)

*(I paragrafi seguenti descrivono il lavoro preliminare condotto nei Checkpoint B-F antecedenti all'audit, conservati esclusivamente per tracciabilità storica e confronto metodologico).*

<details>
<summary><b>Visualizza dettagli storici Checkpoint A-F (INVALIDATI DA AUDIT ESTERNO)</b></summary>

### CHECKPOINT A: Baseline Quantitativa (Storico)
- D184 e D185 dispongono nel PdB di 111.419 bus-km/anno (+23,3% vs Merate D201+D202), ma sole 6 coppie di corse e buchi fino a 6h 55m.

### CHECKPOINT B: Popolazione e Accessibilità (INVALIDATO - Modello Sintetico)
- Generato con pesi manuali per frazioni e decadimento esponenziale. Griglia sostituita da WorldPop reale 100m.

### CHECKPOINT C: Alternative di Tracciato (INVALIDATO - Distanza Euclidea x 1,25)
- Calcolato con formule approssimate. Sostituito da vero routing su grafo stradale OSM in Checkpoint 4.

### CHECKPOINT D: Pareto Frontier e Simulazione (INVALIDATO)
- Frequenze e scenari da ricalibrare (4 bus necessari per 30' per senso con ciclo 60').

### CHECKPOINT E: Alternative Consigliate (INVALIDATO)
- Lunghezza VAR_04 da ricavare dal routing effettivo senza forzature a 19,5 km.

### CHECKPOINT F: Rapporto Finale Preliminare (INVALIDATO)
- In attesa di ricalcolo integrale su fonti reali primarie nei Checkpoint 2-5.

</details>
