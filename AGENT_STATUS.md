# AGENT_STATUS

Snapshot strutturata corrente del coordinamento. La cronologia completa resta nella Git history e nella GitHub Issue #1 `Agent Coordination Bus`.

## Stato corrente

**Data:** 2026-09-04  
**Fase:** Phase 2 — final-tournament input readiness
**Ultima lineage operativa integrata:** Stage E RT001 V3 @ `063e119` + repaired Stage-C evidence
**Final-tournament contract audit:** **V2 INCOMPATIBLE; V3 non-decisional Pareto frontier PASS; final selection BLOCKED**
**PRIMARY selection authorised:** **false**  
**RUNNER-UP selection authorised:** **false**

## Governance

- GitHub Issue #1 `Agent Coordination Bus` resta il bus di coordinamento operativo.
- `COLLABORATION_PROTOCOL.md` è il documento di collaborazione esistente.
- `AGENT_PROTOCOL.md` non risulta essere mai esistito nella lineage auditata. Non viene creato retroattivamente e nessuna run storica viene dichiarata dipendente da quel file.
- Le evidenze computazionali devono essere identificate tramite branch/commit, validation contract e SHA256.

## Phase 2 — evidenze correnti

### Tournament Contract Audit + Non-Decisional Frontier RT001 V3

- branch `codex/phase2-final-tournament-rt001-v3`;
- evidence/source commit `8d858793200b3ab644d2612a272ad0ac614d6c34`;
- CI `33885550489` SUCCESS;
- artifact `9941685708`, SHA256 `e1db684c081373d6cd4ddc76785501f7f9e144e7f7e797a9641e3654beddf0af`;
- contract audit `PASS_PHASE2_LEGACY_TOURNAMENT_CONTRACT_AUDIT_RT001_V3`;
- frontier validation `PASS_PHASE2_NON_DECISIONAL_TOURNAMENT_FRONTIER_RT001_V3`.

Verdetto sul contratto V2: **incompatibile con l'evidenza certificata corrente**. I campi GJT demand-weighted e missed-connection probability non esistono; Stage-E engineering retention non viene reinterpretata come probabilità; current continuity resta lower-bound; complexity/unverified fields non hanno equivalenti certificati. Inoltre la chiave V2 `(scenario_id, plan_id)` ha 9.534 identità uniche su 16.495 contesti e comprimerebbe 6.961 contesti budget/timetable distinti.

Il contratto V3 usa invece `(plan_context_id, selected_timetable_id)`, 29 assi certificati senza pesi, confronto decimal exact a tolleranza zero e 12 partizioni separate per sei budget e due classi di completezza. Missing values non sono imputati. Risultato descrittivo: 12.284 contesti non dominati e 4.211 dominati. La frontiera non è ranking, shortlist o raccomandazione.

`legacy_v2_finalizer_invoked=false`
`candidate_evaluation_rows_materialized=false`
`decision_budget_selected=false`
`uncertainty_band_selected=false`
`primary_selection_authorised=false`
`runner_up_selection_authorised=false`

### Final Tournament Readiness RT001 V3

- branch `codex/phase2-final-tournament-rt001-v3`;
- evidence/source commit `8a2d528ee2cc5e099b5b1efdb7c17b11b32d8032`;
- CI `33883848887` SUCCESS;
- artifact `9940994538`, SHA256 `adb31b6dfe28c36dddde3fb4a949403ea43febae1b1ad274b1ce5aefe52a34a3`;
- validation `PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3`;
- 16.495 contesti budget-qualified uniti losslessly a 6.000 timetable esatti;
- tutti i 646 contesti di frontiera recuperati da RT-001 sono presenti;
- sei envelope exact: 89.135,2 / 100.277,1 / 111.419,0 / 122.560,9 / 133.702,8 / 144.844,7 bus-km/anno;
- test, rebuild byte-for-byte e guard anti-selezione PASS;
- nessun `CandidateEvaluation`, ranking, budget decisionale, uncertainty band, calendario, recovery, PRIMARY o RUNNER-UP materializzato.

Blocker finali formalizzati:

1. full demand-weighted GJT non disponibile: il journey universe è municipal-OD e `full_gjt_ready=false`;
2. missed-connection probability empirica non disponibile: Stage E è deterministic engineering stress;
3. Stage-F incompleto per dwell variation, bus-runtime decrease, non-zero rail delay e route-level demand perturbation;
4. current-service continuity resta un lower bound localizzabile incompleto;
5. decision budget non selezionato dal caller;
6. uncertainty band non selezionata dal caller.

### Stage D exact RT001 V3 — PASS e cross-audit PASS

- branch canonica `codex/phase2-stage-d-exact-rt001-v3`;
- evidence commit `2e667db698e282542bc486e8f64ed4fa590549c6`;
- CI `33872934005` SUCCESS;
- cross-audit branch `phase2-stage-d-v3-cross-implementation-audit`, run `33875195829` SUCCESS;
- 5.325 timing problem, 16.495 contesti, 6.772.755 phase vector exhaustive, 6.000 timetable selezionati, 285.748 trip;
- zero differenze semantiche fra le due implementazioni indipendenti.

### Stage E final operational robustness RT001 V3 — PASS

- branch `phase2-stage-e-rt001-v3-final-a`;
- evidence commit `063e119`;
- CI `33876737866` SUCCESS;
- artifact `9938582797`, SHA256 `c9aa25cfa09c0d4d9c21c0d9a8f0295185dae79711b4067f198a1a2e61dbda16`;
- 6.000 timetable, 16.495 plan context, 285.748 trip, 3.260.753 planned connection e 157.968 robustness row;
- delay bus 0/+5/+10/+15 e recovery 5/10/15 restano engineering sensitivity non probabilistiche e non selezionate;
- rail delay resta nominale 0 per assenza di un contratto certificato non-zero;
- nessuna selezione finale autorizzata.

### Final Methodological Red-Team V2

- branch `phase2-final-method-redteam-v2`;
- report commit `9122e6664df0ba29447cb76e4c6a695a90831602`;
- CI `33868348370` SUCCESS;
- artifact `9934869206`;
- verdict: **BLOCKED for final PRIMARY / RUNNER-UP selection**.

RT-001 resta il blocker upstream: il prefilter annuale a continuous clockface non è lossless vicino ai budget cap in tutti i contesti span/headway. Questo Stage-E workstream non modifica budget-policy, Passenger Utility o Stage-D manifest.

### Stage D exact V2 — PASS tecnico storico, fixture non finale

Lo Stage D exact corrente resta tecnicamente **PASS rispetto al proprio input**:

- branch `phase2-exact-timetable-optimizer-v2`;
- evidence commit `96e033e77f2b9b7b82ff4555b682816bf8c71111`;
- workflow run `33866312583`;
- artifact `9934216350`;
- status `PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2`.

Recovery 5/10/15 e runtime stress 0/+5/+10/+15 sono sensitivity non selezionate. A causa di RT-001 questo Stage D è una **development/regression fixture**, non la final-selection lineage.

### Stage E — Final Operational Robustness V2 storico

**PASS WITH LIMITATIONS come motore di robustness. Non PASS della scelta di rete.**

- branch `phase2-final-operational-robustness-v2`;
- computational/workflow commit `5ffa97645de09a66fed998b64681ec51b6924d0f`;
- evidence commit `044851176ae44bba668a013704dc32e3f2370282`;
- workflow run `33870757131` SUCCESS;
- artifact `9936018364`, SHA256 `076d4feb52014b65b504c1113b4b58080e9199372ddc153345503f307cf490b9`;
- validation `PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_V2`;
- Stage-D role `CURRENT_STAGE_D_USED_AS_ENGINE_VALIDATION_FIXTURE_NOT_FINAL_SELECTION_LINEAGE`;
- 5.345 exact timetable analizzati, 262.149 trip pubblici;
- 2.930.045 planned connections su 2.963.094 connection candidates;
- 142.254 righe di robustness e 64.140 recovery/runtime block cases;
- technical-return passenger connections: 0;
- planned target identity preservata, later alternative riportata separatamente;
- deterministic byte-for-byte rebuild PASS;
- nessun budget, calendar, recovery, PRIMARY o RUNNER-UP selezionato;
- nessun weighted reliability score, passenger weighting, OD downscaling o ridership forecast.

Limitazione corrente: non esiste nella lineage un sensitivity contract certificato per rail delay non nullo. Il fixture run usa quindi solo rail delay 0; bus runtime 0/+5/+10/+15 e recovery 5/10/15 sono invece valutati come engineering sensitivities deterministic.

### RT-003 — current-service lower-bound limitation

RT-003 è formalizzato in `docs/PHASE2_RT003_CURRENT_SERVICE_BASELINE_LIMITATION.md`.

Il baseline corrente resta un **certified localisable lower bound**: 51 righe D184/D185 considerate, 12 localizzate, 39 unresolved/unlocalised, 7 cluster esattamente localizzabili, accessibility lower bound circa 7,69% / 15,03% / 19,24% a 5/8/10 minuti e worst-municipality lower bound 0.

Un PASS di non-regression contro questo artifact non prova non-regressione contro il servizio attuale reale completo. Nessun fuzzy matching, nearest-neighbour forcing o stop placement inventato è autorizzato per chiudere la limitation.

### RT-004 — governance

RT-004 è **formalizzato/mitigato sulla branch Stage E**: questo status sostituisce il vecchio snapshot del 2026-09-03 e registra esplicitamente red-team, RT-001, Stage D tecnico e Stage E. L'assenza storica di `AGENT_PROTOCOL.md` resta documentata senza retroattività.

## Vincoli metodologici invariati

- zero dati sintetici o inventati;
- zero `np.random` / random search;
- niente live Overpass o live GTFS nel robustness run;
- `S8_DIRECT` non è modal share e i 1.882 worker non sono route ridership;
- niente municipal OD downscaling non supportato;
- niente weighted composite score;
- technical vehicle return ≠ passenger service;
- nessun default implicito di budget, calendar o recovery;
- final selection richiede lineage lossless e Decision Contract esplicito.

## Critical path corrente

RT-001, Stage D exact e Stage E final sono chiusi con PASS. Il prossimo lavoro autorizzabile deve ora colmare evidenza, non produrre una classifica prematura:

1. ottenere una lineage esplicita e supportata di allocazione spaziale/route-level della domanda, oppure mantenere formalmente `full_gjt_ready=false`;
2. materializzare full Passenger GJT per candidato sulle sensitivity walk/wait e sulle altre dimensioni richieste;
3. certificare le sensitivity Stage-F mancanti e una base empirica per la missed-connection probability, senza convertire arbitrariamente gli stress deterministici in probabilità;
4. completare o esplicitamente accettare il limite del current-service baseline;
5. richiedere al decisore una delle sei envelope di budget e una uncertainty band finita non negativa;
6. solo a quel punto costruire reali `CandidateEvaluation` e invocare il finalizer per PRIMARY/RUNNER-UP.

`primary_selection_authorised=false`  
`runner_up_selection_authorised=false`

## GPT handoff — Finalist Simplicity Diagnostic V3

**Timestamp:** 2026-09-04 21:07 Europe/Rome  
**Autore:** GPT  
**Branch:** `phase2-final-policy-contract-v3`  
**Source/workflow commit:** `ff776b7d0b7e768461011791e94d9e19e452e344`  
**Evidence commit:** `aa16a9934a78be9a3ee1230996fcaf72c5657f92`  
**Task:** chiusura e certificazione del Phase 2 Finalist Simplicity Diagnostic V3.  
**Workflow:** `33909488053` SUCCESS  
**Artifact:** `9950786078`, SHA256 `3d1be56ff2f42a2915724ca730d20a58389d1191cbae4aa7af3e76e1b7b46070`  
**Validation:** `PASS_PHASE2_FINALIST_SIMPLICITY_DIAGNOSTIC_V3`.

File persistiti:
- `outputs/phase2/finalist_simplicity_diagnostic_v3/finalist_simplicity_diagnostic_v3_validation.json`
- `outputs/phase2/finalist_simplicity_diagnostic_v3/finalist_timetable_structure_v3.csv`
- `outputs/phase2/finalist_simplicity_diagnostic_v3/finalist_route_structure_v3.csv`
- `outputs/phase2/finalist_simplicity_diagnostic_v3/finalist_exact_departures_v3.csv`
- `outputs/phase2/finalist_simplicity_diagnostic_v3/finalist_stage_f_summary_v3.csv`

Risultati principali: quattro timetable finalisti ricostruiti deterministicamente dal Final Policy Dry Run V3 e verificati contro lo Stage D pinned; due topology family (`interlined_figure8`, `two_independent_loops`), due span (960/1110 minuti), H60 uniforme; 8 route structure row, 136 exact public trip e 12 Stage-F summary row, pari a 3 profili di engineering robustness per finalista. Il diagnostic conserva sequenze di anchor certificate e non inventa geometrie stradali.

Stato epistemico: **DERIVED / non-decisional descriptive diagnostic**. Nessun weighted/synthetic complexity score, nessun simplicity rank, nessun vincitore implicito, nessun PRIMARY o RUNNER-UP selezionato.

Problemi aperti per questo workstream: **nessuno**.  
Richiesta all'altro agente: usare questi output come input read-only per il sito, mantenendo separata la baseline Current Service V4 e senza reinterpretare il diagnostic come ranking o raccomandazione.

## Agent A handoff — RT-028 final-stop pedestrian accessibility substrate V3

**Timestamp:** 2026-09-06 16:16 Europe/Rome  
**Autore:** Agent A / GPT takeover  
**Branch:** `rt028-final-stop-pedestrian-accessibility-substrate-v3`  
**Computational evidence commit:** `8a926234b8635aa48db4b80a61fb293be35f74f2`  
**Methodology correction commit:** `fbfe1f8ca4e20078ffc8f67a955bdfb360bb36a8`  
**Task:** chiusura del substrato atomico border-neutral `population unit × final stop` per RT-028, senza candidate aggregation o selezione downstream.  
**Certified computational workflow:** `34037985015` SUCCESS  
**Certified artifact:** `9990832031`, SHA256 `f09bfa9fb8d7aeacc9c7b80f4bc17dff5c4ce391e6a16c25bc0afd973e509415`  
**Validation contract:** `RT028_FINAL_STOP_BORDER_NEUTRAL_PEDESTRIAN_ACCESSIBILITY_SUBSTRATE_V3`, status `PASS`.

Evidenza computazionale verificata indipendentemente dopo il takeover:
- RT-016 population lineage: commit `3eaa227fc7a3cd3f82a9c3161ac4827bc32b862a`, artifact `9971024216`, digest `sha256:2937c60aec0280ae1837bc3f763103d5ac45acd2e3b93a949cc75235b1152fe9`;
- 10.230 population units: 4.283 `core`, 5.947 `external`;
- frozen final-stop lineage: commit `ea30fbd18421164abaf2125033292cbe827e024d`;
- exact stop contract: 36 = 35 `CONVENTIONAL_TPL` + 1 `SPECIAL_SERVICE`;
- pinned OSM timestamp `2026-09-06T12:00:00Z`, raw snapshot SHA256 `365a6a76c8364c441b3827328073009863f5813db1c60734a669f88773215230`;
- pedestrian graph digest `0ab9ef773db40194f3c3d235a1466654e30761fd9cf5eccb1dbdfd62dd7a583f`;
- 93.677 routable nodes, 194.062 directed edges, 220 blocking barrier nodes, 1.790 obstacle geometries;
- matrix: 368.280 exact pairs = 10.230 × 36;
- canonical matrix SHA256 `e20c59300c463d45a170fca70b8456db536f6eaab7d42f9dee3e9f7ab65cab1b`;
- 301.140 `REACHABLE`, 67.140 `UNREACHABLE`, every unreachable row has an explicit reason;
- population-level unreachable diagnostics: 1.504 units `POPULATION_NO_ACCESSIBLE_NODE_WITHIN_MAX_CONNECTOR`, 204 `POPULATION_CONNECTOR_BLOCKED_BY_BARRIER`, 157 `GRAPH_DISCONNECTED`; the remaining 8.365 units reach the final-stop component;
- weighted population reachable: 44.937,376 / 45.828 core and 40.845,760 / 41.689,399 external; unresolved population remains explicit instead of being Euclidean-filled;
- artifact ZIP digest, matrix digest and OSM snapshot digest were independently recomputed from downloaded bytes and match the certified metadata.

Red-team findings and corrections:
- legacy `scripts/04_walk_network.py` is direct coordinate-distance + slope correction, not graph routing, so its territorial output is rejected;
- Access Equity V2 aggregation helpers are methodologically reusable only downstream for deterministic union/no-double-count summaries, not as a new graph engine;
- the original RT-028 methodology text misstated the R5 state. Corrected at `fbfe1f8...`: RT-012 certifies `r5py 1.1.7` only on a pinned Helsinki fixture, while RT-028 has OSM XML and no certified territorial XML→PBF lineage. The optional R5 check is therefore explicitly `NOT_RUN_TECHNICAL_BLOCKER`, never fabricated or averaged;
- all 15 RT-028 contract tests pass in the certified run, including graph-not-straight-line, barrier-aware connector, cross-municipality access, exact 36-stop freeze, old-43 fail-closed, explicit unreachable states, connector failure and row-order determinism;
- candidate/topology/rank/score/PRIMARY/RUNNER-UP fields are absent and candidate identity is rejected by contract.

Stato epistemico: **DERIVED / certified atomic pedestrian-access evidence**. RT-028 itself does not establish a preferred network, accessibility threshold result, Pareto set or recommendation.

Problemi aperti RT-028: nessun blocker per il primary graph substrate. Il solo optional independent R5 cross-check resta `NOT_RUN_TECHNICAL_BLOCKER` per assenza di una frozen territorial XML→PBF lineage certificata; Issue #68 lo definisce non bloccante per il risultato primario.

Richiesta ad Alpha: consumare questa matrice read-only solo downstream, combinandola con i candidate stop sets RT-022/RT-023. Escludere di default la fermata `SPECIAL_SERVICE` dall'automatic conventional candidate evaluation salvo attivazione esplicita; calcolare 5/8/10/12-minute access, equity, Pareto e shortlist solo nel workstream Alpha, senza modificare RT-028.

## GPT handoff — RT-031 bounded typed composition

**Timestamp:** 2026-09-06 (UTC)
**Author:** GPT / Codex
**Branch:** `codex/rt031-typed-composition-gate`
**Base commit:** `8f138f8ea7ac2c1f39e76a79201125f041d69cd5`
**Scope:** bounded implementation of the Astra representation/composition step and
its three deep-red-team counterexamples; parent Issue #79.

Files: `src/phase2_rt031_typed_composition_v3.py`, corresponding tests,
`docs/RT031_TYPED_COMPOSITION_GATE.md`, deterministic replay script/output and CI.
The exact source commit is the Git commit containing this handoff (no circular
self-SHA is embedded).

Local evidence: **32 tests PASS** (25 typed-composition cases + 7 existing macro
regressions); separate replay A/B byte-identical. Epistemic status: **DERIVED on
CONTROLLED_TEST_FIXTURE**, not territorial evidence. CI status is not claimed here.

Preserves full restriction history, directed carrier occurrences, ordered service
annotations, passenger/vehicle continuity separately, public eligibility and
boundary provenance. Exact stop-identity guarantees require a complete nonempty
compatible domain. No cross-realization journey guarantee or vehicle-run cost is
inferred. Existing topology contraction remains unchanged.

Open: certified RT-017 full restriction/context adapter; RT-023/030 segment-offset
and visit correspondence binding; network/service decomposition; independent
review; physical D184/D185 calibration; prospective search/stopping contract.
See `docs/RT031_TYPED_COMPOSITION_GATE.md`. Production gate remains OPEN.
No RT-029 change, territorial enumeration, new Pareto or winner selection.
Independent reviewer should inspect the committed payload and tests, particularly
restriction history, occurrence reconciliation and unknown service-state handling.


## GPT handoff — RT-031 linked service network and historical calibration

Date: 2026-09-10 UTC. Author: GPT / Codex. Branch: `codex/rt031-typed-composition-gate`, PR #80.
Base: `737391a439e043c933b229da5dc13c6027bc1bb6` (scoped physical composition).
Exact implementation identity is the commit containing this handoff.

Read the September 7 Agent A A–F review, tri-state blocker/fix and scoped physical
composition handoff before continuing. No earlier branch state was overwritten.

New bounded service-network contract binds complete macro incidence, atomic
carriers, source visits, explicit service events, pattern labels and movement
instances into one identity. Unknown physical legality cannot produce complete
passenger relations. Location correspondence never implies event merge. Tests
distinguish one movement with two labels from two separately operated movements.
No real operating assignments, timetable or annual vehicle-km were introduced.

Historical calibration inventory pins eight Arriva GTFS files: 42 D184/D185 trips
(15/27), 541 occurrences and 18 direction/shape/eligibility profiles. All 18 shapes
are present. Published feed period is 2026-01-01 to 2026-06-08: historical only.
Full trip payload SHA256: `e4a7ca44c10cdcac9142f5ce35e5392a3e907e9bb728bfa42c7e6e956364671c`.
No inferred interlining from shared block IDs; no historical stop promotion.

Validation before push: 126 RT-031/macro tests PASS; historical A/B rebuild
byte-identical. CI status is reported separately on #79/#80 with exact run/head.
Epistemic scope: controlled service scenarios + DERIVED historical source inventory.
See `docs/RT031_SERVICE_NETWORK_AND_CALIBRATION.md` and committed historical audit.

Open: independent review of this delta; evidence-backed real service assignments;
exact D184/D185 physical/turn/attachment calibration and historical stop mapping;
production candidate domain/equivalence/repetition/objectives/stopping contract.
RT-029 unchanged. No territorial search, new Pareto or winner selection.

## Codex handoff — complete-route physical distance bridge

2026-09-10 UTC. Base 4d87d92677859923c4e3c29bbd2ff3544c98b311, PR #80.
User explicitly requested substantial end-to-end progress. Implemented exact
compatible realization count/minimum distance for declared complete chains and
cyclic seams, plus a pinned real-data runner for six reproducible all-stop
structural stress scenarios. Full-history replay independently checks selected
witnesses. See docs/RT031_COMPLETE_ROUTE_EVALUATION.md.
Local validation: 138 RT031/macro tests pass, including exhaustive comparison of
all small compatibility graphs with brute-force enumeration. Real-data results
are pending CI at this commit; report exact run/head separately on #79.
No service assignments, territorial winner or production PASS inferred.

## Codex handoff — physical result and historical stop-place binding

2026-09-11 UTC. Base d0db2bd3c1dad398cff57a5325edff97a91db039.
Complete-route CI 34522467636 SUCCESS (PR merge 51517bebaabd324972997a365d1630cb56492118),
artifact 10170243158, ZIP digest af4e47225fb19c7e198cab8364aeed04e537cdf21eaaaaae53e544b30bfc7a4f.
Six full 35-stop structural stress scenarios physically compatible; forward/reverse
cycle distances 35.139/36.121 km, repeating out-and-return 77.241 km (rounded).
Independent full-history replay and A/B rebuild pass. This is not a service or
territorial optimum. Details: docs/RT031_PROGRESS_2026_09_11.md.

New historical provenance binder preserves all 541 visits/70 IDs/42 trips: 140
occurrences direct provenance, 38 explicitly confirmed crosswalk, 72 unconfirmed
candidates, 291 no binding evidence. Stop-place binding only; boarding/road
attachments remain unset. Exact provider namespaces, special exclusion and
ambiguity guards. Frozen 36/35 universe unchanged. Historical source coordinates
and trip semantics retained. 143 local tests pass and A/B bytes identical.
Occurrence payload SHA256 6cefce41930e0577ad8bfc94a55ad5afa12c1159c591795a901f7fd9ed2cef6e.
Full occurrence payload in CI artifact; compact audit committed. Pending delta CI
status and review reported separately on #79. Production gate remains OPEN.
