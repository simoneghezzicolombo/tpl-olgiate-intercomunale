(() => {
  'use strict';

  const maplibre = window.maplibregl;
  if (!maplibre || !maplibre.Map) return;

  // Replace the legacy CARTO raster endpoint before the single persistent map
  // is constructed. OSM is deliberately only contextual here: the analytical
  // layers remain pinned evidence. Browser CI intercepts these tile requests
  // with a local transparent tile, so automated QA does not consume OSM tiles.
  const CapturedMap = maplibre.Map;
  maplibre.Map = new Proxy(CapturedMap, {
    construct(Target, args) {
      const options = args[0] || {};
      const style = options.style;
      if (style && style.sources && style.sources.carto) {
        style.sources.carto.tiles = ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'];
        style.sources.carto.attribution = '© OpenStreetMap contributors';
        style.sources.carto.maxzoom = 19;
      }
      const rasterLayer = style && style.layers && style.layers.find(layer => layer.id === 'carto');
      if (rasterLayer && rasterLayer.paint) {
        rasterLayer.paint['raster-saturation'] = -1;
        rasterLayer.paint['raster-contrast'] = 0.18;
        rasterLayer.paint['raster-brightness-min'] = 0;
        rasterLayer.paint['raster-brightness-max'] = 0.24;
        rasterLayer.paint['raster-opacity'] = 0.24;
      }
      return Reflect.construct(Target, args);
    }
  });

  function safePaint(map, id, prop, value) {
    if (!map || !map.getLayer(id)) return;
    try { map.setPaintProperty(id, prop, value); } catch (_) {}
  }

  function applySceneHygiene() {
    const map = window.__analysisJourneyMap;
    if (!map) return;
    const scene = document.body.dataset.scene || 'intro';

    // MapLibre circle fill opacity does not suppress its stroke. Explicitly
    // gate strokes so analytical points cannot leak as ghost rings into later
    // chapters after their fill has been faded out by the main controller.
    safePaint(map, 'piece-halo', 'circle-stroke-opacity', scene === 'walk' ? 0.72 : 0);
    safePaint(map, 'existing-stops', 'circle-stroke-opacity',
      scene === 'walk' || scene === 'baseline' ? 0.9 : scene === 'candidates' ? 0.32 : 0);
    safePaint(map, 'candidates', 'circle-stroke-opacity',
      scene === 'candidates' ? 0.8 : scene === 'finalists' ? 0.08 : 0);
    safePaint(map, 'hub', 'circle-stroke-opacity', 1);

    // The dasymetric spark layer is intentionally transient during the
    // sections→buildings reveal. It must never persist into network chapters.
    if (scene !== 'buildings') safePaint(map, 'dasymetric-sparks', 'circle-opacity', 0);
  }

  const observer = new MutationObserver(applySceneHygiene);
  observer.observe(document.body, {attributes:true, attributeFilter:['data-scene']});

  const timer = setInterval(() => {
    const map = window.__analysisJourneyMap;
    if (!map) return;
    applySceneHygiene();
    if (map.getLayer('dasymetric-sparks')) clearInterval(timer);
  }, 120);
  setTimeout(() => clearInterval(timer), 120000);
})();
