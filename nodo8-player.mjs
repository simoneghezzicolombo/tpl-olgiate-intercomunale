import {
  statesAt,
  clockSeconds,
  playbackWindow,
  adjacentEvent,
  diagramStops,
  servicePhase,
} from "./nodo8-line.mjs?v=20261008s";
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
const text = (node, value) => {
  if (node.textContent !== value) node.textContent = value;
};

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
    speed = 30,
    previousUiKey = null,
    previousBoundsSelection = null,
    lastSingleSelection = selection === "all" ? "1" : selection;
  const header = el("div", "n8-player-title");
  const identity = el("div", "n8-player-identity"),
    badge = el("span", "n8-line-badge", "8"),
    titleWrap = el("div"),
    heading = el("h3", "", "Segui un giro"),
    subtitle = el(
      "p",
      "n8-player-subtitle",
      "Una linea. Ogni corsa fa tutto il giro.",
    );
  badge.setAttribute("aria-hidden", "true");
  titleWrap.append(heading, subtitle);
  identity.append(badge, titleWrap);
  header.append(
    identity,
    el("span", "n8-model-label", "Simulazione · non GPS"),
  );
  const modes = el("div", "n8-player-modes");
  modes.setAttribute("role", "group");
  modes.setAttribute("aria-label", "Vista della simulazione");
  const tripMode = button("Un giro completo", "", () =>
      changeSelection(lastSingleSelection),
    ),
    dayMode = button("I quattro bus", "", () => changeSelection("all", 455));
  modes.append(tripMode, dayMode);
  const selectWrap = el("div", "n8-trip-select"),
    select = el("select");
  select.id = prefix + "-trip";
  const label = el("label", "n8-trip-label", "Scegli la corsa");
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
  const all = el("option", "", "Tutta la giornata · i quattro bus simulati");
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
  const clockWrap = el("div", "n8-clock-wrap"),
    clockCaption = el("span", "n8-clock-caption", "Ora simulata");
  clockWrap.append(clockCaption, time);
  top.append(clockWrap, play, reset);
  const rangeLabel = el(
    "label",
    "n8-range-label",
    "Trascina per scegliere il momento",
  );
  const range = el("input");
  range.type = "range";
  range.id = prefix + "-clock";
  range.step = "any";
  rangeLabel.htmlFor = range.id;
  const limits = el("div", "n8-range-limits");
  const startLimit = el("span"),
    endLimit = el("span");
  limits.append(startLimit, endLimit);
  const progress = el("div", "n8-trip-progress"),
    progressTrack = el("div", "n8-trip-progress-track"),
    progressFill = el("span"),
    progressText = el("span", "n8-trip-progress-text");
  progressTrack.setAttribute("aria-hidden", "true");
  progressTrack.append(progressFill);
  progress.append(progressText, progressTrack);
  const phases = el("ol", "n8-service-phases");
  phases.setAttribute("aria-label", "Avanzamento del giro completo");
  [
    "FS · partenza",
    "Primo anello",
    "FS · sosta",
    "Secondo anello",
    "FS · arrivo",
  ].forEach((text) => phases.append(el("li", "", text)));
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
  back.setAttribute("aria-label", "Fermata precedente");
  forward.setAttribute("aria-label", "Fermata successiva");
  steps.append(back, forward);
  const current = el("div", "n8-current-event");
  current.setAttribute("aria-live", "off");
  const eventKicker = el("span", "n8-event-kicker"),
    eventName = el("strong", "n8-event-name"),
    eventDetail = el("p", "n8-event-detail");
  current.append(eventKicker, eventName, eventDetail);
  const fleet = el("div", "n8-fleet");
  fleet.setAttribute(
    "aria-label",
    "Quattro bus simulati: scegline uno per seguire il giro",
  );
  const fleetHeading = el("div", "n8-fleet-heading"),
    fleetCount = el("strong"),
    fleetHint = el("span", "", "Seleziona un bus per seguire il suo giro");
  fleetHeading.append(fleetCount, fleetHint);
  const cards = new Map(
    line.vehicles.map((v) => {
      const card = button("", "n8-vehicle-card", () => {
        const state = statesAt(line, minute).find((s) => s.id === v.id);
        if (state.trip) changeSelection(String(state.trip), minute);
      });
      card.dataset.vehicle = v.id;
      const name = el("strong", "n8-vehicle-id", v.id),
        text = el("div", "n8-vehicle-copy"),
        trip = el("span", "n8-vehicle-trip"),
        state = el("span", "n8-vehicle-state"),
        sub = el("small"),
        track = el("span", "n8-vehicle-progress"),
        fill = el("span");
      track.setAttribute("aria-hidden", "true");
      track.append(fill);
      text.append(trip, state, sub, track);
      card.append(name, text);
      fleet.append(card);
      return [v.id, { card, trip, state, sub, fill }];
    }),
  );
  const info = el("details", "n8-player-details"),
    summary = el("summary", "", "Come funziona l’animazione");
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
      "I bus seguono le strade e l’orario del progetto, non dati GPS. Si fermano per 30 secondi a ogni fermata e attendono a FS quanto previsto. Il movimento tra fermate è calcolato in base alla distanza: non misura velocità, traffico o passeggeri reali. B1–B4 sono bus simulati, non mezzi assegnati. La vista giornata comprende 10 minuti di pausa dopo ogni rientro; non ricostruisce gli spostamenti fuori servizio.",
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
    "Un unico giro completo, con sosta intermedia a Olgiate FS. La prosecuzione sullo stesso bus è progettata; permanenza a bordo da autorizzare.",
  );
  const navigation = el("details", "n8-event-navigation"),
    navigationSummary = el(
      "summary",
      "",
      "Vai a una fermata o alla sosta in stazione",
    );
  navigation.append(navigationSummary, milestones, steps);
  container.replaceChildren(
    header,
    modes,
    selectWrap,
    top,
    rangeLabel,
    range,
    limits,
    progress,
    phases,
  );
  if (inlineMap) container.append(inlineMap);
  container.append(current, fleetHeading, fleet, navigation, status, info);
  info.append(hint);
  if (brief) {
    summary.textContent = "Altri controlli e come funziona";
    info.append(navigation);
  }
  function changeSelection(value, at = null) {
    selection = String(value);
    if (selection !== "all") lastSingleSelection = selection;
    select.value = selection;
    jump(at ?? bounds().start);
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
    status.textContent = "In pausa · orario del progetto.";
    render();
  }
  function render(force = true) {
    const b = bounds(),
      states = statesAt(line, minute),
      chosen = b.trip && states.find((s) => s.trip === b.trip.number);
    const update = {
      minute,
      states,
      followedTrip: b.trip?.number ?? null,
      playing,
      completed: minute >= b.end,
      selection,
    };
    // Keep map movement at animation-frame precision. The control surface only
    // needs a new nominal second (or explicit state change), not 60 DOM rewrites.
    const stateKey = states
      .map(
        (s) =>
          `${s.trip}:${s.status}:${s.event?.ordinal ?? s.event?.role}:${s.next?.ordinal ?? s.next?.role}`,
      )
      .join("|");
    const uiKey = `${selection}:${Math.floor(minute * 60)}:${playing}:${update.completed}:${stateKey}`;
    if (!force && uiKey === previousUiKey) {
      onUpdate(update);
      return;
    }
    previousUiKey = uiKey;
    if (previousBoundsSelection !== selection) {
      previousBoundsSelection = selection;
      range.min = b.start;
      range.max = b.end;
      startLimit.textContent = hhmm(b.start) + " · partenza";
      endLimit.textContent =
        hhmm(b.end) +
        (b.trip ? " circa · arrivo FS" : " circa · fine recupero");
    }
    range.value = minute;
    range.setAttribute("aria-valuetext", clockSeconds(minute));
    text(time, clockSeconds(minute));
    tripMode.setAttribute("aria-pressed", String(!!b.trip));
    dayMode.setAttribute("aria-pressed", String(!b.trip));
    container.dataset.view = b.trip ? "trip" : "day";
    container.dataset.playbackTime = minute.toFixed(6);
    container.dataset.playing = String(playing);
    container.dataset.selection = selection;
    container.dataset.completed = String(minute >= b.end);
    text(heading, b.trip ? "Segui un giro" : "La linea, in movimento");
    text(
      subtitle,
      b.trip
        ? "Una linea. Ogni corsa fa tutto il giro."
        : "Quattro bus simulati, un solo percorso.",
    );
    text(
      rangeLabel,
      b.trip
        ? "Trascina per scegliere il momento"
        : "Trascina per scegliere l’ora",
    );
    back.disabled = minute <= b.start;
    forward.disabled = minute >= b.end;
    current.hidden = !b.trip;
    phases.hidden = !b.trip;
    progress.hidden = !b.trip;
    navigation.hidden = !b.trip;
    if (b.trip) {
      const elapsed = Math.max(0, minute - b.start),
        duration = b.end - b.start;
      text(
        progressText,
        `Giro ${String(b.trip.number).padStart(2, "0")} · ${Math.floor(elapsed)} di ${Math.round(duration)} min circa`,
      );
      progressFill.style.width = `${(elapsed / duration) * 100}%`;
      const phase = servicePhase(line, b.trip.number, minute);
      [...phases.children].forEach((item, i) => {
        item.classList.toggle("is-complete", i < phase);
        if (i === phase) item.setAttribute("aria-current", "step");
        else item.removeAttribute("aria-current");
      });
    }
    fleet.hidden = !!b.trip;
    fleetHeading.hidden = !!b.trip;
    const occupied = states.filter(
      (s) => s.trip && s.status !== "recovery",
    ).length;
    text(fleetCount, `${occupied} di 4 bus in corsa`);
    if (b.trip) {
      const completed = minute >= b.end;
      current.dataset.status = completed ? "complete" : chosen.status;
      text(
        eventKicker,
        completed
          ? "GIRO CONCLUSO"
          : chosen.status === "fs-hold"
            ? "SOSTA A FS"
            : chosen.status === "stop"
              ? "IN FERMATA"
              : "IN VIAGGIO",
      );
      text(
        eventName,
        completed
          ? "Di nuovo a Olgiate FS"
          : chosen.status === "moving"
            ? "Verso " + friendly(chosen.next)
            : friendly(chosen.event),
      );
      text(
        eventDetail,
        completed
          ? "Il giro completo termina qui. Il recupero del mezzo non è una prosecuzione passeggeri."
          : chosen.status === "fs-hold"
            ? `Il bus attende fino alle ${hhmm(chosen.until)} e prosegue sul secondo anello. La continuità a bordo è prevista, da autorizzare.`
            : chosen.status === "stop"
              ? `Fermata n. ${chosen.event.ordinal} del giro · riparte alle ${clockSeconds(chosen.until)} circa.`
              : `Arrivo previsto alle ${clockSeconds(chosen.until)} circa.`,
      );
    }
    if (!b.trip)
      states.forEach((s) => {
        const c = cards.get(s.id);
        c.card.dataset.status = s.status;
        c.card.disabled = !s.trip;
        c.card.setAttribute(
          "aria-label",
          s.trip ? `Segui ${s.id}, giro ${s.trip}` : `${s.id}, fuori corsa`,
        );
        text(
          c.trip,
          s.trip ? `Giro ${String(s.trip).padStart(2, "0")}` : "Fuori corsa",
        );
        text(
          c.state,
          s.status === "moving"
            ? "Verso " + friendly(s.next)
            : s.status === "stop"
              ? friendly(s.event)
              : s.status === "fs-hold"
                ? "Olgiate FS · sosta intermedia"
                : s.status === "recovery"
                  ? "Olgiate FS · recupero terminale"
                  : "Posizione non ricostruita",
        );
        text(
          c.sub,
          s.trip
            ? `${s.status === "moving" ? "Arrivo" : s.status === "stop" ? "Ripartenza" : "Fino alle"} ${clockSeconds(s.until)}`
            : s.nextTrip
              ? `Prossimo giro ${s.nextTrip}`
              : "Giri assegnati conclusi.",
        );
        const t = s.trip && line.trips.find((t) => t.number === s.trip);
        c.fill.style.width = t
          ? `${Math.max(0, Math.min(1, (minute - t.start) / (t.end - t.start))) * 100}%`
          : "0%";
      });
    onUpdate(update);
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
    render(false);
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
    status.textContent = `Riproduzione ×${speed} · orario del progetto.`;
    render();
    frame = requestAnimationFrame(tick);
  }
  select.addEventListener("change", () => {
    changeSelection(select.value, select.value === "all" ? 455 : null);
  });
  range.addEventListener("input", () => jump(Number(range.value)));
  speedSelect.addEventListener("change", () => {
    speed = Number(speedSelect.value);
    previous = null;
    if (playing)
      status.textContent = `Riproduzione ×${speed} · orario del progetto.`;
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
    selectTrip: (value) => changeSelection(value),
    firstStop: () => jump((bounds().trip ?? line.trips[0]).events[1].arrival),
    getMinute: () => minute,
  };
}
