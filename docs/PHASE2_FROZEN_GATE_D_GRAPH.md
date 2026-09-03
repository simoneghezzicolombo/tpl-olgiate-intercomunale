# Phase 2 — Frozen Gate D graph and reduced transfer graph

**Workstream:** `phase2-graph-freeze`
**Phase 2 baseline:** `1b9b3d359be48bf58e592e0698702f58e7559e19`
**Gate D computational commit:** `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`
**Gate D closure head:** `7826b53bc4ac72cfbe93ebc7dd3ef0efe7898e1e`
**Canonical network epoch:** `gate-d-2026-09-03-834d5caa0bfd`

## 1. Scope

This workstream materialises the road-network state that actually received Gate D PASS and creates the first reduced transfer-graph layer for Phase 2. It does not choose a bus topology, create a proposed stop, optimise a timetable, change headways or calculate a service budget.

`AGENT_PROTOCOL.md` is not present on the Phase 2 baseline. The repository file actually available for the multi-agent rules is `COLLABORATION_PROTOCOL.md`; this workstream follows that file without claiming that it is a renamed or byte-equivalent `AGENT_PROTOCOL.md`.

A branch-lineage check also found that `phase2-service-design` and the Gate D closure branch diverge from the old common baseline `549198743e7265b333da565ce6990f9241cfd1fd`. Therefore the Phase 2 graph is not inferred from whichever road files happen to exist on the Phase 2 branch. Its provenance is pinned explicitly to the Gate D PASS commit and artifact.

## 2. Canonical Gate D epoch

Gate D PASS identifies the following authoritative computational evidence:

- computational commit: `7c220f7586d0f6e5cccd14a2d518be52eb1c4a55`;
- CI run: `33746091690`;
- final artifact ID: `9891607118`;
- artifact ZIP SHA256: `6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a`;
- Gate D bbox, south/west/north/east: `45.68, 9.31, 45.82, 9.56`;
- raw OSM SHA256: `834d5caa0bfd6e9f4a1400ef5d2f5083ed0da60ba51c0331f59fcbcb5d4b097c`;
- validated structural GeoJSON SHA256: `9032fa1fa2f8a22fd5cfcf81ad7366269d062cb7c27ffbfd57bfba754a1b51ce`;
- routable restriction CSV SHA256: `6cf56e36d095af9b2612924d4210d31207d37c0f7a8dc4592c0d5b929dbda8d6`;
- Gate D anchor evidence SHA256: `c3ab598a43bfb83f31f086d6a14f29d92941969a349ef9087b5e6d87fe10b3d1`.

The graph is built from the **validated structural derivative**, not by replaying a current Overpass query. This distinction matters at Ponte di Brivio: Gate D already made and validated the structural long-run interpretation, while retaining the raw OSM snapshot for provenance. Phase 2 freezes that exact interpretation rather than re-deciding it.

## 3. Persistent frozen source

The first CI bootstrap is allowed to retrieve only the exact Gate D PASS artifact above. Before using it, CI verifies the artifact ZIP checksum and all embedded source checksums. It then stores deterministic compressed copies under:

`data/phase2/frozen_gate_d/source/`

The persistent source bundle contains:

- `osm_gate_d_context.json.gz`;
- `osm_gate_d_structural.geojson.gz`;
- `osm_turn_restrictions_routable.csv.gz`;
- `osm_turn_restrictions_summary.json`;
- `structural_anchor_evidence.csv`;
- `source_manifest.json`.

The three deterministic gzip archives use `mtime=0` and an empty gzip filename, so byte-level checksums are stable. Once this bundle is committed, clean-checkout builds are fully source-closed and do not need the expiring Gate D Actions artifact.

There is **no Overpass acquisition code** in `src/phase2_frozen_graph.py` or `scripts/phase2_materialize_frozen_gate_d_graph.py`. A future OSM refresh is a new epoch and must be separately compared and revalidated before it can replace this one.

## 4. Exact directed graph representation

The materialiser reproduces Gate D v4 semantics:

- metric CRS: EPSG:32632;
- split at every OSM way vertex;
- Gate D graph-node identity: projected endpoint rounded to 0.01 m;
- `oneway:bus` then `oneway:psv` precedence over generic `oneway`;
- roundabout directionality;
- modal access precedence `bus > psv > access/vehicle/motor_vehicle`;
- unparsed bus/psv access values fail closed;
- conditional access is surfaced as uncertainty;
- OSM via-node turn restrictions are retained for stateful routing;
- the eight Gate D `via-way` restrictions remain explicitly unsupported rather than being approximated.

Persistent node IDs are deterministic serialisations of the exact Gate D coordinate keys:

`n:{x_epsg32632:.2f}:{y_epsg32632:.2f}`

Persistent edge IDs combine OSM way ID, source segment sequence, direction, parallel index and the two graph-node IDs. Each edge also retains `osm_way_id`, metric length, direction source, `highway`, `access`, `vehicle`, `motor_vehicle`, `bus`, `psv`, `oneway`, `oneway:bus`, `oneway:psv`, `junction`, dimensional tags, model speed status and Gate D uncertainty flags.

### Frozen graph validation

| Metric | Result |
| --- | ---: |
| OSM highway ways | 24,384 |
| Bus-eligible ways | 15,872 |
| Denied ways | 8,512 |
| Graph nodes | **104,071** |
| Directed edges | **199,217** |
| Weak components | 183 |
| Largest weak component | 98,177 nodes |
| Strong components | 719 |
| Largest strong component | 97,722 nodes |
| Directed edge pairs without reverse counterpart | 14,996 |

The single quantised micro-segment that becomes a self-loop is retained because Gate D retained it. Removing it would produce 199,216 edges and would silently change the graph that received PASS.

## 5. Turn restrictions

The Gate D source contains 566 bus-applicable via-node restrictions. Reapplying Gate D's required-field filtering produces:

- **564** serialised active restriction rows;
- **551** distinct `(via node, incoming OSM way)` rule keys;
- **535** keys whose via node exists in the bus graph;
- 8 `via-way` restrictions not approximated;
- 1 relation without resolvable via-node coordinates.

OSM way identifiers are normalised using the same integer semantics as Gate D before path computation. This prevents CSV values such as `33825785.0` from silently failing to match graph edges stored as `33825785`.

## 6. Reduced transfer graph, level 1

No stop is invented here. The anchor universe contains source records that already exist upstream:

- **581** official bus GTFS stop records within the frozen Gate D bbox;
- **1** rail anchor, `S01514 Olgiate-Calco-Brivio`, taken directly from the Gate D PASS anchor evidence;
- **15** additional Gate D anchors after avoiding a duplicate FS alias.

Total: **597 anchor records**, snapping to **480 unique frozen graph nodes**.

Snap bands are deterministic diagnostic categories, not claims of physical stop feasibility:

- 595 anchors: `ROUTE_READY_LE_75M`;
- 2 anchors: `REVIEW_75_250M`;
- 0 anchors: `OUTSIDE_250M`.

Of the 480 unique reduced nodes, 476 lie in the largest weak component and four lie in smaller road components. Those four are retained and flagged, not deleted or force-connected.

The three Gate D design anchors `MONDONICO`, `SAN_ZENO` and `CALCO_SUPERIORE` remain `ASSUMPTION`. They are never promoted to verified stops or destinations. No `PROPOSED_STOP` is created by this workstream.

## 7. Shortest-path cache contract

The path layer uses the same directed graph and via-node turn rules. The optimisation API is based on **one restriction-aware one-to-many Dijkstra per unique new source graph node**, not one full-graph Dijkstra for every scenario leg.

The first cache is deliberately limited to the 16 Gate D/rail seed anchors. All 581 official stop records are already materialised as reduced nodes, but precomputing every all-pairs stop path before the stop-universe workstream decides which nodes matter would create unnecessary computation and storage.

Initial path-cache validation:

- seed anchor records: 16;
- unique seed graph nodes: 16;
- one-to-many Dijkstra runs: **16**;
- ordered seed paths: **240 = 16 × 15**;
- disconnected seed pairs: **0**;
- directionally asymmetric unordered anchor pairs: **118**;
- maximum directional distance difference: about **433.34 m**, Beverate ↔ San Zeno.

A later proposed stop can be appended without modifying the frozen graph. It must carry its own epistemic status, snap to this epoch and trigger only missing source-node cache runs.

## 8. Outputs

Persistent outputs are under `outputs/phase2/frozen_gate_d/`:

- `graph_nodes.csv.gz`;
- `graph_edges.csv.gz`;
- `turn_rules.csv.gz`;
- `anchor_universe.csv.gz`;
- `reduced_transfer_nodes.csv.gz`;
- `reduced_transfer_seed_paths.csv.gz`;
- `graph_validation.json`.

The validation JSON is the machine-readable contract for downstream workstreams. It records source checksums, graph cardinalities, connectivity, restriction counts, anchor counts, path-cache strategy and explicit prohibitions.

## 9. Reproducibility and prohibitions

CI pins the spatial/network Python versions, runs from clean checkout and performs a second materialisation into a temporary directory. Every generated output must be byte-identical to the first run.

Tests fail if:

- the canonical Gate D checksum or graph cardinality changes;
- turn-rule structure differs from 564 / 551 / 535;
- an output checksum changes unexpectedly;
- the directed path matrix loses asymmetry;
- a seed path references an edge absent from the frozen graph;
- a proposed stop appears;
- `np.random`, Python `random`, `requests`, `urllib` or `httpx` are introduced into the materialiser;
- an Overpass endpoint appears in production materialisation code.

This workstream does not select a topology and does not create service-policy variables. It only supplies a reproducible network substrate for the next Phase 2 workstreams.
