# Phase 2 — Analysis envelope

## Status

Workstream: `phase2-analysis-envelope`
Baseline: `phase2-optimizer-core` @ `147ad941579eb7ef17a5a54c19a5f820e5a226d4`.

This workstream changes **no V1 PASS output**. It only adds a V2 spatial acquisition/context layer.

## Decision core versus analysis context

The `DECISION_CORE` remains exactly the five municipalities already defined by Phase 2:

- Brivio (`097010`)
- Calco (`097012`)
- Olgiate Molgora (`097058`)
- Santa Maria Hoè (`097074`)
- La Valletta Brianza (`097092`)

External territory is `CONTEXT`, not an automatic enlargement of the political or equity constituency. A resident outside the core does not receive an equal municipal equity obligation merely because their building, stop or walking catchment lies inside the analysis envelope.

## Reproducible rule

Three topology-neutral rules are compared from official ISTAT municipal geometries:

1. `METRIC_GUARD_ONLY`: union of the five core municipalities plus the inherited V1 edge guard.
2. `ADJACENCY_1_PLUS_V1_WALK_GUARD`: union of the core and every municipality whose official geometry is first-order adjacent to the core, then the inherited V1 edge guard.
3. `ADJACENCY_2_PLUS_V1_WALK_GUARD_SENSITIVITY`: the same construction extended to the second adjacency ring, used only as a sensitivity comparison.

No external municipality name is whitelisted in production code. Adjacency is derived spatially with a 5 m topology tolerance to avoid tiny geometry-gap artefacts.

The primary rule is selected mechanically after comparison: choose the **largest nested tested rule** that fully contains the inherited V1 core walk+snap guard and remains fully supported by the frozen Gate D source bbox with the 250 m graph probe. Its epistemic state is `ASSUMPTION_RULE_EXPLICIT_AND_TOPOLOGY_NEUTRAL`, not FACT. Wider rules that fail source support remain published sensitivity geometries instead of being clipped or silently accepted.

The first CI red-team was useful: the full first-order municipal shell plus guard exceeded the frozen Gate D source bbox and was therefore rejected. This is an edge-effect finding, not a reason to expand or shrink the frozen road epoch silently. The audited primary rule is therefore `METRIC_GUARD_ONLY` unless a future explicitly versioned road epoch makes a wider tested rule source-complete.

## Edge guard

The outer metric guard is not an arbitrary round buffer. It is derived mechanically from the already validated V1 accessibility contract:

`12 min × (4.8 km/h × 1000 / 60) + 250 m snap cap = 1,210 m`.

The 4.8 km/h connector speed is itself an inherited V1 model assumption, therefore the 1,210 m guard is labelled `DERIVED_FROM_V1_ACCESSIBILITY_ASSUMPTION_CONTRACT`.

A second 1,210 m `SOURCE_ACQUISITION_GUARD` is stored outside the selected analysis geometry. It exists only to acquire complete source features around the outer boundary. It is not a population denominator, service area or equity constituency.

## Source layers

Primary external sources are frozen after first successful acquisition:

- ISTAT non-generalised municipal boundaries, 1 January 2026;
- ISTAT Lombardia census sections 2021 (`R03_21.zip`), retaining `POP21` and `EDI21` when exposed by the official source;
- Regione Lombardia DBGT, Tema Edificato, class `EDIFC_CR_EDF_ME`, official building-footprint polygons, CC BY 4.0.

Roads are not refreshed from live OSM. The workstream consumes the already frozen Gate D epoch `gate-d-2026-09-03-834d5caa0bfd`. Stops/anchors likewise come from the frozen Phase 2 Gate D transfer layer. This prevents the analysis envelope from silently creating a second road-network epoch.

The first acquisition writes deterministic compressed source snapshots under `data/phase2/analysis_envelope/source/`, with upstream ZIP/query provenance and SHA256 checksums. Subsequent CI builds are source-closed and must reproduce from those committed snapshots.

## Entity inventory

The selected envelope materialises separate inventories for:

- municipalities and `CORE`/`CONTEXT` role;
- census sections, without area-prorating official `POP21` at the outer boundary;
- DBGT building footprints and building centroids;
- frozen Gate D road edges;
- official GTFS bus stops, the rail anchor and any inherited Gate D design anchors, preserving their original epistemic status.

Buildings and sections intersecting the acquisition guard remain available in the frozen source bundle so the next building-population model can clip without a source hole at the analysis boundary.

The analysis envelope is not a routing clip. Later route/path calculations continue to use the complete frozen Gate D graph. The envelope controls spatial evidence acquisition and population/building accounting, which prevents administrative-boundary truncation without artificially forcing every route to remain inside a buffer polygon.

## Edge-effect audit

PASS requires all of the following:

- the selected rule contains the full core plus its 1,210 m V1 guard;
- wider first-order and second-order municipal rules remain explicitly reported as sensitivities, including whether the frozen road epoch can fully support them;
- the selected envelope plus a 250 m graph probe remains inside the frozen Gate D source bbox;
- municipalities, sections, buildings, roads and stops are all non-empty and source-labelled;
- all frozen-source checksums reconcile;
- output checksums reconcile;
- no `np.random`, synthetic coordinates/data, external-municipality whitelist, topology selection, final-stop selection or headway selection;
- protected V1 outputs remain byte-for-byte untouched relative to baseline.

## Downstream contract

The next building-population workstream should use:

- `outputs/phase2/analysis_envelope/analysis_envelope.geojson`, feature `ANALYSIS_ENVELOPE`, as the analytical cutline;
- its `SOURCE_ACQUISITION_GUARD` feature as the acquisition cutline;
- `data/phase2/analysis_envelope/source/census_sections_context.geojson.gz` and `dbgt_buildings_context.geojson.gz` as frozen source inputs;
- `outputs/phase2/analysis_envelope/source_cutline_contract.json` for machine-readable clipping semantics.

It must keep `CORE` and `CONTEXT` population accounting separate and must not silently promote external context population into the five-municipality equity denominator.
