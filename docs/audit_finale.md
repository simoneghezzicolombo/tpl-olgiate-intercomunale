# Registro Ufficiale di Audit Metodologico Finale

Il presente documento costituisce il registro ufficiale e vincolante di audit del progetto **TPL Olgiate Intercomunale**, conforme agli standard definiti in `COLLABORATION_PROTOCOL.md` e `AGENT_STATUS.md`.

In conformità ai principi di trasparenza epistemica, nessun dato o metrica può essere consolidato nel rapporto finale se la relativa componente non ha ottenuto lo stato `PASS` (o `WARNING` chiaramente documentato e circoscritto) a seguito del superamento dei rispettivi Gate di revisione.

---

## 1. Quadro di Avanzamento dei Gate

| Gate di Revisione | Descrizione e Requisiti | Stato Attuale | Data Validazione |
| :--- | :--- | :---: | :---: |
| **GATE A - Provenance** | Fonti primarie reali scaricate, verificate crittograficamente con SHA256 in `data/manifest.csv`, risoluzione integrale blocker A1-A3 e warning A4-A7 | ⏳ **IN REVIEW (Ripresentato REVIEW GATE A)** | - |
| **GATE B - Spatial Integrity** | Popolazione WorldPop reale calibrata, DEM Copernicus reale, isocrone su vero grafo pedonale OSM | ⏳ IN ATTESA DI GATE A | - |
| **GATE C - Transit Integrity** | GTFS ferroviario Trenord e GTFS ufficiale Agenzia TPL (Arriva + Linee Lecco), stops.txt ufficiale | ⏳ IN ATTESA DI GATE A | - |
| **GATE D - Route Integrity** | Routing reale su grafo stradale OSM, distanze e runtime calcolati deterministicamente senza km forzati | ⏳ IN ATTESA DI GATE A | - |
| **GATE E - Service Math** | Frequenze (headway CW, CCW, combinato), turni macchina, bus-km e vettura-ore matematicamente corretti | ⏳ IN ATTESA DI GATE A | - |
| **GATE F - Recommendation** | Raccomandazione finale e sensitività coerenti con i risultati reali e non condizionate a priori | ⏳ IN ATTESA DI GATE A | - |

---

## 2. Matrice di Audit delle Componenti

Stati ammessi: `PASS`, `WARNING`, `FAIL`, `FIELD CHECK REQUIRED`.

| Componente | Stato | Evidenza | Limiti | Azione |
| :--- | :---: | :--- | :--- | :--- |
| **Confini Amministrativi (5 comuni core)** | `PASS` | Poligoni vettoriali ISTAT 01/01/2026 estratti da `Limiti01012026.zip` WGS84 (`comuni_core_istat_2026.geojson`). URL ufficiale verificato: `https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2026/Limiti01012026.zip`. SHA256: `7008e5380b28...` | Confini comunali a fini statistici (non catastali). | Maschera geometrica deterministica per clipping WorldPop e DEM. |
| **Popolazione Raster (WorldPop 2020 100m)** | `PASS` | GeoTIFF nazionale 100m unconstrained UN-adjusted originale `ita_ppp_2020_UNadj.tif` (160.705.122 bytes, 14268x13919 pixel). Serie ufficiale: `Global_2000_2020`. Risoluzione: 3 arc-seconds (~64,6m lon x ~92,6m lat al suolo). URL ufficiale: `https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/ITA/ita_ppp_2020_UNadj.tif`. SHA256: `a9f9743a08f7...`. Ritaglio core: `worldpop_core_unadj_raw.tif` (4.283 celle, 25.127,76 ab grezzi, SHA256: `a441578ca49c...`). | Anno 2020 pre-calibrazione; totale grezzo +9,6% vs ISTAT 2025. | Calibrazione deterministica proporzionale cella-per-cella sui totali comunali ISTAT POSAS 2025 senza alterare la forma intracomunale. |
| **Altimetria e Pendenze (Copernicus DEM)** | `PASS` | Tile COG 30m GLO-30 N45_00_E009_00 da AWS Open Data ESA (`Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif`, 44 MB). Licenza con attribuzione ufficiale obbligatoria: Copernicus Sentinel data / Copernicus DEM Licence. SHA256: `fb357e36d4f0...`. Ritaglio core (`copernicus_dem_core_raw.tif`, SHA256: `14bbb5eb6cca...`). | Risoluzione a terra 30 metri; quota min 0m, max 699,5 m s.l.m. | Utilizzare per campionare pendenze e penalizzare percorsi pedonali con Tobler's hiking function. |
| **Mobilità Sistematica (Matrice OD ISTAT)** | `PASS` | 1.575 record reali individuali di tipo 'S' estratti dal file `matrix_pendo2011_10112014.txt`. URL ufficiale diretto: `https://www.istat.it/storage/cartografia/matrici_pendolarismo/matrici_pendolarismo_2011.zip`. SHA256: `131cc7e5070a...` | Anno 2011 (esplicitamente dichiarato); mobilità sistematica (lavoro/studio). | Pesare flussi interscambio frazionali verso stazione e poli attrattori. |
| **Orario Ferroviario Regionale (Trenord S8)** | `PASS` | Feed GTFS ufficiale Trenord da Open Data Regione Lombardia (`3z4k-mxz9`). SHA256: `b4296f145b42...`. Stazione Olgiate-Calco-Brivio identificata con ID `S01514`. | Orario teorico di programmazione 2026. | Sincronizzazione deterministica nodale delle coincidenze treno-bus (Milano e Lecco). |
| **GTFS Automobilistico Ufficiale Agenzia TPL** | `PASS` | Feed GTFS ufficiali inv. 2025-2026 scaricati dalla sezione Open Data dell'Agenzia TPL Como-Lecco-Varese (`https://www.tplcomoleccovarese.it/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/172`). Arriva Italia (4,48 MB, SHA256: `f890c393b909...`) e Linee Lecco (2,51 MB, SHA256: `f9b902807a2b...`). Identificate linee D184, D185, D150, D170 e 56 fermate ufficiali nel core. | Orario invernale di esercizio. | Base empirica istituzionale (FACT) per rete esistente e confronto scenari. |
| **Rete Stradale e Pedonale (OpenStreetMap)** | `PASS` | 4.477 segmenti viari/pedonali e 1.762 nodi estratti dal planet PBF snapshot Marzo 2026 bbox [8.872E, 45.469N, 9.833E, 45.883N] (103 MB, SHA256: `8c9e469581ef...`). | Completezza attributi illuminazione variabile su percorsi minori. | Costruire grafo NetworkX deterministico per routing e isocrone reali. |
| **Fermate Bus su OSM (Cross-check)** | `PASS` | 37 fermate Overpass classificate `FACT_OSM_OBSERVATION` (SHA256: `464c818c08e7...`). | Non sono autorità formale TPL. | Utilizzate come riscontro geometrico per banchine/marciapiedi; fonte primaria resta `stops.txt` del GTFS Arriva. |
| **Chilometraggi e Budget PdB 2025** | `PASS` | Programma di Bacino Agenzia TPL Como-Lecco-Varese: D184 (52.560 km/anno), D185 (58.859 km/anno). SHA256: `e31b992d7bc6...` | Dati aggregati di contratto. | Benchmark economico e chilometrico invalicabile a parità di risorse (111.419 km/anno). |
| **Passaggi Stretti e Geometrie Critiche** | `FIELD CHECK REQUIRED` | 5 punti critici individuati sulla viabilità minore (stretta di Mondonico, curva Arlate SP72, tornanti San Zeno, via Manzoni Calco, strettoia Monticello). | Non verificabile solo da cartografia; raggio e ingombro bus 10-12m. | Marcare come `DA VERIFICARE SUL CAMPO` prima di assegnare bus standard. |

---

## 3. Discrepanze e Correzioni di Provenance Effettuate in Gate A

| Elemento / Dataset | Stato Pre-Review GPT | Correzione Audit Gate A | Impatto Metodologico |
| :--- | :--- | :--- | :--- |
| **GTFS Agenzia TPL Como-Lecco-Varese** | Dichiarato inesistente come open data | Individuati e scaricati i feed ufficiali invernali 2025-2026 Arriva e Linee Lecco dall'URL CMS dell'Agenzia | **Risolto Blocker A1**: Servizio su gomma basato su GTFS istituzionale reale (`FACT`), non su ricostruzione parziale. |
| **WorldPop Raster Resolution & URL** | URL cartella `1km` per errore di trascrizione | Verificato raster 100m reale (3 arc-sec, ~65mx93m), corretto URL a `Global_2000_2020` | **Risolto Blocker A2**: Provenance URL corretta al 100%, confermata risoluzione 100m da metadati GeoTIFF. |
| **Riproducibilità Pipeline da Ambiente Pulito** | Dipendenza da percorsi `D:\Utente\Downloads` | Implementata funzione `download_file_if_missing()` con URL ufficiali e SHA256 in `audit_01_fetch_real_inputs.py` | **Risolto Blocker A3**: Qualunque revisore può rieseguire lo script da ambiente pulito e ottenere i dati. |
| **OSM PBF Provenance** | Geofabrik generico | Registrato bbox esatto [8.872, 45.469, 9.833, 45.883] e data snapshot Marzo 2026 | **Risolto Warning A4**: Provenance geografica e temporale trasparente. |
| **Fermate OSM vs Fermate Ufficiali** | Qualificate genericamente come fermate TPL | Riclassificate `FACT_OSM_OBSERVATION` per cross-check, stabilendo `stops.txt` Arriva come fonte primaria | **Risolto Warning A5**: Risolta ambiguità tra osservazione cartografica e programmazione TPL. |
| **Licenza Copernicus DEM** | Etichettata 'Public Domain' | Registrata la formale licenza Copernicus con attribuzione contrattuale obbligatoria COPE-GSP-EOPG-TN-15-0005 | **Risolto Warning A6**: Rispetto della proprietà intellettuale europea. |
| **Serie Storica SFR Stazioni** | Riferimento generico trenord.it | Specificato: Regione Lombardia D.G. Trasporti e Trenord (campagne novembre feriale) | **Risolto Warning A7**: Piena tracciabilità della fonte ferroviaria. |
