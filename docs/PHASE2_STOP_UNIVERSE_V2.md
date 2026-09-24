# Phase 2 — Stop Universe V2

## Status and purpose

`Stop Universe V2` is the first downstream workstream allowed after the validated Phase-2 building-population handoff.

Its purpose is to construct a topology-neutral universe of existing and proposed stop locations using the validated building-level population model, frozen walking network, frozen bus-eligible road network and validated analysis envelope. It does **not** choose a final network, rank stops, choose headways, alter the timetable or consume the service budget.

Every proposed point remains `PROPOSED_STOP/FIELD_CHECK_PENDING` and is an optimisation hypothesis, not a claim that a stop can physically be built there.

## Upstream evidence

The build consumes only versioned PASS evidence:

- Gate B walking graph and official GTFS stop records;
- Gate D frozen structural road network and official reference-period GTFS feeds;
- Phase-2 analysis envelope, primary rule `METRIC_GUARD_ONLY`;
- Phase-2 building-population artifact, validated HEAD `29203ad64c3e32e6164ef6997933eb5c5ff2d5b1`, artifact `9910900017`, ZIP SHA256 `4f5f0123ced2b763c2a063258ad724c43ac7f57ede707db3fa76e6a8977688b1`;
- ISTAT 2021 municipal work-commuting profile as context only;
- frozen OSM settlement/destination observations already present in the repository.

No live Overpass query is used.

## Population spatial unit

V1 used calibrated WorldPop cells. V2 replaces them with the validated dasymetric `BUILDING_SECTION_INTERSECTION` population units exported by the building-population workstream.

For the five-municipality decision core:

- POSAS 2025 population denominator: 22,914;
- population spatially located in building-section pieces: 22,820.83993743439;
- residual explicitly unlocated population: 93.16006256561045;
- population units: 4,348.

The residual population is retained in accounting but is never forced into a building, catchment or proposed stop. Consequently, accessibility percentages are reported both against the complete POSAS denominator and, where useful, against the spatially located model population.

Building resident estimates remain model outputs and are not observations of residents at individual addresses.

## Spatial scope

Population and equal-equity accounting remain restricted to the five-municipality `DECISION_CORE`:

- Brivio;
- Calco;
- Olgiate Molgora;
- Santa Maria Hoè;
- La Valletta Brianza.

Candidate discovery uses the validated `ANALYSIS_ENVELOPE` geometry and the inherited 150 m stop-siting buffer already used by the audited road-sampling routine. Context municipalities therefore prevent boundary artefacts without becoming equal members of the core equity denominator.

## Existing-stop universe

The Gate B core GTFS stop records remain authoritative sources inside the core. To avoid artificial accessibility gaps at the decision-core boundary, V2 also consumes official GTFS stop-cluster centroids already materialised inside the validated analysis envelope by the Gate D transfer layer.

These context centroids are not invented stops. They are labelled as reference-period official GTFS cluster evidence and are snapped deterministically to the frozen Gate B walking graph.

Existing-stop physical clustering retains the audited 40 m rule. Walking catchments use all snapped official records or official cluster centroids belonging to a physical cluster as multi-source seeds. A single representative stop record is not substituted when multiple valid access points exist.

## Candidate discovery

The discovery algorithm intentionally preserves the V1 structural contract so V1→V2 changes can be attributed to improved spatial evidence rather than a redesigned optimiser:

- bus-eligible road samples derive from the frozen Gate D road network;
- road sampling interval: 150 m;
- discovery seed radius: 800 m;
- uncovered population seeds: building-section pieces outside the 8-minute existing-stop catchment;
- uncovered settlement/destination observations may also seed discovery;
- deterministic spatial thinning: 140 m;
- proposed stops within 150 m walking-network distance of an existing official stop are removed;
- candidates without additional population, settlement or destination accessibility gain are removed;
- remaining candidates are compressed using the inherited 220 m spacing rule and 10-minute catchment Jaccard threshold 0.90 within 500 m.

Candidate order is deterministic spatial order only. It is not an attractiveness ranking.

## Accessibility

All principal accessibility calculations continue to use the frozen Gate B walking graph and the inherited connector-speed assumption. Thresholds remain 5, 8, 10 and 12 minutes.

Candidate and existing-stop catchments operate on building-section population units rather than V1 grid cells. The primary structural-optimiser catchment threshold remains 10 minutes, while all four thresholds remain reported for accessibility analysis.

## Epistemic safeguards

The V2 validation contract requires that:

- no WorldPop cell is used as the candidate-population spatial unit;
- no synthetic or random spatial input enters production;
- the 93.16-person residual is not geographically allocated;
- proposed stops are never promoted beyond `FIELD_CHECK_PENDING`;
- no final topology or network is selected;
- no stop ranking is produced;
- no headway, timetable or budget is changed;
- the existing V1 benchmark outputs remain untouched;
- all generated V2 outputs have SHA256 checksums.

## Downstream contract

A PASS Stop Universe V2 authorises construction of the **Reduced Path Matrix V2**. That matrix may use the V2 stop universe as its node/anchor set but must continue to route on the complete frozen Gate D graph rather than clipping routes to the analysis envelope.

Only after the Reduced Path Matrix V2 is independently validated may the 100,000-scenario structural catalog be regenerated or replayed for V2. No primary, runner-up or final network recommendation is authorised by this workstream.
