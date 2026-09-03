# Phase 2 current-service stop identity

## Purpose

The audited current-service timetable for 2026-09-03 is reconstructed from official primary operator PDFs. Those PDFs provide ordered stop labels and scheduled times but do not provide current GTFS stop IDs or coordinates.

This workstream creates a conservative bridge between those current PDF rows and official stop identities so the later current-service GJT calculation can join scheduled service to spatial walking-access evidence without inventing stop locations.

## Evidence hierarchy

1. Current operator PDF label and ordered row are the current-service evidence.
2. The official Arriva GTFS snapshot is used only as a validity-bounded historical identity and route-sequence cross-check.
3. Parallel GTFS records are treated as one physical-equivalence class only when their normalized official name and numeric coordinates are exactly identical. No distance tolerance is used.
4. A resolved historical GTFS identity is joined to Stop Universe V1 only through an exact GTFS ID present in that physical-equivalence class.
5. Stop Universe V2 may later refresh that exact-ID spatial join for stops outside V1.

Historical GTFS does not become evidence that a trip or stop is active on 2026-09-03. Current timetable activation and times remain those reconstructed from the official 2026 summer PDFs.

## Name matching

The resolver does not use edit distance, fuzzywuzzy, RapidFuzz, nearest-coordinate guessing or a route-specific manual stop alias table.

Normalization is limited to Unicode/case/punctuation handling and generic transit abbreviations such as `F.S.` and `P.zza`. A PDF label is compatible with a GTFS name only through deterministic token containment. Long tokens may match an unabbreviated suffix form, for example `CALOLZIO` and `CALOLZIOCORTE`; short prefix matching is forbidden.

A route-unique compatible physical GTFS identity can be resolved directly. Some records in the official aggregate GTFS occur under parallel namespaces while retaining the exact same official stop name and exact same coordinates. These are not treated as distinct physical locations merely because their record IDs differ. The output preserves the complete equivalence class of source IDs and chooses a stable representative, preferring an exact V1 stop ID when one is present.

If the compatible name still refers to multiple physical locations, the resolver compares ordered historical route patterns. Only a unique physical identity surviving the maximum-agreement ordered pattern set is resolved. Equal best patterns implying different physical locations remain `AMBIGUOUS_HISTORICAL_GTFS`.

No unresolved row is force-assigned for coverage statistics or GJT.

## Physical cluster join

A resolved physical equivalence is joined to `outputs/phase2/existing_official_stops.csv` only when at least one exact member `stop_id` exists there. Equivalent-source IDs must have the same official normalized name and exactly identical coordinates before such substitution is permitted.

The status `GTFS_IDENTIFIED_NOT_IN_V1_STOP_UNIVERSE` means precisely that V1 lacks a member of that resolved physical identity. It does not assert that the physical stop is absent.

This distinction is required because the V2 analysis envelope is broader than the original five-core Stop Universe V1.

## Outputs

- `outputs/phase2/current_service_stop_identity_2026-09-03.csv`
- `outputs/phase2/current_service_stop_times_with_identity_2026-09-03.csv`
- `outputs/phase2/current_service_stop_trip_matrix_with_identity_2026-09-03.csv`
- `outputs/phase2/current_service_stop_identity_validation.json`

The joined stop-time and stop-trip files preserve every original row. They add identity fields only and do not interpolate times or calls.

## GJT rule

Rows with a resolved GTFS physical identity may be joined to spatial evidence. Rows that remain ambiguous or unresolved cannot be assigned a walking-access origin/destination stop unless a later authoritative identity source resolves them.

A missing V1 physical cluster is not a missing stop. After Stop Universe V2 is available, the preserved GTFS-equivalence IDs can be rejoined to the broader physical stop universe without changing the timetable reconstruction or identity algorithm.
