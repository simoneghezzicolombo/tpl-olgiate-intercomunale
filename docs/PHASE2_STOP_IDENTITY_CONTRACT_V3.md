# Phase 2 stop identity contract V3

**Author:** GPT reviewer/co-developer  
**Date:** 2026-09-05  
**Branch:** `gpt-stop-source-completeness-v3`

## Purpose

A complete stop inventory must not equate source rows with physical passenger locations. GTFS, OSM and operator databases can each contain multiple records for the same place, while opposite sides of a road can be distinct boarding points belonging to one passenger-facing stop place.

The inventory therefore uses three identity levels.

## Level 1 — source record

`source_record_id`

One row exactly as represented by a source, for example:

- GTFS `stop_id=300407`
- GTFS `stop_id=L00407`
- OSM node `1847848087`
- OSM node `14006806495`
- ASF stop code such as `CALCOA04`

Source records are never counted directly as the number of passenger-facing stops.

## Level 2 — physical boarding point

`boarding_point_id`

A geographically distinct place where passengers actually board/alight, normally corresponding to one side of a road, one platform or one signed waiting point.

Rules:

1. opposite road sides remain separate boarding points when spatial evidence shows distinct passenger positions;
2. a GTFS stop-position and an OSM platform describing the same physical waiting location are one boarding point only after affirmative conflation evidence;
3. records cannot be merged solely because names, identifiers or coordinates are similar;
4. **no spatial threshold proves boarding-point identity**. Distances of 5, 10, 20 or 40 metres can all represent distinct directional poles, opposite road sides or nearby stopping positions;
5. proximity thresholds may be used only to generate candidate associations for review or candidate `stop_place_id` groupings;
6. operator A/R directional records default to distinct boarding-point candidates even when their coordinates are close. They may later be conflated only if physical or operator evidence proves that both directions use the same passenger boarding position;
7. a source coordinate known or strongly suspected to be wrong remains a source record linked to a coordinate-conflict case, not a new boarding point;
8. special-service boarding points, such as the Casa di Comunità shuttle point, retain their own boarding-point class and are not silently recoded as ordinary TPL infrastructure.

Affirmative evidence sufficient to propose a boarding-point conflation can include an explicit operator mapping, a shared stable physical-stop identifier, practically identical geometry combined with source-alias evidence, or manual physical/map verification that the records represent the same pole/platform. Name similarity or spatial proximity by itself is insufficient.

## Level 3 — stop place

`stop_place_id`

The passenger-facing location grouping one or more boarding points that function as the same named stop/interchange, for example:

- `Olgiate-Calco-Brivio FS`
- a two-sided road stop with one pole in each direction
- a terminal with multiple operator records referring to the same passenger location

A stop place can contain multiple boarding points and many source records. Stop-place grouping is deliberately less strict than boarding-point conflation: two opposite-side boarding points can belong to one stop place without ever becoming one boarding point.

## Legacy spatial clusters

Historical V3 `physical_cluster_id` values were produced with a 40 m spatial union rule. They remain useful provenance and candidate-neighbourhood information, but **must not be interpreted as authoritative boarding-point identity**. The master inventory preserves them as legacy cluster identifiers only.

Any downstream code that consumes those clusters must treat them as review/candidate groupings unless a separate identity decision upgrades the relationship.

## Counting contract

The project must report at least two distinct counts when completeness matters:

- `boarding_points_count`: physical passenger boarding positions;
- `stop_places_count`: passenger-facing stop locations.

It may additionally report `source_records_count`, but that value is provenance/debug information and must never be presented as the number of stops.

Strict municipality counts use exact ISTAT 2026 polygon containment of the boarding-point geometry. A stop place spanning a boundary must retain the municipalities of its member boarding points rather than receiving an arbitrary nearest municipality.

`PRO_COM_T` from the frozen routing/context universe is not accepted as strict municipality truth because that artifact deliberately includes external/context rows assigned to core analysis codes. The master layer therefore separates `physical_municipality_exact` from `analysis_context_role`.

## Routing boundary with Alpha

The master stop inventory is an **upstream neutral evidence layer**. A row appearing in the master does not make it a routing terminal, required stop or preferred stop.

The inventory must expose a separate field such as `routing_terminal_eligibility_status`, defaulting to `NOT_EVALUATED`. Alpha's routing/network-design workstream consumes only a later validated-terminal materialization produced under an explicit terminal-selection contract.

This prevents the invalid equivalence `source record = boarding point = stop place = routing terminal` and keeps stop completeness independent from topology search.

## Olgiate FS coordinate-conflict example

The frozen reference universe demonstrates why this contract is necessary.

- Arriva GTFS record `300407`, `Olgiate Molgora - stazione f.s.`, is at `45.733710, 9.405760`.
- LineeLecco GTFS record `L00407`, `Olgiate Molgora (stazione f.s.)`, is at `45.729170, 9.404410`.
- OSM node `1847848087`, `Olgiate Molgora FS - Piazza Repubblica`, carries `ref=300407` but is at `45.7291359, 9.4043941`.
- OSM node `14006806495`, same stop-place wording, is at `45.7291031, 9.4043680`.

The V3 matcher correctly refuses to confirm OSM `1847848087` against the geographically distant Arriva coordinate even though its OSM `ref` exactly equals `300407`. The same OSM evidence lies only metres from the LineeLecco record.

External station evidence also places the railway halt around `45°43'45\"N, 9°24'13\"E`, consistent with the LineeLecco/OSM location, while RFI confirms the current station is in the municipality of Olgiate Molgora.

Therefore the correct interpretation is a `SOURCE_COORDINATE_CONFLICT` affecting the Arriva source record, not two different passenger-facing stations.

## Operator-name conflict example: CALCOA06

Official ASF OTP identifies `CALCOA06` as `Calco - Largo Pomea`, while a user-transcribed Google Maps card associated the same claimed code with `Calco - Via Nazionale (edicola)` near frozen GTFS `300089`.

The geometries are close, but this does not prove that the records are the same boarding point. The correct state is `CODE_CANONICAL_NAME_CONFLICT_PHYSICAL_IDENTITY_UNRESOLVED`: preserve every source claim, prefer the operator source for canonical operator naming, and keep physical identity open until affirmative evidence resolves it.

## Beverate counterexample

The user-transcribed Google Maps point `Brivio - Beverate (paese)` is only about 5 m from frozen GTFS `300398`, but current ASF `Beverate - Cartello Paese` (`BRIVIA05`/`BRIVIR05`) lies about 388–392 m away from `300398`.

Therefore name similarity cannot justify a stop-place or boarding-point conflation between those two locations. The ASF Cartello Paese records and frozen/Maps Beverate Paese evidence remain distinct unless future operator evidence proves otherwise.

## Epistemic rules

- source record: `FACT_SOURCE_RECORD`
- confirmed boarding-point conflation: `DERIVED_CROSS_SOURCE_IDENTITY`
- stop-place grouping: `DERIVED_PASSENGER_LOCATION_IDENTITY`
- unresolved spatial/name case: `REVIEW_REQUIRED`
- suspected wrong source coordinate: `SOURCE_COORDINATE_CONFLICT`, never automatically corrected in the raw source
- operator/manual naming disagreement: `CODE_CANONICAL_NAME_CONFLICT_PHYSICAL_IDENTITY_UNRESOLVED`

No source record is deleted or silently rewritten. Corrections are represented in the processed identity layer with explicit provenance.
