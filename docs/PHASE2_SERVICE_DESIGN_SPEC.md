# Phase 2 — Massive service-design optimisation specification

**Status:** implementation specification  
**Branch:** `phase2-service-design`  
**Upstream state:** Gates A–F PASS. Phase 2 is a new design/optimisation phase, not a repair of the audit gates.  
**Normative reference:** `docs/PHASE2_TRANSIT_BEST_PRACTICES.md`

## 1. Decision question

Phase 2 must answer one concrete question:

> **Given the real road network, population, existing transit, S8 timetable and realistic operating resources, what bus network centred on Olgiate-Calco-Brivio FS maximises practical passenger utility and is robust enough to recommend for further design?**

The answer must not be restricted to the four paired Gate E hypotheses. Those are valid seed designs, not finalists selected by evidence.

Phase 2 must finish with:

1. **one primary recommended design**;
2. **one runner-up**;
3. a quantified explanation of why the primary design is preferred;
4. a budget/utility frontier showing what is lost if production is reduced and what is gained if production is increased;
5. explicit remaining field checks before operational implementation.

A final answer of only “it depends” is not sufficient. If several alternatives are statistically/behaviourally indistinguishable, apply the tie-break rules in section 11.

## 2. Frozen validated upstream inputs

Phase 2 must reuse the validated A–F evidence and must not silently regenerate invalidated legacy data.

### Spatial/demand base

- Gate B population grid and walking graph.
- Gate B official municipal boundaries and demographic validation.
- Existing official bus stops from validated GTFS sources.

### Transit and railway

- Gate C current/reference bus evidence according to its epistemic contract.
- Gate C official Trenord S8 timetable/station evidence for `S01514 Olgiate-Calco-Brivio`.

### Road network

- Gate D validated structural OSM snapshot/graph and routing semantics.
- Gate D field-check flags and structural constraints.
- **No routine live Overpass calls in scenario generation or optimisation CI.**

The Gate D PASS computational snapshot is the canonical road-network epoch for Phase 2. Phase 2 may later provide an explicit refresh command, but a refresh creates a new network epoch and requires comparison/revalidation before replacing the canonical graph.

### Service production

- Gate E validated route/cycle mathematics.
- Primary current production reference: **111,419 bus-km/year** for D184+D185.
- Gate E service-math semantics for directional headway, fleet and cycle time.

### Decision/audit machinery

- Gate F bridges and epistemic controls may be reused where useful.
- Gate F’s four paired hypotheses and five unpaired candidates become **seed scenarios**, not the complete search space.

## 3. New demand evidence to acquire

Phase 2 should add verified demand evidence rather than use the INVALIDATED legacy OD matrix.

### Mandatory new source: ISTAT 2021 commuting matrix

ISTAT published the 2021 municipal origin-destination commuting matrix for work in October 2025. It provides observed/estimated daily work flows between municipalities and is suitable for identifying external destinations and functional mobility relationships.

Official source:
- https://www.istat.it/notizia/matrice-di-pendolarismo-per-lavoro/
- https://www.istat.it/notizia/matrici-di-contiguita-distanza-e-pendolarismo/

This input must receive manifest metadata and checksum like other project sources.

### Study travel

ISTAT’s 2021 work matrix does not by itself provide a complete student OD matrix. School-related demand must therefore remain separately identified and must use verified school locations and any official study-flow source that can be obtained. Do not infer a precise student OD matrix from population alone.

### Non-commute trips

Health, shopping, municipal-service and leisure destinations may enter accessibility analysis as verified opportunity locations, but they must not receive arbitrary demand volumes. Where no empirical trip weights exist, report accessibility to those opportunities separately from the calibrated work/S8 utility objective.

## 4. OSM computational strategy: freeze once, route many

Gate D demonstrated that repeated live OSM acquisition is slow and fragile. Phase 2 therefore uses a two-level graph architecture.

### Level 1 — canonical exact graph

Persist the Gate D PASS bus-eligible directed graph locally with:

- node/edge IDs;
- metric lengths;
- directionality;
- bus/psv/vehicle access semantics;
- turn-restriction context supported by Gate D;
- structural uncertainty flags;
- source snapshot SHA256.

### Level 2 — optimisation transfer graph

Create a reduced graph whose important nodes are candidate stops, settlement anchors, the railway station and major verified destinations.

Precompute shortest-path distance/time between relevant node pairs once. This avoids running full-graph Dijkstra for every leg in every candidate scenario.

Workflow:

`Gate D exact graph → candidate nodes → precomputed path matrix → massive search → exact re-route of finalists`

Full exact routing is rerun only for the shortlist/finalists and for any candidate containing a previously unseen node sequence.

## 5. Candidate-stop universe

Existing stops are a **prior**, not a hard boundary.

### 5.1 Existing stops

All spatially valid official GTFS stops on or near the Phase 2 road graph are candidate stops. Record whether each is currently served by D184, D185 or another route.

### 5.2 New-stop generation

Generate possible new stop locations algorithmically from the bus-eligible graph. Candidate points should be created where at least one of the following applies:

- meaningful population exists outside current walking catchments;
- a settlement/frazione has a documented accessibility gap;
- a verified major destination is poorly served;
- a route already passes the location and a stop can materially improve network utility.

The generator should sample the graph densely enough to discover useful gaps, then prune candidates using walking-network overlap and stop-spacing logic.

New stops are always labelled `PROPOSED_STOP/FIELD_CHECK_PENDING` until physical safety and placement are verified.

### 5.3 Stop optimisation

The search may:

- retain an existing stop;
- omit a redundant stop;
- add a proposed stop;
- move a stop only as an explicitly new proposed location, never by silently editing official GTFS coordinates.

Every omitted existing stop must have a quantified access impact.

## 6. Topology search space

The optimiser must generate a large, diverse scenario universe. Required topology families include at least:

1. **single compact loop**;
2. **two independent loops**;
3. **bidirectional loop pair**;
4. **interlined double-loop / figure-8**;
5. **two radial out-and-back feeders**;
6. **multiple short radial feeders meeting at FS**;
7. **trunk + branches**;
8. **short-turn overlay**, where central sections run more often than outer sections;
9. **scheduled extensions**, where Ravellino/Calco Superiore/other outer areas are served on selected trips rather than every cycle;
10. **hybrid/interlined services**, where a vehicle changes public-facing route at FS without forcing passengers through a single giant loop;
11. **blank-slate generated topologies** not derived from D184/D185 or the original FIG8 concept.

The Gate D/E hypotheses must be injected as named seeds so the optimiser can prove whether generated alternatives improve on them.

## 7. Massive search strategy

Do not brute-force every permutation of road nodes. Use staged search.

### Stage A — structural generation

Generate a very large number of unique route skeletons from candidate stops/anchors using the reduced path matrix.

Target scale: **order of 10^5 structurally distinct scenarios**, subject to computational convergence rather than an arbitrary fixed minimum.

Reject early if a skeleton violates hard road/service constraints or is obviously pathological, for example:

- disconnected from Olgiate-Calco-Brivio FS when the scenario is intended as a feeder;
- physically unroutable on the Gate D graph;
- extreme repeated-edge/backtracking without a required operational reason;
- impossible cycle time for any allowed fleet policy;
- duplicate topology/service pattern.

### Stage B — service-policy optimisation

For each promising topology, optimise service rather than attaching one predetermined timetable.

Variables may include:

- directional headway;
- peak/off-peak headway pattern;
- service span;
- day types/calendar;
- clockface phase;
- dwell/recovery;
- number of simultaneously active vehicles;
- direction locking versus interlining at FS;
- which trips serve optional extensions;
- stop set.

Prefer clockface-compatible patterns where utility is similar.

### Stage C — passenger utility screening

Evaluate the best topology/service combinations using generalised journey time and accessibility. Retain a broad high-performing frontier rather than only one score winner.

### Stage D — exact timetable and S8 integration

For the leading scenarios:

- construct explicit trip schedules;
- phase arrivals/departures against verified S8 events;
- calculate bus→rail and rail→bus transfers;
- test missed connections under runtime perturbation;
- calculate vehicle blocks and required fleet.

### Stage E — exact OSM verification

Reconstruct the leading scenarios on the canonical full Gate D graph and recalculate:

- exact km;
- exact model running time;
- road uncertainty exposure;
- directional asymmetry;
- slope/physical flags where applicable.

### Stage F — robustness tournament

Perturb key assumptions and rerank finalists. Required sensitivities include at least:

- walk weight within the published TAG range;
- wait weight within the published TAG range;
- bus running time increase/decrease;
- dwell variation;
- recovery requirement;
- rail/bus delay affecting connections;
- lower/higher annual bus-km envelope;
- plausible demand-weight changes.

The recommended network must remain near the top over a wide region of this parameter space.

## 8. Budget exploration

### 8.1 Primary decision envelope

The main recommendation must be feasible at or below:

**111,419 bus-km/year**

unless the final report explicitly identifies a substantially better higher-budget scenario and quantifies the incremental utility obtained.

### 8.2 Budget frontier

In addition to the main budget, evaluate at least proportional envelopes around it, for example:

- −20%
- −10%
- current validated reference
- +10%
- +20%
- +30%

The exact frontier can be evaluated continuously or at finer intervals once the optimisation engine is cheap enough.

Output must show marginal utility per added 1,000 bus-km. This is intended to identify a genuine “sweet spot”, including the possibility that a network cheaper than today provides almost the same utility.

### 8.3 Calendar is part of optimisation

Do not assume 303, 365 or a Merate-style annual service-day count as a hidden constant. Construct explicit calendars/day types and compute annual production from them.

The optimiser may discover that concentrating service on high-demand days produces more utility, or that Saturday/evening availability is valuable enough to retain. The result must be data/model driven.

## 9. Passenger utility model

### 9.1 Primary unit

The primary passenger-facing metric is **demand-weighted generalised journey time/accessibility**, not route length.

For each relevant OD pair and departure window:

`GJT = IVT + w_walk*walk + w_wait*wait + transfer_penalties + reliability/missed_connection_cost`

Use published TAG ranges from `PHASE2_TRANSIT_BEST_PRACTICES.md` and report sensitivity instead of claiming one coefficient is a fact.

### 9.2 Demand layers

Use separate, traceable layers:

1. **S8 feeder utility:** population/verified demand to and from Olgiate-Calco-Brivio FS and onward rail connections.
2. **Work OD utility:** ISTAT 2021 commuting flows, mapped only at the spatial resolution actually supported by the source.
3. **School accessibility:** verified school destinations and any official study-flow evidence available.
4. **Essential/local opportunity accessibility:** hospital/health, municipal services and major verified centres, reported separately if empirical trip weights are unavailable.

Do not collapse unsupported demand layers into invented passenger counts.

### 9.3 Useful departures and timetable existence

Report:

- departures/day by direction and day type;
- median and maximum useful headway;
- longest service gap during the declared span;
- first/last useful S8 connection;
- probability of making planned S8 transfers under perturbation.

## 10. Equity and continuity safeguards

Avoid hiding social/territorial policy inside an arbitrary weighted score.

For every scenario report:

- total population within 5/8/10/12-minute walking catchments;
- the same metrics by municipality;
- worst-served municipality;
- change versus current validated baseline;
- existing stops retained/lost;
- population whose nearest useful stop moves materially farther away.

### Default non-regression safeguard

Unless a later explicit political/service policy overrides it, the preferred scenario should not make the **worst municipality’s passenger-utility/accessibility result worse than the current validated baseline** while improving the regional total. If the optimiser finds such a trade-off attractive, report it as a policy choice rather than silently accepting it.

## 11. How Phase 2 selects one recommendation without arbitrary weights

Phase 2 must not create a hidden weighted score such as `0.3 coverage + 0.2 frequency + ...`.

Use a **constraint + robust utility + lexicographic tie-break** rule.

### Step 1 — hard eligibility

A candidate is eligible only if it passes:

- road/routing integrity;
- explicit annual production budget for the decision run;
- service-cycle/fleet feasibility;
- minimum declared recovery/reliability rules;
- no INVALIDATED/PLACEHOLDER evidence;
- baseline territorial non-regression safeguard unless explicitly waived.

### Step 2 — robust passenger utility

Among eligible candidates, rank by the **median/expected demand-weighted GJT improvement or accessibility utility across the declared behavioural/runtime sensitivity set**.

Also record worst-case percentile performance so a fragile scenario cannot win solely at one parameter point.

### Step 3 — practical tie-break

If the top alternatives are within a small uncertainty band rather than meaningfully distinguishable, prefer in this order:

1. higher reliability / lower missed-connection risk;
2. simpler public-facing pattern and more clockface regularity;
3. lower annual bus-km;
4. fewer operationally unverified road/stop elements;
5. greater continuity with existing stops/corridors.

The final report must show whether the tie-break was invoked.

## 12. Required outputs

At minimum Phase 2 must produce:

- `outputs/phase2/scenario_catalog.*` — all unique generated scenarios or reproducible compact representation;
- `outputs/phase2/frontier.*` — high-performing non-dominated/robust frontier;
- `outputs/phase2/budget_utility_curve.*`;
- `outputs/phase2/finalists.*`;
- `outputs/phase2/final_recommendation.json`;
- `outputs/phase2/stop_changes.*`;
- `outputs/phase2/s8_connections.*`;
- `outputs/phase2/equity_by_municipality.*`;
- `outputs/phase2/robustness.*`;
- maps for primary recommendation, runner-up and current baseline;
- explicit public-facing service plan for the primary recommendation.

The final recommendation must state at least:

- topology and route sequence;
- stop set, distinguishing existing and proposed;
- headway by time period/direction;
- service span and calendar;
- S8 connection strategy;
- annual bus-km;
- scheduled vehicle-hours if computable from explicit timetable;
- simultaneous vehicles and operating blocks;
- passenger utility improvement versus current service;
- population access metrics;
- municipal equity results;
- reliability/robustness metrics;
- field checks still required.

## 13. Initial seed catalogue

The following Gate E/D designs enter Phase 2 as benchmark seeds, not privileged solutions:

- `WEST_COMPACT_MONDONICO`
- `EAST_COMPACT_ARLATE`
- `EAST_CALCO_SUPERIORE_SENSITIVITY`
- `FIG8_COMPACT`
- `WEST_RAVELLINO_EXTENSION`
- `EAST_CAPRINO_CELANA_EXTENSION`
- `WEST_SAN_ZENO_SENSITIVITY`
- D184/D185 corridor-style alternatives where upstream semantics permit comparison
- current D184+D185 service baseline
- local Merate D201+D202 concept as an external comparator, not an Olgiate scenario

## 14. Implementation order

Phase 2 implementation should now proceed directly in this order:

1. materialise/checksum canonical Phase 2 inputs from A–F;
2. acquire and manifest ISTAT 2021 work-commuting OD;
3. serialise the frozen Gate D graph and build the reduced transfer/path matrix;
4. generate candidate-stop universe;
5. implement structural topology generator;
6. implement service-policy optimiser;
7. implement passenger GJT/S8 utility calculation;
8. run massive search;
9. exact-route and timetable the shortlist;
10. robustness tournament;
11. publish primary recommendation and runner-up.

This is a single design programme. It should not be split into another chain of artificial PASS gates unless a genuinely independent audit boundary becomes necessary.
