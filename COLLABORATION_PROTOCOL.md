# Protocollo di collaborazione multi-agente

Questo repository viene sviluppato con due agenti complementari:

- **Antigravity IDE**: executor locale, download e preprocessing di dataset pesanti, browser/terminal, routing e generazione artefatti.
- **GPT reviewer/co-developer**: audit indipendente, verifica metodologica, sviluppo concorrente, test, controllo provenance e revisione degli output via GitHub.

GitHub è la fonte condivisa di verità. Nessun risultato è considerato valido perché dichiarato tale in chat o in un report: deve essere ricostruibile dal repository.

## 1. Branch

- `main`: solo risultati revisionati e sufficientemente affidabili.
- `antigravity-real-data`: lavoro di Antigravity sui dati reali.
- `gpt-coordination`: protocollo, audit, test e modifiche del secondo agente.

Eventuali branch ulteriori devono avere scopo esplicito.

## 2. Stati epistemici obbligatori

Ogni metrica rilevante deve avere uno dei seguenti stati:

- `FACT`: direttamente derivata da fonte primaria identificata.
- `DERIVED`: calcolo deterministico su FACT, con script riproducibile.
- `ESTIMATE`: stima basata su dati reali, con metodo e incertezza dichiarati.
- `ASSUMPTION`: parametro scelto per simulazione, non osservato.
- `PLACEHOLDER`: dato sintetico o provvisorio, vietato nelle conclusioni.
- `INVALIDATED`: risultato precedentemente prodotto ma bocciato dall'audit.

`PLACEHOLDER` e `INVALIDATED` non possono alimentare raccomandazioni finali.

## 3. Provenance minima

Ogni dataset utilizzato nelle conclusioni deve comparire in `data/manifest.csv` o in un manifest equivalente con almeno:

- dataset_id
- ente/source
- URL o origine verificabile
- data di accesso
- anno/data di riferimento
- licenza
- file locale
- checksum SHA256
- trasformazioni
- stato epistemico

Sono obbligatori record separati per almeno:

- ISTAT
- WorldPop o altra griglia reale di popolazione
- DEM reale
- OpenStreetMap / grafo di routing
- GTFS ufficiale
- Programma di Bacino
- matrice OD ufficiale, se reperita
- frequentazione ferroviaria
- orario ferroviario

## 4. Regola anti-sintetico

Sono vietati nelle pipeline di produzione, salvo file esplicitamente in `legacy/` o `fixtures/`:

- `np.random` per creare dati territoriali
- popolazioni di frazione assegnate manualmente e poi presentate come WorldPop
- coordinate di fermata inventate quando esiste un GTFS
- matrici OD hard-coded presentate come ISTAT
- distanze euclidee moltiplicate per un fattore e definite `routing OSM`
- km o runtime di varianti scritti a mano e successivamente "ottimizzati"
- giudizi `raccomandata`, `ottimale`, `bocciata` inseriti prima del calcolo

## 5. Parametri di progetto condivisi

### Territorio core

- Olgiate Molgora
- Calco
- Brivio
- Santa Maria Hoè
- La Valletta Brianza

Territori esterni necessari: Colle Brianza/Ravellino, Cisano Bergamasco, Caprino Bergamasco e altri toccati dalle linee rilevanti.

### Hub

Stazione Olgiate-Calco-Brivio FS.

### Ipotesi da testare

Sistema locale a doppio anello / figura 8 con circolazione in entrambi i versi, senza assumere che sia necessariamente la soluzione finale.

### Frequenze

Le metriche devono distinguere sempre:

- `headway_CW`
- `headway_CCW`
- `headway_combined`

Con ciclo vicino a 60 minuti:

- 1 bus CW + 1 bus CCW => circa 60 min per senso, circa 30 min combinati se sfalsati.
- 30 min per senso richiede circa 4 bus, salvo diversa struttura operativa dimostrata.

### Accessibilità pedonale

Output principali alle soglie 5, 8, 10, 12 minuti.

Il risultato principale deve usare routing pedonale reale su rete. Un'approssimazione euclidea può esistere solo come benchmark separato.

### Popolazione

Distribuzione spaziale da dataset raster/grid reale, eventualmente calibrata sui totali ISTAT comunali. La calibrazione può modificare il totale comunale ma non inventare la distribuzione intracomunale.

### Routing bus

Geometrie e distanze devono derivare da una rete stradale reale. I segmenti con idoneità bus non dimostrabile devono essere marcati per field check.

### Tempi di esercizio

Separare sempre:

- pure running time
- dwell time
- layover/recovery
- cycle time

Non utilizzare un singolo valore ambiguo `runtime`.

### Interscambio ferroviario

Usare orario S8 vigente da fonte ufficiale. Distinguere bus->train e train->bus, Milano e Lecco. Non hardcodare minuti senza provenance.

### Risorse

Confrontare bus-km e vehicle-hours con il Programma di Bacino. Non chiamare `saldo zero` uno scenario semplicemente vicino al budget: riportare delta assoluto e percentuale.

## 6. Metriche minime per variante

Ogni variante deve produrre automaticamente:

- route geometry
- route_km
- pure_running_minutes
- dwell_minutes
- recovery_minutes
- cycle_minutes
- stops_count
- residents_5m
- residents_8m
- residents_10m
- residents_12m
- newly_served_residents
- POI by category
- OD demand captured, solo se supportata da dati reali
- uncertain_road_km
- existing_service_overlap
- annual_bus_km by service scenario
- vehicle_hours
- vehicles_required
- headway_CW
- headway_CCW
- headway_combined

## 7. Pareto e selezione

La Pareto frontier viene calcolata solo dopo il completamento delle metriche reali.

Nessun singolo score ponderato può da solo definire la soluzione finale. Lo score può essere usato come sensitivity analysis dopo l'identificazione della frontiera.

## 8. Handoff tra agenti

Ogni handoff deve aggiornare `AGENT_STATUS.md` con:

- timestamp
- autore (`ANTIGRAVITY` o `GPT`)
- branch
- commit
- task completato
- file modificati
- risultati principali
- stato epistemico dei risultati
- problemi aperti
- richiesta precisa all'altro agente

Il destinatario deve verificare il commit, non soltanto leggere il riassunto.

## 9. Gate di revisione

Prima di promuovere un risultato a `main` devono essere superati i gate:

### GATE A - provenance
Fonti reali presenti e verificabili.

### GATE B - spatial integrity
Popolazione, DEM e routing reali, nessun placeholder.

### GATE C - transit integrity
GTFS/orari reali e rete strutturale correttamente distinta dalle ricostruzioni.

### GATE D - route integrity
Geometrie, km e runtime calcolati, non hard-coded.

### GATE E - service math
Frequenze, mezzi, bus-km e vehicle-hours matematicamente coerenti.

### GATE F - recommendation
Raccomandazione compatibile con risultati, limiti e sensitivity analysis.

## 10. Regola di arresto

Se un gate fallisce, i checkpoint downstream dipendenti vengono marcati `BLOCKED` o `INVALIDATED` fino alla correzione.

La priorità è l'accuratezza, non preservare una conclusione precedente.
