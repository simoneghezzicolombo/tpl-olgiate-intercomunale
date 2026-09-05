# Phase 2 ASF C146 OTP stop-source discovery V4

## Verdict

The ASF OpenTripPlanner backend exposes a route-level stop endpoint for the current C146 route:

`https://transitpay.asfautolinee.it/otp/routers/default/index/routes/2:C_46/stops`

A parallel executor queried the endpoint and spatially filtered returned `lat`/`lon` points against `data/raw/boundaries/comuni_core_istat_2026.geojson`.

This materially upgrades the C146 source from timetable/schema-only evidence to a machine-readable official operator stop source with stable stop codes and coordinates.

## Current extract summary

The reported five-municipality extract contains:

- 39 coded ASF route-stop records inside the exact ISTAT polygons;
- 20 distinct normalized stop names / nominal stop places;
- municipality-record counts: Olgiate Molgora 6, Calco 11, Brivio 8, La Valletta Brianza 6, Santa Maria Hoè 8;
- all nominal stop places appear as A/R code pairs except `Arlate - B.vio Brivio - Madonnina`, for which only `CALCOA09` appears in the polygon-filtered extract.

These counts MUST NOT be described as 20 physical boarding points. A/R code pairs may be two distinct side-specific boarding points. Until coordinates are compared pairwise, the defensible statement is **39 coded ASF stop records representing 20 named stop places**.

## Important corrections

1. `CALCOA06` is officially `Calco - Largo Pomea`, not `Calco - Via Nazionale (edicola)`. A previous manual Google Maps association is invalidated.
2. `CALCOA05` is `Calco - Via Garibaldi`.
3. `ROVAGA03` / `ROVAGR03` are `Rovagnate - Strada Statale - AGIP`.
4. `ROVAGA01` / `ROVAGR01` are `Rovagnate - S.S. - Ang. V. Lombardia`.
5. `SAMAHA04` / `SAMAHR04` are `Santa Maria Hoè - Via Giovanni XXIII`.

## Boundary/name cases

Spatial polygon assignment and stop labels are separate dimensions:

- `Imbersago - Località Cazzulino` (`IMBERA07`, `IMBERR07`) was reported inside the Calco polygon despite the Imbersago name.
- `Rovagnate - Frazione Alduno` (`ROVAGA04`, `ROVAGAR4`) was reported inside the Santa Maria Hoè polygon despite the Rovagnate name.

Do not assign municipality from stop-name prefix.

## Required next step

The parallel executor should persist the raw ASF endpoint payload, including `name`, `code`, `lat`, `lon`, with retrieval timestamp and SHA256, then build a deterministic comparison table containing:

- ASF code;
- ASF name;
- latitude / longitude;
- exact ISTAT polygon municipality;
- A/R counterpart code;
- pairwise A↔R distance;
- nearest Arriva/LineeLecco GTFS record and distance;
- nearest OSM boarding-point record and distance;
- identity status at `source_record`, `boarding_point`, and `stop_place` levels.

No merge is authorised from proximity alone.

## Provenance status

The complete endpoint extract in `asf_c146_otp_route_stops_parallel_extract_v4.csv` is recorded as `OFFICIAL_ASF_OTP_EXTRACT_REPORTED_BY_PARALLEL_EXECUTOR` because the GPT web environment could not independently fetch the endpoint payload during this audit. Independent current web indexing corroborates several critical code/name pairs, including CALCOA06 = Largo Pomea, CALCOA05 = Via Garibaldi and ROVAGA03 = Rovagnate Statale (AGIP).
