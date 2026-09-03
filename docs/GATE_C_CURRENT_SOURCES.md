# Gate C — current-period source acquisition

**Workstream:** `gate-c-workstream`
**Acquisition date:** 2026-09-03
**Purpose:** reduce Gate C temporal blockers independently of Gate B. No spatial snapping, catchment or territorial inference is performed here.

## 1. Current bus timetables: FACT primary sources

Lecco Trasporti / Arriva publish current summer timetable PDFs for all four core routes. Each source below explicitly states validity from **9 June 2026 to 13 September 2026**, therefore 2026-09-03 is inside the declared validity interval.

| Route | Primary source | Declared validity | Status |
|---|---|---|---|
| D184 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d184.pdf` | 2026-06-09 → 2026-09-13 | `FACT_CURRENT_PRIMARY_TIMETABLE` |
| D185 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d185.pdf` | 2026-06-09 → 2026-09-13 | `FACT_CURRENT_PRIMARY_TIMETABLE` |
| D150 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d150.pdf` | 2026-06-09 → 2026-09-13 | `FACT_CURRENT_PRIMARY_TIMETABLE` |
| D170 | `https://www.leccotrasporti.it/percorsi/estivo/linea-d170.pdf` | 2026-06-09 → 2026-09-13 | `FACT_CURRENT_PRIMARY_TIMETABLE` |

These PDFs are admissible evidence for current-period timetable facts. They are **not** silently converted into GTFS and do not repair the stale GTFS snapshot in `data/raw/gtfs/agency_arriva`. Any machine-readable table reconstructed from the PDFs must be explicitly labelled `RECONSTRUCTED_FROM_PRIMARY_TIMETABLE`, with provenance down to source PDF and page/table.

### D184 current-period notes

The official timetable is edition 9 June 2026. It identifies D184 as `OLGIATE MOLGORA → RAVELLINO` / reverse and marks trips with note `A` as suspended from 27 July to 30 August. Because the audit date is 3 September 2026, that temporary summer suspension has ended.

### D185 current-period notes

The official timetable is edition 9 June 2026. It explicitly states that from 4 May 2026, because of works on the Brivio bridge, buses run via Ponte Cantù and `CISANO Sosta` is suspended. This confirms that the deviation is source-grounded current service, not the legacy project's manually generated `+25 min` emergency network.

### D150 current-period notes

The official timetable is current for 3 September 2026. Notes distinguish regular FER services and summer-period exceptions, including trips suspended from 27 July to 30 August and trips running only in that interval. These rules must be applied trip by trip; they cannot be represented by a single hard-coded headway.

### D170 current-period notes

The official timetable is current for 3 September 2026. It includes summer-period notes analogous to D150 and route-specific day-of-week rules. Again, current service must be derived from the timetable's own service annotations rather than legacy constants.

## 2. Current Trenord GTFS: official source identified

Regione Lombardia publishes Trenord's regional railway timetable as GTFS at dataset `3z4k-mxz9`:

- dataset page: `https://www.dati.lombardia.it/Mobilit-e-trasporti/Orario-Ferroviario-Regionale-Gtfs/3z4k-mxz9`
- current static GTFS producer URL: `https://www.dati.lombardia.it/download/3z4k-mxz9/application/zip`

Regione Lombardia's service documentation explicitly identifies this dataset as the GTFS publication of regional railway timetables supplied by Trenord.

Independent feed catalogs were used only as verification aids, not as the primary source. Transitland reports a successful fetch from the Regione Lombardia producer URL on 2026-08-26 and an active feed version with SHA1 `49744f28979449039012992da17c758463ab4de2`, with scheduled service from **2026-07-26 to 2026-12-12**. MobilityDatabase independently reports the same official producer URL and the same 2026-07-26 → 2026-12-12 service range.

This changes the interpretation of Finding C-06: the **repository snapshot** `data/raw/gtfs/rail_trenord` is incomplete because it lacks the service calendar, but a current official upstream GTFS exists and covers 2026-09-03. The blocker is therefore now `SOURCE_IDENTIFIED_INGEST_PENDING`, not `SOURCE_UNAVAILABLE`.

## 3. Current S8 context

Trenord states that the railway timetable currently in force is the timetable valid from **14 June 2026**. The S8 line page confirms the route `Lecco - Carnate - Milano P.ta Garibaldi` and includes `Olgiate-Calco-Brivio` among its stations.

RFI/Trenord also publish temporary infrastructure notices separately. This is important because Gate C must distinguish the ordinary timetable from temporary operational changes rather than bake temporary modifications into the base schedule. For example, works on 21-23 and 28-30 August 2026 caused cancellations between Carnate and Lecco, but that disruption had ended before the 3 September audit date. A separate RFI notice valid from 29 August to 9 October 2026 documents specific train modifications related to works in the Milan node; these must be handled as dated exceptions, not as a replacement base timetable.

## 4. What is now independent of Gate B

The following Gate C tasks can be completed while Gate B is still validating spatial inputs:

1. ingest the current Regione Lombardia / Trenord GTFS into an isolated current-period snapshot and resolve S8 service dates from the actual feed calendar;
2. parse and validate D184/D185/D150/D170 current timetable PDFs into source-traceable structured tables, labelled `RECONSTRUCTED_FROM_PRIMARY_TIMETABLE` rather than GTFS;
3. compare current summer PDFs against the older official GTFS snapshot to identify real service changes without inventing missing trips;
4. quarantine downstream legacy transit consumers that still rely on hard-coded timetable constants;
5. build tests for service-day rules, temporary deviations and timetable source provenance.

Gate B is still required only when Gate C output is combined with geographic snapping, catchments, walk access, municipal coverage or other spatial metrics.

## 5. Remaining Gate C blocker after this acquisition

The principal unresolved bus-side issue is narrower than before: the Agency TPL Open Data page still exposes its GTFS section as `orario invernale ed estivo 2025-2026`; no official 2026-2027 bus GTFS was found on that page on 2026-09-03. Current bus service is nevertheless directly evidenced by the four official operator timetable PDFs above.

Therefore, source acquisition can proceed now without Gate B, but Gate C should remain `PROVISIONAL` until the current Trenord feed is actually ingested/tested and the methodology decides whether current bus PDFs plus the older structural GTFS are sufficient for PASS or whether a current official bus GTFS remains a mandatory criterion.
