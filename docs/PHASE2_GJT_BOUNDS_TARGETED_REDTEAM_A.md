# Phase 2 GJT bounds targeted red-team A

This is a deliberately small independent review layer for Alpha's `phase2-gjt-set-bounds-exact-v3` work. It is not a competing GJT implementation and is not a new mandatory Phase 2 blocker.

The precheck validates only the mathematical admissibility of reusing the historical 243-case feeder generalized-access grid as monotone assumption-sensitivity axes. The historical feeder formula contains `uniform_headway/2` and is explicitly `ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL`; therefore that waiting assumption is forbidden in the exact set-bounds artifact. Origin waiting remains unidentified unless separate evidence is introduced.

For fixed non-negative exact-timetable components, the exact-bound sensitivity form may use the historical ranges for bus-IVT weight, walk weight, wait weight, transfer penalty and station-transfer walk only if the feasible itinerary set is independent of those coefficients and no coefficient-dependent threshold or pruning changes feasibility. Under those preconditions, each itinerary cost is coordinate-wise non-decreasing, the pointwise minimum across feasible itineraries is also non-decreasing, and min/max across population units remain non-decreasing. Consequently the lower and upper corners of the finite 243-case grid are exact extrema. The accompanying deterministic brute-force oracle checks this property with itinerary switching deliberately present.

The final review is intentionally deferred until Alpha publishes the exact builder and evidence. It will check only: no worker allocation or population-demand weighting, no H/2 or departure-time imputation, reconstructible min/max witnesses, exact `selected_timetable_id` lineage, public in-span BUS→RAIL semantics, no technical-return passenger service, no target rebinding, direction-conditioned evidence where necessary, and no claim of full expected demand-weighted GJT or final ranking.

A PASS of this precheck does not certify Alpha's final bounds. It certifies only the corner-envelope shortcut under the stated preconditions.
