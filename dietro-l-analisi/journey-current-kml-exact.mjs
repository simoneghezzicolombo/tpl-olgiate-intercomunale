const map = window.__analysisJourneyMap;

if (!map || !window.pako) {
  throw new Error('Exact current-service KML loader requires the map and pako.');
}

const FILES = [
  'current-routes-kml-exact.geojson.gz.b64.0',
  'current-routes-kml-exact.geojson.gz.b64.1'
];

async function waitForLineage(timeoutMs = 30000) {
  const started = performance.now();
  while (performance.now() - started < timeoutMs) {
    const lineage = window.__analysisJourneyLineage;
    if (lineage?.installed && map.getSource('current-routes')) return lineage;
    await new Promise(resolve => setTimeout(resolve, 25));
  }
  throw new Error('Timed out waiting for current-route lineage before KML override.');
}

async function loadGeoJson(names) {
  const parts = await Promise.all(names.map(async name => {
    const response = await fetch(name);
    if (!response.ok) throw new Error(`${name} ${response.status}`);
    return (await response.text()).trim();
  }));
  const encoded = parts.join('');
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return JSON.parse(window.pako.inflate(bytes, { to: 'string' }));
}

const [lineage, currentData] = await Promise.all([
  waitForLineage(),
  loadGeoJson(FILES)
]);

const d184 = currentData.features.filter(f => f.properties?.route === 'D184');
const d185 = currentData.features.filter(f => f.properties?.route === 'D185');
const coordCount = features => features.reduce((sum, f) => sum + (f.geometry?.coordinates?.length || 0), 0);

if (currentData.features.length !== 18 || d184.length !== 7 || d185.length !== 11) {
  throw new Error(`Unexpected KML route variants: total=${currentData.features.length} D184=${d184.length} D185=${d185.length}`);
}
if (coordCount(d184) !== 2268 || coordCount(d185) !== 3618) {
  throw new Error(`Unexpected KML coordinate counts: D184=${coordCount(d184)} D185=${coordCount(d185)}`);
}
if (!currentData.features.every(f => f.geometry?.type === 'LineString' && f.properties?.source === 'OFFICIAL_AGENCY_KML_USER_SUPPLIED')) {
  throw new Error('Current route asset is not the exact supplied-KML contract.');
}

const source = map.getSource('current-routes');
if (!source) throw new Error('current-routes source missing');
source.setData(currentData);

lineage.currentData = currentData;
lineage.currentSource = 'USER_SUPPLIED_AGENCY_KML_LINESTRINGS_EXACT';
lineage.currentGeometryContract = 'CURRENT_SERVICE_KML_GEOMETRY_V1';
lineage.currentRouteGraphReconstruction = false;

function exactBounds() {
  const bounds = new maplibregl.LngLatBounds();
  currentData.features.forEach(feature => feature.geometry.coordinates.forEach(coord => bounds.extend(coord)));
  return bounds;
}

function applyExactBaselineView() {
  if (document.body.dataset.scene !== 'baseline') return;
  map.fitBounds(exactBounds(), {
    padding: innerWidth < 800 ? 35 : 70,
    maxZoom: 12,
    duration: window.__analysisJourneyReduceMotion ? 0 : 850,
    pitch: 40,
    bearing: -8
  });
}

new MutationObserver(applyExactBaselineView).observe(document.body, {
  attributes: true,
  attributeFilter: ['data-scene']
});
applyExactBaselineView();

window.__analysisJourneyCurrentKmlExact = {
  installed: true,
  contract: 'CURRENT_SERVICE_KML_GEOMETRY_V1',
  currentData,
  variants: { D184: d184.length, D185: d185.length },
  coordinateCounts: { D184: coordCount(d184), D185: coordCount(d185) },
  graphReconstruction: false
};
