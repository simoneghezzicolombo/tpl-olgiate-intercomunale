# AGENT_STATUS

Questo file è la lavagna corrente di handoff tra agenti. Gli handoff storici dettagliati restano preservati nella Git history e nella GitHub Issue #1 `Agent Coordination Bus`; i verbali `docs/GATE_*_PASS.md` prevalgono sui vecchi stati provvisori.

## Stato corrente

**Data:** 2026-09-03  
**Autore:** GPT external reviewer / co-developer  
**Branch:** `gate-e-workstream`

- **Gate A — provenance:** **PASS**. Commit validato `019a12806af09d744f6f22032d980441ae60dc06`.
- **Gate B — spatial integrity:** **PASS**. Commit validato `55d726564e13acca55ce563cc911263ac513acb0`.
- **Gate C — transit integrity:** **PASS**. Commit finale `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`.
- **Gate D — route integrity:** **PASS**. Commit computazionale validato `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`; CI run `33746091690`; artifact `9891607118`.
- **Gate E — service math:** **PASS**. Commit computazionale validato `e2d096ca929c92da0d8a4abdacde827445e208bd`; CI run `33755350763`; job `100648344246`; **130/130 test PASS**.

**Verdetto Gate E autorevole:** `docs/GATE_E_PASS.md`.  
**Prossimo checkpoint:** **GATE F — recommendation UNLOCKED**.

## Gate E handoff

### Input verificati

Gate E consuma Gate C tramite commit pinning e Gate D tramite l'artifact PASS esatto. Il CI scarica l'artifact D `9891607118`, verifica SHA256 `6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a`, confronta la snapshot delle metriche e rigenera deterministicamente l'evidenza minima dei waypoint.

### Risultati principali

- benchmark D184 + D185: **111.419 bus-km/anno**;
- figura 8 compatta, solo `ASSUMPTION` di composizione:
  - 23,706064 km CW;
  - 23,037668 km CCW;
  - 45,777279 min pure running CW;
  - 44,955157 min pure running CCW;
  - massimo **2.383** coppie complete CW+CCW/anno entro 111.419 bus-km;
  - 2.383 coppie = 111.390,315 bus-km, margine +28,685 km;
  - 2.384 coppie = sforamento +18,058 km.
- sensitivity flotta:
  - a 60 min/direzione, 1 bus CW + 1 CCW è matematicamente possibile solo con dwell+recovery <=14,223 min CW e <=15,045 min CCW;
  - a 45 min/direzione, 1 bus CW è impossibile anche con dwell=recovery=0;
  - a 30 min/direzione servono almeno 2 bus CW + 2 CCW già dal pure running.

### Epistemologia e limiti

- route-km: `DERIVED` da Gate D `DERIVED_OSM_STRUCTURAL`;
- pure running: `MODEL_OUTPUT`;
- definizione delle candidate e composizione figura 8: `ASSUMPTION` / hypothesis, mai raccomandazione;
- dwell, recovery, headway target, calendario, deadhead, relief e spare ratio: parametri di progetto da mantenere espliciti;
- `headway_combined` è rate-equivalent dove applicabile, non max passenger gap senza timetable fasato;
- il PdB disponibile non contiene vehicle-hours D184+D185, quindi è vietato inventare una neutralità storica in ore/costi;
- le incertezze fisiche stradali di Gate D restano valide e devono essere mantenute da Gate F.

### Richiesta precisa al Gate F

Usare esclusivamente risultati e lineage A–E validati. Confrontare le topologie senza assumere che la figura 8 sia vincente; scegliere eventuali headway, calendario, dwell/recovery e flotta come `ASSUMPTION` esplicite e sottoporle a sensitivity. Non usare `saldo zero`, `ottimale`, `fattibile` o equivalenti senza dimostrazione quantitativa e senza conservare i limiti di Gate D/E.
