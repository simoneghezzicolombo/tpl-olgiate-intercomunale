# Phase 2 ASF C146 OTP stop-source discovery V4

## Verdict

The ASF OpenTripPlanner backend exposes a machine-readable current C146 stop universe at:

`https://transitpay.asfautolinee.it/otp/routers/default/index/routes/2:C_46/stops`

A parallel executor subsequently enumerated all C146 patterns and trips. The route-level `/stops` response contains **167 unique stops**, and the union of the stop sequences used by all **16 operational patterns / 36 trips** also contains **167 unique stops**. The two sets are exactly equal: zero pattern stops are absent from the route-level endpoint and zero route-level stops are unused by all patterns.

Therefore the earlier completeness blocker is resolved: for the observed ASF OTP snapshot, `/routes/2:C_46/stops` is the exact union of all C146 pattern stops.

## Five-municipality exact polygon extract versus service context

The latest strict spatial extract contains **38 coded ASF C146 route-stop records inside the exact ISTAT polygons** of Olgiate Molgora, Calco, Brivio, La Valletta Brianza and Santa Maria Hoè.

This strict count is not the same as the operationally relevant boundary inventory. In particular:

- `CALCOA04` / `CALCOR04`, the two boarding points of `Calco - Via Statale - Ang. Scagnello` / Scagnello-Esselunga, are genuine C146 pattern stops but their coordinates fall only a few metres outside the Calco polygon on the Merate side;
- they must therefore have `physical_municipality_exact` assigned from geometry while retaining an `analysis_context_role` linking them to the Calco boundary/service corridor.

This demonstrates why exact municipality containment and analysis/service context must remain separate fields.

## Temporal/current-service asymmetry at Brivio

Two reported extractions differed by one route-stop record:

- an earlier snapshot contained 39 coded records inside the five polygons;
- the latest current snapshot contains 38.

The difference is `BRIVIA06`, the A-side record formerly associated with `Brivio - Via Como - Pensilina`. `BRIVIR06` remains current. This is consistent with ASF's bridge-closure operational notice effective 4 May 2026, during which the chimney-side stop is unused and current service is channelled through the central Brivio boarding area.

Historical snapshots must be retained as historical evidence rather than overwritten.

## Identity model confirmed by current evidence

The evidence now strongly supports the three-level contract:

1. `source_record_id`: operator/GTFS/Maps record;
2. `boarding_point_id`: side-specific physical pickup/alighting point;
3. `stop_place_id`: passenger-facing stop location that may contain multiple directional boarding points.

Same name, same code family or proximity does not authorise a boarding-point merge.

## Key operator-name versus Google/Arriva aliases

Pattern enumeration and manual Google Maps checks resolve several apparent discrepancies as naming aliases rather than missing stops:

- `CALCOA05` / `CALCOR05`: ASF canonical name `Calco - Via Garibaldi`; Google Maps and Arriva commonly expose `Calco - Via Virgilio`. One passenger stop place, two directional boarding points.
- `CALCOA06` / `CALCOR06`: ASF canonical name `Calco - Largo Pomea`; Google Maps/Arriva expose `Calco - Via Nazionale (edicola)` / `via statale (edicola)`. Same coded stop place, not an additional missing C146 stop.
- `CALCOA04` / `CALCOR04`: ASF `Calco - Via Statale - Ang. Scagnello`; Google Maps adds the Esselunga description. Two directional boarding points of one stop place, just outside the strict Calco polygon.
- `BRIVIA03` / `BRIVIR03`: ASF `Brivio - Bar Cristallo`; Google Maps/Arriva expose `Brivio - via Como (pizzeria)`. Same stop place under different landmarks.
- `OLGMOA04`: `Olgiate Molgora - Via Statale`; some interfaces may label the area ambiguously, but the geometry lies in Olgiate Molgora.

## Directional boarding-point geometry findings

Examples from official ASF coordinates and manual corroboration show why directional records must remain separate:

- Rovagnate S.S. / Via Lombardia: ASF A/R coordinates separated by ~77.7 m;
- Santa Maria Hoè Via Giovanni XXIII: ASF A/R coordinates separated by ~47.5 m; the eastern side is also labelled Tremonte/Via Leopardi by Google/Arriva;
- Vaccarezza: ~36.1 m;
- Perego Via Statale 79: ~27.5 m;
- Olgiate Scarpone: ~18.7 m;
- Calco Via Garibaldi / Via Virgilio: manual Google Maps boarding points ~27.9 m apart;
- Scagnello-Esselunga: manual Google Maps boarding points ~20.2 m apart;
- Alduno: one stop place with two directional boarding points; manual Maps pins are farther apart than the inward-shifted ASF coordinates but align to the respective sides;
- Imbersago Cazzulino: ASF gives identical geometry to the two directional codes, which means the source does not spatially distinguish sides there.

No universal distance threshold should convert source records into boarding-point identity.

## Santa Maria Hoè / Tremonte resolution

`SAMAHA04` and `SAMAHR04` share the ASF stop-place name `Santa Maria Hoè - Via Giovanni XXIII`, but their geometries are distinct. Manual Google Maps plus Arriva evidence supports interpreting them as opposite-direction boarding points of the same passenger stop place, with the eastern side also exposed as `Tremonte / Via Leopardi`.

Separate nearby stop places also exist around Tremonte / Via Trento. These must not be collapsed merely because they are spatially close.

A current manual Google Maps check did not identify a transit pin named `S. Maria Hoè - Centro`. This is absence evidence only and does not invalidate historical frozen GTFS records named `S.Maria Hoe' - paese`; those records remain a temporal/identity review item.

## Alduno boundary/name resolution

ASF uses `Rovagnate - Frazione Alduno` with codes `ROVAGA04` and `ROVAGAR4`, but geometry and local administrative reality place the stop in Santa Maria Hoè. The operator name must not drive municipality assignment.

Manual Google Maps checks confirm one Alduno passenger stop place with two directional boarding points.

## Brivio stop-place collision resolved

The frozen GTFS contained two distant locations carrying the same broad label `Brivio - capolinea`.

Manual map/street evidence resolves them as distinct places:

- the southern point around `45.741330, 9.445699` is `Brivio - Via Bergamo (Scuola Materna)` and matches frozen GTFS `300063` within about 0.3 m;
- the northern/central point around `45.74243, 9.44582-9.44590` corresponds to the current central Brivio / Via V. Emanuele boarding area and current `BRIVIR06` geometry.

They must remain separate stop places. The old identical GTFS naming was a naming collision, not evidence for grouping.

Current service membership of the Via Bergamo / Scuola Materna bay remains unresolved even though Street View shows bus infrastructure and ASF-related signage.

## No-stop locality checks

Targeted high-zoom Google Maps checks found no current transit pin in:

- San Zeno;
- Mondonico borgo;
- Calco Alta / Piazza San Vigilio.

The correct status is `NO_GOOGLE_MAPS_TRANSIT_PIN_OBSERVED`, not proof of absolute real-world absence. This can be combined with operator/GTFS evidence when evaluating current ordinary-service coverage.

## Provenance and next integration step

The parallel executor saved raw ASF route and pattern dumps locally. These should be committed or otherwise captured reproducibly with retrieval timestamp and SHA256 before final source freeze.

The master current-stop inventory should now integrate:

- all official Arriva/LineeLecco source records;
- the complete ASF C146 route-level stop universe and pattern memberships;
- exact ISTAT polygon municipality;
- separate analysis-context role;
- directional boarding-point identity;
- passenger stop-place identity;
- Google Maps/manual evidence only as corroborating identity/geometry evidence;
- temporal status for current versus historical/suspended records.

The C146 route-level completeness question is **RESOLVED**. Remaining work is cross-operator conflation and temporal/current-service classification, not discovery of hidden C146 pattern stops.
