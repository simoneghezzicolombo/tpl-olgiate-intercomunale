# RT-031 data-guided candidate expansion V3

## Purpose

This lane removes Current-Service stop retention as a candidate constraint.
Olgiate FS remains the required hub. Frequency, span and annual production are
reported as a service surface and do not eliminate physical portfolios.

The current D184/D185 exact-ID subset is retained only as a benchmark.

## Certified pool-scoped result

The first exact expansion consumes the previously certified one-million-state
physical closed-walk pool:

- 105 hub-serving physical movement witnesses;
- 105, 5,460, 187,460 and 4,780,230 combinations evaluated at one through
  four movements;
- 9,789 distinct minimum-distance availability portfolios;
- 233 exact Pareto-nondominated portfolios;
- frontier composition: 17 one-movement, 104 two-movement, 72 three-movement
  and 40 four-movement portfolios.

Pareto axes are the separate total and worst-municipality 5/8/10-minute walking
access shares plus physical distance. There are no weights or scalar score.

For every frontier portfolio the service surface reports H20/H30/H40/H60 over
600/720/960-minute spans and 260 days. The 111,419 km reference cap is an
annotation, not a candidate-generation filter.

## What the data says—and does not say

None of the 9,789 portfolios is no worse than the current exact-ID benchmark on
all six access axes. This is not evidence that Current Service is globally
optimal. The upstream physical pool is resource-incomplete, contains only 105
hub-serving witnesses and exposes only 16 distinct hub-walk stop identities.
Its individual-walk envelope was 13.392 km.

The result instead diagnoses why the earlier generic search underperformed:
the available hub-walk pool does not yet span enough of the territory. The
targeted two-circuit witness found later is itself evidence that the generic
one-million-state pool missed relevant compositions.

A second search lane therefore used Olgiate FS as the declared root, a 30 km
individual-walk envelope and two million expansions. It found 2,062 positive
hub-serving stop-set witnesses spanning 29 stop identities, with up to 12 stops
on one movement. Every retained witness passed full-history seam replay.

Run `34896019917` succeeded at commit
`57745200f0f6e6a90d1f38f108d9ff7d01b83b56`, artifact `10368324023`, ZIP
digest
`sha256:dedf6d067af0188dde13c3041c482dd5551e23b9d4551cf757c7a137590dcf6b`.
The committed search-audit SHA256 is
`075b75ff7baaa01889a2ae237722741f2b7642bf722979198a9560fba64cb45c`.

The search remains `RESOURCE_LIMIT_INCOMPLETE` with 4,282,646 labels pending.
Its positive witnesses are usable; absence is not an impossibility proof.

This lane still contains closed walks only. Radial, trunk-branch, short-turn and
interlined service families remain outside its candidate-domain completeness
claim.

## Reproducibility

CI run `34896176171` succeeded at commit
`17b6f8c4d37429825e9f41a242fb1b3e96b422c2`. Artifact
`10368611576` has ZIP digest
`sha256:01eb10db5a76ef25b6ec61a7a428aa63b3fdeb0737effa9def677d3e94e17f72`.
The committed audit SHA256 is
`fd0475a803e338456570e2157928d7aef1d5a775830ee055bdcedefe9a24cb43`.

`candidate_domain_complete=false`

`network_selected=false`

`primary_selection_authorised=false`

`runner_up_selection_authorised=false`
