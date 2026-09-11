# Approved budget and exact resource screen

## Correction to earlier handoffs

`config/phase2_final_policy_contract_v3.json` already records the human-approved
111,419 annual bus-km cap, no global scalar uncertainty band, preference for H<=30
and a reporting-only role for existing-service continuity. These are not missing
user decisions. Earlier generic handoff statements that the budget still needed
to be chosen were stale. No new approval is requested or inferred here.

The same contract does not require full demand-weighted GJT or empirical
missed-connection probabilities for its deterministic V3 decision pathway.
Missing evidence must still be reported without probabilistic overclaims.
The new territorial representation/search/calibration boundary remains open.

## Necessary production bound

For a declared complete cyclic movement with minimum certified distance d, a
phase-specific departure count n and an explicitly assumed calendar D, annual
carrier kilometres have lower bound d*n*D. Positive depot/repositioning costs
can only increase that number. Therefore, if the smallest phase-specific bound
already exceeds the approved cap, no choice of speed, fleet or recovery can
make that declared production fit the kilometre budget.

The runner consumes freshly rebuilt exact complete-route distances. It checks
three closed stress scenarios (path repeating out-and-return, cycle forward,
cycle reverse) across the existing 4 headways, 2 spans and 3 assumed calendars:
72 contexts. These are declared movement-production obligations, not assertions
of actual service, boarding permissions or the optimal territorial network.

Integer-minute phases 0..H-1 are all enumerated in the half-open departure
window [start,end), consistent with the existing exact timetable convention.
Each departure incurs a complete cycle, including returns after the final
in-window departure. This avoids the RT001 continuous span/headway undercount.
For example, 1,110 minutes at H20 produces 55 or 56 departures depending on phase.
No timetable phase is selected. Recovery and running time remain unresolved.

The calendar grid remains explicitly hypothetical (260/312/365 days); it is
not the observed calendar. A within-cap distance bound would not certify
operational feasibility. Rejection applies only to the declared complete order,
movement obligation, headway/span/calendar; it does not exclude every possible
all-stop route or justify removing a specific stop.

At H30, 06:00–22:00 and the least demanding 260-day grid calendar, the cap permits
at most 111419/(32*260) = approximately 13.392 km per complete operated cycle
before any extra vehicle movement. At H60 the analogous ceiling is 26.783 km.
These thresholds guide the next search; they are not arbitrary stop-count caps.

Reproduce after the pinned real route runner:

```
PYTHONPATH=. python scripts/phase2_screen_rt031_resource_budget_v3.py --routes ROUTES/complete_route_evaluation.json --out OUTPUTS
```

CI artifact: `rt031-exact-resource-budget-screen-v3`. Full exact context outputs,
source policy hashes, phase counts and limitations are retained. Exact run and
results are reported on #79 after execution.
