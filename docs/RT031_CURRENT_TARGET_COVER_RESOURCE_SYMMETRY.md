# RT-031 current-target resource symmetry

## Corrected question

The earlier broad-pool screens asked whether one or two short generic physical
movements could match the static walking-access envelope of the Current-Service
V4 exact-ID subset. They did not establish that D184/D185 were optimal.

This audit asks the narrower but resource-symmetric feasibility question: what
minimum physical distance was found for up to three closed movements covering
all 11 current stop identities actually used by the common RT-028 substrate?
The resulting portfolios are evaluated separately at H30 and H60 under the same
111,419 annual bus-km cap, 960-minute design span and 260-day design calendar.

## Found witnesses

The bounded search found no one-movement cover, but found both two- and
three-movement covers:

| Maximum movements | Found distance | H30 annual km | H60 annual km | Access versus current exact subset |
|---:|---:|---:|---:|---|
| 2 | 15.450427 km | 128,547.555 — over cap | 64,273.777 — within cap | no worse on all six; strictly better on total 5/8/10 |
| 3 | 11.929500 km | 99,253.441 — within cap | 49,626.720 — within cap | no worse on all six; strictly better on total 5/8/10 |

For the three-movement H30 witness, the approved-cap residual is approximately
12,165.559 km/year. Its total/core walking-access shares change from current
21.7376%, 38.7287%, 48.7696% at 5/8/10 minutes to 23.1947%, 39.2548%,
49.3106%. The three worst-municipality safeguards remain exactly equal to the
current exact-ID subset because every current target identity is retained.

The two-movement H60 witness reaches 24.2398%, 41.2864%, 51.0618% total/core
at 5/8/10 minutes, also retaining the three exact equity values.

## Epistemic boundary

These are valid physical witnesses, not selected networks. The 2,000,000-state
search remains `RESOURCE_LIMIT_INCOMPLETE` with 1,286,499 heap entries pending,
so the distances are minimum found, not certified global optima. Each witness
passes full-history physical replay, but the following are still unset:

- directional stop occurrences and ordered passenger-service events;
- route identity, pickup/drop-off and transfer relations;
- running time, dwell, recovery and vehicle blocks;
- timetable feasibility and S8 connection retention;
- actual annual calendar and nonuniform peak/off-peak service.

The H30/H60 annual-km values are explicit design screens. They do not claim the
same physical vehicle operates consecutive movements and do not infer passenger
continuity.

## Reproducibility

GitHub Actions run `34868712081` succeeded at commit
`fc34ed89868cd60185570c61ada3834a4e598d84`. Both executions were byte-identical.
Artifact `10358326654` has ZIP digest
`sha256:d93e26c07f299863653c4bf720cfe086795369d45f77173abebfa97401bf6c54`.

## Disposition

The previous negative result must remain pool-scoped. The new evidence supports
promoting exactly these two found physical portfolios to a typed service-binding
and operational stress stage. It does not authorise PRIMARY or RUNNER-UP.
