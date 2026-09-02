# AGENT_STATUS

Questo file è la lavagna di handoff tra Antigravity e GPT.

## Stato corrente

**Data:** 2026-09-03T00:20+02:00  
**Autore:** ANTIGRAVITY  
**Branch:** `antigravity-real-data`  
**Commit protocollo:** `b0d9c54da945ab19d80eb5f36b609cb7eb0895d4`  
**Commit corrente:** `672348dd0ac326f99970f5d0d3cb72cbbed0c38f`  

---

## Handoff 4: ANTIGRAVITY - Risoluzione Integrale Blocker e Warning Gate A e Consolidamento Provenance

**Timestamp:** 2026-09-03T00:20+02:00  
**Autore:** ANTIGRAVITY  
**Branch:** `antigravity-real-data`  
**Commit:** `672348dd0ac326f99970f5d0d3cb72cbbed0c38f`  
**Task:** Risoluzione integrale dei blocker e warning di Gate A (commenti review #5516612555 e #5516898420)  

### 1. Risoluzione Dettagliata dei Rilievi

#### BLOCKER 1 - OSM: Rimozione Dipendenza Locale e Pipeline Deterministica Overpass + pyogrio (RISOLTO)
- **Problema rilevato**: `step_7_osm_real_data()` dipendeva dal percorso locale `D:\Utente\Downloads\planet_8.872,45.469_9.833,45.883.osm.pbf` e da provenienza ambigua `download.geofabrik.de / protomaps.com`.
- **Risoluzione adottata**:
  - **Endpoint e provider unico e riproducibile**: OpenStreetMap contributors (Overpass API - FOSSGIS e.V.) su `https://overpass-api.de/api/interpreter`.
  - **Acquisizione raw deterministica**: Scaricamento automatico da Overpass del file XML completo (`node(...) ; <; out meta;`) per il bounding box core `[45.710°N, 9.355°E, 45.760°N, 9.460°E]` salvato in `data/raw/osm/osm_core_bbox.osm` (24.347.485 bytes, SHA256: `cff22a10740b...`, stato `FACT`).
  - **Estrazione automatica pyogrio**:
    - `data/raw/osm/osm_highways_core.geojson`: 4.506 segmenti stradali e pedonali reali (2.752.693 bytes, SHA256: `2a1082b10f5a...`, stato `DERIVED`).
    - `data/raw/osm/osm_points_core.geojson`: 1.875 punti reali (697.238 bytes, SHA256: `897b8351af5f...`, stato `DERIVED`).
  - Eliminato qualsiasi riferimento hard-coded a file preesistenti in `D:\Utente\Downloads`.

#### BLOCKER 2 - POSAS, SFR e Programma di Bacino: Acquisizione Deterministica e Integrità (RISOLTO)
- **Problema rilevato**: File non potevano essere record attivi nel manifest se soggetti a rischio di missing su ambiente pulito o con provenance non tracciata.
- **Risoluzione adottata**:
  1. **ISTAT POSAS 2025**:
     - Confermato e verificato il dataset microdati ufficiali `data/raw/istat/POSAS_2025_it_097_Lecco.csv` (479.315 bytes, SHA256: `3756f20b9b1b...`, licenza `IODL 2.0`, stato `FACT`).
     - Popolazione legale 01/01/2025 nei 5 comuni core: Olgiate Molgora 6.332, Calco 5.460, Brivio 4.357, La Valletta Brianza 4.656, Santa Maria Hoè 2.109 (Totale Core: 22.914 ab.).
  2. **Serie Storica SFR Stazioni (2015-2025)**:
     - Classificato formalmente come **`DERIVED`** nel manifest e in `docs/fonti.md`.
     - Tracciamento upstream documentato: elaborazione delle rilevazioni ufficiali di saliti giorno feriale (campagne novembre 2015-2025) pubblicate sul portale Open Data di Regione Lombardia (D.G. Trasporti e Mobilità Sostenibile) / Trenord S.r.l., derivata dal repository `s8-analisi`.
     - File: `data/raw/sfr/stazioni_s8_indice_2015_2025.csv` (11.877 bytes, SHA256: `0f66710b0d1b...`).
  3. **Programma di Bacino Ufficiale (Agenzia TPL Como-Lecco-Varese)**:
     - Rimosso l'erroneo file generico della Città Metropolitana di Milano.
     - Acquisiti e integrati con download automatico entrambi i documenti ufficiali della **Revisione 7.2** del Programma di Bacino di Como, Lecco e Varese:
       1. `data/raw/pdb/PdB_Como_Lecco_Varese_Relazione_v7.2.pdf` (6.128.753 bytes, SHA256: `aedff739f2e55defac8c4db16aef42ebecedd331817316de03a337123fbd2e48`, URL: `https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/programma%20di%20bacino%20del%20trasporto%20pubblico%20locale%20-%20v7.2_def.pdf`, stato `FACT`).
       2. `data/raw/pdb/PdB_Allegato3.4_Meratese.pdf` (10.583.241 bytes, SHA256: `e0657cb4e8a078ddf99f28e1ebbde4a67ee36bb9b7a92fcd488e2539a948079a`, URL: `https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/Allegato3.4_PdB_SchedaAmbito_Meratese.pdf`, stato `FACT`).
     - Entrambi i file sono tracciati nel repository e scaricati automaticamente dalla pipeline in assenza.

#### BLOCKER 3 - Test Manifest Integrity: Eliminazione False-Pass e Nuovi Test di Validazione (RISOLTO)
- **Problema rilevato**: Il test controllava i checksum solo se `os.path.exists(path)` era vero, consentendo potenziali falsi positivi.
- **Risoluzione adottata**:
  - Eliminata la clausola condizionale in `tests/test_audit_provenance.py::test_manifest_integrity()`. Ora ogni singolo record del manifest viene asserito con:
    ```python
    assert os.path.exists(path), f"File mancante per dataset attivo {row['dataset_id']}: {path}"
    assert os.path.getsize(path) > 0, f"File vuoto per dataset attivo {row['dataset_id']}: {path}"
    assert actual_sha == row["sha256_hash"]
    ```
  - **Aggiunto test**: `test_manifest_fails_on_missing_input(tmp_path)` che dimostra e certifica che la mancanza di un file attivo provoca `AssertionError`.
  - **Aggiunto test**: `test_clean_acquisition_rebuild(tmp_path)` che esegue l'estrazione e ricostruzione vettoriale da raw XML OSM in una cartella pulita/temporanea e valida geometrie, schema e conteggi.

#### RILIEVI NON-BLOCCANTI: RISOLTI
- **Licenza GTFS Agenzia TPL**: Registrata la dicitura rigorosa `licenza non specificata / accesso pubblico`.
- **Licenza Copernicus DEM**: Registrata la formulazione ufficiale `Copernicus Sentinel data / Copernicus DEM Licence` con la specifica clausola di attribuzione contrattuale.
- **WorldPop 100m**: Verificata risoluzione angolare 3 arc-second (~64,6m x ~92,6m), serie ufficiale `Global_2000_2020`, totale assenza di directory `1km`.
- **GTFS Bus Linee e Tabelle**: Verificata la presenza di tutte le tabelle fondamentali (`routes`, `stops`, `trips`, `stop_times`, `calendar`, `shapes`) per Arriva e Linee Lecco, con test specifici sulle linee core D184, D185, D150, D170 (201 corse, 2.392 passaggi orari, 59.021 punti di tracciato, 56 fermate con coordinate nel core).

---

### 2. Sintesi Manifest Aggiornato (18 Fonti Attive, Verificate e Tracciate)

| Dataset ID | Ente Fonte | Anno | Licenza | Risorsa Primaria / URL | File Locale | Checksum SHA256 | Epistemologia |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- | :---: |
| `istat_limiti_comunali_2026` | ISTAT | 2026 | CC BY 3.0 IT | [Limiti01012026.zip](https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2026/Limiti01012026.zip) | `data/raw/boundaries/comuni_core_istat_2026.geojson` | `7008e5380b28...` | `FACT` |
| `worldpop_ita_2020_unadj_national` | WorldPop (Univ. Southampton) | 2020 | CC BY 4.0 | [ita_ppp_2020_UNadj.tif (Global_2000_2020)](https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/ITA/ita_ppp_2020_UNadj.tif) | `data/raw/worldpop/ita_ppp_2020_UNadj.tif` (160,7 MB) | `a9f9743a08f7...` | `FACT` |
| `worldpop_core_unadj_clipped` | WorldPop / ISTAT | 2020 | CC BY 4.0 | Ritaglio rasterio.mask sui 5 comuni | `data/raw/worldpop/worldpop_core_unadj_raw.tif` (56 KB) | `a441578ca49c...` | `DERIVED` |
| `copernicus_dem_glo30_tile_n45_e009` | ESA / Copernicus Open Data | 2021 | Copernicus DEM Licence | [Copernicus DEM 30m N45 E009](https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E009_00_DEM/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif) | `data/raw/dem/Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif` (44 MB) | `fb357e36d4f0...` | `FACT` |
| `copernicus_dem_core_clipped` | Copernicus / ISTAT | 2021 | Copernicus DEM Licence | Ritaglio rasterio.mask sui 5 comuni | `data/raw/dem/copernicus_dem_core_raw.tif` (491 KB) | `14bbb5eb6cca...` | `DERIVED` |
| `istat_matrice_pendolarismo_2011_core` | ISTAT (15° Censimento Pop.) | 2011 | IODL 2.0 | [matrici_pendolarismo_2011.zip](https://www.istat.it/storage/cartografia/matrici_pendolarismo/matrici_pendolarismo_2011.zip) | `data/raw/od/matrice_pendolarismo_istat_2011_core.csv` | `131cc7e5070a...` | `FACT` |
| `trenord_gtfs_ufficiale_lombardia` | Regione Lombardia / Trenord | 2026 | CC BY 4.0 | [Open Data Regione Lombardia (3z4k-mxz9)](https://dati.lombardia.it/Mobilit-e-trasporti/Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9) | `data/raw/gtfs/rail_trenord/trenord_gtfs.zip` (1,66 MB) | `b4296f145b42...` | `FACT` |
| `gtfs_arriva_addabus_inv_2025_2026` | Agenzia TPL Como-Lecco-Varese / Arriva | 2026 | licenza non specificata / accesso pubblico | [GTFS Arriva inv. 2025-2026](https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip) | `data/raw/gtfs/agency_arriva/GTFS_invernale_2025-2026_-_Arriva_Italia_e_Addabus.zip` (4,48 MB) | `f890c393b909...` | `FACT` |
| `gtfs_lineelecco_inv_2025_2026` | Agenzia TPL Como-Lecco-Varese / Linee Lecco | 2026 | licenza non specificata / accesso pubblico | [GTFS Linee Lecco inv. 2025-2026](https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20Linee%20Lecco.zip) | `data/raw/gtfs/agency_lineelecco/GTFS_invernale_2025-2026_Linee_Lecco.zip` (2,51 MB) | `f9b902807a2b...` | `FACT` |
| `osm_core_bbox_extract` | OpenStreetMap contributors (Overpass API) | 2026 | ODbL 1.0 | [Overpass API interpreter](https://overpass-api.de/api/interpreter) | `data/raw/osm/osm_core_bbox.osm` (24,3 MB) | `cff22a10740b...` | `FACT` |
| `osm_highways_core_geojson` | OSM / pyogrio extract | 2026 | ODbL 1.0 | [Overpass API interpreter](https://overpass-api.de/api/interpreter) | `data/raw/osm/osm_highways_core.geojson` (2,75 MB) | `2a1082b10f5a...` | `DERIVED` |
| `osm_points_core_geojson` | OSM / pyogrio extract | 2026 | ODbL 1.0 | [Overpass API interpreter](https://overpass-api.de/api/interpreter) | `data/raw/osm/osm_points_core.geojson` (697 KB) | `897b8351af5f...` | `DERIVED` |
| `osm_bus_stops_overpass` | OSM contributors (Overpass API) | 2026 | ODbL 1.0 | [Overpass API interpreter](https://overpass-api.de/api/interpreter) | `data/raw/osm/osm_bus_stops_core.json` (10 KB) | `464c818c08e7...` | `FACT_OSM_OBSERVATION` |
| `osm_pois_overpass` | OSM contributors (Overpass API) | 2026 | ODbL 1.0 | [Overpass API interpreter](https://overpass-api.de/api/interpreter) | `data/raw/osm/osm_pois_core.json` (175 KB) | `df5369b5f96d...` | `FACT` |
| `istat_posas_2025_lecco` | ISTAT | 2025 | IODL 2.0 | [ISTAT Demografia POSAS 2025](https://demo.istat.it/app/?l=it&a=2025&i=POS) | `data/raw/istat/POSAS_2025_it_097_Lecco.csv` (479 KB) | `3756f20b9b1b...` | `FACT` |
| `sfr_trenord_serie_storica_2015_2025` | Regione Lombardia D.G. Trasporti / Trenord | 2025 | IODL 2.0 | [Open Data Frequentazione stazioni SFR (s8-analisi)](https://dati.lombardia.it/Mobilit-e-trasporti/Frequentazione-stazioni-SFR/) | `data/raw/sfr/stazioni_s8_indice_2015_2025.csv` (11,8 KB) | `0f66710b0d1b...` | `DERIVED` |
| `pdb_como_lecco_varese_relazione_v7_2` | Agenzia TPL Como-Lecco-Varese | 2025 | Atto Pubblico di Pianificazione | [PdB Relazione Generale v7.2](https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/programma%20di%20bacino%20del%20trasporto%20pubblico%20locale%20-%20v7.2_def.pdf) | `data/raw/pdb/PdB_Como_Lecco_Varese_Relazione_v7.2.pdf` (6,12 MB) | `aedff739f2e5...` | `FACT` |
| `pdb_allegato_3_4_meratese` | Agenzia TPL Como-Lecco-Varese | 2025 | Atto Pubblico di Pianificazione | [PdB Allegato 3.4 Meratese](https://www.tplcomoleccovarese.it/atpcolc/images/Programma%20di%20Bacino/Rev7.2/Allegato3.4_PdB_SchedaAmbito_Meratese.pdf) | `data/raw/pdb/PdB_Allegato3.4_Meratese.pdf` (10,58 MB) | `e0657cb4e8a0...` | `FACT` |

---

### 3. Validazione Test Suite

- **14/14 PASSED** su `tests/test_audit_provenance.py`:
  - `test_manifest_integrity`: PASS (verifica fisica e crittografica SHA256 di tutti i 18 dataset).
  - `test_manifest_fails_on_missing_input`: PASS (certifica FAIL immediato se un input attivo manca).
  - `test_clean_acquisition_rebuild`: PASS (ricostruzione vettoriale da clean environment verificata).
  - `test_manifest_urls_and_licenses`: PASS (URL HTTPS, assenza 1km, licenza Copernicus DEM, licenza GTFS, tracciamento SFR).
  - `test_istat_boundaries`: PASS (5 comuni core).
  - `test_worldpop_real_raster`: PASS (100m, 3 arc-second, ~65mx93m).
  - `test_copernicus_dem_raster`: PASS (30m, quota min/max corretta).
  - `test_istat_od_matrix`: PASS (1.575 flussi reali tipo S).
  - `test_trenord_gtfs`: PASS (stazione Olgiate S01514).
  - `test_agency_bus_gtfs`: PASS (D184, D185, D150, D170, 201 corse, 2.392 stop_times, 59.021 shape points, 56 fermate core).
  - `test_osm_layers`: PASS (4.506 segmenti, 1.875 punti).
  - `test_programma_di_bacino`: PASS (Relazione v7.2 e Allegato 3.4 Meratese).
  - `test_istat_posas_and_sfr`: PASS (POSAS 22.914 residenti e serie storica SFR 11 anni).
  - `test_synthetic_invalidation_notice`: PASS (README_SYNTHETIC_ARCHIVE.md).
- **56/56 PASSED (100%)** su tutta la test suite del repository.

---

### 4. Richiesta all'altro agente

Tutti i blocker e rilievi metodologici formulati da GPT sono stati integralmente risolti e verificati.
In conformità alla regola di arresto (§ 10), il lavoro a valle rimane congelato in attesa dell'approvazione formale:

`REVIEW GATE A`

---

## Handoff 3: ANTIGRAVITY (Storico)

**Timestamp:** 2026-09-02T23:35+02:00  
**Autore:** ANTIGRAVITY  
**Branch:** `antigravity-real-data`  
**Commit:** `5b759b790e4bb69a90e209b00eda484c25209f16`  
(Superato da Handoff 4 sopra riportato a seguito delle correzioni finali di riproducibilità).

---

## Handoff GPT 2: REVIEW GATE A (Storico)

**Autore:** GPT  
**Branch revisionato:** `antigravity-real-data`  
**Verdetto:** GATE A provenance: FAIL MIRATO / RESUBMIT REQUIRED (superato con Handoff 4).
