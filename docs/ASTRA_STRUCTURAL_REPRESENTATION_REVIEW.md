# ASTRA structural representation review — 2026-09-06

Verdict: **REPRESENTATION CHANGE REQUIRED**.

The change concerns the use of elementary stop-to-stop edge count as a search-complexity limit. RT-019's primitive graph remains defensible as an index of admitted corridor evidence. Replacing that entire graph with a road-junction graph is not justified by the present evidence. Adopt an embedded service multigraph with reversible macro chains, directed road-carrier occurrences and a separate passenger-stop layer. Extend RT-031 / Issue #79; no duplicate Gate number is needed.

## Evidence and limits

Read in order: Issue #1, #69, #75, #74, #79 and the current RT-031 documentation, followed by the narrow upstream interfaces. RT-029 final acceptance supersedes stale pending-review wording still present in its issue body. This review does not repeat its full numerical audit.

RT-029 V4 at `1aab6c7014cd32dfa067b1174cfdaa1654a5e3cd`, run `34044402524`, artifact `9992669914` is accepted for complete E4/E5/E6 evaluation: 112,843 structures, 9,454 decision stop sets, 481 Pareto-union members, all 7–9 stops. Its burden is a lower envelope of realization distances, not bus-km or a timetable. Its reduction is objective-specific.

RT-030 at `37873b8a8c693234603281283eec8ad88802fb7f`, run `34043902080`, artifact `9992507233` establishes 267 endpoint-only and 21 intermediate-stop realizations among 288. Only two distinct additional stop identities occur globally. For connected structures, V <= E+1; hence N <= E+3 in this frozen corpus. E<=6 therefore implies N<=9 regardless of the Pareto algorithm. This is a structural restriction, not evidence that nine stops is optimal or inadequate for every possible service.

RT-031 has advanced beyond the previous chat: canonical head `62f241d4df89585cd9dad6965ba866e28c91128d` includes a 35-vertex Hamiltonian PATH and CYCLE diagnostic. GitHub run `34049973223` is SUCCESS at that exact head; artifact `9994241222` API digest is `sha256:a995681269f4607fb17393b77927e1644abe269aab2e10d37219d946084b256b`. This review checked run/artifact metadata and source; it did not independently download and rehash this ZIP. The earlier lossless contraction diagnostic at `af58cfd...`, run `34047175234`, artifact `9993459525`, preserves 672,806 elementary-link memberships. Both remain diagnostics. Neither proves continuous road-level composition, operability, route optimality or search completeness.

**Demonstrated:** the old cap mathematically restricts passenger-stop count; the frozen reciprocal graph is structurally capable of larger simple paths; existing contraction preserves elementary chains.

**Architectural inference:** topology should be measured on the selected service skeleton modulo ordinary degree-2 subdivision, with geometry and operational descriptors alongside it. There is no justified single scalar complexity score. Counted branches/cycles, length and directness answer different questions.

**Open:** valid concatenation of actual directional alternatives, route decomposition, physical overlaps, repeated traversal semantics, full D184/D185 road geometry calibration, and a prospective bounded search/completeness contract. A Hamiltonian witness supplies no reason to serve all 35 stops.

## Alternatives assessed

| Alternative | Value / reuse | Limitation / judgment |
|---|---|---|
| Keep RT-019 graph but cap E | Maximum reuse, valid scoped diagnostics | E measures segmentation; unsuitable as a silent general design-complexity limit |
| Contract only global road degree-2 nodes | Optional exact RT-017 acceleration | Ordinary road intersections remain even when the bus simply passes through; road degree is not service branching. Restrictions require directed transition state |
| Global structural junction graph | Records real intersections without named anchors | Counts unused junctions; geographic crossing need not be a service connection; cannot alone define route complexity |
| Abstract macro corridors without embedded paths | Compact, reuses RT-031 | Can hide prohibited turns, directional incompatibility, overlap and detours; insufficient alone |
| Independent ordered road routes only | Preserves direction, geometry and stop-independent paths | A single trip order is always a sequence; by itself it hides network branches, overlap and transfers |
| Embedded service multigraph + directed carrier + stop occurrences | Reuses RT-031, RT-017, RT-023 and RT-030; admits many stops on a simple skeleton | Recommended; needs composition proof and explicit service/network semantics before search |

Do not identify candidates solely by PATH/TREE labels or degree signatures: non-isomorphic graphs and different embedded routes can share descriptors. Preserve full multigraph incidence, parallel edges, self-loops, canonical cycle handling and expansion mappings. Graph leaves and canonical cycle origins do not establish operational termini.

## Concrete diagnostic

Run `python scripts/astra_structural_representation_diagnostic.py`. It reuses `contract_structure` from existing RT-031; no second contraction implementation or territorial search is introduced. Output: `outputs/phase2/astra_structural_representation/diagnostic.json`.

Controlled checks cover two-to-fifteen subdivision invariance, stop annotations on one carrier, branch and cycle sensitivity, reversed input order, unknown/disconnected directed paths and a join-turn counterexample. A geometrical detour is deliberately still PATH: length changes from 100 to 180 fixture metres. Requiring every detour to change cycle rank or branch count would itself be a contract error. These lengths and graph examples are labelled controlled fixtures, not territorial data. The pair-turn prototype illustrates the interface only; production requires enough history for via-way restrictions.

Real calibration consumes frozen D184 pattern 1 (13 stops) and D185 pattern 13 (14 stops), preserving exact ordered IDs. Their stop-sequence skeletons both contract to one PATH edge with zero branches/cycles. This proves sequence representability only. Inferring physical topology from an ordered stop list would be circular; acceptance C remains open until certified road-carrier evidence is supplied. Historical GTFS IDs in this calibration must not replace the frozen operational stop inventory.

The benchmark's 13.5 trip-weighted median is descriptive. The approximately 522 m figure is explicitly **geodesic inter-stop distance**, not routed spacing. Neither becomes a target. A small primary-source check confirms conceptual separation: [TTC May 2024 standards](https://cdn.ttc.ca/-/media/Project/TTC/DevProto/Documents/Home/About-the-TTC/Projects-Landing-Page/Transit-Planning/Service-Standards_May-2024.pdf?rev=6c96a85cc0a64147ad424f949dabce64) separately discuss system structure/directness and surface stop spacing (sections 2.2 and 2.4); [TransLink guidelines](https://www.translink.ca/-/media/translink/documents/plans-and-projects/managing-the-transit-network/transit-oriented-communities/transit-services-guidelines-public-summary.pdf) distinguish routing directness/deviations from stop spacing. These sources support separation, not our particular algorithm or a numerical stop constraint.

## Exact next actions

The machine-readable contract is `config/astra_structural_representation_contract.json`. It is a proposed production Gate, not a claimed production PASS.

**Alpha:** extend RT-031 with an embedded service representation and a bounded composition adapter. First preserve the full macro multigraph and exact ordered directed road-edge occurrences, including repeated/shared segments. Build a lazy compatibility relation between RT-023 alternatives using RT-017 transition evidence; fail closed on unknown boundaries. Retain feasible alternatives without selecting independent minimum-distance fragments. Compose RT-030 occurrences with direction and provenance; do not introduce transfers at elementary-link boundaries. Distinguish available stops from an explicitly served pattern. Recompute exact guaranteed/possible sets only over the certified complete feasible realization domain; empty domains must not create vacuous guarantees. Component-wise intersections can be conservative bounds, but may cease to be exact after compatibility filtering.

Before territorial search, declare domain, candidate identity/equivalence, route decomposition, repetition semantics, directionality, admissibility and stopping/completeness. A simple structural subgraph of the frozen graph gives a finite scoped domain but does not cover every road walk or service design. A solver time cap means INCOMPLETE. Do not infer an elementary or macro complexity cap, a PATH-only prior, named anchors or an all-stop requirement. Completeness within RT-021's admitted corridor corpus is not global road-network completeness.

**Antigravity:** independently audit the proposed adapter with subdivision, branch, pure-cycle, parallel-edge, shared-path, forbidden boundary turn, via-way restriction, asymmetric direction, unknown transition and empty-compatible-domain cases. Require exact expansion and occurrence conservation. Check that a stop lying on another carrier remains excluded. Complete D184/D185 physical calibration only using certified geometry/path evidence with historical-stop mapping and uncertainty; if unavailable report OPEN, retaining the sequence-only result. No copying the real lines into the candidate generator. Report production acceptance A–F individually; this review claims no full A–F production certification.

Preserve RT-017, directional corridor evidence, RT-028 for the same stops/population, RT-030 attachments, population/ISTAT identity and municipal OD at its supported scope. RT-030's current 288-row production adapter requires separately certified generalization for new carriers. Future FIELD_CHECK_PENDING stops need independent eligibility, attachment and walking-matrix extension; create none here. Keep RT-029 frozen as diagnostic evidence. Issue #74 remains visible explanation/counterfactual work without automatic repair. Keep budget and uncertainty caller-declared, selection flags false, and no OD allocation, full demand-weighted GJT, empirical missed probability or weighted score.

No new full search or CI workflow is needed for this bounded review. Local diagnostic evidence is persisted; no new Actions run/artifact is claimed.
