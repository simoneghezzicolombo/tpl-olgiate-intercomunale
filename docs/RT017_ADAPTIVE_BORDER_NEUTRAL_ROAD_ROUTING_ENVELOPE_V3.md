# RT-017 · Adaptive border-neutral road routing envelope V3

## Scope
RT-017 changes only the geographic acquisition/search envelope of the V3 road graph. Municipal boundaries remain minimum passenger-service obligations downstream; they are not road-routing barriers. RT-016 population logic and the frozen 36-stop inventory are not modified.

Baseline: `phase2-cross-engine-experiment-manifest-v3` @ `8a2cd43405dbac04cea56294407bcc7b453c65b4` (RT-015 PASS). The final 36-stop files arrived later on a separate audited workstream, so RT-017 imports their exact Git blobs without editing them. `AGENT_PROTOCOL.md` is not present at the RT-015 baseline; the repository coordination contract actually present there is `COLLABORATION_PROTOCOL.md`, plus `AGENT_STATUS.md` and Issue #1.

## Inherited routing contracts
- RT-006: deterministic restriction-aware bounded alternative corridors remain compatible with the frozen graph interface.
- RT-009: reciprocity is never inferred from one direction.
- RT-010: the pair universe is all ordered non-self pairs, with no geographic/topologic filtering.
- RT-015: cross-engine experiment-manifest lineage is the compatibility baseline.

RT-017 uses all 36 frozen stop places as **stabilization probes only**. This does not declare them routing terminals for the eventual network.

## Why Gate-D geometry was insufficient
The Gate-D frozen epoch records a fixed WGS84 bbox `(45.68, 9.31, 45.82, 9.56)`. That was adequate for Gate D, but it is not evidence that a topology-neutral candidate path cannot profitably leave that rectangle. RT-017 therefore removes the fixed-bbox assumption.

## Deterministic adaptive expansion
All 36 stop coordinates are projected to EPSG:32632. The smallest axis-aligned rectangle containing them is the invariant probe extent.

The initial routing margin is **500 m**, derived mechanically as twice the already validated Gate-D maximum waypoint snap ceiling of 250 m. Successive margins double: `500, 1000, 2000, 4000, ...`. `max_levels=7` is only a fail-closed computational ceiling. It can never itself produce PASS.

For every level:
1. convert the metric envelope to WGS84;
2. query all OSM `highway` ways and `type=restriction` relations in four deterministic tiles;
3. use historical Overpass time `2026-09-05T13:45:50Z`, exactly the RT-015 baseline commit timestamp;
4. canonicalize and hash the returned OSM elements;
5. rebuild the bus-eligible directed graph using the certified Gate-D/V3 access, speed and oneway semantics;
6. keep only road segments whose two projected endpoints are within the current metric envelope;
7. preserve bus-applicable via-node turn restrictions and do not approximate via-way restrictions;
8. snap the same 36 probes under the inherited 250 m ceiling;
9. build the full RT-010 oracle of `36 × 35 = 1,260` directed pairs;
10. run one restriction-aware one-to-many search per source probe;
11. record exact edge sequence, projected path-geometry digest, model runtime, distance and boundary clearance.

No municipality name, polygon, allowlist or denylist appears in this algorithm.

## Convergence
A transition is stable only if, pair-by-pair:
- the pair universe is identical;
- routability is identical;
- snapped graph-node identity is identical;
- routed edge sequence is exactly identical;
- projected geometry digest is exactly identical;
- runtime differs by no more than `1e-9 min`;
- distance differs by no more than `1e-6 m`.

A level can be frozen only when:
- all 1,260 probe pairs are routable there;
- no accepted path comes within 250 m of that level's acquisition boundary;
- the level is unchanged by **two successive larger expansions**.

Therefore if levels `k→k+1` and `k+1→k+2` are both stable, level `k` is the earliest freeze candidate, provided it is boundary-clear. Any newly routable path, changed edge sequence, geometry change or material improvement necessarily prevents freezing and forces continued expansion.

## Reproducibility and fail-closed behavior
The OSM epoch is historical rather than `latest`. Every expansion records its canonical OSM SHA256 and acquisition endpoints. CI repeats the complete territorial run independently and requires identical frozen bounds and graph/pair digests.

If historical OSM acquisition fails, any probe exceeds the inherited snap ceiling, any directed pair remains unroutable, path identity does not stabilize, a path remains boundary-sensitive, or two confirming expansions are not available within the computational ceiling, RT-017 exits nonzero and records `FAIL_RT017_NO_PROVEN_CONVERGENCE`.

## Outputs
Artifact directory `outputs/phase2/rt017/` contains:
- `complete_directed_probe_pair_manifest_v3.csv`
- `envelope_expansion_audit_v3.csv`
- `pair_stabilization_transitions_v3.csv`
- `osm_acquisition_audit_v3.csv`
- pair results and snap audits by executed level
- `frozen_graph_nodes.csv.gz`
- `frozen_graph_edges.csv.gz`
- `frozen_turn_rules.csv.gz`
- `frozen_osm_snapshot.json.gz`
- `frozen_pair_results_v3.csv`
- `frozen_routing_envelope_metadata_v3.json`
- `rt017_validation.json`

The workflow also commits a compact evidence subset under `outputs/phase2/rt017_frozen_evidence/` after PASS. Large frozen graph/source files remain in the CI artifact and are identified by SHA256 in metadata.

## Non-claims
RT-017 does not discover stops, choose a topology, choose a route, calculate headways, recommend PRIMARY/RUNNER-UP alternatives, score policy outcomes or alter population accounting. Its sole claim, if CI passes, is that the V3 road search space has a reproducibly frozen border-neutral envelope demonstrated by adaptive stabilization.
