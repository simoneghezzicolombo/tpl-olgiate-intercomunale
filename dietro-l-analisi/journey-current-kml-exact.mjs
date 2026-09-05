const map = window.__analysisJourneyMap;
const lineage = window.__analysisJourneyLineage;

if (!map || !lineage || !window.pako) {
  throw new Error('Exact current-service KML override cannot start before lineage/map/pako.');
}

const FILES = [
  'current-routes-kml-exact.geojson.gz.b64.0',
  'current-routes-kml-exact.geojson.gz.b64.1'
];

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

const currentData = await loadGeoJson(FILES);
const d184 = currentData.features.filter(f => f.properties?.route === 'D184');
const d185 = currentData.features.filter(f => f.properties?.route === 'D185');
const coordCount = features => features.reduce((sum, f) => sum + (f.geometry?.coordinates?.length || 0), 0);

if (currentData.features.length !== 18 || d184.length !== 7 || d185.length !== 11) {
  throw new Error(`Unexpected KML route variants: total=${currentData.features.length} D184=${d184.length} D185=${d185.length}`);
}
if (coordCount(d184) !== 2268 || coordCount(d185) !== 3618) {
  throw new Error(`Unexpected KML coordinate counts: D184=${coordCount(d184)} D185=${coordCount(d185)}`);
}

const source = map.getSource('current-routes');
if (!source) throw new Error('current-routes source missing');
source.setData(currentData);

lineage.currentData = currentData;
lineage.currentSource = 'USER_SUPPLIED_OFFICIAL_AGENCY_KML_EXACT';
lineage.currentGeometryContract = 'CURRENT_SERVICE_KML_GEOMETRY_V1';
lineage.apply?.();

window.__analysisJourneyCurrentKmlExact = {
  installed: true,
  contract: 'CURRENT_SERVICE_KML_GEOMETRY_V1',
  currentData,
  variants: { D184: d184.length, D185: d185.length },
  coordinateCounts: { D184: coordCount(d184), D185: coordCount(d185) },
  graphReconstruction: false
};
