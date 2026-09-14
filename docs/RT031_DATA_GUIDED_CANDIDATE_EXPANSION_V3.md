# RT-031 data-guided candidate expansion V3

## Purpose

This lane removes Current-Service stop retention as a candidate constraint.
Olgiate FS remains the required hub. Frequency, span and annual production are
reported as a service surface and do not eliminate physical portfolios.

The current D184/D185 exact-ID subset is retained only as a benchmark.

## Preliminary pool diagnosis

The first exact expansion consumes the previously certified one-million-state
physical closed-walk pool:

- 105 hub-serving physical movement witnesses;
- 105, 5,460, 187,460 and 4,780,230 combinations evaluated at one through
  four movements;
- 9,789 distinct minimum-distance availability portfolios;
- 233 exact Pareto-nondominated portfolios;
- frontier composition: 17 one-movement, 104 two-movement, 72 three-movement
  and 40 four-movement portfolios.

None of the 9,789 portfolios is no worse than the current exact-ID benchmark on
all six access axes. This is not evidence that Current Service is globally
optimal. The upstream physical pool is resource-incomplete, contains only 105
hub-serving witnesses and exposes only 16 distinct hub-walk stop identities.
Its individual-walk envelope was 13.392 km.

The result instead diagnoses why the earlier generic search underperformed:
the available hub-walk pool does not yet span enough of the territory. The
targeted two-circuit witness found later is itself evidence that the generic
one-million-state pool missed relevant compositions.

## Expanded data-guided frontier

A second search lane used Olgiate FS as the declared root, a 30 km
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

An exact zero-one union dynamic program then evaluated the complete
availability/distance envelope of these supplied witnesses up to four
movements. It represents 578,235 distinct minimum-distance portfolios and
retains 2,410 exact Pareto-nondominated alternatives. Of those, 1,761 are no
worse than the current exact-ID benchmark on all six access axes and strictly
better on at least one.

The shortest such frontier member uses two movements totalling 15.204 km. It
improves both total and worst-municipality access at 5/8/10 minutes. This is a
descriptive minimum-distance member of a large frontier, not a selected
network.

### Service-context counts at the reference cap

Frequency and span do not filter candidate generation. Applying them later as
explicit service contexts gives the following counts among the 1,761
benchmark-improving frontier alternatives:

| Per-movement service | Span | Within 111,419 km/year |
|---|---:|---:|
| H20 | 10/12/16 h | 0 |
| H30 | 10 h | 185 |
| H30 | 12 h | 119 |
| H30 | 16 h | 0 |
| H40 | 16 h | 119 |
| H60 | 16 h | 752 |

The shortest benchmark-improving member would require 126,498.713 km/year at
H30 for 16 hours, or 94,874.034 km/year at H30 for 12 hours. These are
trade-off coordinates, not recommendations.

Pareto axes remain the separate total and worst-municipality 5/8/10-minute
walking-access shares plus physical distance. There are no weights or scalar
score.

This lane still contains closed physical walks only. Its combinations can
represent radial out-and-back and multiple independent movements, but public
trunk-branch, short-turn and interlining semantics have not yet been assigned.
Candidate-domain completeness remains false.

## Reproducibility

Expanded-frontier CI run `34897632951` succeeded at commit
`a2ae263521e303787ebab473517b819b70d3527d`. Artifact `10370190130`
has ZIP digest
`sha256:c891c3a8c27dc59cae08b6d7dbb57a91be0290d7a7687f60617dc7f1a5a31a79`.
The committed audit SHA256 is
`7358c61050caddacdb7f84052673b61d7bdbda703b33a43a5d05640f1ff4b073`.

`candidate_domain_complete=false`

`network_selected=false`

`primary_selection_authorised=false`

`runner_up_selection_authorised=false`
