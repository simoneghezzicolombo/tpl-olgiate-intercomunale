# Phase 2 C146 stop-inventory closure V5

**Date:** 2026-09-05

## Closure verdict

`C146_STOP_SOURCE_AND_PATTERN_COMPLETENESS_RESOLVED`

The ASF OTP route `2:C_46` has been exhaustively checked at route and pattern/trip level.

- 16 operational patterns / 36 trips were enumerated by the parallel executor.
- The union of all pattern stop sequences contains 167 unique stops.
- `/routes/2:C_46/stops` also contains 167 unique stops.
- Set difference in either direction is zero.

Therefore the ASF route-level stop endpoint is accepted as the complete C146 stop universe for the observed current OTP snapshot.

## Resolved naming / identity cases

The following Google Maps / Arriva labels are aliases of ASF stop identities, not missing C146 stops:

- `Calco - Via Virgilio` = ASF `CALCOA05/CALCOR05`, canonical ASF name `Calco - Via Garibaldi`.
- `Calco - Via Nazionale (edicola)` / Arriva `via statale (edicola)` = ASF `CALCOA06/CALCOR06`, canonical ASF name `Calco - Largo Pomea`.
- `Calco - Via Statale/Via Scagnello (Esselunga)` = ASF `CALCOA04/CALCOR04`.
- `Brivio - via Como (pizzeria)` = ASF `BRIVIA03/BRIVIR03`, canonical ASF name `Brivio - Bar Cristallo`.
- `Santa Maria Hoè - Via Giovanni XXIII` and `Tremonte/Via Leopardi` are treated as one passenger stop place with two directional boarding points under ASF `SAMAHA04/SAMAHR04` and different map/operator side aliases.
- `Rovagnate - Frazione Alduno` is one passenger stop place with two directional boarding points `ROVAGA04/ROVAGAR4`; exact polygon municipality is Santa Maria Hoè despite the ASF name prefix.

## Boundary case: Scagnello

`CALCOA04/CALCOR04` are genuine C146 stops used in the relevant patterns. Their coordinates fall only a few metres outside the exact Calco ISTAT polygon on the Merate side.

They must therefore be retained in the project as an operational boundary/interchange context stop while `physical_municipality_exact` is assigned strictly from geometry. This validates the separate `analysis_context_role` contract.

## Brivio stop-place resolution

Two old records named `Brivio - capolinea` correspond to two distinct locations:

1. southern point around `45.741330, 9.445699`, manually identified as `Brivio - Via Bergamo (Scuola Materna)` and spatially coincident with old GTFS `300063`;
2. northern/central point around `45.74243, 9.44582-9.44590`, corresponding to `Brivio - Via V. Emanuele (Capolinea)` / current ASF `BRIVIR06` boarding area.

These must remain separate stop places / boarding areas.

For the Via Bergamo / Scuola Materna point, current route attribution is not required to close the physical-stop identity issue. Record:

`physical_stop_status = CONFIRMED`
`current_service_status = UNKNOWN`

until a current operator source resolves it.

## Google Maps stale pin

A further Google Maps pin observed beyond the resolved Via Virgilio pair has no current ASF/Arriva identity and is considered obsolete cartographic residue unless future official evidence says otherwise. It must not be added to the current master inventory.

## Remaining project work

This closure resolves the C146 source/pattern/alias investigation. It does **not** by itself certify the full multi-operator master inventory. Remaining work is integration of:

- current/future Arriva/LineeLecco evidence;
- special-service boarding points;
- exact municipality assignment;
- source record -> boarding point -> stop place conflation;
- current-stop coverage calculation.

No further manual C146 stop hunting is required unless a new contradiction appears.
