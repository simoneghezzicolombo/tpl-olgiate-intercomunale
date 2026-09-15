# Phase 2 — Current-Service Baseline V4

## Purpose

V4 replaces the old conceptual assumption that the 51 D184/D185 timetable rows are the physical stop universe.

The V4 unit is:

`official public GTFS/KML physical stop universe + explicit activation semantics`

This is the last circumscribed evidence improvement before the V3 Decision Packet update and finalizer. It does not rerun Stage C, D, E or F and it does not select PRIMARY or RUNNER-UP.

## Reference date and structural-comparison policy

Project reference date: **2026-09-04**.

The official Arriva timetable page valid through 2026-09-13 is used only to establish that D184 and D185 are current routes in the reference window.

The official 2025/26 Agenzia TPL Como-Lecco-Varese / Arriva Italia + Addabus GTFS is used for official stop IDs, stop names, coordinates, D184/D185 route membership, stop sequences and historical ordinary trip patterns.

It is **not** used to claim that each historical trip or each intermediate stop is independently confirmed as operating on 2026-09-04.

### D185 and the temporary Brivio bridge closure

By explicit project policy, the temporary Ponte di Brivio diversion is **excluded from the structural baseline** used for the network comparison.

The closure and its temporary stop suppressions are nevertheless retained in provenance as a real 2026 disruption. V4 therefore does not describe the D185 ordinary stop universe as a literal operational snapshot of 2026-09-04.

The D185 structural baseline role is:

`HISTORICAL_ORDINARY_NETWORK_STRUCTURE_NOT_2026_09_04_STOP_LEVEL_OPERATIONAL_SNAPSHOT`

The overall V4 semantics are:

`OFFICIAL_PHYSICAL_STOP_UNIVERSE_WITH_ROUTE_LEVEL_CURRENT_ACTIVATION_AND_D185_ORDINARY_STRUCTURAL_BASELINE_TEMPORARY_DISRUPTION_EXCLUDED`

This makes the comparison suitable for long-lived network design without silently converting a temporary works diversion into the permanent baseline.

The Arriva 2026/27 page, valid from 2026-09-14, is only `FUTURE_2026_09_14_CONTINUITY_CORROBORATION_ONLY`.

## Official source provenance

The CI downloads source material directly at run time and persists the official source URL, retrieval timestamp UTC, downloaded filename, SHA256, epistemic role, required/optional status and acquisition outcome.

Required sources:

1. official Agenzia TPL GTFS winter 2025/26, Arriva Italia + Addabus;
2. Arriva current timetable page whose validity window contains 2026-09-04;
3. official Agenzia TPL notice documenting the temporary Brivio bridge disruption.

Optional corroboration:

- Arriva 2026/27 timetable page;
- official D184 KML;
- official D185 KML.

A KML download failure does not block V4 when the GTFS and timetable evidence are sufficient. The validation records `kml_source_official=false` in that case.

## Physical stop clustering

Directional stop records are always preserved.

A stop record may enter the same `physical_stop_cluster_id` as another only through this deterministic hierarchy:

1. exact `stop_id` membership in the already certified frozen Phase 2 physical cluster universe;
2. outside that frozen universe, explicit `300xxx` / `L00xxx` suffix equivalence plus exact conservatively-normalised official stop name plus coordinate compatibility within 100 m;
3. otherwise a singleton official-GTFS physical cluster.

There is no free nearest-neighbour clustering, no edit-distance/fuzzy matching and no proximity-only merge.

A representative cluster coordinate is never fabricated. The cluster table retains one original official member stop as its representative and retains all member stop IDs and coordinates.

## Walking catchment

V4 does not build a new walking graph.

It reuses the frozen Phase 2 stop catchments from `stop_universe_v2` and the same building-section-intersection population units, population weights, walking graph epoch, walking-speed semantics and 5, 8, 10 and 12 minute thresholds.

Official D184/D185 physical clusters that do not already have certified Phase 2 catchment evidence stay in the physical stop universe but do **not** receive an invented catchment.

For this reason `current_service_baseline_complete=false` remains mandatory even if all GTFS stop records have official coordinates.

## Olgiate Molgora diagnostic

The diagnostic reports, where supported by already certified settlement anchors, Centro/Stazione, Mondonico, San Zeno and Monticello.

It identifies named D184/D185 physical-stop support and reports Olgiate municipality-wide V4 coverage.

It does not create new anchor-to-stop routing results. If the frozen settlement file contains an older `current_walk_min`, that value is exposed only as an explicitly labelled **all-existing-service context**, not as D184/D185-specific walking access.

If San Zeno has no certified settlement anchor in the frozen lineage, it remains unresolved rather than being geocoded ad hoc.

The diagnostic is reporting only and `used_in_candidate_optimisation=false`.

## V3 to V4 interpretation

V3 is still preserved as a valid **localisable lower bound** over PDF timing rows.

V4 changes the unit of analysis, so its success is not measured as `51/51 localized`.

The relevant V4 questions are instead how many official D184/D185 directional stop records and unique stop IDs exist, how many deterministic physical clusters they form, how many of those clusters have certified Phase 2 walking catchments, what 5/8/10/12-minute coverage follows and what remains unresolved because catchment or activation evidence is not granular enough.

## Decision impact

V4 does not reopen the tournament by itself.

If it passes without a certified lineage contradiction, it is a `CASE_A_BASELINE_ENRICHMENT_ONLY_PRE_FINALIZER` input for the Decision Packet/reporting layer.

`DECISION_GATE_REOPEN_REQUIRED` is reserved for an actual certified contradiction or hard-safeguard violation. Because V4 does not select PRIMARY or RUNNER-UP, it cannot by itself manufacture such a violation.

The comparison interface is materialised with blank PRIMARY/RUNNER-UP columns for later use by the authorized finalizer.

## Outputs

`outputs/phase2/current_service_access_baseline_v4/` contains:

- `current_service_directional_stops_v4.csv`
- `current_service_physical_stop_clusters_v4.csv`
- `current_service_access_by_population_unit_v4.csv.gz`
- `current_service_access_by_municipality_v4.csv`
- `current_service_olgiate_diagnostic_v4.csv`
- `current_service_v3_v4_comparison.csv`
- `current_service_candidate_comparison_interface_v4.csv`
- `current_service_v4_source_provenance.csv`
- `current_service_access_baseline_v4_validation.json`
