# Phase 2 ASF C146 OTP stop-source discovery V4

## Verdict

The ASF OpenTripPlanner backend exposes a route-level stop endpoint for the current C146 route:

`https://transitpay.asfautolinee.it/otp/routers/default/index/routes/2:C_46/stops`

Parallel executors queried the endpoint and spatially filtered returned `lat`/`lon` points against `data/raw/boundaries/comuni_core_istat_2026.geojson`.

This materially upgrades the C146 source from timetable/schema-only evidence to a machine-readable official operator stop source with stable stop codes and coordinates.

## Temporal snapshots

Two reported extractions differ by one active route-stop record:

- earlier parallel extract: **39 coded ASF route-stop records** inside the exact ISTAT polygons;
- latest subagent extract: **38 coded ASF route-stop records**.

The difference is `BRIVIA06`, the A-side record for `Brivio - Via Como - Pensilina`, which was present in the earlier snapshot but absent in the latest endpoint result. `BRIVIR06` remains present.

This is consistent with ASF's official Brivio bridge-closure notice effective 4 May 2026: the `Brivio - Via Como - Pensilina` stop on the chimney side is unused and all C146 services use only the Via Vittorio Emanuele side in both directions during the closure. Therefore the 39-record extract must be retained as a source snapshot, but the latest 38-record extract is the better representation of the currently exposed active route-stop set.

Do not rewrite the historical snapshot as if it never existed.

## Latest extract summary

The latest reported five-municipality extract contains:

- **38 coded ASF route-stop records** inside the exact ISTAT polygons;
- 20 named stop places / stop-name groups if directional A/R records are grouped nominally;
- two currently unpaired route-stop records in the five-municipality extract: `CALCOA09` (Arlate - B.vio Brivio - Madonnina) and `BRIVIR06` (Brivio - Via Como - Pensilina);
- all other nominal ASF stop names in the extract have A/R-coded counterparts, but their geometries may be distinct.

These counts MUST NOT be described as physical boarding-point counts. A/R code pairs may be two distinct side-specific boarding points.

## Pairwise geometry findings from latest extraction

The latest subagent extraction compared A/R coordinates directly. Important examples:

- Rovagnate S.S. / Via Lombardia: ~77.7 m;
- Santa Maria Hoè Via Giovanni XXIII: ~47.5 m;
- Vaccarezza Cartello Paese: ~36.1 m;
- Perego Via Statale 79: ~27.5 m;
- Olgiate Scarpone: ~18.7 m;
- Alduno: ~17.8 m;
- Calco Via Garibaldi: ~11.7 m;
- Calco Largo Pomea: ~9.1 m;
- Rovagnate AGIP: ~7.8 m;
- Brivio Bar Cristallo: ~6.9 m;
- Via della Salute: ~3.4 m;
- Arlate Bivio per il Paese: ~1.1 m;
- Imbersago Cazzulino: 0.0 m in ASF geometry.

No proximity threshold authorises a boarding-point merge. Same-name A/R records remain separate source records, with boarding-point identity resolved independently.

## Important corrections

1. `CALCOA06` is officially `Calco - Largo Pomea`, not `Calco - Via Nazionale (edicola)`.
2. `CALCOA05` is `Calco - Via Garibaldi`.
3. `ROVAGA03` / `ROVAGR03` are `Rovagnate - Strada Statale - AGIP`.
4. `ROVAGA01` / `ROVAGR01` are `Rovagnate - S.S. - Ang. V. Lombardia`.
5. `SAMAHA04` / `SAMAHR04` are both named `Santa Maria Hoè - Via Giovanni XXIII` in ASF, but their geometries are ~47.5 m apart. Google Maps/Arriva evidence identifies the eastern geometry with `Tremonte / Via Leopardi`; therefore these cannot be collapsed into one physical boarding point solely from the ASF stop name.
6. `ROVAGAR4` is the current returned code spelling for the R-side Alduno record; do not silently regularise it to `ROVAGR04`.

## Boundary/name cases

Spatial polygon assignment and stop labels are separate dimensions:

- `Imbersago - Località Cazzulino` (`IMBERA07`, `IMBERR07`) is reported inside the Calco polygon despite the Imbersago name.
- `Rovagnate - Frazione Alduno` (`ROVAGA04`, `ROVAGAR4`) is reported inside the Santa Maria Hoè polygon despite the Rovagnate name.

Do not assign municipality from stop-name prefix.

## Google Maps targeted verification

Browser verification adds strong boarding-point evidence:

- Scagnello/Esselunga: two distinct Google Maps bus pins at approximately `45.7169153, 9.4082750` and `45.7168196, 9.4080556`;
- Alduno: two distinct Google Maps pins aligned respectively with the two Arriva/ASF sides;
- Santa Maria Hoè Via Giovanni XXIII and Tremonte/Via Leopardi: distinct pins ~47.5 m apart;
- Tremonte and Tremonte/Via Trento: distinct pins ~21 m apart;
- Arlate Bivio Brivio/Madonnina: one Google Maps pin observed, consistent with the single current ASF route-stop record `CALCOA09`;
- no Google Maps transit pin was observed in targeted high-zoom checks of San Zeno, Mondonico borgo or Calco Alta. This is corroborating absence evidence only, not proof that no physical or informal stop exists.

## Remaining C146 completeness blocker: route-stop endpoint vs observed trip patterns

A current Google Maps C146 trip operated by ASF explicitly showed intermediate stops including:

- `Calco - Via Virgilio`;
- `Calco - Via Nazionale (edicola)`;
- `Calco - Via Statale - Ang. Via Scagnello`;
- `Brivio - via Como (pizzeria)`.

These labels are not represented as such in the latest `routes/2:C_46/stops` extraction. Therefore the route-level `/stops` endpoint must **not yet** be treated as a proven exhaustive union of every current C146 trip pattern.

Possible explanations to test, not assume:

1. OTP route-level `/stops` exposes only a subset/current canonical pattern;
2. additional stop identities appear only through trip/pattern endpoints;
3. Google consumes a different or richer transit feed/source version;
4. some Google labels correspond to other ASF stop records under different official names, requiring code-level trip evidence.

The next deterministic task is to enumerate all C146 OTP patterns/trips and compare their stop sequences against the route-level `/stops` response and observed Google trip sequences.

## Required next step

Persist the raw ASF endpoint payloads with retrieval timestamp and SHA256, then build a deterministic comparison table containing:

- ASF code;
- ASF name;
- latitude / longitude;
- exact ISTAT polygon municipality;
- A/R counterpart code;
- pairwise A↔R distance;
- all C146 trip/pattern memberships;
- nearest Arriva/LineeLecco GTFS record and distance;
- nearest OSM boarding-point record and distance;
- identity status at `source_record`, `boarding_point`, and `stop_place` levels.

No merge is authorised from proximity alone.

## Provenance status

The machine-readable ASF coordinates in the latest table are recorded as `SUBAGENT_REPORTED_OFFICIAL_ASF_OTP` until the raw JSON dumps and hashes are committed into the repository. Google Maps observations are separate corroborating browser evidence and do not override operator stop codes or service membership.
