# Phase 2 — Optimizer core contract

**Branch:** `phase2-optimizer-core`  
**Purpose:** provide the deterministic engine that will turn validated territorial evidence into a primary network recommendation and runner-up.

## 1. This is not an OD-matrix optimiser

The Phase 2 decision is not based on the ISTAT commuting matrix alone and does not assign arbitrary percentage weights to datasets.

The final design must combine separate evidence layers according to what each source can actually measure:

- **population and walking access:** where people live and how far they must walk to useful service;
- **official stops and existing network:** continuity, interchange opportunities and current-service baseline;
- **frozen Gate D road graph:** whether a bus can structurally route between candidate anchors and the resulting distance/runtime/uncertainty;
- **S8 timetable and station evidence:** connection quality, waiting, missed-connection risk and rail-feeder utility;
- **ISTAT 2021 work OD:** observed municipality-to-municipality work demand at the spatial resolution supported by the matrix;
- **schools and verified opportunity locations:** accessibility outcomes, without inventing passenger volumes where no empirical trip weights exist;
- **service production:** explicit calendar, frequency, span, fleet, recovery and annual bus-km;
- **equity:** municipal and settlement-level non-regression constraints, not a hidden score component.

No source is allowed to impersonate another. Population is not converted into invented trips, POIs are not assigned arbitrary passenger counts and `S8_DIRECT` is not treated as observed rail modal share.

## 2. Final-result pipeline

The intended end-to-end path is:

`validated evidence -> candidate anchors/stops -> reduced directed path matrix -> structural topology catalog -> service-policy catalog -> passenger utility -> hard eligibility -> robustness tournament -> budget frontier -> primary recommendation + runner-up`

The optimizer core implemented in `src/phase2_optimizer_core.py` owns the parts in the middle that should remain independent from individual data-acquisition workstreams.

### Structural generation

The generator receives a real hub, a real candidate-anchor universe and a validated directed path matrix. It never creates coordinates or path legs.

It can generate structural candidates across these Phase 2 families:

1. single compact loop;
2. two independent loops;
3. bidirectional loop pair;
4. interlined figure-8;
5. two radial out-and-back feeders;
6. multiple short radials;
7. trunk + branches;
8. short-turn overlay;
9. scheduled extensions;
10. hybrid/interlined service;
11. blank-slate closed structures.

Generation is deterministic. The same inputs produce the same candidate order and stable scenario IDs. No stochastic search is required for reproducibility. If the catalog becomes too large, later search stages can prune deterministically using hard feasibility and dominance rules before service optimisation.

### Service policy

Headway, span, recovery, fleet, annual calendar and extension share are not hidden constants. The caller supplies explicit candidate grids and the core enumerates them deterministically.

This allows the same geometry to compete under different service plans. A longer route is therefore not automatically worse and a short route is not automatically better: the effect appears through frequency, waiting, cycle feasibility, production and passenger utility.

## 3. Selection rule

The engine follows `PHASE2_SERVICE_DESIGN_SPEC.md`, section 11.

### A. Hard eligibility

A candidate cannot win unless all required constraints pass:

- road/routing integrity;
- annual production budget for that decision run;
- fleet/cycle feasibility;
- minimum recovery/reliability rule;
- valid evidence lineage;
- territorial non-regression unless explicitly waived by a declared policy decision.

An ineligible candidate is excluded even if its unconstrained passenger metric looks excellent.

### B. Robust passenger utility

Eligible candidates are evaluated over a declared sensitivity set. The core aggregates demand-weighted generalised-journey-time improvement across these runs and records both median performance and a lower-tail result.

The sensitivity engine is expected to vary at least walking/wait weights, runtime, dwell/recovery, connection delay and demand assumptions as required by the Phase 2 specification.

### C. Explicit tie-break, not composite weights

If the leading candidates are inside a declared uncertainty band, the winner is selected lexicographically in this order:

1. lower missed-connection risk;
2. simpler public-facing pattern;
3. lower annual bus-km;
4. fewer operationally unverified road/stop elements;
5. greater continuity with existing stops/corridors.

The uncertainty band itself must be declared in the decision run. The engine reports whether the tie-break was invoked.

## 4. Budget frontier

The core can evaluate the best eligible scenario below each declared annual bus-km envelope and calculate marginal passenger utility per additional 1,000 bus-km.

This is how the project will answer not only “which network is best around the current 111,419 bus-km/year reference?” but also:

- could a cheaper network retain almost the same utility?
- does +10% production produce a meaningful jump?
- where does the marginal benefit flatten?

The current validated production reference remains an input to a decision run, not a magic constant embedded in the engine.

## 5. Relationship with parallel Phase 2 workstreams

The core is intentionally merge-friendly.

- The **graph-freeze** workstream should supply the canonical directed Gate D graph and reduced path matrix.
- The **stop-universe** workstream should supply existing/proposed candidate anchors and access metrics.
- The **S8-interchange** workstream should supply timetable-event and transfer-quality functions.
- The **2011 OD audit** may add historical sensitivity but is not required to run the optimizer.
- The already materialised **2021 demand profile** remains one calibrated work-demand layer.

The optimizer must continue functioning if the historical OD comparison is unavailable.

## 6. What remains before the massive search

This branch does **not** yet claim to have found the final route. It establishes the reproducible decision machinery so that the search can begin immediately when the graph/path matrix and candidate-stop universe are merged.

Before the first full catalog run we still need:

1. canonical reduced path matrix from validated Gate D geometry;
2. candidate-stop/anchor universe with access metrics;
3. explicit operational policy grids for the first search pass;
4. passenger utility evaluator combining calibrated demand, walking, wait, IVT and S8 transfer quality;
5. baseline municipal non-regression metrics.

Once these are present, Phase 2 can generate the large structural catalog, optimise service policies, build the robust frontier and select the final recommendation under the already declared decision rule.
