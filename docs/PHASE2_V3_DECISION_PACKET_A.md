# Phase 2 V3 Decision Packet A

## Stato

La fase tecnica non ha ulteriori blocker obbligatori nel pathway V3. Il Final Decision Sufficiency Gate certifica `v3_deterministic_technical_open_data_requirement_count = 0`.

Il GJT set-identification workstream di Alpha è stato inoltre sottoposto al targeted red-team concordato con A. La review aggiornata è `PASS_PHASE2_GJT_BOUNDS_TARGETED_REVIEW_A_V3`, con zero blocking issue. Il risultato GJT resta informativo ma non decisionale: 60.000 righe su 60.000 hanno upper bound non limitato, quindi non può produrre interval dominance, ranking o pruning.

Questo packet non seleziona PRIMARY o RUNNER-UP. Riduce la scelta finale a input normativi espliciti.

## 1. Pathway

### Opzione legacy

`LEGACY_V2_FULL_EVIDENCE`

Richiede ancora quattro evidenze tecniche/open-data oggi non identificate: non-regression completa rispetto al servizio attuale, full demand-weighted GJT, probabilità empirica di missed connection e sensitivity della domanda a livello di percorso.

### Opzione proposta

`V3_CERTIFIED_METRICS_DETERMINISTIC_ROBUSTNESS`

Ha zero requisiti tecnici/open-data ancora aperti. Usa solo accessibilità certificata, produzione exact, robustezza deterministica di coincidenze e vehicle blocks, incertezza di campo e baseline del servizio attuale esplicitamente come lower bound.

**Proposta A: scegliere V3.** Non perché sia “più favorevole” a una particolare rete, ma perché è l'unico contratto oggi chiudibile senza inventare dati o probabilità.

## 2. Budget annuale

I sei envelope sono sensitivity di policy separate. Il numero di contesti disponibili cresce col budget, ma non è una misura di qualità e non autorizza a scegliere automaticamente il budget maggiore.

| Envelope | bus-km/anno | Delta vs reference | Contesti exact | Con metriche bidirezionali | Frontiera descrittiva |
| --- | ---: | ---: | ---: | ---: | ---: |
| m20pct | 89.135,2 | -20% | 2.181 | 1.911 | 1.695 |
| m10pct | 100.277,1 | -10% | 2.478 | 2.174 | 1.865 |
| reference | 111.419,0 | 0% | 2.633 | 2.259 | 1.877 |
| p10pct | 122.560,9 | +10% | 2.856 | 2.464 | 2.059 |
| p20pct | 133.702,8 | +20% | 3.112 | 2.668 | 2.301 |
| p30pct | 144.844,7 | +30% | 3.235 | 2.799 | 2.487 |

**Proposta A: usare `reference = 111.419 bus-km/anno` come decision budget.** È il punto metodologicamente più neutro perché coincide con il riferimento di produzione ricostruito e validato: non incorpora né un taglio implicito né un'espansione implicita. Non è una dichiarazione che il budget reference sia socialmente ottimale. Se si vuole autorizzare esplicitamente più servizio, `p10pct`, `p20pct` e `p30pct` restano scelte perfettamente ammissibili.

## 3. Uncertainty band

Il vecchio `uncertainty_band_min` apparteneva a un contratto con una singola utilità GJT in minuti. V3 non possiede quella variabile: ha 29 dimensioni certificate con unità diverse, comprese quote, minuti, conteggi, km e booleani.

Applicare una singola banda in minuti a V3 sarebbe semanticamente scorretto oppure richiederebbe un nuovo modello di normalizzazione, cioè esattamente il tipo di peso nascosto che il contratto vuole evitare.

**Proposta A: non mantenere il legacy `uncertainty_band_min` nel contratto V3.** Usare i valori certificati persistiti con confronto deterministico exact. Se in futuro si desiderano soglie di equivalenza pratica, dovranno essere definite campo per campo e dichiarate esplicitamente.

## 4. Regola no-weight proposta

ID: `V3_SERVICE_EQUITY_ROBUSTNESS_LEXICOGRAPHIC_A`

La regola non calcola score e non normalizza le metriche. Dopo la selezione del budget:

1. richiede la classe `BIDIRECTIONAL_ENGINEERING_RETENTION_AVAILABLE` per la selezione finale, dato che in tutti e sei i budget esistono numerosi contesti con evidenza bidirezionale;
2. applica una selezione lessicografica sequenziale sui 29 assi certificati, mantenendo a ogni passaggio solo i candidati con il valore migliore del criterio corrente;
3. usa come ordine sostanziale: fattibilità operativa sotto sensitivity, equità territoriale e accessibilità, raggiungibilità bidirezionale, frequenza, robustezza delle coincidenze, ampiezza del servizio, continuità con il servizio attuale e incertezza di campo, efficienza di flotta e produzione, generalized feeder access pre-phase;
4. usa `plan_context_id` e `selected_timetable_id` soltanto come tie-break deterministico finale.

L'ordine completo campo per campo è congelato in `config/phase2_v3_decision_packet_a.json` e viene verificato automaticamente contro i 29 assi del contratto Pareto V3. Le direzioni `min`/`max` devono coincidere esattamente con quelle certificate.

### Perché questo ordine

La proposta rende prima non negoziabile l'assenza di fragilità operative gravi. Tra alternative operativamente credibili privilegia poi la copertura del comune peggio servito, quindi l'accessibilità generale e la funzione di feeder bidirezionale. Frequenza e robustezza dell'interscambio vengono prima dell'efficienza marginale di produzione, perché il budget è già stato fissato a monte. Costi di flotta e bus-km restano comunque tie-break sostanziali, non vengono ignorati.

Questa è una regola normativa proposta, non un fatto tecnico. Può essere approvata o modificata senza riaprire la fase di data science.

## 5. Cosa non facciamo

- non trattiamo i 12.284 Pareto members come shortlist;
- non eliminiamo automaticamente i 4.211 non-frontier contexts;
- non trasformiamo il GJT set-identification in full GJT;
- non assegniamo probabilità agli stress case di Stage E/F;
- non usiamo popolazione o OD comunale come demand weights;
- non scegliamo implicitamente il budget più alto;
- non usiamo weighted composite score.

Tutti i 16.495 contesti rimangono la base della finalizzazione fino all'approvazione esplicita del Decision Contract V3.

## 6. Input umano residuo

Per autorizzare la singola finalizzazione che produce `PRIMARY + RUNNER-UP` servono quindi quattro approvazioni, che possono essere date insieme:

- pathway: proposta `V3_CERTIFIED_METRICS_DETERMINISTIC_ROBUSTNESS`;
- budget: proposta `111.419 bus-km/anno`;
- uncertainty: proposta `DO_NOT_RETAIN_LEGACY_SINGLE_MINUTE_UNCERTAINTY_BAND_UNDER_V3`;
- rule: proposta `V3_SERVICE_EQUITY_ROBUSTNESS_LEXICOGRAPHIC_A`.

Una volta approvate, il passo successivo autorizzato è uno solo: implementare un finalizer V3 fail-closed, applicarlo ai 16.495 contesti conservati e materializzare PRIMARY e RUNNER-UP con trace completa di ogni eliminazione. Nessun altro Stage tecnico è richiesto prima di quel run.
