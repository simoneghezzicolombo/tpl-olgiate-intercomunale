# Gate F v2 — real-upstream integration state

**Workstream:** `gate-f-workstream`  
**Stato upstream:** A/B/C/D/E formalmente PASS al 2026-09-03.  
**Stato Gate F:** READY_FOR_SCENARIO_CONSTRUCTION, non ancora recommendation PASS.

## 1. Perché il PASS A-E non produce automaticamente una raccomandazione

I Gate upstream certificano i motori e i dati necessari, ma non inventano il futuro piano di esercizio. In particolare Gate E PASS dichiara esplicitamente che figura 8, target headway, dwell, recovery, calendario, spare ratio, deadhead e relief restano scelte o `ASSUMPTION` quando usate in sensitivity. Gate F deve quindi costruire e confrontare scenari decisionali espliciti, mantenendo queste scelte separate dai fatti e dai risultati derivati.

Non è consentito promuovere automaticamente la sensitivity `FIG8 compact` di Gate E a scenario raccomandato.

## 2. Lineage upstream verificabile

Gate F schema v2 può verificare evidence file direttamente nell'oggetto Git esatto del rispettivo workstream, tramite `git show <commit>:<path>` + SHA256.

Evidence attesa:

- A: `docs/GATE_A_PASS.md` su `antigravity-real-data`;
- B: `docs/GATE_B_PASS.md` su `antigravity-real-data`, motore spaziale validato al commit computazionale `55d726564e13acca55ce563cc911263ac513acb0`;
- C: `docs/GATE_C_PASS.md` su `gate-c-workstream`;
- D: `docs/GATE_D_PASS.md` su `gate-d-workstream`;
- E: `docs/GATE_E_PASS.md` su `gate-e-workstream`, commit computazionale validato `e2d096ca929c92da0d8a4abdacde827445e208bd`.

Un PASS digitato manualmente non è sufficiente a sbloccare il runner v2.

## 3. Bridge real-data predisposti

### B -> copertura e territori

`src/gate_f_gate_b_bridge.py` riusa i veri artefatti Gate B PASS:

- `walk_graph_nodes.csv`;
- `walk_graph_edges.csv`;
- `population_accessibility.csv`.

Le fermate candidate vengono snappate al walking graph validato in EPSG:32632 e la copertura viene ricalcolata con shortest path. Non vengono usati buffer euclidei o moltiplicatori stradali.

La CI scarica l'artifact Gate B PASS originale e riproduce la baseline ufficiale a 10 minuti prima di autorizzare l'uso del bridge sulle candidate.

### D -> eligibility strutturale e incertezza

`src/gate_f_gate_d_adapter.py` consuma il contratto `GATE_D_TO_E_V2` e distingue:

- `road_feasible = true`: il tracciato è strutturalmente instradabile secondo il motore Gate D;
- `road_uncertainty_status = RESOLVED / QUANTIFIED / UNKNOWN`: stato delle incertezze fisiche residue.

Un tracciato strutturalmente valido non viene quindi reinterpretato come certificazione fisica completa per un autobus specifico.

### E -> headway, bus-km e flotta scheduled

`src/gate_f_gate_e_adapter.py` richiede una policy esplicita che selezioni:

- service-day group;
- headway band;
- nozione di flotta: `DIRECTION_LOCKED_TOTAL` oppure `HUB_INTERLINING_ALLOWED`.

La metrica di flotta Gate F v2 è `minimum_scheduled_vehicles`, con semantica esplicita di minimo teorico in servizio. Non è un conteggio di flotta di procurement e non include deadhead, relief, manutenzione o scorte.

Il combined headway è accettato solo quando Gate E conferma un shared-stop pattern e mantiene la semantica `RATE_EQUIVALENT_NOT_MAX_GAP`.

### C + E -> coincidenze S8

`src/gate_f_s8_bridge.py` combina:

- eventi S8 ufficiali Gate C;
- eventi di arrivo/partenza bus scenario-specific prodotti dal piano Gate E.

La policy deve scegliere esplicitamente `BUS_TO_S8` oppure `S8_TO_BUS`, data, finestra di valutazione, tempo minimo di interscambio e maximum acceptable wait. Nessuna media bidirezionale o coefficiente di rail score è nascosto nel codice.

## 4. Contratto Gate F v2

Le metriche Pareto previste sono:

1. `population_covered_pct`, max;
2. `headway_combined_min`, min, rate-equivalent;
3. `annual_bus_km`, min;
4. `minimum_scheduled_vehicles`, min;
5. `s8_useful_connection_pct`, max;
6. `territories_served_count`, max.

Ogni metrica richiede valore, status epistemico, source, unit, semantics e comparison basis. I basis devono essere identici tra scenari per evitare confronti apples-to-oranges.

Gate D road uncertainty resta un vincolo epistemico esterno agli obiettivi. Una soluzione robustamente Pareto ma con `QUANTIFIED` o `UNKNOWN` road uncertainty non può ricevere recommendation definitiva.

## 5. Artefatti che mancano per il vero run Gate F

Non mancano più PASS metodologici. Mancano le definizioni scenario-specific necessarie per applicare i motori validati:

1. **scenario catalog** completo, comprendente baseline D184+D185 e alternative serie, non solo figura 8;
2. **candidate stop sets** per ogni scenario, con coordinate e territorio, per ricalcolare Gate B;
3. **Gate D v2 handoff scenario-specific** congelato sulla stessa catalog/version;
4. **service plans Gate E** con band/day group scelti e senza ASSUMPTION se si vuole una recommendation definitiva;
5. **bus hub arrival/departure events** per calcolare il feeder S8 con Gate C;
6. policy esplicite per threshold B, day/band/fleet E e finestra/direzione di interscambio S8.

Se una di queste componenti resta `ASSUMPTION`, Gate F può eseguire sensitivity e Pareto provvisori, ma non deve trasformarli in una raccomandazione definitiva.

## 6. Regola decisionale

- scenario strutturalmente inammissibile: escluso prima del Pareto;
- scenario con incertezza D: resta confrontabile ma può bloccare la recommendation;
- input `ESTIMATE`: robust Pareto tramite bounds, se disponibili;
- più scenari robustamente non dominati: nessun vincitore artificiale;
- un unico robust winner può essere raccomandato solo con A-E evidence verificata, assembly hashato, scenario inputs epistemicamente eleggibili e nessun blocker residuo.

## 7. Prossimo checkpoint

Il prossimo lavoro di Gate F non è più infrastrutturale: è **scenario construction and integration**. La prima tabella numerica Gate F valida dovrà essere generata meccanicamente da B/C/D/E e non dai legacy `route_variants.csv`, `service_simulation_scenarios.csv`, `train_connections.csv` o `scenario_comparison.csv`.
