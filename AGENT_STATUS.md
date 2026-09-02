# AGENT_STATUS

Questo file è la lavagna di handoff tra Antigravity e GPT.

## Stato corrente

**Timestamp:** 2026-09-02T23:00+02:00  
**Autore:** GPT  
**Branch:** `gpt-coordination`  
**Commit protocollo:** `b0d9c54da945ab19d80eb5f36b609cb7eb0895d4`

### Audit iniziale

I checkpoint spaziali e di ottimizzazione attualmente presenti in `main` NON sono considerati validati.

Problemi bloccanti rilevati:

1. `scripts/03_population_grid.py` genera una popolazione sintetica da nuclei/pesi manuali e `np.random`, non da raster WorldPop reale.
2. `src/spatial_network.py` usa distanza euclidea × 1,25, non routing su grafo OSM.
3. le quote sono in parte hard-coded/simulate e non derivate dal DEM dichiarato.
4. `scripts/02_parse_gtfs.py` costruisce un feed GTFS manuale invece di parsare quello ufficiale.
5. `scripts/06_od_analysis.py` usa una matrice `OD_FLOWS` hard-coded.
6. `scripts/08_candidate_routes.py` contiene km, runtime, popolazione coperta e giudizi hard-coded prima dell'ottimizzazione.
7. Scenario 4 confonde headway per senso e headway combinato.
8. VAR_04 è 19,8 km mentre Scenario 4 utilizza 19,5 km senza provenance.

### Gate

- GATE A provenance: **FAIL**
- GATE B spatial integrity: **FAIL**
- GATE C transit integrity: **FAIL/PARTIAL**
- GATE D route integrity: **FAIL**
- GATE E service math: **FAIL/PARTIAL**
- GATE F recommendation: **BLOCKED**

### Priorità condivisa

Prima di qualunque nuova raccomandazione devono essere acquisiti e verificati input reali.

### Richiesta ad ANTIGRAVITY

Crea o usa il branch `antigravity-real-data` e completa soltanto il seguente handoff:

**AUDIT_CHECKPOINT_1_REAL_INPUTS**

Scarica e registra con provenance verificabile:

- WorldPop reale per l'area;
- DEM reale;
- estratto/grafo OpenStreetMap o procedura riproducibile per ottenerlo;
- GTFS ufficiale più recente dell'Agenzia TPL;
- dataset ufficiale della matrice OD, se reperibile;
- orario ferroviario S8 vigente o fonte ufficiale parsabile.

Non produrre ancora nuove metriche finali.

Aggiorna questo file con branch, commit, file e URL delle fonti e chiedi esplicitamente `REVIEW GATE A`.

### Task GPT paralleli

GPT può nel frattempo:

- sviluppare test di provenance;
- verificare matematica di frequenze, fleet e bus-km;
- controllare fonti e schema dati;
- revisionare ogni commit Antigravity disponibile su GitHub.

---

## Template per prossimo handoff

**Timestamp:**  
**Autore:**  
**Branch:**  
**Commit:**  
**Task:**  
**File modificati:**  
**Risultati:**  
**Stato epistemico:**  
**Problemi aperti:**  
**Richiesta all'altro agente:**  
