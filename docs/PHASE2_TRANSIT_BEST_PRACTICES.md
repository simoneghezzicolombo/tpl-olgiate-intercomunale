# Phase 2 — Transit design best practices

**Status:** normative design reference for Phase 2  
**Purpose:** translate external evidence and comparable practice into explicit objectives and constraints for the Olgiate-Calco-Brivio service-design optimiser.  
**Scope:** feeder/intermunicipal fixed-route bus network centred on Olgiate-Calco-Brivio FS.  
**Important:** this document does **not** select a topology. FIG8, loops, radial services, interlining and branched services remain competing design families.

## 1. Core objective

Phase 2 is not an exercise in minimising kilometres or maximising raw population coverage in isolation. The design objective is:

> **Maximise the practical usefulness of public transport to the largest possible number of people, subject to realistic operating resources, physical constraints and reliability requirements.**

The optimiser must therefore represent the whole passenger journey: access walk, service availability, waiting, in-vehicle time, transfers, connection quality, reliability and destination access.

The primary budget reference remains the validated D184+D185 production envelope of **111,419 bus-km/year**. Lower-cost and higher-cost sensitivities are allowed to identify the marginal value of additional or reduced production. Budget is a design constraint/sensitivity, not a hidden scoring weight.

## 2. Evidence-backed principles

### BP-01 — Frequency and span determine whether a service is genuinely usable

The Transit Capacity and Quality of Service Manual treats service availability in terms of how often, how long and where transit is available. It also distinguishes qualitatively between frequent service and hourly-or-worse service: at long headways passengers must organise their day around the timetable, while higher frequency reduces the penalty of missed departures and makes spontaneous use more feasible.

The European Commission Expert Group on Urban Mobility reports frequency/connectivity as the factor with the greatest impact on satisfaction with public transport, followed by reliability and accessibility.

**Model implication**

- Never represent frequency as a cosmetic attribute.
- Compute waiting and missed-connection consequences explicitly.
- Measure service span and number of useful departures, not only route coverage.
- Report headway by direction and time period.
- Avoid claiming that 60-minute service is simply “half as useful” as 30-minute service.

Sources:
- Transit Capacity and Quality of Service Manual, 3rd ed.: https://nap.nationalacademies.org/skim.php?act=nap&chap=191-298&record_id=24766
- European Commission EGUM recommendation on public transport/shared mobility: https://transport.ec.europa.eu/document/download/f222ead0-192c-413d-ad91-0f7dfe6de97e_en?filename=EGUM+Recommendation+-+PTSM+sub+group+-+TOPIC2.pdf

### BP-02 — Use generalised journey time, not route kilometres, as the passenger-facing measure

UK Department for Transport TAG guidance models public-transport generalised cost using walking, waiting, in-vehicle time and interchange penalties. Indicative TAG ranges weight walking/transfer time around **1.5–2.0×** in-vehicle time and waiting around **1.5–2.5×**, with explicit transfer penalties. TfL strategic modelling likewise uses generalised journey time rather than raw travel time alone.

**Model implication**

For every modelled OD movement, calculate at least:

`GJT = in_vehicle_time + w_walk*walk_time + w_wait*wait_time + transfer_penalty + reliability_penalty`

Use published parameter ranges as sensitivity bounds rather than inventing a single immutable coefficient. Initial reference ranges:

- access/egress walk: 1.5–2.0×
- waiting: 1.5–2.5×
- bus in-vehicle time: 1.0–1.4× relative to rail IVT reference
- transfer/boarding penalty: 2–10 equivalent minutes where applicable

Sources:
- UK DfT TAG M3.2 Public Transport Assignment Modelling: https://assets.publishing.service.gov.uk/media/666af32effd07973a043d110/tag-unit-m3.2-public-transport-assignment-modelling.pdf
- UK DfT TAG M2.1 Variable Demand Modelling: https://assets.publishing.service.gov.uk/media/69a034423e672177d0bc7710/tag-unit-m21-variable-demand-modelling.pdf
- TfL example of generalised journey-time modelling: https://tfl.gov.uk/cdn/static/cms/documents/property-impacts-report-acc.pdf

### BP-03 — Clockface regularity and memorability are real service quality

A network that leaves at the same minute every hour is easier to learn, trust and use than a collection of irregular departures with many pattern variants. Frequency and span should be visible as defining characteristics of the network, not hidden behind a route line on a map.

Switzerland provides a strong reference case for integrated clockface operation and timed interchange. SBB’s timetable system explicitly incorporates interchange times and integrates timetable data across operators.

**Model implication**

- Prefer regular headways and stable departure minutes where operationally feasible.
- Measure timetable irregularity explicitly.
- Penalise unnecessary route-pattern proliferation.
- A scenario with many bespoke school/peak variants must demonstrate enough utility to justify the added complexity.

Sources:
- SBB timetable/interchange information: https://www.sbb.ch/en/help-and-contact/products-services/timetable.html
- ETH description of the Swiss integrated clockface/timed-transfer system: https://www.research-collection.ethz.ch/server/api/core/bitstreams/30bbe8c2-bdc2-4fec-807c-a8fb1a15b108/content
- Frequency and legibility discussion: https://humantransit.org/basics/the-case-for-frequency-mapping

### BP-04 — The S8 connection is part of the bus trip, not an external bonus

For a feeder network centred on Olgiate-Calco-Brivio FS, the relevant passenger outcome is not merely arrival at the station. It is the probability of completing a useful bus→train or train→bus connection with a tolerable transfer time.

**Model implication**

- Use the verified Gate C S8 timetable events.
- Score both directions of interchange.
- Include transfer walk/time at the station.
- Test robustness to bus and rail delay.
- Measure missed-connection cost, not only nominal timetable coincidence.
- Allow the optimiser to choose clockface phase relative to S8 events.

Local precedent: the Meratese basin redesign explicitly organises services around railway nodes and describes D201/D202 trips as operating in coincidence with trains.

Source:
- Programma di Bacino, Ambito Meratese: https://www.merateonline.it/public/filemanager/pub_files/2025/Giugno/PianodiBacino.pdf

### BP-05 — Reliability must constrain the design before frequency is advertised

TCRP reliability guidance identifies schedule/headway optimisation, route shortening/realignment, reducing route variations, timed-transfer coordination and stop consolidation as relevant operational treatments. Surveyed agencies reported strong success particularly for shortening routes and reducing route variations.

**Model implication**

- Do not schedule at pure-running-time limits.
- Include dwell and recovery explicitly.
- Test runtime uncertainty and late arrival propagation.
- Long or highly variable routes must pay an explicit reliability cost.
- Compare nominal headway with robust headway under runtime perturbation.
- Missed trips and connection failures should be treated as severe outcomes.

Sources:
- TCRP Developing a Guide to Bus Transit Service Reliability: https://nap.nationalacademies.org/read/25903/chapter/6
- TCRP Minutes Matter reliability guide: https://nap.nationalacademies.org/skim.php?act=nap&chap=58-68&record_id=25727

### BP-06 — Directness matters, but coverage and directness are a trade-off

Bus network redesign practice consistently treats excessive deviations, branches and turns as costs because they increase passenger travel time, reduce frequency and worsen reliability. Transit service standards surveyed by TCRP commonly include directness criteria and limits on route branches.

**Model implication**

- Calculate route circuity/directness for relevant OD pairs.
- Penalise repeated-edge kilometres and unnecessary backtracking.
- Do not add a deviation solely because it captures a small amount of population.
- Extensions may be scheduled on selected trips if they outperform making every trip longer.

Sources:
- TCRP Transit Service Evaluation Standards: https://nap.nationalacademies.org/read/25446/chapter/7
- TransitCenter network-redesign principles: https://transitcenter.org/is-the-bronx-bus-network-redesign-ambitious-enough/

### BP-07 — Stop spacing is an access-versus-speed optimisation problem

More stops are not automatically better. Closely spaced stops increase dwell and acceleration/deceleration losses, while excessive spacing worsens walking access. TCRP surveys show agencies commonly apply explicit stop-spacing standards and use stop consolidation as a speed/reliability treatment.

**Model implication**

- Existing GTFS stops are the preferred starting set, not an immutable constraint.
- New stops may be generated where they materially increase accessibility or serve a verified destination/settlement gap.
- Existing stops may be omitted only when the model documents the accessibility loss and operating benefit.
- Stop spacing must be evaluated jointly with walking-network catchment, not Euclidean distance alone.
- Any new physical stop remains `FIELD_CHECK_PENDING` until road-safety/space suitability is verified.

Sources:
- TCRP Commonsense Approaches for Improving Transit Bus Speeds: https://nap.nationalacademies.org/read/22421/chapter/13
- TCRP Transit Service Evaluation Standards: https://nap.nationalacademies.org/read/25446/chapter/7

### BP-08 — Simple networks create useful connections

TransitCenter and international network-redesign practice emphasise connectivity, legibility and simple route structures. Complexity can dilute frequency and make the network harder to understand.

**Model implication**

Track at least:

- number of distinct public-facing route patterns;
- branches/conditional deviations;
- number of timed transfers;
- number of destinations reachable within useful time thresholds;
- common-clock departure consistency.

A topologically complex scenario must outperform a simpler one by a meaningful amount, not by a microscopic metric improvement.

Sources:
- TransitCenter Bus Network Redesign: https://transitcenter.org/publication/bus-network-redesign
- Dublin redesign discussion: https://humantransit.org/dublinbus

### BP-09 — Preserve continuity where it helps, but do not inherit the old network blindly

Existing stops and known corridors have value: passengers know them, physical stop infrastructure may already exist and current travel habits have adapted to them. But network redesign guidance also recommends a “blank slate” check so inherited route geometry does not become an unquestioned constraint.

**Model implication**

- Existing D184/D185 stops/corridors receive a continuity prior, not automatic survival.
- Always include at least one “blank-slate” generated family.
- Quantify how many existing stops remain served and how many passengers face a changed boarding location.
- Never add an arbitrary score merely for looking similar to today’s map.

Source:
- Network-redesign methodology discussion: https://humantransit.org/2010/05/basics-should-we-redesign-our-bus-network-and-how.html

### BP-10 — Coverage and ridership are different objectives; expose the trade-off

A service can maximise geographic/social coverage while producing low ridership, or concentrate frequency where demand is strongest and leave some areas with less service. Good planning makes this trade-off explicit.

**Model implication**

- Report both demand-weighted utility and worst-served-area indicators.
- Set an explicit minimum equity/coverage floor rather than hiding equity inside a weighted score.
- Report results by municipality and meaningful settlement/frazione where data support it.
- A high-utility network cannot be recommended if it catastrophically fails the agreed territorial floor.

Source:
- Network redesign and ridership/coverage trade-off: https://humantransit.org/2025/11/how-do-network-redesigns-increase-ridership.html

### BP-11 — Functional-area planning is the correct geographic scale

EU SUMP guidance emphasises planning around actual functional mobility areas and real traffic flows rather than administrative boundaries alone.

**Model implication**

- Core optimisation covers the five project municipalities but may route across adjacent territory when necessary.
- Connections and destinations outside the five municipalities can matter if verified OD or network evidence shows they are important.

Sources:
- European Commission SUMP planning and monitoring: https://transport.ec.europa.eu/transport-themes/urban-transport/sustainable-urban-mobility-planning-and-monitoring_en
- 2026 SUMP Guidelines: https://urban-mobility-observatory.transport.ec.europa.eu/sustainable-urban-mobility-plans/guidelines-developing-and-implementing-sustainable-urban-mobility-plan-0_en

### BP-12 — Accessibility and multimodal integration are first-class outcomes

The EU Urban Mobility Framework prioritises accessible, inclusive, integrated public transport and multimodal hubs. The 2026 EU mobility-indicator framework explicitly includes accessibility among the core monitoring dimensions.

**Model implication**

- Measure access to mobility opportunities, not merely kilometres operated.
- Explicitly report people served within walking thresholds.
- Preserve accessibility for lower-mobility users in stop-design sensitivity where possible.
- Treat Olgiate-Calco-Brivio FS as a multimodal node, not simply another stop.

Sources:
- EU Urban Mobility Framework: https://transport.ec.europa.eu/transport-themes/urban-transport/sustainable-urban-mobility_en
- EU urban mobility indicators, 2026: https://transport.ec.europa.eu/news-events/news/commission-adopts-implementing-regulation-strengthen-sustainable-urban-mobility-through-harmonised-2026-07-09_en

## 3. Local benchmark: Circolare Meratese

The Meratese Programma di Bacino is a useful local comparator, not a template to copy mechanically.

The basin plan restructures the area around the Cernusco-Merate railway node, defines D201/D202 circular services and explicitly targets train coincidence. The authoritative PdB production values previously reconstructed in this repository total approximately **90,372 bus-km/year** for D201+D202. The important lesson is not “copy two loops”; it is that a relatively compact network can concentrate a finite annual production envelope into useful rail-feeder service.

Sources:
- Programma di Bacino: https://www.merateonline.it/public/filemanager/pub_files/2025/Giugno/PianodiBacino.pdf
- Circolare Meratese presentation: https://www.merateonline.it/public/filemanager/pub_files/2025/Giugno/SlidesSoloCircolare.pdf

## 4. What Phase 2 must not do

Phase 2 must **not**:

1. declare FIG8 the preferred topology in advance;
2. restrict the search to the four Gate E paired hypotheses;
3. optimise raw population coverage while ignoring frequency and waiting;
4. use a single arbitrary weighted score with undocumented coefficients;
5. query Overpass repeatedly during scenario generation;
6. promote a new stop to operationally feasible without field verification;
7. treat scheduled rail coincidence as reliable connection without perturbation testing;
8. interpret `ASSUMPTION` as “not comparable”: all future network designs are necessarily hypotheses before implementation;
9. use INVALIDATED legacy outputs as evidence;
10. end with “it depends” without identifying the best robust design under the declared decision rule.

## 5. Phase 2 decision philosophy

The final recommendation should be based on three layers:

1. **Hard feasibility constraints:** road eligibility, budget envelope, fleet/cycle feasibility, minimum recovery, mandatory service rules.
2. **Passenger utility:** demand-weighted generalised journey time/accessibility, including walking, waiting, in-vehicle time, transfers and S8 connection quality.
3. **Robustness and equity:** the preferred design must remain strong across plausible behavioural/runtime assumptions and meet declared minimum territorial-access floors.

The optimiser should therefore be free to discover that the best answer is a short loop, two independent feeders, interlined loops, a figure-8, radials, trunk-and-branch service, scheduled extensions or another generated structure that satisfies the same rules.
