(() => {
  "use strict";

  const map = window.__analysisJourneyMap;
  const J = window.ANALYSIS_JOURNEY_DATA;
  if (!map || !window.maplibregl) return;

  const COLORS = {
    D184: "#4ca5ff",
    D185: "#ff9b61",
    R2_23d58cd05658247380d7: "#57d7e8",
    R2_65db885119e69d50c7d4: "#55e1bf",
    R2_b2032eeb31cba06561f0: "#ff9b61",
    R2_2ffb6743b10bb3f0a97d: "#f6d36f",
  };
  const LABELS = {
    R2_23d58cd05658247380d7: "16 h · linea 1",
    R2_65db885119e69d50c7d4: "16 h · linea 2",
    R2_b2032eeb31cba06561f0: "18 h 30 · linea 1",
    R2_2ffb6743b10bb3f0a97d: "18 h 30 · linea 2",
  };
  const compatibilityState = { proposals: false, current: false, stops: true };
  const layers = {
    worldpop: false,
    sections: false,
    buildings: false,
    walk: false,
    roads: false,
    candidates: false,
    current: false,
    d184: false,
    d185: false,
    proposals: false,
    nodo8: true,
    stops: true,
    s8: false,
  };
  let lineage = null;
  let popup = null;
  let active = false;
  let fitted = false;
  let roadPromise = null;
  let controls = null;
  let walkPromise = null;

  // The hidden selection is a compatibility bridge to the shared dated player.
  // Visible network switches are independent and never select a different day.
  function syncCurrentSelection() {
    layers.current = layers.d184 || layers.d185;
    compatibilityState.current = layers.current;
    const choice = controls?.querySelector("#currentRouteChoice");
    if (choice) choice.value = layers.d184 && layers.d185 ? "ALL" : layers.d184 ? "D184" : layers.d185 ? "D185" : "ALL";
  }

  async function ensureActiveWalk() {
    if (window.__analysisJourneyActiveWalk) return;
    if (walkPromise) return walkPromise;
    walkPromise = (async () => {
      const { validateActiveWalkAsset, activeWalkFeatureCollection } = await import("../nodo8-active-walk.mjs?v=20261009b");
      const response = await fetch("../assets/nodo8-active-walk.json?v=20261009b");
      if (!response.ok) throw new Error("Active-network walk data unavailable");
      const model = validateActiveWalkAsset(await response.json());
      map.addSource("explore-active-walk", {type:"geojson",data:{type:"FeatureCollection",features:[]}});
      map.addLayer({id:"explore-active-walk",type:"circle",source:"explore-active-walk",paint:{
        "circle-radius":["interpolate",["linear"],["zoom"],10,2,14,4],
        "circle-color":["match",["get","walk_band"],"5","#55e1bf","8","#99d5aa","10","#e7d69a","over10","#e99b71","#8a9494"],
        "circle-opacity":0,"circle-stroke-width":0.4,"circle-stroke-color":"#102e27"
      }}, "hub-glow");
      let previousKey = null;
      window.__analysisJourneyActiveWalk = {render({visible,networks}) {
        const key = networks.join("|");
        if (key !== previousKey) {
          const features = activeWalkFeatureCollection(model, networks);
          map.getSource("explore-active-walk").setData(features);
          document.documentElement.dataset.activeWalkPointCount = String(features.features.length);
          previousKey = key;
        }
        map.setPaintProperty("explore-active-walk","circle-opacity",visible && networks.length ? 0.82 : 0);
        document.documentElement.dataset.activeWalkNetworks = key;
        document.documentElement.dataset.activeWalkVisible = String(visible && networks.length > 0);
      }};
      document.documentElement.dataset.activeWalkReady = "true";
    })().finally(() => {walkPromise = null;});
    return walkPromise;
  }

  const esc = (v) =>
    String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  const fmt = (v, d = 1) =>
    Number.isFinite(Number(v))
      ? Number(v).toLocaleString("it-IT", { maximumFractionDigits: d })
      : "n.d.";
  const toArray = (v) => {
    if (Array.isArray(v)) return v;
    if (v == null) return [];
    if (typeof v !== "string") return [String(v)];
    try {
      const p = JSON.parse(v);
      return Array.isArray(p) ? p : [v];
    } catch (_) {
      return v.includes(",")
        ? v
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean)
        : [v];
    }
  };

  function opacity(id, value) {
    if (!map.getLayer(id)) return;
    const t = map.getLayer(id).type;
    const p =
      t === "fill-extrusion"
        ? "fill-extrusion-opacity"
        : t === "fill"
          ? "fill-opacity"
          : t === "line"
            ? "line-opacity"
            : t === "circle"
              ? "circle-opacity"
              : t === "symbol"
                ? "text-opacity"
                : null;
    if (p) map.setPaintProperty(id, p, value);
  }
  function addLayer(def) {
    if (!map.getLayer(def.id)) map.addLayer(def);
  }
  function card(kicker, title, body, meta = [], code = "") {
    return `<div class="map-card"><p class="map-card__eyebrow">${esc(kicker)}</p><h3 class="map-card__title">${esc(title)}</h3><p class="map-card__body">${body}</p>${
      meta.length
        ? `<div class="map-card__meta">${meta
            .filter(Boolean)
            .map((x) => `<span>${esc(x)}</span>`)
            .join("")}</div>`
        : ""
    }${code ? `<div class="map-card__code">${esc(code)}</div>` : ""}</div>`;
  }
  function show(lngLat, html) {
    if (popup) popup.remove();
    popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: "320px",
      offset: 10,
    })
      .setLngLat(lngLat)
      .setHTML(html)
      .addTo(map);
  }

  function buildRouteLayers() {
    const finalColor = [
      "match",
      ["get", "route_id"],
      "R2_23d58cd05658247380d7",
      COLORS.R2_23d58cd05658247380d7,
      "R2_65db885119e69d50c7d4",
      COLORS.R2_65db885119e69d50c7d4,
      "R2_b2032eeb31cba06561f0",
      COLORS.R2_b2032eeb31cba06561f0,
      "R2_2ffb6743b10bb3f0a97d",
      COLORS.R2_2ffb6743b10bb3f0a97d,
      "#fff",
    ];
    const currentColor = [
      "match",
      ["get", "route"],
      "D184",
      COLORS.D184,
      "D185",
      COLORS.D185,
      "#fff",
    ];
    const has184 = [">=", ["index-of", "D184", ["get", "routes"]], 0],
      has185 = [">=", ["index-of", "D185", ["get", "routes"]], 0];
    addLayer({
      id: "explore-current-glow",
      type: "line",
      source: "current-routes",
      paint: {
        "line-color": currentColor,
        "line-width": 10,
        "line-blur": 8,
        "line-opacity": 0,
      },
    });
    addLayer({
      id: "explore-current-routes",
      type: "line",
      source: "current-routes",
      paint: {
        "line-color": currentColor,
        "line-width": [
          "interpolate",
          ["linear"],
          ["zoom"],
          9,
          2.1,
          12,
          3.1,
          15,
          4.2,
        ],
        "line-opacity": 0,
        "line-dasharray": [3, 1],
      },
    });
    addLayer({
      id: "explore-current-hit",
      type: "line",
      source: "current-routes",
      paint: { "line-color": "#fff", "line-width": 17, "line-opacity": 0 },
    });
    addLayer({
      id: "explore-current-stops-halo",
      type: "circle",
      source: "current-gtfs-stops",
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          9,
          4.2,
          12,
          6.2,
          15,
          8,
        ],
        "circle-color": [
          "case",
          has184,
          COLORS.D184,
          has185,
          COLORS.D185,
          "#fff",
        ],
        "circle-opacity": 0,
      },
    });
    addLayer({
      id: "explore-current-stops",
      type: "circle",
      source: "current-gtfs-stops",
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          9,
          2.4,
          12,
          3.8,
          15,
          5.2,
        ],
        "circle-color": [
          "case",
          has185,
          COLORS.D185,
          has184,
          COLORS.D184,
          "#fff",
        ],
        "circle-opacity": 0,
        "circle-stroke-width": 1.2,
        "circle-stroke-color": "#07131f",
        "circle-stroke-opacity": 0.75,
      },
    });
    addLayer({
      id: "explore-final-glow",
      type: "line",
      source: "final-routes-exact",
      paint: {
        "line-color": finalColor,
        "line-width": 13,
        "line-blur": 9,
        "line-opacity": 0,
      },
    });
    addLayer({
      id: "explore-final-routes",
      type: "line",
      source: "final-routes-exact",
      paint: {
        "line-color": finalColor,
        "line-width": [
          "interpolate",
          ["linear"],
          ["zoom"],
          9,
          3,
          12,
          4.6,
          15,
          6,
        ],
        "line-opacity": 0,
      },
    });
    addLayer({
      id: "explore-final-hit",
      type: "line",
      source: "final-routes-exact",
      paint: { "line-color": "#fff", "line-width": 19, "line-opacity": 0 },
    });
    addLayer({
      id: "explore-final-anchors",
      type: "circle",
      source: "final-anchors-exact",
      paint: {
        "circle-radius": [
          "case",
          ["==", ["get", "kind"], "RAIL_HUB"],
          8,
          ["==", ["get", "kind"], "PROPOSED_STOP"],
          6,
          4.5,
        ],
        "circle-color": [
          "case",
          ["==", ["get", "kind"], "PROPOSED_STOP"],
          "#ffd36d",
          "#fff",
        ],
        "circle-opacity": 0,
        "circle-stroke-width": [
          "case",
          ["==", ["get", "kind"], "PROPOSED_STOP"],
          2,
          1.4,
        ],
        "circle-stroke-color": [
          "case",
          ["==", ["get", "kind"], "PROPOSED_STOP"],
          "#6b551f",
          "#07131f",
        ],
        "circle-stroke-opacity": 0,
      },
    });
  }

  async function loadGzip(urls) {
    const parts = await Promise.all(
      urls.map(async (u) => {
        const r = await fetch(u);
        if (!r.ok) throw new Error(`${u} ${r.status}`);
        return (await r.text()).trim();
      }),
    );
    const bin = atob(parts.join("")),
      bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    if (window.pako)
      return JSON.parse(window.pako.inflate(bytes, { to: "string" }));
    const stream = new Blob([bytes])
      .stream()
      .pipeThrough(new DecompressionStream("gzip"));
    return JSON.parse(
      new TextDecoder().decode(await new Response(stream).arrayBuffer()),
    );
  }
  async function ensureRoads() {
    if (map.getLayer("road-network")) return true;
    if (roadPromise) return roadPromise;
    roadPromise = (async () => {
      const geo = await loadGzip(J.meta.localAssets.roads);
      if (!map.getSource("road-graph"))
        map.addSource("road-graph", { type: "geojson", data: geo });
      addLayer({
        id: "road-shadow",
        type: "line",
        source: "road-graph",
        paint: {
          "line-color": "#06101a",
          "line-width": 4.2,
          "line-opacity": 0,
        },
      });
      addLayer({
        id: "road-network",
        type: "line",
        source: "road-graph",
        paint: {
          "line-color": [
            "case",
            ["boolean", ["get", "uncertain"], false],
            "#ff9b61",
            "#57d7e8",
          ],
          "line-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            10,
            0.3,
            13,
            1.15,
            16,
            2.4,
          ],
          "line-opacity": 0,
        },
      });
      return true;
    })().finally(() => (roadPromise = null));
    return roadPromise;
  }

  function addControls() {
    controls = document.createElement("div");
    controls.id = "journeyExplorerControls";
    controls.className = "explore-controls";
    controls.innerHTML = `<div class="explore-controls__head"><div><strong>Esplora Nodo8</strong><small>Simulazione</small></div><button class="explore-controls__exit" data-action="exit" type="button">Torna al racconto</button></div>
      <div class="explore-networks" aria-label="Linee sulla mappa">
        <button data-layer="nodo8" class="is-active" type="button"><i style="--c:#55e1bf"></i><span>Nodo8<small>La proposta</small></span><b aria-hidden="true">✓</b></button>
        <button data-layer="s8" type="button" disabled><i style="--c:#f8b1b0"></i><span>S8<small>Treni</small></span><b aria-hidden="true">✓</b></button>
        <button data-layer="d184" type="button" disabled><i style="--c:#4ca5ff"></i><span>D184<small>Situazione attuale</small></span><b aria-hidden="true">✓</b></button>
        <button data-layer="d185" type="button" disabled><i style="--c:#ff9b61"></i><span>D185<small>Situazione attuale</small></span><b aria-hidden="true">✓</b></button>
      </div>
      <select id="currentRouteChoice" hidden aria-hidden="true" tabindex="-1"><option value="ALL">D184 e D185</option><option value="D184">D184</option><option value="D185">D185</option></select>
      <div class="explore-controls__tabs" role="tablist" aria-label="Controlli"><button id="exploreBusTab" role="tab" aria-selected="true" aria-controls="exploreBusPanel" type="button">Orario</button><button id="exploreLayersTab" role="tab" aria-selected="false" aria-controls="exploreLayersPanel" tabindex="-1" type="button">Mappa</button></div>
      <section id="exploreBusPanel" role="tabpanel" aria-labelledby="exploreBusTab">
        <div id="explorePlayback" data-theme="dark" aria-label="Orologio condiviso Nodo8, D184, D185 e S8"><p role="status">Caricamento dell’orario…</p></div>
        <p id="explorePlaybackUnavailable" hidden role="status">Accendi una linea per vedere la simulazione.</p>
        <section id="currentComparisonPanel" hidden aria-label="Corse D184 e D185"><p id="currentBusStatus" class="current-bus-status" hidden></p></section>
        <p id="s8SimulationStatus" class="s8-status" hidden></p>
      </section>
      <section id="exploreLayersPanel" role="tabpanel" aria-labelledby="exploreLayersTab" hidden>
        <div class="explore-controls__group"><span>Fermate e accessibilità</span><div class="explore-controls__layers"><button data-layer="stops" class="is-active" type="button">Fermate</button><button data-layer="walk" type="button">Minuti a piedi</button></div></div>
        <div id="activeWalkLegend" hidden><small id="activeWalkStatus"></small><div class="explore-walk-key"><span><i style="--c:#55e1bf"></i>≤ 5 min</span><span><i style="--c:#99d5aa"></i>5–8</span><span><i style="--c:#e7d69a"></i>8–10</span><span><i style="--c:#e99b71"></i>&gt; 10</span><span><i style="--c:#8a9494"></i>n.d.</span></div></div>
        <div class="explore-controls__group"><span>Territorio</span><div class="explore-controls__layers"><button data-layer="worldpop" type="button">Abitanti stimati</button><button data-layer="sections" type="button">Zone ISTAT</button><button data-layer="buildings" type="button">Edifici abitati</button><button data-layer="roads" type="button">Rete stradale</button></div></div>
      </section>
      <details id="exploreTechnical" class="explore-technical"><summary>Dati e metodo</summary>
        <h4>Nodo8</h4><p>Orario di progetto 2027, 16 giri completi sullo stesso percorso. B1–B4 sono quattro mezzi di modello, non turni assegnati. Sosta prevista di 30 secondi alle fermate, attesa a FS e recupero di 10 minuti dopo il rientro. Movimento interpolato lungo il tracciato; non GPS, velocità osservata o traffico reale. La prosecuzione passeggeri sullo stesso bus a FS resta da autorizzare.</p>
        <h4>D184 e D185</h4><p>GTFS ufficiale 2025/26: tutte le 34 corse attive mercoledì 6 maggio 2026, 15 D184 e 19 D185. Tracciati e orari dello stesso feed. Questa fotografia storica non è l’orario più recente 2026/27. Le icone rappresentano corse, non mezzi fisici; i tempi intermedi sono interpolati. Il feed contiene anche tempi e distanze incoerenti: 48 dei 388 intervalli implicano oltre 90 km/h medi lungo la shape. In questi intervalli l’icona non viene disegnata; la corsa resta nel conteggio. È un filtro prudenziale della visualizzazione, non un limite stradale o una certificazione delle altre velocità. Le posizioni della shape alle fermate possono discostarsi dalle coordinate GTFS fino a circa 547 metri. Arrivo e partenza coincidono nel feed: non inventiamo soste o tempi corretti.</p><a href="../index.html#confronto">Confronto con gli orari 2026/27 ↗</a>
        <h4>Fonti ferroviarie</h4><p id="s8SourceNote">S8: orari Trenord del 1 ottobre 2026, 74 corse, percorso ferroviario OpenStreetMap Milano Porta Garibaldi–Lecco. Posizioni interpolate, non GPS. Nessuna validità futura o coincidenza garantita.</p>
        <h4>Accessibilità e territorio</h4><p>I minuti a piedi usano solo le fermate delle linee bus accese. Con più linee, si considera la fermata più vicina nella loro unione; S8 non contribuisce. Modello pedonale RT028 congelato, 80 m/min e connettori, su 4.283 unità di popolazione stimate RT016. Grigio significa cammino non calcolabile nel modello; 12 fermate esterne D185 non si collegano al grafo congelato. Non una verifica di accessibilità universale, frequenza, direzione di viaggio o domanda. La rete stradale è quella dello studio, non una certificazione di percorribilità con bus.</p>
      </details>
      <div class="explore-controls__footer"><div class="explore-controls__hint">Clicca le fermate sulla mappa.</div><div class="explore-controls__layers"><button data-action="clear" type="button">Spegni tutto</button><button data-action="reset" type="button">↺ Inquadra</button></div></div>`;
    document.body.appendChild(controls);
    controls.querySelectorAll('[data-layer="s8"]').forEach(button => {
      button.disabled = document.documentElement.dataset.s8Ready !== "true";
    });
    controls.querySelectorAll('[data-layer="d184"], [data-layer="d185"]').forEach(button => {
      button.disabled = document.documentElement.dataset.currentSimulationReady !== "true";
    });
    const tabs = [...controls.querySelectorAll('[role="tab"]')];
    const chooseTab = (chosen) => {
      tabs.forEach((tab) => {
        const selected = tab === chosen;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute("aria-controls")).hidden =
          !selected;
      });
      if (chosen.id !== "exploreBusTab")
        window.__analysisJourneyNodo8?.pauseExplorer();
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => chooseTab(tab));
      tab.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        event.preventDefault();
        const next = tabs[1 - index];
        chooseTab(next);
        next.focus();
      });
    });
    if (document.documentElement.dataset.nodo8Ready === "error") {
      controls.querySelector('[data-layer="nodo8"]').disabled = true;
      controls
        .querySelector('[data-layer="nodo8"]')
        .classList.remove("is-active");
      layers.nodo8 = false;
    }
    controls.querySelectorAll("[data-layer]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const k = btn.dataset.layer;
        layers[k] = !layers[k];
        if (k === "d184" || k === "d185") syncCurrentSelection();
        if (k in compatibilityState) compatibilityState[k] = layers[k];
        btn.classList.toggle("is-active", layers[k]);
        btn.setAttribute("aria-pressed", String(layers[k]));
        if (k === "walk" && layers.walk) {
          btn.disabled = true;
          try { await ensureActiveWalk(); }
          catch (error) {
            layers.walk = false;
            document.documentElement.dataset.activeWalkReady = "error";
            console.warn("Active-network walk layer unavailable",error);
          } finally {btn.disabled = false;}
        }
        if (k === "roads" && layers.roads) {
          btn.disabled = true;
          try {
            await ensureRoads();
          } catch (e) {
            console.warn("Gate D graph explore load failed", e);
            layers.roads = false;
            btn.classList.remove("is-active");
          } finally {
            btn.disabled = false;
          }
        }
        render();
      }),
    );
    controls
      .querySelector('[data-action="reset"]')
      .addEventListener("click", () => fit(true));
    controls
      .querySelector('[data-action="clear"]')
      .addEventListener("click", () => {
        Object.keys(layers).forEach((k) => (layers[k] = false));
        Object.keys(compatibilityState).forEach(
          (k) => (compatibilityState[k] = false),
        );
        syncCurrentSelection();
        controls
          .querySelectorAll("[data-layer]")
          .forEach((b) => b.classList.remove("is-active"));
        render();
      });
    controls
      .querySelector('[data-action="exit"]')
      .addEventListener("click", exit);
  }

  function render() {
    const scene = document.body.dataset.scene === "explore",
      interactive = scene && active,
      preview = scene && !active;
    // Outside Esplora, only clear layers owned by this controller. Previously
    // this observer ran last and erased the story's KML lines and population
    // layers immediately after their own scene controller had made them visible.
    if (!scene) {
      [
        "explore-current-glow", "explore-current-routes", "explore-current-hit",
        "explore-current-stops-halo", "explore-current-stops",
        "explore-final-glow", "explore-final-routes", "explore-final-hit",
        "explore-final-anchors", "explore-active-walk",
      ].forEach((id) => opacity(id, 0));
      window.__analysisJourneyActiveWalk?.render({visible:false,networks:[]});
      if (map.getLayer("explore-current-stops")) map.setPaintProperty("explore-current-stops", "circle-stroke-opacity", 0);
      if (controls) {
        controls.style.pointerEvents = "none";
        controls.inert = true;
        controls.setAttribute("aria-hidden", "true");
      }
      if (popup) {
        popup.remove();
        popup = null;
      }
      return;
    }
    [
      "current-route-glow",
      "current-routes",
      "final16-glow",
      "final16",
      "final185-glow",
      "final185",
      "existing-stops",
      "existing-stops-halo",
      "worldpop-stack",
      "sections-stack",
      "buildings-stack",
      "dasymetric-sparks",
    ].forEach((id) => opacity(id, 0));
    opacity("worldpop-columns", interactive && layers.worldpop ? 0.72 : 0);
    opacity("worldpop-wire", interactive && layers.worldpop ? 0.26 : 0);
    opacity("sections-fill", interactive && layers.sections ? 0.58 : 0);
    opacity("sections-outline", interactive && layers.sections ? 0.52 : 0);
    opacity("buildings-extrude", interactive && layers.buildings ? 0.82 : 0);
    opacity("buildings-outline", interactive && layers.buildings ? 0.26 : 0);
    // The narrative walk model is never reused as a selected-network result.
    opacity("piece-halo", 0);
    opacity("candidate-halo", interactive && layers.candidates ? 0.12 : 0);
    opacity("candidates", interactive && layers.candidates ? 0.9 : 0);
    opacity("road-shadow", interactive && layers.roads ? 0.3 : 0);
    opacity("road-network", interactive && layers.roads ? 0.66 : 0);
    const cur = interactive && layers.current,
      fin = (preview || interactive) && layers.proposals,
      showStops = (preview || interactive) && layers.stops;
    const datedCurrent = window.__analysisJourneyCurrent?.installed === true;
    opacity("explore-current-glow", cur && !datedCurrent ? 0.12 : 0);
    opacity("explore-current-routes", cur && !datedCurrent ? 0.9 : 0);
    const currentChoice = controls?.querySelector("#currentRouteChoice")?.value || "ALL";
    const routeFilter = currentChoice === "ALL" ? ["in", ["get", "route"], ["literal", ["D184", "D185"]]] : ["==", ["get", "route"], currentChoice];
    const stopFilter = currentChoice === "ALL" ? ["any", [">=", ["index-of", "D184", ["get", "routes"]], 0], [">=", ["index-of", "D185", ["get", "routes"]], 0]] : [">=", ["index-of", currentChoice, ["get", "routes"]], 0];
    for (const id of ["explore-current-routes", "explore-current-glow", "explore-current-hit"])
      if (map.getLayer(id)) map.setFilter(id, routeFilter);
    for (const id of ["explore-current-stops", "explore-current-stops-halo"])
      if (map.getLayer(id)) map.setFilter(id, stopFilter);
    opacity("explore-current-hit", cur && !datedCurrent ? 0.001 : 0);
    opacity(
      "explore-current-stops-halo",
      showStops && cur && !datedCurrent ? 0.72 : 0,
    );
    opacity(
      "explore-current-stops",
      showStops && cur && !datedCurrent ? 0.96 : 0,
    );
    if (map.getLayer("explore-current-stops")) map.setPaintProperty("explore-current-stops", "circle-stroke-opacity", showStops && cur && !datedCurrent ? 0.75 : 0);
    opacity("explore-final-glow", fin ? (preview ? 0.16 : 0.22) : 0);
    opacity("explore-final-routes", fin ? (preview ? 0.96 : 0.96) : 0);
    opacity("explore-final-hit", interactive && layers.proposals ? 0.001 : 0);
    opacity("explore-final-anchors", showStops && fin ? 0.98 : 0);
    if (map.getLayer("explore-final-anchors"))
      map.setPaintProperty(
        "explore-final-anchors",
        "circle-stroke-opacity",
        showStops && fin ? 0.9 : 0,
      );
    opacity("municipality-fill", scene ? 0.055 : 0.08);
    opacity("municipality-outline", scene ? 0.3 : 0.45);
    opacity("hub", 1);
    opacity("hub-glow", scene ? 0.24 : 0.1);
    if (map.getLayer("carto"))
      map.setPaintProperty("carto", "raster-opacity", scene ? 0.24 : 0.42);
    const walkNetworks = [
      ...(layers.nodo8 ? ["NODO8"] : []),
      ...(cur && currentChoice !== "D185" ? ["D184"] : []),
      ...(cur && currentChoice !== "D184" ? ["D185"] : []),
    ];
    window.__analysisJourneyActiveWalk?.render({visible:interactive && layers.walk,networks:walkNetworks});
    if (controls) {
      controls.querySelector("#currentComparisonPanel").hidden = !cur;
      controls.style.pointerEvents = interactive ? "auto" : "none";
      controls.inert = !interactive;
      controls.setAttribute("aria-hidden", String(!interactive));
      controls.querySelector("#explorePlaybackUnavailable").hidden =
        layers.nodo8 || layers.current || layers.s8;
      controls.querySelector("#activeWalkLegend").hidden = !layers.walk;
      controls.querySelector("#activeWalkStatus").textContent = walkNetworks.length
        ? "Fermate: " + walkNetworks.map(n => n === "NODO8" ? "Nodo8" : n).join(" + ")
        : "Accendi Nodo8, D184 o D185.";
      controls.querySelectorAll("[data-layer]").forEach((button) => {
        button.classList.toggle("is-active", layers[button.dataset.layer]);
        button.setAttribute(
          "aria-pressed",
          String(layers[button.dataset.layer]),
        );
      });
      document.documentElement.dataset.currentComparisonVisible = String(cur);
      document.documentElement.dataset.currentComparisonSelection = currentChoice;
      const currentModel = window.__analysisJourneyCurrent?.data;
      const datedTrips = currentModel?.trips.filter(t => currentChoice === "ALL" || t.route === currentChoice);
      document.documentElement.dataset.currentComparisonRouteCount = String(cur ? (datedTrips ? new Set(datedTrips.map(t=>`${t.route}:${t.shape_id}`)).size : lineage.currentData.features.filter(f => currentChoice === "ALL" || f.properties.route === currentChoice).length) : 0);
      document.documentElement.dataset.currentComparisonStopCount = String(cur && showStops ? (datedTrips ? new Set(datedTrips.flatMap(t=>t.calls.map(c=>c.stop_id))).size : lineage.stopData.features.filter(f => currentChoice === "ALL" || toArray(f.properties.routes).includes(currentChoice)).length) : 0);
    }
    if (scene)
      window.__analysisJourneyNodo8?.renderExplorer({
        visible: layers.nodo8,
        showStops,
        active: interactive,
      });
    if (!scene && popup) {
      popup.remove();
      popup = null;
    }
  }

  function fit(force = false) {
    if (!lineage || (!force && fitted)) return;
    if (
      layers.nodo8 &&
      !layers.proposals &&
      !layers.current &&
      window.__analysisJourneyNodo8?.installed
    ) {
      window.__analysisJourneyNodo8.fit();
      fitted = true;
      return;
    }
    const b = new maplibregl.LngLatBounds();
    const currentChoice = controls?.querySelector("#currentRouteChoice")?.value || "ALL";
    const dated = window.__analysisJourneyCurrent?.data;
    const currentFeatures = dated ? dated.trips.map(t => ({properties:{route:t.route},geometry:{type:"LineString",coordinates:dated.shapes[t.shape_id].coordinates}})) : lineage.currentData.features;
    const features = [
      ...(layers.current ? currentFeatures.filter(f => currentChoice === "ALL" || f.properties.route === currentChoice) : []),
      ...(layers.proposals ? lineage.finalData.features : []),
      ...(layers.nodo8 ? (window.__analysisJourneyNodo8?.data.routes || []).map(route => ({geometry:{type:"LineString",coordinates:route.coordinates}})) : []),
    ];
    if (!features.length) return;
    features.forEach((f) => {
      const c = f.geometry.coordinates;
      if (f.geometry.type === "Point") b.extend(c);
      else c.forEach((x) => b.extend(x));
    });
    map.fitBounds(b, {
      padding:
        innerWidth < 800
          ? { top: 85, right: 24, bottom: 195, left: 24 }
          : { top: 100, right: 460, bottom: 75, left: 60 },
      maxZoom: 12.5,
      duration: window.__analysisJourneyReduceMotion ? 0 : 900,
      pitch: 50,
      bearing: 3,
    });
    fitted = true;
  }
  function interactions(on) {
    if (on) {
      map.dragPan?.enable();
      map.scrollZoom?.enable();
      map.doubleClickZoom?.enable();
      map.boxZoom?.enable();
      map.keyboard?.enable();
      map.touchZoomRotate?.enable();
      map.dragRotate?.enable();
    } else {
      map.dragPan?.disable();
      map.scrollZoom?.disable();
      map.doubleClickZoom?.disable();
      map.boxZoom?.disable();
      map.keyboard?.disable();
      map.touchZoomRotate?.disable();
      map.dragRotate?.disable();
      map.touchZoomRotate?.disableRotation();
    }
  }
  function enter() {
    if (active) return;
    const chapter = document.querySelector('main .chapter[data-scene="explore"]');
    const rect = chapter?.getBoundingClientRect();
    if (!rect || rect.bottom <= 0 || rect.top >= innerHeight) return;
    // A freshly laid-out deep link can be visible before the scroll director
    // updates its scene. The visible entry button must work on the first click.
    window.ScrollTrigger?.update();
    active = true;
    document.body.dataset.scene = "explore";
    document.body.classList.add("is-map-exploring");
    document.documentElement.classList.add("is-map-exploring");
    interactions(true);
    render();
    requestAnimationFrame(() => fit(true));
  }
  function exit() {
    if (!active) return;
    active = false;
    document.body.classList.remove("is-map-exploring");
    document.documentElement.classList.remove("is-map-exploring");
    interactions(false);
    if (popup) {
      popup.remove();
      popup = null;
    }
    render();
  }

  function inspect(kind, f, lngLat) {
    const p = f.properties || {};
    if (kind === "anchor") {
      const k = p.kind;
      if (k === "PROPOSED_STOP")
        return show(
          f.geometry.coordinates,
          card(
            "Nuova fermata candidata",
            "Fermata da verificare sul posto",
            "È un punto individuato dalla ricerca, <strong>da verificare sul posto</strong>.",
            toArray(p.routes).map((x) => LABELS[x] || x),
            p.anchor_id,
          ),
        );
      if (k === "RAIL_HUB")
        return show(
          f.geometry.coordinates,
          card(
            "Nodo ferroviario",
            p.label || "Olgiate-Calco-Brivio FS",
            "Nodo di interscambio attorno al quale vengono valutati gli assetti finalisti.",
            [],
            p.anchor_id,
          ),
        );
      return show(
        f.geometry.coordinates,
        card(
          "Fermata esistente riutilizzata",
          p.label || p.anchor_id,
          "Fermata già presente nella baseline ufficiale.",
          toArray(p.routes).map((x) => LABELS[x] || x),
          p.anchor_id,
        ),
      );
    }
    if (kind === "stop")
      return show(
        f.geometry.coordinates,
        card(
          "D184 / D185 · fermata di riferimento",
          p.name || p.cluster_id,
          "Fermata strutturale dal GTFS ufficiale 2025/26. Non certifica quali corse la servano oggi.",
          toArray(p.routes),
          p.cluster_id,
        ),
      );
    if (kind === "candidate")
      return show(
        lngLat,
        card(
          "Ricerca storica · possibile fermata",
          "Un punto da verificare",
          "Punto nelle zone lontane dalle fermate. Non è una raccomandazione: <strong>serve una verifica sul posto</strong>.",
          [
            `+${fmt(p.gain, 0)} residenti entro 10 min`,
            p.highway || "classe n.d.",
          ],
          p.uncertainty || "",
        ),
      );
    if (kind === "walk")
      return show(
        lngLat,
        card(
          "Accessibilità pedonale",
          Number(p.walk) < 90 ? `${fmt(p.walk, 1)} minuti` : "tempo n.d.",
          "Tempo di rete pedonale verso la fermata esistente più vicina, non distanza in linea d’aria.",
          [`${fmt(p.pop, 1)} residenti`, "unità edificio × sezione"],
        ),
      );
    if (kind === "building")
      return show(
        lngLat,
        card(
          "Edificio · residenti stimati",
          `${fmt(p.pop, 1)} residenti modellati`,
          "Stima spaziale su sagoma edilizia compatibile con uso residenziale, non dato anagrafico a un civico.",
          [p.pieces ? `${fmt(p.pieces, 0)} unità` : "DBGT"],
          p.building_id || "",
        ),
      );
    if (kind === "section")
      return show(
        lngLat,
        card(
          "Sezione di censimento",
          `${fmt(p.pop2025, 1)} residenti 2025`,
          "Struttura territoriale ISTAT riallineata ai totali comunali POSAS 2025.",
          ["ISTAT", "POSAS 2025"],
          p.SEZ2011 || p.section_id || "",
        ),
      );
    if (kind === "worldpop")
      return show(
        lngLat,
        card(
          "WorldPop · griglia 100 m",
          `${fmt(p.pop, 1)} residenti modellati`,
          "Prima rappresentazione spaziale della popolazione usata nello scroll.",
          ["cella 100 m", "rappresentazione iniziale"],
        ),
      );
    if (kind === "road")
      return show(
        lngLat,
        card(
          "Rete stradale dello studio",
          p.uncertain ? "Tratto con incertezza" : "Tratto incluso nella rete del bus",
          "Segmento del grafo congelato usato per i percorsi finalisti, con sensi unici, accessi e restrizioni di svolta.",
          [
            p.highway || "classe n.d.",
            p.uncertain ? "uncertainty flag" : "strutturale",
          ],
          p.way_id || p.osm_way_id || "",
        ),
      );
  }

  function clickEvents() {
    map.on("mousemove", (e) => {
      if (!active || document.body.dataset.scene !== "explore") return;
      const ids = interactiveIds();
      const hits = ids.length
        ? map.queryRenderedFeatures(e.point, { layers: ids })
        : [];
      map.getCanvas().style.cursor = hits.length ? "pointer" : "grab";
    });
    map.on("click", (e) => {
      if (!active || document.body.dataset.scene !== "explore") return;
      const ids = interactiveIds(),
        hits = ids.length
          ? map.queryRenderedFeatures(e.point, { layers: ids })
          : [];
      if (!hits.length) {
        if (popup) popup.remove();
        popup = null;
        return;
      }
      const find = (id) => hits.find((x) => x.layer.id === id);
      let f;
      if ((f = find("nodo8-sites"))) {
        if (popup) {
          popup.remove();
          popup = null;
        }
        return window.__analysisJourneyNodo8?.showSite(f.properties.site_id);
      }
      if ((f = find("nodo8-hit"))) {
        if (popup) {
          popup.remove();
          popup = null;
        }
        return window.__analysisJourneyNodo8?.showRoute(e.lngLat);
      }
      if ((f = find("explore-final-anchors")))
        return inspect("anchor", f, e.lngLat);
      if ((f = find("explore-current-stops")))
        return inspect("stop", f, e.lngLat);
      if ((f = find("current-dated-stops")))
        return show(e.lngLat,card("Fermata D184 / D185", f.properties.name,
          "",[f.properties.route]));
      if ((f = find("candidates"))) return inspect("candidate", f, e.lngLat);
      if ((f = find("explore-active-walk"))) {
        const minutes = f.properties.walk_min;
        const seconds = Math.round(Number(minutes) * 60);
        const label = minutes !== null && minutes !== undefined && Number.isFinite(Number(minutes))
          ? `${Math.floor(seconds / 60)} min ${seconds % 60} s a piedi`
          : "Cammino non calcolabile";
        return show(e.lngLat,card("Alla fermata più vicina",label,"Stima del modello.",
          [String(f.properties.active_networks || "").replaceAll("NODO8","Nodo8")]));
      }
      if ((f = find("buildings-extrude")))
        return inspect("building", f, e.lngLat);
      if ((f = find("sections-fill"))) return inspect("section", f, e.lngLat);
      if ((f = find("worldpop-columns")))
        return inspect("worldpop", f, e.lngLat);
      if ((f = find("road-network"))) return inspect("road", f, e.lngLat);
      const finals = hits.filter((x) => x.layer.id === "explore-final-hit");
      if (finals.length) {
        const uniq = [
          ...new Map(finals.map((x) => [x.properties.route_id, x])).values(),
        ];
        return show(
          e.lngLat,
          card(
            uniq.length > 1 ? "Tratto condiviso" : "Linea finalista",
            uniq
              .map(
                (x) => LABELS[x.properties.route_id] || x.properties.route_id,
              )
              .join(" + "),
            "Geometria Gate D validata contro la Reduced Path Matrix V2.",
            uniq.flatMap((x) => [
              `${fmt(x.properties.distance_km, 2)} km`,
              `${fmt(x.properties.runtime_min, 1)} min`,
            ]),
          ),
        );
      }
      const current = hits.filter((x) => ["explore-current-hit","current-dated-hit"].includes(x.layer.id));
      if (current.length) {
        const rs = [
          ...new Set(current.map((x) => x.properties.route).filter(Boolean)),
        ];
        if (current[0].layer.id === "current-dated-hit") return show(e.lngLat,
          card("Percorso della situazione attuale",rs.join(" + "),"Tracciato ufficiale GTFS.",[]));
        return show(
          e.lngLat,
          card(
            "D184 / D185 · percorso ufficiale",
            rs.join(" + "),
            "Tracciato copiato dal KML ufficiale, senza ricalcolo stradale. È una variante di riferimento, non prova che una corsa sia qui nell’ora simulata.",
            rs,
            "CURRENT_SERVICE_KML_GEOMETRY_V1",
          ),
        );
      }
    });
  }
  function interactiveIds() {
    const a = [];
    if (layers.nodo8) {
      if (layers.stops) a.push("nodo8-sites");
      a.push("nodo8-hit");
    }
    if (layers.proposals) a.push("explore-final-anchors", "explore-final-hit");
    if (layers.stops && layers.current)
      a.push(layers.current && window.__analysisJourneyCurrent?.installed ? "current-dated-stops" : "explore-current-stops");
    if (layers.current) a.push(window.__analysisJourneyCurrent?.installed ? "current-dated-hit" : "explore-current-hit");
    if (layers.candidates) a.push("candidates");
    if (layers.walk) a.push("explore-active-walk");
    if (layers.buildings) a.push("buildings-extrude");
    if (layers.sections) a.push("sections-fill");
    if (layers.worldpop) a.push("worldpop-columns");
    if (layers.roads) a.push("road-network");
    return a.filter((id) => map.getLayer(id));
  }

  function sceneChanged() {
    const here = document.body.dataset.scene === "explore";
    if (here) {
      render();
      requestAnimationFrame(() => fit(false));
    } else {
      if (active) exit();
      fitted = false;
      render();
    }
  }
  function install() {
    lineage = window.__analysisJourneyLineage;
    if (
      !lineage?.installed ||
      !lineage.exactRoutes ||
      !window.__analysisJourneyCurrentKmlExact?.installed
    )
      return false;
    if (
      ![
        "current-routes",
        "current-gtfs-stops",
        "final-routes-exact",
        "final-anchors-exact",
        "worldpop",
        "sections",
        "buildings",
        "pieces",
        "candidates",
      ].every((id) => map.getSource(id))
    )
      return false;
    buildRouteLayers();
    addControls();
    clickEvents();
    document
      .querySelector("[data-explore-enter]")
      ?.addEventListener("click", enter);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && active) exit();
    });
    new MutationObserver(sceneChanged).observe(document.body, {
      attributes: true,
      attributeFilter: ["data-scene"],
    });
    sceneChanged();
    window.__analysisJourneyExplore = {
      installed: true,
      state: compatibilityState,
      layers,
      render,
      fit: () => fit(true),
      enter,
      exit,
      isActive: () => active,
      ensureRoadGraph: ensureRoads,
      showAnchor: (id) => {
        const f = lineage.anchorData.features.find(
          (x) => x.properties.anchor_id === id,
        );
        if (f) inspect("anchor", f, f.geometry.coordinates);
        return !!f;
      },
      showCurrentStop: (id) => {
        const f = lineage.stopData.features.find(
          (x) => x.properties.cluster_id === id,
        );
        if (f) inspect("stop", f, f.geometry.coordinates);
        return !!f;
      },
    };
    document.dispatchEvent(new Event("journey-explore-ready"));
    return true;
  }
  let tries = 0;
  const timer = setInterval(() => {
    tries++;
    if (install() || tries > 240) clearInterval(timer);
  }, 50);
})();
