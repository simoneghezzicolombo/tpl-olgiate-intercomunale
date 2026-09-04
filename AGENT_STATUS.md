# AGENT_STATUS

## CODEX checkpoint — Stage D Exact Timetable RT-001 V3

**Timestamp:** 2026-09-04T12:49Z

**Author:** CODEX

**Branch:** `codex/phase2-stage-d-exact-rt001-v3`

**Computational commit:** `3d19e0a0b996428b15826d0b477d9681d3bcdf94`

**Persisted evidence commit:** `d41bb678382d018929c1c6b46542f12549f20d4f`

**Workflow:** `33872934005` — SUCCESS

**Artifact:** `9937340770`, SHA256 `4f9913f6d56242a9052a562919fb2881d8711bc5692e00feda0de79b883b9d99`

Status: **PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3** under contract
`PHASE2_BUDGET_LOSSLESS_EXHAUSTIVE_EXACT_CLOCKFACE_TIMETABLE_RT001_V3`.

- 5,325 daily exact problems, cardinality read from the certified manifest;
- 16,495 budget/calendar plan contexts, all exact-hard-cap eligible;
- 6,772,755 integer route-specific phase vectors exhaustively evaluated;
- 6,000 distinct selected exact timetables and 285,748 explicit public trips;
- 1,292 upstream `SOME_PHASES_BUDGET_FEASIBLE` Stage-C contexts retained;
- all 646 Stage-C contexts recovered by RT-001 remain exact feasible;
- exact annual bus-km derived from the materialised phase vector and reapplied
  against each context's own hard cap;
- in-span passenger-return semantics and technical-closure exclusion retained;
- deterministic vehicle-block assignments materialised separately for recovery
  5, 10, and 15 minutes; no recovery selected;
- deterministic byte-for-byte rebuild, anti-random and anti-cardinality-hardcode
  guards PASS;
- no budget, calendar, topology, PRIMARY, or RUNNER-UP selected.

A separately authored implementation is concurrently running on
`phase2-stage-d-exact-rt001-v3`, and a semantic cross-implementation audit is
being prepared on `phase2-stage-d-v3-cross-implementation-audit`.  This CODEX
checkpoint is therefore ready as an independent comparison target; no branch is
declared authoritative until that audit is complete.

Next dependency: complete the independent cross-implementation audit, then feed
the certified lossless Stage-D lineage to the unchanged Stage-E robustness
engine. Final selection still requires explicit `decision_budget_km` and
`uncertainty_band_min`.

Snapshot strutturata corrente del coordinamento. La cronologia completa resta nella Git history e nella GitHub Issue #1 `Agent Coordination Bus`.

## Stato corrente

**Data:** 2026-09-03
**Fase:** Phase 2 — service-design optimisation
**Branch di integrazione:** `phase2-optimizer-core`
**HEAD dopo integrazione screening:** `c79088c70c313e98600991c118da3f767654650b`

### Gate A–F

A, B, C, D, E e F: **PASS**. Gate F finale: `e84c409ffdbcd0313c93d248496862b5c5356663`.

### Phase 2 — evidenze validate e integrate

- **ISTAT 2021 work OD / demand profile:** PASS, SHA `1b9b3d359be48bf58e592e0698702f58e7559e19`; 8.754 resident workers. Work OD resta una sola componente della domanda.
- **Frozen Gate D graph:** PASS, branch `phase2-graph-freeze`, final HEAD `892c6906168fd658a4733a5b31a7fa3e7ed49207`, CI `33770304214`; 104.071 nodi, 199.217 archi diretti, epoca OSM congelata e routing restriction-aware.
- **Candidate-stop universe V1:** PASS, branch `phase2-stop-universe`, final HEAD `07091300259491c2c9915b41c819af336f89d34a`, CI `33771932566`; 43 cluster fisici esistenti, 180 candidate proposed stops, tutte `PROPOSED_STOP/FIELD_CHECK_PENDING`. Resta un benchmark V1 da rigenerare dopo il layer building-population.
- **Analysis envelope V2:** PASS, branch `phase2-analysis-envelope`, validated computational commit `8a4608a60ecb367535814d965822e7502ae31eb9`, CI `33780587046`; regola primaria `METRIC_GUARD_ONLY`, cioè decision core + 1.210 m derivati dal contratto V1 walk+snap. Intercetta 25 comuni, 621 sezioni censuarie, 12.359 edifici, 60.519 archi del frozen graph, 174 fermate bus ufficiali e 1 rail anchor. `CORE` e `CONTEXT` restano separati; la sensitivity di primo ordine comunale è esplicitamente non supportata dall'epoch Gate D ai bordi e quindi non viene forzata. Snapshot sorgente, checksum e rebuild source-closed sono PASS; nessun output V1 è stato modificato.
- **Current/reference stop×trip timetable:** PASS, source branch final HEAD `dbda7ee2a6f2c3b5f6bfc7d4c6e0e936b2e26189`; 119 colonne di corsa, 104 attive al 2026-09-03, 1.145 orari pubblicati e matrice completa da 3.089 celle. Ricostruzione da fonti primarie ufficiali, nessuna interpolazione degli orari non pubblicati.
- **Current-service stop identity bridge:** PASS / PARTIAL COVERAGE, source branch final HEAD `2616f58a758591adc12bd6a5abe1d1779d2d0b1e`; 209 righe PDF preservate, 54 identità GTFS storiche risolte, 155 ambigue/non risolte. Nessun fuzzy matching, nearest-coordinate forcing o whitelist manuale; le righe non risolte sono vietate come identità spaziali nel walking GJT.
- **Decision-contract hardening:** PASS, source branch `phase2-decision-contract-hardening`, final HEAD `13050318d269eea1dc6779639d8e9e5993090043`; budget decisionale e uncertainty band sono input espliciti, nessun default implicito verso il budget massimo e nessun weighted composite score nascosto.
- **V2 prerequisites integration:** PR #14 MERGED in `phase2-optimizer-core`, merge commit `cdc72eab5ba853144e52e47fb6f98c993352608b`. Il blocker CI era esclusivamente l'interpretazione CRLF del `git diff --check`; correzione al commit `3b0dec7e56657262175ee545397a8d99a94050c9`. Run finale timetable `33795636848`, job `100782538267`: SUCCESS completo, inclusi whitespace audit, test, source rebuild, byte comparison e anti-shortcut guard. Gli altri workflow del PR sono SUCCESS.
- **Topology-neutral structural screening V1:** PASS / BENCHMARK ONLY, source branch HEAD `afe44aac71e0dd9d4d51aeb92c5a80e624f3d471`, PR #15 MERGED in `phase2-optimizer-core` con merge commit `c79088c70c313e98600991c118da3f767654650b`. CI `33795730762`, job `100782848163`: SUCCESS. Screenate esattamente 100.000 configurazioni strutturali su 25.421 gambe dirette uniche; rebuild deterministico byte-for-byte PASS; nessun ranking di famiglie, scelta di topologia, scelta fermate, annualizzazione o service-policy selection. Artifact `9909090951`, SHA256 ZIP `641254b6661bd6436a0a70ff5287b8d47936ed942f0ec6030b64d42b62eb56b0`; CSV interno SHA256 `504879d2fbfc26de3b7c7095c56c406c690701f9e8bcdf9008d4dbb6b4cebced`, verificato contro il validation JSON. Il motore di union delle catchment è input-agnostic e può ricevere unità V1 o edifici V2 senza cambiare algoritmo.
- **S8 interchange:** PASS, branch `phase2-s8-interchange`, final HEAD `88ea13a79bc3a731433dbeeee4985ea11d977580`, CI `33767531076`; 74 eventi S8 reali il 2026-09-03, scoring continuo e topology-neutral.
- **ISTAT 2011 trend audit:** `VALIDATED_WITH_SERIES_BREAK`, branch `phase2-od-2011-audit`, HEAD `329e3b15a3c31c8edc2252babf3e5bb1f6248b8c`; utile come contesto storico, non come serie perfettamente omogenea e non come blocker. PR storico separato non è sulla critical path.
- **Optimizer core:** multi-family topology search, explicit service-policy search, service production, passenger GJT, equity/non-regression, S8 bridge, robust candidate tournament, budget frontier e structural screening. Nessun `np.random`, nessun legacy hardcoded candidate/current-service output.

### Vincoli metodologici invariati

- zero dati sintetici o inventati;
- niente live Overpass nel normale optimisation loop;
- proposed stops non sono fermate fisicamente certificate finché manca il field check;
- `S8_DIRECT` non è modal share;
- popolazione, OD lavoro, accessibilità, S8, opportunità locali e produzione di servizio restano layer distinti;
- nessun weighted composite score nascosto;
- una candidata finale è `scenario_id + plan_id`, quindi topologia e piano di servizio competono con identità distinta;
- il catalogo e lo screening V1 sono benchmark congelati, non un universo autorizzato per la raccomandazione finale.

## Prossimo checkpoint / dipendenze

**BLOCKED sulla validazione del workstream `phase2-building-population`.** Non pubblicare primary, runner-up, fermate definitive o classifica finale usando il benchmark V1.

Dopo building population validato, la catena autorizzata è:

**building population + analysis envelope → Stop Universe V2 → reduced path matrix V2 → rigenerazione/replay del catalogo strutturale V2 → structural/operational screening → service-policy search → S8 phasing → passenger GJT/equity → robustness tournament → primary + runner-up + budget frontier.**

Il budget di riferimento resta quello validato Gate E, 111.419 bus-km/anno; gli envelope inferiori e superiori sono sensitivity di progetto, non un default implicito per la decisione finale.
