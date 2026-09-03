# Gate C — Transit integrity

**Workstream:** `gate-c-workstream`
**Original baseline:** `549198743e7265b333da565ce6990f9241cfd1fd`
**Stato:** `PASS`
**Documento di chiusura:** `docs/GATE_C_PASS.md`

## Obiettivo

Gate C verifica l'integrità del livello TPL per D184, D185, D150, D170 e S8: fonti ufficiali, operatori, service dates, fermate, pattern, timetable S8 e distinzione tra servizio ordinario e deviazioni temporanee. Le metriche spaziali consumano gli output validati di Gate B, che è PASS.

## Gerarchia delle fonti

### Autobus, struttura GTFS

Lo snapshot GTFS ufficiale Agenzia TPL Como-Lecco-Varese / Arriva in `data/raw/gtfs/agency_arriva` è usato esclusivamente nel proprio periodo dichiarato `2026-01-01` → `2026-06-08`.

Da questo feed derivano:

- presenza di D184, D185, D150, D170;
- operatori tramite `routes.agency_id -> agency.agency_id`;
- service dates tramite `calendar.txt` + `calendar_dates.txt`;
- fermate e pattern tramite `trips.txt`, `stop_times.txt`, `stops.txt`.

Poiché `calendar.txt` è header-only, l'attivazione effettiva dei servizi è ricavata da `calendar_dates.txt`. È vietato inferire il calendario dal testo del `service_id`.

### Autobus, servizio corrente

Per il 3 settembre 2026 il GTFS bus conservato è scaduto. Gate C non lo estende e non crea un GTFS sostitutivo.

La validità corrente viene verificata dai timetable ufficiali Lecco Trasporti / Arriva:

- `https://www.leccotrasporti.it/percorsi/estivo/linea-d184.pdf`
- `https://www.leccotrasporti.it/percorsi/estivo/linea-d185.pdf`
- `https://www.leccotrasporti.it/percorsi/estivo/linea-d150.pdf`
- `https://www.leccotrasporti.it/percorsi/estivo/linea-d170.pdf`

Tutti dichiarano validità 9 giugno → 13 settembre 2026. `scripts/gate_c_live_bus_timetables.py` scarica i PDF, calcola SHA256, verifica direzioni e validità e associa day-code e note A/B/D/V usando coordinate PDF.

Questi record sono `RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE`, mai etichettati come GTFS.

### Ferrovia

Per il servizio corrente S8 si usa il GTFS ufficiale Regione Lombardia / Trenord:

- dataset: `https://www.dati.lombardia.it/Mobilit-e-trasporti/Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9`
- download: `https://www.dati.lombardia.it/download/3z4k-mxz9/application/zip`

`scripts/gate_c_live_trenord.py` scarica il feed, ne verifica le tabelle core, applica `calendar.txt` + `calendar_dates.txt`, seleziona S8 e risolve `S01514` / `Olgiate-Calco-Brivio`.

Lo snapshot Trenord storico privo di calendario resta una fonte congelata ma non viene usato per dichiarare l'attività di una specifica data corrente.

## Regole epistemiche

- record letti direttamente da fonti ufficiali: `FACT`;
- metriche calcolate direttamente da GTFS ufficiale: `DERIVED_FROM_OFFICIAL_GTFS` o `DERIVED_FROM_LIVE_OFFICIAL_GTFS`;
- colonne ricostruite dai timetable bus ufficiali: `RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE`;
- scenari di rete futuri: `MODEL OUTPUT` / `ASSUMPTION` secondo il Gate downstream;
- pseudo-GTFS e metriche manuali legacy: `INVALIDATED_AS_EVIDENCE`.

Una ricostruzione da timetable primario non viene mai rinominata `FACT GTFS`.

## Distinzione ordinario / temporaneo

La D185 del periodo corrente contiene una deviazione esplicita dovuta ai lavori al ponte di Brivio, con transito via Ponte Cantù e sospensione di `CISANO Sosta`. È una condizione temporanea di fonte primaria e non viene incorporata come geometria ordinaria storica.

Il vecchio `network_2026_emergency` e il `+25 min` manuale restano invalidati.

## Quarantena legacy

Non sono evidenza ammessa:

- `data/raw/gtfs/network_structural/`;
- `data/raw/gtfs/network_2026_emergency/`;
- `src/gtfs_loader.py` per il database fermate/calendario manuale;
- `src/timetable_engine.py::TRENI_S8_VIGENTI`;
- i precedenti output hard-coded di `scripts/05_current_service.py` e `scripts/11_train_coordination.py`.

`scripts/02_parse_gtfs.py`, `scripts/05_current_service.py` e `scripts/11_train_coordination.py` sono fail-closed: se eseguiti terminano con errore esplicito.

## Criteri di validazione

Gate C richiede contemporaneamente:

1. route/operator/stop/pattern verificati dal GTFS bus ufficiale nel periodo coperto;
2. servizio bus corrente verificato da fonte primaria valida alla data di audit senza generare dati sintetici;
3. S8 corrente risolto da GTFS ufficiale con calendario;
4. note di servizio e deviazioni temporanee applicate senza assunzioni nascoste;
5. Gate B PASS per le dipendenze spaziali;
6. legacy hard-coded non utilizzabile come evidenza;
7. test mirati, guardrail anti-synthetic e `git diff --check` verdi su runner pulito.

Tutti i criteri sono soddisfatti. Il verdetto e i risultati numerici autorevoli sono in `docs/GATE_C_PASS.md`.
