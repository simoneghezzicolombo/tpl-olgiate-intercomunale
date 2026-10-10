import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { waitForPreparedMap, storyMapPadding } from "../dietro-l-analisi/journey-map-ready.mjs";

const explorerSource = readFileSync(new URL("../dietro-l-analisi/journey-explore-v2.js", import.meta.url), "utf8");
const explorerRender = explorerSource.slice(explorerSource.indexOf("  function render() {"), explorerSource.indexOf("  function fit(force = false)"));

test("story refresh cannot replace an active exploration scene or its running clock",()=>{
  const source=readFileSync(new URL("../dietro-l-analisi/journey.js",import.meta.url),"utf8");
  const code=source.slice(source.indexOf("  function updateActive(index)"),source.indexOf('  function restoreStoryChapter()'));
  for(const exploring of [false,true]) {
    const writes=[],node={classList:{toggle:(...args)=>writes.push(args)}};
    runInNewContext(code+'\nupdateActive(0);',{
      document:{body:{classList:{contains:name=>name==="is-map-exploring"&&exploring}}},
      chapters:[{...node,dataset:{scene:"grid",label:"Dove viviamo"}}],railDots:[node],
      hudIndex:{},hudName:{},setScene:scene=>writes.push(scene),
    });
    assert.equal(writes.length,exploring?0:3);
  }
  assert.match(explorerSource,/Explicit navigation leaves exploration/);
  const resize=explorerSource.slice(explorerSource.indexOf('    window.addEventListener("resize"'),explorerSource.indexOf('    new MutationObserver(sceneChanged)'));
  assert.match(resize,/fit\(true\)/);
  assert.doesNotMatch(resize,/exit\(|pauseExplorer|jump\(|layers\[/);
});

test("leaving exploration restores the actual visible chapter after responsive layout changes",()=>{
  const source=readFileSync(new URL("../dietro-l-analisi/journey.js",import.meta.url),"utf8");
  const code=source.slice(source.indexOf("  function restoreStoryChapter()"),source.indexOf('  map.on("load"'));
  const writes=[],events={};
  runInNewContext(code,{innerHeight:800,
    chapters:[{getBoundingClientRect:()=>({top:-700,bottom:-100})},{getBoundingClientRect:()=>({top:100,bottom:900})}],
    updateActive:index=>writes.push(index),document:{addEventListener:(name,fn)=>events[name]=fn}});
  events["journey-story-resume"]();assert.deepEqual(writes,[1]);
  const exit=explorerSource.slice(explorerSource.indexOf("  function exit()"),explorerSource.indexOf("  function inspect("));
  assert.ok(exit.indexOf('classList.remove("is-map-exploring")')<exit.indexOf('new Event("journey-story-resume")'));
});

test("proposal popup closes when leaving exploration even if the proposal layer stays enabled",()=>{
  const source=readFileSync(new URL("../dietro-l-analisi/journey-nodo8.mjs",import.meta.url),"utf8");
  const prefix=source.slice(source.indexOf("    const renderExplorer ="),source.indexOf('      document.documentElement.dataset.nodo8Visible'));
  for(const [visible,active,shouldClose] of [[true,true,false],[true,false,true],[false,true,true],[false,false,true]]) {
    const result={removed:0};
    runInNewContext('let popup={remove:()=>result.removed++};\n'+prefix+'};\nrenderExplorer({visible,active});result.cleared=popup===null;',
      {result,visible,active});
    assert.equal(result.removed,Number(shouldClose));
    assert.equal(result.cleared,shouldClose);
  }
});

test("data and current-stop popups close with Escape and restore keyboard focus without exiting the map",()=>{
  const code=explorerSource.slice(explorerSource.indexOf("  function show(lngLat, html)"),explorerSource.indexOf("  function buildRouteLayers()"));
  const attributes={},events={},result={focusRestored:0,prevented:0,stopped:0};
  const previousFocus={isConnected:true,focus(){document.activeElement=this;result.focusRestored++;}};
  const document={body:{},activeElement:previousFocus};
  const heading={focus(){document.activeElement=this;}};
  const close={setAttribute:(name,value)=>attributes[name]=value};
  const element={querySelector:s=>s===".map-card__title"?heading:close,
    setAttribute:(name,value)=>attributes[name]=value,contains:n=>n===heading||n===close,
    addEventListener:(name,listener)=>events[name]=listener};
  class Popup {
    constructor(options){result.options=options;this.events={};}
    setLngLat(){return this;}setHTML(){return this;}addTo(){return this;}getElement(){return element;}
    on(name,listener){this.events[name]=listener;return this;}
    remove(){document.activeElement=document.body;this.events.close?.();}
  }
  const context={maplibregl:{Popup},map:{},document,active:true,popup:null};
  runInNewContext(code+'\nshow([9,45],"<h3>Test</h3>");',context);
  assert.equal(result.options.className,"journey-map-popup");
  assert.equal(attributes.role,"dialog");assert.equal(attributes["aria-labelledby"],heading.id);
  assert.equal(attributes["aria-label"],"Chiudi informazioni sulla mappa");
  assert.equal(document.activeElement,heading);
  events.keydown({key:"Escape",preventDefault:()=>result.prevented++,stopPropagation:()=>result.stopped++});
  assert.equal(context.popup,null);assert.equal(result.focusRestored,1);
  assert.equal(result.prevented,1);assert.equal(result.stopped,1);
  assert.equal(document.activeElement,previousFocus);
});

test("interactive map allows touch panning and is exposed to assistive technology only in exploration",()=>{
  const css=readFileSync(new URL("../dietro-l-analisi/journey-usability.css",import.meta.url),"utf8");
  assert.match(css,/body\.is-map-exploring \.maplibregl-canvas\s*\{[^}]*touch-action:\s*none\s*!important/);
  assert.match(css,/body\.is-map-exploring main > \.chapter\s*\{[^}]*visibility:\s*hidden/);
  assert.match(css,/body\.is-map-exploring:has\(\.journey-map-popup\) #journeyExplorerControls/);
  assert.match(css,/\.journey-map-popup \.maplibregl-popup-content\s*\{[^}]*background:\s*#f5f2e9\s*!important/);
  const code=explorerSource.slice(explorerSource.indexOf("  function interactions(on)"),explorerSource.indexOf("  function enter()"));
  const writes=[],handler={enable(){},disable(){},disableRotation(){}};
  const map=Object.fromEntries(["dragPan","scrollZoom","doubleClickZoom","boxZoom","keyboard","touchZoomRotate","dragRotate"].map(name=>[name,handler]));
  runInNewContext(code+'\ninteractions(true);interactions(false);',{
    map,document:{getElementById:()=>({setAttribute:(...args)=>writes.push(args)})},
  });
  assert.deepEqual(writes,[["aria-hidden","false"],["aria-hidden","true"]]);
});

test("stop and walking points take precedence over an overlapping proposed-route hit area",()=>{
  const click=explorerSource.slice(explorerSource.indexOf('      const find = (id) => hits.find'));
  assert.ok(click.indexOf('find("current-dated-stops")')<click.indexOf('find("nodo8-hit")'));
  assert.ok(click.indexOf('find("explore-active-walk")')<click.indexOf('find("nodo8-hit")'));
});
test("FS is a centered glyph in the station map layer, never a separately moving DOM marker",()=>{
  const source=readFileSync(new URL("../dietro-l-analisi/journey.js",import.meta.url),"utf8");
  const block=source.slice(source.indexOf('    addLayer({\n      id: "hub",'),source.indexOf('    layersReady = true;'));
  const layers=[],images=[],text=[];
  const ctx={fillText:(...args)=>text.push(args),getImageData:()=>({width:64,height:64})};
  const canvas={getContext:()=>ctx};
  runInNewContext(block,{
    document:{createElement:tag=>{assert.equal(tag,"canvas");return canvas;}},
    map:{addImage:(...args)=>images.push(args)},addLayer:layer=>layers.push(layer),
  });
  assert.equal(layers[0].paint["circle-radius"],12);
  assert.equal(layers[0].source,"hub");
  assert.equal(layers[1].source,"hub");
  assert.equal(layers[1].layout["icon-anchor"],"center");
  assert.equal(layers[1].layout["icon-pitch-alignment"],"viewport");
  assert.equal(images[0][0],"station-fs-text");assert.equal(images[0][2].pixelRatio,2);
  assert.deepEqual(text,[["FS",32,33]]);
  assert.doesNotMatch(source,/hub-marker|new maplibregl\.Marker/);
  assert.match(explorerSource,/const a = \["nodo8-station-point"\]/);
  assert.match(explorerSource,/find\("nodo8-station-point"\) \|\| find\("nodo8-sites"\)/);
});
test("exploration basemap stays faint in both preview and interactive mode",()=>{
  const block=explorerRender.slice(explorerRender.indexOf('    if (map.getLayer("carto"))'),explorerRender.indexOf('    const walkNetworks ='));
  for(const interactive of [false,true]) {
    const writes=[];
    runInNewContext(block,{interactive,map:{getLayer:()=>true,setPaintProperty:(...args)=>writes.push(args)}});
    assert.equal(writes.find(([,p])=>p==="raster-opacity")[2],.16);
    assert.equal(writes.find(([,p])=>p==="raster-brightness-max")[2],.38);
  }
});
test("changing explorer control tabs preserves the running shared clock",()=>{
  const block=explorerSource.slice(explorerSource.indexOf('    const chooseTab ='),explorerSource.indexOf('    tabs.forEach((tab, index) =>'));
  const panels={orario:{hidden:false},mappa:{hidden:true}},selected={};
  const tabs=["orario","mappa"].map(id=>({id,setAttribute:(key,v)=>selected[id+key]=v,getAttribute:()=>id}));
  runInNewContext(block+'\nchooseTab(tabs[1]);chooseTab(tabs[0]);',{
    tabs,document:{getElementById:id=>panels[id]},
    window:{__analysisJourneyNodo8:{pauseExplorer(){throw new Error("Must not stop clock");}}},
  });
  assert.equal(panels.orario.hidden,false);assert.equal(panels.mappa.hidden,true);
  assert.doesNotMatch(block,/pauseExplorer|setInterval|requestAnimationFrame/);
});
test("proposal popup surface overrides injected dark styles with opaque accessible contrast",()=>{
  const css=readFileSync(new URL("../dietro-l-analisi/journey-usability.css",import.meta.url),"utf8");
  assert.match(css,/\.nodo8-map-popup \.maplibregl-popup-content\s*\{[^}]*background:\s*#f5f2e9\s*!important/);
  assert.match(css,/\.nodo8-popup-card h3\s*\{[^}]*color:\s*#153d34/);
  assert.match(css,/\.nodo8-popup-times td\s*\{[^}]*color:\s*#153d34/);
  assert.match(css,/\.nodo8-popup-card \.nodo8-stop-link\s*\{[^}]*min-height:\s*44px/);
  assert.match(css,/body\.is-map-exploring footer/);
  assert.match(css,/body\.is-map-exploring:has\(\.nodo8-map-popup\) #journeyExplorerControls/);
  const luminance=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255)
    .map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
    .reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
  const contrast=(a,b)=>(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
  assert.ok(contrast("#153d34","#f5f2e9")>=7);
  assert.ok(contrast("#4c6258","#f5f2e9")>=4.5);
  assert.match(explorerSource,/non riproduce|Non riproduce/);
  assert.match(explorerSource,/3 min 33 s/);
});
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
  assert.match(explorerSource, /fotografia storica, non l’orario più recente 2026\/27/);
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
test("disabling walking access hides both fills and outlines, including when no network is active",()=>{
  const code=explorerSource.slice(explorerSource.indexOf("      let previousKey = null;"),explorerSource.indexOf('      document.documentElement.dataset.activeWalkReady = "true"'));
  const writes=[],window={},document={documentElement:{dataset:{}}};
  const map={getSource:()=>({setData(){}}),setLayoutProperty:(...args)=>writes.push(args),setPaintProperty:(...args)=>writes.push(args)};
  runInNewContext(code,{window,document,map,model:{},activeWalkFeatureCollection:()=>({type:"FeatureCollection",features:[]})});
  for(const [visible,networks,shown] of [[true,["NODO8"],true],[false,["NODO8"],false],[true,[],false]]) {
    writes.length=0;
    window.__analysisJourneyActiveWalk.render({visible,networks});
    assert.deepEqual(writes,[
      ["explore-active-walk","visibility",shown?"visible":"none"],
      ["explore-active-walk","circle-opacity",shown?0.82:0],
      ["explore-active-walk","circle-stroke-opacity",shown?1:0],
    ]);
    assert.equal(document.documentElement.dataset.activeWalkVisible,String(shown));
  }
});
test("compact controls mirror the shared clock and cannot create a second simulation or narrow to one trip",()=>{
  const collapse=explorerSource.slice(explorerSource.indexOf('    controls.querySelector(\'[data-action="collapse"]\')'),explorerSource.indexOf('    controls.querySelectorAll(\'[data-layer="s8"]\')'));
  assert.match(collapse,/exploreControlsBody/);assert.match(collapse,/aria-expanded/);
  assert.doesNotMatch(collapse,/pauseExplorer|selectTrip|setInterval|requestAnimationFrame|layers\[/);
  assert.match(explorerSource,/\.n8-clock/);assert.match(explorerSource,/toggleExplorer\(\)/);
  const overlay=readFileSync(new URL("../dietro-l-analisi/journey-nodo8.mjs",import.meta.url),"utf8");
  assert.match(overlay,/updateClock\(state\)/);
  assert.match(overlay,/visibilityTarget: document\.getElementById\("map"\)/);
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
