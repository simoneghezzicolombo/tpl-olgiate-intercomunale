# Gate F — Recommendation / Pareto workstream

**Branch baseline:** `antigravity-real-data` @ `549198743e7265b333da565ce6990f9241cfd1fd`
**Workstream:** `gate-f-workstream`
**Stato:** **PROVISIONAL**

## Dipendenze verificate

- Gate A: **PASS**, come registrato in `AGENT_STATUS.md` e `docs/GATE_A_PASS.md`.
- Gate B: **IN VALIDAZIONE**, come registrato in `docs/GATE_B_METHOD.md`.
- Gate C: nessun PASS autorevole presente nella baseline.
- Gate D: nessun PASS autorevole presente nella baseline.
- Gate E: nessun PASS autorevole presente nella baseline.

Di conseguenza Gate F non può produrre una raccomandazione definitiva. Il codice di questo workstream può essere preparato e testato, ma ogni eventuale risultato calcolato prima del PASS upstream deve essere marcato `PROVISIONAL/BLOCKED_BY_GATE_X`.

## Audit del materiale preesistente

La baseline contiene ancora artefatti della pipeline precedente invalidata. Non sono ammessi come evidenza Gate F:

- `outputs/route_variants.csv` contiene tracciati, distanze, runtime, popolazioni e giudizi inseriti come valori già risolti, incluso `VAR_04_DOPPIO_ANELLO_INTEGRATO` etichettato “Raccomandata” e “SOLUZIONE PARETO-OTTIMALE”;
- `scripts/10_service_simulation.py` costruisce cinque scenari con km, tempi, frequenze, mezzi e giudizi hardcoded e chiama lo scenario 4 “Raccomandato” prima della validazione upstream;
- `scripts/11_train_coordination.py` costruisce manualmente minuti di arrivo/partenza bus e assegna un rail score con coefficienti arbitrari;
- `scripts/12_scenario_comparison.py` confronta scenari con metriche hardcoded;
- `src/multi_criteria.py::sensitivity_analysis()` usa pesi prefissati e `scripts/09_route_optimization.py` seleziona un `best_balanced` sulla base di quei pesi.

Questi file possono restare nella baseline per cronologia/compatibilità, ma **Gate F rifiuta esplicitamente i relativi output legacy**. La loro presenza non costituisce un risultato e non viene usata per raccomandare la figura a 8.

## Metodo Gate F introdotto

`src/gate_f_pareto.py` implementa un confronto Pareto senza punteggi di preferenza predefiniti. Gli obiettivi previsti sono copertura della popolazione, headway combinato, bus-km annui, mezzi di punta, connessioni utili S8 e territori serviti. Ogni metrica deve arrivare con:

- valore numerico finito;
- stato epistemico ammesso (`FACT`, `DERIVED`, `ESTIMATE`, `RECONSTRUCTED`, `MODEL OUTPUT`);
- fonte tracciabile specifica;
- un solo scenario esplicitamente identificato come baseline.

Il modulo calcola inoltre una sensitivity **leave-one-objective-out**. Non usa pesi: misura quante volte ciascuno scenario resta sulla frontiera quando, a turno, viene rimosso un obiettivo. È una misura di robustezza della non-dominanza, non un ranking di merito.

La raccomandazione automatica segue regole restrittive:

1. se almeno uno tra Gate A–E non è `PASS`, verdict `PROVISIONAL` e nessuna raccomandazione;
2. se tutti i Gate sono `PASS` ma più scenari restano non dominati, Gate F restituisce `NO_SINGLE_WINNER_PARETO_TRADEOFF`;
3. una raccomandazione automatica è possibile solo se esiste un'unica soluzione Pareto non dominata rispetto a tutti gli obiettivi dichiarati;
4. preferenze politiche o vincoli aggiuntivi possono essere applicati solo come criteri espliciti e tracciati, non come pesi nascosti.

## Contratto di input upstream

Il runner `scripts/13_gate_f_pareto.py` attende `outputs/gate_f_scenario_metrics.csv` o un percorso indicato con `--input`. Per ogni obiettivo `<metric>` devono esistere anche `<metric>__status` e `<metric>__source`.

I seguenti output sono rifiutati esplicitamente come sorgente perché appartengono alla pipeline hardcoded invalidata:

- `outputs/route_variants.csv`
- `outputs/pareto_frontier.csv`
- `outputs/service_simulation_scenarios.csv`
- `outputs/train_connections.csv`
- `outputs/scenario_comparison.csv`

Il confronto con la baseline non contiene il valore `111419` nel codice Gate F: i delta vengono derivati dalla riga baseline fornita da Gate E, così il valore entra solo dopo validazione upstream.

## Condizioni per chiudere Gate F

Per un PASS definitivo servono tutti i seguenti elementi:

1. Gate B, C, D ed E formalmente PASS sulla stessa catena di input/versione;
2. tabella scenari upstream generata dalla pipeline reale e non da script legacy, con provenance per ogni metrica;
3. almeno baseline D184+D185 e tutte le alternative realmente ammissibili prodotte da Gate D/E, incluse alternative non-figura-8;
4. metriche omogenee di copertura, frequenza, bus-km, mezzi, accessibilità S8 e territorio servito;
5. esecuzione Pareto e sensitivity su quegli input;
6. controllo sostanziale degli scenari non dominati, non soltanto test verdi;
7. eventuale raccomandazione coerente con la frontiera. Se rimangono trade-off reali, il risultato corretto è una shortlist Pareto e non un vincitore artificiale.

## Risultati numerici attuali

Nessun risultato numerico di scenario viene dichiarato valido in questo workstream. Gli output preesistenti con distanze, tempi, coperture, bus-km o rail score sono considerati **INVALIDATED** per Gate F finché non vengono rigenerati dai Gate real-data upstream.
