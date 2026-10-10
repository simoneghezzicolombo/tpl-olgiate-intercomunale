import test from "node:test";
import {validateBenefits,benefitsView} from "../nodo8-benefits.mjs";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  makeNodo8Features,
  validateNodo8,
  NODO8_SCENES,
  playbackVisible,
  popupSiteRows,
  stationMapFeature,
} from "../dietro-l-analisi/journey-nodo8.mjs";
import { buildLine, statesAt } from "../nodo8-line.mjs";
import { validateCoverageComparison, coverageChangeLabel } from "../nodo8-coverage.mjs";
import { buildCurrent, currentTripsAt, currentPositionQuality, installCurrent, CURRENT_DISPLAY_SEGMENT_MEAN_LIMIT_KMH } from "../nodo8-current.mjs";

const data = JSON.parse(
  readFileSync(
    new URL("../assets/nodo8-proposal.json", import.meta.url),
    "utf8",
  ),
);
const coverageComparison = JSON.parse(readFileSync(new URL("../assets/nodo8-coverage-comparison.json", import.meta.url), "utf8"));
const serviceComparison=JSON.parse(readFileSync(new URL("../assets/nodo8-service-comparison.json",import.meta.url),"utf8"));
const coverageDiagnostic=JSON.parse(readFileSync(new URL("../assets/nodo8-coverage-diagnostic.json",import.meta.url),"utf8"));
test("station point uses the single confirmed hub site without moving or mutating source coordinates",()=>{
  const before=JSON.stringify(data),feature=stationMapFeature(data);
  const site=data.sites.find(s=>s.hub_service_roles.length);
  assert.deepEqual(feature.features[0].geometry.coordinates,site.coordinates_lon_lat);
  assert.equal(feature.features[0].properties.site_id,site.site_id);
  assert.equal(JSON.stringify(data),before);
  const duplicate=structuredClone(data);duplicate.sites.find(s=>!s.hub_service_roles.length).hub_service_roles=["invented"];
  assert.throws(()=>stationMapFeature(duplicate));
  const invalid=structuredClone(data);invalid.sites.find(s=>s.hub_service_roles.length).coordinates_lon_lat=[NaN,45];
  assert.throws(()=>stationMapFeature(invalid));
});
test("compact stop popups preserve all ordered occurrences and express durations in minutes and seconds",()=>{
  const line=buildLine(data);
  for(const site of data.sites) {
    const rows=popupSiteRows(line,site.site_id);
    if(site.hub_service_roles.length) assert.deepEqual(rows.map(r=>r.role),["FULL_TRIP_START_FS","INTERMEDIATE_FS_STAY_ONBOARD_DESIGN","FULL_TRIP_END_FS"]);
    else {
      assert.deepEqual(rows.map(r=>r.ordinal),site.ordered_occurrences.map(e=>e.ordered_nonhub_event_number));
      rows.forEach(r=>{assert.match(r.fromFs,/^\d+ min \d{2} s$/);assert.match(r.toFs,/^\d+ min \d{2} s$/);});
    }
  }
});
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
    shown.find((site) => site.properties.name === "Olgiate Aldo Moro").properties
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

const currentData = buildCurrent(JSON.parse(readFileSync(new URL("../assets/nodo8-current-simulation.json", import.meta.url), "utf8")));
test("existing-service display guard withholds inconsistent source intervals without changing clocks or inventory", () => {
  const before = JSON.stringify(currentData);
  const trip = currentData.trips.find(t => t.id === "A2013327-0036-50214");
  const minute = (trip.calls[0].departure_min + trip.calls[1].arrival_min) / 2;
  const state = currentTripsAt(currentData, minute).find(t => t.id === trip.id);
  const quality = currentPositionQuality(currentData, {...state, minute});
  assert.equal(state.status, "moving");
  assert.equal(CURRENT_DISPLAY_SEGMENT_MEAN_LIMIT_KMH, 90);
  assert.equal(quality.displayable, false);
  assert.equal(quality.reason, "EXCEEDS_ENGINEERING_DISPLAY_GUARD");
  assert.ok(Math.abs(quality.segment_metres - 1570.0244637006854) < 0.01);
  assert.ok(Math.abs(quality.segment_mean_kmh - 565.2088069323753) < 0.01);
  let withheld = 0, legs = 0;
  for (const t of currentData.trips) for (let i = 1; i < t.calls.length; i++) {
    const minute = (t.calls[i - 1].departure_min + t.calls[i].arrival_min) / 2;
    const state = currentTripsAt(currentData, minute).find(s => s.id === t.id);
    if (!currentPositionQuality(currentData, {...state, minute}).displayable) withheld++;
    legs++;
  }
  assert.equal(legs, 388);
  assert.equal(withheld, 48);
  assert.equal(currentData.trips.length, 34);
  assert.equal(JSON.stringify(currentData), before);
  assert.equal(currentPositionQuality(currentData, state).displayable, false);
});

test("stop-to-shape offsets stay diagnostic and do not fabricate a position or dwell", () => {
  const trip = currentData.trips.find(t => t.id === "A2013327-0019-52778");
  const call = trip.calls.find(c => c.stop_id === "300407");
  const minute = call.arrival_min;
  const state = currentTripsAt(currentData, minute).find(t => t.id === trip.id);
  const before = [...state.coordinates];
  const quality = currentPositionQuality(currentData, {...state, minute});
  assert.equal(quality.displayable, true);
  assert.equal(quality.reason, "SOURCE_STOP_CALL");
  assert.ok(Math.abs(quality.stop_shape_offset_metres - 546.5009952605039) < 0.01);
  assert.deepEqual(state.coordinates, before);
  assert.notDeepEqual(state.coordinates, call.coordinates);
  assert.equal(call.arrival_min, call.departure_min);
});

test("reconciled renderer keeps every active trip visible without rewriting the raw clocks", async () => {
  const saved = {fetch:globalThis.fetch, window:globalThis.window, document:globalThis.document};
  const markers = new Set(), status = {hidden:true, textContent:""}, dataset = {};
  class Marker {
    constructor({element}) {this.element = element;}
    setLngLat(coordinates) {this.coordinates = coordinates;return this;}
    addTo() {markers.add(this);return this;}
    remove() {markers.delete(this);}
  }
  const display = JSON.parse(readFileSync(new URL("../assets/nodo8-current-playback.json",import.meta.url),"utf8"));
  const proposal = JSON.parse(readFileSync(new URL("../assets/nodo8-proposal.json",import.meta.url),"utf8"));
  globalThis.fetch = async url => ({ok:true, json:async () => url.includes("current-playback") ? display : url.includes("proposal") ? proposal : currentData});
  globalThis.window = {maplibregl:{Marker}};
  globalThis.document = {documentElement:{dataset}, getElementById:() => status,
    createElement:() => ({dataset:{}, attributes:{}, setAttribute(name, value) {this.attributes[name] = value;}})};
  const map = {addSource() {}, addLayer() {}, setPaintProperty() {}, setFilter() {}};
  try {
    const renderer = await installCurrent(map);
    const trip = currentData.trips.find(t => t.id === "A2013327-0036-50214");
    const minute = (trip.calls[0].departure_min + trip.calls[1].arrival_min) / 2;
    renderer.render({minute, visible:true});
    const active = currentTripsAt(currentData, minute);
    assert.equal(Number(dataset.currentBusCount), active.length);
    assert.equal(Number(dataset.currentBusMarkerCount), markers.size);
    assert.equal(markers.size,active.length);
    assert.equal(Number(dataset.currentBusWithheldPositionCount),0);
    assert.equal(Number(dataset.currentBusEstimatedPositionCount),active.length);
    assert.ok([...markers].some(m => m.element.dataset.trip === trip.id));
    assert.doesNotMatch(status.textContent, /non affidabil/);
    assert.doesNotMatch(status.textContent, /2026|maggio|06\/05/);
    renderer.render({minute:trip.calls[1].arrival_min, visible:true});
    assert.ok([...markers].some(m => m.element.dataset.trip === trip.id));
    renderer.render({minute, visible:false});
    assert.equal(markers.size, 0);
    assert.equal(dataset.currentBusCount, "0");
    assert.equal(dataset.currentBusMarkerCount, "0");
    assert.equal(dataset.currentPlaybackModel,"reconciled-v2");
    assert.equal(dataset.currentPlaybackDate,"2026-04-28");
    assert.equal(status.hidden, true);
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  }
});
