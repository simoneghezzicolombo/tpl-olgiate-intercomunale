# RT-031 reciprocal open-corridor search

## Decision result

The bounded reciprocal-corridor pool does not establish a broad-access replacement
for the exact-ID Current-Service V4 structural subset. The current subset is no
worse on all six RT-028 access/equity dimensions than every one of the 22,220
distinct reciprocal availability sets evaluated.

This is a useful stopping result for this candidate family, not a selection of the
current network and not a global impossibility proof. The open-path search stopped
at its declared 250,000-state execution limit with 750,628 heap entries pending.

## Certified comparison

- 71,339 bounded open physical paths were retained.
- 398 endpoint pairs had both directions represented.
- 5,412,651 opposite-direction path pairs fit the shared 13,391.7067 m physical
  distance budget.
- These pairs produced 22,220 distinct stop-identity availability sets.
- Zero sets were no worse than the current exact-ID subset on all six dimensions.
- The current subset was no worse than all 22,220 sets.
- Even the componentwise maxima, which may come from different candidates, were
  below the current subset on every dimension.

The comparison uses one identical RT-028 population/walking substrate on both
sides. Current stops are bridged only by exact official native stop identity; no
name, coordinate, fuzzy or nearest-neighbour mapping is admitted.

## Contract boundaries

The two directions are independently declared physical paths. Pairing them does
not infer a vehicle turn, passenger continuity, a transfer, route identity,
boarding rights, timetable service or public operation.

Availability is guaranteed only at stop-identity level. It is not a guarantee of
a directional occurrence, ordered service event or feasible passenger journey.
The search retains each full ordered realization witness and replays it through
the full-history transition oracle. Its compact label state is admissible only
under the pinned history-locality certificate for the frozen RT-023 atomic domain;
it makes no claim for new carriers or another restriction universe.

No weighted score or uncertainty band is used. No primary or runner-up selection
is authorised.

## Reproducibility

GitHub Actions run `34864124573` completed successfully at commit
`9064007f977737f042943db8bb04c732873216d3`. Two full executions were byte-identical.
Artifact `10357161018` has ZIP digest
`sha256:c473f9214b735126a433d20d407fb49879e75043451aa50088b012a75f5201c5`.
The committed audit is subsequently strengthened with explicit restriction-state
and stop-occurrence semantics and re-certified by the next run.

## Operational conclusion

Do not promote the bounded reciprocal open-corridor family to service-network
finalists. The remaining productive direction is a genuinely multi-line network
candidate domain with typed ordered service events and explicit passenger transfer
relations. That later domain must still beat the same current structural reference
and remains non-decisional until separately authorised.
