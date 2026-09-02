# Protocollo di coordinamento multi-agent

## Obiettivo
Questo repository è lavorato da due agenti indipendenti:

- **Antigravity**: executor locale, download e processing geospaziale pesante, browser validation, esecuzione pipeline completa.
- **GPT reviewer/co-developer**: audit indipendente, verifica provenance, controllo matematico e trasportistico, test, correzioni di codice e review dei risultati.

L'obiettivo è evitare che assunzioni o placeholder vengano promossi a risultati senza verifica indipendente.

## Branch model

- `main`: solo risultati verificati e accettati.
- `antigravity-real-data`: lavoro principale Antigravity.
- `gpt-audit-fixes`: correzioni e strumenti indipendenti GPT.
- branch temporanei ammessi per singoli task.

Nessun agente deve sviluppare direttamente su `main`.

## Source-of-truth rule
Ogni metrica quantitativa deve avere provenance tracciabile.

Classificazione obbligatoria:

- `FACT`: importato da fonte primaria/ufficiale.
- `DERIVED`: trasformazione riproducibile di FACT.
- `ESTIMATE`: stima basata su input reali, con metodo dichiarato.
- `ASSUMPTION`: parametro scelto, sempre separato dagli input empirici.
- `MODEL_OUTPUT`: risultato del modello.
- `PLACEHOLDER`: valore sintetico o temporaneo, vietato nei risultati finali.

Un valore `PLACEHOLDER` non può entrare in Pareto, scenario comparison o rapporto finale.

## Provenance gate
Prima di usare un dataset nel modello devono esistere:

1. ente/source;
2. URL o origine verificabile;
3. data di accesso;
4. anno/versione;
5. licenza quando disponibile;
6. checksum SHA256 quando il file è locale;
7. script che lo importa;
8. classificazione epistemica.

`data/manifest.csv` è la fonte primaria di provenance del progetto.

## Dataset minimi reali richiesti

- ISTAT popolazione/totali comunali;
- WorldPop o altra griglia demografica reale;
- DEM reale;
- OSM reale;
- GTFS ufficiale Agenzia TPL;
- Programma di Bacino;
- dati ferroviari S8;
- orario ferroviario vigente;
- matrice OD ufficiale, se reperibile.

Se una fonte non è disponibile, scrivere `DATA NOT AVAILABLE`. Non sostituirla con numeri inventati.

## Routing rules

### Walking
Il risultato principale deve usare un vero grafo pedonale OSM/routing engine. Distanza euclidea × fattore può essere mantenuta soltanto come benchmark esplicitamente denominato `approximation_baseline`.

### Bus
Km e runtime devono derivare dalla geometria stradale effettiva. Se una strada non può essere verificata come bus-suitable, marcarla `FIELD_CHECK` e non trattarla come certa.

## Population rules

- Vietati `np.random`, nuclei manuali e pesi di frazione per creare il raster principale.
- WorldPop può essere calibrato ai totali ISTAT solo con fattore di scala comunale.
- La distribuzione intra-comunale deve restare quella della fonte reale.

## Transit rules

- GTFS corrente deve provenire dal feed ufficiale.
- Una rete storica/strutturale ricostruita deve essere chiamata `RECONSTRUCTED`, non `official GTFS`.
- Vietati tempi sintetici per le corse correnti.

## OD rules

- Vietati flussi OD hard-coded nei risultati empirici.
- Ogni matrice deve riportare anno e fonte.
- Nessuna estrapolazione verso il 2025 senza metodo quantitativo esplicito e sensitivity analysis.

## Operational consistency
Per ogni scenario pubblicare separatamente:

- `headway_cw_min`
- `headway_ccw_min`
- `headway_combined_min`
- `vehicles_peak`
- `vehicles_offpeak`
- `route_km`
- `cycle_runtime_min`
- `scheduled_cycle_min`
- `recovery_min`
- `annual_bus_km`

Regola: con ciclo ~60 min e 2 veicoli totali, 1 CW + 1 CCW equivale circa a 60 min per senso e 30 min combinati, non 30 min per senso.

## Independent review gates

### Gate 1 - Real inputs
Antigravity pubblica fonti, manifest, checksum e raw data metadata. GPT verifica che siano reali.

### Gate 2 - Spatial pipeline
Antigravity pubblica WorldPop/DEM/OSM processing. GPT controlla codice, determinismo, CRS, routing e double counting.

### Gate 3 - Transit baseline
Antigravity pubblica GTFS parsing e baseline. GPT verifica feed, calendari, fermate, trips, headway e anomalie.

### Gate 4 - Candidate routing
Antigravity pubblica geometrie e metriche. GPT verifica che km/runtime siano calcolati e non hard-coded.

### Gate 5 - Model results
Solo dopo i gate precedenti vengono ammessi Pareto e scenario comparison.

### Gate 6 - Final recommendation
La raccomandazione deve distinguere chiaramente FACT, DERIVED, ESTIMATE, ASSUMPTION e MODEL_OUTPUT.

## Handoff file
Ogni agente mantiene `AGENT_STATUS.md` con questa struttura:

```
agent: <antigravity|gpt>
branch: <branch>
last_commit: <sha>
status: <working|ready_for_review|blocked|accepted>
current_gate: <1-6>
changed_files:
  - ...
claims_added_or_changed:
  - ...
open_questions:
  - ...
next_action: ...
```

Quando `status: ready_for_review`, l'altro agente deve revisionare prima di procedere al gate successivo.

## Conflict rule
Se i due agenti ottengono risultati diversi:

1. nessuno dei due valori entra in `main`;
2. si confrontano input, versione della fonte, formule e unità;
3. si crea un piccolo test riproducibile;
4. prevale il risultato supportato da fonte e pipeline verificabile, non il consenso tra agenti.

## No self-certification
Un agente non può dichiarare un proprio checkpoint `validated` soltanto perché i test scritti dallo stesso agente passano.

I test verificano coerenza e regressioni. La validazione epistemica richiede review indipendente della provenance e del metodo.

## Main merge criterion
Un checkpoint può essere portato su `main` solo quando:

- provenance gate superato;
- test automatici passano;
- reviewer indipendente non ha blocker aperti;
- `AGENT_STATUS.md` è aggiornato;
- eventuali assunzioni sono esplicite.

## Current audit state
I precedenti risultati spaziali, OD e di ottimizzazione costruiti con input sintetici devono essere considerati `INVALIDATED_PENDING_REAL_DATA` e possono restare nel repository soltanto per tracciabilità storica.
