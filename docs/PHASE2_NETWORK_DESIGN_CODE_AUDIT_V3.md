# Phase 2 Network Design Code Audit V3

Status: **IN PROGRESS — RT-006**

Canonical coordination issue: #20 `RT-006 · External algorithm/code audit and existing-stop-first network design`.

This audit is implementation-oriented. Papers and reviews are used to discover and understand methods, but an approach is not admitted into the Phase-2 implementation lineage until its actual repository, code interfaces, license, tests and assumptions have been inspected.

## 1. Why this audit exists

RT-005 established a formulation failure in the previous candidate-network search. Structural routing anchors were allowed to stand in for the complete explicit passenger-stop set. The resulting four finalists are retained only as negative regression fixtures.

The correction is **not** to hand-design a more plausible network. The correction is to rebuild the independent search representation so that:

1. a corridor/path and its passenger stop pattern are separate objects;
2. a normal local-bus route may naturally contain many passenger stops;
3. existing physical stop infrastructure is reused by default;
4. an on-path stop is primarily a dwell-time choice, not a kilometre-scale route detour;
5. proposed new stops are exceptional hypotheses, not automatic optimization anchors;
6. passenger access is evaluated on the walking network and later cross-checked independently;
7. route, stop-pattern, timetable and passenger-routing stages remain auditable and separable.

The human-defined EAST_BASE/WEST_BASE corridor seeds are **non-decision regression fixtures only**. Their successful materialization into 12 and 19 comparable stop positions demonstrates that separating structural waypoints from passenger stops fixes the stop-count representation, but it does not establish those corridors as candidate solutions.

## 2. Existing-stop-first policy

Phase 2 V3 should search an expanded stop universe rather than a D184/D185-only universe.

Evidence layers, in descending evidentiary strength for physical-stop reuse:

1. official/reference-period GTFS stop records and reconciled physical clusters;
2. OpenStreetMap public-transport objects and relations, reconciled rather than treated as official truth;
3. route/corridor evidence from the broader Meratese/Lecco network, including the existing OneDrive KML archive;
4. proposed new-stop hypotheses only when a demonstrated residual access gap cannot be adequately served by suitable existing infrastructure.

Useful OSM object families include `public_transport=stop_position`, `public_transport=platform`, `highway=bus_stop` and `type=public_transport` stop-area relations.

A new stop remains `FIELD_CHECK_PENDING` until its identity, road side, boarding plausibility, pedestrian access, bus access and physical siting have been checked. No external algorithm is allowed to silently promote a proposed point to finalist-ready status.

## 3. Correction to the walking-access diagnosis

The legacy `scripts/04_walk_network.py` uses an approximate planar distance plus a detour factor. It is **not** the certified Phase-2 Access Equity V2 engine used for the four finalists.

Certified Phase-2 stop/access evidence uses a frozen pedestrian graph and NetworkX Dijkstra. `src/phase2_stop_core.py::walk_distances_to_stop_node()` reverses the directed graph and calls `nx.single_source_dijkstra_path_length(..., weight="walk_min")`; Access Equity V2 consumes those certified catchment tables.

A remaining audit risk is the connector/snap model. `src/phase2_stop_sources.py::attach_point_to_walk_graph()` connects a stop or candidate to the nearest walk-graph node by Euclidean nearest-neighbour distance and accepts the snap when it is <=250 m. That connector does not itself prove that the straight connection does not cross a railway, fence, watercourse or other impermeable barrier.

Therefore RT-006 does **not** discard Graph A. It requires:

- a barrier/snap red-team for pathological candidates such as the former Olgiate-south/"Centro Sportivo" case;
- explicit inspection of the source walk-graph edge extraction;
- an independent routing replication for selected origins/stops, with R5/r5py a leading candidate.

## 4. Repository audit — first pass

The table below records only code-level findings already inspected. `ADOPT`, `ADAPT`, `BENCHMARK_ONLY`, `CROSS_CHECK_ONLY` and `REJECT_FOR_CORE` are role labels, not software-quality judgments.

### 4.1 RenatoArbex/TransitNetworkDesign

**Role:** `BENCHMARK_ONLY`.

The repository is a public collection of TNDP instances and published solution route sets. Its basic representation is directly relevant: nodes are possible boarding/alighting locations, links carry travel time, demand is OD demand and a solution route is a sequence of many nodes. It includes Ceder, Mandl, Mumford and Rivera instances and route-set examples with optional frequencies.

Why it matters:

- provides public smoke-test networks for any route-generation algorithm we implement;
- provides a standard way to represent route sets as full node sequences rather than a handful of anchors;
- provides published comparison solutions and objective outputs.

Why it is not core production code:

- it is primarily a dataset/benchmark repository, not a maintained route-generation library;
- several classic instances are highly abstract compared with the Brianza road/stop universe;
- repository data licensing is framed for academic research and source attribution, so datasets should be used as benchmark fixtures rather than copied into production artifacts without recording provenance.

**Decision:** use Mandl plus at least one larger Mumford/Rivera instance for deterministic algorithm smoke tests; do not treat its published route sets as a model for the Brianza geography.

### 4.2 r5py/r5py + Conveyal R5

**Role:** `ADOPT_OR_CROSS_CHECK` for multimodal passenger routing/accessibility, **not** route generation.

Inspected branch head: `eca45579bff083284100076e53e18602aa60307b` (2026-08-03, update to R5 v7.6).

The project is an active Python interface to Conveyal R5. It accepts real multimodal networks and calculates travel-time matrices/accessibility for walking, bicycle, public transport and car. The project exposes test/coverage/documentation infrastructure and is dual licensed `GPL-3.0-or-later OR MIT`.

Best fit for Phase 2:

- create a candidate GTFS from a generated corridor + stop pattern + timetable;
- combine it with the reference GTFS and OSM network;
- calculate door-to-door multimodal travel outcomes;
- cross-check Graph-A walking access around known pathological barriers;
- independently evaluate S8/bus transfers rather than reproducing all passenger-routing logic ourselves.

Open questions before `ADOPT` is final:

- deterministic build/pinning of Java/R5 dependencies in GitHub Actions;
- reproducibility of OSM/GTFS input snapshots;
- precise treatment of access/egress connectors and barrier topology;
- runtime for the full Brianza origin/destination evidence universe.

### 4.3 UTEL-UIUC/gtfs_segments

**Role:** `ADOPT_CANDIDATE` for GTFS segmentation, stop-spacing diagnostics and independent validation.

Inspected branch head: `1bf2a5682400c027bfe0fa404dd59e5014f7ecbc` (2025-05-21).

This Python package converts bus GTFS into stop-to-stop segments, includes route/direction/traversal fields, calculates segment distance, traversal time and speed, supplies stop-spacing/statistical utilities and has tests/documentation. It is MIT licensed and accompanied by a JOSS publication.

Best fit for Phase 2:

- independent replication of our D184/D185 descriptive spacing benchmark;
- standard segment table for the complete local GTFS universe;
- anomaly detection for candidate stop patterns;
- removal of avoidable custom code where a tested package already implements the same descriptive operation.

It does not solve route design or stop selection.

### 4.4 transnetlab/transit-routing

**Role:** `CROSS_CHECK_ONLY` / algorithm reference for schedule-based passenger routing.

Inspected branch head: `1789109e670a900634cb1a14ec472293b0511dbd` (2024-05-04).

The repository implements several public-transit routing families in Python: RAPTOR/rRAPTOR, TBTR/rTBTR, hyper-partitioned variants, Transfer Patterns and CSA. Its primary objective space is bicriteria passenger routing, typically arrival time and number of transfers. License: MIT.

Best fit:

- independent algorithmic reference for transit assignment/routing semantics;
- possible smoke-test comparison for a small subset of R5 outputs;
- useful source for understanding one-to-many passenger routing.

Not selected as the primary Phase-2 engine because R5/r5py already integrates walking + GTFS + multimodal network construction more directly. It is also not a route-network design generator.

### 4.5 dimichai/mo-tndp

**Role:** `BENCHMARK_CONCEPT_ONLY`; `REJECT_FOR_CORE` under the current architecture.

Inspected branch head: `931e36e503261bfefb7898660a2692b6b0b52aeb` (2026-06-02).

This is a current multi-objective Gymnasium environment in which an agent moves through adjacent grid cells and places stations, with vector rewards based on OD demand for socio-economic groups. The group-wise multi-objective framing and action-mask concept are interesting.

Why it is a poor direct fit:

- city representation is a grid rather than our certified road graph;
- actions place a station at every movement step, recreating the conceptual coupling between route geometry and stop placement that RT-005 requires us to separate;
- episode length is framed as a station budget;
- example/reset workflows may use random starts, incompatible with the project's deterministic evidence contract unless completely controlled;
- it does not directly exploit our official physical-stop universe.

Useful ideas to retain conceptually: vector/fairness objectives, explicit action masks, separation of environment constraints from optimization policy. Do not transplant the grid/station-placement architecture.

### 4.6 organicmaps/gtfs-osm-matcher

**Role:** `ADAPT_PATTERN` for stop reconciliation.

The repository provides a current GTFS↔OSM stop-matching workflow/UI with confidence categories based on exact ID/code, routes, normalized names, nearby generic stops, transit hubs and unresolved clusters. License: Apache-2.0.

This is directly aligned with the existing-stop-first requirement. The valuable part is the **matching taxonomy and conflict handling**, not necessarily copying the UI.

Phase-2 adaptation target:

- reconcile GTFS physical stop clusters with OSM stop positions/platforms;
- prefer exact ID/code references where present;
- use route membership and normalized names as secondary evidence;
- explicitly retain many-to-one, cluster, conflict and no-match states rather than forcing a match;
- use coordinates only as one piece of evidence.

The inspected repository is the web interface and expects matching data from a sibling parser workflow, so the actual matching implementation must be traced before any code is copied.

### 4.7 CxAalto/gtfspy

**Role:** `CROSS_CHECK_ONLY` / source of proven design patterns.

The package can import multiple GTFS feeds, augment stop data with OSM-based real walking distances, calculate network statistics and perform Pareto accessibility routing with a CSA-derived engine. License: MIT.

It is highly relevant conceptually, but its README itself describes interfaces as not yet stabilized and its stack is older than r5py. It should be audited as an independent reference for OSM walking-distance construction and GTFS network analysis rather than made the primary passenger router without further evidence.

## 5. Early architecture implication

The first code-level audit supports, rather than replaces, the following decomposition:

```text
FROZEN REAL EVIDENCE
  ├─ road graph / bus feasibility
  ├─ official GTFS stops + routes
  ├─ OSM stop/platform/stop-area evidence
  ├─ KML route-corridor evidence
  ├─ population buildings / OD / POI
  └─ S8 + timetable evidence
          │
          ▼
INDEPENDENT CORRIDOR SEARCH
(no human EAST/WEST prescription)
          │
          ▼
EXISTING-STOP MATERIALIZATION
(all suitable physical stops encountered by corridor)
          │
          ▼
STOP SUBSET / SPACING OPTIMIZATION
(only if needed; walking benefit vs dwell cost)
          │
          ▼
NEW-STOP GAP TEST
(exception only; field check required)
          │
          ▼
TIMETABLE / FREQUENCY / ROBUSTNESS
          │
          ▼
CANDIDATE GTFS
          │
          ├─ existing Phase-2 evaluators
          └─ independent R5/r5py passenger-routing cross-check
          │
          ▼
PARETO EVIDENCE + HUMAN POLICY DECISION
```

The outstanding technical gap is now clearer: mature open-source tools are readily available for **benchmarking, GTFS segmentation, stop reconciliation and passenger routing**, but we still need a code-level audit of route/corridor-generation and corridor-specific stop-subset optimization implementations that fit a real bus-operable road graph.

## 6. Next audit queue

Priority A:

- inspect mature route-generation / UTRP / TNDP algorithm implementations on Mandl/Mumford rather than generic "bus optimization" demos;
- identify implementations of k-shortest-path / path-set generation followed by multi-objective route-set selection;
- inspect code where stop selection occurs after or along a fixed corridor;
- determine whether a reusable deterministic implementation exists or whether the safest solution is a small auditable implementation built from NetworkX/OR-Tools primitives and tested against public benchmarks.

Priority B:

- inspect the actual parser/matching backend behind Organic Maps GTFS↔OSM matching;
- compare with `GTFS2OSM` and other stop conflation implementations;
- build a frozen OSM extraction contract for the five municipalities + justified buffer;
- reconcile the complete GTFS stop universe, not only D184/D185.

Priority C:

- install/pin `gtfs_segments` in an isolated reproducibility workflow and compare its D184/D185 segment/spacing outputs with our certified benchmark;
- create a minimal R5/r5py smoke test using frozen OSM + frozen GTFS and a small origin set;
- specifically test barrier-sensitive stop/candidate snaps against Graph A.

## 7. Non-negotiable guards

- No manually drawn corridor may be relabelled as an independent search result.
- No proposed `FIELD_CHECK_PENDING` stop is finalist-ready.
- No algorithm may use a hidden weighted composite to declare a winner.
- No external code is copied before license and pinned source are recorded.
- No benchmark result is evidence that the benchmark's simplifying assumptions are valid in Brianza.
- Existing physical stops are preferred by default, but they are not mandatory when demonstrably inaccessible, unsafe, directionally wrong or materially inferior.
- The five-municipality explicit-stop safeguard is a declared policy constraint, not a neutral mathematical discovery.
- PRIMARY/RUNNER-UP remain blocked until RT-005/RT-006 downstream rebuild is complete.