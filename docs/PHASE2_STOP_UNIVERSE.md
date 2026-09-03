# Phase 2 — Candidate-stop universe e accessibility gaps: PASS

**Verdetto:** PASS  
**Data:** 2026-09-03  
**Branch:** `phase2-stop-universe`  
**Baseline Phase 2:** `1b9b3d359be48bf58e592e0698702f58e7559e19`  
**Commit sorgente/test validato:** `293e85d2ece0782171baee6249092e0ee8e3c87b`  
**Commit output persistiti:** `0c9d1577db30251f7875ef10a72d777d362129b0`  
**CI validata:** run `33771096043`, job `100701210576`  
**Artifact:** `9899673389`, ZIP SHA256 `cc1dfefc2e93ac67a563df81f7f02ac339fd91c0817363dace36578a22149664`

## 1. Significato del PASS

Questo workstream costruisce un universo auditabile di luoghi nei quali una futura ottimizzazione può testare una fermata. **Non progetta la linea finale e non produce una graduatoria delle reti.**

Restano esplicitamente non modificati:

- headway;
- timetable;
- budget;
- topologia finale;
- ranking o recommendation definitiva.

Ogni nuovo punto mantiene contemporaneamente:

- `epistemic_status = PROPOSED_STOP/FIELD_CHECK_PENDING`;
- `physical_status = FIELD_CHECK_PENDING`;
- `candidate_status = HYPOTHESIS_NOT_RECOMMENDATION`.

Nessuna candidata è quindi dichiarata fisicamente realizzabile, sicura o idonea a una specifica classe di autobus senza verifica sul campo.

## 2. Lineage degli input

Il workstream usa snapshot congelati e già validati, non una nuova acquisizione live della rete.

### Gate B

- commit computazionale validato: `55d726564e13acca55ce563cc911263ac513acb0`;
- artifact GitHub Actions: `9873385893`;
- ZIP SHA256: `aca8889c8f1a4148c252c3530a56e8c68fa3f33c8e6ddf81a9ed743c51c1cfd1`;
- contenuti usati: popolazione WorldPop calibrata su POSAS 2025, walking graph reale, fermate GTFS ufficiali, accessibility cell-by-cell.

### Gate D

- commit computazionale validato: `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`;
- artifact GitHub Actions: `9891607118`;
- ZIP SHA256: `6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a`;
- contenuti usati: snapshot stradale strutturale OSM e GTFS ufficiale di riferimento per le assegnazioni di linea.

La CI scarica entrambi gli artifact per ID, ne verifica il checksum e fallisce prima della costruzione se la lineage non coincide.

### Altri input ammessi

- confini comunali ISTAT 2026;
- `data/raw/osm/osm_pois_core.json` e `data/raw/osm/osm_points_core.geojson` come osservazioni OSM congelate;
- profilo ISTAT 2021 del pendolarismo **per lavoro** soltanto come contesto comunale.

La matrice ISTAT 2021 non viene disaggregata artificialmente a fermata e non diventa un peso di domanda puntuale.

## 3. Input esclusi

Sono esclusi dalla pipeline attiva:

- `data/processed/population_grid_calibrated.csv`;
- `data/processed/walk_isochrones_cells.csv`;
- `data/processed/poi_dataset.csv`.

I primi due non sono gli artifact canonici del Gate B PASS. Il terzo deriva da una lista di POI e pesi inseriti manualmente in `scripts/07_poi_analysis.py`, quindi non può essere usato come evidenza reale per questo workstream.

Il validation bundle registra inoltre:

- `legacy_processed_population_used = false`;
- `legacy_hardcoded_poi_dataset_used = false`;
- `live_overpass_used = false`.

## 4. Fermate ufficiali esistenti e walking catchment

Il set istituzionale resta quello del GTFS ufficiale validato da Gate B:

- **66 record GTFS ufficiali** nel relativo universo spaziale;
- **43 cluster fisici** dopo clustering a 40 m;
- **62 record** agganciati al walking graph entro la soglia Gate B di 250 m;
- **40 cluster fisici** con almeno una sorgente pedonale valida.

Tre cluster completamente non agganciati corrispondono a fermate di contesto al bordo dell'universo Gate B, con nomi Monte Marenzo o Calolziocorte e distanze dal grafo di circa 0,75–0,99 km. Non contribuiscono al catchment pedonale.

### Catchment fisico multi-record

Un cluster fisico può contenere più record GTFS, per esempio fermate contrapposte sui due lati della strada. La versione finale usa **tutti i record GTFS agganciati del cluster come sorgenti simultanee** nel grafo pedonale, con il rispettivo connector time.

Metodo registrato:

`MULTI_SOURCE_ALL_SNAPPED_GTFS_RECORDS_PER_40M_CLUSTER`

Questo evita di sottostimare un catchment scegliendo arbitrariamente un solo record rappresentativo.

### Nota sui comuni di bordo

Il campo `COMUNE` delle fermate eredita la semantica Gate B: le fermate sono selezionate nella geometria dei cinque comuni con buffer e poi associate al comune core più vicino. Per fermate poste appena oltre il confine il campo è quindi **contesto del comune core più vicino**, non una certificazione del comune amministrativo legale della palina.

## 5. Baseline di accessibilità e gap

Denominatore Gate B calibrato 2025: **22.914 residenti**.

| Soglia pedonale | Copertura baseline | Popolazione fuori catchment |
| --- | ---: | ---: |
| 5 min | 48,6868% | circa 11.757,91 |
| 8 min | 72,1229% | circa 6.387,76 |
| 10 min | 80,0033% | circa 4.582,05 |
| 12 min | 85,9040% | circa 3.229,97 |

La soglia principale destinata al successivo ottimizzatore è **10 minuti**, coerente con il replay Gate B già validato. Restano materializzate anche le soglie 5, 8 e 12 minuti.

### Gap a 10 minuti per comune

| Comune | Popolazione fuori catchment | Quota comunale fuori catchment |
| --- | ---: | ---: |
| Brivio | 331,13 | 7,60% |
| Calco | 547,24 | 10,02% |
| La Valletta Brianza | 1.538,13 | 33,04% |
| Olgiate Molgora | 2.120,94 | 33,50% |
| Santa Maria Hoè | 44,61 | 2,12% |

Queste quantità descrivono accessibilità residenziale sul walking graph. Non equivalgono a domanda TPL osservata e non autorizzano da sole una scelta topologica.

## 6. Settlement e destination anchors

Dagli snapshot OSM congelati vengono estratti:

- **57 settlement anchors**;
- **30 destination anchors**.

Sono `FACT_OSM_OBSERVATION`, senza pesi di attrattività manuali. OSM non è una registry esaustiva, quindi l'assenza di un POI non dimostra l'assenza della destinazione nel territorio.

Le destination categories ammesse sono classi osservabili come istruzione, sanità, servizi civici, principali strutture commerciali, sport e alcune destinazioni turistiche. Non vengono riutilizzati i pesi legacy.

## 7. Generazione delle fermate proposte

I punti sono generati soltanto su segmenti del grafo Gate D che risultano strutturalmente bus-eligible secondo la stessa precedenza modale:

`bus > psv > vehicle/motor_vehicle/access`

Valori espliciti non riconosciuti per `bus` o `psv` falliscono chiusi. Gli accessi condizionali restano tracciati come incertezza. Motorway e trunk non vengono usati come siti di fermata.

Assunzioni dichiarate del discovery/pruning:

- campionamento stradale: 150 m;
- raggio massimo tra evidence seed e sample: 800 m;
- eliminazione di punti entro 150 m di walking-network distance da una fermata ufficiale;
- distanza minima deterministica fra candidate conservate: 220 m;
- controllo di ridondanza catchment: Jaccard ≥ 0,90 entro 500 m.

Questi valori sono **ASSUMPTION di costruzione dell'universo ridotto**, non standard fisici o regole di esercizio. Nel run finale il pruning a 220 m ha già eliminato tutte le ulteriori ridondanze che avrebbero richiesto il filtro Jaccard; il codice Jaccard resta comunque corretto e coperto da test.

### Audit del pruning

È stato corretto un errore individuato in red-team: dopo l'ordinamento geometrico, i set di celle del catchment potevano restare associati all'indice precedente. La versione finale conserva una chiave stabile pre-sort.

Metodo registrato:

`STABLE_PRE_SORT_KEYS`

## 8. Dimensione finale dell'universo

La riduzione auditabile produce:

- 2.559 sample stradali bus-eligible con accesso al walking graph Gate B;
- 1.296 seed candidati prima del primo thinning geometrico;
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

Questa è una distribuzione dell'universo di test, **non una graduatoria di bisogno o di priorità**.

## 9. Metriche candidate

Per ogni candidata sono disponibili, tra le altre:

- popolazione raggiungibile a 5/8/10/12 minuti;
- popolazione aggiuntiva rispetto ai catchment ufficiali;
- popolazione sovrapposta ai catchment esistenti e relativa percentuale;
- walking-network distance dalla fermata ufficiale più vicina;
- settlement coverage e settlement aggiuntivi;
- destination coverage e destination aggiuntive;
- linee ufficiali del GTFS di riferimento presenti alla fermata più vicina;
- opportunità di interscambio di riferimento;
- classe stradale Gate D e uncertainty flags;
- lineage e stato epistemico.

Il file candidate-cell a 10 minuti contiene **13.406 righe** e copre tutte le 180 candidate, così il successivo ottimizzatore può comporre unioni di catchment senza ricalcolare buffer euclidei.

### Descrizione numerica, non ranking

Popolazione aggiuntiva a 10 minuti per singola candidata:

- mediana: circa **63,41**;
- media: circa **134,27**;
- 90° percentile: circa **348,52**;
- massimo: circa **1.045,89**.

Distanza pedonale di rete dalla fermata ufficiale più vicina:

- minimo: circa **177 m**;
- mediana: circa **951 m**;
- massimo: circa **3.297 m**.

Una candidata senza incremento demografico a 8/10 minuti è conservata perché copre un settlement OSM precedentemente fuori soglia. Questo è coerente con la regola che il discovery non deve essere population-only.

## 10. Test neutrale dell'ipotesi Arlate

Il GTFS ufficiale di riferimento validato contiene ad Arlate fermate servite da **D150 e D170**. Esiste quindi una reale opportunità candidata di interscambio con altri servizi ufficiali se una futura topologia scegliesse di raggiungere Arlate.

Il medesimo GTFS di riferimento non contiene D201/D202. Di conseguenza la pipeline registra esplicitamente:

`D201/D202 Circolare Meratese absent from validated 2025-2026 GTFS, so no shared-stop claim is made`

Una verifica separata della pagina corrente dell'Agenzia TPL conferma l'esistenza delle linee D201 e D202 come Circolare Meratese e di D170 come Arlate–Vimercate, ma la fonte consultata non dimostra che D201/D202 servano una fermata di Arlate. Questa verifica corrente è contesto, non input computazionale del workstream.

Fonte corrente Agenzia TPL: https://www.tplcomoleccovarese.it/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/134

**Conclusione Arlate:** opportunità candidata D150/D170 sì; interscambio Circolare Meratese ad Arlate non dimostrato; nessuna ragione per forzare la topologia verso Arlate.

## 11. Incertezze fisiche e stradali

Tutte le 180 candidate mantengono almeno una road uncertainty Gate D, spesso per assenza di tag OSM su larghezza, corsie o vincoli dimensionali. Nel run finale le classi stradali dei punti proposti comprendono service, unclassified, residential, tertiary e primary.

In particolare:

- **64 candidate** ricadono su strade classificate OSM `service`;
- **2 candidate** conservano `conditional_access=destination` tra gli uncertainty flags.

Queste righe possono essere utili al discovery, ma sono particolarmente sensibili al field check. Il fatto che un segmento sia strutturalmente bus-eligible nel grafo non dimostra spazio di fermata, sicurezza pedonale, visibilità, marciapiede, swept path, possibilità di incrocio o autorizzabilità della palina.

## 12. Output persistiti

La branch contiene i seguenti output optimizer-facing:

- `outputs/phase2/existing_official_stops.csv`;
- `outputs/phase2/existing_official_stops.geojson`;
- `outputs/phase2/existing_stop_catchment_summary.csv`;
- `outputs/phase2/existing_stop_catchment_cells_12min.csv`;
- `outputs/phase2/accessibility_gap_cells.csv`;
- `outputs/phase2/accessibility_gap_cells.geojson`;
- `outputs/phase2/settlement_destination_anchors.csv`;
- `outputs/phase2/settlement_destination_anchors.geojson`;
- `outputs/phase2/proposed_stop_candidates.csv`;
- `outputs/phase2/proposed_stop_candidates.geojson`;
- `outputs/phase2/proposed_stop_candidate_catchment_cells_10min.csv`;
- `outputs/phase2/interchange_opportunities.csv`;
- `outputs/phase2/candidate_pruning_audit.csv`;
- `outputs/phase2/stop_universe_validation.json`;
- `outputs/phase2/stop_universe_checksums.sha256`.

Il file checksum copre tutti gli output materializzati del workstream.

## 13. Test e riproducibilità

Run finale validato `33771096043`, job `100701210576`:

- download e SHA256 Gate B PASS: PASS;
- download e SHA256 Gate D PASS: PASS;
- materializzazione completa: PASS;
- test stop-universe: **9/9 PASS**;
- guardrail anti-synthetic: **3/3 PASS**;
- `py_compile`: PASS;
- contract assertions: PASS;
- `git diff --check 1b9b3d359be48bf58e592e0698702f58e7559e19...HEAD`: PASS;
- persistenza output optimizer-facing: PASS;
- artifact finale: PASS.

Artifact finale:

- ID `9899673389`;
- ZIP SHA256 `cc1dfefc2e93ac67a563df81f7f02ac339fd91c0817363dace36578a22149664`.

## 14. Limiti epistemici

- WorldPop/POSAS misura distribuzione residenziale stimata/calibrata, non domanda TPL osservata puntuale.
- ISTAT 2021 è pendolarismo per lavoro a livello comunale, non domanda totale e non OD di fermata.
- OSM settlement/POI è osservazionale e non esaustivo.
- Il GTFS bus usato per route assignment è ufficiale ma appartiene al periodo di riferimento 2025-2026; il servizio corrente post 2026-06-08 resta governato da Gate C e non viene inventato qui.
- `road_eligibility_status = DERIVED_GATE_D_BUS_ELIGIBLE` è eleggibilità strutturale del segmento nel modello, non certificazione di una fermata fisica.

## 15. Decisione finale

**PHASE 2 — CANDIDATE-STOP UNIVERSE: PASS.**

Il workstream consegna un set ridotto, geografico, tabellare, checksum-validato e auditabile di **180 candidate** più il set ufficiale esistente, i catchment, i gap e le opportunità di interscambio necessarie alla fase successiva.

Il prossimo lavoro consentito è costruire la **reduced stop/path matrix** e usare questi `candidate_id` nel generatore/ottimizzatore delle topologie sul grafo Gate D congelato. La selezione della rete, il calendario, la frequenza e il budget restano fasi successive.