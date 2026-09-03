# Phase 2 decision contract handoff

Workstream: `phase2-decision-contract-hardening`

Verdict: **PASS**

Validated branch HEAD: `952045bc905602c31407a1507ad0700819f1bd0b`

CI: GitHub Actions run `33781891674`, job `100737322133`, SUCCESS.

The finalizer now requires an explicit positive finite decision budget that matches exactly one materialised budget envelope within the declared numeric tolerance. The previous implicit `max(budgets)` fallback is removed. `--decision-budget-km` is CLI-required. The uncertainty band remains explicit and mandatory.

Candidate, sensitivity, frontier and budget metrics now reject NaN/infinity. Invalid budget envelopes are rejected rather than silently dropped.

No route, stop, service policy, budget choice or recommendation was materialised by this workstream.
