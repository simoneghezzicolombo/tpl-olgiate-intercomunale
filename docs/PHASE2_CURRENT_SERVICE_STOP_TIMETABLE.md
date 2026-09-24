# Phase 2 current-service stop timetable

## Status and scope

This workstream reconstructs an auditable stop-level and timetable-column-level current-service reference for routes D184, D185, D150 and D170 on the Phase 2 reference date **2026-09-03**.

It does not select, rank or recommend any future bus network.

Branch: `phase2-current-service-stop-timetable`.

Base optimizer commit: `147ad941579eb7ef17a5a54c19a5f820e5a226d4`.

Pinned Gate C PASS commit: `dcc3e75ae3b4f4ea5170f48e85345b83620c5536`.

The workstream extends the existing summary-level `current_service_reference` by materialising the stop rows, published times and complete PDF stop-row × timetable-column cell universe required for a defensible scheduled GJT baseline.

## Forbidden legacy inputs

The production parser does not consume:

- `outputs/current_service_baseline.csv`;
- `scripts/05_current_service.py`;
- `data/raw/gtfs/network_structural/`;
- `data/raw/gtfs/network_2026_emergency/`.

No synthetic current-service schedule is generated and no `np.random` is used.

## Current primary sources

The current timetable is reconstructed from the official Lecco Trasporti / Arriva Italia summer 2026 PDFs pinned and validated by Gate C. The parser downloads each source and refuses to continue if its SHA256 differs from Gate C.

| Route | Official source | Gate C SHA256 | Published columns | Active on 2026-09-03 |
| --- | --- | --- | ---: | ---: |
| D184 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d184.pdf` | `6d5246976d369a283ee5ec3f6a49481755cfce851dd81839ccca4588205dd6ea` | 12 | 12 |
| D185 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d185.pdf` | `31f2da4a8f6539bbb08da8b7ec08b8d4a475f38482f880d3d1206ef9fbd90c66` | 13 | 13 |
| D150 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d150.pdf` | `ee2707bdb4a2174008b6819e04b2f2a564e4bef5c2d6f8830e6dc9589f47349b` | 39 | 30 |
| D170 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d170.pdf` | `87ab0fe1f2c68a38f8e54fd911f0ef38c9b29a22b3d875e34e4209a1a922f63b` | 55 | 49 |

Total: **119 published timetable columns**, of which **104 are active on 2026-09-03** under the published calendar/day-note rules.

Epistemic status of the reconstructed timetable records: `RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE`.

## Reproducible PDF parser

`src/phase2_current_service_stop_timetable.py` and `scripts/phase2_build_current_service_stop_timetable.py` reconstruct the timetable from PDF coordinates rather than a manual transcription.

The parser:

1. verifies each PDF checksum against pinned Gate C evidence;
2. identifies the published route-direction page heading;
3. identifies timetable columns from the day-code header coordinates;
4. attaches note codes such as A, B, D and V by coordinate alignment;
5. identifies stop rows between the timetable header and source legend;
6. maps only explicit clock tokens to their timetable column by x-coordinate;
7. preserves blanks as blanks;
8. rejects ambiguous column, note, time or direction mappings;
9. validates monotonic published stop times, allowing a midnight rollover only when the clock sequence supports it;
10. checks the reconstructed route/active-column counts against Gate C.

The reference-date activation logic uses only source-demonstrable calendar semantics. It does **not** infer annual service days.

## Trip identity

The current PDFs do not expose a verified operator trip identifier for every timetable column. Therefore each column receives a stable reconstructed identity such as:

`PDF20260903:D184:P01:C01`

This is explicitly labelled:

`RECONSTRUCTED_TIMETABLE_COLUMN_ID_NOT_OPERATOR_TRIP_ID`

`operator_trip_id` remains blank.

The page direction heading is preserved as published but is not silently treated as the exact origin and destination of every individual timetable column. The actual first and last published timed stop labels are stored separately for each reconstructed column.

## Stop-level output

The production bundle contains **209 parsed PDF stop rows** and **1,145 explicit published stop-time records**, of which **990 are attached to columns active on 2026-09-03**.

Published stop-time records by route:

| Route | PDF stop rows | Published stop times | Active published stop times |
| --- | ---: | ---: | ---: |
| D184 | 24 | 118 | 118 |
| D185 | 27 | 114 | 114 |
| D150 | 55 | 512 | 397 |
| D170 | 103 | 401 | 361 |
| **Total** | **209** | **1,145** | **990** |

No unpublished stop time is interpolated.

## Complete stop × timetable-column matrix

A PDF timetable contains more semantic information than the subset of cells with a printed clock. To prevent blank cells from being silently converted into calls, skips or interpolated times, `src/phase2_current_service_matrix.py` materialises the complete stop-row × timetable-column universe.

The result contains **3,089 cells**:

| Cell state | Count | GJT use |
| --- | ---: | --- |
| `PUBLISHED_TIME` | 1,145 | exact scheduled-time evidence usable |
| `OUTSIDE_PUBLISHED_TIMED_SPAN` | 1,477 | not time-usable |
| `NO_PUBLISHED_TIME_WITHIN_COLUMN_SPAN` | 454 | not time-usable without further call/time evidence |
| `EXPLICITLY_SUSPENDED_STOP` | 13 | explicit D185 temporary suspension evidence |

A blank inside a timetable column is therefore **not** automatically interpreted as a served stop, a skipped stop or an interpolated time.

`unpublished_time_interpolation_used = false`.

## Temporary D185 condition

The D185 primary source explicitly documents the 2026 Brivio bridge condition. The Phase 2 reference records it separately as:

`D185_BRIVIO_BRIDGE_PONTE_CANTU_2026`

with:

- condition type `TEMPORARY_DEVIATION_AND_STOP_SUSPENSION`;
- known start `2026-05-04`;
- end `UNKNOWN_FROM_TIMETABLE_SOURCE`;
- active on the reference date;
- routing effect `SERVICES_USE_PONTE_CANTU`;
- stop effect `CISANO_SOSTA_SUSPENDED`.

This condition describes the **current reference-date service**, but it does not overwrite the ordinary structural-network baseline used for future topology design.

## Historical official GTFS cross-check

The committed official Arriva GTFS is valid only for the earlier timetable period and is **not** used to fill current PDF cells.

It is used as a structural cross-check on **2026-05-06**, reproducing the Gate C active-day counts:

| Route | Snapshot trips | Active trips | Snapshot stop patterns | Active stop patterns |
| --- | ---: | ---: | ---: | ---: |
| D184 | 15 | 15 | 8 | 8 |
| D185 | 27 | 19 | 10 | 9 |
| D150 | 41 | 33 | 33 | 28 |
| D170 | 118 | 96 | 57 | 49 |

The GTFS period and the current PDF period remain temporally distinct.

## Scheduled timetable versus observed runtime

Every published clock is an **official scheduled time**.

A scheduled runtime can be derived only as a difference between two published times in the same reconstructed timetable column.

The workstream does not possess observed AVL/real-time running-time evidence for these bus trips. Therefore:

- `scheduled_runtime = DERIVED_DIFFERENCE_OF_PUBLISHED_STOP_TIMES`;
- `observed_runtime = NOT_AVAILABLE_FROM_THIS_SOURCE`;
- observed runtime is never substituted with scheduled runtime under a different label.

## GJT handoff contract

This workstream makes the following scheduled current-service components available to a downstream GJT engine:

- route identity;
- stable reconstructed timetable-column identity;
- published page orientation;
- actual first/last published timed stop labels;
- published stop-row sequence;
- exact published stop times;
- reference-date activation of timetable columns;
- scheduled in-vehicle time between pairs of published timed stops;
- scheduled waiting opportunities derivable from explicit active published columns;
- explicit temporary D185 condition.

The following remain unavailable or require another evidence layer:

- verified operator trip IDs for the current PDF columns;
- exact call semantics for untimed cells unless a source note resolves them;
- observed runtime/reliability;
- walking access until PDF stop labels are deterministically joined to the official/spatial stop universe where labels are not unique;
- annual bus-km unless taken from a separate authoritative production source;
- passenger demand or mode share;
- unpublished headways or frequencies.

A downstream GJT implementation must fail closed whenever a requested OD movement requires an untimed or unresolved stop cell.

## Materialised outputs

The validated branch commits:

- `outputs/phase2/current_service_sources_2026-09-03.csv`;
- `outputs/phase2/current_service_trips_2026-09-03.csv`;
- `outputs/phase2/current_service_stop_times_2026-09-03.csv`;
- `outputs/phase2/current_service_stop_trip_matrix_2026-09-03.csv`;
- `outputs/phase2/current_service_pdf_stop_rows_2026-09-03.csv`;
- `outputs/phase2/current_service_temporary_conditions_2026-09-03.csv`;
- `outputs/phase2/current_service_stop_timetable_validation_2026-09-03.json`.

The CI rebuilds the bundle from the pinned primary sources and performs byte-for-byte comparison with these committed outputs. Any source, parser or output drift therefore fails closed instead of silently rewriting the baseline.

## Validation evidence

The materialisation run `33778193664`, job `100725076508`, completed successfully with **15/15 parser and adversarial tests PASS**, production-contract validation PASS, anti-shortcut guard PASS and artifact upload PASS.

That run produced artifact `9902465907`, digest:

`sha256:392357819db3050229c2fa993c0e69939d9af376a32012285a376119c99bad81`

The materialised-data commit is `3181cc019e06eb9f073c9729d6e6cf05f9e61901`.

This is a current-service **reference reconstruction**, not a recommendation and not a future-network scenario.
