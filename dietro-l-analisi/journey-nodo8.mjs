/* Current proposal overlay. Historical datasets and route sources stay separate. */
import { buildLine, diagramStops, siteTimetable } from "../nodo8-line.mjs?v=20261010b";
import { stopLink } from "../nodo8-stop-times.mjs?v=20261010b";
import { journeyDurationLabel } from "../nodo8-journey-inspector.mjs?v=20261010b";
import { installS8 } from "../nodo8-s8.mjs?v=20261010b";
import { installCurrent } from "../nodo8-current.mjs?v=20261010b";
import {
  mountPlayer,
  makeBusMarker,
  updateBusMarker,
} from "../nodo8-experience.mjs?v=20261010b";
export const NODO8_SCENES = ["nodo8", "nodo8-time", "end"];

// Only a visible current-proposal context may paint the shared map markers.
export function playbackVisible({ scene, exploring, nodo8Visible }, context) {
  return context === "explore" &&
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

/* Popup rows follow the ledger's occurrence order. Duration fields remain the
 * confirmed site-level values, rather than a journey inferred from one trip. */
export function popupSiteRows(line, siteId) {
  const { columns } = siteTimetable(line, siteId);
  const site = line.sites.get(siteId);
  const hubLabels = {
    FULL_TRIP_START_FS: "Partenza del giro",
    INTERMEDIATE_FS_STAY_ONBOARD_DESIGN: "Sosta intermedia",
    FULL_TRIP_END_FS: "Arrivo finale",
  };
  return columns.map((column) => {
    if (!column.ordinal)
      return { key: column.key, role: column.role, label: hubLabels[column.role] };
    const occurrence = site.ordered_occurrences.find(
      (event) => event.occurrence_id === column.key,
    );
    return {
      key: column.key,
      role: column.role,
      ordinal: column.ordinal,
      fromFs: journeyDurationLabel(occurrence.nominal_fs_to_occurrence_in_vehicle_min),
      toFs: journeyDurationLabel(occurrence.nominal_occurrence_to_next_fs_in_vehicle_min),
    };
  });
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
const popupNode = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const popupDetails = (summary, text) => {
  const details = popupNode("details", "nodo8-popup-method");
  details.append(popupNode("summary", "", summary), popupNode("p", "", text));
  return details;
};

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
    const siteNames = new Map(
      diagramStops(line).map((e) => [e.siteId, e.display]),
    );
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
    let rail = null;
    let current = null;
    const currentVisible = () => current !== null && document.body.dataset.scene === "explore" &&
      window.__analysisJourneyExplore?.isActive() === true && window.__analysisJourneyExplore?.layers.current === true;
    installCurrent(map).then(installed => {
      current = installed;
      window.__analysisJourneyCurrent = {installed:true,data:current.data,playback:current.playback.asset};
      document.documentElement.dataset.currentSimulationReady = "true";
      document.querySelectorAll('[data-layer="d184"], [data-layer="d185"]').forEach(button => {button.disabled = false;});
      window.__analysisJourneyExplore?.render();
      explorerPlayer?.render();
    }).catch(error => {
      document.documentElement.dataset.currentSimulationReady = "error";
      const status = document.getElementById("currentBusStatus");
      if (status) {status.hidden=false;status.textContent="Animazione D184/D185 non disponibile. Resta solo il riferimento geometrico.";}
      console.warn("Existing-service animation unavailable",error);
    });
    const railVisible = () => document.body.dataset.scene === "explore" &&
      window.__analysisJourneyExplore?.isActive() === true &&
      window.__analysisJourneyExplore?.layers.s8 === true;
    // Rail failure cannot replace or invalidate the confirmed bus proposal.
    installS8(map).then(installed => {
      rail = installed;
      document.documentElement.dataset.s8Ready = "true";
      document.querySelectorAll('[data-layer="s8"]').forEach(b => { b.disabled = false; });
      explorerPlayer?.render();
    }).catch(error => {
      document.documentElement.dataset.s8Ready = "error";
      document.querySelectorAll('[data-layer="s8"]').forEach(b => { b.disabled = true; });
      const note = document.getElementById("s8SourceNote");
      if (note) note.textContent = "S8 non disponibile: nessun tracciato o treno sostitutivo viene inventato.";
      console.warn("S8 overlay unavailable", error);
    });
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
            : window.__analysisJourneyMapFrame?.() || {
                top: 100, right: 70, bottom: 80, left: Math.min(680, innerWidth * 0.5),
              },
        maxZoom: 13.2,
        pitch: document.body.classList.contains("is-map-exploring") ? 0 : 35,
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
      if (host) {
        host.hidden = !active || (!visible && !railVisible() && !currentVisible());
        host.dataset.nodo8Enabled = String(visible);
      }
      if (explorerPlayer) {
        if (!contextVisible("explore") && !railVisible() && !currentVisible()) explorerPlayer.pause();
        explorerPlayer.render();
      }
      if (!contextVisible("story") && !contextVisible("explore")) {
        markers.forEach((entry) => {
          entry.marker.remove();
          entry.added = false;
        });
      }
    };
    const openPopup = (card, lngLat) => {
      if (popup) popup.remove();
      const previousFocus = document.activeElement;
      const heading = card.querySelector("h3");
      heading.id = "nodo8-popup-heading";
      heading.tabIndex = -1;
      popup = new window.maplibregl.Popup({
        className: "nodo8-map-popup",
        maxWidth: "340px",
        offset: 12,
      })
        .setLngLat(lngLat)
        .setDOMContent(card)
        .addTo(map);
      const element = popup.getElement();
      element.setAttribute("role", "dialog");
      element.setAttribute("aria-labelledby", heading.id);
      element.querySelector(".maplibregl-popup-close-button")
        ?.setAttribute("aria-label", "Chiudi informazioni sulla mappa");
      const openedPopup = popup;
      element.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        event.stopPropagation();
        openedPopup.remove();
        if (previousFocus?.isConnected && !element.contains(previousFocus))
          previousFocus.focus({ preventScroll: true });
      });
      heading.focus({ preventScroll: true });
    };
    const showSite = (siteId) => {
      const site = data.sites.find((row) => row.site_id === siteId);
      if (!site) return false;
      const isHub = site.hub_service_roles.length > 0;
      const card = popupNode("div", "nodo8-popup-card");
      const header = popupNode("div", "nodo8-popup-header");
      header.append(popupNode("span", "nodo8-popup-eyebrow", "Nodo8 · proposta"));
      if (site.proposed_new_site)
        header.append(popupNode("span", "nodo8-popup-badge", "Nuova fermata"));
      const heading = popupNode("h3", "", isHub
        ? "Olgiate FS"
        : siteNames.get(site.site_id) || site.name);
      card.append(header, heading);
      const rows = popupSiteRows(line, site.site_id);
      if (isHub) {
        const roles = popupNode("ol", "nodo8-popup-hub-roles");
        rows.forEach((row) => roles.append(popupNode("li", "", row.label)));
        card.append(roles);
      } else {
        const table = popupNode("table", "nodo8-popup-times");
        const caption = popupNode("caption", "", "Tempi nominali sul bus");
        const head = document.createElement("thead");
        const headings = document.createElement("tr");
        ["Nel giro", "Da FS", "Verso FS"].forEach((label) => {
          const cell = popupNode("th", "", label);
          cell.scope = "col";
          headings.append(cell);
        });
        head.append(headings);
        const body = document.createElement("tbody");
        rows.forEach((row, index) => {
          const record = document.createElement("tr");
          const label = document.createElement("th");
          label.scope = "row";
          label.append(popupNode("span", "nodo8-popup-ordinal", String(row.ordinal).padStart(2, "0")));
          if (rows.length > 1)
            label.append(popupNode("small", "", index === 0 ? "Prima volta" : "Ritorno"));
          record.append(label, popupNode("td", "", row.fromFs), popupNode("td", "", row.toFs));
          body.append(record);
        });
        table.append(caption, head, body);
        card.append(table);
      }
      card.append(popupNode("p", "nodo8-popup-authority", "Fermata di progetto, da verificare."));
      const times = popupNode("a", "nodo8-stop-link", "Orari della fermata →");
      times.href = stopLink(site.site_id, "../");
      card.append(times);
      card.append(popupDetails(isHub ? "I tre momenti in stazione" : "Come leggere i tempi", isHub
        ? "Partenza, sosta intermedia e arrivo appartengono allo stesso giro. La permanenza a bordo è prevista dal progetto; la continuità fisica del mezzo e dei passeggeri non è certificata."
        : "FS è la stazione di Olgiate: partenza precedente e arrivo successivo di quel passaggio. Tempi a bordo, esclusi cammino e attesa. Passaggi diversi della stessa fermata non sono intercambiabili."));
      openPopup(card, site.coordinates_lon_lat);
      return true;
    };
    const showRoute = (lngLat) => {
      const card = popupNode("div", "nodo8-popup-card");
      card.append(popupNode("span", "nodo8-popup-eyebrow", "Nodo8 · proposta"),
        popupNode("h3", "", "Un percorso a otto"));
      const metrics = popupNode("dl", "nodo8-popup-metrics");
      const distance = popupNode("div", "");
      distance.append(popupNode("dt", "", "Percorso completo"),
        popupNode("dd", "", (data.complete_path_distance_m / 1000).toLocaleString("it-IT", { maximumFractionDigits: 3 }) + " km"));
      const trips = popupNode("div", "");
      trips.append(popupNode("dt", "", "Giorno di progetto"), popupNode("dd", "", data.trips.length + " giri"));
      metrics.append(distance, trips);
      card.append(metrics, popupDetails("Base di progetto",
        "Stesso percorso e stesso mezzo di modello per tutta la corsa. La geometria è di progetto e non costituisce autorizzazione stradale."));
      openPopup(card, lngLat);
    };
    const markers = new Map();
    const focusBus = (id, state) => {
      if (!state?.coordinates || !contextVisible("explore")) return;
      explorerPlayer?.focusVehicle(id);
      map.flyTo({center:state.coordinates,zoom:Math.max(map.getZoom(),13.2),
        padding:innerWidth < 800 ? {top:85,right:25,bottom:Math.min(innerHeight*0.5,360),left:25} : {top:90,right:460,bottom:80,left:45},
        duration:window.__analysisJourneyReduceMotion ? 0 : 550});
    };
    const paintBuses = ({ states, followedTrip }) => {
      states.forEach((s) => {
        const visible =
          s.coordinates && (!followedTrip || s.trip === followedTrip);
        if (!markers.has(s.id)) {
          const icon = makeBusMarker(s.id);
          icon.tabIndex = 0;
          icon.setAttribute("role", "button");
          const selectBus = () => focusBus(s.id,markers.get(s.id)?.state);
          icon.addEventListener("click",selectBus);
          icon.addEventListener("keydown",event => {
            if (!["Enter"," "].includes(event.key)) return;
            event.preventDefault();
            selectBus();
          });
          const marker = new window.maplibregl.Marker({
            element: icon,
            anchor: "center",
          });
          markers.set(s.id, { marker, icon, added: false });
        }
        const entry = markers.get(s.id),
          { marker, icon } = entry;
        entry.state = s;
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
    const mountExplorerPlayer = () => {
      const host = document.getElementById("explorePlayback");
      if (!host || explorerPlayer) return;
      explorerPlayer = mountPlayer(
        host,
        line,
        (state) => {
          window.__analysisJourneyExplore?.updateClock(state);
          if (contextVisible("explore")) paintBuses(state);
          rail?.render({minute: state.minute, visible: railVisible()});
          current?.render({minute:state.minute,visible:currentVisible(),selection:document.querySelector("#currentRouteChoice")?.value || "ALL",
            showStops:window.__analysisJourneyExplore?.layers.stops !== false});
        },
        {
          compact: true,
          brief: true,
          overviewOnly: true,
          initialSelection: "all",
          initialMinute: 455,
          visibilityTarget: document.getElementById("map"),
          onVehicleFocus: focusBus,
        },
      );
      document.documentElement.dataset.nodo8ExplorerPlaybackReady = "true";
    };
    const renderScene = () => {
      const scene = document.body.dataset.scene;
      mountExplorerPlayer();
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
      toggleExplorer: () => explorerPlayer?.toggle(),
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
      // Honour the landing anchor after asynchronous setup, unless the reader
      // has already acted.
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
    console.error("Nodo8 journey overlay unavailable", error);
  }
}

if (typeof window !== "undefined") installNodo8();
