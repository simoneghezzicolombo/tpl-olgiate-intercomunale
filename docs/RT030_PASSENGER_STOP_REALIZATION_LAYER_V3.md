# RT-030 certified passenger-stop realization layer V3

## Status and ownership

RT-030 is an atomic **Agent A / Antigravity** workstream between RT-023 and RT-029. It compiles passenger-stop evidence once for the 288 certified RT-023 directional realizations. It does **not** compose or evaluate the 112,843 E4+E5+E6 structures, calculate RT-028 accessibility, run Pareto analysis, select a network or modify Alpha/GPT's RT-029 branch.

## Purpose

RT-023 used the frozen RT-018 exact-node occurrence semantic. That was internally consistent but incomplete in a small number of cases because the nearest certified graph node can attach a stop to a side/service node even when the stop itself lies on the physical road segment actually traversed by a realization.

RT-030 preserves the RT-018 node evidence and adds one route-independent supplemental attachment:

1. freeze the final 36-stop layer, exactly 35 `CONVENTIONAL_TPL` plus the excluded `SPECIAL::CASA_DI_COMUNITA_OLGIATE`;
2. for every frozen stop, find its globally nearest **physical bus-graph segment** in the complete frozen RT-017 graph;
3. collapse directional F/R edge duplicates to one unordered topological segment with a deterministic canonical node orientation;
4. materialize a conventional stop for a realization only when either its certified RT-018 attachment node is on the exact ordered path, or its globally nearest physical segment is exactly traversed by that ordered path;
5. never use distance from stop to candidate route as an eligibility rule.

`route_proximity_buffer_m = 0.0`. The stop-to-segment distance is retained only as provenance and audit evidence.

## Frozen upstream

- RT-023 final certification commit: `2e8baf13ea4171164bc8c4b18d4b31bee4c3003d`
- RT-023 certified run: `34034770563`
- RT-023 artifact: `9989805162`
- RT-022 artifact: `9988386073`
- RT-017 deterministic replay artifact: `9972204236`
- graph epoch: `RT017::2026-09-05T13:45:50Z::466f562f95805cb1`
- graph-node artifact SHA256: `2ab72595b7c52d8a08ccf767a20a9a5fc00b39552b37da01a53f270467a4ca06`
- graph-edge artifact SHA256: `466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19`
- elementary-corridor SHA256: `7798f41b238dc818c76f4a440b4fc16203f4bb1e710f40394816399b39adf76c`
- stop-attachment SHA256: `30d64ff20e9b89c31f7878c415dd4c6bb5a0d10f51b24d041e4deb4d57e6571b`
- corridor-stop-occurrence SHA256: `6de033c008a5b4db9a44ad31652aea8276a3b588239fbd2e2d7c23b2e88add97`

## Explicit RT-023 lineage reconciliation

GitHub Actions run `34034770563` executed at commit `0d9a82caa1d1d624e0f6945e709f3548785fb8dc` and produced the 17-column realization catalog with SHA256:

`a33b24664f9cd416f16989c7a66a668a3e90a83244dd3662cac735751532adc5`

The final RT-023 commit `2e8baf13ea4171164bc8c4b18d4b31bee4c3003d` added exactly three frozen provenance columns:

- `rt021_elementary_corridor_evidence_sha256`
- `rt018_stop_attachment_layer_sha256`
- `rt018_stop_occurrence_corpus_sha256`

RT-030 reconstructs those columns from the independently hash-locked RT-022 inputs and fail-closes unless the resulting canonical catalog SHA256 is exactly:

`24d806b3b30cf75c91cf531746bada443bf3d5bedf3878e9587778cad7c9d36a`

This proof is written into `rt030_audit.json` under `rt023_lineage_reconciliation`.

## Canonical outputs

The workflow artifact contains:

- `rt030_realization_passenger_stop_patterns.csv`
- `rt030_realization_stop_occurrences.csv`
- `rt030_frozen_stop_physical_segment_attachments.csv`
- `rt030_diagnostics.csv`
- `rt030_audit.json`

The global attachment table preserves stop identity, certified RT-018 node and distance, canonical physical segment identity, OSM way, road class, stop-to-segment distance, uniqueness/tie evidence and eligibility.

The occurrence table preserves realization ID, structural link, direction, pair, corridor, ordinal stop position, exact path hashes, certified RT-018 node/distance, canonical physical segment, traversed directed edge when supplemental evidence is used and the precise materialization reason.

## Certified territorial result

The production run must fail closed unless the frozen corpus produces exactly:

- **288 realizations**
- **267 endpoint-only realizations**
- **21 realizations with one intermediate passenger stop**
- **597 stop occurrences**
- **21 recovered intermediate occurrences**
- **0 ambiguous stop-to-segment attachments**

Recovered intermediate stop identities:

- `ASF::CALCO_LARGO_POMEA`
- `ASF::OLGIATE_MOLGORA_SCARPONE`

The complete 36-stop stop-to-segment distance distribution is embedded in the audit. No distance threshold is used as a route-capture policy. On the frozen corpus the observed maximum is `6.425006533 m`, for `FROZEN::300634`; median is `1.916677678 m` and p90 is `5.255183699 m`. There are no unresolved ambiguous attachments and no attachment outliers requiring a fail-closed exclusion in this frozen corpus.

## Negative assertions

The audit explicitly asserts `false` for:

- `route_geometry_modified_for_stop_capture`
- `proximity_buffer_used`
- `field_check_pending_promoted`
- `special_service_promoted`
- `network_candidate_selected`
- `pareto_or_ranking_performed`
- `passenger_stop_count_target_used`
- `rt030_claims_sparse_network_problem_resolved`
- `accepts_old_43_stop_universe`
- `promotes_structural_vertex_without_stop_evidence`
- `reverses_opposite_direction_instead_of_compiling_it`
- `uses_np_random`
- `uses_synthetic_territorial_evidence`

## Mandatory controlled tests

CI runs exactly 14 adversarial tests covering waypoint promotion, exact-node evidence, near-parallel-road rejection, directional independence, ordering, special-service exclusion, field-check exclusion, row-order invariance, byte determinism, graph/path mismatch, old 43-stop rejection, zero route buffer and fail-closed RT-023 hash reconciliation.

CI then performs two independent production rebuilds from the frozen GitHub artifacts and compares all five outputs byte-for-byte before uploading the certified artifact.

## Interpretation boundary for RT-029

RT-030 proves that endpoint-only RT-023 materialization was incomplete in 21 occurrences. It does **not** prove that the structural candidate universe now represents realistic full passenger networks. The certified realization corpus remains overwhelmingly sparse: 267 of 288 directional realizations are genuinely endpoint-only under the corrected evidence rule.

**RT-030 is required downstream evidence, but it does not justify treating E4/E5/E6 as realistic full passenger networks merely because passenger-stop materialization has been corrected. The certified corpus remains overwhelmingly sparse at realization level.**

Any finding in RT-029 that nondominated structures still contain only about 5–7 passenger stops must be reported as evidence about the structural representation, not repaired by inventing stops inside RT-030.
