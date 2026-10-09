import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { validateActiveWalkAsset, activeWalkNetworks, activeWalkFeatureCollection, activeWalkLabel } from "../nodo8-active-walk.mjs";

const asset = JSON.parse(readFileSync(new URL("../assets/nodo8-active-walk.json", import.meta.url), "utf8"));
const proposal = JSON.parse(readFileSync(new URL("../assets/nodo8-proposal.json", import.meta.url), "utf8"));
const current = JSON.parse(readFileSync(new URL("../assets/nodo8-current-simulation.json", import.meta.url), "utf8"));

test("active walking asset preserves exact population IDs and reproduces confirmed Nodo8 coverage", () => {
  assert.equal(validateActiveWalkAsset(asset, proposal), asset);
  assert.equal(asset.rows.length, 4283);
  assert.equal(new Set(asset.rows.map(row => row[0])).size, 4283);
  const sourcePath = new URL("../" + asset.sources.population_coordinates.path, import.meta.url);
  // The frozen cache is kept outside the site publication checkout. Locally,
  // also verify every exact ID/coordinate join against that full source file.
  if (existsSync(sourcePath)) {
    const sourceRows = readFileSync(sourcePath, "utf8").trim().split(/\r?\n/).slice(1).map(line => line.split(","));
    const population = new Map(sourceRows.map(row => [row[0], row]));
    const coreIds = sourceRows.filter(row => row[8] === "core").map(row => row[0]).sort();
    assert.deepEqual(asset.rows.map(row => row[0]), coreIds);
    for (const [id, lon, lat, code, weight] of asset.rows) {
      const source = population.get(id);
      assert.deepEqual([lon, lat], [Number(source[2]), Number(source[1])]);
      assert.equal(code, String(Number(source[3])));
      assert.ok(Math.abs(weight - Number(source[7])) < 1e-10);
    }
  }
  for (const key of ["proposal", "dated_current_service"]) {
    const source = asset.sources[key];
    const bytes = readFileSync(new URL("../" + source.path, import.meta.url), "utf8").replaceAll("\r\n", "\n");
    assert.equal(createHash("sha256").update(bytes).digest("hex"), source.sha256);
  }
  assert.deepEqual(asset.nodo8_percent, proposal.coverage);
});

test("D184 and D185 use exact stops from their 34 dated GTFS trips", () => {
  for (const route of ["D184", "D185"]) {
    const calls = new Map(current.trips.filter(trip => trip.route === route).flatMap(trip => trip.calls.map(call => [call.stop_id, call.coordinates])));
    const evidence = asset.network_evidence[route];
    assert.equal(evidence.dated_trip_count, current.route_counts[route]);
    assert.equal(evidence.stop_identity_count, calls.size);
    assert.deepEqual(evidence.stops.map(stop => [stop.stop_id, stop.coordinates_lon_lat]), [...calls.entries()].sort(([a], [b]) => a.localeCompare(b)));
    assert.equal(evidence.attached_stop_count, evidence.stops.filter(stop => stop.snap_status === "REACHABLE").length);
    for (const stop of evidence.stops) {
      if (stop.snap_status === "REACHABLE") assert.ok(stop.graph_node_id && stop.connector_distance_m >= 0 && stop.connector_distance_m <= 90);
      else assert.ok(stop.snap_reason && stop.graph_node_id === null && stop.connector_distance_m === null);
    }
  }
});

test("each line-only choice uses exactly its own vector, and S8 cannot add access", () => {
  assert.deepEqual(activeWalkNetworks({ s8: true }), []);
  assert.deepEqual(activeWalkNetworks({ nodo8: true, current: true, currentRouteChoice: "D184" }), ["NODO8", "D184"]);
  assert.deepEqual(activeWalkNetworks({ current: true, currentRouteChoice: "D185" }), ["D185"]);
  assert.deepEqual(activeWalkNetworks({ current: true }), ["D184", "D185"]);
  assert.deepEqual(activeWalkFeatureCollection(asset, ["S8"]).features, []);
  for (const [name, index] of [["NODO8", 5], ["D184", 6], ["D185", 7]]) {
    const points = activeWalkFeatureCollection(asset, [name, "S8"]);
    for (let i = 0; i < asset.rows.length; i++) {
      assert.equal(points.features[i].properties.walk_min, asset.rows[i][index]);
      assert.deepEqual(points.features[i].geometry.coordinates, asset.rows[i].slice(1, 3));
      assert.equal(points.features[i].id, asset.rows[i][0]);
    }
  }
  assert.ok(asset.rows.some(row => row[6] !== row[7]), "separate lines cannot silently share a union vector");
});

test("every enabled-network combination takes the finite minimum and retains null when unreachable", () => {
  for (const names of [["NODO8", "D184"], ["NODO8", "D185"], ["D184", "D185"], ["NODO8", "D184", "D185"]]) {
    const indexes = names.map(name => asset.columns.indexOf(name));
    const points = activeWalkFeatureCollection(asset, names).features;
    for (let i = 0; i < asset.rows.length; i++) {
      const values = indexes.map(index => asset.rows[i][index]).filter(value => value !== null);
      assert.equal(points[i].properties.walk_min, values.length ? Math.min(...values) : null);
    }
  }
  const fixture = { rows: [["WP_00001", 9.4, 45.7, "97058", 1, null, 8, null], ["WP_00002", 9.41, 45.7, "97058", 1, null, null, null]] };
  assert.deepEqual(activeWalkFeatureCollection(fixture, ["NODO8", "D184"]).features.map(f => f.properties.walk_min), [8, null]);
  assert.equal(activeWalkLabel(["D185", "NODO8", "S8"]), "Nodo8 + D185");
});

test("model rejects mismatched IDs, connectors, dates, networks and coverage", () => {
  for (const mutate of [copy => copy.rows[0][0] = copy.rows[1][0], copy => copy.rows[0][3] = "external",
    copy => copy.rows[0][5] = -1, copy => copy.rows[0][6] = NaN, copy => copy.current_service_date = "2026-10-09",
    copy => copy.connectors_included = ["population"], copy => copy.s8_contributes = true,
    copy => copy.network_names.push("S8"), copy => copy.nodo8_percent.TOTAL[5] += 1]) {
    const copy = structuredClone(asset);
    mutate(copy);
    assert.throws(() => validateActiveWalkAsset(copy, proposal));
  }
});
