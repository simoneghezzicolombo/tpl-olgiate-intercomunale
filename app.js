/* Nodo8 showcase. Presentation only: no routing, ranking or timetable synthesis. */
"use strict";
import { buildLine } from "./nodo8-line.mjs";
import {
  mountPlayer,
  renderDiagram,
  makeBusMarker,
  updateBusMarker,
} from "./nodo8-experience.mjs";
const formatNumber = (value, decimals = 2) =>
  new Intl.NumberFormat("it-IT", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
const clock = (minutes) => {
  const whole = Math.floor(minutes + 1e-8);
  return (
    String(Math.floor(whole / 60)).padStart(2, "0") +
    ":" +
    String(whole % 60).padStart(2, "0")
  );
};
const element = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
function initScroll() {
  const progress = document.getElementById("scrollProgress");
  let queued = false;
  const update = () => {
    const distance = document.documentElement.scrollHeight - window.innerHeight;
    progress.style.width =
      (distance > 0
        ? Math.min(100, Math.max(0, (window.scrollY / distance) * 100))
        : 0) + "%";
    queued = false;
  };
  const queue = () => {
    if (!queued) {
      queued = true;
      requestAnimationFrame(update);
    }
  };
  window.addEventListener("scroll", queue, { passive: true });
  window.addEventListener("resize", queue);
  update();
  if ("IntersectionObserver" in window) {
    const nav = [...document.querySelectorAll(".site-header nav a")].filter(
      (link) => link.hash,
    );
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          nav.forEach((link) => {
            if (link.hash === "#" + entry.target.id)
              link.setAttribute("aria-current", "location");
            else link.removeAttribute("aria-current");
          });
        }
      },
      { rootMargin: "-15% 0px -55% 0px" },
    );
    nav.forEach((link) => {
      const section = document.querySelector(link.hash);
      if (section) observer.observe(section);
    });
  }
}
function renderTimetable(data) {
  const filter = document.getElementById("scheduleFilter").value;
  const rows = data.trips.filter(
    (trip) =>
      filter === "all" ||
      (filter === "peak" ? trip.peak_bank : !trip.peak_bank),
  );
  const body = document.getElementById("timetableBody");
  body.replaceChildren();
  rows.forEach((trip) => {
    const row = element("tr", trip.peak_bank ? "peak-row" : "");
    [
      String(trip.number).padStart(2, "0"),
      clock(trip.first_fs_min),
      clock(trip.second_fs_min),
      clock(trip.return_fs_min),
    ].forEach((value) => row.append(element("td", "", value)));
    body.append(row);
  });
  document.getElementById("scheduleCount").textContent =
    rows.length + " giri completi";
}
function renderCoverage(data) {
  const time = document.getElementById("coverageTime").value;
  const total = document.getElementById("totalCoverage");
  total.replaceChildren(
    document.createTextNode(formatNumber(data.coverage.TOTAL[time])),
    element("span", "", "%"),
  );
  total.nextElementSibling.textContent =
    "copertura pedonale potenziale del bacino entro " +
    time +
    " minuti da un sito di progetto.";
  const bars = document.getElementById("coverageBars");
  bars.replaceChildren();
  data.municipalities.forEach((municipality) => {
    const value = data.coverage[municipality.code][time];
    const row = element("div", "coverage-row"),
      label = element("div");
    label.append(
      element("span", "", municipality.name),
      element("span", "", formatNumber(value) + "%"),
    );
    const track = element("div", "coverage-track");
    track.setAttribute("aria-hidden", "true");
    const fill = element("span");
    fill.style.width = value + "%";
    track.append(fill);
    row.append(label, track);
    bars.append(row);
  });
}
function showSite(site) {
  document.querySelectorAll(".stop-list button").forEach((button) => {
    const selected = button.dataset.site === site.site_id;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  const detail = document.getElementById("stopDetail");
  detail.replaceChildren(
    element("h3", "", site.name),
    element(
      "p",
      "",
      site.proposed_new_site
        ? "Nuovo sito proposto. Posizione di progetto, non fermata autorizzata."
        : "Sito derivato dall’inventario. Accosto e lato per questo servizio restano da validare.",
    ),
  );
  if (site.hub_service_roles.length) {
    detail.append(
      element(
        "p",
        "",
        "FS è partenza, fermata intermedia e arrivo dello stesso giro. La permanenza a bordo è progettata, non ancora autorizzata.",
      ),
    );
  } else {
    const cards = element("div", "event-cards");
    site.ordered_occurrences.forEach((occurrence) => {
      const card = element("div", "event-card");
      card.append(
        element(
          "strong",
          "",
          "Nodo8 · evento " + occurrence.ordered_nonhub_event_number,
        ),
      );
      card.append(
        element(
          "p",
          "",
          "Dall’ultima FS → questo evento: " +
            formatNumber(
              occurrence.nominal_fs_to_occurrence_in_vehicle_min,
              1,
            ) +
            " min. Da qui alla prossima FS: " +
            formatNumber(
              occurrence.nominal_occurrence_to_next_fs_in_vehicle_min,
              1,
            ) +
            " min.",
        ),
      );
      cards.append(card);
    });
    detail.append(
      cards,
      element(
        "p",
        "",
        "Tempi nominali a bordo, esclusi cammino e attesa iniziale. Eventi diversi dello stesso sito non si combinano in un viaggio garantito.",
      ),
    );
  }
}
/* Offline/CDN fallback projects the exact confirmed LineStrings, never schematic routes. */
function renderFallbackMap(data, onSelect) {
  const ns = "http://www.w3.org/2000/svg";
  const svgNode = (tag, attributes) => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attributes).forEach(([key, value]) =>
      node.setAttribute(key, value),
    );
    return node;
  };
  const svg = svgNode("svg", {
    viewBox: "0 0 760 480",
    class: "fallback-map",
    role: "group",
    "aria-label": "Tracciato geografico di progetto, senza sfondo cartografico",
  });
  const all = data.routes.flatMap((route) => route.coordinates);
  const lat = all.reduce((sum, point) => sum + point[1], 0) / all.length,
    factor = Math.cos((lat * Math.PI) / 180);
  const xs = all.map((point) => point[0] * factor),
    ys = all.map((point) => point[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs),
    minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const scale = Math.min(680 / (maxX - minX), 380 / (maxY - minY));
  const project = (point) => [
    380 + (point[0] * factor - (minX + maxX) / 2) * scale,
    240 - (point[1] - (minY + maxY) / 2) * scale,
  ];
  data.routes.forEach((route) => {
    const path = route.coordinates
      .map(project)
      .map(
        (point, index) =>
          (index ? "L" : "M") + point[0].toFixed(2) + "," + point[1].toFixed(2),
      )
      .join(" ");
    svg.append(
      svgNode("path", {
        d: path,
        fill: "none",
        stroke: "#163d33",
        "stroke-width": 3,
        "stroke-linejoin": "round",
      }),
    );
  });
  data.sites.forEach((site) => {
    const [x, y] = project(site.coordinates_lon_lat);
    const circle = svgNode("circle", {
      cx: x,
      cy: y,
      r: site.hub_service_roles.length ? 7 : 4,
      fill: site.proposed_new_site ? "#e77652" : "#fffdf8",
      stroke: "#163d33",
      "stroke-width": 1.5,
      tabindex: 0,
      role: "button",
      "aria-label": site.name,
    });
    const title = svgNode("title", {});
    title.textContent = site.name;
    circle.append(title);
    circle.addEventListener("click", () => onSelect(site));
    circle.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onSelect(site);
      }
    });
    svg.append(circle);
  });
  const north = svgNode("text", { x: 710, y: 30 });
  north.textContent = "↑ N";
  svg.append(north);
  document
    .getElementById("routeMap")
    .replaceChildren(
      svg,
      element(
        "p",
        "fallback-notice",
        "Geometria reale · sfondo cartografico non disponibile",
      ),
    );
  const buses = new Map();
  return {
    focus: onSelect,
    reset: () => {},
    updateBuses: ({ states, followedTrip }) => {
      states.forEach((s) => {
        let g = buses.get(s.id);
        if (!g) {
          g = svgNode("g", {});
          const icon = makeBusMarker(s.id);
          g.append(icon.querySelector("svg"));
          svg.append(g);
          buses.set(s.id, g);
        }
        g.style.display =
          s.coordinates && (!followedTrip || s.trip === followedTrip)
            ? ""
            : "none";
        if (s.coordinates) {
          const [x, y] = project(s.coordinates);
          g.setAttribute("transform", `translate(${x - 17} ${y - 21})`);
        }
        g.setAttribute("class", "n8-bus");
        updateBusMarker(g, s);
      });
    },
  };
}
function createMap(data) {
  if (!window.L) return renderFallbackMap(data, showSite);
  const container = document.getElementById("routeMap");
  container.replaceChildren();
  const map = L.map(container, { scrollWheelZoom: false, tap: false });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  const lines = data.routes.map((route) =>
    L.polyline(
      route.coordinates.map(([lon, lat]) => [lat, lon]),
      {
        color: "#163d33",
        weight: 4,
        opacity: 0.95,
      },
    ).addTo(map),
  );
  const bounds = L.featureGroup(lines).getBounds(),
    markers = new Map();
  data.sites.forEach((site) => {
    const marker = L.circleMarker(
      [site.coordinates_lon_lat[1], site.coordinates_lon_lat[0]],
      {
        radius: site.hub_service_roles.length ? 9 : 5,
        color: "#163d33",
        weight: 2,
        fillColor: site.proposed_new_site ? "#e77652" : "#fffdf8",
        fillOpacity: 1,
      },
    ).addTo(map);
    const popup = element("div");
    popup.append(
      element("strong", "", site.name),
      element(
        "p",
        "",
        site.proposed_new_site
          ? "Nuovo sito proposto · accosto da approvare"
          : "Sito da inventario · accosto da validare",
      ),
    );
    marker.bindPopup(popup);
    marker.on("click", () => showSite(site));
    markers.set(site.site_id, marker);
  });
  const reset = () =>
    map.fitBounds(bounds, { padding: [25, 25], animate: false });
  reset();
  const busMarkers = new Map();
  if ("ResizeObserver" in window)
    new ResizeObserver(() => {
      map.invalidateSize();
      reset();
    }).observe(container);
  return {
    reset,
    updateBuses: ({ states, followedTrip }) => {
      states.forEach((s) => {
        if (!busMarkers.has(s.id)) {
          const icon = makeBusMarker(s.id);
          const marker = L.marker([0, 0], {
            icon: L.divIcon({
              html: icon,
              className: "n8-bus-icon",
              iconSize: [34, 42],
              iconAnchor: [17, 21],
            }),
            keyboard: false,
            zIndexOffset: 1000,
          });
          busMarkers.set(s.id, { marker, icon });
        }
        const { marker, icon } = busMarkers.get(s.id);
        const visible =
          s.coordinates && (!followedTrip || s.trip === followedTrip);
        if (visible) {
          marker.setLatLng([s.coordinates[1], s.coordinates[0]]);
          if (!map.hasLayer(marker)) marker.addTo(map);
          updateBusMarker(icon, s);
          icon.classList.toggle("is-followed", followedTrip === s.trip);
        } else if (map.hasLayer(marker)) map.removeLayer(marker);
      });
    },
    focus: (site) => {
      showSite(site);
      const marker = markers.get(site.site_id);
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 15), {
        animate: false,
      });
      marker.openPopup();
    },
  };
}
function renderStops(data, map) {
  const filter = document.querySelector('[data-stops][aria-pressed="true"]')
    .dataset.stops;
  const sites = data.sites.filter(
    (site) => filter === "all" || site.proposed_new_site,
  );
  const list = document.getElementById("stopList");
  list.replaceChildren();
  sites.forEach((site) => {
    const item = element("li"),
      button = element("button");
    button.type = "button";
    button.dataset.site = site.site_id;
    button.setAttribute("aria-pressed", "false");
    button.append(
      element(
        "span",
        "stop-index",
        String(data.sites.indexOf(site) + 1).padStart(2, "0"),
      ),
      element("span", "stop-name", site.name),
    );
    if (site.proposed_new_site)
      button.append(element("span", "new-tag", "NUOVO"));
    button.addEventListener("click", () => map.focus(site));
    item.append(button);
    list.append(item);
  });
}
function validatePresentationData(data) {
  if (
    data.contract !== "nodo8_showcase_v1" ||
    data.sites.length !== 27 ||
    data.trips.length !== 16 ||
    data.routes.length !== 2 ||
    data.authority.public_operating_timetable_authorised !== false ||
    data.authority.primary_selection_authorised !== false ||
    data.authority.runner_up_selection_authorised !== false ||
    data.calendar.service_year !== 2027
  ) {
    throw new Error(
      "Dati della vetrina non coerenti con il contratto di presentazione",
    );
  }
}
async function initProposal() {
  try {
    const response = await fetch("assets/nodo8-proposal.json");
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    validatePresentationData(data);
    renderTimetable(data);
    renderCoverage(data);
    const map = createMap(data);
    renderStops(data, map);
    const line = buildLine(data);
    mountPlayer(
      document.getElementById("routePlayback"),
      line,
      (state) => {
        map.updateBuses(state);
        document.getElementById("mapPlaybackClock").textContent =
          document.querySelector("#routePlayback .n8-clock").textContent;
        const play = document.getElementById("mapPlaybackPlay");
        play.textContent = state.playing ? "Ⅱ Pausa" : "▶ Riproduci";
        play.setAttribute("aria-pressed", String(state.playing));
      },
      {
        compact: true,
        visibilityTarget: document.querySelector(".route-explorer"),
      },
    );
    document
      .getElementById("mapPlaybackPlay")
      .addEventListener("click", () =>
        document.querySelector("#routePlayback .n8-play").click(),
      );
    document
      .getElementById("mapPlaybackStop")
      .addEventListener("click", () =>
        document
          .querySelector("#routePlayback .n8-presets button:nth-child(2)")
          .click(),
      );
    renderDiagram(document.getElementById("stopsDiagram"), line, {
      onSelect: (site) => {
        document
          .getElementById("percorso")
          .scrollIntoView({ behavior: "instant", block: "start" });
        map.focus(site);
      },
    });
    renderDiagram(document.getElementById("localitiesDiagram"), line, {
      localities: true,
    });
    const tabs = [...document.querySelectorAll('.diagram-tabs [role="tab"]')];
    const selectTab = (tab) =>
      tabs.forEach((t) => {
        const active = t === tab;
        t.setAttribute("aria-selected", String(active));
        t.tabIndex = active ? 0 : -1;
        document.getElementById(t.getAttribute("aria-controls")).hidden =
          !active;
      });
    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => selectTab(tab));
      tab.addEventListener("keydown", (e) => {
        if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
          e.preventDefault();
          const next =
            tabs[
              e.key === "Home"
                ? 0
                : e.key === "End"
                  ? tabs.length - 1
                  : (i + 1) % tabs.length
            ];
          selectTab(next);
          next.focus();
        }
      });
    });
    document.getElementById("resetMap").addEventListener("click", map.reset);
    document
      .getElementById("scheduleFilter")
      .addEventListener("change", () => renderTimetable(data));
    document
      .getElementById("coverageTime")
      .addEventListener("change", () => renderCoverage(data));
    document.querySelectorAll("[data-stops]").forEach((button) =>
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-stops]").forEach((other) => {
          const active = button === other;
          other.classList.toggle("active", active);
          other.setAttribute("aria-pressed", String(active));
        });
        renderStops(data, map);
      }),
    );
  } catch (error) {
    console.error("Nodo8: caricamento non completato", error);
    document
      .getElementById("routeMap")
      .replaceChildren(
        element(
          "p",
          "map-loading",
          "Dati interattivi non disponibili. Consulta la proposta e il GeoJSON nei collegamenti sotto.",
        ),
      );
    document
      .getElementById("stopList")
      .replaceChildren(
        element(
          "li",
          "",
          "Elenco non caricato: non vengono generate fermate sostitutive.",
        ),
      );
    const cell = element(
      "td",
      "",
      "Orario non caricato. Usa il documento della proposta completa.",
    );
    cell.colSpan = 4;
    const row = element("tr");
    row.append(cell);
    document.getElementById("timetableBody").replaceChildren(row);
    document
      .getElementById("coverageBars")
      .replaceChildren(
        element(
          "p",
          "",
          "Dati interattivi non caricati; nessuna stima sostitutiva.",
        ),
      );
    document
      .querySelectorAll(
        "#coverageTime, #scheduleFilter, #resetMap, [data-stops], .diagram-tabs button, .map-playback-bar button",
      )
      .forEach((control) => {
        control.disabled = true;
      });
    ["routePlayback", "stopsDiagram", "localitiesDiagram"].forEach((id) => {
      document
        .getElementById(id)
        .replaceChildren(
          element(
            "p",
            "notice",
            "Visualizzazione non disponibile: nessuna sequenza o simulazione sostitutiva viene inventata.",
          ),
        );
    });
  }
}
initScroll();
initProposal();
