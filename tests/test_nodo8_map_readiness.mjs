import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { waitForPreparedMap } from "../dietro-l-analisi/journey-map-ready.mjs";
test("cached route data cannot overtake the primary style/route setup", async () => {
  let hub = false,
    routes = false,
    settled = false;
  const map = { getLayer: () => hub, getSource: () => routes };
  const ready = waitForPreparedMap(map, { timeoutMs: 1000, pollMs: 1 }).then(
    (m) => {
      settled = true;
      return m;
    },
  );
  await new Promise((r) => setTimeout(r, 3));
  assert.equal(settled, false);
  routes = true;
  await new Promise((r) => setTimeout(r, 3));
  assert.equal(settled, false);
  hub = true;
  assert.equal(await ready, map);
});
test("ready style does not wait for unrelated raster tiles", async () => {
  const map = {
    getLayer: () => ({}),
    getSource: () => ({}),
    isStyleLoaded: () => false,
  };
  assert.equal(await waitForPreparedMap(map), map);
});
test("missing primary sources fail closed at the deadline", async () => {
  await assert.rejects(
    waitForPreparedMap(
      { getLayer: () => false, getSource: () => false },
      { timeoutMs: 5, pollMs: 1 },
    ),
    /deadline/,
  );
});
test("legacy mutations are gated and KML awaits the complete lineage install", () => {
  const legacy = readFileSync(
    new URL("../dietro-l-analisi/journey-lineage.js", import.meta.url),
    "utf8",
  );
  const install = legacy.slice(legacy.indexOf("async function install()"));
  assert.ok(
    install.indexOf("await waitForPreparedMap(map)") <
      install.indexOf("map.getSource('current-routes')?.setData"),
  );
  const kml = readFileSync(
    new URL(
      "../dietro-l-analisi/journey-current-kml-exact.mjs",
      import.meta.url,
    ),
    "utf8",
  );
  assert.ok(kml.includes("await window.__analysisJourneyLineageReady"));
});
