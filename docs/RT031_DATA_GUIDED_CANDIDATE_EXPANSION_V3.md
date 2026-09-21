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

The caller has now declared H30 over a ten-hour span. The annual 260-day count
remains a design assumption. Two additional 75,000-expansion H30/10h search
lanes add 1,001 resource-bounded ordered witnesses. Their result disproves the
previous apparent 9/11 retention ceiling: it was a search-truncation result,
not a structural impossibility.

Combining all positive pools yields 3,663 distinct ordered single-walk
candidates and a 197-member no-weight frontier over six access axes,
current-stop identity retention and distance. Thirty-three frontier candidates
are no worse than the current benchmark on all six access axes and strictly
better on at least one. Seventeen fit the 111,419 km/year H30/10h reference-cap
context: one retains 10/11 current exact identities, six retain 9/11, eight
retain 8/11 and two retain 7/11. None fits H30/12h or H30/16h. These are
service-context counts, not a network selection, and the physical pools remain
resource-incomplete.

The unique 10/11 alternative is `SL_d25aca47905d0743f6a6`: 21.405390 km,
approximately 111,308.028 km/year in the declared context, and 23 available
stop identities. It retains every current exact identity except
`FROZEN::300063`, the separately tracked historical Brivio naming-collision
identity. This statement is exact-identity retention only; it does not silently
promote stop identity to a directional-occurrence or ordered-event guarantee.

All 17 H30/10h alternatives are now bound as candidate service designs with
one public route identity, one closed physical movement and one ordered public
pattern. Directional occurrences and every ordered service event are explicit.
Passenger continuity is declared only within that ordered pattern and is
terminated at the Olgiate FS cycle seam; vehicle continuity is never substituted
for passenger continuity. This certifies the one-line candidate structure, not
an observed or selected production service.

The exhaustive H30/10h timetable surface evaluates all 18 aligned ten-hour
windows, all 30 clock phases and all 27 inherited deterministic
runtime/dwell/recovery cases for every candidate: 9,180 timetable contexts and
247,860 engineering realisations. The no-weight frontier retains 1,802 timetable
contexts, and every one of the 17 candidates contributes at least one. The
unique 10/11 candidate `SL_d25aca47905d0743f6a6` contributes 97 contexts, so it
is not operationally dominated. Pareto-context counts are not votes and do not
rank candidates. Every context reaches four vehicles somewhere in the
conservative grid; therefore a smaller robust fleet is not certified until
observed dwell evidence narrows that grid. Deterministic miss shares are not
empirical missed-connection probabilities.

### Municipality-resolved correction

The earlier 197-member frontier used the minimum municipal share as a single
equity coordinate. That aggregation concealed which municipality bore a loss.
V4 therefore keeps all 5/8/10-minute shares for Brivio, Calco, Olgiate Molgora,
Santa Maria Hoe and La Valletta Brianza as 15 separate Pareto preferences,
alongside the three total-access shares, exact current-stop retention and
distance. Municipal non-regression is not an admission constraint.

Across the same 3,663 one-line candidates, this produces 778 nondominated
alternatives; 736 fit the 20-daily-cycle reference cap. Retention within that
cap ranges from one to ten of the 11 exact current identities: 146/161/141/61/
45/124/34/14/9/1 alternatives retain respectively one through ten. No member is
componentwise no worse than Current Service on all three total and all 15
municipal axes. This is a trade-off diagnosis, not a filter or a proof that the
current network is globally optimal.

The former unique 10/11 candidate remains nondominated, but its apparent broad
gain is purchased with a large Brivio loss. Total potential coverage changes
from 21.74/38.73/48.77% to 33.25/52.48/58.73% at 5/8/10 minutes, while Brivio
changes from 42.34/69.52/78.38% to 22.61/32.88/35.24%. It improves the other
four municipalities on the same substrate. It must therefore not be called an
alpha or a territorial winner absent an explicit normative preference about
that distribution.

Municipal-frontier run `35017718349` succeeded with artifact `10416805424`,
ZIP digest
`sha256:d4726e765501c52944428111c43c34eb010b37667b62c96f5f09d8c48dec1d52`
and result SHA256
`0757d9513e21e1e68a7fc43c1732b45c4ccd83242e84d20ea8a324d0866bca26`.

### Equal-production mixed-frequency surface

Four caller-visible service templates hold production at exactly 20 daily
departures while trading peak H30 hours for a longer H60 base: 12 hours with
eight H30 peak hours, 14 with six, 16 with four, and 18 with two. All 30 clock
phases and all 27 inherited deterministic engineering cases are evaluated for
the 17 already typed candidates: 2,040 contexts and 55,080 realisations.
Popular Times only supports qualitative temporal plausibility of the tested
windows; it is not demand, a weight or a hard filter.

The mixed-only Pareto surface has 1,179 contexts. Its joint comparison with the
uniform H30/10h surface retains 2,981: all 1,802 safely prepruned uniform
contexts and 1,179 mixed contexts. Counts are not votes. The 12/14/16-hour
templates reach four vehicles somewhere in every context's deterministic grid.
Every one of the 510 tested 18-hour contexts instead remains at no more than
three vehicles throughout that grid. Thus an 18-hour H30-peak/H60-base pattern
is a serious resource-equivalent service-policy alternative, not a selected
timetable; it trades away H30 hours and transfer quality.

This timetable result is diagnostic for the 17 typed candidates only. The
municipality-resolved frontier has 778 members, so operational binding of that
larger frontier is still incomplete. Mixed-frequency run `35018816775`
succeeded with artifact `10417175153`, ZIP digest
`sha256:78e78097b7279fceea196660415d3166459fa02aedcd28b7cc24ee53aa3cd48e`
and result SHA256
`2ab04ca24a525fa32f450f419cfd21c495ea616001404bd114264e0bb4ce03bf`.

Subsequent complete typed binding closes that structural gap for all 736
municipal-frontier candidates within the reference production cap (run
`35076669258`, artifact `10438835538`, ZIP SHA256
`a5c61c01934890c4a7a06a0bbc24c7e56ff477bb4efa7da8084c21a18c74cca6`).
An exact full-frontier fleet screen then evaluates all four 20-departure
templates across the inherited 27-case grid (run `35587456801`, artifact
`10632938711`, ZIP SHA256
`1dda77b013bf7cf0d95e1633a9128e8f5840af1f0fb44e54d48d387e444af627`).
The 18-hour template has two H30 peak hours and 16 H60-only hours; every one of
the 736 candidates stays within three vehicles, whereas 108 need four under
each of the 12/14/16-hour templates. Within the 18-hour case, all candidates
retaining 7–10 exact current stops require three vehicles. This is not a
three-vehicle admission rule or a selected timetable. The full 736-candidate
30-phase transfer comparison was subsequently completed.

The full 18-hour phase run `35588461021` succeeded with eight byte-replayed
shards and an exact coverage check in the aggregate. Artifact `10633402248`
has ZIP SHA256
`1eb77d06a3fb0dda5d0b92217cbe1cd386ec59d39ae69d5280abbb43f16180e7`;
the result SHA256 is
`4be12d21db6bf63cd87937df9baafaeeabbce7b86b160adf6dee0c7ab5dd1cfd`.
It contains 22,080 line/phase contexts and 596,160 deterministic engineering
realisations. The no-weight within-line phase Pareto check retains 14,395
contexts, five to 26 phases for each line. It does not eliminate any of the
736 candidate lines. They were already mutually nondominated on the territorial,
retention and distance coordinates, so a larger operational vector cannot
manufacture a unique winner. No global cross-line Pareto pass, weighted score,
empirical missed-connection probability or final network choice is claimed.

### Where a Brivio safeguard moves the loss

An exact, descriptive audit compares all 736 within-cap municipal-frontier
candidates to the current exact-ID structural stop subset. Brivio non-regression
and total gain are *questions*, not added admission rules. Twenty-one candidates
avoid regression at all 5/8/10-minute thresholds for both Brivio and total
coverage, with at least one strict total gain: seven retain six and fourteen
retain seven of the 11 exact current stop identities. No candidate retaining
eight to ten does so in this supplied pool.

The 21 do not solve equity for the whole territory. Their Santa Maria Hoe
potential 10-minute walking coverage is 11.14–30.03%, against 75.39% for the
current structural subset. All 21 avoid regression in Calco and Olgiate Molgora at all
three thresholds; six also avoid La Valletta Brianza regression at all three.
These are potential catchments, not passenger demand or a service guarantee.
The result locates a real territorial trade-off within the resource-bounded
pool; it does not prove that a better geometry is impossible outside it and
does not nominate a replacement line.

Trade-off run `35589310664` succeeded with artifact `10633553070`, ZIP
SHA256 `1aaa37dc0cf28fd1aee045022863bfc714e3cb3883c70d55de1497dfbad74669`.
The machine-readable result SHA256 is
`0aed8abc60fef5dbb91822f3e307704c3b26b307703c6cba97005f9fccd7da01`.

Diversified-search CI run `34982075116` succeeded with artifact `10402211767`
and ZIP digest
`sha256:5b89fbe0b14edf2277404a93177383fef042cc1642477baa65c6802390421062`.
Single-line frontier CI run `34982695261` succeeded with artifact `10402480319`
and ZIP digest
`sha256:308828d3af91d33b039f89ac9669e2fe57e9bcf8811e331b80c50a218f2ffaf0`.
The committed audit SHA256 at that earlier discovery stage was
`433ea63276f30fac92b42fbb548687c4461cfa88a1bdca911c72cee72a1b48a4`.

The H30-envelope search run `34983044901` succeeded with artifact
`10402307782` and ZIP digest
`sha256:772178af46d2dec587aac49e2fdfb4f5c29291f4be6a3be2c02af60e61ac2c03`.
Deep H30/10h search run `34987371969` succeeded with artifact `10403709761`
and ZIP digest
`sha256:37b5e4f51240eabf0cc8ddbfa34746ebf6aa3226a8d9ca222a0b72f89854e7cc`.
The expanded single-line frontier run `35011955376` succeeded with artifact
`10414420652` and ZIP digest
`sha256:0621c06a04bdccffefa60bd17dbe07bf9dbb0056b41929e86c57fdb6fcb28892`.
The committed frontier audit SHA256 is
`a755aaec2f3edbc903ae1bdb50a106911476b8d41f82b183c48b7563ea72c216`.

Typed one-line binding run `35012428602` succeeded with artifact `10414630100`
and ZIP digest
`sha256:9dbc356dedb7e2fdf774f5d7e8d1fb6e3538f557fdd6dab5218b0930ebe8c673`.
The exhaustive timetable run `35012571290` succeeded with artifact
`10414363725` and ZIP digest
`sha256:ae05e90d41ae198892372862cb32efc2c71c7d527be05dd76be3e5471f2b99ff`.
The committed timetable audit SHA256 is
`bfc1a901363666a461f1317d50086fbdaa26b5bbf7b039b5d735f05a095fed3c`.

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
