import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {reconcileCurrentDisplayProfile, reconcileCurrentDisplayProfiles} from "../nodo8-current-profile.mjs";
import {reconstructCurrentGeometry, applyDisplayOccurrenceAnchors, currentFsStationEvidence} from "../nodo8-current-geometry.mjs";

const near = (a, b, epsilon = 1e-8) => assert.ok(Math.abs(a - b) < epsilon, `${a} != ${b}`);
function fixture(metres, seconds) {
  const source = seconds.map((s, i) => ({sequence:i + 1, stop_id:`S${i}`, arrival_min:s / 60, departure_min:s / 60}));
  const geometry = metres.map((s, i) => ({sequence:i + 1, stop_id:`S${i}`, chainage_metres:s}));
  return {source, geometry};
}

test("maximum-cardinality source anchors can skip the first individually compatible anchor", () => {
  const {source, geometry} = fixture([0,100,400,700,1000], [0,14,21,34,54]);
  const profile = reconcileCurrentDisplayProfile(source, geometry);
  assert.equal(profile.feasible, true);
  assert.deepEqual(profile.kept_anchor_indices, [0,2,3,4]);
  assert.deepEqual(profile.dropped_anchor_indices, [1]);
  near(profile.calls[1].display_arrival_min * 60, 5.25);
  assert.equal(profile.calls[1].source_arrival_min * 60, 14);
  assert.equal(profile.calls[1].timing_basis, "CHAINAGE_INTERPOLATION_BETWEEN_RETAINED_SOURCE_CLOCKS");
});

test("equal-count compatible anchor choices use lexicographic source occurrence indices", () => {
  const {source, geometry} = fixture([0,100,200,300], [0,9,12,20]);
  const profile = reconcileCurrentDisplayProfile(source, geometry);
  assert.deepEqual(profile.kept_anchor_indices, [0,1,3]);
  assert.deepEqual(reconcileCurrentDisplayProfile(source, geometry), profile);
});

test("impossible endpoint windows fail closed without moving either source clock", () => {
  const {source, geometry} = fixture([0,500,2000], [600,630,660]);
  const before = JSON.stringify(source);
  const profile = reconcileCurrentDisplayProfile(source, geometry);
  assert.equal(profile.feasible, false);
  assert.equal(profile.failure, "ENDPOINT_WINDOW_EXCEEDS_DISPLAY_CEILING");
  near(profile.evidence.mean_kmh, 120);
  assert.deepEqual(profile.calls, []);
  assert.equal(JSON.stringify(source), before);
});

test("collapsed, backward, missing and mismatched occurrence geometries fail closed", () => {
  for (const positions of [[0,0,100], [0,100,90], [0,NaN,100]]) {
    const {source, geometry} = fixture(positions, [0,30,60]);
    const result = reconcileCurrentDisplayProfile(source, geometry);
    assert.equal(result.feasible, false);
    assert.equal(result.failure, "GEOMETRIC_CALL_ORDER_NOT_STRICT");
    assert.deepEqual(result.calls, []);
  }
  const {source, geometry} = fixture([0,100,200], [0,30,60]);
  geometry[1].stop_id = "other occurrence";
  assert.equal(reconcileCurrentDisplayProfile(source, geometry).feasible, false);
  geometry[1] = null;
  assert.equal(reconcileCurrentDisplayProfile(source, geometry).feasible, false);
});

test("no artificial dwell is introduced and unsupported existing dwell is rejected", () => {
  const {source, geometry} = fixture([0,300,600], [0,10,60]);
  const profile = reconcileCurrentDisplayProfile(source, geometry);
  profile.calls.forEach(c => assert.equal(c.display_arrival_min, c.display_departure_min));
  source[1].departure_min += 0.1;
  assert.equal(reconcileCurrentDisplayProfile(source, geometry).feasible, false);
});

test("retained anchors match an independent exhaustive subset search", () => {
  const {source, geometry} = fixture([0,100,400,700,900,1000,1200,1500], [0,14,21,34,42,46,55,80]);
  const viable = [];
  for (let mask = 0; mask < 1 << (source.length - 2); mask++) {
    const anchors = [0, ...source.slice(1, -1).map((_, i) => i + 1).filter((_, i) => mask & (1 << i)), source.length - 1];
    if (anchors.slice(1).every((to, i) => {
      const from = anchors[i];
      return (geometry[to].chainage_metres - geometry[from].chainage_metres) * 3.6 <=
        (source[to].arrival_min - source[from].departure_min) * 60 * 90 + 1e-6;
    })) viable.push(anchors);
  }
  viable.sort((a, b) => b.length - a.length || (() => {for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] - b[i]; return 0;})());
  assert.deepEqual(reconcileCurrentDisplayProfile(source, geometry).kept_anchor_indices, viable[0]);
});

const data = JSON.parse(readFileSync(new URL("../assets/nodo8-current-simulation.json", import.meta.url), "utf8"));
const proposal = JSON.parse(readFileSync(new URL("../assets/nodo8-proposal.json", import.meta.url), "utf8"));
const before = JSON.stringify(data);
const geometry = applyDisplayOccurrenceAnchors(data, reconstructCurrentGeometry(data), currentFsStationEvidence(proposal));
const geometryBefore = JSON.stringify(geometry);
const profiles = reconcileCurrentDisplayProfiles(data, geometry);

test("all dated trips retain endpoint clocks while the derived model has zero excessive leg means", () => {
  assert.deepEqual([profiles.summary.trips, profiles.summary.feasible_trips, profiles.summary.infeasible_trips], [34,34,0]);
  assert.equal(profiles.summary.calls, 422);
  assert.equal(profiles.summary.retained_source_clock_anchors, 374);
  assert.equal(profiles.summary.derived_internal_clocks, 48);
  assert.equal(profiles.summary.source_legs_over_ceiling, 48);
  assert.equal(profiles.summary.model_legs_over_ceiling, 0);
  assert.ok(profiles.summary.max_model_mean_kmh <= 90 + 1e-8);
  for (const profile of profiles.trips) {
    const source = data.trips.find(t => t.id === profile.id);
    assert.equal(profile.calls[0].display_arrival_min, source.calls[0].arrival_min);
    assert.equal(profile.calls.at(-1).display_departure_min, source.calls.at(-1).departure_min);
    assert.equal(profile.kept_anchor_indices[0], 0);
    assert.equal(profile.kept_anchor_indices.at(-1), source.calls.length - 1);
    profile.calls.forEach((c, i) => {
      assert.equal(c.source_arrival_min, source.calls[i].arrival_min);
      assert.equal(c.source_departure_min, source.calls[i].departure_min);
      assert.equal(c.display_arrival_min, c.display_departure_min);
      if (c.source_clock_retained) assert.equal(c.display_arrival_min, c.source_arrival_min);
      if (i) assert.ok(c.display_arrival_min > profile.calls[i - 1].display_departure_min);
    });
    profile.legs.forEach(l => assert.ok(l.mean_kmh > 0 && l.mean_kmh <= 90 + 1e-8));
  }
  assert.equal(JSON.stringify(data), before);
  assert.equal(JSON.stringify(geometry), geometryBefore);
});

test("profile semantics cannot imply a repaired timetable, physical certification or inferred dwell", () => {
  assert.equal(profiles.semantics.source_clocks_unchanged, true);
  assert.equal(profiles.semantics.official_timetable_repaired, false);
  assert.equal(profiles.semantics.actual_vehicle_speed_certified, false);
  assert.equal(profiles.semantics.inferred_dwell, false);
});
