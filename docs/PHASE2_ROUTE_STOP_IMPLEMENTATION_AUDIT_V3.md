# Phase 2 Route + Stop Implementation Audit V3

Status: **RT-006 / implementation audit in progress**

This document records the code-level findings that matter most for replacing the RT-005 `anchor = passenger stop` failure without hand-designing a new network.

## 1. Strongest route-generation implementation found so far

### `AHolliday/transit_learning`

Pinned revision: `39656ba7a570f9efa23aa0c8847db368cf6eeb30`

License: GPL-3.0.

Associated project is current, tested on Mandl/Mumford and contains actual route-generation, initialization, evolutionary, Pareto and repair code rather than only benchmark data.

Relevant implementation files inspected:

- `learning/initialization.py`
- `learning/utils.py`
- `learning/nsgaii.py`
- `scripts/gtfs_route_to_node_ids.py`
- repository test tree including `tests/test_yen.py`, `tests/test_heuristics.py`, `tests/test_hyperheuristics.py`, `tests/test_models.py` and `tests/test_simulators.py`.

### 1.1 Route representation

The code represents a transit route as a sequence of graph nodes and a network as a collection of such routes. This is materially better aligned with Phase-2 V3 than the old four-anchor structural representation because route length can naturally comprise many nodes.

However, in the benchmark formulation route nodes also behave as transit stops. We therefore should **not** transplant the representation unchanged into Brianza. In V3 the road/path node sequence must remain distinct from the passenger stop sequence.

### 1.2 John et al. initialization

`john_init()` constructs a route from a seed edge and grows it from either end through adjacent graph vertices. Edge costs combine normalized street travel time and OD demand with parameter `alpha`.

If too few routes have been generated, the implementation sorts uncovered node pairs by descending demand and calls Yen's k-shortest-path algorithm with `k=10`, accepting paths that respect route-length constraints and improve the transit connection for that pair.

Useful pattern:

- candidate-route generation from graph paths;
- demand-aware terminal-pair ordering;
- explicit minimum/maximum route length;
- Yen alternatives rather than a single shortest path.

Do not copy unchanged because:

- edge cost is a scalarized time/demand score;
- exact ties during route growth are broken randomly;
- the benchmark route node remains a transit stop node;
- GPL-3.0 code copying would create licensing consequences for our repository.

### 1.3 Nikolic initialization

`nikolic_init()` repeatedly chooses shortest paths that satisfy the greatest amount of currently uncovered direct demand.

Useful pattern:

- demand is removed from the uncovered matrix after being directly connected;
- candidate route construction is therefore incremental rather than based on a fixed small anchor set.

Risk for Brianza:

- maximizing directly satisfied OD demand alone can systematically neglect low-demand municipal areas;
- our five-municipality explicit-stop safeguard must remain a declared policy constraint rather than be left to demand coverage.

### 1.4 Husselmann initialization

This is the most promising route-pool pattern inspected so far.

The implementation:

1. enumerates every unordered node pair;
2. runs Yen k-shortest paths with default `K=50`;
3. filters candidates to minimum/maximum route-node counts;
4. computes path travel time and demand satisfied along each path;
5. sorts by ascending length, breaking ties by descending satisfied demand;
6. keeps a default of 15 paths per terminal pair;
7. constructs route networks from that candidate pool;
8. applies trim/grow mutations.

This suggests a defensible V3 route-generation architecture:

- generate a **large deterministic corridor pool** from the frozen bus-operable graph;
- do not preselect Arlate, Bernaga, Brivio centre, Perego or any other settlement as a required corridor waypoint;
- apply the five-municipality policy safeguard only when evaluating/selecting networks;
- keep multiple alternative paths between relevant termini instead of committing to a single shortest path;
- materialize passenger stops only after each road corridor exists.

The exact Husselmann implementation is not suitable as canonical evidence because the downstream network assembly/crossover and mutation contain substantial randomness. The **candidate-pool idea** is the reusable part.

### 1.5 NSGA-II

The repository contains a true non-dominated-sorting NSGA-II implementation. This is conceptually compatible with Phase 2's rejection of a single hidden weighted score.

But the implementation uses random tournament selection, crossover, shuffling and mutation. It also samples objective weights in parts of the generation process. A fixed seed makes a run reproducible, but the current Phase-2 evidence contract requires stronger determinism than merely seeded stochastic search.

Decision:

`ADAPT_ALGORITHM_REFERENCE`, not direct canonical adoption.

Potential use:

- independent benchmark comparator on Mandl/Mumford;
- stress-test whether a deterministic Phase-2 search misses important portions of a Pareto front;
- source of route repair/mutation ideas after each operator is independently specified and tested.

## 2. Strongest stop-selection implementation found so far

### `pysal/spopt`

Pinned revision: `493a58aa99134b6abecf8d37479fbee01a46e820`

License: BSD-3-Clause.

The package is active, documented, CI-tested and part of the PySAL ecosystem. It implements standard spatial facility-location models rather than a transit-specific ad-hoc score.

### 2.1 P-median is directly useful

`spopt.locate.PMedian.from_cost_matrix()` accepts:

- an origin-to-candidate-facility cost matrix;
- demand/population weights for each origin;
- the number of facilities to select;
- optional predefined mandatory facilities;
- optional capacities.

Its objective is to minimize population/service-load weighted shortest distance or travel time from demand points to selected facilities.

This maps very naturally to our corrected stop problem:

- **clients** = population cells/buildings or OD origins;
- **facilities** = existing physical stops encountered by a candidate corridor;
- **cost matrix** = real walking-network minutes from each client to each stop;
- **weights** = calibrated population or another explicitly defined demand measure;
- **predefined facilities** = hub and any explicitly required stop under a declared policy scenario.

This directly implements the user's preferred principle: a stop arrangement should favour stops that are actually close to where people live rather than treating everybody inside a broad 10–15 minute threshold as equally covered.

### 2.2 Why this is better than a fixed walking threshold

A p-median objective penalizes every extra minute of walking continuously. A resident 3 minutes from a stop is therefore better served than one 9 minutes away, and both are better served than one 14 minutes away.

The familiar 5/8/10/12-minute statistics should remain as descriptive/equity diagnostics, not the sole stop-selection objective.

### 2.3 Why p-median cannot be the whole rule

Vanilla p-median requires a fixed number `p` of facilities. For Phase 2 we do not want to decide arbitrarily that a corridor must contain exactly 8, 12 or 15 stops.

The likely implementation should therefore compare either:

- a family of `p` values and retain the non-dominated access-vs-dwell frontier; or
- a custom MILP extension where each selected stop has an explicit dwell/operating penalty and the number of stops is endogenous; or
- p-median plus a hard maximum walking-time/equity guard, again evaluated across multiple `p` values.

This lets the data determine whether a corridor sensibly wants 11, 14, 17 or 20 stops.

### 2.4 Existing-stop-first implication

`spopt` should initially receive **only suitable existing physical stops** on the corridor.

A new stop should enter the facility set only in a second residual-gap scenario:

1. solve/evaluate using existing stops only;
2. identify materially underserved population after the best existing-stop frontier;
3. test whether an evidenced new-stop hypothesis provides a meaningful improvement;
4. retain it as `FIELD_CHECK_PENDING` until physical and barrier validation is complete.

This prevents the optimization from preferring a mathematically convenient coordinate when a nearby existing stop is practically adequate.

## 3. Recommended deterministic Phase-2 V3 search experiment

The audit now supports testing the following architecture.

### Stage A — full existing-stop evidence

Create a reconciled master inventory using:

- all relevant official/reference GTFS stops, not only D184/D185;
- OSM `public_transport=stop_position`, `public_transport=platform`, `highway=bus_stop` and stop-area relations;
- the user's wider Meratese/Lecco KML archive as route/corridor evidence;
- explicit source/provenance and physical-stop clustering.

### Stage B — independent corridor pool

On the frozen bus-operable graph:

- define only legitimate terminal/hub and service-area policy constraints;
- generate K-shortest bus paths for relevant terminal pairs using deterministic Yen ordering;
- retain multiple paths per pair using transparent, non-random filters such as runtime bound, detour ratio and path uniqueness;
- do not constrain routes to a handful of named human-selected waypoints.

The exact value of K and path-retention limits must be sensitivity-tested rather than copied from Husselmann's defaults.

### Stage C — existing-stop materialization

For each candidate road path:

- match all suitable existing stop clusters lying on the routed road sequence or a rigorously defined same-road stop connector;
- keep road path and stop pattern separate;
- do not use a broad geometric buffer that could pull in stops from a parallel road or wrong side of a barrier.

### Stage D — stop subset frontier

If a corridor contains many candidate existing stops:

- compute population-weighted real walking-time matrix;
- solve p-median / related facility-location problems for a range of stop counts;
- add estimated dwell-time cost for each extra served stop;
- reject dominated stop sets;
- preserve 5/8/10/12-minute coverage, mean/median walking time and high-percentile walking time as diagnostics.

A corridor may retain many stops. There is no canonical small stop-count cap.

### Stage E — residual new-stop test

Only after Stage D:

- identify gaps not reasonably solved by existing stops;
- consider new-stop hypotheses;
- apply road-side, pedestrian-barrier and bus-operability checks;
- never promote a new candidate without field-check status.

### Stage F — operations and passenger assignment

Continue with:

- timetable/frequency construction;
- Stage D/E/F operational robustness lineage;
- candidate GTFS generation;
- R5/r5py door-to-door multimodal evaluation including S8;
- independent comparisons against the current service.

## 4. Immediate benchmark plan

Before applying this to Brianza, implement two public reproducibility smoke tests:

1. **Route-generation benchmark**: Mandl, then one Mumford instance. Verify that our deterministic candidate-pool implementation can reconstruct valid multi-node route candidates and does not degenerate into tiny anchor sequences.
2. **Stop-selection benchmark**: synthetic/frozen small cost matrix with known p-median optimum using `spopt`, followed by a Brianza corridor regression fixture where the selected stops minimize population-weighted walking time.

The EAST_BASE/WEST_BASE fixtures may be used for Stage-C/D regression because they already demonstrate 12 and 19-stop materialization, but their geography remains non-canonical.

## 5. Current provisional decision

The audit does **not** support copying one external TNDP project wholesale.

It supports a modular build using mature pieces:

- `NetworkX`/audited Yen-style K-shortest paths for deterministic corridor-pool generation;
- TransitNetworkDesign/Mandl/Mumford for benchmark fixtures;
- `spopt` for formal existing-stop facility-location optimization;
- `gtfs_segments` for GTFS segment/spacing validation;
- GTFS↔OSM matching patterns for existing-stop reconciliation;
- `r5py/R5` for independent multimodal passenger-routing evaluation.

The custom Phase-2 code should be concentrated only where the problem is genuinely Brianza-specific: bus-operable path constraints, policy guards, existing-stop materialization, timetable/S8 logic and evidence lineage.