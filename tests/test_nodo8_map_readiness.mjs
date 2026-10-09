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
test("independent network switches share simulation and map views, with official route and stop filters", () => {
  const markup = explorerSource.slice(explorerSource.indexOf("    controls.innerHTML ="), explorerSource.indexOf("    document.body.appendChild(controls)"));
  for (const network of ["nodo8", "s8", "d184", "d185"])
    assert.equal((markup.match(new RegExp(`data-layer="${network}"`, "g")) || []).length, 1);
  assert.match(explorerSource, /id="currentRouteChoice"/);
  assert.match(explorerSource, /map\.setFilter\(id, routeFilter\)/);
  assert.match(explorerSource, /map\.setFilter\(id, stopFilter\)/);
  assert.match(explorerSource, /GTFS ufficiale 2025\/26/);
  assert.match(explorerSource, /fotografia storica non è l’orario più recente 2026\/27/);
  const fit = explorerSource.slice(explorerSource.indexOf("  function fit(force = false)"), explorerSource.indexOf("  function interactions(on)"));
  assert.match(fit, /layers\.current \? currentFeatures\.filter/);
  assert.match(fit, /layers\.proposals \? lineage\.finalData\.features : \[\]/);
  assert.doesNotMatch(fit, /\.\.\.lineage\.anchorData/);
});
test("explorer walking access never uses the static narrative baseline or implicit current stops", () => {
  assert.match(explorerRender, /opacity\("piece-halo", 0\)/);
  assert.match(explorerSource, /activeWalkFeatureCollection\(model, networks\)/);
  assert.match(explorerRender, /layers\.nodo8 \? \["NODO8"\]/);
  assert.match(explorerRender, /cur && currentChoice !== "D185" \? \["D184"\]/);
  assert.match(explorerRender, /cur && currentChoice !== "D184" \? \["D185"\]/);
  assert.doesNotMatch(explorerRender, /\|\| layers\.walk/);
  assert.doesNotMatch(explorerSource, /data-layer="(?:candidates|proposals)"/);
  assert.doesNotMatch(explorerSource, /id="exploreSiteSelect"/);
});
test("independent D switches keep the hidden dated-player selection synchronized, including neither", () => {
  const code = explorerSource.slice(explorerSource.indexOf("  function syncCurrentSelection()"),explorerSource.indexOf("  async function ensureActiveWalk()"));
  for (const [d184,d185,expected] of [[true,true,"ALL"],[true,false,"D184"],[false,true,"D185"],[false,false,"ALL"]]) {
    const layers = {d184,d185,current:false}, compatibilityState = {}, choice = {value:null};
    runInNewContext(code + "\nsyncCurrentSelection();",{layers,compatibilityState,controls:{querySelector:()=>choice}});
    assert.equal(layers.current,d184||d185);
    assert.equal(compatibilityState.current,d184||d185);
    assert.equal(choice.value,expected);
  }
});
test("each current-line selection filters routes and shared stops together", () => {
  const start = explorerRender.indexOf('    const currentChoice =');
  const end = explorerRender.indexOf('    opacity("explore-current-hit"');
  const filterCode = explorerRender.slice(start, end);
  for (const choice of ["ALL", "D184", "D185"]) {
    const writes = [];
    runInNewContext(filterCode, {
      controls: {querySelector:()=>({value:choice})},
      map: {getLayer:()=>true,setFilter:(id,filter)=>writes.push([id,JSON.parse(JSON.stringify(filter))])},
    });
    assert.equal(writes.length,5);
    const route = writes.find(([id])=>id === "explore-current-routes")[1];
    const stop = writes.find(([id])=>id === "explore-current-stops")[1];
    if (choice === "ALL") {
      assert.deepEqual(route,["in",["get","route"],["literal",["D184","D185"]]]);
      assert.equal(stop[0],"any");
    } else {
      assert.deepEqual(route,["==",["get","route"],choice]);
      assert.deepEqual(stop,[">=",["index-of",choice,["get","routes"]],0]);
    }
  }
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
test("changing story column uses a camera offset, not padding retained into fitBounds", () => {
  const source = readFileSync(new URL("../dietro-l-analisi/journey.js", import.meta.url), "utf8");
  const camera = source.slice(source.indexOf("  function camera(opts)"), source.indexOf("  function setScene(scene)"));
  for (const [left, right] of [[544, 58], [40, 544]]) {
    const calls = [];
    runInNewContext(camera + "\ncamera({zoom:12});", {
      map: { easeTo: options => calls.push(options) },
      window: { __analysisJourneyMapFrame: () => ({ left, right, top: 100, bottom: 70 }) },
    });
    assert.equal(calls[0].padding, 0);
    assert.equal(calls[0].offset[0], (left - right) / 2);
    assert.equal(calls[0].offset[1], 15);
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
