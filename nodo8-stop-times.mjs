import { siteTimetable, clockSeconds } from "./nodo8-line.mjs?v=20261008f";

const labels = {
  FULL_TRIP_START_FS: "Partenza FS",
  INTERMEDIATE_FS_STAY_ONBOARD_DESIGN: "Sosta e prosecuzione FS",
  FULL_TRIP_END_FS: "Arrivo finale FS",
};
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
export function stopLink(siteId, base = "./") {
  return base + "?site=" + encodeURIComponent(siteId) + "#stopDetail";
}

/* Only select IDs already bound to the validated ledger. Never synthesize a trip. */
export function readStopSelection(line, url) {
  const params = new URL(url).searchParams;
  const siteId = params.get("site");
  if (!siteId) return null;
  if (!line.sites.has(siteId))
    throw new Error("Fermata del collegamento non presente nella proposta.");
  return siteId;
}

export function renderStopTimes(
  host,
  line,
  siteId,
  onEvent,
  { open = false } = {},
) {
  const tableData = siteTimetable(line, siteId);
  const details = el("details", "n8-stop-times");
  details.dataset.columns = tableData.columns.length;
  details.open = open;
  details.append(el("summary", "", "Quando passa qui? · Tutti i 16 giri"));
  const note = el(
    "p",
    "n8-stop-times-note",
    "Base feriale 2027: lunedì–venerdì, esclusi festivi nazionali, prima di eccezioni locali. Orari nominali del progetto, non un orario pubblico autorizzato. Tocca un’ora per vedere quel passaggio sulla mappa.",
  );
  const wrap = el("div", "n8-stop-times-scroll");
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute(
    "aria-label",
    "Orari nominali della fermata, scorribili se necessario",
  );
  const table = el("table");
  table.append(
    el(
      "caption",
      "",
      tableData.columns.length === 1
        ? "Arrivo e ripartenza dal registro nominale, al secondo circa."
        : "I passaggi della stessa corsa sono separati: non sono linee diverse o viaggi intercambiabili. Orari al secondo circa.",
    ),
  );
  const head = el("thead"),
    heading = el("tr");
  const first = el("th", "", "Giro");
  first.scope = "col";
  heading.append(first);
  tableData.columns.forEach((column, index) => {
    const cell = el(
      "th",
      "",
      labels[column.role] ||
        (tableData.columns.length > 1
          ? `Passaggio ${index + 1} · evento ${column.ordinal}`
          : `Evento ${column.ordinal}`),
    );
    cell.scope = "col";
    heading.append(cell);
  });
  head.append(heading);
  const body = el("tbody");
  tableData.rows.forEach((row) => {
    const tr = el("tr");
    tr.dataset.trip = row.trip;
    const trip = el("th", "", String(row.trip).padStart(2, "0"));
    trip.scope = "row";
    tr.append(trip);
    row.events.forEach((event) => {
      const cell = el("td"),
        button = el("button", "n8-stop-time", clockSeconds(event.arrival));
      button.type = "button";
      button.dataset.event = event.occurrenceId || event.role;
      button.dataset.arrival = event.arrival;
      button.setAttribute(
        "aria-label",
        `Visualizza giro ${row.trip}, ${labels[event.role] || "evento " + event.ordinal}, ${clockSeconds(event.arrival)} circa`,
      );
      button.addEventListener("click", () => onEvent(row.trip, event));
      cell.append(button);
      if (event.departure > event.arrival)
        cell.append(el("small", "", "rip. " + clockSeconds(event.departure)));
      tr.append(cell);
    });
    body.append(tr);
  });
  table.append(head, body);
  wrap.append(table);
  if (tableData.columns.length > 1)
    details.append(
      el(
        "p",
        "n8-stop-times-mobile-hint",
        "↔ Se necessario, scorri la tabella per confrontare i passaggi.",
      ),
    );
  details.append(
    note,
    wrap,
    el(
      "p",
      "n8-stop-times-note",
      "Non include cammino, attesa iniziale, ritardi o una garanzia di coincidenza ferroviaria. Recupero terminale e corse a vuoto non sono passaggi passeggeri.",
    ),
  );
  host.append(details);
  return details;
}
