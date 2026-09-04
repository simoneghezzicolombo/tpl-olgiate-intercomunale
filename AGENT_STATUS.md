# AGENT_STATUS

Snapshot strutturata corrente del coordinamento. La cronologia completa resta nella Git history e nella GitHub Issue #1 `Agent Coordination Bus`.

## Stato corrente

**Data:** 2026-09-04  
**Fase:** Phase 2 — final robustness / decision preparation  
**Ultimo snapshot integrato pre-fix RT-001:** `phase2-robustness-final-v2` @ `864c83accb81c615f9778396408b21e31ca72983`  
**Final selection:** **BLOCKED by RT-001 and downstream lineage rebuild**  
**PRIMARY selection authorised:** **false**  
**RUNNER-UP selection authorised:** **false**

## Governance

- GitHub Issue #1 `Agent Coordination Bus` resta il bus di coordinamento operativo.
- `COLLABORATION_PROTOCOL.md` è il documento di collaborazione esistente.
- `AGENT_PROTOCOL.md` non risulta essere mai esistito nella lineage auditata. Non viene creato retroattivamente e nessuna run storica viene dichiarata dipendente da quel file.
- Le evidenze computazionali devono essere identificate tramite branch/commit, validation contract e SHA256.

## Phase 2 — evidenze correnti

### Final Methodological Red-Team V2

- branch `phase2-final-method-redteam-v2`;
- report commit `9122e6664df0ba29447cb76e4c6a695a90831602`;
- CI `33868348370` SUCCESS;
- artifact `9934869206`;
- verdict: **BLOCKED for final PRIMARY / RUNNER-UP selection**.

RT-001 resta il blocker upstream: il prefilter annuale a continuous clockface non è lossless vicino ai budget cap in tutti i contesti span/headway. Questo Stage-E workstream non modifica budget-policy, Passenger Utility o Stage-D manifest.

### Stage D exact — PASS tecnico, fixture non finale

Lo Stage D exact corrente resta tecnicamente **PASS rispetto al proprio input**:

- branch `phase2-exact-timetable-optimizer-v2`;
- evidence commit `96e033e77f2b9b7b82ff4555b682816bf8c71111`;
- workflow run `33866312583`;
- artifact `9934216350`;
- status `PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2`.

Recovery 5/10/15 e runtime stress 0/+5/+10/+15 sono sensitivity non selezionate. A causa di RT-001 questo Stage D è una **development/regression fixture**, non la final-selection lineage.

### Stage E — Final Operational Robustness V2

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

1. RT-001 repair su workstream separato: hard-budget eligibility lossless;
2. rebuild downstream di budget-policy, Passenger Utility e packaging dipendente;
3. nuovo Stage D exact sulla lineage lossless con produzione annua exact del timetable;
4. rerun dello **stesso Stage-E engine** sul nuovo Stage D senza cambiare algoritmo;
5. final robustness tournament e materializzazione degli input espliciti del Decision Contract;
6. soltanto dopo, eventuale PRIMARY e RUNNER-UP.

`primary_selection_authorised=false`  
`runner_up_selection_authorised=false`
