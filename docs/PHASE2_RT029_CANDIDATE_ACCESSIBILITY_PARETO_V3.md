# Phase 2 RT-029 — 88-candidate accessibility evaluation and Pareto shortlist V3

## Role

RT-029 is the Alpha-owned downstream compiler authorised by RT-028. It does not reroute pedestrians and does not alter the frozen network structures. It composes certified evidence from:

- RT-022: 88 topology-neutral 5-vertex / 4-link structures;
- RT-023: independent directed link realizations and exact ordered passenger-stop sequences;
- RT-028: atomic border-neutral `population unit × final stop` pedestrian travel times.

The workstream tracker is GitHub Issue #69.

## Frozen upstream lineage

| Layer | Identity |
| --- | --- |
| RT-022 | persisted commit `1c10837486a339b8fc21dc0638f45edcb547f04d`; artifact `9988386073`; digest `sha256:1cab2e18eec4920cbdb348d0d9cd224c7516f8d62bc63b0eacf2a91f6fb134d7` |
| RT-023 | certified run `34034770563`; head `0d9a82caa1d1d624e0f6945e709f3548785fb8dc`; artifact `9989805162`; digest `sha256:d206af90c247f87940f51db17e5497183199cceb9070e84124c0ef3b5ddba981` |
| RT-028 | certified run `34037985015`; head `8a926234b8635aa48db4b80a61fb293be35f74f2`; artifact `9990832031`; digest `sha256:f09bfa9fb8d7aeacc9c7b80f4bc17dff5c4ce391e6a16c25bc0afd973e509415` |

CI verifies the upstream Actions artifact digests and run head SHAs before evaluation. Input file SHA256 values are then embedded in the RT-029 audit.

## Stop-set semantics

A structural candidate does not identify one unique RT-023 corridor realization. Using the union of every stop appearing in every alternative would therefore overstate guaranteed accessibility.

RT-029 materializes three nested scenarios:

1. `VERTEX_ONLY`: the five RT-022 structural vertices.
2. `GUARANTEED_RT023`: the vertices plus, for every required link-direction component, only passenger stops appearing in the **intersection** of all its RT-023 alternatives. This is the decision-eligible accessibility scenario.
3. `POSSIBLE_RT023`: the vertices plus the **union** of alternative stops. It is an optimistic diagnostic envelope only and is prohibited from Pareto screening.

All automatically evaluated stops must map to `CONVENTIONAL_TPL` in RT-028. The single frozen `SPECIAL_SERVICE` identity is retained upstream for completeness but cannot enter RT-029 automatically.

## Population accessibility

For a candidate stop set, RT-029 takes each population unit's minimum certified reachable RT-028 walking time to the selected stops. A unit with no reachable selected stop remains explicitly unreachable.

The 5/8/10/12-minute shares retain unreachable population in the denominator. This prevents a candidate from appearing stronger merely because difficult origins disappear from a reachable-only subset.

Reachable-only walking-distribution diagnostics are reported separately:

- weighted mean;
- weighted median;
- weighted P90;
- weighted P95.

Results are produced for `ALL`, `CORE` and `EXTERNAL`. The same threshold shares are also computed separately for each core municipality.

## Municipal equity

For every frozen threshold and candidate/scenario RT-029 reports:

- minimum core-municipality accessibility share;
- maximum core-municipality accessibility share;
- max-minus-min municipality share gap.

External spillover never substitutes for a weak core municipality.

## RT-023 realization-burden envelope

RT-029 does not choose one corridor alternative. For each of the candidate's four links and both directions, it sums component-wise minima and maxima for:

- `distance_m`;
- `running_minutes_model`.

These quantities are topology-neutral lower/upper link-realization burdens. They are not timetable cycle times, annual kilometres or operating costs.

## Pareto semantics

There is no weighted composite score and no total ordering.

Four independent Pareto frontiers are computed on `GUARANTEED_RT023`, one for each frozen threshold 5/8/10/12. Each frontier:

- maximizes core reachable population share;
- maximizes the threshold-specific core accessibility share;
- maximizes the minimum core-municipality threshold share;
- minimizes reachable-population weighted P90 walking time;
- minimizes minimum bidirectional link-realization distance.

The RT-029 shortlist is the set union of candidates nondominated on at least one threshold-specific frontier. `frontier_membership_count` is descriptive membership information, not a rank.

RT-029 **does not select PRIMARY or RUNNER-UP**. A later decision layer still needs any additional operational, timetable, demand and policy evidence required by the final decision contract.

## Outputs

- `rt029_candidate_stop_sets_v3.csv`
- `rt029_candidate_accessibility_summary_v3.csv`
- `rt029_candidate_core_municipality_accessibility_v3.csv`
- `rt029_candidate_core_equity_v3.csv`
- `rt029_candidate_operating_envelope_v3.csv`
- `rt029_pareto_frontiers_by_threshold_v3.csv`
- `rt029_pareto_shortlist_v3.csv`
- `rt029_candidate_accessibility_pareto_audit_v3.json`

The workflow performs focused red-team tests, a real 88-candidate run and a byte-for-byte deterministic rebuild before uploading the artifact.
