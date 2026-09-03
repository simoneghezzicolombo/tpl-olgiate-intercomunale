# AGENT_STATUS

Questo file è la snapshot strutturata corrente del coordinamento tra agenti. La cronologia completa resta disponibile nella Git history e nella GitHub Issue #1 `Agent Coordination Bus`.

## Stato corrente

**Data:** 2026-09-03  
**Autore:** GPT external reviewer / co-developer  
**Branch:** `phase2-stop-universe`  
**Task:** Phase 2 — costruzione auditabile del candidate-stop universe e delle accessibility gaps  
**Verdetto:** **PASS**

### Baseline e dipendenze

- baseline Phase 2: `1b9b3d359be48bf58e592e0698702f58e7559e19` (`phase2-service-design`);
- Gate B: PASS, commit computazionale `55d726564e13acca55ce563cc911263ac513acb0`;
- Gate C: PASS, commit finale `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`;
- Gate D: PASS, commit computazionale `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`;
- Gate F aveva già chiuso A–F senza una topologia definitiva e ha motivato la necessità di specificare stop set e service design in Phase 2.

### Commit del workstream

- sorgente/test validato: `293e85d2ece0782171baee6249092e0ee8e3c87b`;
- output optimizer-facing persistiti: `0c9d1577db30251f7875ef10a72d777d362129b0`;
- verbale autorevole: `docs/PHASE2_STOP_UNIVERSE.md`.

### CI validata

- workflow: `Phase 2 candidate-stop universe`;
- run: `33771096043`;
- job: `100701210576`;
- 9/9 test stop-universe PASS;
- 3/3 anti-synthetic guardrail PASS;
- compile PASS;
- contract assertions PASS;
- `git diff --check` dalla baseline Phase 2 PASS;
- download/checksum degli artifact Gate B e Gate D PASS;
- persistenza output e artifact upload PASS.

Artifact finale del run validato:

- ID `9899673389`;
- ZIP SHA256 `cc1dfefc2e93ac67a563df81f7f02ac339fd91c0817363dace36578a22149664`.

### Risultati principali

- popolazione Gate B calibrata: **22.914**;
- fermate ufficiali: **66 record GTFS**, **43 cluster fisici**, **62 record snapped** entro 250 m;
- baseline walking coverage: 48,6868% a 5 min, 72,1229% a 8 min, **80,0033% a 10 min**, 85,9040% a 12 min;
- gap a 10 min: circa **4.582 residenti**, con quota maggiore a Olgiate Molgora e La Valletta Brianza;
- OSM anchors: **57 settlement**, **30 destination**;
- sample bus-eligible Gate D con walking access: **2.559**;
- candidate prima del pruning finale: **347**;
- candidate finali: **180**;
- candidate-cell matrix 10 min: **13.406 righe**, tutte le 180 candidate rappresentate.

### Contratto epistemico

Ogni nuova fermata è:

- `PROPOSED_STOP/FIELD_CHECK_PENDING`;
- `FIELD_CHECK_PENDING` sul piano fisico;
- `HYPOTHESIS_NOT_RECOMMENDATION`;
- `DERIVED_GATE_D_BUS_ELIGIBLE` per il solo segmento stradale modellato.

Nessuna candidata è certificata fisicamente realizzabile. Tutte mantengono road uncertainty flags Gate D e richiedono verifica sul campo prima di qualsiasi scelta operativa.

WorldPop/POSAS misura accessibilità residenziale, non domanda TPL puntuale. ISTAT 2021 resta domanda di pendolarismo per lavoro a livello comunale e non viene disaggregata a fermata. Gli anchor OSM sono osservazioni reali ma non esaustive.

### Arlate

Il GTFS ufficiale di riferimento dimostra fermate Arlate servite da **D150 e D170**, quindi esiste una opportunità candidata di interscambio con questi servizi. D201/D202 Circolare Meratese non sono nel GTFS di riferimento consumato dalla pipeline e la verifica corrente dell'Agenzia non dimostra una fermata D201/D202 ad Arlate. Nessun shared-stop con la Circolare viene quindi dichiarato e Arlate non è forzata nella topologia.

### Output canonici

Gli output optimizer-facing sono in `outputs/phase2/`:

- `existing_official_stops.*`;
- `existing_stop_catchment_*`;
- `accessibility_gap_cells.*`;
- `settlement_destination_anchors.*`;
- `proposed_stop_candidates.*`;
- `proposed_stop_candidate_catchment_cells_10min.csv`;
- `interchange_opportunities.csv`;
- `candidate_pruning_audit.csv`;
- `stop_universe_validation.json`;
- `stop_universe_checksums.sha256`.

### Open issues non bloccanti

- tutte le proposed stops richiedono field check fisico;
- 64 candidate sono su OSM `service` e richiedono particolare cautela;
- 2 candidate conservano `conditional_access=destination`;
- gli anchor OSM non sono una registry completa delle destinazioni;
- per le fermate nel buffer di bordo, `COMUNE` eredita la semantica Gate B di comune core più vicino e non certifica il comune amministrativo legale;
- eventuale interscambio corrente con D201/D202 ad Arlate richiede evidenza stop-level corrente separata.

## Prossimo checkpoint

**Phase 2 — reduced stop/path matrix e topology generation.**

Richiesta precisa al prossimo agente: usare i `candidate_id` e la candidate-cell matrix di questo workstream insieme al grafo Gate D congelato per costruire una matrice ridotta stop/path riproducibile e generare famiglie topologiche concorrenti. Non introdurre ancora ranking finale, timetable, headway o budget operativo se non nella fase esplicitamente autorizzata dalla service-design specification.