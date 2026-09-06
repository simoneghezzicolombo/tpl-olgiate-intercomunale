# RT-022 · Topology-neutral territorial structural-search orchestrator V3

## Purpose

RT-022 is the deterministic Alpha integration layer between the frozen real RT-021 corridor corpus and the existing V3 structural-search machinery.

It does **not** introduce a new routing algorithm, choose a service topology, identify a preferred network, infer service termini or score candidates. Its role is to compose already validated contracts and fail closed if their identities or semantics do not match.

The pipeline is:

`RT-021 frozen corridor corpus → RT-018 exact stop occurrences → RT-019 elementary reduction → RT-009 bidirectional reciprocity → RT-008 connected topology-neutral structure frontier`

RT-007 remains the exhaustive abstract-subset oracle for controlled cases. RT-008 is the scalable connected-only implementation used for territorial enumeration.

## Current status

Until a frozen RT-021 real-territory PASS bundle is supplied, the only valid RT-022 status is:

`PREPARED_BLOCKED_PENDING_RT021_REAL_CORPUS`

Unit tests may use controlled fixtures to verify the integration contract, but fixture output is never territorial evidence.

## Frozen stop semantics

The final stop-place layer contains 36 physical stop places across the five core municipalities. RT-022 requires the final municipality counts to remain unchanged.

Thirty-five `CONVENTIONAL_TPL` stop places become **technical pair-query anchors**. The one `SPECIAL_SERVICE` stop remains in the graph attachment universe but is excluded from the conventional pair-query manifest.

A technical query anchor is not a service terminus or capolinea.

The complete RT-010 request universe must therefore contain exactly:

- 35 technical anchors;
- 1,190 directed non-self pairs;
- 595 unordered pair identities.

RT-022 rebuilds that universe independently and requires exact equality with the RT-021 supplied manifest.

## Input integrity

Before structural work begins, RT-022 validates:

1. exactly 36 unique stop-place attachments;
2. exactly 35 conventional and one special-service stop;
3. all conventional stops are route-ready;
4. every attachment belongs to one common frozen graph epoch;
5. the independently rebuilt RT-010 manifest exactly matches the supplied 1,190-row manifest;
6. `audit_pair_execution_completeness()` passes;
7. every corridor references a known pair and has endpoints equal to that pair;
8. corridor IDs are globally unique;
9. a pair marked route-found has corridor evidence and corridor evidence cannot belong to a pair marked no-route;
10. optional graph epoch and SHA256 identities supplied by RT-021 agree with the actual bundle.

For a territorial run, RT-021 metadata must explicitly report PASS. Controlled or synthetic fixture metadata is rejected.

## Stop occurrence and elementary-link semantics

RT-018 materializes passenger stop occurrences only from the exact ordered `path_node_ids` of each corridor alternative. Names, settlement labels and municipalities do not create stop occurrences.

RT-019 then classifies every admitted directional corridor alternative. A corridor A→C that physically encounters a third conventional stop B strictly between its endpoints is decomposable. An elementary structural alternative is one that has no third conventional intermediate stop.

All original corridor evidence remains auditable. Only admitted elementary alternatives are exposed to RT-009 for structural eligibility.

## Reciprocity

RT-009 remains unchanged. An undirected structural link exists only when both requested directions have a route and at least one admitted elementary corridor.

Directional asymmetry is therefore preserved rather than averaged away.

## Policy groups are not geographic barriers

The required service-policy groups are exactly:

- Brivio
- Calco
- La Valletta Brianza
- Olgiate Molgora
- Santa Maria Hoè

Municipality membership is used only as a hard **coverage guard on generated structures**. It is never used to allow, forbid or clip roads or corridors.

This preserves the V3 rule that municipal boundaries define minimum service obligations, not routing barriers.

## Topology-neutral generation

RT-008 expands connected edge sets without consulting topology labels. Topology classes and shape flags are calculated only after a connected structure has been generated.

Consequently labels such as `PATH`, `CYCLE`, `TREE_BRANCHING` or `FIGURE_EIGHT_LIKE` cannot seed, prioritize, filter or score the search.

A figure-eight-like structure may appear only as a descriptive property of an already generated candidate.

## Technical caps

RT-008 has explicit state and structure caps for computational safety. A cap hit is a blocker, not a sampling rule.

If a technical cap is reached:

- the run is incomplete;
- no partial structure pool is exposed as usable territorial evidence;
- the solution is not to prune by municipality, topology family or a hand-authored route preference.

Any required scalability change must remain deterministic and topology-neutral.

## Outputs after a real RT-021 handoff

The runner writes an auditable bundle including:

- frozen stop attachments;
- technical pair-query anchors;
- independently validated directed-pair manifest;
- explicit pair results;
- complete retained corridor evidence;
- exact stop-occurrence corpus;
- elementary/decomposable classification;
- directional elementary availability;
- RT-009 pair audit;
- reciprocal elementary structural links;
- topology-neutral RT-008 structure universe;
- deterministic SHA256 identities and run metadata.

## Non-goals

RT-022 does not:

- select PRIMARY or RUNNER-UP;
- choose a final service topology;
- choose service termini;
- create new stops;
- change stop conflation;
- generate candidate GTFS yet;
- select headways or timetables;
- evaluate passenger accessibility or population benefit;
- introduce Cassina or Circolare Meratese interchange logic;
- use synthetic territorial evidence or random generation.

Once RT-022 has a complete real structure universe, later stages may materialize candidate service patterns and GTFS for passenger-routing evaluation. That downstream work is not part of RT-022.
