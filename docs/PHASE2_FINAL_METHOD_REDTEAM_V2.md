# Phase 2 Final Methodological Red-Team V2

## Verdict

**BLOCKED for final PRIMARY / RUNNER-UP selection.**

This verdict does **not** invalidate the Phase 2 structural search, the current Passenger Utility screening frontier or the S8 opportunity layer as exploratory/screening evidence. It means that the frozen integrated lineage audited here does not yet satisfy the Phase 2 specification strongly enough to authorise a final network recommendation.

Audit target:

- repository: `simoneghezzicolombo/tpl-olgiate-intercomunale`
- integrated branch audited: `phase2-robustness-final-v2`
- frozen target SHA: `864c83accb81c615f9778396408b21e31ca72983`
- audit branch: `phase2-final-method-redteam-v2`
- audit contract: `PHASE2_FINAL_METHOD_REDTEAM_V2`

Machine-readable evidence is in:

- `outputs/phase2/final_method_redteam_v2/findings.json`
- `outputs/phase2/final_method_redteam_v2/final_method_redteam_v2_validation.json`

The audit is intentionally non-decisional. It does not create a weighted score, choose a decision budget, invent an uncertainty band or select a PRIMARY / RUNNER-UP.

## 1. Audit method

The red-team did not treat a green CI job, a `PASS` label or an existing JSON validation file as sufficient evidence. It independently checked code, current artifacts, declared hashes and selected source data.

The reproducible audit runner:

`python scripts/phase2_run_final_method_redteam_v2.py`

performs, among other checks:

1. verification of the structural benchmark counts and reference budget;
2. SHA256 comparison across 33 declared current-file lineage edges;
3. exact lower/upper departure-count bounds around the service-policy budget approximation;
4. independent recomputation of S8 `ALL / SOME / NONE` opportunity classes from the pinned 800,000-row source surface;
5. static scanning for stochastic search, hidden weighted scores, OD downscaling and ridership inference;
6. checks of current-service baseline semantics and the station pedestrian bridge;
7. inspection of Passenger Utility axes and two-stage Pareto semantics.

The regression suite also contains a deliberate strict `xfail` witness for the budget-production issue described in RT-001. It demonstrates on the real design-space contract that `S8_EXTENDED` with H20 has either 55 or 56 explicit departures per route, while the current service-production approximation uses 55.5 equivalent pattern sets per day.

## 2. Summary of findings

| ID | Classification | Severity | Stage | Finding |
| --- | --- | --- | --- | --- |
| RT-001 | METHODOLOGICAL BLOCKER | BLOCKING | Service Policy / Budget → Stage C | Continuous production approximation is used before exact hard-budget eligibility |
| RT-002 | METHODOLOGICAL BLOCKER | BLOCKING | Stage D / final decision | Frozen integrated lineage is not yet final-decision complete |
| RT-003 | IMPORTANT LIMITATION | MAJOR | Current baseline / non-regression | Current lower-bound baseline makes the safeguard non-binding |
| RT-004 | IMPORTANT LIMITATION | MAJOR | Governance / lineage | Narrative governance state is stale relative to frozen artifacts |
| RT-006 | IMPORTANT LIMITATION | MAJOR | Passenger Utility Frontier | Stage C is a screening frontier, not the normative robust passenger-utility ranking |
| RT-011 | IMPORTANT LIMITATION | MINOR | Technical auditability | Production code contains epoch-specific expected cardinalities |
| RT-005 | NON-ISSUE | INFO | Lineage | 33 audited current-file hash edges match |
| RT-007 | NON-ISSUE | INFO | S8 | Missing `SOME` class on Stage C is a real subset property |
| RT-008 | NON-ISSUE | INFO | Station bridge | Pedestrian-only bridge scope is preserved |
| RT-009 | NON-ISSUE | INFO | Passenger Utility Pareto | 5/8/10 axes and two-stage skyline semantics are preserved |
| RT-010 | NON-ISSUE | INFO | Zero-band | Zero eliminations are genuine |
| RT-012 | NON-ISSUE | INFO | OD / leakage | No hidden score, OD downscaling, ridership inference or random search detected |
| RT-013 | ACCEPTABLE ASSUMPTION | INFO | Service policy | Calendars, recovery and extension shares remain explicitly assumptions |

The machine-readable validation currently reports:

- blocking issues: **2**
- major issues: **3**
- minor issues: **1**
- hidden weighted score detected: **false**
- municipal OD downscaling detected: **false**
- ridership inference detected: **false**
- synthetic/random data detected: **false**
- nondeterminism detected: **false**
- lineage mismatch detected: **false**
- audited current-file lineage edges: **33**
- lineage mismatches: **0**
- PRIMARY selection authorised: **false**
- RUNNER-UP selection authorised: **false**

## 3. RT-001: hard budget is not exact before Stage C

### Classification

**METHODOLOGICAL BLOCKER, BLOCKING**

### Affected stage

Service Policy / Budget → Passenger Utility Frontier.

### What the code does

The declared service-production model is:

`annual_bus_km = expected_equal_pattern_set_cycle_km × (span_minutes / headway_minutes) × annual_service_days`

and is explicitly labelled:

`MODEL_OUTPUT_CONTINUOUS_CLOCKFACE_PRODUCTION_APPROXIMATION`

with `exact_departure_count=false`.

For the `S8_EXTENDED_0530_2400` span, the span is 1,110 minutes. Therefore:

- H20: `1110 / 20 = 55.5` equivalent pattern sets/day;
- H60: `1110 / 60 = 18.5` equivalent pattern sets/day.

An explicit timetable cannot operate half a departure. Depending on the clock phase, the actual count is the integer floor or ceiling.

### Real-data reproduction

The red-team recomputed floor/ceiling exact-count annual-km bounds from persisted rows using only:

- declared span;
- headway;
- persisted pattern-set cycle distance;
- annual service days;
- budget cap.

It found:

- **142,290** non-integral departure-count rows on the budget-policy frontier;
- **2,328** budget-policy rows where the hard budget falls between the exact lower and upper count bounds;
- **6,479** non-integral rows that survive to Passenger Utility Stage C;
- **666 Stage-C plans** where the budget cap lies between the exact lower and upper production bounds.

Example:

`P2_3058c75ede542cb2`, `m20pct`, H20, `S8_EXTENDED_0530_2400`, 260 days:

- approximate annual bus-km: **88,817.1067**
- budget cap: **89,135.2**
- exact-count lower bound: **88,016.9526**
- exact-count upper bound: **89,617.2608**

The approximate row is below budget, but one legitimate exact departure count is above it.

A H60 example, `P2_697e52069eb8f42a`, has:

- approximate annual bus-km: **88,495.6871**
- budget cap: **89,135.2**
- exact-count bounds: **86,103.9118–90,887.4625**

### Consequence

The existing Stage-C budget eligibility cannot be interpreted as exact for these plans. More importantly, an approximate budget prefilter can work in both directions near a hard cap:

- retain a plan whose eventual exact phase is over budget;
- exclude an alternative whose exact lower-count phase would have fitted.

Therefore exact timetabling downstream is insufficient if Stage C has already discarded a boundary alternative.

### Required fix

Do not introduce a new heuristic. Instead, before budget-driven candidate elimination for non-integral span/headway combinations:

1. retain a lossless exact-production feasibility envelope across possible phase-dependent departure counts, or enumerate exact departure counts directly;
2. only exclude a candidate when exact feasibility is resolved;
3. rebuild the budget-policy frontiers and Passenger Utility frontier from the corrected safe surface;
4. after exact phase selection, recompute annual production for the selected timetable and verify the same budget cap again.

## 4. RT-002: frozen integrated lineage is not final-decision complete

### Classification

**METHODOLOGICAL BLOCKER, BLOCKING**

### Evidence

At the frozen integrated target SHA:

- `scripts/phase2_run_exact_timetable_optimizer_v2.py` is absent;
- `outputs/phase2/exact_timetable_optimizer_v2/stage_d_exact_timetable_v2_validation.json` is absent;
- Passenger Utility says `exact_timetable_constructed=false`;
- S8 Robust Opportunity says `exact_timetable_constructed=false`;
- zero-band says `final_reliability_proven=false`;
- PRIMARY and RUNNER-UP are still false.

This audit deliberately evaluates the frozen integrated branch requested by the audit contract. Exact-timetable work on another branch is not silently treated as integrated evidence.

### Consequence

The final specification requires:

`hard constraints → robust passenger utility across declared sensitivities → uncertainty-band lexicographic tie-break`

The frozen integrated lineage does not yet contain the evidence needed to execute that final rule, including final missed-connection reliability and exact vehicle-block/timetable evidence.

### Required fix

Integrate independently audited exact-timetable evidence only after RT-001 is resolved at the upstream hard-budget boundary. Then execute the declared robustness tournament and materialise the explicit decision inputs required for a final selection.

## 5. RT-003: current-service non-regression safeguard is too weak to prove real non-regression

### Classification

**IMPORTANT LIMITATION, MAJOR**

### Current artifact, not stale narrative

The current frozen baseline is:

- PDF rows D184+D185: **51**
- historical identities resolved: **20**
- spatially localisable rows: **12**
- unresolved/unlocalised rows: **39**
- localisable physical clusters: **7**
- accessibility lower bound at 5 min: **7.69%**
- at 8 min: **15.03%**
- at 10 min: **19.24%**

The worst-municipality lower bound is **0** at the declared thresholds.

This is intentionally labelled a certified localisable lower bound, not complete current-service access.

### Consequence

A candidate whose worst municipality is at least zero trivially passes this mathematical floor. Therefore the current safeguard is non-binding and **cannot** be described as proving that no municipality becomes worse than the true current service.

### Required treatment

The correct response is not to invent municipality-specific floors. Preserve the lower-bound comparison, but propagate a final-decision caveat that states:

> territorial non-regression has been checked only against the certified localisable lower bound, not against a complete reconstruction of current service.

Resolve additional current stops if stronger real non-regression evidence is required.

## 6. RT-004: governance and narrative snapshot drift

### Classification

**IMPORTANT LIMITATION, MAJOR**

`AGENT_PROTOCOL.md`, requested by the audit brief, does not exist at the frozen HEAD. `COLLABORATION_PROTOCOL.md` exists instead.

`AGENT_STATUS.md` is dated 2026-09-03 and still identifies `phase2-optimizer-core` and an older commit as the integration state. It also describes a next blocker that has already been superseded by later work.

The current baseline numbers in the audit brief are also from an older snapshot. The computational artifact at the frozen SHA is 12 localisable / 39 unresolved and 7.69% / 15.03% / 19.24%, not 20 / 31 and 14.13% / 17.59% / 19.24%.

### Consequence

Narrative governance files are unsafe as the sole audit source. This does not mean the computational lineage is corrupted: the separate hash audit found zero mismatches across 33 tested current-file edges.

### Recommended fix

Refresh governance/status pointers and make every final report cite the validation contract and content SHA of the artifact it describes.

## 7. RT-006: Stage C is screening, not the final robust passenger-utility rule

### Classification

**IMPORTANT LIMITATION, MAJOR**

The current Passenger Utility Frontier is internally consistent with its own no-weight screening contract. The red-team did **not** find a Pareto implementation defect in that contract.

However, its semantics are narrower than the final Phase 2 decision rule:

- `full_gjt_calculated=false`;
- municipal work OD is not downscaled, correctly;
- municipal structural worker-addressability upper bounds enter the Pareto axes;
- population accessibility and several correlated reachability indicators enter separately;
- annual service days and span are global availability axes;
- the 260/312/365 calendars remain assumptions and are not demand-weighted observed calendars.

The Phase 2 specification ultimately requires demand-weighted generalized journey time/accessibility across the declared behavioural/runtime sensitivity set, including waiting, IVT, transfer and reliability effects.

### Consequence

Stage C is suitable as a broad non-dominated screening frontier. It cannot itself justify statements such as “plan X has the highest passenger utility” in the final normative sense.

### Recommended fix

Keep Stage C broad. Do not collapse its correlated axes into a new weighted score. Use the final robustness stage to evaluate supported demand layers and behavioural/runtime sensitivities explicitly before ranking finalists.

## 8. RT-011: epoch-specific cardinalities in production code

### Classification

**IMPORTANT LIMITATION, MINOR**

Static scanning found 14 production checks that hard-code current artifact cardinalities such as:

- 100,000 scenarios;
- 490,962 budget-policy rows;
- 21,237 rows in an intermediate frontier;
- 16,883 Passenger Utility plans;
- 50,115 routes.

These are fail-closed checks, not ranking manipulation, and no current result was invalidated by them.

Their weakness is maintainability: a legitimate refreshed evidence epoch can require source-code edits simply because a cardinality changed.

### Recommended fix

Move epoch-specific expected counts into versioned contracts/manifests while retaining schema, hash and consistency validation in production code.

## 9. Findings that the red-team attempted to prove and could not

### 9.1 No current byte-level lineage mismatch

**RT-005, NON-ISSUE.**

Thirty-three current-file lineage edges were independently SHA256-checked. All matched.

This is distinct from stale narrative/status documentation.

### 9.2 S8 intermediate class is not suppressed by an aggregation bug

**RT-007, NON-ISSUE.**

Direct recomputation from the pinned 800,000-row S8 scenario×timing surface found:

- ALL: **557,161**
- SOME: **1,567**
- NONE: **241,272**

So the code is capable of producing the intermediate class.

Restricting to the **5,345 unique Stage-C scenario×timing keys** gives:

- ALL: **4,275**
- SOME: **0**
- NONE: **1,070**

The promoted 16,883 plan rows give:

- ALL: **13,794**
- SOME: **0**
- NONE: **3,089**

The direct source class and promoted class disagreed on **zero** Stage-C rows. The absence of `SOME` is therefore a property of the Stage-C subset, not a hard-coded aggregation impossibility.

This does not convert route-level `some complete phase` evidence into joint timetable feasibility. The existing warning remains necessary.

### 9.3 Station accessibility bridge does not double count population

**RT-008, NON-ISSUE.**

The bridge is restricted to:

- rail anchor `rail:S01514`;
- official stop `L00407`;
- physical cluster `EX_039`;
- pedestrian access only.

It keeps historical `300407 / EX_011` separate and the catchment union computes one minimum walk value per population unit across anchors. A regression test confirms that presenting the same population unit through both the rail anchor and the official cluster does not count it twice.

No route geometry, runtime, bus-km, OD, S8 evidence or service-policy mutation was detected.

### 9.4 Passenger Utility 5/8/10 and two-stage skyline survive audit

**RT-009, NON-ISSUE.**

The certified wrapper restores both total and worst-municipality 5/8/10 accessibility axes.

The two-stage Pareto decomposition is also mathematically defensible because Stage 1 dominance occurs within a fixed budget/headway/span/calendar context, where the availability values added in Stage 2 are identical. A dominated row within that context cannot become globally non-dominated after those identical values are appended.

Missing directional generalized-access cost is explicitly treated as worse than a finite value, not as zero or best.

### 9.5 Zero-band genuinely removes no plans

**RT-010, NON-ISSUE.**

The zero-width equivalence stage has:

- 16,883 input plans;
- 8,092 multi-plan passenger-equivalence groups;
- zero reduced groups;
- 16,883 survivors.

The result is therefore not an accounting error hiding eliminated plans.

The stage remains provisional because its reliability evidence is pre-timetable. It must not be reused as the final missed-connection/reliability tie-break.

### 9.6 No hidden demand inference or stochastic search detected

**RT-012, NON-ISSUE.**

The source/contract audit did not detect:

- hidden weighted composite score;
- municipal OD downscaling;
- ridership inference;
- `np.random` / random search;
- synthetic search data.

The 1,882 S8 worker reference is used to weight the Milano/Lecco rail directions only. It is not allocated to bus routes and is explicitly not a modal share.

Municipal work OD remains structural municipal addressability, not stop-level passenger assignment.

## 10. Acceptable service-policy assumptions

**RT-013, ACCEPTABLE ASSUMPTION.**

The service-policy design grid correctly labels:

- headways;
- 260 / 312 / 365 annual days;
- 5 / 10 / 15 min recovery;
- scheduled-extension shares

as assumptions/sensitivities, not observed current-service facts.

The assumptions themselves are not a methodological breach. Their final selection would require the downstream evidence described in the specification.

## 11. Repair sequence required before final recommendation

The red-team recommends the following order because it addresses the two blockers without inventing a new decision rule.

### 11.1 Repair hard-budget exactness upstream

For every non-integral span/headway context, preserve all phase-dependent exact departure-count possibilities until budget feasibility is known exactly. Rebuild:

1. service-policy/budget feasibility;
2. budget-policy Pareto frontiers;
3. Passenger Utility Stage-C frontier;
4. dependent S8/continuity/Stage-D packaging.

The corrected process must demonstrate that no potentially budget-feasible alternative was pruned by the continuous production approximation.

### 11.2 Integrate and audit exact timetable evidence

After the corrected upstream frontier is frozen:

- construct explicit trips;
- verify annual bus-km from those trips;
- phase route-specific timetables against the verified S8 events;
- calculate exact vehicle blocks for the declared recovery sensitivities;
- retain the distinction between public passenger returns and technical vehicle closures.

### 11.3 Complete the normative robustness rule

Before PRIMARY / RUNNER-UP:

- run the declared walk, wait, bus-IVT, runtime/dwell, recovery and rail/bus delay sensitivities;
- calculate final missed-connection/reliability outcomes;
- use supported demand evidence only at its actual spatial resolution;
- materialise the decision budget as an explicit input;
- materialise a substantive uncertainty-band rule as an explicit decision input, rather than inventing one inside the optimiser;
- apply the lexicographic practical tie-break only within that band.

### 11.4 Preserve the current-baseline caveat

Do not invent a stronger municipality floor. Either improve the current-service spatial reconstruction or explicitly state that the non-regression test is against a conservative localisable lower bound only.

### 11.5 Refresh governance state

Update the status/protocol pointers so later reviewers do not mix old baseline counts or old branch names with the current computational lineage.

## 12. Final red-team conclusion

The red-team found **no evidence that Phase 2 is synthetic, random, secretly weighted or silently downscaling municipal OD**. Several suspicious components survived attempted falsification: the S8 `ALL/NONE` split is genuine on the Stage-C subset, the station bridge is pedestrian-only, the Passenger Utility two-stage skyline is internally coherent and the audited byte-level lineage is consistent.

The pipeline nevertheless remains **BLOCKED for final network selection** for two reasons:

1. the hard annual bus-km constraint is currently applied through a continuous production approximation before exact phase-dependent departure counts are known, with **666 surviving Stage-C plans demonstrably straddling a budget boundary**;
2. the frozen integrated lineage does not yet contain the complete exact-timetable/reliability/robust-utility evidence required by the normative final decision rule.

Until both are resolved and the dependent frontier is rebuilt, `primary_selection_authorised=false` and `runner_up_selection_authorised=false` are the only defensible final-selection states.
