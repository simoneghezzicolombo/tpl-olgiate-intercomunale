# Gate C — PASS

**Gate:** C — Transit integrity  
**Verdict:** `PASS`  
**Workstream:** `gate-c-workstream`  
**Original baseline:** `549198743e7265b333da565ce6990f9241cfd1fd`  
**Gate B dependency:** `PASS`, validated computational commit `55d726564e13acca55ce563cc911263ac513acb0`; canonical status subsequently recorded on `antigravity-real-data`.  
**Audit date:** 2026-09-03

## Scope closed

Gate C establishes a source-grounded transit layer for D184, D185, D150, D170 and S8 without using the project's former reconstructed pseudo-GTFS or hard-coded timetables as evidence.

The PASS rests on two complementary bus evidence layers and one current rail layer:

1. the official Agency/Arriva GTFS snapshot in `data/raw/gtfs/agency_arriva`, used only inside its declared validity range to verify route/operator relationships, stops, service-date logic and real stop patterns;
2. current official Lecco Trasporti / Arriva summer-2026 timetable PDFs, valid 2026-06-09 through 2026-09-13, reconstructed by PDF coordinates for the audit date 2026-09-03 and explicitly labelled `RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE` rather than GTFS;
3. the current official Regione Lombardia / Trenord GTFS downloaded live and calendar-resolved for 2026-09-03.

This combination closes the temporal gap of the stored bus GTFS without fabricating a replacement GTFS. Historical GTFS facts remain GTFS facts; current bus timetable rows remain reconstructed primary-source records.

## Official bus GTFS verification

The stored Arriva feed declares `2026-01-01` through `2026-06-08`. Its `calendar.txt` is header-only and service activation is encoded in `calendar_dates.txt`; Gate C therefore applies GTFS calendar exceptions rather than inferring dates from `service_id` text.

On the covered audit date 2026-05-06:

| Route | Operator | Snapshot trips | Active trips | Active stop patterns |
|---|---|---:|---:|---:|
| D184 | Arriva Italia Srl - Lecco | 15 | 15 | 8 |
| D185 | Arriva Italia Srl - Lecco | 27 | 19 | 9 |
| D150 | Arriva Italia Srl - Lecco | 41 | 33 | 28 |
| D170 | Arriva Italia Srl - Lecco | 118 | 96 | 49 |

Patterns are ordered `stop_id` sequences from official `stop_times.txt`; tests verify that every referenced stop exists in official `stops.txt`.

## Current bus service on 2026-09-03

The official operator timetables are downloaded on every live audit, hashed, checked for the declared validity period and parsed using PDF word coordinates. Day-code columns are associated with their A/B/D/V note cells by horizontal coordinate rather than text order.

For 2026-09-03, after weekday and note rules are applied:

| Route | Scheduled timetable columns | Thursday-eligible before notes | Active reconstructed columns |
|---|---:|---:|---:|
| D184 | 12 | 12 | **12** |
| D185 | 13 | 13 | **13** |
| D150 | 39 | 35 | **30** |
| D170 | 55 | 54 | **49** |

Epistemic status for these values: `RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE`. They are not represented as GTFS trips.

The parser implements the published timetable semantics:

- `A`: suspended from 27 July through 30 August, therefore active again on 3 September;
- `B`: runs only from 27 July through 30 August, therefore inactive on 3 September;
- `D`: does not run on Saturdays within that exception interval; it does not suppress a Thursday outside the interval;
- `V`: stop-pattern note, not a service-date restriction.

## D185 ordinary service versus temporary deviation

The current official D185 timetable records the Brivio bridge works explicitly: services use Ponte Cantù and `CISANO Sosta` is suspended. This is treated as a current temporary-service `FACT` supported by primary sources, while the old project-generated emergency pseudo-GTFS and its manually added `+25 min` are `INVALIDATED_AS_EVIDENCE`.

No temporary detour is promoted to the ordinary network baseline.

## Current S8 timetable from official GTFS

`scripts/gate_c_live_trenord.py` downloads the current official Regione Lombardia / Trenord GTFS and resolves service by GTFS calendar rules.

For 2026-09-03:

- feed service span: `2026-07-26` to `2026-12-12`;
- download SHA256: `b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6`;
- active service IDs: `2871`;
- active S8 trips: **74**;
- active S8 events at Olgiate-Calco-Brivio: **74**;
- station: `S01514`, `Olgiate-Calco-Brivio`.

Epistemic status: `DERIVED_FROM_LIVE_OFFICIAL_GTFS`.

The older rail snapshot lacking `calendar.txt` / `calendar_dates.txt` remains valid only as a frozen snapshot and is no longer used to resolve the current service date.

## Gate B dependency

Gate B is PASS. Its validated output includes 66 GTFS core stops, 62 snapped within the 250 m threshold and 5/5 audited spot checks. Gate C therefore no longer carries `BLOCKED_BY_GATE_B` for stop snapping/catchment dependencies. Spatial metrics must still consume the validated Gate B outputs rather than reimplementing snapping inside Gate C.

## Invalidated and quarantined legacy paths

The following remain forbidden as transit evidence:

- `data/raw/gtfs/network_structural/` — `RECONSTRUCTED`, `INVALIDATED`;
- `data/raw/gtfs/network_2026_emergency/` — `RECONSTRUCTED`, `INVALIDATED`;
- `src/gtfs_loader.py` manual stop/calendar database — `INVALIDATED_AS_EVIDENCE`;
- `src/timetable_engine.py::TRENI_S8_VIGENTI` — `INVALIDATED_AS_EVIDENCE`;
- old hard-coded current-service and train-coordination metrics — `INVALIDATED_AS_EVIDENCE`.

`scripts/02_parse_gtfs.py`, `scripts/05_current_service.py` and `scripts/11_train_coordination.py` are now fail-closed and raise an explicit error rather than regenerating or consuming invalidated transit results.

## Tests and reproducibility

The Gate C workflow executes on a clean GitHub runner and requires:

- `tests/test_gate_c_transit.py`;
- `tests/test_gate_c_quarantine.py`;
- official stored-GTFS audit for 2026-05-06;
- stale-snapshot audit for 2026-09-03;
- live current bus timetable audit for 2026-09-03;
- live current Trenord GTFS audit for 2026-09-03;
- `tests/test_audit_anti_synthetic_guardrails.py`;
- `git diff --check` from the original Gate C baseline.

The last pre-PASS full run (`33702829064`) completed successfully: 10 targeted Gate C tests passed, 3 anti-synthetic guardrail tests passed, both live source audits passed and `git diff --check` passed.

## PASS conditions

All Gate C closing conditions are satisfied:

1. D184/D185/D150/D170 and operators verified from official GTFS;
2. official GTFS service dates/stops/patterns verified on a covered date;
3. current bus service on the project audit date verified from primary operator timetables without creating synthetic GTFS;
4. current S8 service date and timetable resolved from official GTFS;
5. ordinary service and the D185 temporary deviation are explicitly separated;
6. Gate B is PASS for the spatial dependency;
7. invalidated hard-coded transit paths are quarantined from active execution;
8. clean-run CI, adversarial tests and whitespace checks pass.

**VERDICT: PASS.**
