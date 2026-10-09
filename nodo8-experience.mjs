import { diagramStops } from "./nodo8-line.mjs?v=20261008n";
const ns = "http://www.w3.org/2000/svg";
const displayText = (value) => String(value).replace(/\u2014/g, ", ");
const node = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = displayText(text);
  return e;
};
const svg = (tag, attributes = {}, text) => {
  const e = document.createElementNS(ns, tag);
  for (const [k, v] of Object.entries(attributes))
    e.setAttribute(k, k.startsWith("aria-") ? displayText(v) : v);
  if (text !== undefined) e.textContent = displayText(text);
  return e;
};
export function makeBusMarker(id) {
  const e = node("div", "n8-bus");
  e.dataset.vehicle = id;
  const icon = svg("svg", {
    viewBox: "0 0 34 42",
    width: 34,
    height: 42,
    "aria-hidden": "true",
  });
  icon.append(
    svg("rect", { x: 1, y: 11, width: 4, height: 7, rx: 1.5, fill: "#153d34" }),
    svg("rect", {
      x: 29,
      y: 11,
      width: 4,
      height: 7,
      rx: 1.5,
      fill: "#153d34",
    }),
    svg("rect", {
      x: 4,
      y: 2,
      width: 26,
      height: 34,
      rx: 7,
      class: "n8-bus-body",
    }),
    svg("rect", { x: 8, y: 7, width: 18, height: 10, rx: 2, fill: "#f5f2e9" }),
    svg("path", { d: "M9 15 L23 9", stroke: "#b7cbc1", "stroke-width": 1.5 }),
    svg(
      "text",
      {
        x: 17,
        y: 29,
        "text-anchor": "middle",
        fill: "white",
        "font-size": 11,
        "font-weight": 800,
      },
      "8",
    ),
    svg("circle", { cx: 10, cy: 33, r: 2, fill: "#ffe4a4" }),
    svg("circle", { cx: 24, cy: 33, r: 2, fill: "#ffe4a4" }),
    svg("rect", { x: 7, y: 35, width: 5, height: 5, rx: 2, fill: "#183b32" }),
    svg("rect", { x: 22, y: 35, width: 5, height: 5, rx: 2, fill: "#183b32" }),
  );
  e.append(icon);
  const carrier = node("span", "n8-bus-carrier", id);
  e.append(carrier);
  return e;
}
export function updateBusMarker(element, state, { showCarrier = false } = {}) {
  element.dataset.status = state.status;
  element.classList.toggle("show-carrier", showCarrier);
  element.title =
    state.id +
    " · " +
    (state.trip ? "giro " + state.trip + " · " : "") +
    displayText(state.label);
  element.setAttribute("aria-label", element.title);
}

export { mountPlayer } from "./nodo8-player.mjs?v=20261008n";

export function mountRoadPreview(line) {
  const host = node("div", "n8-road-preview"),
    drawing = svg("svg", {
      viewBox: "0 0 600 340",
      role: "img",
      "aria-label":
        "Tracciato stradale reale della proposta, senza sfondo cartografico",
    });
  const points = line.coordinates,
    lat = points.reduce((s, p) => s + p[1], 0) / points.length,
    factor = Math.cos((lat * Math.PI) / 180);
  const xs = points.map((p) => p[0] * factor),
    ys = points.map((p) => p[1]),
    cx = (Math.min(...xs) + Math.max(...xs)) / 2,
    cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const scale = Math.min(
    540 / (Math.max(...xs) - Math.min(...xs)),
    280 / (Math.max(...ys) - Math.min(...ys)),
  );
  const project = (p) => [
    300 + (p[0] * factor - cx) * scale,
    170 - (p[1] - cy) * scale,
  ];
  drawing.append(
    svg("rect", {
      x: 0,
      y: 0,
      width: 600,
      height: 340,
      class: "n8-diagram-paper",
    }),
    svg("path", {
      d: points
        .map((p, i) => {
          const [x, y] = project(p);
          return `${i ? "L" : "M"}${x} ${y}`;
        })
        .join(" "),
      class: "n8-road-line",
    }),
  );
  line.sites.forEach((s) => {
    const [x, y] = project(s.coordinates_lon_lat);
    drawing.append(
      svg("circle", {
        cx: x,
        cy: y,
        r: s.hub_service_roles.length ? 6 : 3,
        class: s.proposed_new_site ? "n8-road-new" : "n8-road-stop",
      }),
    );
  });
  const hub = [...line.sites.values()].find((s) => s.hub_service_roles.length);
  const [hx, hy] = project(hub.coordinates_lon_lat);
  const hubLabel = svg("g", {
    class: "n8-road-hub-label",
    transform: `translate(${hx + 12} ${hy - 33})`,
  });
  hubLabel.append(
    svg("rect", { width: 109, height: 28, rx: 9 }),
    svg("text", { x: 12, y: 19 }, "Olgiate FS"),
  );
  drawing.append(hubLabel);
  const buses = new Map(
    line.vehicles.map((v) => {
      const bus = svg("g", { class: "n8-road-bus", "data-vehicle": v.id });
      bus.style.display = "none";
      bus.append(
        svg("rect", { x: -13, y: -17, width: 26, height: 34, rx: 7 }),
        svg("text", { "text-anchor": "middle", y: 5 }, "8"),
      );
      drawing.append(bus);
      return [v.id, bus];
    }),
  );
  host.append(
    drawing,
    node(
      "p",
      "n8-road-caption",
      "Tracciato stradale di progetto · senza basemap · non GPS",
    ),
  );
  return {
    node: host,
    update: ({ states, followedTrip }) =>
      states.forEach((s) => {
        const bus = buses.get(s.id),
          visible = s.coordinates && (!followedTrip || s.trip === followedTrip);
        bus.style.display = visible ? "" : "none";
        if (visible) {
          const [x, y] = project(s.coordinates);
          bus.setAttribute("transform", `translate(${x} ${y})`);
          bus.dataset.status = s.status;
        }
      }),
  };
}

function wrapLabel(value, maxLength = 23) {
  if (value.includes(" / ")) return value.split(" / ");
  if (value.length <= maxLength) return [value];
  const words = value.split(" ");
  let a = "",
    b = "";
  words.forEach((w) => {
    if (!b && (a + " " + w).trim().length <= maxLength)
      a = (a + " " + w).trim();
    else b = (b + " " + w).trim();
  });
  return [a, b];
}

const circlePoint = (cx, cy, radius, degrees) => {
  const angle = (degrees * Math.PI) / 180;
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
};

function appendCircle(drawing, cx, cy, radius, attributes = {}) {
  drawing.append(
    svg("circle", { cx, cy, r: radius, class: "n8-diagram-shadow" }),
    svg("circle", {
      cx,
      cy,
      r: radius,
      class: "n8-diagram-line",
      ...attributes,
    }),
  );
}

function appendArrow(drawing, cx, cy, radius, degrees, clockwise = false) {
  const { x, y } = circlePoint(cx, cy, radius, degrees);
  drawing.append(
    svg("path", {
      d: "M-8 -7 L2 0 L-8 7",
      transform: `translate(${x} ${y}) rotate(${degrees + (clockwise ? 90 : -90)})`,
      class: "n8-diagram-arrow",
      "data-direction": clockwise ? "clockwise" : "counterclockwise",
    }),
  );
}

export function renderDiagram(
  container,
  line,
  { localities = false, onSelect } = {},
) {
  if (localities) return renderLocalityDiagram(container, line);
  const entries = diagramStops(line),
    id = container.id;
  const drawing = svg("svg", {
    viewBox: "0 0 1200 1760",
    class: "n8-diagram n8-diagram--stops",
    role: onSelect ? "group" : "img",
    "aria-labelledby": id + "-title " + id + "-description",
  });
  drawing.append(
    svg("rect", {
      x: 0,
      y: 0,
      width: 1200,
      height: 1760,
      class: "n8-diagram-paper",
    }),
    svg(
      "title",
      { id: id + "-title" },
      "Nodo8 · tutte le fermate in due anelli circolari",
    ),
    svg(
      "desc",
      { id: id + "-description" },
      "Un'unica linea a otto. Partenza, sosta intermedia e arrivo a Olgiate FS. " +
        entries.map((e) => e.display).join(" → ") +
        ". Schema non geografico; nessuna autorizzazione fisica delle fermate.",
    ),
  );
  drawing.append(
    svg("text", { x: 72, y: 47, class: "n8-diagram-brand" }, "nodo8"),
    svg(
      "text",
      { x: 1128, y: 43, "text-anchor": "end", class: "n8-diagram-caption" },
      "UN GIRO COMPLETO · 27 FERMATE · UN’UNICA LINEA",
    ),
  );
  const placed = [];
  [true, false].forEach((upper) => {
    const part = entries.filter((e) => e.ordinal <= 14 === upper),
      cy = upper ? 460 : 1320;
    appendCircle(drawing, 600, cy, 360, {
      "data-loop": upper ? "first" : "second",
    });
    // Merge only the repeated physical site at this loop's station-side end.
    // Its two distinct passenger events stay in the ledger and ordered list.
    const first = part[0], last = part.at(-1);
    if (first.siteId !== last.siteId)
      throw new Error("The station-side shared stop must have the same site identity");
    placed.push({
      ...first,
      ordinals: [first.ordinal, last.ordinal],
      occurrenceIds: [first.occurrenceId, last.occurrenceId],
      x: 600, y: upper ? 820 : 960, shared: true, upper,
    });
    part.slice(1, -1).forEach((e, i) => {
      const right = i < 6,
        j = right ? i : i - 6,
        degrees = upper
          ? right
            ? 55 - (110 * j) / 5
            : -125 - (110 * j) / 5
          : right
            ? -55 + (110 * j) / 5
            : 125 + (110 * j) / 5;
      placed.push({ ...e, ...circlePoint(600, cy, 360, degrees), right });
    });
    [-90, 0, 180].forEach((angle) =>
      appendArrow(drawing, 600, cy, 360, angle, !upper),
    );
  });
  drawing.append(
    svg("path", {
      d: "M600 820 V840 M600 940 V960",
      class: "n8-diagram-line n8-diagram-connector",
    }),
  );
  placed.forEach((e) => {
    const isNew = line.sites.get(e.siteId).proposed_new_site;
    const g = svg("g", {
      class: "n8-diagram-stop" + (e.shared ? " n8-diagram-stop--shared" : ""),
      "data-occurrence": e.occurrenceId,
      "data-occurrences": (e.occurrenceIds || [e.occurrenceId]).join(" "),
      "data-site": e.siteId,
      "data-ordinals": e.ordinals.join(" "),
    });
    if (onSelect) {
      g.setAttribute("tabindex", "0");
      g.setAttribute("role", "button");
      g.setAttribute(
        "aria-label",
        "Fermata " +
          e.ordinals.join(" e ") +
          ": " +
          displayText(e.display) +
          (isNew ? ", nuova fermata proposta" : ""),
      );
      g.addEventListener("click", () => onSelect(line.sites.get(e.siteId)));
      g.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          onSelect(line.sites.get(e.siteId));
        }
      });
    }
    const labelX = e.shared ? e.x : e.x + (e.right ? -32 : 32),
      textAnchor = e.shared ? "middle" : e.right ? "end" : "start",
      labelLines = wrapLabel(e.display),
      labelY = e.shared
        ? e.y + (e.upper ? -65 : 45)
        : e.y + 6 - (labelLines.length - 1) * 10;
    g.append(
      svg(
        "title",
        {},
        e.display + " · " + e.ordinals.map((o) => "fermata " + o).join(", "),
      ),
      svg("line", {
        x1: e.x,
        y1: e.y,
        x2: e.shared ? e.x : labelX + (e.right ? 5 : -5),
        y2: e.shared ? e.y + (e.upper ? -28 : 28) : e.y,
        class: "n8-diagram-leader",
      }),
      svg("circle", {
        cx: e.x,
        cy: e.y,
        r: e.shared ? 24 : 17,
        class: isNew ? "n8-diagram-new" : "n8-diagram-dot",
      }),
    );
    g.append(
      svg(
        "text",
        {
          x: e.x,
          y: e.y + 5,
          "text-anchor": "middle",
          class: "n8-diagram-number",
        },
        e.ordinals.join("·"),
      ),
    );
    const text = svg("text", {
      x: labelX,
      y: labelY,
      "text-anchor": textAnchor,
      class: "n8-diagram-name",
    });
    labelLines.forEach((t, i) =>
      text.append(svg("tspan", { x: labelX, dy: i ? 20 : 0 }, t)),
    );
    g.append(text);
    const note = e.shared ? "Nuova · due volte nel giro" : isNew ? "Nuova proposta" : "";
    if (note)
      g.append(
        svg(
          "text",
          {
            x: e.shared ? labelX : labelX + (e.right ? -32 : 32),
            y: labelY + (labelLines.length - 1) * 20 + 18,
            "text-anchor": textAnchor,
            class: "n8-diagram-sub",
          },
          note,
        ),
      );
    drawing.append(g);
  });
  drawing.append(
    svg(
      "text",
      {
        x: 600,
        y: 448,
        "text-anchor": "middle",
        class: "n8-diagram-loop-title",
      },
      "VERSO BRIVIO E CALCO",
    ),
    svg(
      "text",
      {
        x: 600,
        y: 475,
        "text-anchor": "middle",
        class: "n8-diagram-loop-note",
      },
      "Primo anello · stessa linea",
    ),
    svg(
      "text",
      {
        x: 600,
        y: 1308,
        "text-anchor": "middle",
        class: "n8-diagram-loop-title",
      },
      "VERSO LA VALLETTA E SANTA MARIA",
    ),
    svg(
      "text",
      {
        x: 600,
        y: 1335,
        "text-anchor": "middle",
        class: "n8-diagram-loop-note",
      },
      "Secondo anello · stessa linea",
    ),
    svg("rect", {
      x: 410,
      y: 840,
      width: 380,
      height: 100,
      rx: 24,
      class: "n8-diagram-hub",
    }),
    svg(
      "text",
      { x: 600, y: 876, "text-anchor": "middle", class: "n8-diagram-hub-name" },
      "Olgiate FS",
    ),
    svg(
      "text",
      { x: 600, y: 903, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
      "Si parte, si torna e si prosegue da qui.",
    ),
    svg(
      "text",
      { x: 600, y: 922, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
      "Prosecuzione a bordo da autorizzare",
    ),
  );
  drawing.append(
    svg(
      "text",
      { x: 600, y: 1715, "text-anchor": "middle", class: "n8-diagram-caption" },
      "27 fermate · San Zeno e Olgiate sud si incontrano due volte",
    ),
    svg(
      "text",
      { x: 600, y: 1740, "text-anchor": "middle", class: "n8-diagram-caption" },
      "Schema non geografico · ordine di servizio, non tempi o distanze",
    ),
  );
  finishDiagram(container, drawing, line, { onSelect, localities: false });
}

function finishDiagram(container, drawing, line, { onSelect, localities }) {
  const scroll = node("div", "n8-diagram-scroll");
  scroll.tabIndex = 0;
  scroll.setAttribute(
    "aria-label",
    "Schema della linea, con ingrandimento disponibile",
  );
  scroll.append(drawing);
  const download = node(
    "button",
    "n8-diagram-download",
    "Scarica questo schema in SVG ↓",
  );
  download.type = "button";
  download.addEventListener("click", async () => {
    download.disabled = true;
    try {
      const response = await fetch(
        new URL("./nodo8-experience.css?v=20261008n", import.meta.url),
      );
      if (!response.ok) throw new Error("Diagram styles unavailable");
      const copy = drawing.cloneNode(true),
        style = svg("style", {}, await response.text());
      copy.insertBefore(style, copy.firstChild);
      copy.setAttribute("xmlns", ns);
      const [, , width, height] = drawing.getAttribute("viewBox").split(" ");
      copy.setAttribute("width", width);
      copy.setAttribute("height", height);
      copy.querySelectorAll("[role=button]").forEach((e) => {
        e.removeAttribute("role");
        e.removeAttribute("tabindex");
      });
      copy.setAttribute("role", "img");
      const blob = new Blob([new XMLSerializer().serializeToString(copy)], {
        type: "image/svg+xml;charset=utf-8",
      });
      const url = URL.createObjectURL(blob),
        a = node("a");
      a.href = url;
      a.download = localities ? "nodo8-localita.svg" : "nodo8-fermate.svg";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (error) {
      download.textContent = "Download non disponibile · riprova";
      console.error("Nodo8 diagram export unavailable", error);
    } finally {
      download.disabled = false;
    }
  });
  const tools = node("div", "n8-diagram-tools");
  const legend = node("div", "n8-diagram-legend"),
    regular = node("span", "", "Fermata di progetto"),
    proposed = node("span", "is-new", "Nuova fermata proposta");
  regular.append(node("i"));
  proposed.append(node("i"));
  legend.append(regular, proposed);
  const zoom = node("button", "n8-diagram-download", "Ingrandisci lo schema");
  zoom.type = "button";
  zoom.setAttribute("aria-pressed", "false");
  zoom.addEventListener("click", () => {
    const enlarged = scroll.classList.toggle("is-zoomed");
    zoom.setAttribute("aria-pressed", String(enlarged));
    zoom.textContent = enlarged ? "Vista completa" : "Ingrandisci lo schema";
  });
  tools.append(zoom, download);
  const order = node("details", "n8-diagram-order"),
    summary = node("summary", "", "Leggi le fermate nell’ordine del giro");
  order.append(summary);
  const list = node("ol", "n8-ordered-list");
  const entries = localities ? diagramStops(line, true) : line.trips[0].events;
  const addHub = (text) => {
    const item = node("li", "n8-order-hub", text);
    list.append(item);
  };
  if (localities) addHub("Olgiate FS · partenza");
  entries.forEach((e, i) => {
    if (localities && e.ordinal === 15)
      addHub("Olgiate FS · sosta e prosecuzione, stesso giro");
    const item = node("li");
    const label = localities
      ? `${i + 1}. ${e.display}`
      : e.ordinal
        ? `${e.ordinal}. ${diagramStops(line)[e.ordinal - 1].display}`
        : e.role === "FULL_TRIP_START_FS"
          ? "Olgiate FS · partenza"
          : e.role === "FULL_TRIP_END_FS"
            ? "Olgiate FS · arrivo"
            : "Olgiate FS · sosta e prosecuzione";
    if (!e.ordinal) item.className = "n8-order-hub";
    if (onSelect && e.ordinal) {
      const b = node("button", "", label);
      b.type = "button";
      b.addEventListener("click", () => onSelect(line.sites.get(e.siteId)));
      item.append(b);
    } else item.textContent = label;
    list.append(item);
  });
  if (localities) addHub("Olgiate FS · arrivo del giro completo");
  order.append(list);
  const narrow = window.matchMedia("(max-width:600px)");
  order.open = narrow.matches;
  narrow.addEventListener("change", (e) => {
    if (e.matches) order.open = true;
  });
  if (localities) container.replaceChildren(scroll, tools, order);
  else container.replaceChildren(legend, scroll, tools, order);
}

function renderLocalityDiagram(container, line) {
  const id = container.id;
  const drawing = svg("svg", {
    viewBox: "0 0 1200 1510",
    class: "n8-diagram n8-diagram--localities",
    role: "img",
    "aria-labelledby": id + "-title " + id + "-description",
  });
  drawing.append(
    svg("rect", {
      x: 0,
      y: 0,
      width: 1200,
      height: 1510,
      class: "n8-diagram-paper",
    }),
    svg(
      "title",
      { id: id + "-title" },
      "Nodo8 · schema concettuale delle località, due anelli e Olgiate FS",
    ),
    svg(
      "desc",
      { id: id + "-description" },
      "Olgiate FS al centro, un raccordo verso San Zeno e un raccordo verso " +
        "Canova / Beolco. Il cerchio superiore dispone Beverate, Vaccarezza, " +
        "Brivio, Arlate e Calco in senso antiorario. Il cerchio inferiore dispone " +
        "Monticello, Santa Maria Hoè, Perego e Rovagnate. Riferimenti territoriali, " +
        "non siti di fermata o copertura certificata. La disposizione concettuale " +
        "non sostituisce l'ordine effettivo delle fermate nel primo schema e nella sequenza.",
    ),
  );
  drawing.append(
    svg("text", { x: 62, y: 48, class: "n8-diagram-brand" }, "nodo8"),
  );
  appendCircle(drawing, 600, 350, 240, { "data-loop": "first" });
  appendCircle(drawing, 600, 1120, 240, { "data-loop": "second" });
  drawing.append(
    svg("path", {
      d: "M600 590 V692 M600 782 V880",
      class: "n8-diagram-line n8-diagram-connector",
    }),
  );
  const localities = [
    ["San Zeno", 350, 90],
    ["Beverate", 350, 30],
    ["Vaccarezza", 350, -30],
    ["Brivio", 350, -90],
    ["Arlate", 350, -150],
    ["Calco", 350, -210],
    ["Canova / Beolco", 1120, -90],
    ["Monticello", 1120, -30],
    ["Santa Maria Hoè", 1120, 30],
    ["Perego", 1120, 150],
    ["Rovagnate", 1120, 210],
  ];
  localities.forEach(([name, cy, degrees]) => {
    const point = circlePoint(600, cy, 240, degrees),
      lines =
        name === "Santa Maria Hoè"
          ? ["Santa Maria", "Hoè"]
          : name === "Canova / Beolco"
            ? ["Canova", "Beolco"]
            : wrapLabel(name),
      group = svg("g", {
        class: "n8-diagram-locality",
        "data-locality": name,
        "data-loop": cy === 350 ? "first" : "second",
      }),
      text = svg("text", {
        x: point.x,
        y: point.y + 9 - (lines.length - 1) * 16,
        "text-anchor": "middle",
        class: "n8-diagram-name n8-diagram-locality-name",
      });
    lines.forEach((value, index) =>
      text.append(svg("tspan", { x: point.x, dy: index ? 32 : 0 }, value)),
    );
    group.append(
      svg("title", {}, name + " · riferimento territoriale"),
      svg("circle", {
        cx: point.x,
        cy: point.y,
        r: 82,
        class: "n8-locality-node",
      }),
      text,
    );
    drawing.append(group);
  });
  [60, -60, -180].forEach((degrees) =>
    appendArrow(drawing, 600, 350, 240, degrees),
  );
  drawing.append(
    svg("rect", {
      x: 442,
      y: 692,
      width: 316,
      height: 90,
      rx: 20,
      class: "n8-diagram-hub",
    }),
    svg(
      "text",
      { x: 600, y: 745, "text-anchor": "middle", class: "n8-diagram-hub-name" },
      "Olgiate FS",
    ),
    svg(
      "text",
      { x: 600, y: 775, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
      "PARTENZA · SOSTA INTERMEDIA · ARRIVO",
    ),
  );
  drawing.append(
    svg(
      "text",
      { x: 600, y: 1480, "text-anchor": "middle", class: "n8-diagram-caption" },
      "Riferimenti territoriali, non fermate: l’ordine effettivo è nello schema completo.",
    ),
  );
  finishDiagram(container, drawing, line, { localities: true });
}
