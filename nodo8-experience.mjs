import { statesAt, clockSeconds, diagramStops } from "./nodo8-line.mjs";
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
      id,
    ),
    svg("circle", { cx: 10, cy: 33, r: 2, fill: "#ffe4a4" }),
    svg("circle", { cx: 24, cy: 33, r: 2, fill: "#ffe4a4" }),
    svg("rect", { x: 7, y: 35, width: 5, height: 5, rx: 2, fill: "#183b32" }),
    svg("rect", { x: 22, y: 35, width: 5, height: 5, rx: 2, fill: "#183b32" }),
  );
  e.append(icon);
  return e;
}
export function updateBusMarker(element, state) {
  element.dataset.status = state.status;
  element.title =
    state.id +
    " · " +
    (state.trip ? "giro " + state.trip + " · " : "") +
    state.label;
  element.setAttribute("aria-label", element.title);
}

/* Controls share one nominal event model in both pages. Never advances without Play. */
export function mountPlayer(
  container,
  line,
  onUpdate,
  { compact = false, brief = false, visibilityTarget = container } = {},
) {
  const prefix = container.id || "n8-player";
  container.classList.add("n8-player");
  if (compact) container.classList.add("n8-player--compact");
  let minute = 455,
    playing = false,
    frame = null,
    previous = null,
    speed = 30;
  const title = node("div", "n8-player-title");
  const heading = node("h3", "", "Una giornata di Nodo8");
  const badge = node("span", "n8-model-label", "SIMULAZIONE · NON LIVE");
  title.append(heading, badge);
  const top = node("div", "n8-player-top"),
    time = node("output", "n8-clock");
  time.setAttribute("aria-label", "Ora nel giorno di progetto");
  const play = node("button", "n8-play", "▶ Riproduci");
  play.type = "button";
  const speedLabel = node("label", "n8-speed-label", "Velocità");
  const speedSelect = node("select");
  speedSelect.id = prefix + "-speed";
  speedLabel.htmlFor = speedSelect.id;
  [30, 120, 300].forEach((s) => {
    const o = node("option", "", "×" + s);
    o.value = s;
    o.selected = s === speed;
    speedSelect.append(o);
  });
  const speedWrap = node("div", "n8-speed");
  speedWrap.append(speedLabel, speedSelect);
  top.append(time, play, speedWrap);
  const rangeLabel = node(
    "label",
    "n8-range-label",
    "Sposta l’orologio del giorno di progetto",
  );
  const range = node("input");
  range.type = "range";
  range.id = prefix + "-clock";
  range.min = line.start;
  range.max = line.end;
  range.step = "0.001";
  range.value = minute;
  rangeLabel.htmlFor = range.id;
  const limits = node("div", "n8-range-limits");
  limits.append(
    node("span", "", "06:05 · prima partenza"),
    node("span", "", "21:18 · fine recupero nominale"),
  );
  const presets = node("div", "n8-presets");
  const first = line.trips[0];
  [
    ["Punta · 07:35", 455],
    ["Sosta a una fermata", first.events[1].arrival + 0.25],
    [
      "Prosecuzione a FS",
      (first.events[15].arrival + first.events[15].departure) / 2,
    ],
  ].forEach(([label, value]) => {
    const b = node("button", "", label);
    b.type = "button";
    b.addEventListener("click", () => {
      pause();
      minute = value;
      render();
    });
    presets.append(b);
  });
  const tripLabel = node("label", "n8-trip-label", "Segui un giro completo");
  const select = node("select");
  select.id = prefix + "-trip";
  tripLabel.htmlFor = select.id;
  const any = node("option", "", "Tutti i mezzi in servizio");
  any.value = "all";
  select.append(any);
  line.trips.forEach((t) => {
    const o = node(
      "option",
      "",
      "Giro " +
        String(t.number).padStart(2, "0") +
        " · " +
        clockSeconds(t.start).slice(0, 5),
    );
    o.value = t.number;
    select.append(o);
  });
  const selectWrap = node("div", "n8-trip-select");
  selectWrap.append(tripLabel, select);
  const fleet = node("div", "n8-fleet");
  const cards = new Map(
    line.vehicles.map((v) => {
      const card = node("div", "n8-vehicle-card");
      card.dataset.vehicle = v.id;
      const id = node("strong", "n8-vehicle-id", v.id),
        content = node("div"),
        label = node("span", "n8-vehicle-state"),
        sub = node("small");
      content.append(label, sub);
      card.append(id, content);
      fleet.append(card);
      return [v.id, { card, label, sub }];
    }),
  );
  const note = node(
    "p",
    "n8-playback-note",
    "Orari nominali e soste dal registro di progetto: 30 s alle fermate, attesa intermedia a FS e 10 min di recupero finale. Tra fermate, posizione interpolata per distanza sul tracciato stradale; velocità, traffico e passeggeri non sono osservati. B1–B4 sono mezzi di modello, non una flotta assegnata.",
  );
  const status = node(
    "p",
    "n8-player-status",
    "In pausa. Premi Riproduci oppure sposta l’orologio.",
  );
  status.setAttribute("role", "status");
  container.replaceChildren(
    title,
    top,
    rangeLabel,
    range,
    limits,
    presets,
    selectWrap,
    fleet,
    status,
    note,
  );
  if (brief) {
    const details = node("details", "n8-player-details"),
      summary = node(
        "summary",
        "",
        "Mezzi di modello e metodo dell’animazione",
      );
    details.append(summary, selectWrap, fleet, note);
    container.append(details);
  }
  const pause = () => {
    playing = false;
    previous = null;
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    play.textContent = "▶ Riproduci";
    play.setAttribute("aria-pressed", "false");
    status.textContent = "In pausa · orario di progetto, non posizione live.";
  };
  const render = () => {
    const states = statesAt(line, minute);
    range.value = minute;
    range.setAttribute("aria-valuetext", clockSeconds(minute));
    time.textContent = clockSeconds(minute);
    container.dataset.playbackTime = minute.toFixed(6);
    container.dataset.playing = String(playing);
    states.forEach((s) => {
      const c = cards.get(s.id);
      c.card.dataset.status = s.status;
      c.card.classList.toggle(
        "is-followed",
        select.value !== "all" && Number(select.value) === s.trip,
      );
      c.label.textContent =
        (s.status === "stop"
          ? "Fermata · "
          : s.status === "fs-hold"
            ? "Sosta intermedia · "
            : "") + s.label;
      c.sub.textContent = s.trip
        ? "Giro " +
          s.trip +
          " · " +
          (s.status === "moving" ? "arrivo ≈ " : "ripartenza/fine ≈ ") +
          clockSeconds(s.until)
        : s.nextTrip
          ? "Prossimo giro: " +
            s.nextTrip +
            " · nessun movimento a vuoto ricostruito"
          : "Giri assegnati conclusi";
    });
    onUpdate({
      minute,
      states,
      followedTrip: select.value === "all" ? null : Number(select.value),
      playing,
    });
  };
  const tick = (now) => {
    if (!playing) return;
    if (previous !== null)
      minute = Math.min(
        line.end,
        minute + (Math.min(now - previous, 1000) / 60000) * speed,
      );
    previous = now;
    if (minute >= line.end) pause();
    render();
    if (playing) frame = requestAnimationFrame(tick);
  };
  play.setAttribute("aria-pressed", "false");
  play.addEventListener("click", () => {
    if (playing) {
      pause();
      render();
      return;
    }
    if (minute >= line.end) minute = line.start;
    playing = true;
    previous = null;
    play.textContent = "Ⅱ Pausa";
    play.setAttribute("aria-pressed", "true");
    status.textContent =
      "Riproduzione accelerata ×" + speed + " · nessun dato live.";
    render();
    frame = requestAnimationFrame(tick);
  });
  range.addEventListener("input", () => {
    pause();
    minute = Number(range.value);
    render();
  });
  speedSelect.addEventListener("change", () => {
    speed = Number(speedSelect.value);
    previous = null;
    if (playing)
      status.textContent =
        "Riproduzione accelerata ×" + speed + " · nessun dato live.";
  });
  select.addEventListener("change", () => {
    pause();
    if (select.value !== "all")
      minute = line.trips[Number(select.value) - 1].start;
    render();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      pause();
      render();
    }
  });
  if ("IntersectionObserver" in window)
    new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting && playing) {
        pause();
        render();
      }
    }).observe(visibilityTarget);
  render();
  return { pause, render, getMinute: () => minute };
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
        ? 565 - t * 440
        : 125 + t * 440
      : outward
        ? 785 + t * 440
        : 1225 - t * 440;
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
  const entries = diagramStops(line, localities),
    id = container.id;
  const drawing = svg("svg", {
    viewBox: "0 0 1200 1335",
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
    const d = [[600, 675], ...points.map((p) => [p.x, p.y]), [600, 675]]
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
      y: 627,
      width: 378,
      height: 95,
      rx: 24,
      class: "n8-diagram-hub",
    }),
    svg(
      "text",
      { x: 600, y: 661, "text-anchor": "middle", class: "n8-diagram-hub-name" },
      "Olgiate FS",
    ),
    svg(
      "text",
      { x: 600, y: 687, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
      "PARTENZA → PASSAGGIO → ARRIVO",
    ),
    svg(
      "text",
      { x: 600, y: 708, "text-anchor": "middle", class: "n8-diagram-hub-sub" },
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
      { x: 600, y: 1296, "text-anchor": "middle", class: "n8-diagram-caption" },
      localities
        ? "Raggruppamenti dei siti di progetto · non tutte le frazioni dei cinque comuni"
        : "27 siti distinti · 28 eventi fuori FS · FS ha tre ruoli nel giro",
    ),
    svg(
      "text",
      { x: 600, y: 1320, "text-anchor": "middle", class: "n8-diagram-caption" },
      "Schema non geografico · ordine di servizio, non tempi o distanze",
    ),
  );
  const scroll = node("div", "n8-diagram-scroll");
  scroll.tabIndex = 0;
  scroll.setAttribute(
    "aria-label",
    "Schema scorrevole orizzontalmente su schermi piccoli",
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
      copy.setAttribute("width", "1200");
      copy.setAttribute("height", "1335");
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
  container.replaceChildren(scroll, download);
}
