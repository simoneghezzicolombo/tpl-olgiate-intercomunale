# Gate C — Transit integrity

**Workstream:** `gate-c-workstream`
**Baseline:** `549198743e7265b333da565ce6990f9241cfd1fd` (`antigravity-real-data`)
**Stato:** PROVISIONAL / IN VALIDAZIONE

## Obiettivo

Gate C verifica esclusivamente l'integrità del livello di trasporto pubblico: feed GTFS ufficiali, operatori, service dates, linee D184/D185/D150/D170, fermate e pattern reali, nonché l'orario S8 derivato dalle tabelle GTFS Trenord. La geometria territoriale e lo snapping alle fermate restano dipendenze di Gate B.

## Fonti ammesse

### Autobus

Fonte primaria: snapshot GTFS ufficiale Agenzia TPL Como-Lecco-Varese / Arriva Italia + Addabus presente in `data/raw/gtfs/agency_arriva`.

Lo snapshot dichiara in `feed_info.txt`:

- `feed_start_date = 20260101`;
- `feed_end_date = 20260608`;
- `feed_version = 20251217`.

`calendar.txt` contiene solo l'intestazione; la risoluzione dei giorni di servizio deve quindi applicare `calendar_dates.txt`. È vietato dedurre il servizio da stringhe nel `service_id` quando esistono le tabelle GTFS previste per il calendario.

Le quattro linee core D184, D185, D150 e D170 risultano nel feed Arriva. L'operatore viene risolto relazionalmente tramite `routes.agency_id -> agency.agency_id`, non inserito a mano.

### Ferrovia

Fonte primaria: snapshot GTFS ufficiale Trenord in `data/raw/gtfs/rail_trenord`.

La linea S8 è identificata tramite `routes.route_id == S8`; gli eventi a Olgiate-Calco-Brivio devono essere estratti da `trips.txt`, `stop_times.txt` e `stops.txt`.

Lo snapshot ferroviario conservato nel repository non contiene né `calendar.txt` né `calendar_dates.txt`. Di conseguenza Gate C può derivare gli eventi/orari S8 presenti nello snapshot, mantenendo il relativo `service_id`, ma non può attestare con regole GTFS standard l'attivazione di un trip in una specifica data civile. Tale limite è classificato `PROVISIONAL_SERVICE_DATE_UNRESOLVED`.

## Invalidazioni esplicite

I seguenti artefatti **non sono evidenza ammessa per Gate C**:

| Artefatto | Stato Gate C | Motivo |
|---|---|---|
| `data/raw/gtfs/network_structural/` | `RECONSTRUCTED`, `INVALIDATED` | pseudo-GTFS costruito dal progetto, non feed istituzionale |
| `data/raw/gtfs/network_2026_emergency/` | `RECONSTRUCTED`, `INVALIDATED` | deviazione costruita manualmente, inclusi tempi a passo fisso |
| `scripts/02_parse_gtfs.py` | `INVALIDATED_AS_EVIDENCE` | contiene orari, sequenze e route metadata hard-coded |
| `src/gtfs_loader.py` | `INVALIDATED_AS_EVIDENCE` | contiene database fermate manuale e calendario ricostruito; la riga `SCOLASTICO` ha inoltre start date successiva alla end date |
| `scripts/05_current_service.py` | `INVALIDATED_AS_EVIDENCE` per metriche transit | baseline di corse/headway/coincidenze inserita a mano |
| `src/timetable_engine.py::TRENI_S8_VIGENTI` | `INVALIDATED_AS_EVIDENCE` | minuti S8 hard-coded pur essendo disponibile il GTFS Trenord |
| `scripts/11_train_coordination.py` | `INVALIDATED_AS_EVIDENCE` | configurazioni nodo e coincidenze giornaliere hard-coded |

Questi file possono rimanere nel repository come legacy finché non vengono refactorati, ma nessun risultato Gate C o downstream deve usarli come FACT.

## Distinzione servizio ordinario / deviazioni temporanee

Una deviazione temporanea può essere promossa a `FACT` solo se supportata da un feed GTFS ufficiale specifico, da un avviso ufficiale dell'ente/operatore con percorso e validità verificabili oppure da altra fonte primaria equivalente. Non è ammesso costruire una deviazione inserendo manualmente fermate o aggiungendo minuti alla percorrenza.

Lo snapshot Arriva 2025-2026 rappresenta una fonte ufficiale per il periodo da esso dichiarato. Non prova automaticamente né il servizio ordinario successivo all'8 giugno 2026 né eventuali deviazioni in vigore a settembre 2026.

## Regole di calcolo

1. Le service dates autobus derivano da `calendar.txt` + `calendar_dates.txt` secondo GTFS.
2. I pattern sono sequenze ordinate di `stop_id` prese da `stop_times.txt` per trip realmente attivi nella data auditata.
3. Gli operatori derivano dalle chiavi GTFS, non dal nome della linea.
4. Gli eventi S8 derivano dal GTFS Trenord, senza utilizzare minuti dell'ora hard-coded.
5. L'assenza di calendario GTFS ferroviario non viene colmata interpretando il testo del `service_id`; viene riportata come limite.
6. Risultati territoriali che richiedono confini, snapping o accessibilità sono `BLOCKED_BY_GATE_B` finché Gate B non è PASS.

## Condizioni per PASS definitivo

Gate C potrà essere PASS solo quando:

1. le quattro linee core sono verificate nel feed ufficiale e i relativi operatori sono risolti;
2. service dates, corse, fermate e pattern sono derivati dalle tabelle ufficiali;
3. l'orario S8 a Olgiate-Calco-Brivio è derivato dal GTFS Trenord;
4. è disponibile una base ufficiale temporalmente valida per il periodo di progetto corrente, oppure il periodo di riferimento viene congelato esplicitamente a una data coperta dal feed;
5. servizio ordinario e deviazioni temporanee sono distinti con provenance primaria;
6. nessun output downstream usa gli artefatti ricostruiti invalidati come se fossero FACT;
7. i test Gate C passano su clone pulito e i risultati numerici vengono ispezionati sostanzialmente.

Alla data del workstream (3 settembre 2026), la condizione 4 non è soddisfatta dal feed autobus conservato, che termina l'8 giugno 2026; inoltre il calendario standard del feed Trenord snapshot non è disponibile. Il verdetto resta quindi **PROVISIONAL** anche in presenza di test verdi.
