import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { waitForPreparedMap, storyMapPadding } from "../dietro-l-analisi/journey-map-ready.mjs";

const explorerSource = readFileSync(new URL("../dietro-l-analisi/journey-explore-v2.js", import.meta.url), "utf8");
const explorerRender = explorerSource.slice(explorerSource.indexOf("  function render() {"), explorerSource.indexOf("  function fit(force = false)"));
function renderWrites(scene) {
  const writes = [];
  runInNewContext(explorerRender + "\nrender();", {
    document: { body: { dataset: { scene } } },
    active: false, controls: null, popup: null,
    layers: { nodo8: true, stops: true },
    opacity: (id, value) => writes.push([id, value]),
    map: { getLayer: () => false },
    window: { __analysisJourneyNodo8: { renderExplorer() {} } },
  });
  return writes;
}
test("inactive explorer cannot erase KML routes or any narrative population layer", () => {
  for (const scene of ["grid", "sections", "buildings", "walk", "roads", "baseline", "candidates", "finalists", "nodo8", "end"]) {
    const writes = renderWrites(scene);
    assert.ok(writes.length > 0, scene);
    assert.ok(writes.every(([id, value]) => id.startsWith("explore-") && value === 0), scene);
  }
});
test("active exploration still owns shared-layer composition and clears narrative KML", () => {
  const writes = renderWrites("explore");
  assert.ok(writes.some(([id, value]) => id === "current-routes" && value === 0));
  assert.ok(writes.some(([id]) => id === "worldpop-columns"));
});
test("map evidence is framed outside the actual left or right narrative column", () => {
  const dimensions = { width: 1280, height: 720 };
  const left = storyMapPadding({ ...dimensions, copyRect: { left: 64, right: 524, width: 460 } });
  assert.equal(left.left, 544);
  assert.ok(dimensions.width - left.left - left.right >= 350);
  const right = storyMapPadding({ ...dimensions, side: "right", copyRect: { left: 756, right: 1216, width: 460 } });
  assert.equal(right.right, 544);
  assert.ok(dimensions.width - right.left - right.right >= 350);
  const wide = storyMapPadding({ ...dimensions, copyRect: { left: 64, right: 1114, width: 1050 } });
  assert.ok(dimensions.width - wide.left - wide.right >= 350);
});
test("mobile map framing does not reserve a full-width card or collapse the map window", () => {
  assert.deepEqual(storyMapPadding({ width: 390, height: 844, copyRect: { left: 17, right: 373, width: 356 } }),
    { top: 90, bottom: 70, left: 25, right: 25 });
});
test("deep links bind chapter controls and scroll triggers to sections, never the active body", () => {
  for (const name of ["journey-director.js", "journey-effects.js", "journey-lens.js", "journey-lineage.js", "journey-explore-prelude.js", "journey-explore-v2.js"]) {
    const source = readFileSync(new URL("../dietro-l-analisi/" + name, import.meta.url), "utf8");
    assert.doesNotMatch(source, /querySelector\(["'`]\[data-scene=/, name);
  }
});
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
