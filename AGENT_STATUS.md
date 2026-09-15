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

### RT-031 caller correction — ONE RECOGNIZABLE PUBLIC LINE

- caller-declared requirement: one public route identity; two physical
  movements or multiple vehicles must not be counted as two lines by default;
- directional patterns may belong to the same line only after route identity,
  directional occurrences, ordered service events and passenger-service
  continuity are explicitly bound;
- the existing five-profile/two-component lane is retained as engineering
  evidence but is not certified to satisfy the single-recognizable-line
  requirement merely by assigning one label;
- a dedicated hub-rooted single-walk discovery lane now explores distance,
  available-stop count and retained-current-stop count separately, without a
  weighted score or retention filter;
- diversified-search CI `34982075116` SUCCESS, artifact `10402211767`: the two
  20,000-expansion lanes reach 34 total stop identities and 11/11 current exact
  identities, disproving the earlier apparent 12-stop ceiling;
- single-line frontier CI `34982695261` SUCCESS, artifact `10402480319`:
  2,457 ordered single-walk candidates, 158 Pareto alternatives, 29 improve the
  current benchmark on all six access axes and four of those retain 11/11;
- none of those 29 fits the reference cap at H30 for 10/12/16h; all fit H60/12h,
  11 fit H60/16h, 25 fit H40/10h and one fits H40/12h. These are context counts,
  not a frequency/span selection; shorter H30-envelope discovery remains open;
- current-stop conservation remains a Pareto preference; Olgiate FS remains a
  required line service node.

`single_public_line_required=true`
`recognizable_public_line_certified=false`
`network_selected=false`
`primary_selection_authorised=false`
`runner_up_selection_authorised=false`

### RT-031 network-connected expansion — STOP RETENTION IS A PREFERENCE

- the 11 current exact stop identities are a separate no-weight Pareto benefit,
  never an admissibility constraint;
- network-connected CI `34900153541` SUCCESS at `9864a42`, artifact
  `10370024100`, ZIP digest
  `sha256:b279b89e72c16f272c1439f4da96e6d6fbc53e417deeac0844e32405639bce45`;
- Olgiate FS is required at network level: at least one movement serves it and
  every other movement must join the same shared-stop-identity intersection
  component; every movement no longer has to visit the hub;
- shared stop identity means potential connectivity only, not a certified
  directional occurrence, ordered service event or passenger transfer;
- two pinned resource-incomplete physical pools provide 3,804 positive
  witnesses, reduced by safe objective dominance to 1,631 movements;
- exact initial two-movement enumeration: 62,947 connected stop unions and 935
  no-weight Pareto alternatives over six access axes, exact-ID retention and
  distance;
- 155 frontier alternatives beat the current access benchmark weakly on all six
  axes and strictly on at least one; frontier retention ranges from 1 to 8 of
  the 11 current identities;
- the two-movement bound is a declared computation scope, not an impossibility
  claim; candidate-domain completeness remains false.

`candidate_domain_complete=false`
`network_selected=false`
`primary_selection_authorised=false`
`runner_up_selection_authorised=false`

## Codex handoff — frequent-access typed development shortlist

2026-09-15. Branch `codex/rt031-decision-convergence`, PR #82. The latest
network-connected artifact (run 34900153541, artifact 10370024100) passes and
contains 62,947 exact two-movement stop unions with a 935-member no-weight
frontier. 155 frontier members are within the approved H30/12h/260-day distance
context, are no worse than the current exact-ID benchmark on all six 5/8/10-
minute total/equity axes and strictly improve at least one.

Added an exact access/equity-only Pareto gate that reduces those 155 profiles to
five, then binds every source physical witness to directional occurrences and
ordered candidate service events. Every component must serve Olgiate FS. Source-
model runtime plus the inherited 27-case Stage-F runtime/dwell/recovery grid
preserve explicit no-observation/no-block-plan status. Four profiles support a
two-vehicle lower bound in 6/27 cases and one in 5/27; all reach four vehicles in
the stressed tail. Controlled local validation: 47 tests pass. Real territorial A/B replay,
artifact identity and exact profile results are pending CI at this commit.

This is a development shortlist, not a selected network. Dwell-inclusive runtime,
H30 timetable/S8 retention, vehicle blocks and robustness remain open. The
upstream physical pools remain resource-incomplete and the two-movement boundary
is not an impossibility claim. No PRIMARY or RUNNER-UP is authorised.

Exact H30 hub phasing is now implemented over the five profiles: 900 ordered
integer-minute phase pairs, 559 nondominated against the frozen 74 S8 events and
three transfer-friction profiles. The regular combined 15-minute subspace has 30
pairs and all 30 remain nondominated, so clock rotation is not selected. Local
tests and A/B output replay pass; real CI identity is pending at this commit.

### RT-031 data-guided expansion — 578,235 PORTFOLIOS / 2,410 FRONTIER

- Current-Service stop retention removed as a candidate constraint; Olgiate FS
  remains the required hub;
- expanded-frontier CI `34897632951` SUCCESS, artifact `10370190130`;
- frequency H20/H30/H40/H60, spans 600/720/960 minutes and annual bus-km are a
  reported service surface; neither frequency nor the 111,419 km reference cap
  filters the physical candidates;
- Olgiate-rooted search CI `34896019917` SUCCESS, artifact `10368324023`:
  2,062 positive hub-serving stop-set witnesses across 29 stop identities, up
  to 12 stops per movement; all retained witnesses pass full-history seam
  replay. Search remains resource-incomplete with 4,282,646 labels pending;
- exact union DP up to four movements: 578,235 distinct minimum-distance
  portfolios and 2,410 no-weight Pareto alternatives;
- 1,761 frontier alternatives are no worse than the current exact-ID benchmark
  on all six access axes and strictly better on at least one;
- reference-cap context counts among those 1,761: H30/10h 185, H30/12h 119,
  H30/16h 0, H40/16h 119, H60/16h 752; H20 has zero at every tested span;
- shortest benchmark-improving frontier member: two movements, 15.204 km;
  126,498.713 km/year at H30/16h or 94,874.034 at H30/12h;
- public trunk-branch, short-turn and interlining semantics remain unassigned,
  so candidate-domain completeness is false.

`candidate_domain_complete=false`
`network_selected=false`
`primary_selection_authorised=false`
`runner_up_selection_authorised=false`

### RT-031 corrected hub-connected target cover — PROMISING CANDIDATE, NOT SELECTED

- branch `codex/rt031-decision-convergence`;
- hub-constrained search CI `34869733360` SUCCESS, artifact `10358581671`;
- typed-service CI `34892996081` SUCCESS, artifact `10368011342`;
- one two-circuit witness retains all 11 current exact-ID targets and requires
  every circuit to serve Olgiate FS;
- total 21.397278 km; H60/16h/260d = 89,012.677 bus-km/year, below the approved
  111,419 cap by 22,406.323 km/year; H30 = 178,025.354 and is over cap;
- same-substrate total walking access improves at 5/8/10 minutes while all three
  worst-municipality safeguards are equal; no weighted score;
- decision consequence: H30 on both circuits is over cap, while the H60
  exception is not established because the approved contract requires strict
  equity improvement over the frequent-class frontier and the current evidence
  has equality against only the current exact-ID subset;
- non-selected production envelope: a 16-hour design with 12 hours H60 plus
  four H30 overlay hours on both circuits is 111,265.846 km/year (153.154 below
  cap); a fifth overlay hour exceeds the cap. No peak window is selected and
  this is not uniform H30;
- directional occurrences and ordered events are bound, with route, passenger
  and vehicle semantics kept distinct;
- source-model runtimes are 23.834 and 23.482 minutes excluding dwell; fleet
  lower bound is two under 5/10/15-minute recovery sensitivity;
- unconstrained earlier witnesses are superseded for promotion because they
  included a hub-disconnected component and, in the three-movement case, a
  265 m micro-loop;
- pending gates: dwell-inclusive runtime, explicit timetable phasing, S8
  deterministic retention, recovery/vehicle blocks and actual-service comparison.
- exact cyclic hub-phase CI `34894073548` SUCCESS, artifact `10368250959`:
  all 3,600 ordered minute pairs evaluated without weights; 2,236 are Pareto
  non-dominated. All 60 exactly half-hour-spaced hub rotations remain
  non-dominated across the separate S8 direction/profile axes. This is phase
  opportunity geometry only: no daily span, timetable or deterministic
  retention case is selected.

`network_selected=false`
`primary_selection_authorised=false`
`runner_up_selection_authorised=false`

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

## Codex correction and resource-screen handoff — 2026-09-11

Base 12c0b0ee9a2b2452489b47b9aa0d189eab8ade2e, PR #80.
IMPORTANT: the existing human-approved final policy already selects a hard cap
of 111,419 annual bus-km, no global uncertainty band and the deterministic V3
pathway. Earlier statements that budget selection/full empirical GJT remained
mandatory were stale. See config/phase2_final_policy_contract_v3.json and
new docs/RT031_APPROVED_BUDGET_SCREEN.md. Do not ask again for these decisions.

Added exact phase-enumerated necessary budget screen for three complete physical
stress cycles across the existing headway/span/calendar assumptions (72 contexts).
No speed/fleet/recovery assumptions introduced. Calendar remains hypothetical.
Rejecting a declared order does not reject all possible all-stop routes or prove
another topology superior. Production search/calibration and review remain open.
CI results reported separately on #79; this commit does not predeclare real-run
success. Full resource output is uploaded by CI.

Resource integration extension: added a route-order-independent metric-MST lower
bound for ONE closed walk serving all mandatory endpoint stop identities. All
possible atomic interior identities are excluded from the mandatory set. This
relaxes directions/turns conservatively and cannot certify feasibility or rule
out independent disconnected service components. Result pending real CI; exact
terminal/tree witnesses and the 24 policy contexts are saved with the 72
predeclared-cycle contexts. Local RT031/macro suite: 153 passed.

## Codex handoff — affordable physical walks + conditional access

2026-09-11. Base 163ce18c1237221cc66d59ff196e2927db35a2b4, PR #80.
Added a budget-bounded single closed physical walk label search over all 288
atomic roots. No named-locality forcing, random search or elementary-edge cap;
repeated vertices/edges and branching excursions allowed. State retains root,
last atom and available-stop union; higher-distance identical states dominated
only for physical distance/availability objectives. Execution limit 250,000
expanded states is explicit; remaining labels mean RESOURCE_LIMIT_INCOMPLETE.

Every found witness is full-history replayed and its available-stop set evaluated
against pinned RT028 matrix using RT029 access/equity metrics. Coverage is
conditional on future public service assignment, not observed service or boarding
rights. Evaluated-set nondominance is descriptive, never a final ranking or
production-search PASS. Single movement domain is not the general RT031 service
network domain. See docs/RT031_AFFORDABLE_WALK_SEARCH.md.

156 local RT031/macro tests pass. Real run and exact artifact/status to be reported
on #79 after CI. No final recommendation yet. Existing approved policy decisions
remain in force, including 111,419 annual bus-km cap and deterministic pathway.

Report-only model bridge added: sum existing frozen edge running_minutes_model
on each exact retained carrier witness, preserving repeated traversals. Excludes
dwell; source maxspeed/highway assumptions are not observations. Model fleet
lower bounds for existing recovery 5/10/15 at H30 are reported, not feasibility.
No runtime objective added to physical label dominance/frontier; longer/faster
alternatives may have been discarded and no service optimality is asserted.

## Codex handoff — one/two independent movement comparison

2026-09-14. Branch `codex/rt031-multimovement-budget-comparison`, draft PR #81
against draft PR #80. Computational commit `0bd19e29fac9b146a3ddbc0cdf42529917cbf679`.
CI run `34832485378` SUCCESS, full computation twice byte-identical; artifact
`10343160253`, GitHub ZIP digest
`06024e6f428894da3959a17da4e9c8bda16342909ac6388aca273ec5171244b9`.

Exhaustive only within the pinned truncated pool: 780 singletons + 303,810 pairs,
173,663 availability unions, 1,331 nondominated summaries. Exact decimal costs
and rational population shares decide dominance; no weighted ranking. All feasible
decompositions retained, including equal-cost distinct witnesses. Available stops
are not boarding rights; shared physical edges are charged for each movement.

Distinct extrema: max core10 42.9650%; max worst-municipality10 25.0317%, with
core10 37.3673% and conditional annual carrier km 77,795.35. No selection.
Existing approved 111,419 km cap retained. H30 per movement, 32 departures and
260 days remain scenario assumptions, not an approved timetable/calendar.
No new uncertainty band, demand allocation or empirical missed probability.

39 combined tests passed before one additional precision regression; all 13 new
module tests then passed. Publication commit adds evidence and that local test,
separate from the pinned CI computational commit. Full tables in artifact;
compact audit/frontier in Git. See docs/RT031_ONE_TWO_MOVEMENT_COMPARISON.md.
Review focus: exact union/cost, rational dominance, retained witness semantics,
and source truncation. Source expansion and typed operational/public-service
binding remain open; dwell/recovery/timetable feasibility is not certified.
primary_selection_authorised=false; runner_up_selection_authorised=false.

## Codex handoff — expanded-pool terminal disposition

2026-09-14. Branch `codex/rt031-decision-convergence`, draft PR #82.
Expanded physical search commit `f7d062f`, run `34861503109` SUCCESS: one million
states replayed twice identically, 1,742 single-walk sets, 10-stop maximum,
2,864,434 queued labels; still RESOURCE_LIMIT_INCOMPLETE. Artifact `10354879891`,
GitHub ZIP SHA256 `53b400b11a6db457037a531d612d3abf99147d7a3162573d11149f432131bd87`.

Computational comparison commit `18a1e61b1cbb154b94659d3769e4c87d6bcc47e6`,
run `34862836065` SUCCESS. Two byte-identical full comparisons; artifact
`10356122465`, GitHub ZIP SHA256
`50c1f7ff5885d34cac5afb50b1f0f448aee4872e6b6d77285959f20de07058bd`.
Downloaded outputs match committed evidence byte-for-byte.

All 1,742 singletons and 1,516,411 distinct pairs fit the conditional distance
screen and reduce to 727,514 exact availability unions. Zero unions are no worse
than the exact-ID current structural subset on all six access/equity axes. The
enlarged pool beats the current subset on optimistic total core maxima, including
51.6796% versus 48.7696% at 10 minutes, but misses worst-municipality equity at
8 minutes (19.9168% vs 20.9192%) and 10 minutes (26.5823% vs 34.4032%).

Technical disposition: DO NOT PROMOTE this supplied physical one/two-walk pool
to operational finalists. Retain Current-Service V4 as structural comparison
reference and require a broadened/redesigned candidate domain. This is not a
global proof over all networks and does not select the current network as PRIMARY.
No public service, timetable or passenger relation inferred. See
docs/RT031_EXPANDED_POOL_CURRENT_V4.md.
primary_selection_authorised=false; runner_up_selection_authorised=false.

## Codex handoff — RT031/current V4 same-substrate conclusion

2026-09-14. Branch `codex/rt031-decision-convergence`. Current-Service V3/V4
source, tests and persisted evidence were integrated unchanged from certified
branch `origin/phase2-current-service-baseline-v4` at `95d99b5`.

Added a fail-closed exact-ID bridge from the V4 D184/D185 structural stop universe
to RT028 and compared all 173,663 RT031 one/two-movement availability sets on the
same population/walking substrate. Eleven conventional stops map by shared
official native ID; no name, coordinate, fuzzy or nearest-neighbour fallback.
Exact rational comparison, no score/tolerance. Zero candidate sets are no worse
than the current subset on all six 5/8/10-minute total/equity dimensions. The
current subset is no worse than 173,427 sets; 236 retain only a trade-off.

At 10 minutes, current exact-ID structural subset: core 48.7696%, worst municipality
34.4032%; optimistic componentwise RT031-pool maxima: 42.9650% and 25.0317%.
Conclusion: no broad-access replacement case is established in this supplied
pool. This rejects promotion of this pool, not every possible future network.
Candidate stops remain potential, not public service; V4 route-level activation
is not relabelled as a stop-level operational snapshot. No network selected.

Tests: 35 passed across comparison, Current-Service V4 and movement portfolios.
See docs/RT031_CURRENT_V4_SAME_SUBSTRATE_DECISION.md. Next valid design work must
expand the physical/service search domain and bind typed public service events.
primary_selection_authorised=false; runner_up_selection_authorised=false.
## Codex handoff — reciprocal open-corridor stopping result

2026-09-14. Branch `codex/rt031-decision-convergence`, PR #82. Added a bounded
reciprocal A→B/B→A physical-corridor domain under the approved 111,419 annual
bus-km cap. Directions remain independent: no vehicle turn, passenger continuity,
transfer, route identity or public service is inferred. Stop availability is
identity-only, never a directional occurrence or ordered service-event guarantee.
Compact search labels are admitted only by the pinned RT-023 history-locality
certificate; complete witnesses are retained and full-history replayed.

Final certified run 34865769629 SUCCESS, two byte-identical executions, artifact
10357208237, ZIP digest 55ac800bfb6a8577c4430ff368b514f3a72238001e10ab97142110b2c21c4196.
At the explicit 250,000-state limit: 71,339 open paths, 5,412,651 feasible
reciprocal pairs, 22,220 unique availability sets. Current V4 exact-ID subset is
no worse on all six same-substrate dimensions than all 22,220; zero broad-access
replacement cases. Search remains RESOURCE_LIMIT_INCOMPLETE (750,628 pending), so
this closes the supplied bounded family as a finalist source, not all possible
networks. No network selected; both selection authorisations remain false. See
`docs/RT031_RECIPROCAL_OPEN_CORRIDOR_SEARCH.md`. The semantics-strengthened audit
SHA256 is 41957e951b825e9677597d7385b759e54c5e9f579fb59e4bb5a345a0d40a8255.
## Codex handoff — resource-symmetric target-cover correction

2026-09-14. Branch `codex/rt031-decision-convergence`, PR #82. The earlier
generic-pool result must not be interpreted as current-service optimality. A new
target-only label search covers the same 11 exact-ID current stops while removing
irrelevant stop identities from dominance. Search is physical and full-history
replayed; no service semantics are inferred.

Run 34868712081 SUCCESS at fc34ed89868cd60185570c61ada3834a4e598d84;
two byte-identical executions; artifact 10358326654; ZIP SHA256
d93e26c07f299863653c4bf720cfe086795369d45f77173abebfa97401bf6c54.
At 2,000,000 states the search remains RESOURCE_LIMIT_INCOMPLETE with 1,286,499
pending labels, but valid feasibility witnesses exist. Two movements cover all
targets at 15.450427 km: H60/260d/16h uses 64,273.777 km/year and improves all
three total-access axes while preserving exact equity. Three movements cover all
targets at 11.929500 km: H30 uses 99,253.441 km/year, 12,165.559 below the approved
cap, and is also no worse on all six axes with strict total-access improvement.

These are the first credible physical shortlists from this workstream. Next gate:
typed directional occurrences/service events, route identity, runtime/dwell/
recovery, blocks, timetable and S8 stress. No network selected; PRIMARY and
RUNNER-UP remain unauthorised. See
`docs/RT031_CURRENT_TARGET_COVER_RESOURCE_SYMMETRY.md`.

## Codex handoff — exhaustive daily timetable surface

The next RT031 gate exhausts every H30-aligned 12-hour span contained in the
frozen S8 05:30–24:00 evidence window, all 30 regular combined-H15 phase pairs,
all five typed development profiles and all 27 inherited engineering cases.
It computes exact interlinable vehicle blocks plus separate deterministic S8
transfer axes. This is a non-decisional surface: no span, phase, timetable or
network is selected, and observed dwell validation remains open. The local
exhaustive result covers 2,100 timetable contexts / 56,700 engineering
realisations and is byte-identical across two builds. Sixty joint
territorial/operational Pareto contexts remain and all five profiles are still
represented. No context is at most two vehicles in every engineering case;
the robust maximum is four for every profile.

Historical runtime follow-through: the pinned D184/D185 GTFS has 42 trips / 541
stop-time occurrences and ends 2026-06-08. Its comparable >=8 km full-trip
scheduled-speed envelope can test source-model plausibility, but all 541 arrival
and departure clocks are equal. It therefore cannot provide observed dwell or
reliability; those remain explicit blockers rather than inferred zeroes.
The 32 comparable >=8 km historical trips span 26.520–34.54875 km/h scheduled;
all ten candidate source-model components (27.524–30.322 km/h) lie inside that
broad envelope. This is plausibility evidence only.
