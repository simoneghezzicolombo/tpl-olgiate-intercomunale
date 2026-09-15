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

### Caller correction: one recognizable public line

The decision objective is one recognizable public line, not a portfolio of
independent passenger-facing lines. Physical movement count and vehicle count
are therefore not line count. Multiple directions can belong to one line only
after a common public route identity, directional occurrences, ordered service
events and passenger-service continuity are bound explicitly.

The original distance-priority hub pool was structurally uninformative for this
objective: its 2,062 single closed walks reached at most 12 stop identities and
no single walk improved the current benchmark on all six access axes. Two
additional deterministic, resource-truncated discovery lanes expand stop-rich
and current-stop-rich states first, without a weighted score or admission
filter. With 20,000 expansions each they find single walks with up to 34 stop
identities and all 11 current exact identities.

Combining the positive pools, including the three H30-derived distance
envelopes, yields 2,675 distinct ordered single-walk candidates and a 209-member
no-weight frontier over six access axes, current-stop identity retention and
distance. Thirty-seven frontier candidates are no
worse than the current benchmark on all six access axes and strictly better on
at least one; four of those retain all 11 current identities. The shortest of
the four is 29.480 km and exposes 31 stop identities.

At the 111,419 km/year reference cap, eight of the 37 benchmark-improving
candidates fit H30/10h; four of those retain 9/11 current exact identities and
four retain 8/11. The shortest is 20.198 km, exposes 20 stop identities and
requires about 105,029 km/year in that context. None fits H30/12h or H30/16h.
All 37 fit H60/12h and 19 fit H60/16h; 33 fit H40/10h and nine fit H40/12h.
These are service-context counts, not a selected frequency or span. The
physical pools remain incomplete.

All eight H30/10h alternatives are now bound as candidate service designs with
one public route identity, one closed physical movement and one ordered public
pattern. Directional occurrences and every ordered service event are explicit.
Passenger continuity is declared only within that ordered pattern and is
terminated at the Olgiate FS cycle seam; vehicle continuity is never substituted
for passenger continuity. This certifies the one-line candidate structure, not
an observed or selected production service.

The exhaustive H30/10h timetable surface evaluates all 18 aligned ten-hour
windows, all 30 clock phases and all 27 inherited deterministic
runtime/dwell/recovery cases for every candidate: 4,320 timetable contexts and
116,640 engineering realisations. The no-weight frontier retains 546 timetable
contexts. Every candidate can use two vehicles in the light cases, but reaches
four in the conservative tail; therefore two vehicles are not robustly
certified until dwell evidence narrows the engineering grid. Deterministic miss
shares are not empirical missed-connection probabilities.

Diversified-search CI run `34982075116` succeeded with artifact `10402211767`
and ZIP digest
`sha256:5b89fbe0b14edf2277404a93177383fef042cc1642477baa65c6802390421062`.
Single-line frontier CI run `34982695261` succeeded with artifact `10402480319`
and ZIP digest
`sha256:308828d3af91d33b039f89ac9669e2fe57e9bcf8811e331b80c50a218f2ffaf0`.
The committed single-line audit SHA256 is
`433ea63276f30fac92b42fbb548687c4461cfa88a1bdca911c72cee72a1b48a4`.

The H30-envelope search run `34983044901` succeeded with artifact
`10402307782` and ZIP digest
`sha256:772178af46d2dec587aac49e2fdfb4f5c29291f4be6a3be2c02af60e61ac2c03`.
The expanded single-line frontier run `34983509128` succeeded with artifact
`10402507221` and ZIP digest
`sha256:0501e591ad604602ef7d587ea75c622e1aa5d6e5da4ff6e477cdae8cfcc2bf73`.

Typed one-line binding run `34985174245` succeeded with artifact `10403361396`
and ZIP digest
`sha256:cc002bfb5f09c15f784259f83b385b91a87fba38502491780f651ea93ed068ad`.
The exhaustive timetable run `34985778470` succeeded with artifact
`10403538038` and ZIP digest
`sha256:f35bbccc587f8ff313488098838e95076b36998f492dca02e1945da936212c54`.
The committed timetable audit SHA256 is
`8b6cdeb7f62f110a3fdd843f0b70f9a1550bc50d9e2a0c1ab455650b2c620756`.

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

Network-connected CI run `34900153541` succeeded at commit
`9864a42168dbca769db2d04d217d21cf5f033064`. Artifact `10370024100` has ZIP
digest
`sha256:b279b89e72c16f272c1439f4da96e6d6fbc53e417deeac0844e32405639bce45`.
The committed machine-readable audit SHA256 is
`32990d94df7b3328d5c63db444fb758120bebe4e7dcc4e49cd83d131ba19874d`.

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

### Historical scheduled-runtime calibration boundary

The frozen Arriva GTFS for D184/D185 supplies 42 historical trips and 541 stop-
time occurrences, with a validity end of 8 June 2026. For full trips of at
least 8 km, the scheduled-speed envelope is compared with each candidate
component's source-model speed. This is a plausibility audit only: the feed is
historical and scheduled, not current AVL/reliability evidence.

There are 32 comparable trips. Their full-trip scheduled-speed range is
26.520–34.54875 km/h (median 26.8827); the ten candidate components' source-
model speeds range from 27.524 to 30.322 km/h and all lie inside that broad
historical envelope. This supports plausibility only, not calibration identity.

All GTFS arrival/departure pairs for those occurrences are equal. That encoding
does not demonstrate zero passenger dwell and cannot calibrate dwell. The audit
therefore fails closed on dwell and forbids replacing candidate runtimes with a
historical median under a different label.

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
