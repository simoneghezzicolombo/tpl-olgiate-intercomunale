/* Current proposal overlay. Historical datasets and route sources stay separate. */
import { buildLine } from "../nodo8-line.mjs?v=20261008d";
import {
  mountPlayer,
  makeBusMarker,
  updateBusMarker,
  mountRoadPreview,
} from "../nodo8-experience.mjs?v=20261008d";
export const NODO8_SCENES = ["nodo8", "nodo8-time", "end"];

// Only a visible current-proposal context may paint the shared map markers.
export function playbackVisible({ scene, exploring, nodo8Visible }, context) {
  return context === "story"
    ? scene === "nodo8-time"
    : context === "explore" &&
        scene === "explore" &&
        exploring === true &&
        nodo8Visible === true;
}

export function validateNodo8(data) {
  if (
    data.contract !== "nodo8_showcase_v1" ||
    data.sites?.length !== 27 ||
    data.trips?.length !== 16 ||
    data.routes?.length !== 2 ||
    data.calendar?.service_year !== 2027 ||
    data.authority?.network_selected !== false ||
    data.authority?.public_operating_timetable_authorised !== false ||
    data.authority?.primary_selection_authorised !== false ||
    data.authority?.runner_up_selection_authorised !== false
  ) {
    throw new Error(
      "Nodo8 source contract is not the confirmed presentation basis.",
    );
  }
  return data;
}

export function makeNodo8Features(data) {
  validateNodo8(data);
  return {
    routes: {
      type: "FeatureCollection",
      features: data.routes.map((route) => ({
        type: "Feature",
        properties: {
          wing: route.wing,
          proposal: "Nodo8",
          source: data.sources.geometry.path,
        },
        geometry: { type: "LineString", coordinates: route.coordinates },
      })),
    },
    sites: {
      type: "FeatureCollection",
      features: data.sites.map((site) => ({
        type: "Feature",
        id: site.site_id,
        properties: {
          site_id: site.site_id,
          name: site.name,
          proposed_new_site: site.proposed_new_site,
          boarding_authorised: false,
          occurrence_count: site.ordered_occurrences.length,
        },
        geometry: { type: "Point", coordinates: site.coordinates_lon_lat },
      })),
    },
  };
}

const colour = "#55e1bf";
const historicalLayers = [
  "final16",
  "final16-glow",
  "final185",
  "final185-glow",
  "final-routes-exact",
  "final-routes-exact-glow",
  "final-anchors-exact",
  "explore-final-routes",
  "explore-final-glow",
  "explore-final-hit",
  "explore-final-anchors",
];
const number = (value) =>
  Number(value).toLocaleString("it-IT", { maximumFractionDigits: 1 });

function setStatus(message, failed = false) {
  document.querySelectorAll(".nodo8-load-status").forEach((node) => {
    node.textContent = message;
    node.classList.toggle("is-error", failed);
  });
  document.documentElement.dataset.nodo8Ready = failed ? "error" : "true";
}

async function waitForMap() {
  return new Promise((resolve, reject) => {
    const started = performance.now();
    const timer = setInterval(() => {
      if (window.__analysisJourneyBootError) {
        clearInterval(timer);
        reject(new Error("Historical WebGL runtime unavailable"));
        return;
      }
      const map = window.__analysisJourneyMap;
      if (map?.getLayer("hub")) {
        clearInterval(timer);
        resolve(map);
      } else if (performance.now() - started > 120000) {
        clearInterval(timer);
        reject(new Error("Map readiness deadline reached"));
      }
    }, 100);
  });
}

async function installNodo8() {
  let validatedLine = null;
  const landingHash = location.hash;
  let landingInterrupted = false;
  const interruptLanding = () => {
    landingInterrupted = true;
  };
  for (const event of ["wheel", "touchstart", "keydown", "pointerdown"])
    window.addEventListener(event, interruptLanding, {
      once: true,
      passive: true,
    });
  try {
    const response = await fetch("../assets/nodo8-proposal.json");
    if (!response.ok) throw new Error("Nodo8 data HTTP " + response.status);
    const data = validateNodo8(await response.json());
    const line = buildLine(data);
    validatedLine = line;
    const features = makeNodo8Features(data);
    const map = await waitForMap();
    map.addSource("nodo8-routes", { type: "geojson", data: features.routes });
    map.addSource("nodo8-sites", { type: "geojson", data: features.sites });
    map.addLayer({
      id: "nodo8-glow",
      type: "line",
      source: "nodo8-routes",
      paint: {
        "line-color": colour,
        "line-width": 11,
        "line-blur": 5,
        "line-opacity": 0,
      },
    });
    map.addLayer({
      id: "nodo8-routes",
      type: "line",
      source: "nodo8-routes",
      paint: {
        "line-color": colour,
        "line-width": ["interpolate", ["linear"], ["zoom"], 10, 3, 14, 5.5],
        "line-opacity": 0,
      },
    });
    map.addLayer({
      id: "nodo8-hit",
      type: "line",
      source: "nodo8-routes",
      paint: { "line-color": "#fff", "line-width": 18, "line-opacity": 0 },
    });
    map.addLayer({
      id: "nodo8-sites",
      type: "circle",
      source: "nodo8-sites",
      paint: {
        "circle-radius": ["case", ["get", "proposed_new_site"], 6, 4],
        "circle-color": [
          "case",
          ["get", "proposed_new_site"],
          "#ffd36d",
          "#fff",
        ],
        "circle-stroke-color": "#07131f",
        "circle-stroke-width": 1.6,
        "circle-stroke-opacity": 0,
        "circle-opacity": 0,
      },
    });
    let popup = null,
      lastScene = null;
    let explorerPlayer = null;
    const contextVisible = (context) =>
      playbackVisible(
        {
          scene: document.body.dataset.scene,
          exploring: window.__analysisJourneyExplore?.isActive() === true,
          nodo8Visible: window.__analysisJourneyExplore?.layers.nodo8 === true,
        },
        context,
      );
    const opacity = (id, value) => {
      if (!map.getLayer(id)) return;
      map.setPaintProperty(
        id,
        map.getLayer(id).type === "circle" ? "circle-opacity" : "line-opacity",
        value,
      );
    };
    const fit = () => {
      const bounds = new window.maplibregl.LngLatBounds();
      data.routes.forEach((route) =>
        route.coordinates.forEach((coordinate) => bounds.extend(coordinate)),
      );
      map.fitBounds(bounds, {
        padding: document.body.classList.contains("is-map-exploring")
          ? {
              top: 90,
              right: innerWidth < 800 ? 35 : 480,
              bottom: innerWidth < 800 ? Math.min(innerHeight * 0.5, 360) : 180,
              left: innerWidth < 800 ? 35 : 60,
            }
          : innerWidth < 800
            ? {
                top: 90,
                right: 30,
                bottom: 100,
                left: 30,
              }
            : {
                top: 100,
                right: 70,
                bottom: 80,
                left: Math.min(680, innerWidth * 0.5),
              },
        maxZoom: 13.2,
        pitch: 35,
        bearing: 0,
        duration: window.__analysisJourneyReduceMotion ? 0 : 650,
      });
    };
    const renderExplorer = ({ visible, showStops, active }) => {
      if (!visible && popup) {
        popup.remove();
        popup = null;
      }
      document.documentElement.dataset.nodo8Visible = String(visible);
      document.documentElement.dataset.nodo8SitesVisible = String(
        visible && showStops,
      );
      opacity("nodo8-glow", visible ? 0.15 : 0);
      opacity("nodo8-routes", visible ? 0.98 : 0);
      opacity("nodo8-hit", visible && active ? 0.001 : 0);
      opacity("nodo8-sites", visible && showStops ? 0.98 : 0);
      map.setPaintProperty(
        "nodo8-sites",
        "circle-stroke-opacity",
        visible && showStops ? 0.95 : 0,
      );
      const host = document.getElementById("explorePlayback");
      if (host) host.hidden = !active || !visible;
      if (explorerPlayer) {
        if (!contextVisible("explore")) explorerPlayer.pause();
        explorerPlayer.render();
      }
      if (!contextVisible("story") && !contextVisible("explore")) {
        markers.forEach((entry) => {
          entry.marker.remove();
          entry.added = false;
        });
      }
    };
    const showSite = (siteId) => {
      const site = data.sites.find((row) => row.site_id === siteId);
      if (!site) return false;
      if (popup) popup.remove();
      const card = document.createElement("div");
      const heading = document.createElement("h3");
      heading.textContent = site.name;
      const note = document.createElement("p");
      note.textContent = site.proposed_new_site
        ? "Nodo8 · nuovo sito proposto. Accosto da approvare."
        : "Nodo8 · sito da inventario. Accosto per questo servizio da validare.";
      card.append(heading, note);
      site.ordered_occurrences.forEach((event) => {
        const line = document.createElement("p");
        line.textContent =
          "Nodo8 · evento " +
          event.ordered_nonhub_event_number +
          ": FS → evento " +
          number(event.nominal_fs_to_occurrence_in_vehicle_min) +
          " min; evento → prossima FS " +
          number(event.nominal_occurrence_to_next_fs_in_vehicle_min) +
          " min.";
        card.append(line);
      });
      const limit = document.createElement("p");
      limit.textContent = site.hub_service_roles.length
        ? "Partenza, sosta intermedia e arrivo dello stesso giro; permanenza a bordo progettata, non autorizzata."
        : "Tempi nominali a bordo, senza cammino o attesa iniziale. Eventi diversi non sono viaggi intercambiabili.";
      card.append(limit);
      popup = new window.maplibregl.Popup({ maxWidth: "340px", offset: 12 })
        .setLngLat(site.coordinates_lon_lat)
        .setDOMContent(card)
        .addTo(map);
      return true;
    };
    const showRoute = (lngLat) => {
      if (popup) popup.remove();
      popup = new window.maplibregl.Popup({ maxWidth: "320px" })
        .setLngLat(lngLat)
        .setText(
          "Nodo8: un unico percorso a otto di 27,124 km, 16 giri completi. Stesso percorso e stesso mezzo di modello per tutta la corsa. Geometria di progetto, non autorizzazione stradale.",
        )
        .addTo(map);
    };
    const playbackContainer = document.getElementById("journeyPlayback");
    document.querySelector("#orario-nodo8 .copy").append(playbackContainer);
    playbackContainer.dataset.theme = "dark";
    playbackContainer.hidden = false;
    const roadPreview = mountRoadPreview(line);
    const markers = new Map();
    const paintBuses = ({ states, followedTrip }) => {
      states.forEach((s) => {
        const visible =
          s.coordinates && (!followedTrip || s.trip === followedTrip);
        if (!markers.has(s.id)) {
          const icon = makeBusMarker(s.id);
          const marker = new window.maplibregl.Marker({
            element: icon,
            anchor: "center",
          });
          markers.set(s.id, { marker, icon, added: false });
        }
        const entry = markers.get(s.id),
          { marker, icon } = entry;
        if (visible) {
          marker.setLngLat(s.coordinates);
          if (!entry.added) {
            marker.addTo(map);
            entry.added = true;
          }
          updateBusMarker(icon, s, { showCarrier: !followedTrip });
        } else if (entry.added) {
          marker.remove();
          entry.added = false;
        }
      });
    };
    const player = mountPlayer(
      playbackContainer,
      line,
      (state) => {
        roadPreview.update(state);
        if (contextVisible("story")) paintBuses(state);
      },
      {
        compact: true,
        brief: true,
        inlineMap: roadPreview.node,
      },
    );
    const mountExplorerPlayer = () => {
      const host = document.getElementById("explorePlayback");
      if (!host || explorerPlayer) return;
      explorerPlayer = mountPlayer(
        host,
        line,
        (state) => {
          if (contextVisible("explore")) paintBuses(state);
        },
        {
          compact: true,
          brief: true,
          initialSelection: "all",
          initialMinute: 455,
        },
      );
      document.documentElement.dataset.nodo8ExplorerPlaybackReady = "true";
    };
    const renderScene = () => {
      const scene = document.body.dataset.scene;
      mountExplorerPlayer();
      if (scene !== "nodo8-time") player.pause();
      player.render();
      if (scene === "explore") {
        const explore = window.__analysisJourneyExplore;
        renderExplorer({
          visible: explore?.layers.nodo8 !== false,
          showStops: explore?.layers.stops !== false,
          active: explore?.isActive() === true,
        });
        if (lastScene !== scene && explore?.layers.nodo8 !== false) fit();
      } else {
        const visible = NODO8_SCENES.includes(scene);
        if (visible) historicalLayers.forEach((id) => opacity(id, 0));
        renderExplorer({ visible, showStops: visible, active: false });
        if (visible && lastScene !== scene) fit();
      }
      if (lastScene !== scene && popup) {
        popup.remove();
        popup = null;
      }
      lastScene = scene;
    };
    window.__analysisJourneyNodo8 = {
      installed: true,
      data,
      renderScene,
      renderExplorer,
      fit,
      showSite,
      showRoute,
      pauseExplorer: () => {
        explorerPlayer?.pause();
        explorerPlayer?.render();
      },
      showFourBuses: () => {
        explorerPlayer?.selectTrip("all");
        explorerPlayer?.jump(455);
      },
    };
    new MutationObserver(renderScene).observe(document.body, {
      attributes: true,
      attributeFilter: ["data-scene", "class"],
    });
    document.addEventListener("journey-explore-ready", renderScene);
    window.addEventListener("resize", () => {
      if (NODO8_SCENES.includes(document.body.dataset.scene)) fit();
    });
    setStatus(
      "Dati Nodo8 caricati · base confermata, non esercizio autorizzato.",
    );
    renderScene();
    requestAnimationFrame(() => {
      window.ScrollTrigger?.refresh();
      // Mounting the in-flow player changes the later chapters' positions.
      // Honour the landing anchor once, unless the reader has already acted.
      if (
        !landingInterrupted &&
        location.hash === landingHash &&
        !document.body.classList.contains("is-map-exploring")
      ) {
        document
          .getElementById(landingHash.slice(1))
          ?.querySelector(".copy")
          ?.scrollIntoView({ behavior: "instant", block: "center" });
      }
    });
  } catch (error) {
    setStatus(
      "Mappa Nodo8 non disponibile. Non vengono usate le vecchie alternative come sostituto: consulta la vetrina e il GeoJSON della proposta.",
      true,
    );
    document.querySelectorAll('[data-layer="nodo8"]').forEach((button) => {
      button.disabled = true;
    });
    document
      .querySelector('[data-action="four-buses"]')
      ?.setAttribute("disabled", "");
    const explorerStatus = document.querySelector("#explorePlayback");
    if (explorerStatus && !explorerStatus.querySelector(".n8-clock")) {
      explorerStatus.textContent =
        "Animazione indisponibile: il registro di progetto o la mappa non è stato caricato. Nessun bus sostitutivo viene inventato.";
    }
    if (
      validatedLine &&
      !document.querySelector("#journeyPlayback .n8-clock")
    ) {
      const host = document.getElementById("journeyPlayback"),
        road = mountRoadPreview(validatedLine);
      document.querySelector("#orario-nodo8 .copy").append(host);
      host.hidden = false;
      host.dataset.theme = "dark";
      mountPlayer(host, validatedLine, road.update, {
        compact: true,
        brief: true,
        inlineMap: road.node,
      });
      document.documentElement.dataset.nodo8PlaybackReady = "fallback";
    }
    console.error("Nodo8 journey overlay unavailable", error);
  }
}

if (typeof window !== "undefined") installNodo8();
