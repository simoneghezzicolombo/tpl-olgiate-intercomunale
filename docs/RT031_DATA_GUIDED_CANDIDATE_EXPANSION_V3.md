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

## Network-level connection and stop-retention preference

The next exact lane combines the Olgiate-rooted physical pool with the earlier
generic pool. A portfolio is admissible when at least one movement contains
Olgiate FS and the movements form a connected intersection graph by shared stop
identity. It is no longer required that every movement visit Olgiate FS.

This is deliberately labelled **potential** network connectivity. A common stop
identity does not certify compatible directions, ordered service events or a
passenger transfer. Those properties require later typed operational binding.

The 11 exact current stop identities are now an explicit Pareto preference:
their retained count/share is maximised alongside the six separate access axes,
while distance is minimised. Retention has no weight and is not an admission
filter. It certifies identity retention only, not current order, adjacency,
directional occurrence or passenger-service continuity.

The initial exact two-movement envelope combines 3,804 positive witnesses into
3,699 unique movement stop sets. Safe superset/distance dominance leaves 1,631
movements, including 833 that serve Olgiate FS. Exact connected-union dynamic
programming produces 62,947 portfolio stop sets and a 935-member eight-axis
frontier. Of these, 155 are no worse than the current exact-ID benchmark on all
six access axes and strictly better on at least one. Frontier alternatives
retain between 1 and 8 of the 11 current identities: this variation confirms
that retention operates as a trade-off, not a disguised hard constraint.

The two-movement bound is an explicit scope boundary, not an impossibility
claim. A local measurement found 1,373,871 connected stop unions at up to three
movements before access evaluation; expanding that exact domain remains future
computation rather than evidence that such portfolios do not exist.

## Frequent-class operational development gate

The certified two-movement frontier is next filtered only by decisions already
present in the approved policy contract: H30 frequent service, the hard annual
kilometre cap, and no regression against the current exact-ID benchmark on any
of the six total/equity 5/8/10-minute dimensions.  For the longest H30 context
that fits this supplied frontier (12 hours, 260 design days), all 155 benchmark-
improving members remain within the cap.  Exact access/equity Pareto dominance
reduces them to five territorial profiles without weights or a scalar score.

`scripts/phase2_bind_rt031_frequent_access_shortlist_v3.py` binds all five source
witnesses to exact directional carrier occurrences and ordered candidate public-
stop events.  Every component must independently serve Olgiate FS.  The binding
also reports source-model running time and 5/10/15-minute recovery fleet lower
bounds.  These exclude dwell and are not a timetable or vehicle-block plan.

The inherited Stage-F deterministic grid (runtime multipliers 0.9/1.0/1.1,
non-hub dwell 0/0.5/1.0 minutes and recovery 5/10/15 minutes) is evaluated
without probabilities. In the current source model, four profiles retain one
vehicle per component in six of 27 cases and one profile in five of 27; every
profile reaches a four-vehicle lower bound in the stressed tail. Therefore none
is robustly certifiable as a two-vehicle H30 operation from source-model evidence
alone. This is a screening result, not observed running-time validation.

The five profiles are a development shortlist, not a network selection.  Their
remaining gate is operational: dwell-inclusive runtime, exact H30 phasing, S8
deterministic retention and vehicle-block robustness must be compared before the
approved decision layers can advance.

### Exact H30 hub-phase surface

The five profiles share the same hub-clock problem because each consists of two
independent H30 components serving Olgiate FS. The complete ordered integer-minute
domain contains 900 phase pairs (0–29 minutes per component). Against all 74
frozen S8 events and the three existing transfer-friction profiles, 559 pairs are
Pareto-nondominated across combined hub gap and the separate directional transfer-
quality axes. Exactly 30 pairs give a regular 15-minute combined hub pattern, and
all 30 remain nondominated.

The phase evidence therefore supports a regular combined pattern but does not
choose its clock rotation. More importantly, it cannot override the deterministic
runtime/dwell/recovery finding: the phase surface is not a vehicle-block
feasibility certificate. Daily timetable construction remains blocked until the
operational stress gate is resolved.

### Daily timetable and exact block surface

The next gate does not silently turn the 12-hour production context into a
selected operating span. It exhausts all 14 H30-aligned 12-hour windows wholly
contained in the frozen 05:30–24:00 S8 design window. For every one of the five
typed profiles it also evaluates all 30 regular combined-H15 clock rotations
and all 27 inherited runtime/dwell/recovery cases. Exact vehicle blocks may
interline the two components when their trip times permit it.

Transfer-quality and deterministic bus-to-rail miss-share axes remain separate.
No passenger weights, empirical probabilities or scalar score are introduced.
The result is a robust Pareto surface; it cannot select a span, phase or
timetable, and source-model dwell sensitivity is not observed dwell validation.

The exhaustive run contains 2,100 timetable contexts and 56,700 engineering
realisations. Sixty contexts remain nondominated after retaining the six exact
territorial access/equity ratios alongside the operational axes; every one of
the five profiles remains represented. No context stays within two vehicles in
all 27 engineering cases, and every profile reaches an exact four-vehicle
requirement in its robust tail. The two latest candidate spans have no member on
the joint frontier, but that bounded dominance result does not itself select an
earlier operating span.

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
