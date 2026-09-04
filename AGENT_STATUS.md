# AGENT_STATUS

Snapshot strutturata corrente del coordinamento. La cronologia completa resta nella Git history e nella GitHub Issue #1 `Agent Coordination Bus`.

## Stato corrente

**Data:** 2026-09-04  
**Fase:** Phase 2 — final robustness / decision preparation  
**Ultimo snapshot integrato pre-fix RT-001:** `phase2-robustness-final-v2` @ `864c83accb81c615f9778396408b21e31ca72983`  
**Final selection:** **BLOCKED**  
**PRIMARY selection authorised:** **false**  
**RUNNER-UP selection authorised:** **false**

### Governance

- La GitHub Issue #1 `Agent Coordination Bus` resta il bus di coordinamento operativo.
- `COLLABORATION_PROTOCOL.md` è il documento di collaborazione esistente.
- `AGENT_PROTOCOL.md` **non risulta essere mai esistito nella lineage auditata**. Non viene creato retroattivamente e nessuna run precedente viene dichiarata dipendente da quel file.
- Le evidenze computazionali devono essere identificate tramite branch/commit, validation contract e SHA256, non tramite copie narrative di conteggi.

### Gate A–F

A, B, C, D, E e F restano **PASS** nei rispettivi contratti storici. Phase 2 è un programma successivo e i blocker attuali non retroagiscono sui Gate A–F.

## Phase 2 — stato della lineage

### Red-team metodologico finale V2

- Branch: `phase2-final-method-redteam-v2`.
- Report commit: `9122e6664df0ba29447cb76e4c6a695a90831602`.
- CI: `33868348370` — SUCCESS.
- Artifact: `9934869206`.
- Verdict: **BLOCKED for final PRIMARY / RUNNER-UP selection**.
- Findings principali: RT-001 budget exactness BLOCKING; RT-002 final-decision completeness BLOCKING; RT-003 current-service lower-bound limitation MAJOR; RT-004 governance drift MAJOR; RT-006 Stage-C screening semantics MAJOR.

### RT-001 — critical-path blocker

RT-001 ha dimostrato che il prefilter di produzione annuale usa una continuous clockface approximation in contesti span/headway non integrali. La frontier upstream deve quindi essere ricostruita in modo lossless rispetto ai budget cap prima di autorizzare una lineage di selezione finale.

**Questo workstream Stage E non prende ownership di RT-001 e non modifica budget-policy, Passenger Utility o Stage-D manifest.**

### Stage D exact — PASS tecnico, non final-selection lineage

Lo Stage D exact corrente resta tecnicamente **PASS rispetto al proprio input**:

- branch: `phase2-exact-timetable-optimizer-v2`;
- evidence commit: `96e033e77f2b9b7b82ff4555b682816bf8c71111`;
- workflow run: `33866312583`;
- artifact: `9934216350`;
- status: `PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2`;
- exact timetable + route-specific phase + vehicle blocks costruiti;
- recovery 5/10/15 valutati e non selezionati;
- runtime stress 0/+5/+10/+15 riportato come engineering sensitivity, non probabilità empirica.

A causa di RT-001 questo Stage D è utilizzabile come **development/regression fixture**, ma non deve essere usato per selezionare PRIMARY/RUNNER-UP.

### Stage E — Final Operational Robustness V2

Workstream indipendente:

- branch: `phase2-final-operational-robustness-v2`;
- stato: **IN DEVELOPMENT / REAL FIXTURE CI PENDING**;
- input di sviluppo: Stage D exact `96e033e…`, esplicitamente marcato `CURRENT_STAGE_D_USED_AS_ENGINE_VALIDATION_FIXTURE_NOT_FINAL_SELECTION_LINEAGE`;
- obiettivo: motore source-closed e deterministic di planned-connection-preserving reliability, recovery e vehicle-block sensitivity;
- nessun budget, calendar, recovery, PRIMARY o RUNNER-UP selezionato;
- nessun weighted reliability score;
- BUS_TO_RAIL e RAIL_TO_BUS mantenuti separati;
- technical vehicle return vietato come passenger service.

Lo Stage-E PASS, quando eventualmente ottenuto, certificherà **il motore di robustness**, non una rete.

### RT-003 — current-service baseline limitation

RT-003 è formalizzato in `docs/PHASE2_RT003_CURRENT_SERVICE_BASELINE_LIMITATION.md`.

Snapshot certificato corrente:

- 51 righe D184/D185 considerate;
- 12 righe spatially localisable;
- 39 unresolved/unlocalised;
- 7 cluster correnti esattamente localizzabili;
- accessibility lower bound circa 7,69% / 15,03% / 19,24% a 5/8/10 minuti;
- worst-municipality lower bound = 0.

Il non-regression test prova soltanto non-regressione rispetto al **certified localisable lower bound**. Non prova che nessun comune peggiori rispetto al servizio attuale reale completo. Nessun fuzzy matching, nearest-neighbour forcing o stop placement inventato è autorizzato per chiudere questa limitation.

### RT-004 — governance drift

RT-004 è preso in carico con questo aggiornamento. Il vecchio `AGENT_STATUS.md` del 2026-09-03 puntava a `phase2-optimizer-core` e a una critical path ormai superata. Questo file ora registra esplicitamente lo snapshot integrato pre-fix, il red-team, RT-001, lo Stage D tecnico e lo Stage E parallelo.

## Vincoli metodologici invariati

- zero dati sintetici o inventati;
- zero `np.random` / random search;
- niente live Overpass nel normale optimisation loop;
- niente live GTFS update nel robustness run;
- proposed stops restano `FIELD_CHECK_PENDING` finché non verificati fisicamente;
- `S8_DIRECT` non è modal share;
- 1.882 worker S8 non sono route ridership;
- niente municipal OD downscaling a passenger/route/stop non supportato;
- nessun weighted composite score nascosto;
- technical vehicle return ≠ passenger service;
- nessun default implicito di budget, calendar o recovery;
- final selection richiede esplicito Decision Contract e lineage lossless.

## Critical path corrente

La critical path autorizzata verso una raccomandazione finale è:

1. **RT-001 repair** su workstream separato: rendere lossless l'hard-budget eligibility attorno ai cap;
2. rebuild downstream di budget-policy, Passenger Utility e packaging dipendente;
3. nuovo **Stage D exact** sulla lineage lossless, con ricontrollo della produzione annua del timetable selezionato;
4. rerun del **Final Operational Robustness Engine V2** sul nuovo Stage D senza cambiare algoritmo;
5. final robustness tournament sul set di sensitività autorizzato e materializzazione degli input espliciti del Decision Contract, inclusa uncertainty band se e solo se dichiarata;
6. soltanto dopo, eventuale PRIMARY e RUNNER-UP.

Fino al completamento di questa catena:

`primary_selection_authorised=false`  
`runner_up_selection_authorised=false`
