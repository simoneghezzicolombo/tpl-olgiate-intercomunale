import { diagramStops } from "./nodo8-line.mjs?v=20261008e";
const ns = "http://www.w3.org/2000/svg";
const node = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const svg = (tag, attributes = {}, text) => {
  const e = document.createElementNS(ns, tag);
  for (const [k, v] of Object.entries(attributes)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
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
    svg("rect", {
      x: 4,
      y: 2,
      width: 26,
      height: 34,
      rx: 7,
      class: "n8-bus-body",
    }),
    svg("rect", { x: 8, y: 7, width: 18, height: 10, rx: 2, fill: "#f6f3eb" }),
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
    state.label;
  element.setAttribute("aria-label", element.title);
}

export { mountPlayer } from "./nodo8-player.mjs?v=20261008e";

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
  const buses = new Map(
    line.vehicles.map((v) => {
      const bus = svg("g", { class: "n8-road-bus", "data-vehicle": v.id });
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

function positions(count, upper) {
  const half = Math.ceil(count / 2),
    other = count - half;
  return Array.from({ length: count }, (_, i) => {
    const outward = i < half,
      n = outward ? half : other,
      index = outward ? i : i - half;
    const t = n > 1 ? index / (n - 1) : 0.5;
    const y = upper
      ? outward
        ? 460 - t * 345
        : 115 + t * 345
      : outward
        ? 685 + t * 345
        : 1030 - t * 345;
    const inset = Math.abs(t - 0.5) * 160;
    const right = upper ? outward : !outward;
    return { x: right ? 800 - inset : 400 + inset, y, right };
  });
}
function wrapLabel(value) {
  if (value.length <= 26) return [value];
  const words = value.split(" ");
  let a = "",
    b = "";
  words.forEach((w) => {
    if (!b && (a + " " + w).trim().length <= 26) a = (a + " " + w).trim();
    else b = (b + " " + w).trim();
  });
  return [a, b];
}
export function renderDiagram(
  container,
  line,
  { localities = false, onSelect } = {},
) {
  if (localities) return renderLocalityDiagram(container, line);
  const entries = diagramStops(line, localities),
    id = container.id;
  const drawing = svg("svg", {
    viewBox: "0 0 1200 1150",
    class: "n8-diagram",
    role: onSelect && !localities ? "group" : "img",
    "aria-labelledby": id + "-title " + id + "-description",
  });
  drawing.append(
    svg(
      "title",
      { id: id + "-title" },
      localities
        ? "Nodo8 · le località in ordine"
        : "Nodo8 · schema delle fermate in ordine di servizio",
    ),
    svg(
      "desc",
      { id: id + "-description" },
      "Un'unica linea a otto. Partenza, passaggio intermedio e arrivo a Olgiate FS. " +
        entries.map((e) => e.display).join(" → ") +
        ". Schema non geografico; nessuna autorizzazione fisica delle fermate.",
    ),
  );
  drawing.append(
    svg("text", { x: 72, y: 47, class: "n8-diagram-brand" }, "nodo8"),
    svg(
      "text",
      { x: 1128, y: 43, "text-anchor": "end", class: "n8-diagram-caption" },
      localities
        ? "LE LOCALITÀ, NELL’ORDINE DEL GIRO"
        : "UN’UNICA LINEA · TUTTE LE FERMATE",
    ),
  );
  const placed = [],
    arrows = [];
  [true, false].forEach((upper) => {
    const part = entries.filter((e) => e.ordinal <= 14 === upper),
      points = positions(part.length, upper);
    const d = [[600, 575], ...points.map((p) => [p.x, p.y]), [600, 575]]
      .map(([x, y], i) => (i ? "L" : "M") + x + " " + y)
      .join(" ");
    drawing.append(
      svg("path", { d, class: "n8-diagram-shadow" }),
      svg("path", { d, class: "n8-diagram-line" }),
    );
    const half = Math.ceil(points.length / 2);
    [points.slice(0, half), points.slice(half)].forEach((side) => {
      const j = Math.max(1, Math.floor(side.length / 2)),
        a = side[j - 1],
        b = side[j];
      arrows.push([
        (a.x + b.x) / 2,
        (a.y + b.y) / 2,
        (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI,
      ]);
    });
    part.forEach((e, i) => placed.push({ ...e, ...points[i] }));
  });
  placed.forEach((e) => {
    const isNew = line.sites.get(e.siteId).proposed_new_site;
    const g = svg("g", {
      class: "n8-diagram-stop",
      "data-occurrence": e.occurrenceId,
    });
    if (onSelect && !localities) {
      g.setAttribute("tabindex", "0");
      g.setAttribute("role", "button");
      g.setAttribute(
        "aria-label",
        "Evento " +
          e.ordinal +
          ": " +
          e.name +
          (isNew ? ", nuovo sito proposto" : ""),
      );
      g.addEventListener("click", () => onSelect(line.sites.get(e.siteId)));
      g.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          onSelect(line.sites.get(e.siteId));
        }
      });
    }
    const labelX = e.right ? 850 : 350,
      textAnchor = e.right ? "start" : "end";
    g.append(
      svg(
        "title",
        {},
        e.name + " · " + e.ordinals.map((o) => "evento " + o).join(", "),
      ),
      svg("line", {
        x1: e.x,
        y1: e.y,
        x2: e.right ? 832 : 368,
        y2: e.y,
        class: "n8-diagram-leader",
      }),
      svg("circle", {
        cx: e.x,
        cy: e.y,
        r: localities ? 10 : 17,
        class: isNew && !localities ? "n8-diagram-new" : "n8-diagram-dot",
      }),
    );
    if (!localities)
      g.append(
        svg(
          "text",
          {
            x: e.x,
            y: e.y + 5,
            "text-anchor": "middle",
            class: "n8-diagram-number",
          },
          e.ordinal,
        ),
      );
    const text = svg("text", {
      x: labelX,
      y: e.y - (localities ? 2 : 3),
      "text-anchor": textAnchor,
      class: "n8-diagram-name",
    });
    wrapLabel(e.display).forEach((t, i) =>
      text.append(svg("tspan", { x: labelX, dy: i ? 20 : 0 }, t)),
    );
    g.append(text);
    const note = localities
      ? "passaggi " + e.ordinals.join("–")
      : e.ordinal === 14 || e.ordinal === 28
        ? "NUOVO · secondo passaggio nello stesso sito"
        : isNew
          ? "NUOVO SITO PROPOSTO"
          : "";
    if (note)
      g.append(
        svg(
          "text",
          {
            x: labelX,
            y: e.y + (wrapLabel(e.display).length > 1 ? 35 : 19),
            "text-anchor": textAnchor,
            class: "n8-diagram-sub",
          },
          note,
        ),
      );
    drawing.append(g);
  });
  drawing.append(
    svg("rect", {
      x: 411,
      y: 527,
      width: 378,
      height: 95,
      rx: 24,
      class: "n8-diagram-hub",
    }),
    svg(
      "text",
      { x: 600, y: 561, "text-anchor": "middle", class: "n8-diagram-hub-name" },
      "Olgiate FS",
    ),
    svg(
      "text",
      { x: 600, y: 587, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
      "PARTENZA → PASSAGGIO → ARRIVO",
    ),
    svg(
      "text",
      { x: 600, y: 608, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
      "stesso bus · prosecuzione progettata",
    ),
  );
  // Arrowheads indicate service order, not an opposite-direction service.
  arrows.forEach(([x, y, rotate]) =>
    drawing.append(
      svg("path", {
        d: "M-8 -7 L2 0 L-8 7",
        transform: `translate(${x} ${y}) rotate(${rotate})`,
        class: "n8-diagram-arrow",
      }),
    ),
  );
  drawing.append(
    svg(
      "text",
      { x: 600, y: 1110, "text-anchor": "middle", class: "n8-diagram-caption" },
      localities
        ? "Raggruppamenti dei siti di progetto · non tutte le frazioni dei cinque comuni"
        : "27 siti distinti · 28 eventi fuori FS · FS ha tre ruoli nel giro",
    ),
    svg(
      "text",
      { x: 600, y: 1134, "text-anchor": "middle", class: "n8-diagram-caption" },
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
        new URL("./nodo8-experience.css", import.meta.url),
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
    summary = node("summary", "", "Leggi la sequenza dei passaggi");
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
  container.replaceChildren(scroll, tools, order);
}

function renderLocalityDiagram(container, line) {
  const entries = diagramStops(line, true),
    id = container.id;
  const drawing = svg("svg", {
    viewBox: "0 0 1200 820",
    class: "n8-diagram n8-diagram--localities",
    role: "img",
    "aria-labelledby": id + "-title " + id + "-description",
  });
  drawing.append(
    svg(
      "title",
      { id: id + "-title" },
      "Nodo8 · un otto, le località in ordine",
    ),
    svg(
      "desc",
      { id: id + "-description" },
      "Un unico giro: Olgiate FS → " +
        entries
          .slice(0, 9)
          .map((e) => e.display)
          .join(" → ") +
        " → FS, sosta intermedia → " +
        entries
          .slice(9)
          .map((e) => e.display)
          .join(" → ") +
        " → FS. Località e corridoi raggruppati, non tutte le frazioni dei cinque comuni.",
    ),
  );
  drawing.append(
    svg("text", { x: 62, y: 48, class: "n8-diagram-brand" }, "nodo8"),
    svg(
      "text",
      { x: 1138, y: 44, "text-anchor": "end", class: "n8-diagram-caption" },
      "LO STESSO GIRO, NELLO STESSO ORDINE",
    ),
  );
  [245, 575].forEach((cy) => {
    drawing.append(
      svg("ellipse", {
        cx: 285,
        cy,
        rx: 165,
        ry: 165,
        class: "n8-diagram-shadow",
      }),
      svg("ellipse", {
        cx: 285,
        cy,
        rx: 165,
        ry: 165,
        class: "n8-diagram-line",
      }),
    );
  });
  entries.forEach((e, i) => {
    const upper = i < 9,
      j = upper ? i : i - 9,
      n = upper ? 9 : 12,
      t = ((j + 1) / (n + 1)) * Math.PI * 2,
      x = 285 + (upper ? 1 : -1) * 165 * Math.sin(t),
      y = (upper ? 245 : 575) + (upper ? 1 : -1) * 165 * Math.cos(t);
    const g = svg("g", {
      class: "n8-diagram-stop",
      "data-occurrence": e.occurrenceId,
    });
    g.append(
      svg(
        "title",
        {},
        `${i + 1}. ${e.display} · eventi ${e.ordinals.join(", ")}`,
      ),
      svg("circle", { cx: x, cy: y, r: 16, class: "n8-diagram-dot" }),
      svg(
        "text",
        { x, y: y + 5, "text-anchor": "middle", class: "n8-diagram-number" },
        i + 1,
      ),
    );
    drawing.append(g);
    const lx = upper ? 555 : 900,
      ly = upper ? 160 + j * 58 : 154 + j * 49;
    drawing.append(
      svg(
        "text",
        { x: lx, y: ly, class: "n8-locality-number" },
        String(i + 1).padStart(2, "0"),
      ),
    );
    const text = svg("text", { x: lx + 38, y: ly, class: "n8-diagram-name" });
    wrapLabel(e.display).forEach((s, k) =>
      text.append(svg("tspan", { x: lx + 38, dy: k ? 20 : 0 }, s)),
    );
    drawing.append(text);
  });
  drawing.append(
    svg("rect", {
      x: 169,
      y: 366,
      width: 232,
      height: 88,
      rx: 20,
      class: "n8-diagram-hub",
    }),
    svg(
      "text",
      { x: 285, y: 402, "text-anchor": "middle", class: "n8-diagram-hub-name" },
      "Olgiate FS",
    ),
    svg(
      "text",
      { x: 285, y: 428, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
      "UN BUS · UN GIRO COMPLETO",
    ),
  );
  drawing.append(
    svg(
      "text",
      { x: 555, y: 107, class: "n8-locality-heading" },
      "Si parte da FS",
    ),
    svg(
      "text",
      { x: 900, y: 107, class: "n8-locality-heading" },
      "Dopo la sosta a FS",
    ),
    svg(
      "text",
      { x: 555, y: 728, class: "n8-locality-heading" },
      "→ FS · si prosegue",
    ),
    svg(
      "text",
      { x: 900, y: 760, class: "n8-locality-heading" },
      "→ FS · arrivo",
    ),
  );
  [
    [450, 245, -90],
    [120, 245, 90],
    [120, 575, 90],
    [450, 575, -90],
  ].forEach(([x, y, a]) =>
    drawing.append(
      svg("path", {
        d: "M-8 -7 L2 0 L-8 7",
        transform: `translate(${x} ${y}) rotate(${a})`,
        class: "n8-diagram-arrow",
      }),
    ),
  );
  drawing.append(
    svg(
      "text",
      { x: 600, y: 795, "text-anchor": "middle", class: "n8-diagram-caption" },
      "Schema non geografico · 21 passaggi raggruppati · le ripetizioni non sono fermate in più",
    ),
  );
  finishDiagram(container, drawing, line, { localities: true });
}
