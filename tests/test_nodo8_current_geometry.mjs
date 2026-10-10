import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {currentGeodesicMetres, indexCurrentShape, matchCurrentCalls, positionOnCurrentShape,
  reconstructCurrentGeometry, currentFsStationEvidence, applyDisplayOccurrenceAnchors} from "../nodo8-current-geometry.mjs";

const near = (actual, expected, tolerance = 1e-8) => assert.ok(Math.abs(actual - expected) < tolerance, `${actual} != ${expected}`);
const call = (sequence, coordinates, stop_id = String(sequence), distance) => ({sequence, coordinates, stop_id, distance});

test("continuous monotone least squares pools reversed calls at their centroid", () => {
  const index = indexCurrentShape({coordinates:[[0, 0], [0.001, 0]]});
  const matched = matchCurrentCalls(index, [call(1, [0.0008, 0]), call(2, [0.0002, 0])]);
  matched.calls.forEach(c => near(c.coordinates[0], 0.0005));
  near(matched.calls[0].chainage_metres, matched.calls[1].chainage_metres);
  const dx = currentGeodesicMetres([0.0008, 0], [0.0005, 0]);
  near(matched.objective_squared_local_metres, 2 * dx ** 2, 1e-7);
});

test("global matching resolves crossing nearest projections without a greedy backward jump", () => {
  const index = indexCurrentShape({coordinates:[[0, 0], [0.001, 0], [0.001, 0.0001], [0, 0.0001]]});
  const matched = matchCurrentCalls(index, [call(1, [0.0002, 0.00009]), call(2, [0.0008, 0])]);
  near(matched.calls[0].coordinates[0], 0.0002);
  near(matched.calls[0].coordinates[1], 0);
  near(matched.calls[1].coordinates[0], 0.0008);
  near(matched.calls[1].coordinates[1], 0);
  assert.ok(matched.calls[0].chainage_metres < matched.calls[1].chainage_metres);
});

test("repeated stops on a loop retain occurrence sequence and complete loop distance", () => {
  const shape = {coordinates:[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]};
  const index = indexCurrentShape(shape);
  const calls = [call(1, [0, 0], "A"), call(2, [0.001, 0], "B"), call(3, [0.001, 0.001], "C"), call(4, [0, 0], "A")];
  const matched = matchCurrentCalls(index, calls);
  assert.deepEqual(matched.calls.map(c => [c.sequence, c.stop_id]), [[1,"A"],[2,"B"],[3,"C"],[4,"A"]]);
  near(matched.calls[0].chainage_metres, 0);
  near(matched.calls.at(-1).chainage_metres, index.distances.at(-1));
  matched.calls.forEach(c => near(c.offset_metres, 0));
  assert.strictEqual(index.coordinates, shape.coordinates);
});

test("source distance breaks only exact geometric ties between indistinguishable loop occurrences", () => {
  const shape = {coordinates:[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0],], distances:[0, 1, 2, 3]};
  const index = indexCurrentShape(shape);
  const matched = matchCurrentCalls(index, [call(1, [0, 0], "A", 0), call(2, [0, 0], "A", 3)]);
  near(matched.calls[0].chainage_metres, 0);
  near(matched.calls[1].chainage_metres, index.distances.at(-1));
  near(matched.objective_squared_local_metres, 0);
});

test("playback follows original shape vertices and clamps only the path extent", () => {
  const index = indexCurrentShape({coordinates:[[9, 45], [9.001, 45], [9.001, 45.002], [9.004, 45.002]]});
  index.coordinates.forEach((c, i) => assert.deepEqual(positionOnCurrentShape(index, index.distances[i]), c));
  const middle = (index.distances[1] + index.distances[2]) / 2;
  const coordinates = positionOnCurrentShape(index, middle);
  near(coordinates[0], 9.001);
  near(coordinates[1], 45.001);
  assert.deepEqual(positionOnCurrentShape(index, -1), index.coordinates[0]);
  assert.deepEqual(positionOnCurrentShape(index, index.distances.at(-1) + 1), index.coordinates.at(-1));
});

test("invalid coordinates and occurrence order fail before reconstruction", () => {
  assert.throws(() => indexCurrentShape({coordinates:[[0, 0], [NaN, 0]]}));
  assert.throws(() => indexCurrentShape({coordinates:[[0, 0], [0, 0]]}));
  const index = indexCurrentShape({coordinates:[[0, 0], [0.001, 0]]});
  assert.throws(() => matchCurrentCalls(index, [call(2, [0, 0]), call(1, [0.001, 0])]));
  assert.throws(() => positionOnCurrentShape(index, NaN));
});

const data = JSON.parse(readFileSync(new URL("../assets/nodo8-current-simulation.json", import.meta.url), "utf8"));
const before = JSON.stringify(data);
const geometry = reconstructCurrentGeometry(data);

test("dated geometry is reproducible and preserves source shape, stops and clocks", () => {
  assert.equal(JSON.stringify(data), before);
  assert.deepEqual(geometry.summary, reconstructCurrentGeometry(data).summary);
  assert.deepEqual([geometry.summary.trips, geometry.summary.shapes, geometry.summary.patterns, geometry.summary.calls, geometry.summary.legs], [34,17,17,422,388]);
  for (const trip of geometry.trips) {
    const source = data.trips.find(t => t.id === trip.id), index = geometry.shapes[trip.shape_id];
    assert.strictEqual(index.coordinates, data.shapes[trip.shape_id].coordinates);
    assert.deepEqual(trip.calls.map(c => [c.stop_id, c.sequence]), source.calls.map(c => [c.stop_id, c.sequence]));
    trip.calls.forEach((c, i) => {
      assert.ok(!i || c.chainage_metres >= trip.calls[i - 1].chainage_metres);
      assert.deepEqual(c.coordinates, positionOnCurrentShape(index, c.chainage_metres));
    });
    trip.legs.forEach((l, i) => near(l.source_seconds, (source.calls[i + 1].arrival_min - source.calls[i].departure_min) * 60));
  }
});

test("geometric correction exposes the terminal source mismatch and cannot repair 10-second clocks", () => {
  const calls = geometry.trips.flatMap(t => t.calls), outliers = calls.filter(c => c.offset_metres > 2);
  assert.equal(outliers.length, 12);
  assert.ok(outliers.every(c => c.stop_id === "300407"));
  near(geometry.summary.max_offset_metres, 486.3326516990398, 1e-6);
  assert.ok(calls.filter(c => c.stop_id !== "300407").every(c => c.offset_metres < 2));
  assert.ok(geometry.summary.mean_offset_metres < geometry.summary.mean_source_offset_metres);
  assert.equal(geometry.summary.source_legs_over_90, 48);
  assert.equal(geometry.summary.legs_over_90, 48);
  near(geometry.summary.max_mean_kmh, 565.2088069323752, 1e-6);
});

const proposal = JSON.parse(readFileSync(new URL("../assets/nodo8-proposal.json", import.meta.url), "utf8"));
const stationEvidence = currentFsStationEvidence(proposal);

test("explicit return-only FS display anchors retain source mismatch and exact official endpoint", () => {
  const originalGeometry = JSON.stringify(geometry);
  const displayed = applyDisplayOccurrenceAnchors(data, geometry, stationEvidence);
  const anchored = displayed.trips.flatMap(t => t.calls.filter(c => c.display_anchor_evidence).map(c => ({c,t})));
  assert.equal(anchored.length, 12);
  assert.equal(displayed.display_anchor_summary.unchanged_statale_departure_calls, 10);
  for (const {c,t} of anchored) {
    const source = data.trips.find(raw => raw.id === t.id), index = geometry.shapes[t.shape_id];
    assert.equal(c.sequence, source.calls.at(-1).sequence);
    assert.deepEqual(c.display_coordinates, index.coordinates.at(-1));
    assert.equal(c.display_chainage_metres, index.distances.at(-1));
    assert.deepEqual(c.display_source_coordinates, [9.40576,45.73371]);
    assert.ok(c.display_source_offset_metres > 500);
    assert.ok(c.display_anchor_evidence.endpoint_station_offset_metres < 7);
    assert.equal(c.display_anchor_evidence.physical_stop_relocated, false);
    assert.equal(c.display_anchor_evidence.physical_stop_certified, false);
  }
  assert.equal(JSON.stringify(geometry), originalGeometry);
  assert.equal(JSON.stringify(data), before);
});

test("outbound FS shape starts remain at Statale without inserting a station leg", () => {
  const displayed = applyDisplayOccurrenceAnchors(data, geometry, stationEvidence);
  const starts = displayed.trips.flatMap(t => t.calls.filter(c => c.display_role === "FS_VIA_STATALE_SHAPE_START").map(c => ({c,t})));
  assert.equal(starts.length, 10);
  for (const {c,t} of starts) {
    assert.equal(c.display_chainage_metres, 0);
    assert.deepEqual(c.display_coordinates, [9.40576,45.73371]);
    assert.equal(c.display_source_offset_metres, 0);
    assert.equal(c.display_anchor_evidence, undefined);
    assert.ok(currentGeodesicMetres(c.display_coordinates, stationEvidence.coordinates) > 500);
    assert.strictEqual(displayed.shapes[t.shape_id].coordinates, data.shapes[t.shape_id].coordinates);
  }
});

test("FS display policy validates station provenance, direction and 50m endpoint condition", () => {
  const wrongStation = structuredClone(proposal); wrongStation.sites.find(s => s.site_id === "FROZEN::L00407").coordinates_lon_lat[0] += 0.01;
  assert.throws(() => currentFsStationEvidence(wrongStation));
  assert.throws(() => applyDisplayOccurrenceAnchors(data, geometry, {...stationEvidence, site_id:"invented"}));
  const wrongDirection = structuredClone(data), trip = wrongDirection.trips.find(t => t.shape_id === "+++D84++012");
  trip.direction_id = "0";
  const displayed = applyDisplayOccurrenceAnchors(wrongDirection, geometry, stationEvidence);
  assert.equal(displayed.trips.find(t => t.id === trip.id).calls.at(-1).display_anchor_evidence, undefined);
  const wrongEndpoint = structuredClone(data); wrongEndpoint.shapes["+++D84++012"].coordinates.at(-1)[0] += 0.001;
  const endpointModel = applyDisplayOccurrenceAnchors(wrongEndpoint, reconstructCurrentGeometry(wrongEndpoint), stationEvidence);
  assert.equal(endpointModel.display_anchor_summary.anchored_return_calls, 7);
});
