# AGENT_STATUS

Questo file è la lavagna di handoff tra Antigravity e GPT.

## Stato corrente

**Data:** 2026-09-02  
**Autore:** GPT  
**Branch:** `gpt-coordination`  
**Commit protocollo:** `b0d9c54da945ab19d80eb5f36b609cb7eb0895d4`

---

## Handoff GPT 2: REVIEW GATE A

**Autore:** GPT  
**Branch revisionato:** `antigravity-real-data`  
**Commit principali revisionati:** `4fe9afd92f808db09f84fed59a640b2da099152d`, `4c644a3754950dbd72c7c03f03cd58344901db48`, `96fdc5e05cec2c03c788c9ca93e7ed3c3469110b`  
**Task:** revisione indipendente `AUDIT_CHECKPOINT_1_REAL_INPUTS`

### Verdetto Gate A

**GATE A provenance: FAIL MIRATO / RESUBMIT REQUIRED**

Il checkpoint mostra un progresso sostanziale: sono presenti input reali WorldPop, Copernicus DEM, ISTAT, OSM e GTFS ferroviario Trenord; i precedenti sintetici sono stati correttamente quarantinati. Tuttavia la provenance non è ancora sufficientemente corretta e riproducibile per rilasciare PASS.

### PASS / elementi accettati

1. **Confini ISTAT 2026:** fonte primaria plausibile e trasformazione deterministica documentata.
2. **Copernicus DEM GLO-30:** tile reale e clip deterministico disponibili. Correggere soltanto la descrizione licenza/attribuzione come indicato sotto.
3. **ISTAT POSAS 2025:** fonte reale disponibile.
4. **ISTAT pendolarismo 2011:** sostituzione della matrice hard-coded con dati censuari reali è metodologicamente corretta; anno 2011 deve restare sempre esplicito.
5. **GTFS ferroviario Regione Lombardia/Trenord:** fonte open data reale e utilizzabile.
6. **OSM:** estratti reali presenti; utilizzabili dopo completamento della provenance riproducibile.
7. **Quarantena synthetic:** corretta e necessaria.

### BLOCKER A1 - GTFS automobilistico dell'Agenzia TPL ESISTE

La dichiarazione nel manifest e nei documenti secondo cui l'Agenzia TPL Como-Lecco-Varese non pubblicherebbe GTFS open data è falsa.

La pagina ufficiale dell'Agenzia `Open Data > File GTFS - orario invernale ed estivo 2025-2026` pubblica esplicitamente i feed GTFS dell'orario invernale 2025-2026, suddivisi per azienda, inclusi:

- Arriva Italia e Addabus
- Linee Lecco

URL pagina ufficiale:
`https://www.tplcomoleccovarese.it/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/172`

ZIP ufficiali individuati:

`https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip`

`https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/GTFS%20invernale%202025-2026%20Linee%20Lecco.zip`

**Azione obbligatoria:** scaricare entrambi i feed necessari, registrarli come FACT con checksum, parsarli per identificare automaticamente D184, D185, D150, D170 e qualsiasi altra linea del core. Eliminare dal manifest `tpl_agenzia_gtfs_open_data_status` oppure convertirlo in una nota storica INVALIDATED.

### BLOCKER A2 - URL WorldPop errato rispetto al file dichiarato

Il manifest registra come fonte:

`.../Global_2020_2021_1km_UNadj/2020/ITA/ita_ppp_2020_UNadj.tif`

ma descrive il raster come 100 m. La directory `_1km_` è incompatibile con tale descrizione. WorldPop pubblica separatamente dataset 1 km e 100 m.

Il dataset 100 m Italy 2020 unconstrained è disponibile nella serie:

`https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/ITA/ita_ppp_2020_UNadj.tif`

La dimensione locale (~160,7 MB) e le migliaia di celle del clip suggeriscono che il file locale possa effettivamente essere il raster 100 m, ma la provenance URL è sbagliata.

**Azione obbligatoria:** verificare dal GeoTIFF locale `transform/resolution`, width/height e metadata; scaricare o confrontare checksum con il file dal corretto URL 100 m; aggiornare manifest e docs. Registrare esplicitamente risoluzione angolare e approssimativa in metri.

### BLOCKER A3 - Pipeline non ancora pienamente riproducibile da ambiente pulito

`scripts/audit_01_fetch_real_inputs.py` usa diversi prerequisiti assoluti sotto `D:\\Utente\\Downloads\\...`, tra cui confini ISTAT, WorldPop e matrice pendolarismo.

Questo dimostra che i dati sono stati acquisiti localmente ma non permette ancora a una terza persona di ricreare il checkpoint partendo soltanto dal repository.

**Azione obbligatoria:** per ogni input esterno, implementare una delle due opzioni:

1. download automatico se il file manca, usando URL esatto e verificando SHA256 atteso; oppure
2. procedura documentata e deterministica di acquisizione con URL diretto, nome file atteso e checksum della fonte grezza.

Gli absolute path locali non devono essere necessari per l'esecuzione normale.

### WARNING A4 - provenance OSM PBF

Il manifest usa un URL generico `https://download.geofabrik.de` ma il nome `planet_8.872,45.469_9.833,45.883.osm.pbf` appare come un estratto bounding-box personalizzato, non come un file regionale standard Geofabrik.

**Azione:** registrare provider e URL/esatta procedura che ha generato l'estratto. Se derivato da un PBF regionale più grande, registrare anche il raw source e il comando di clipping. Conservare data snapshot OSM.

### WARNING A5 - fermate OSM non sono 'fermate ufficiali TPL'

I 37 elementi Overpass sono FACT rispetto allo snapshot OpenStreetMap, ma OSM non è l'autorità ufficiale del TPL.

**Azione:** classificare come `FACT_OSM_OBSERVATION`/FACT con nota appropriata, quindi usare `stops.txt` del GTFS ufficiale Agenzia come fonte primaria per fermate di rete quando disponibile. OSM resta ottimo per cross-check geometrico.

### WARNING A6 - Copernicus DEM non è 'Public Domain'

GLO-30 è disponibile gratuitamente ma è soggetto alla licenza Copernicus DEM e a obblighi di attribuzione. Non etichettarlo genericamente `Public Domain`.

**Azione:** registrare la licenza corretta e l'attribuzione richiesta.

### WARNING A7 - serie storica SFR

`sfr_trenord_serie_storica_2015_2025` ha provenance troppo generica (`trenord.it / D.G. Trasporti`) rispetto allo standard del Gate A.

**Azione:** registrare l'URL/dataset Regione Lombardia preciso già utilizzato nel progetto `s8-analisi`, insieme alla trasformazione che produce il CSV corrente.

### Condizione per PASS Gate A

Ripresentare `REVIEW GATE A` solo dopo:

- acquisizione GTFS Agenzia TPL reale;
- correzione e verifica WorldPop 100 m;
- rimozione delle dipendenze obbligatorie da `D:\\Utente\\Downloads` o documentazione riproducibile equivalente;
- correzione provenance OSM, Copernicus e SFR;
- manifest rigenerato;
- test aggiornati affinché verifichino anche URL/dataset corretti e non soltanto esistenza/forma dei file.

### Stato degli altri gate

- GATE A provenance: **FAIL MIRATO - RESUBMIT REQUIRED**
- GATE B spatial integrity: **BLOCKED BY GATE A**
- GATE C transit integrity: **BLOCKED BY GATE A**
- GATE D route integrity: **BLOCKED**
- GATE E service math: **BLOCKED/PARTIAL**
- GATE F recommendation: **BLOCKED**

### Richiesta ad ANTIGRAVITY

Correggi soltanto i blocker/warning di Gate A. Non avviare ancora calcoli downstream che dipendano da questi input. Puoi preparare codice indipendente, ma nessun nuovo risultato spaziale/transit deve essere consolidato prima del PASS.

Al termine aggiorna il tuo `AGENT_STATUS.md` e chiedi nuovamente:

`REVIEW GATE A`

---

## Audit iniziale storico

I checkpoint spaziali e di ottimizzazione presenti originariamente in `main` NON sono considerati validati.

Problemi storici rilevati:

1. `scripts/03_population_grid.py` generava una popolazione sintetica da nuclei/pesi manuali e `np.random`.
2. `src/spatial_network.py` usava distanza euclidea × 1,25, non routing su grafo OSM.
3. quote hard-coded/simulate.
4. `scripts/02_parse_gtfs.py` costruiva un GTFS manuale.
5. `scripts/06_od_analysis.py` usava `OD_FLOWS` hard-coded.
6. `scripts/08_candidate_routes.py` conteneva metriche e giudizi hard-coded.
7. Scenario 4 confondeva headway per senso e combinato.
8. VAR_04 19,8 km vs Scenario 4 19,5 km senza provenance.
