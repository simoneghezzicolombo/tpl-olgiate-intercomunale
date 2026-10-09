import test from "node:test";
import {validateBenefits,benefitsView} from "../nodo8-benefits.mjs";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  makeNodo8Features,
  validateNodo8,
  NODO8_SCENES,
  playbackVisible,
} from "../dietro-l-analisi/journey-nodo8.mjs";
import { buildLine, statesAt } from "../nodo8-line.mjs";
import { validateCoverageComparison, coverageChangeLabel } from "../nodo8-coverage.mjs";

const data = JSON.parse(
  readFileSync(
    new URL("../assets/nodo8-proposal.json", import.meta.url),
    "utf8",
  ),
);
const coverageComparison = JSON.parse(readFileSync(new URL("../assets/nodo8-coverage-comparison.json", import.meta.url), "utf8"));
const serviceComparison=JSON.parse(readFileSync(new URL("../assets/nodo8-service-comparison.json",import.meta.url),"utf8"));
const coverageDiagnostic=JSON.parse(readFileSync(new URL("../assets/nodo8-coverage-diagnostic.json",import.meta.url),"utf8"));
test("resident comparison keeps independent spatial and station metrics, including losses",()=>{
  const model=validateBenefits(data,coverageComparison,serviceComparison,coverageDiagnostic);
  for(const code of ["TOTAL",...data.municipalities.map(m=>m.code)]) for(const threshold of ["5","8","10"]) for(const direction of ["west","east"]) {
    const v=benefitsView(model,code,threshold,direction);
    assert.equal(v.proposalCount,16);assert.equal(v.proposalGap,120);
    assert.equal(v.currentCount,direction==="west"?8:5);
    assert.equal(v.currentGap,direction==="west"?377:380);
    assert.equal(v.delta,coverageComparison.delta_percentage_points[code][threshold]);
  }
  assert.ok(benefitsView(model,"97010","5").delta<0);
  assert.ok(benefitsView(model,"97074","5").delta<0);
  assert.ok(benefitsView(model,"TOTAL","5").delta>0);
  const brivio=coverageDiagnostic.municipality_details["97010"].old_closest_groups_for_lost_units;
  assert.equal(brivio[0].cluster_id,"EX_036");assert.deepEqual(brivio[0].member_stop_ids,["L00063"]);
  const smh=coverageDiagnostic.municipality_details["97074"].old_closest_groups_for_lost_units;
  assert.equal(smh[0].cluster_id,"EX_028");assert.deepEqual(smh[0].member_stop_ids,["300873","L00873"]);
  assert.equal(serviceComparison.pdb.proposed_terminal,"Cisano Bergamasco FS");
});
test("resident comparison rejects invented joint scores, budgets or unreconciled losses",()=>{
  for(const mutate of [s=>s.annual_service_count_inferred=true,s=>s.combined_frequency_accessibility_score_inferred=true,
    s=>s.pdb.automatic_km_entitlement_certified=true,s=>s.pdb.automatic_funding_transfer_certified=true,
    s=>s.east.current_departures_min.pop()]) {
    const s=structuredClone(serviceComparison);mutate(s);assert.throws(()=>validateBenefits(data,coverageComparison,s,coverageDiagnostic));
  }
  for(const mutate of [d=>d.municipality_details["97074"].lost_pp=0,d=>d.sources.pedestrian_osm.sha256="other",
    d=>d.additional_resident_count_inferred=true]) {
    const d=structuredClone(coverageDiagnostic);mutate(d);assert.throws(()=>validateBenefits(data,coverageComparison,serviceComparison,d));
  }
  assert.throws(()=>benefitsView(validateBenefits(data,coverageComparison,serviceComparison,coverageDiagnostic),"other"));
});
test("spatial comparison preserves the confirmed percentages and exposes losses without claiming current service", () => {
  assert.equal(validateCoverageComparison(coverageComparison, data), coverageComparison);
  assert.equal(coverageComparison.additional_resident_count_inferred, false);
  assert.equal(coverageComparison.baseline_trip_level_current_activation_certified, false);
  assert.ok(coverageComparison.delta_percentage_points["97010"]["5"] < 0);
  assert.ok(coverageComparison.delta_percentage_points["97074"]["5"] < 0);
  assert.equal(coverageChangeLabel(13.437652483858656), "+13,44 p.p.");
  assert.equal(coverageChangeLabel(-6.3921307209988), "−6,39 p.p.");
  assert.throws(() => coverageChangeLabel(NaN));
});
test("incomplete, mismatched or near-core unresolved coverage comparison fails closed", () => {
  for (const mutate of [
    d => { d.proposal_coverage_reproduced = false; },
    d => { d.proposal_percent.TOTAL["10"] += 1; },
    d => { d.baseline_percent.TOTAL["10"] = null; },
    d => { d.delta_percentage_points.TOTAL["10"] = 1; },
    d => { d.additional_resident_count_inferred = true; },
    d => { d.distant_unattached_points[0].minimum_core_distance_lower_bound_m = 500; },
  ]) {
    const changed = structuredClone(coverageComparison);
    mutate(changed);
    assert.throws(() => validateCoverageComparison(changed, data));
  }
});

test("explorer overview has four occupied full-trip carriers at 07:35", () => {
  const line = buildLine(data);
  const states = statesAt(line, 455);
  assert.deepEqual(
    states.map((s) => s.id),
    ["B1", "B2", "B3", "B4"],
  );
  assert.ok(states.every((s) => s.coordinates && s.trip));
  states.forEach((s) => {
    const trip = line.trips.find((t) => t.number === s.trip);
    assert.equal(trip.events[0].role, "FULL_TRIP_START_FS");
    assert.equal(trip.events[15].role, "INTERMEDIATE_FS_STAY_ONBOARD_DESIGN");
    assert.equal(trip.events.at(-1).role, "FULL_TRIP_END_FS");
  });
  assert.ok(statesAt(line, line.start).filter((s) => s.coordinates).length < 4);
});

test("playback hides and pauses outside the active current-proposal context", () => {
  const state = { scene: "explore", exploring: true, nodo8Visible: true };
  assert.equal(playbackVisible(state, "explore"), true);
  for (const changed of [
    { ...state, scene: "finalists" },
    { ...state, scene: "nodo8-time" },
    { ...state, exploring: false },
    { ...state, nodo8Visible: false },
    { ...state, nodo8Visible: undefined },
  ])
    assert.equal(playbackVisible(changed, "explore"), false);
  assert.equal(playbackVisible({ scene: "nodo8-time" }, "story"), false);
  assert.equal(playbackVisible(state, "story"), false);
});
test("story does not embed another map or inline playback, but keeps the explorer", () => {
  const module = readFileSync(new URL("../dietro-l-analisi/journey-nodo8.mjs", import.meta.url), "utf8");
  const html = readFileSync(new URL("../dietro-l-analisi/index.html", import.meta.url), "utf8");
  assert.ok(!module.includes("mountRoadPreview"));
  assert.ok(!module.includes("inlineMap:"));
  assert.ok(!html.includes('id="journeyPlayback"'));
  assert.ok(module.includes('document.getElementById("explorePlayback")'));
});
test("overlay copies every confirmed road coordinate, not historical anchors", () => {
  const before = JSON.stringify(data);
  const shown = makeNodo8Features(data);
  assert.equal(shown.routes.features.length, 2);
  shown.routes.features.forEach((feature, index) => {
    assert.deepEqual(
      feature.geometry.coordinates,
      data.routes[index].coordinates,
    );
    assert.equal(feature.properties.wing, data.routes[index].wing);
    assert.equal(feature.properties.source, data.sources.geometry.path);
  });
  assert.equal(JSON.stringify(data), before);
});
test("27 distinct sites, four new sites, and two-event sites remain explicit", () => {
  const shown = makeNodo8Features(data).sites.features;
  assert.equal(shown.length, 27);
  assert.equal(new Set(shown.map((site) => site.properties.site_id)).size, 27);
  assert.equal(
    shown.filter((site) => site.properties.proposed_new_site).length,
    4,
  );
  assert.equal(
    shown.reduce((count, site) => count + site.properties.occurrence_count, 0),
    28,
  );
  assert.equal(
    shown.find((site) => site.properties.name === "Olgiate sud").properties
      .occurrence_count,
    2,
  );
  assert.equal(
    shown.find((site) => site.properties.name === "San Zeno/Via Cantu")
      .properties.occurrence_count,
    2,
  );
  assert.ok(
    shown.every((site) => site.properties.boarding_authorised === false),
  );
});
test("historical finalist and time scenes are not current-proposal scenes", () => {
  assert.deepEqual(NODO8_SCENES, ["nodo8", "nodo8-time", "end"]);
  assert.ok(!NODO8_SCENES.includes("finalists"));
  assert.ok(!NODO8_SCENES.includes("time"));
});
test("changed authority, incomplete sites or calendar fail closed", () => {
  for (const change of [
    (value) => {
      value.authority.primary_selection_authorised = true;
    },
    (value) => {
      value.authority.runner_up_selection_authorised = true;
    },
    (value) => {
      value.authority.public_operating_timetable_authorised = true;
    },
    (value) => {
      value.sites.pop();
    },
    (value) => {
      value.trips.pop();
    },
    (value) => {
      value.calendar.service_year = 2028;
    },
  ]) {
    const changed = structuredClone(data);
    change(changed);
    assert.throws(() => validateNodo8(changed));
  }
});
