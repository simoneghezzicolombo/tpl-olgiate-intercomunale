# Gate C audit findings

**Workstream:** `gate-c-workstream`
**Baseline:** `549198743e7265b333da565ce6990f9241cfd1fd`
**Verdict corrente:** `PROVISIONAL`

## Stato upstream verificato

- Gate A: `PASS` documentato in `docs/GATE_A_PASS.md` e `AGENT_STATUS.md`.
- Gate B: `IN VALIDAZIONE` in `docs/GATE_B_METHOD.md`, quindi non viene trattato come PASS.
- `AGENT_PROTOCOL.md`: non presente nella baseline; il protocollo operativo presente è `COLLABORATION_PROTOCOL.md`.

Gate C non assume output spaziali di Gate B. Qualsiasi successivo conteggio basato su snapping, catchment o appartenenza territoriale dovrà essere marcato `BLOCKED_BY_GATE_B` finché Gate B non è PASS.

## Finding C-01 — pseudo-GTFS ricostruito usato come se fosse sorgente

**Severità:** critica
**Stato:** corretto nel workstream / legacy invalidato

`scripts/02_parse_gtfs.py` non effettua il parsing del feed istituzionale. Costruisce manualmente D184/D185, assegna sequenze fermata e orari hard-coded e genera anche una variante `network_2026_emergency` con tempi artificialmente dilatati. I test legacy `tests/test_gtfs_integrity.py` verificano soltanto la coerenza interna di questi file ricostruiti, perciò possono risultare verdi senza dimostrare la veridicità del dato transit.

**Azione:** Gate C legge esclusivamente `agency_arriva`, `agency_lineelecco` e `rail_trenord`. `network_structural` e `network_2026_emergency` sono `RECONSTRUCTED` + `INVALIDATED_AS_EVIDENCE`.

## Finding C-02 — service dates autobus lette dal file sbagliato

**Severità:** alta
**Stato:** corretto

Nel feed Arriva ufficiale `calendar.txt` contiene solo l'intestazione. L'effettiva attivazione dei `service_id` è espressa da `calendar_dates.txt`. Un parser che guarda soltanto `calendar.txt` conclude erroneamente che non esiste alcun servizio.

**Azione:** `active_service_ids()` applica prima l'eventuale calendario ordinario e poi le eccezioni GTFS di `calendar_dates.txt`, senza inferire date dal testo del `service_id`.

## Finding C-03 — snapshot autobus non valido per settembre 2026

**Severità:** alta
**Stato:** blocker temporale

Il `feed_info.txt` Arriva nel repository dichiara validità `2026-01-01` → `2026-06-08`, versione `20251217`. La pagina Open Data dell'Agenzia TPL Como-Lecco-Varese consultata il 3 settembre 2026 continua a presentare come dataset GTFS pubblicato l'"orario invernale ed estivo 2025-2026" e non espone nella stessa sezione un GTFS 2026-2027.

Fonte primaria: `https://www.tplcomoleccovarese.it/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/172`

**Conseguenza:** il feed resta FACT per il periodo dichiarato, ma qualunque conclusione sulle corse autobus del 3 settembre 2026 basata esclusivamente su quel GTFS è `PROVISIONAL`.

## Finding C-04 — deviazione D185 reale diversa dalla ricostruzione legacy

**Severità:** critica
**Stato:** fonte primaria trovata; ricostruzione legacy invalidata

Fonti ufficiali Agenzia TPL, Provincia di Lecco, Arriva Italia e Lecco Trasporti attestano che dal 4 maggio 2026 la chiusura del Ponte di Brivio modifica la D185 con deviazione via Olginate / Ponte Cesare Cantù / Calolziocorte-Bisone. L'Agenzia e la Provincia indicano un allungamento di circa 12 km e un incremento stimato dei tempi di percorrenza di 30-40 minuti.

Fonti:

- `https://tplcomoleccovarese.it/atpcolc/po/mostra_news.php?area=H&id=1137`
- `https://www.provincia.lecco.it/2026/04/23/chiusura-ponte-di-brivio-le-modifiche-alle-linee-bus/`
- `https://www.leccotrasporti.it/avvisi/linea-d185-chiusura-ponte-di-brivio/`
- `https://www.leccotrasporti.it/percorsi/estivo/linea-d185.pdf`

L'orario ufficiale D185 estivo è dichiarato in vigore dal 9 giugno al 13 settembre 2026 e riporta esplicitamente la deviazione via Ponte Cantù e la sospensione di `CISANO Sosta`. Il 3 settembre 2026 ricade quindi nel periodo di validità dichiarato di tale timetable.

La precedente ricostruzione del progetto usa invece una dilatazione temporale manuale e non può essere promossa a FACT. In particolare, qualunque `+25 min` costruito nel codice non sostituisce il dato ufficiale 30-40 minuti, che peraltro è un intervallo stimato dall'ente e non una costante da sommare a ogni corsa.

## Finding C-05 — stazione S8 cercata con denominazione non ufficiale

**Severità:** media
**Stato:** corretto e coperto da regressione

Nel GTFS Trenord la stazione è `Olgiate-Calco-Brivio`, `stop_id = S01514`. Una prima implementazione Gate C cercava erroneamente anche il token `Molgora`, producendo zero match. La CI ha intercettato il bug. Il resolver ora usa i token ufficiali `Olgiate`, `Calco`, `Brivio` e il test fissa nome e stop ID di fonte.

## Finding C-06 — GTFS Trenord snapshot senza calendario standard

**Severità:** alta
**Stato:** blocker di service-date, non di estrazione timetable

Nel folder `data/raw/gtfs/rail_trenord` sono presenti `routes.txt`, `trips.txt`, `stop_times.txt`, `stops.txt` e `feed_info.txt`, ma non `calendar.txt` né `calendar_dates.txt`.

La S8 e gli eventi alla stazione possono quindi essere estratti dalle tabelle GTFS e mantenuti con il loro `service_id`, ma non viene dichiarato che un trip sia attivo in una specifica data civile usando convenzioni non standard o interpretando il testo dell'ID. Lo stato è `PROVISIONAL_SERVICE_DATE_UNRESOLVED`.

## Finding C-07 — timetable S8 hard-coded nel motore legacy

**Severità:** alta
**Stato:** invalidato come evidenza

`src/timetable_engine.py` contiene `TRENI_S8_VIGENTI` con minuti dell'ora hard-coded. `scripts/11_train_coordination.py` contiene ulteriori minuti e conteggi di coincidenze inseriti manualmente. Entrambi sono incompatibili con Gate C come fonte di verità.

**Azione:** `s8_station_events()` deriva gli eventi da `routes` → `trips` → `stop_times` → `stops` del GTFS Trenord.

## Evidenza corrente extra-GTFS per D184

Il timetable ufficiale Lecco Trasporti / Arriva della D184 pubblicato nel percorso estivo dichiara validità dal 9 giugno al 13 settembre 2026, quindi costituisce evidenza primaria corrente per quella linea nel giorno di audit. Non viene però usato per colmare artificialmente il GTFS scaduto o per generare record GTFS sintetici.

Fonte: `https://www.leccotrasporti.it/percorsi/estivo/linea-d184.pdf`

## Cosa manca per PASS

1. Una fonte autobus ufficiale strutturata e temporalmente valida per il periodo operativo che il progetto vuole modellare, idealmente GTFS 2026-2027, oppure una decisione metodologica esplicita di congelare la baseline a una data coperta dallo snapshot 2025-2026.
2. Una modalità source-grounded per risolvere le service dates Trenord, senza inferirle informalmente dal `service_id`.
3. Verifica current-period anche di D150 e D170 se il periodo di progetto resta settembre 2026; lo snapshot GTFS 2025-2026 ne prova struttura e storico, non la validità corrente.
4. Refactor o quarantena downstream dei consumatori legacy hard-coded prima che Gate E/F possano trattarne gli output come input validi.
5. Gate B PASS per qualunque metrica Gate C che dipenda da snapping, catchment o classificazione territoriale delle fermate.
