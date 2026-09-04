(() => {
  const GEO = window.TRA_PAESI_GEO;
  const DATA = window.TRA_PAESI_DATA;
  if (!GEO || !DATA) return;

  const COLORS = { r1: "#155e56", r2: "#d65b35", d184: "#68756e", d185: "#9a8060", halo: "#fffefa" };
  const routeCache = new Map();
  let map;
  let layerProposed;
  let layerCurrent;
  let layerMarkers;
  let activePackage = new URLSearchParams(location.search).get("pkg") || "16";
  if (!GEO.proposedPackages[activePackage]) activePackage = "16";
  let activeTopology = new URLSearchParams(location.search).get("topology") || "loops";
  if (!["loops", "fig"].includes(activeTopology)) activeTopology = "loops";
  let mapMode = new URLSearchParams(location.search).get("map") || "overlay";
  if (!["proposal", "overlay", "current"].includes(mapMode)) mapMode = "overlay";
  let currentEnabled = { D184: true, D185: true };
  let renderGeneration = 0;
  let selectedRouteKey = null;
  const routeLayers = new Map();
  const markerLayers = new Map();

  function injectSection() {
    if (document.querySelector("#mappa")) return;
    const section = document.createElement("section");
    section.className = "section section-map";
    section.id = "mappa";
    section.dataset.section = "mappa";
    section.innerHTML = `
      <div class="map-intro reveal revealed">
        <div>
          <p class="eyebrow">03 · Il territorio</p>
          <h2>La rete, <em>sulla mappa.</em></h2>
        </div>
        <div class="map-intro-copy">
          <p><strong>Qui il confronto diventa geografico.</strong> La rete ordinaria D184/D185 resta sullo sfondo; sopra puoi accendere il pacchetto finalistico e cliccare tracciati e fermate. L'ordine delle fermate è certificato. Il percorso sulle strade è una ricostruzione visuale, non un allineamento ufficiale.</p>
        </div>
      </div>
      <div class="map-workbench reveal revealed">
        <div class="map-toolbar">
          <div class="map-toolbar-title"><i></i><div><strong>Route Explorer</strong><span id="mapToolbarStatus">rete proposta + rete attuale</span></div></div>
          <div class="map-segment" aria-label="Vista geografica">
            <button type="button" data-map-mode="proposal">Proposta</button>
            <button type="button" data-map-mode="overlay">Sovrapposta</button>
            <button type="button" data-map-mode="current">Attuale</button>
          </div>
          <div class="map-segment" aria-label="Pacchetto finalistico">
            <button type="button" data-map-package="16">16h</button>
            <button type="button" data-map-package="18.5">18h30</button>
          </div>
          <div class="map-segment" aria-label="Semantica operativa">
            <button type="button" data-map-topology="loops">Due anelli</button>
            <button type="button" data-map-topology="fig">Figure-8</button>
          </div>
          <button class="map-tool-button" id="mapFit" type="button">Inquadra rete</button>
        </div>
        <div class="map-stage">
          <div class="map-canvas-shell">
            <div id="geoMap" class="tp-map" aria-label="Mappa interattiva della rete attuale e delle proposte"></div>
            <div class="map-legend" aria-label="Legenda mappa">
              <div class="map-legend-row"><i class="map-legend-line r1"></i>Ramo proposto 1</div>
              <div class="map-legend-row"><i class="map-legend-line r2"></i>Ramo proposto 2</div>
              <div class="map-legend-row"><i class="map-legend-line old"></i>D184 / D185 attuali</div>
              <div class="map-legend-row"><i class="map-legend-dot hub"></i>Nodo ferroviario</div>
              <div class="map-legend-row"><i class="map-legend-dot"></i>Fermata esistente</div>
              <div class="map-legend-row"><i class="map-legend-dot new"></i>Fermata candidata</div>
            </div>
            <div class="map-status" id="mapRoutingStatus"><i></i><span>routing stradale in caricamento</span></div>
            <div class="map-route-rail" id="mapRouteRail"></div>
            <div class="map-layer-tools" id="mapLayerTools">
              <button type="button" data-current-route="D184">D184</button>
              <button type="button" data-current-route="D185">D185</button>
            </div>
          </div>
          <aside class="map-side" id="mapSide" aria-live="polite"></aside>
        </div>
      </div>`;
    const rete = document.querySelector("#rete");
    const compare = document.querySelector("#confronta");
    if (rete && rete.parentNode) rete.parentNode.insertBefore(section, compare || rete.nextSibling);

    const nav = document.querySelector(".topnav");
    if (nav && !nav.querySelector('a[href="#mappa"]')) {
      const link = document.createElement("a");
      link.href = "#mappa";
      link.textContent = "Mappa";
      const compareLink = nav.querySelector('a[href="#confronta"]');
      nav.insertBefore(link, compareLink || null);
    }
  }

  function loadCss(href) {
    return new Promise(resolve => {
      if ([...document.styleSheets].some(s => s.href === href)) return resolve();
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      link.onload = resolve;
      link.onerror = resolve;
      document.head.appendChild(link);
    });
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      if (window.L) return resolve();
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  function allAnchor(id) {
    if (id === GEO.hub.id) return GEO.hub;
    return GEO.proposedStops[id];
  }

  function pathPointsFromAnchors(ids) {
    return ids.map(allAnchor).filter(Boolean);
  }

  function currentPatternPoints(pattern) {
    return pattern.stopIds.map(id => ({ id, ...GEO.currentStops[id], kind: "current" })).filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon));
  }

  function setRoutingStatus(kind, text) {
    const el = document.querySelector("#mapRoutingStatus");
    if (!el) return;
    el.className = `map-status ${kind || ""}`.trim();
    el.querySelector("span").textContent = text;
  }

  async function roadPath(points, cacheKey) {
    if (routeCache.has(cacheKey)) return routeCache.get(cacheKey);
    const fallback = points.map(p => [p.lat, p.lon]);
    const coords = points.map(p => `${p.lon},${p.lat}`).join(";");
    const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson&steps=false`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 9000);
    try {
      const response = await fetch(url, { signal: controller.signal, mode: "cors" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const json = await response.json();
      const coordinates = json?.routes?.[0]?.geometry?.coordinates;
      if (!coordinates?.length) throw new Error("No geometry");
      const path = { points: coordinates.map(([lon, lat]) => [lat, lon]), routed: true };
      routeCache.set(cacheKey, path);
      return path;
    } catch {
      const path = { points: fallback, routed: false };
      routeCache.set(cacheKey, path);
      return path;
    } finally {
      clearTimeout(timer);
    }
  }

  function divIcon(kind) {
    return L.divIcon({ className: "tp-marker-wrap", html: `<span class="tp-marker ${kind}"></span>`, iconSize: kind === "hub" ? [18,18] : kind === "current" ? [8,8] : [14,14], iconAnchor: kind === "hub" ? [9,9] : kind === "current" ? [4,4] : [7,7] });
  }

  function popupHtml(stop, context = "") {
    const detail = stop.kind === "proposed" ? "fermata candidata" : stop.kind === "hub" ? "nodo ferroviario" : stop.kind === "current" ? "fermata rete attuale" : "fermata esistente";
    return `<strong>${stop.name}</strong><span>${detail}${stop.municipality ? ` · ${stop.municipality}` : ""}${context ? ` · ${context}` : ""}</span>`;
  }

  function addStopMarker(stop, context = "", key = stop.id) {
    const markerKey = `${key}:${context}`;
    if (markerLayers.has(markerKey)) return markerLayers.get(markerKey);
    const marker = L.marker([stop.lat, stop.lon], { icon: divIcon(stop.kind || "existing"), keyboard: true, riseOnHover: true });
    marker.bindPopup(popupHtml(stop, context), { className: "tp-popup", closeButton: false, offset: [0,-3] });
    marker.on("click", () => showStopDetail(stop, context));
    marker.addTo(layerMarkers);
    markerLayers.set(markerKey, marker);
    return marker;
  }

  function syncMapUrl() {
    const url = new URL(location.href);
    url.searchParams.set("map", mapMode);
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function mapModeLabel() {
    return mapMode === "proposal" ? "solo proposta" : mapMode === "current" ? "solo rete attuale" : "rete proposta + rete attuale";
  }

  function topologyLabel() {
    return activeTopology === "fig" ? "Figure-8 interlineato" : "Due anelli indipendenti";
  }

  function showOverview() {
    const pkg = DATA.packages[activePackage];
    const side = document.querySelector("#mapSide");
    side.innerHTML = `
      <p class="map-detail-kicker">Vista geografica</p>
      <h3 class="map-detail-title">${pkg.spanLabel} · ${topologyLabel()}</h3>
      <p class="map-detail-sub">Clicca un tracciato o una fermata. La topologia non cambia la geografia passenger-facing a parità di pacchetto: la mappa mostra quindi i due rami pubblici certificati del pacchetto selezionato.</p>
      <div class="map-detail-meta">
        <div><span>finestra</span><b>${pkg.spanStart}–${pkg.spanEnd}</b></div>
        <div><span>corse</span><b>${pkg.exactTrips}</b></div>
        <div><span>km / anno</span><b>${new Intl.NumberFormat("it-IT",{maximumFractionDigits:0}).format(pkg.annualKm)}</b></div>
        <div><span>technical closure</span><b>0′</b></div>
      </div>
      <div class="map-contract"><strong>Contratto cartografico.</strong> Fermate e ordine derivano dagli output certificati. Le linee sulle strade sono ricostruite via routing a partire da quei punti e servono a leggere il territorio, non costituiscono un tracciato ufficiale definitivo.</div>`;
  }

  function showRouteDetail(route) {
    const points = pathPointsFromAnchors(route.anchors);
    const side = document.querySelector("#mapSide");
    side.innerHTML = `
      <p class="map-detail-kicker">Ramo proposto ${route.ordinal}</p>
      <h3 class="map-detail-title">${route.label}</h3>
      <p class="map-detail-sub">Percorso pubblico del pacchetto ${DATA.packages[activePackage].spanLabel}. Clicca una fermata nella sequenza per localizzarla sulla mappa.</p>
      <div class="map-detail-meta">
        <div><span>partenza</span><b>ogni ora a :${String(route.phase).padStart(2,"0")}</b></div>
        <div><span>giro pubblico</span><b>${route.runtime.toLocaleString("it-IT",{maximumFractionDigits:1})}′</b></div>
        <div><span>prima</span><b>${route.first}</b></div>
        <div><span>ultima</span><b>${route.last}</b></div>
      </div>
      <div class="map-stop-list">
        ${points.map(stop => `<button class="map-stop-button ${stop.kind}" type="button" data-map-stop="${stop.id}"><strong>${stop.name}</strong><small>${stop.kind === "proposed" ? "candidata" : stop.kind === "hub" ? "nodo ferroviario" : stop.municipality || "esistente"}</small></button>`).join("")}
      </div>
      <div class="map-contract"><strong>Geometria visuale.</strong> La linea stradale è calcolata dalla sequenza certificata degli anchor. Nessun segmento viene presentato come allineamento ufficiale.</div>`;
    side.querySelectorAll("[data-map-stop]").forEach(btn => btn.addEventListener("click", () => {
      const stop = allAnchor(btn.dataset.mapStop);
      if (!stop) return;
      map.flyTo([stop.lat, stop.lon], Math.max(map.getZoom(), 15), { duration: .55 });
      const marker = [...markerLayers.values()].find(m => Math.abs(m.getLatLng().lat-stop.lat)<1e-7 && Math.abs(m.getLatLng().lng-stop.lon)<1e-7);
      if (marker) marker.openPopup();
    }));
  }

  function showCurrentDetail(pattern) {
    const points = currentPatternPoints(pattern);
    const side = document.querySelector("#mapSide");
    side.innerHTML = `
      <p class="map-detail-kicker">Rete attuale · ${pattern.route}</p>
      <h3 class="map-detail-title">${pattern.direction}</h3>
      <p class="map-detail-sub">Pattern ordinario rappresentativo congelato dal GTFS ufficiale 2025–2026. Per D185 la perturbazione temporanea del ponte di Brivio è esclusa dalla baseline strutturale.</p>
      <div class="map-detail-meta"><div><span>linea</span><b>${pattern.route}</b></div><div><span>occorrenze GTFS</span><b>${pattern.tripCount}</b></div><div><span>fermate pattern</span><b>${points.length}</b></div><div><span>ruolo</span><b>baseline</b></div></div>
      <div class="map-stop-list">${points.map(stop => `<button class="map-stop-button" type="button" data-current-stop="${stop.id}"><strong>${stop.name}</strong><small>${stop.id}</small></button>`).join("")}</div>
      <div class="map-contract"><strong>Rete attuale.</strong> Sequenza fermate dal GTFS congelato. Anche qui il road-following è una ricostruzione cartografica della sequenza, non una shape GTFS ufficiale.</div>`;
    side.querySelectorAll("[data-current-stop]").forEach(btn => btn.addEventListener("click", () => {
      const stop = GEO.currentStops[btn.dataset.currentStop];
      if (stop) map.flyTo([stop.lat, stop.lon], Math.max(map.getZoom(), 15), { duration: .55 });
    }));
  }

  function showStopDetail(stop, context = "") {
    const side = document.querySelector("#mapSide");
    const pkgRoutes = GEO.proposedPackages[activePackage].filter(r => r.anchors.includes(stop.id));
    side.innerHTML = `
      <p class="map-detail-kicker">${stop.kind === "proposed" ? "Fermata candidata" : stop.kind === "hub" ? "Nodo ferroviario" : stop.kind === "current" ? "Fermata attuale" : "Fermata esistente"}</p>
      <h3 class="map-detail-title">${stop.name}</h3>
      <p class="map-detail-sub">${stop.municipality || context || "Rete attuale"}</p>
      <div class="map-detail-meta">
        <div><span>lat</span><b>${stop.lat.toFixed(5)}</b></div><div><span>lon</span><b>${stop.lon.toFixed(5)}</b></div>
        <div><span>stato</span><b>${stop.kind === "proposed" ? "candidata" : stop.kind === "hub" ? "hub S8" : "esistente"}</b></div>
        <div><span>rami ${DATA.packages[activePackage].spanLabel}</span><b>${pkgRoutes.length ? pkgRoutes.map(r => `R${r.ordinal}`).join(" + ") : "—"}</b></div>
      </div>
      <div class="map-contract"><strong>Provenienza.</strong> ${stop.source || "GTFS congelato della baseline attuale"}.</div>`;
  }

  function styleRouteSelection(key) {
    selectedRouteKey = key;
    routeLayers.forEach((entry, routeKey) => {
      const selected = routeKey === key;
      entry.main.setStyle({ weight: selected ? 7 : entry.proposed ? 4.5 : 2.5, opacity: selected ? 1 : entry.proposed ? .82 : .48 });
      if (entry.halo) entry.halo.setStyle({ weight: selected ? 11 : 8, opacity: selected ? .86 : .6 });
    });
    document.querySelectorAll(".map-route-chip").forEach(el => el.classList.toggle("active", el.dataset.routeKey === key));
  }

  async function addProposedRoute(route, generation) {
    const points = pathPointsFromAnchors(route.anchors);
    const routed = await roadPath(points, `proposed:${activePackage}:${route.id}`);
    if (generation !== renderGeneration) return routed.routed;
    const color = route.ordinal === 1 ? COLORS.r1 : COLORS.r2;
    const halo = L.polyline(routed.points, { color: COLORS.halo, weight: 8, opacity: .62, lineJoin: "round", lineCap: "round", interactive: false }).addTo(layerProposed);
    const main = L.polyline(routed.points, { color, weight: 4.5, opacity: .92, lineJoin: "round", lineCap: "round" }).addTo(layerProposed);
    const key = `proposal:${route.id}`;
    main.on("click", () => { styleRouteSelection(key); showRouteDetail(route); });
    main.on("mouseover", () => main.setStyle({ weight: selectedRouteKey === key ? 7 : 6 }));
    main.on("mouseout", () => main.setStyle({ weight: selectedRouteKey === key ? 7 : 4.5 }));
    routeLayers.set(key, { main, halo, proposed: true, route });
    points.forEach(stop => addStopMarker(stop, `Ramo ${route.ordinal}`, stop.id));
    return routed.routed;
  }

  async function addCurrentPattern(pattern, generation) {
    if (!currentEnabled[pattern.route]) return true;
    const points = currentPatternPoints(pattern);
    const routed = await roadPath(points, `current:${pattern.id}`);
    if (generation !== renderGeneration) return routed.routed;
    const color = pattern.route === "D184" ? COLORS.d184 : COLORS.d185;
    const main = L.polyline(routed.points, { color, weight: 2.5, opacity: .48, dashArray: "7 7", lineJoin: "round", lineCap: "round" }).addTo(layerCurrent);
    const key = `current:${pattern.id}`;
    main.on("click", () => { styleRouteSelection(key); showCurrentDetail(pattern); });
    main.on("mouseover", () => main.setStyle({ weight: 4, opacity: .82 }));
    main.on("mouseout", () => main.setStyle({ weight: selectedRouteKey === key ? 7 : 2.5, opacity: selectedRouteKey === key ? 1 : .48 }));
    routeLayers.set(key, { main, halo: null, proposed: false, pattern });
    points.forEach(stop => addStopMarker(stop, pattern.route, `${pattern.route}:${stop.id}`));
    return routed.routed;
  }

  function routeRail() {
    const rail = document.querySelector("#mapRouteRail");
    if (mapMode === "current") {
      rail.innerHTML = ["D184","D185"].map(route => `<button class="map-route-chip" type="button" data-current-focus="${route}"><span>Rete attuale</span><strong>${route}</strong><small>pattern ordinari GTFS · clicca per esplorare</small></button>`).join("");
      rail.querySelectorAll("[data-current-focus]").forEach(btn => btn.addEventListener("click", () => {
        const pattern = GEO.currentPatterns.find(p => p.route === btn.dataset.currentFocus);
        const key = pattern ? `current:${pattern.id}` : null;
        if (key && routeLayers.has(key)) { styleRouteSelection(key); showCurrentDetail(pattern); fitLayer(routeLayers.get(key).main); }
      }));
      return;
    }
    const routes = GEO.proposedPackages[activePackage];
    rail.innerHTML = routes.map(route => `<button class="map-route-chip r${route.ordinal}" type="button" data-route-key="proposal:${route.id}"><span>Ramo ${route.ordinal}</span><strong>${route.label.replace(/^Ramo \d · /,"")}</strong><small>:${String(route.phase).padStart(2,"0")} ogni ora · ${route.runtime.toLocaleString("it-IT",{maximumFractionDigits:1})}′</small></button>`).join("");
    rail.querySelectorAll("[data-route-key]").forEach(btn => btn.addEventListener("click", () => {
      const key = btn.dataset.routeKey;
      const entry = routeLayers.get(key);
      if (!entry) return;
      styleRouteSelection(key);
      showRouteDetail(entry.route);
      fitLayer(entry.main);
    }));
  }

  function updateControlState() {
    document.querySelectorAll("[data-map-mode]").forEach(btn => btn.classList.toggle("active", btn.dataset.mapMode === mapMode));
    document.querySelectorAll("[data-map-package]").forEach(btn => btn.classList.toggle("active", btn.dataset.mapPackage === activePackage));
    document.querySelectorAll("[data-map-topology]").forEach(btn => btn.classList.toggle("active", btn.dataset.mapTopology === activeTopology));
    document.querySelectorAll("[data-current-route]").forEach(btn => btn.classList.toggle("active", currentEnabled[btn.dataset.currentRoute]));
    const status = document.querySelector("#mapToolbarStatus");
    if (status) status.textContent = `${mapModeLabel()} · ${DATA.packages[activePackage].spanLabel} · ${topologyLabel()}`;
  }

  async function renderMapLayers({ fit = false } = {}) {
    const generation = ++renderGeneration;
    selectedRouteKey = null;
    routeLayers.clear();
    markerLayers.clear();
    layerProposed.clearLayers();
    layerCurrent.clearLayers();
    layerMarkers.clearLayers();
    showOverview();
    updateControlState();
    setRoutingStatus("", "routing stradale in caricamento");

    const tasks = [];
    if (mapMode !== "current") GEO.proposedPackages[activePackage].forEach(route => tasks.push(addProposedRoute(route, generation)));
    if (mapMode !== "proposal") GEO.currentPatterns.forEach(pattern => tasks.push(addCurrentPattern(pattern, generation)));
    const results = await Promise.all(tasks);
    if (generation !== renderGeneration) return;
    const fallbackCount = results.filter(x => !x).length;
    if (fallbackCount) setRoutingStatus("fallback", `${fallbackCount} tracciat${fallbackCount === 1 ? "o" : "i"} in fallback anchor`);
    else setRoutingStatus("", "routing stradale ricostruito");
    routeRail();
    if (fit) fitVisible();
  }

  function fitLayer(layer) {
    const bounds = layer.getBounds?.();
    if (bounds?.isValid()) map.fitBounds(bounds.pad(.18), { animate: true, duration: .55, maxZoom: 15 });
  }

  function fitVisible() {
    const bounds = L.latLngBounds([]);
    [layerProposed, layerCurrent].forEach(group => group.eachLayer(layer => { if (layer.getBounds) bounds.extend(layer.getBounds()); else if (layer.getLatLng) bounds.extend(layer.getLatLng()); }));
    if (bounds.isValid()) map.fitBounds(bounds.pad(.08), { animate: true, duration: .6, maxZoom: 14 });
    else map.fitBounds(GEO.initialBounds);
  }

  function bindControls() {
    document.querySelectorAll("[data-map-mode]").forEach(btn => btn.addEventListener("click", () => {
      mapMode = btn.dataset.mapMode;
      syncMapUrl();
      renderMapLayers({ fit: true });
    }));
    document.querySelectorAll("[data-map-package]").forEach(btn => btn.addEventListener("click", () => {
      activePackage = btn.dataset.mapPackage;
      const external = document.querySelector(`[data-network-package="${activePackage}"]`);
      if (external) external.click();
      renderMapLayers({ fit: true });
    }));
    document.querySelectorAll("[data-map-topology]").forEach(btn => btn.addEventListener("click", () => {
      activeTopology = btn.dataset.mapTopology;
      const external = document.querySelector(`[data-network-topology="${activeTopology}"]`);
      if (external) external.click();
      updateControlState();
      showOverview();
    }));
    document.querySelectorAll("[data-current-route]").forEach(btn => btn.addEventListener("click", () => {
      const route = btn.dataset.currentRoute;
      currentEnabled[route] = !currentEnabled[route];
      renderMapLayers();
    }));
    document.querySelector("#mapFit")?.addEventListener("click", fitVisible);

    document.querySelectorAll("[data-network-package],[data-span]").forEach(btn => btn.addEventListener("click", () => setTimeout(() => {
      const pkg = new URLSearchParams(location.search).get("pkg");
      if (pkg && GEO.proposedPackages[pkg] && pkg !== activePackage) { activePackage = pkg; renderMapLayers(); }
    }, 0)));
    document.querySelectorAll("[data-network-topology]").forEach(btn => btn.addEventListener("click", () => setTimeout(() => {
      const topology = new URLSearchParams(location.search).get("topology");
      if (["loops","fig"].includes(topology)) { activeTopology = topology; updateControlState(); showOverview(); }
    }, 0)));
  }

  async function boot() {
    injectSection();
    await loadCss("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
    try {
      await loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
    } catch {
      const canvas = document.querySelector("#geoMap");
      if (canvas) canvas.innerHTML = '<div class="map-side-empty"><div><strong>Mappa non caricata</strong>La libreria cartografica esterna non è raggiungibile. Il resto del sito resta disponibile.</div></div>';
      return;
    }

    map = L.map("geoMap", { zoomControl: true, preferCanvas: true, scrollWheelZoom: true, zoomSnap: .5 }).fitBounds(GEO.initialBounds);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", { maxZoom: 20, subdomains: "abcd", attribution: '&copy; OpenStreetMap contributors &copy; CARTO' }).addTo(map);
    layerCurrent = L.layerGroup().addTo(map);
    layerProposed = L.layerGroup().addTo(map);
    layerMarkers = L.layerGroup().addTo(map);
    bindControls();
    await renderMapLayers({ fit: true });
    setTimeout(() => map.invalidateSize(), 50);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once:true });
  else boot();
})();
