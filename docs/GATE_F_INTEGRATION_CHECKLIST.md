# Gate F integration checklist

Gate F is intentionally designed so most final work is mechanical once B/C/D/E are validated. This checklist is the remaining closure path.

## 1. Freeze the integration candidate

- record the integration/release-candidate commit;
- preserve the authoritative PASS evidence for Gates A-E;
- do not mix metrics generated from incompatible upstream revisions.

## 2. Freeze the scenario universe

- one scenario catalog with stable `scenario_id` values;
- exactly one current-service baseline;
- serious non-figure-8 alternatives retained rather than silently omitted;
- Gate D road-feasibility row for every catalog scenario;
- inspect the topology-diversity warning as an audit prompt, not as a scoring rule.

## 3. Validate fragments before assembly

For B/C/D/E verify:

- no duplicate/unknown/missing eligible scenario IDs;
- epistemic status and source for every metric;
- exact canonical units;
- exact metric semantics;
- identical comparison basis across scenarios;
- finite uncertainty bounds for every objective classified `ESTIMATE` if a definitive recommendation is desired.

## 4. Assemble and fingerprint

Run `scripts/gate_f_build_inputs.py`. Inspect:

- canonical scenario table;
- explicit Gate D exclusions;
- assembly manifest hashes;
- baseline ID;
- eligible/excluded ID lists;
- comparison-scope audit.

No manual CSV editing is allowed after manifest generation.

## 5. Build upstream status evidence bundle

Create a schema-v1 bundle following `schemas/gate_f_status_bundle.schema.json`. For A-E include full commit SHA, source branch and SHA256 of authoritative evidence file(s). A manually typed PASS cannot substitute for this bundle.

## 6. Run Gate F

Run `scripts/13_gate_f_pareto.py` with canonical metrics, assembly manifest and verified gate-status bundle. Inspect all outputs, not just the exit code:

- point Pareto frontier;
- interval-robust Pareto frontier;
- leave-one-objective-out robustness;
- dominance-pair audit;
- trade-offs versus baseline;
- epistemic audit;
- metric contract;
- final verdict.

## 7. Substantive review before final PASS

Even a green pipeline is insufficient. Confirm that:

- coverage and S8 percentages use substantively meaningful denominators;
- the rate-equivalent frequency metric is not described as max gap/wait;
- road-infeasible scenarios were excluded for defensible Gate D reasons;
- scenario search did not cherry-pick only figure-8 variants;
- a unique robust dominator, if present, remains credible under upstream uncertainty;
- if multiple robust Pareto scenarios remain, Gate F reports the trade-off instead of inventing a winner.

Only after these checks can the workstream move from PROVISIONAL to a final Gate F verdict.
