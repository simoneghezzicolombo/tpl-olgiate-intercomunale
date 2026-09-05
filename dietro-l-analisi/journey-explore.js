(() => {
  'use strict';

  const map = window.__analysisJourneyMap;
  if (!map || !window.maplibregl) return;

  const ROUTE_COLORS = {
    D184: '#4ca5ff',
    D185: '#ff9b61',
    R2_23d58cd05658247380d7: '#57d7e8',
    R2_65db885119e69d50c7d4: '#55e1bf',
    R2_b2032eeb31cba06561f0: '#ff9b61',
    R2_2ffb6743b10bb3f0a97d: '#f6d36f'
  };
  const ROUTE_LABELS = {
    R2_23d58cd05658247380d7: '16 h · linea 1',
    R2_65db885119e69d50c7d4: '16 h · linea 2',
    R2_b2032eeb31cba06561f0: '18 h 30 · linea 1',
    R2_2ffb6743b10bb3f0a97d: '18 h 30 · linea 2'
  };
  const state = { proposals: true, current: false, stops: true };
  let popup = null;
  let enteredExplore = false;
  let lineage = null;

  function opacity(id, value) {
    if (!map.getLayer(id)) return;
    const type = map.getLayer(id).type;
    const prop = type === 'line' ? 'line-opacity' : type === 'circle' ? 'circle-opacity' : null;
    if (prop) map.setPaintProperty(id, prop, value);
  }

  function addLayer(layer) {
    if (!map.getLayer(layer.id)) map.addLayer(layer);
  }

  function toArray(value) {
    if (Array.isArray(value)) return value;
    if (typeof value !== 'string') return value == null ? [] : [String(value)];
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [value];
    } catch (_) {
      return value.includes(',') ? value.split(',').map(x => x.trim()).filter(Boolean) : [value];
    }
  }

  function esc(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function routeLabels(routes) {
    return toArray(routes).map(id => ROUTE_LABELS[id] || id);
  }

  function popupHtml({ eyebrow, title, body, meta = [], code = '' }) {
    return `<div class="map-card">
      <p class="map-card__eyebrow">${esc(eyebrow)}</p>
      <h3 class="map-card__title">${esc(title)}</h3>
      <p class="map-card__body">${body}</p>
      ${meta.length ? `<div class="map-card__meta">${meta.map(x => `<span>${esc(x)}</span>`).join('')}</div>` : ''}
      ${code ? `<div class="map-card__code">${esc(code)}</div>` : ''}
    </div>`;
  }

  function showPopup(lngLat, html) {
    if (popup) popup.remove();
    popup = new maplibregl.Popup({ closeButton: true, closeOnClick: false, maxWidth: '320px', offset: 10 })
      .setLngLat(lngLat)
      .setHTML(html)
      .addTo(map);
  }

  function stopNameFromAnchor(anchorId) {
    if (!anchorId?.startsWith('existing:')) return null;
    const cluster = anchorId.slice('existing:'.length);
    return lineage.stopData.features.find(f => f.properties.cluster_id === cluster)?.properties?.name || cluster;
  }

  function showAnchor(feature) {
    const p = feature.properties || {};
    const kind = p.kind;
    const coords = feature.geometry.coordinates;
    if (kind === 'PROPOSED_STOP') {
      showPopup(coords, popupHtml({
        eyebrow: 'Nuova fermata candidata',
        title: 'Fermata da verificare sul posto',
        body: 'Questo punto appartiene alla lineage certificata, ma non è una fermata esistente né una localizzazione già approvata. Resta <strong>FIELD CHECK PENDING</strong>.',
        meta: [p.budget || 'assetto finale', ...routeLabels(p.routes)],
        code: p.anchor_id
      }));
      return;
    }
    if (kind === 'RAIL_HUB') {
      showPopup(coords, popupHtml({
        eyebrow: 'Nodo ferroviario',
        title: p.label || 'Olgiate-Calco-Brivio FS',
        body: 'È il nodo di interscambio attorno al quale vengono valutati i quattro assetti finalisti.',
        meta: routeLabels(p.routes),
        code: p.anchor_id
      }));
      return;
    }
    showPopup(coords, popupHtml({
      eyebrow: 'Fermata esistente riutilizzata',
      title: stopNameFromAnchor(p.anchor_id) || p.label || 'Fermata esistente',
      body: 'La proposta passa da una fermata che esiste già nella baseline ufficiale.',
      meta: [p.budget || 'assetto finale', ...routeLabels(p.routes)],
      code: p.anchor_id
    }));
  }

  function showCurrentStop(feature) {
    const p = feature.properties || {};
    const routes = toArray(p.routes);
    showPopup(feature.geometry.coordinates, popupHtml({
      eyebrow: 'Fermata della rete attuale',
      title: p.name || p.cluster_id,
      body: 'Fermata ricostruita dal Current Service Baseline V4 a partire dal GTFS ufficiale congelato.',
      meta: routes,
      code: p.cluster_id
    }));
  }

  function showFinalRoutes(features, lngLat) {
    const unique = [];
    const seen = new Set();
    for (const f of features) {
      const id = f.properties?.route_id;
      if (!id || seen.has(id)) continue;
      seen.add(id);
      unique.push(f);
    }
    if (!unique.length) return;
    if (unique.length > 1) {
      showPopup(lngLat, popupHtml({
        eyebrow: 'Tratto condiviso',
        title: `${unique.length} linee finaliste si sovrappongono qui`,
        body: 'La sovrapposizione è geografica reale: non è stato applicato alcun offset grafico ai percorsi.',
        meta: unique.map(f => ROUTE_LABELS[f.properties.route_id] || f.properties.route_id)
      }));
      return;
    }
    const p = unique[0].properties;
    showPopup(lngLat, popupHtml({
      eyebrow: 'Linea finalista',
      title: ROUTE_LABELS[p.route_id] || p.route_id,
      body: 'Percorso instradato sul grafo Gate D con restrizioni di svolta e validato contro la Reduced Path Matrix V2.',
      meta: [`${Number(p.distance_km).toLocaleString('it-IT', { maximumFractionDigits: 2 })} km`, `${Number(p.runtime_min).toLocaleString('it-IT', { maximumFractionDigits: 1 })} min`],
      code: p.route_id
    }));
  }

  function showCurrentRoutes(features, lngLat) {
    const routes = [...new Set(features.map(f => f.properties?.route).filter(Boolean))];
    const first = features[0]?.properties || {};
    if (!routes.length) return;
    showPopup(lngLat, popupHtml({
      eyebrow: 'Rete attuale · GTFS ufficiale',
      title: routes.join(' + '),
      body: routes.length > 1
        ? 'In questo tratto più linee della baseline condividono la stessa geometria.'
        : 'La linea è mostrata usando le shape ufficiali congelate del servizio 2025-26, incluse le varianti presenti nel feed.',
      meta: routes,
      code: routes.length === 1 && first.shape_id ? `shape ${first.shape_id}` : ''
    }));
  }

  function buildLayers() {
    const finalColor = ['match', ['get', 'route_id'],
      'R2_23d58cd05658247380d7', ROUTE_COLORS.R2_23d58cd05658247380d7,
      'R2_65db885119e69d50c7d4', ROUTE_COLORS.R2_65db885119e69d50c7d4,
      'R2_b2032eeb31cba06561f0', ROUTE_COLORS.R2_b2032eeb31cba06561f0,
      'R2_2ffb6743b10bb3f0a97d', ROUTE_COLORS.R2_2ffb6743b10bb3f0a97d,
      '#ffffff'];
    const currentColor = ['match', ['get', 'route'], 'D184', ROUTE_COLORS.D184, 'D185', ROUTE_COLORS.D185, '#ffffff'];
    const hasD184 = ['>=', ['index-of', 'D184', ['get', 'routes']], 0];
    const hasD185 = ['>=', ['index-of', 'D185', ['get', 'routes']], 0];

    addLayer({ id: 'explore-current-glow', type: 'line', source: 'current-routes', paint: { 'line-color': currentColor, 'line-width': 10, 'line-blur': 8, 'line-opacity': 0 } });
    addLayer({ id: 'explore-current-routes', type: 'line', source: 'current-routes', paint: { 'line-color': currentColor, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2.1, 12, 3.1, 15, 4.2], 'line-opacity': 0, 'line-dasharray': [2, 1.4] } });
    addLayer({ id: 'explore-current-hit', type: 'line', source: 'current-routes', paint: { 'line-color': '#ffffff', 'line-width': 17, 'line-opacity': 0 } });

    addLayer({ id: 'explore-current-stops-halo', type: 'circle', source: 'current-gtfs-stops', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 4.2, 12, 6.2, 15, 8], 'circle-color': ['case', hasD184, ROUTE_COLORS.D184, hasD185, ROUTE_COLORS.D185, '#fff'], 'circle-opacity': 0 } });
    addLayer({ id: 'explore-current-stops', type: 'circle', source: 'current-gtfs-stops', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 2.4, 12, 3.8, 15, 5.2], 'circle-color': ['case', hasD185, ROUTE_COLORS.D185, hasD184, ROUTE_COLORS.D184, '#fff'], 'circle-opacity': 0, 'circle-stroke-width': 1.2, 'circle-stroke-color': '#07131f', 'circle-stroke-opacity': .75 } });

    addLayer({ id: 'explore-final-glow', type: 'line', source: 'final-routes-exact', paint: { 'line-color': finalColor, 'line-width': 13, 'line-blur': 9, 'line-opacity': 0 } });
    addLayer({ id: 'explore-final-routes', type: 'line', source: 'final-routes-exact', paint: { 'line-color': finalColor, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 3, 12, 4.6, 15, 6], 'line-opacity': 0 } });
    addLayer({ id: 'explore-final-hit', type: 'line', source: 'final-routes-exact', paint: { 'line-color': '#ffffff', 'line-width': 19, 'line-opacity': 0 } });
    addLayer({ id: 'explore-final-anchors', type: 'circle', source: 'final-anchors-exact', paint: {
      'circle-radius': ['case', ['==', ['get', 'kind'], 'RAIL_HUB'], 8, ['==', ['get', 'kind'], 'PROPOSED_STOP'], 6, 4.5],
      'circle-color': ['case', ['==', ['get', 'kind'], 'PROPOSED_STOP'], '#ffd36d', '#ffffff'],
      'circle-opacity': 0,
      'circle-stroke-width': ['case', ['==', ['get', 'kind'], 'PROPOSED_STOP'], 2, 1.4],
      'circle-stroke-color': ['case', ['==', ['get', 'kind'], 'PROPOSED_STOP'], '#6b551f', '#07131f'],
      'circle-stroke-opacity': 0
    } });
  }

  function addControls() {
    if (document.querySelector('.explore-controls')) return;
    const box = document.createElement('div');
    box.className = 'explore-controls';
    box.innerHTML = `
      <div class="explore-controls__head"><div><strong>Esplora la rete</strong><small>mappa libera · geometrie certificate</small></div></div>
      <div class="explore-controls__layers">
        <button type="button" data-layer="proposals" class="is-active"><i style="--c:#57d7e8"></i>Finaliste</button>
        <button type="button" data-layer="current"><i style="--c:#4ca5ff"></i>D184 / D185</button>
        <button type="button" data-layer="stops" class="is-active"><i style="--c:#ffd36d"></i>Fermate</button>
        <button type="button" data-action="reset">↺ vista</button>
      </div>
      <div class="explore-controls__hint">Trascina la mappa, usa la rotella o il pinch per zoomare, clicca su linee e fermate per leggere i dettagli.</div>`;
    document.body.appendChild(box);
    box.querySelectorAll('[data-layer]').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.layer;
        state[key] = !state[key];
        btn.classList.toggle('is-active', state[key]);
        render();
      });
    });
    box.querySelector('[data-action="reset"]').addEventListener('click', () => fitExplore(true));
  }

  function render() {
    const exploring = document.body.dataset.scene === 'explore';
    const currentOn = exploring && state.current;
    const finalOn = exploring && state.proposals;
    const currentStopsOn = currentOn && state.stops;
    const finalStopsOn = finalOn && state.stops;

    opacity('explore-current-glow', currentOn ? .12 : 0);
    opacity('explore-current-routes', currentOn ? .58 : 0);
    opacity('explore-current-hit', currentOn ? .001 : 0);
    opacity('explore-current-stops-halo', currentStopsOn ? .78 : 0);
    opacity('explore-current-stops', currentStopsOn ? .98 : 0);

    opacity('explore-final-glow', finalOn ? .22 : 0);
    opacity('explore-final-routes', finalOn ? .96 : 0);
    opacity('explore-final-hit', finalOn ? .001 : 0);
    opacity('explore-final-anchors', finalStopsOn ? .98 : 0);
    if (map.getLayer('explore-final-anchors')) map.setPaintProperty('explore-final-anchors', 'circle-stroke-opacity', finalStopsOn ? .9 : 0);

    if (!exploring && popup) {
      popup.remove();
      popup = null;
    }
  }

  function fitExplore(force = false) {
    if (!lineage || (!force && enteredExplore)) return;
    const b = new maplibregl.LngLatBounds();
    [...lineage.finalData.features, ...lineage.anchorData.features].forEach(f => {
      const coords = f.geometry.type === 'Point' ? [f.geometry.coordinates] : f.geometry.coordinates;
      coords.forEach(c => b.extend(c));
    });
    map.fitBounds(b, {
      padding: innerWidth < 800 ? { top: 95, right: 28, bottom: 185, left: 28 } : { top: 105, right: 430, bottom: 80, left: 70 },
      maxZoom: 12.6,
      duration: window.__analysisJourneyReduceMotion ? 0 : 900,
      pitch: 50,
      bearing: 3
    });
    enteredExplore = true;
  }

  function interactiveLayers() {
    return ['explore-final-anchors', 'explore-current-stops', 'explore-final-hit', 'explore-current-hit'].filter(id => map.getLayer(id));
  }

  function installEvents() {
    map.on('mousemove', e => {
      if (document.body.dataset.scene !== 'explore') return;
      const hits = map.queryRenderedFeatures(e.point, { layers: interactiveLayers() });
      map.getCanvas().style.cursor = hits.length ? 'pointer' : 'grab';
    });
    map.on('mouseleave', () => {
      if (document.body.dataset.scene === 'explore') map.getCanvas().style.cursor = 'grab';
    });
    map.on('click', e => {
      if (document.body.dataset.scene !== 'explore') return;
      const hits = map.queryRenderedFeatures(e.point, { layers: interactiveLayers() });
      if (!hits.length) {
        if (popup) popup.remove();
        popup = null;
        return;
      }
      const anchor = hits.find(f => f.layer.id === 'explore-final-anchors');
      if (anchor) return showAnchor(anchor);
      const currentStop = hits.find(f => f.layer.id === 'explore-current-stops');
      if (currentStop) return showCurrentStop(currentStop);
      const finals = hits.filter(f => f.layer.id === 'explore-final-hit');
      if (finals.length) return showFinalRoutes(finals, e.lngLat);
      const current = hits.filter(f => f.layer.id === 'explore-current-hit');
      if (current.length) return showCurrentRoutes(current, e.lngLat);
    });
  }

  function onScene() {
    const exploring = document.body.dataset.scene === 'explore';
    if (exploring) {
      render();
      requestAnimationFrame(() => fitExplore(false));
    } else {
      enteredExplore = false;
      render();
    }
  }

  function install() {
    lineage = window.__analysisJourneyLineage;
    if (!lineage?.installed || !lineage.exactRoutes) return false;
    if (!map.getSource('current-routes') || !map.getSource('current-gtfs-stops') || !map.getSource('final-routes-exact') || !map.getSource('final-anchors-exact')) return false;

    buildLayers();
    addControls();
    installEvents();
    new MutationObserver(onScene).observe(document.body, { attributes: true, attributeFilter: ['data-scene'] });
    onScene();

    window.__analysisJourneyExplore = {
      installed: true,
      state,
      render,
      fit: () => fitExplore(true),
      showAnchor: anchorId => {
        const f = lineage.anchorData.features.find(x => x.properties.anchor_id === anchorId);
        if (f) showAnchor(f);
        return !!f;
      },
      showCurrentStop: clusterId => {
        const f = lineage.stopData.features.find(x => x.properties.cluster_id === clusterId);
        if (f) showCurrentStop(f);
        return !!f;
      }
    };
    return true;
  }

  let attempts = 0;
  const timer = setInterval(() => {
    attempts += 1;
    if (install() || attempts > 240) clearInterval(timer);
  }, 50);
})();
