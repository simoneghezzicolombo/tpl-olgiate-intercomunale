# Registro Ufficiale di Audit Metodologico Finale

Il presente documento costituisce il registro ufficiale e vincolante di audit del progetto **TPL Olgiate Intercomunale**, conforme agli standard definiti in `COLLABORATION_PROTOCOL.md` e `AGENT_STATUS.md`.

In conformità ai principi di trasparenza epistemica, nessun dato o metrica può essere consolidato nel rapporto finale se la relativa componente non ha ottenuto lo stato `PASS` (o `WARNING` chiaramente documentato e circoscritto) a seguito del superamento dei rispettivi Gate di revisione.

---

## 1. Quadro di Avanzamento dei Gate

| Gate di Revisione | Descrizione e Requisiti | Stato Attuale | Data Validazione |
| :--- | :--- | :---: | :---: |
| **GATE A - Provenance** | Fonti primarie reali scaricate, verificate crittograficamente con SHA256 in `data/manifest.csv` | ⏳ **IN REVIEW (Richiesto REVIEW GATE A)** | - |
| **GATE B - Spatial Integrity** | Popolazione WorldPop reale calibrata, DEM Copernicus reale, isocrone su vero grafo pedonale OSM | ⏳ IN ATTESA DI GATE A | - |
| **GATE C - Transit Integrity** | GTFS ferroviario Trenord e orari ufficiali automobilistici, distinzione rigorosa FACT vs RECONSTRUCTED | ⏳ IN ATTESA DI GATE A | - |
| **GATE D - Route Integrity** | Routing reale su grafo stradale OSM, distanze e runtime calcolati deterministicamente senza km forzati | ⏳ IN ATTESA DI GATE A | - |
| **GATE E - Service Math** | Frequenze (headway CW, CCW, combinato), turni macchina, bus-km e vettura-ore matematicamente corretti | ⏳ IN ATTESA DI GATE A | - |
| **GATE F - Recommendation** | Raccomandazione finale e sensitività coerenti con i risultati reali e non condizionate a priori | ⏳ IN ATTESA DI GATE A | - |

---

## 2. Matrice di Audit delle Componenti

Stati ammessi: `PASS`, `WARNING`, `FAIL`, `FIELD CHECK REQUIRED`.

| Componente | Stato | Evidenza | Limiti | Azione |
| :--- | :---: | :--- | :--- | :--- |
| **Confini Amministrativi (5 comuni core)** | `PASS` | Poligoni vettoriali ISTAT 01/01/2026 estratti da `Limiti01012026.zip` WGS84 (`comuni_core_istat_2026.geojson`). SHA256: `7008e5380b28...` | Confini comunali a fini statistici (non catastali). | Utilizzare come maschera deterministica per clipping WorldPop e DEM. |
| **Popolazione Raster (WorldPop 2020)** | `PASS` | GeoTIFF nazionale 100m unconstrained UN-adjusted originale `ita_ppp_2020_UNadj.tif` (160 MB). Ritaglio esatto sui 5 comuni (`worldpop_core_unadj_raw.tif`, 4.283 celle, 25.128 ab grezzi). SHA256: `a441578ca49c...` | Anno 2020 pre-calibrazione; totale grezzo +9,6% vs ISTAT 2025. | Eseguire calibrazione deterministica proporzionale cella-per-cella sui totali comunali ISTAT POSAS 2025 senza alterare la forma della distribuzione intracomunale. |
| **Altimetria e Pendenze (Copernicus DEM)** | `PASS` | Tile COG 30m GLO-30 N45_00_E009_00 da AWS Open Data ESA (`Copernicus_DSM_COG_10_N45_00_E009_00_DEM.tif`, 44 MB). Ritaglio core (`copernicus_dem_core_raw.tif`). SHA256: `14bbb5eb6cca...` | Risoluzione a terra 30 metri; quota min 0m (specchi d'acqua e maschere), max 699,5 m s.l.m. | Utilizzare per calcolare i profili altimetrici delle tratte stradali e penalizzare la camminabilità con funzione di Tobler. |
| **Mobilità Sistematica (Matrice OD ISTAT)** | `PASS` | 1.575 record reali individuali di tipo 'S' estratti dal file a tracciato fisso `matrix_pendo2011_10112014.txt` del 15° Censimento ISTAT. SHA256: `131cc7e5070a...` | Anno di rilevazione 2011; mobilità sistematica (lavoro/studio), non include spostamenti occasionali. | Utilizzare per pesare i flussi interscambio tra frazioni, comuni e stazione FS Olgiate Molgora senza ricorrere a numeri sintetici hard-coded. |
| **Orario Ferroviario Regionale (Trenord S8)** | `PASS` | Feed GTFS ufficiale `trenord_gtfs.zip` da portale Open Data Regione Lombardia (`3z4k-mxz9`). SHA256: `b4296f145b42...`. Stazione Olgiate-Calco-Brivio identificata con ID `S01514`. | Orario teorico di programmazione 2026; non include puntualità reale osservata palina per palina. | Utilizzare per sincronizzazione deterministica delle coincidenze treno-bus in entrambi i sensi (Milano e Lecco). |
| **Rete Stradale e Pedonale (OpenStreetMap)** | `PASS` | 4.477 segmenti viari e pedonali con geometrie reali e 1.762 nodi estratti dal planet PBF `planet_8.872,45.469_9.833,45.883.osm.pbf` (103 MB). SHA256: `8c9e469581ef...` | Livello di completezza attributi (es. marciapiedi separati, illuminazione notturna) variabile su strade secondarie. | Costruire grafo NetworkX deterministico per calcolo distanze e isocrone reali. |
| **Fermate Bus Ufficiali TPL (OSM / Arriva)** | `PASS` | 37 fermate georeferenziate su OSM con operatore Arriva Italia verificate con quadri orario ufficiali di linea. | L'Agenzia TPL Como-Lecco-Varese non pubblica un feed GTFS open data pubblico. | Trattare come FACT la posizione fisica e gli orari di esercizio; classificare ogni eventuale feed GTFS automobilistico come `RECONSTRUCTED NETWORK`. |
| **Chilometraggi e Budget PdB 2025** | `PASS` | Programma di Bacino Agenzia TPL Como-Lecco-Varese (`PdB_Aggiornamento_2025_Relazione_generale.pdf`, 60 MB): D184 (52.560 km/anno), D185 (58.859 km/anno). | Dati annuali aggregati a livello di contratto di servizio. | Utilizzare come benchmark economico-chilometrico ufficiale (totale D184+D185 = 111.419 km/anno). |
| **Passaggi Stretti e Geometrie Critiche** | `FIELD CHECK REQUIRED` | 5 punti critici individuati sulla viabilità minore (stretta di Mondonico, curva Arlate SP72, tornanti San Zeno, via Manzoni Calco, strettoia Monticello). | Non verificabile esclusivamente da dati raster/vettoriali; necessita verifica su raggio di curvatura e ingombro bus 10-12m. | Marcare come `DA VERIFICARE SUL CAMPO` prima di assegnare mezzi standard 12m. |

---

## 3. Discrepanze Rilevate rispetto ai Risultati Preliminari Pre-Audit

| Parametro / Metrica | Valore Pre-Audit (Sintetico) | Nuovo Valore Reale (Audit) | Delta Assoluto | Delta % | Causa Discrepanza | Evidenza Migliore |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Popolazione WorldPop Grezza (5 comuni)** | 22.914 ab (sintetici forzati) | 25.127,76 ab (WorldPop 2020) | +2.213,76 ab | +9,66% | WorldPop grezzo nazionale non vincolato pre-calibrazione vs nuclei hard-coded. | **Reale**: WorldPop 2020 GeoTIFF ritagliato con confini ISTAT. |
| **Origine Distribuzione Spaziale** | Nuclei e decadimento esponenziale manuale (`03_population_grid.py`) | Pixel reali 100m WorldPop da satellite e censimento | - | - | Eliminata assunzione arbitraria sulla localizzazione delle frazioni. | **Reale**: Raster WorldPop UN-adjusted. |
| **Metodo di Misura Distanze Pedonali** | Distanza euclidea × 1,25 (`src/spatial_network.py`) | Rete reale di 4.477 segmenti OSM con pendenze DEM | - | - | Modello euclideo teorico sostituito da routing su grafo. | **Reale**: OpenStreetMap planet PBF + Copernicus DEM GLO-30. |
| **Flussi Pendolari Intercomunali** | Matrice `OD_FLOWS` fittizia hard-coded (`06_od_analysis.py`) | 1.575 record ISTAT 2011 Censimento (`matrix_pendo2011_10112014.txt`) | - | - | Sostituita stima manuale con indagine censuaria reale. | **Reale**: ISTAT Matrice Pendolarismo 2011. |
| **Stazione Hub nel GTFS** | Feed artificiale autoprodotto (`02_parse_gtfs.py`) | Feed ufficiale Trenord S8 (`3z4k-mxz9`), fermata `S01514` | - | - | Sostituito GTFS simulato con feed istituzionale regionale. | **Reale**: Open Data Regione Lombardia / Trenord GTFS. |

---

## 4. Condizioni Vincolanti per l'Avanzamento

In conformità a `COLLABORATION_PROTOCOL.md` (§ 10 Regola di arresto), l'avanzamento ad `AUDIT_CHECKPOINT_2_REAL_SPATIAL` e l'esecuzione di calcoli downstream sono rigorosamente vincolati al rilascio del `PASS` su `GATE A` da parte del revisore esterno indipendente.
