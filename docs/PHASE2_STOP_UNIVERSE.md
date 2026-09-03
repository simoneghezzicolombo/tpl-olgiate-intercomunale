# Phase 2 — Candidate-stop universe e accessibility gaps: PASS

**Verdetto:** PASS
**Data:** 2026-09-03
**Branch:** `phase2-stop-universe`
**Baseline Phase 2:** `1b9b3d359be48bf58e592e0698702f58e7559e19`
**Commit sorgente/test validato:** `293e85d2ece0782171baee6249092e0ee8e3c87b`
**Commit output persistiti:** `0c9d1577db30251f7875ef10a72d777d362129b0`
**CI computazionale validata:** run `33771096043`, job `100701210576`
**Artifact:** `9899673389`, ZIP SHA256 `cc1dfefc2e93ac67a563df81f7f02ac339fd91c0817363dace36578a22149664`

## 1. Significato del PASS

Questo workstream costruisce un universo auditabile di luoghi nei quali una futura ottimizzazione può testare una fermata. Non progetta la linea finale e non produce una graduatoria delle reti.

Restano esplicitamente non modificati headway, timetable, budget, topologia finale e ranking definitivo. Il validation bundle registra `final_network_selected=false`, `headway_modified=false`, `timetable_modified=false`, `budget_modified=false` e `ranking_produced=false`.

Ogni nuovo punto mantiene:

- `epistemic_status = PROPOSED_STOP/FIELD_CHECK_PENDING`;
- `physical_status = FIELD_CHECK_PENDING`;
- `candidate_status = HYPOTHESIS_NOT_RECOMMENDATION`;
- `road_eligibility_status = DERIVED_GATE_D_BUS_ELIGIBLE`.

Nessuna candidata è dichiarata fisicamente realizzabile, sicura o idonea a una specifica classe di autobus senza verifica sul campo.

## 2. Protocollo e lineage

`AGENT_PROTOCOL.md` non è presente nel repository. Il protocollo effettivo è `COLLABORATION_PROTOCOL.md`, che rende GitHub fonte condivisa di verità e impone provenance, stati epistemici e regola anti-sintetico.

Il workstream riusa snapshot congelati già validati, senza una nuova acquisizione live della rete.

### Gate B

- commit computazionale: `55d726564e13acca55ce563cc911263ac513acb0`;
- artifact GitHub Actions: `9873385893`;
- ZIP SHA256: `aca8889c8f1a4148c252c3530a56e8c68fa3f33c8e6ddf81a9ed743c51c1cfd1`;
- contenuti usati: popolazione WorldPop calibrata su POSAS 2025, walking graph reale, fermate GTFS ufficiali e accessibility cell-by-cell.

### Gate C

Gate C è PASS al commit `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`. Le assegnazioni di linea del GTFS bus usate qui descrivono il periodo ufficiale di riferimento 2025-2026 e non vengono presentate come servizio corrente post 2026-06-08.

### Gate D

- commit computazionale: `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`;
- artifact GitHub Actions: `9891607118`;
- ZIP SHA256: `6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a`;
- contenuti usati: snapshot stradale strutturale OSM e semantica di bus eligibility Gate D.

La CI scarica Gate B e Gate D per artifact ID, verifica i checksum e fallisce prima della costruzione se la lineage non coincide.

Altri input ammessi sono i confini comunali ISTAT 2026, gli snapshot OSM congelati `osm_pois_core.json` e `osm_points_core.geojson` e il profilo ISTAT 2021 del pendolarismo per lavoro, usato soltanto come contesto comunale.

## 3. Input esclusi

La pipeline non usa:

- `data/processed/population_grid_calibrated.csv`;
- `data/processed/walk_isochrones_cells.csv`;
- `data/processed/poi_dataset.csv`.

I primi due non sono gli artifact canonici del Gate B PASS. Il terzo deriva da una lista di POI e pesi inseriti manualmente in `scripts/07_poi_analysis.py` e non è ammesso come evidenza reale del workstream.

Il validation bundle registra:

- `legacy_processed_population_used = false`;
- `legacy_hardcoded_poi_dataset_used = false`;
- `live_overpass_used = false`.

## 4. Fermate ufficiali e catchment esistenti

Il set istituzionale deriva dal GTFS ufficiale validato da Gate B:

- 66 record GTFS ufficiali;
- 43 cluster fisici ottenuti con clustering a 40 m;
- 62 record agganciati al walking graph entro 250 m;
- 40 cluster con almeno una sorgente pedonale valida.

Tre cluster di contesto al bordo dell'universo Gate B non hanno una sorgente pedonale valida e non contribuiscono ai catchment.

Per ogni cluster fisico il catchment viene calcolato con tutti i record GTFS agganciati del cluster come sorgenti simultanee, non scegliendo arbitrariamente un solo lato della strada. Metodo registrato:

`MULTI_SOURCE_ALL_SNAPPED_GTFS_RECORDS_PER_40M_CLUSTER`

## 5. Baseline di accessibilità e gap

Denominatore Gate B calibrato 2025: **22.914 residenti**.

| Soglia | Copertura baseline | Popolazione fuori catchment |
| --- | ---: | ---: |
| 5 min | 48,6868% | 11.757,91 |
| 8 min | 72,1229% | 6.387,76 |
| 10 min | 80,0033% | 4.582,05 |
| 12 min | 85,9040% | 3.229,97 |

La soglia principale destinata al successivo ottimizzatore è 10 minuti, coerente con il replay Gate B validato. Le soglie 5, 8 e 12 minuti restano comunque materializzate.

Gap residenziale a 10 minuti:

| Comune | Popolazione fuori catchment | Quota comunale |
| --- | ---: | ---: |
| Brivio | 331,13 | 7,60% |
| Calco | 547,24 | 10,02% |
| La Valletta Brianza | 1.538,13 | 33,04% |
| Olgiate Molgora | 2.120,94 | 33,50% |
| Santa Maria Hoè | 44,61 | 2,12% |

Queste quantità descrivono accessibilità residenziale sul walking graph. Non equivalgono a domanda TPL osservata e non autorizzano da sole una scelta topologica.

## 6. Settlement e destination anchors

Dagli snapshot OSM congelati vengono estratti 57 settlement anchors e 30 destination anchors. Sono `FACT_OSM_OBSERVATION` e non ricevono pesi di attrattività manuali. OSM non è una registry esaustiva.

Alla soglia di 10 minuti risultano fuori dai catchment correnti:

- 32 settlement su 57;
- 3 destination su 30.

## 7. Generazione e pruning delle proposed stops

I punti sono generati soltanto su segmenti Gate D strutturalmente bus-eligible, rispettando la precedenza modale `bus > psv > vehicle/motor_vehicle/access`. Motorway e trunk non sono usati come siti di fermata. Gli accessi condizionali restano tracciati come incertezza.

Assunzioni dichiarate per costruire l'universo ridotto:

- campionamento stradale: 150 m;
- raggio seed-sample: 800 m;
- eliminazione entro 150 m di walking-network distance da una fermata ufficiale;
- distanza minima deterministica fra candidate conservate: 220 m;
- controllo di ridondanza catchment: Jaccard ≥ 0,90 entro 500 m.

Sono `ASSUMPTION` di discovery/pruning, non standard fisici o regole di esercizio.

Un errore individuato in red-team nell'allineamento fra ordinamento geometrico e set di celle del catchment è stato corretto usando chiavi stabili pre-sort. Metodo registrato: `STABLE_PRE_SORT_KEYS`.

## 8. Dimensione finale dell'universo

La pipeline produce:

- 2.559 sample stradali bus-eligible con accesso al walking graph Gate B;
- 1.296 seed prima del primo thinning;
- 381 dopo il primo thinning;
- 347 prima del pruning finale;
- **180 proposed-stop candidates finali**.

Distribuzione territoriale delle 180 candidate:

| Comune core di contesto | Candidate |
| --- | ---: |
| La Valletta Brianza | 63 |
| Olgiate Molgora | 44 |
| Brivio | 30 |
| Calco | 28 |
| Santa Maria Hoè | 15 |

La distribuzione è descrittiva e non rappresenta una graduatoria.

## 9. Metriche disponibili per l'ottimizzatore

Per ogni candidata sono materializzate popolazione raggiungibile e popolazione aggiuntiva a 5/8/10/12 minuti, overlap con catchment ufficiali, walking-network distance dalla fermata ufficiale più vicina, settlement e destination coverage, linee del GTFS di riferimento alla fermata più vicina, opportunità di interscambio, classe stradale, uncertainty flags, lineage e stato epistemico.

`proposed_stop_candidate_catchment_cells_10min.csv` contiene 13.406 righe e copre tutte le 180 candidate, così l'ottimizzatore può comporre unioni di catchment senza ricorrere a buffer euclidei.

Descrizione del set, non ranking:

- 175/180 candidate aggiungono popolazione alla soglia di 10 minuti;
- incremento mediano a 10 minuti: circa 63,41 residenti calibrati;
- massimo per singola candidata: circa 1.045,89;
- distanza pedonale di rete dalla fermata ufficiale più vicina: mediana circa 951 m;
- 74 candidate aggiungono almeno un settlement a 10 minuti;
- 13 aggiungono almeno una destination.

## 10. Test neutrale Arlate

Il GTFS ufficiale di riferimento contiene ad Arlate fermate servite da D150 e D170. Se una futura topologia raggiunge Arlate, esiste quindi una opportunità candidata di interscambio con questi servizi.

Il medesimo GTFS di riferimento non contiene D201/D202. La pipeline registra esplicitamente che non viene fatta alcuna dichiarazione di shared stop con la Circolare Meratese. Una verifica corrente dell'Agenzia TPL conferma l'esistenza di D201/D202 come Circolare Meratese e di D170 come Arlate-Vimercate, ma la fonte consultata non dimostra che D201/D202 servano una fermata di Arlate.

Conclusione: opportunità D150/D170 sì, interscambio Circolare Meratese ad Arlate non dimostrato, nessun favoritismo o obbligo topologico verso Arlate.

## 11. Incertezze fisiche

Tutte le 180 candidate restano `FIELD_CHECK_PENDING`. Il fatto che un segmento sia strutturalmente bus-eligible non dimostra spazio di fermata, sicurezza pedonale, visibilità, marciapiede, swept path, possibilità di incrocio o autorizzabilità della palina.

Nel set finale:

- 64 candidate sono su OSM `service`;
- 2 conservano `conditional_access=destination`;
- nessuna è su motorway o trunk.

Queste condizioni non invalidano il discovery ma aumentano la priorità del field check se una candidata entrerà in una topologia finalista.

## 12. Output persistiti

Gli output optimizer-facing sono in `outputs/phase2/`:

- `existing_official_stops.csv` e `.geojson`;
- `existing_stop_catchment_summary.csv`;
- `existing_stop_catchment_cells_12min.csv`;
- `accessibility_gap_cells.csv` e `.geojson`;
- `settlement_destination_anchors.csv` e `.geojson`;
- `proposed_stop_candidates.csv` e `.geojson`;
- `proposed_stop_candidate_catchment_cells_10min.csv`;
- `interchange_opportunities.csv`;
- `candidate_pruning_audit.csv`;
- `stop_universe_validation.json`;
- `stop_universe_checksums.sha256`.

Il manifest contiene 14 checksum SHA256 e tutti sono stati ricalcolati e verificati contro l'artifact finale. SHA256 del manifest stesso: `d2e987aeed4bb5ccc5eeab433cb61165aa9dc808458f33d618341398e026ec5c`.

## 13. Test e riproducibilità

Run computazionale finale `33771096043`, job `100701210576`:

- download e SHA256 Gate B PASS: PASS;
- download e SHA256 Gate D PASS: PASS;
- materializzazione completa: PASS;
- test stop-universe: **9/9 PASS**;
- guardrail anti-synthetic: **3/3 PASS**;
- `py_compile`: PASS;
- contract assertions: PASS;
- `git diff --check` dalla baseline Phase 2: PASS;
- persistenza output optimizer-facing: PASS;
- artifact finale: PASS.

Totale test dedicati e guardrail: **12/12 PASS**.

## 14. Limiti epistemici

- WorldPop/POSAS misura distribuzione residenziale stimata e calibrata, non domanda TPL osservata puntuale.
- ISTAT 2021 è pendolarismo per lavoro a livello comunale, non domanda totale e non OD di fermata.
- OSM settlement/POI è osservazionale e non esaustivo.
- Le route assignment GTFS sono ufficiali del periodo di riferimento, non garanzia di servizio corrente post 2026-06-08.
- `DERIVED_GATE_D_BUS_ELIGIBLE` certifica solo l'eleggibilità strutturale modellata del segmento, non la fattibilità fisica della palina.

## 15. Decisione finale

**PHASE 2 — CANDIDATE-STOP UNIVERSE: PASS.**

Il workstream consegna un set ridotto, geografico, tabellare, checksum-validato e auditabile di 180 candidate, insieme al set ufficiale esistente, ai catchment, alle accessibility gaps e alle opportunità di interscambio necessarie alla fase successiva.

Il prossimo lavoro consentito è costruire la reduced stop/path matrix e usare questi `candidate_id` nel generatore delle topologie sul grafo Gate D congelato. La selezione della rete, il calendario, la frequenza e il budget restano fasi successive.