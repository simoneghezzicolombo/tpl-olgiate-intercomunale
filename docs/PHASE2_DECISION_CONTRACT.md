# Phase 2 final decision contract

This document hardens the final selection boundary before any V2 passenger-utility result is available.

## Caller-declared budget

`decision_budget_km` is a mandatory policy input. It has no implicit default and is not inferred from the largest materialised budget envelope.

The caller-provided value must be finite, positive and match exactly one materialised `annual_bus_km_cap` within the declared numeric tolerance in `scripts/phase2_finalize_tournament.py`. The matched envelope value is then used as the canonical decision budget.

The validated D184+D185 production reference of 111,419 bus-km/year may be used as the primary normative budget only when the caller explicitly selects the corresponding materialised envelope. Higher and lower envelopes remain sensitivities unless explicitly selected.

## Uncertainty

`uncertainty_band_min` remains mandatory. It must be finite and non-negative. No default practical-equivalence tolerance is introduced.

## Fail-closed numeric semantics

Candidate utility, reliability, retained-stop share, annual bus-km, sensitivity values, frontier tolerance and budget values must be finite. `NaN` and infinities are rejected rather than entering Python comparison/sorting semantics.

Invalid budget envelopes are rejected. They are not silently filtered from the frontier.

## Ranking semantics

The final order remains:

1. hard eligibility;
2. robust demand-weighted GJT improvement;
3. explicit uncertainty band;
4. the documented lexicographic tie-break.

The stable candidate ID is the final deterministic tie-break only after substantive tie-break dimensions are exhausted. No weighted composite score, hidden imputation, random ordering or first-row-wins rule is introduced.

## Scope

This contract changes no route, stop, timetable, headway, fleet assumption, demand metric or recommendation. It only ensures that later V2 evidence cannot be converted into a primary/runner-up recommendation through an undeclared budget or non-finite numeric shortcut.
