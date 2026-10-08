import {
  statesAt,
  clockSeconds,
  playbackWindow,
  adjacentEvent,
  diagramStops,
} from "./nodo8-line.mjs?v=20261008d";
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
const button = (text, cls, action) => {
  const b = el("button", cls, text);
  b.type = "button";
  b.addEventListener("click", action);
  return b;
};
const hhmm = (m) => clockSeconds(m).slice(0, 5);

export function mountPlayer(
  container,
  line,
  onUpdate,
  {
    compact = false,
    brief = false,
    visibilityTarget = container,
    inlineMap = null,
    initialSelection = "1",
    initialMinute = null,
  } = {},
) {
  const prefix = container.id || "n8-player";
  const names = new Map(diagramStops(line).map((e) => [e.siteId, e.display]));
  const friendly = (e) => names.get(e?.siteId) || e?.name || "Olgiate FS";
  container.classList.add("n8-player");
  if (compact) container.classList.add("n8-player--compact");
  let selection = String(initialSelection),
    minute = initialMinute ?? playbackWindow(line, selection).start,
    playing = false,
    frame = null,
    previous = null,
    speed = 30;
  const header = el("div", "n8-player-title");
  const heading = el("h3", "", "Un bus, tutto l’otto");
  header.append(
    heading,
    el("span", "n8-model-label", "SIMULAZIONE · NON LIVE"),
  );
  const selectWrap = el("div", "n8-trip-select"),
    select = el("select");
  select.id = prefix + "-trip";
  const label = el("label", "n8-trip-label", "Quale giro vuoi vedere?");
  label.htmlFor = select.id;
  line.trips.forEach((t) => {
    const o = el(
      "option",
      "",
      `Giro ${String(t.number).padStart(2, "0")} · ${hhmm(t.start)} → ${hhmm(t.end)} circa`,
    );
    o.value = t.number;
    select.append(o);
  });
  const all = el("option", "", "Intera giornata · tutti i mezzi di modello");
  all.value = "all";
  select.append(all);
  select.value = selection;
  selectWrap.append(label, select);
  const top = el("div", "n8-player-top"),
    time = el("output", "n8-clock");
  time.setAttribute("aria-label", "Ora simulata");
  const play = button("Riproduci", "n8-play", () => toggle());
  play.setAttribute("aria-pressed", "false");
  const reset = button("↺", "n8-reset", () => {
    pause();
    minute = bounds().start;
    render();
  });
  reset.setAttribute(
    "aria-label",
    "Ricomincia il giro o la giornata selezionata",
  );
  top.append(time, play, reset);
  const rangeLabel = el(
    "label",
    "n8-range-label",
    "Sposta il bus lungo il giro",
  );
  const range = el("input");
  range.type = "range";
  range.id = prefix + "-clock";
  range.step = "any";
  rangeLabel.htmlFor = range.id;
  const limits = el("div", "n8-range-limits");
  const milestones = el("div", "n8-milestones");
  const first = button("Partenza", "", () => jump(bounds().start));
  const stop = button("Prima fermata", "", () =>
    jump((bounds().trip ?? line.trips[0]).events[1].arrival),
  );
  const fs = button("Sosta a FS", "", () => {
    const e = (bounds().trip ?? line.trips[0]).events[15];
    jump((e.arrival + e.departure) / 2);
  });
  milestones.append(first, stop, fs);
  const steps = el("div", "n8-event-steps");
  const back = button("← Precedente", "", () =>
    jump(adjacentEvent(line, selection, minute, -1).arrival),
  );
  const forward = button("Successiva →", "", () =>
    jump(adjacentEvent(line, selection, minute, 1).arrival),
  );
  back.setAttribute("aria-label", "Evento di fermata precedente");
  forward.setAttribute("aria-label", "Evento di fermata successivo");
  steps.append(back, forward);
  const current = el("div", "n8-current-event");
  current.setAttribute("aria-live", "off");
  const eventKicker = el("span", "n8-event-kicker"),
    eventName = el("strong", "n8-event-name"),
    eventDetail = el("p", "n8-event-detail");
  current.append(eventKicker, eventName, eventDetail);
  const fleet = el("div", "n8-fleet");
  const cards = new Map(
    line.vehicles.map((v) => {
      const card = el("div", "n8-vehicle-card");
      card.dataset.vehicle = v.id;
      const name = el("strong", "n8-vehicle-id", v.id),
        text = el("div"),
        state = el("span", "n8-vehicle-state"),
        sub = el("small");
      text.append(state, sub);
      card.append(name, text);
      fleet.append(card);
      return [v.id, { card, state, sub }];
    }),
  );
  const info = el("details", "n8-player-details"),
    summary = el("summary", "", "Velocità e metodo della simulazione");
  const speedWrap = el("div", "n8-speed"),
    speedLabel = el("label", "", "Riproduzione accelerata"),
    speedSelect = el("select");
  speedSelect.id = prefix + "-speed";
  speedLabel.htmlFor = speedSelect.id;
  [30, 120, 300].forEach((s) => {
    const o = el("option", "", `×${s}`);
    o.value = s;
    speedSelect.append(o);
  });
  speedWrap.append(speedLabel, speedSelect);
  info.append(
    summary,
    speedWrap,
    el(
      "p",
      "n8-playback-note",
      "Ricostruzione nominale, non GPS live. Soste di 30 secondi alle fermate e attesa intermedia a FS dal registro di progetto. Tra fermate il movimento è interpolato per distanza su tutti i vertici del tracciato: velocità, traffico e passeggeri non sono osservati. B1–B4 sono identificativi di modello, non mezzi assegnati. Nella vista giornata sono inclusi 10 minuti di recupero finale, senza inventare corse a vuoto.",
    ),
  );
  const status = el(
    "p",
    "n8-player-status",
    "In pausa. Scegli un giro e premi Riproduci.",
  );
  status.setAttribute("role", "status");
  const hint = el(
    "p",
    "n8-route-continuity",
    "FS → primo anello → FS → secondo anello → FS. Stesso giro, senza cambio di linea; permanenza a bordo da autorizzare.",
  );
  container.replaceChildren(
    header,
    selectWrap,
    top,
    rangeLabel,
    range,
    limits,
    milestones,
    steps,
  );
  if (inlineMap) container.append(inlineMap);
  container.append(current, fleet, hint, status, info);
  if (brief) {
    summary.textContent = "Fermate, velocità e metodo";
    info.append(milestones, steps, hint);
  }
  function bounds() {
    return playbackWindow(line, selection);
  }
  function pause() {
    playing = false;
    previous = null;
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    play.textContent = "Riproduci";
    play.setAttribute("aria-pressed", "false");
    status.textContent = "In pausa · nessun dato live.";
  }
  function jump(value) {
    pause();
    const b = bounds();
    minute = Math.max(b.start, Math.min(b.end, value));
    status.textContent = "In pausa · evento del registro nominale.";
    render();
  }
  function render() {
    const b = bounds(),
      states = statesAt(line, minute),
      chosen = b.trip && states.find((s) => s.trip === b.trip.number);
    range.min = b.start;
    range.max = b.end;
    range.value = minute;
    range.setAttribute("aria-valuetext", clockSeconds(minute));
    time.textContent = clockSeconds(minute);
    limits.replaceChildren(
      el("span", "", hhmm(b.start) + " · partenza"),
      el(
        "span",
        "",
        hhmm(b.end) +
          (b.trip ? " circa · arrivo FS" : " circa · fine recupero"),
      ),
    );
    container.dataset.playbackTime = minute.toFixed(6);
    container.dataset.playing = String(playing);
    container.dataset.selection = selection;
    container.dataset.completed = String(minute >= b.end);
    heading.textContent = b.trip
      ? "Un bus, tutto l’otto"
      : "La giornata di Nodo8";
    rangeLabel.textContent = b.trip
      ? "Sposta il bus lungo il giro"
      : "Sposta l’orologio della giornata";
    back.disabled = minute <= b.start;
    forward.disabled = minute >= b.end;
    current.hidden = !b.trip;
    fleet.hidden = !!b.trip;
    if (b.trip) {
      const completed = minute >= b.end;
      current.dataset.status = completed ? "complete" : chosen.status;
      eventKicker.textContent = completed
        ? "GIRO CONCLUSO"
        : chosen.status === "fs-hold"
          ? "PASSAGGIO INTERMEDIO"
          : chosen.status === "stop"
            ? "IN FERMATA"
            : "IN VIAGGIO";
      eventName.textContent = completed
        ? "Di nuovo a Olgiate FS"
        : chosen.status === "moving"
          ? "Verso " + friendly(chosen.next)
          : friendly(chosen.event);
      eventDetail.textContent = completed
        ? "Il giro completo termina qui. Il recupero del mezzo non è una prosecuzione passeggeri."
        : chosen.status === "fs-hold"
          ? `Il bus attende fino alle ${hhmm(chosen.until)} e prosegue sul secondo anello. La continuità a bordo è prevista, da autorizzare.`
          : chosen.status === "stop"
            ? `Evento ${chosen.event.ordinal} di 28 · sosta nominale di 30 s · ripartenza ${clockSeconds(chosen.until)}.`
            : `Prossimo evento ${chosen.next.ordinal ?? "FS"} · arrivo nominale ${clockSeconds(chosen.until)}.`;
    }
    states.forEach((s) => {
      const c = cards.get(s.id);
      c.card.dataset.status = s.status;
      c.state.textContent =
        s.status === "stop"
          ? "In fermata · " + s.label
          : s.status === "fs-hold"
            ? "Sosta intermedia · FS"
            : s.label;
      c.sub.textContent = s.trip
        ? `Giro ${s.trip} · ${s.status === "moving" ? "arrivo" : "fine sosta"} ${clockSeconds(s.until)}`
        : s.nextTrip
          ? `Prossimo giro: ${s.nextTrip}. Posizione fuori corsa non ricostruita.`
          : "Giri assegnati conclusi.";
    });
    onUpdate({
      minute,
      states,
      followedTrip: b.trip?.number ?? null,
      playing,
      completed: minute >= b.end,
      selection,
    });
  }
  function tick(now) {
    if (!playing) return;
    if (previous !== null)
      minute = Math.min(
        bounds().end,
        minute + (Math.min(now - previous, 1000) / 60000) * speed,
      );
    previous = now;
    if (minute >= bounds().end) {
      pause();
      status.textContent =
        selection === "all"
          ? "Giornata di modello conclusa."
          : "Giro completo concluso a FS. Premi Riproduci per rivederlo.";
    }
    render();
    if (playing) frame = requestAnimationFrame(tick);
  }
  function toggle() {
    if (playing) {
      pause();
      status.textContent = "In pausa · nessun dato live.";
      render();
      return;
    }
    if (minute >= bounds().end) minute = bounds().start;
    playing = true;
    previous = null;
    play.textContent = "Pausa";
    play.setAttribute("aria-pressed", "true");
    status.textContent = `Riproduzione accelerata ×${speed} · orario nominale.`;
    render();
    frame = requestAnimationFrame(tick);
  }
  select.addEventListener("change", () => {
    selection = select.value;
    jump(selection === "all" ? 455 : bounds().start);
  });
  range.addEventListener("input", () => jump(Number(range.value)));
  speedSelect.addEventListener("change", () => {
    speed = Number(speedSelect.value);
    previous = null;
    if (playing)
      status.textContent = `Riproduzione accelerata ×${speed} · orario nominale.`;
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
  return {
    pause,
    render,
    toggle,
    jump,
    selectTrip: (value) => {
      selection = String(value);
      select.value = selection;
      jump(bounds().start);
    },
    firstStop: () => jump((bounds().trip ?? line.trips[0]).events[1].arrival),
    getMinute: () => minute,
  };
}
