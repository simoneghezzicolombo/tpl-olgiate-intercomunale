import { clockSeconds, diagramStops } from "./nodo8-line.mjs?v=20261008g";
export const eventKey = (event) => event.occurrenceId || event.role;

/* A specific ordered event pair within one certified nominal ledger.
 * No identity-level merging, optimal-journey choice, transfers or actual-service guarantee. */
export function inspectJourney(line, tripNumber, fromKey, toKey) {
  const trip = line.trips.find((t) => t.number === Number(tripNumber));
  if (!trip) throw new Error("Giro non presente nel registro.");
  const fromIndex = trip.events.findIndex((e) => eventKey(e) === fromKey);
  const toIndex = trip.events.findIndex((e) => eventKey(e) === toKey);
  if (fromIndex < 0 || toIndex <= fromIndex)
    throw new Error("Scegli due passaggi in ordine nello stesso giro.");
  const from = trip.events[fromIndex],
    to = trip.events[toIndex];
  if (to.arrival < from.departure)
    throw new Error("Passaggi non compatibili nel registro.");
  const middle = trip.events[15];
  const crossesFS = fromIndex < 15 && toIndex > 15;
  return {
    trip: trip.number,
    from,
    to,
    minutes: to.arrival - from.departure,
    intermediateHoldMinutes: crossesFS ? middle.departure - middle.arrival : 0,
    crossesFS,
    carrier: line.vehicles.find((v) =>
      v.blocks.some((b) => b.number === trip.number),
    ).id,
    passengerContinuityAuthorised: false,
  };
}

const make = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
export function mountJourneyInspector(container, line, onInspect) {
  const tripSelect = container.querySelector("#journeyTrip"),
    fromSelect = container.querySelector("#journeyFrom"),
    toSelect = container.querySelector("#journeyTo"),
    result = container.querySelector("#journeyResult");
  const names = new Map(diagramStops(line).map((e) => [e.siteId, e.display]));
  const label = (event) =>
    event.role === "FULL_TRIP_START_FS"
      ? "Olgiate FS · partenza"
      : event.role === "INTERMEDIATE_FS_STAY_ONBOARD_DESIGN"
        ? "Olgiate FS · passaggio intermedio"
        : event.role === "FULL_TRIP_END_FS"
          ? "Olgiate FS · arrivo finale"
          : `${names.get(event.siteId) || event.name} · passaggio ${event.ordinal}`;
  const option = (value, text) => {
    const o = make("option", "", text);
    o.value = value;
    return o;
  };
  tripSelect.replaceChildren(
    ...line.trips.map((trip) =>
      option(
        trip.number,
        `Giro ${String(trip.number).padStart(2, "0")} · FS ${clockSeconds(trip.start).slice(0, 5)}`,
      ),
    ),
  );
  const template = line.trips[0];
  fromSelect.replaceChildren(
    ...template.events.slice(0, -1).map((e) => option(eventKey(e), label(e))),
  );
  const refreshDestinations = () => {
    const previous = toSelect.value;
    const first = template.events.findIndex(
      (e) => eventKey(e) === fromSelect.value,
    );
    const events = template.events.slice(first + 1);
    toSelect.replaceChildren(
      option("", "Scegli dove arrivare…"),
      ...events.map((e) => option(eventKey(e), label(e))),
    );
    if (events.some((e) => eventKey(e) === previous)) toSelect.value = previous;
  };
  refreshDestinations();
  // Explicit demonstration, not a recommended or automatically minimised journey.
  toSelect.value = eventKey(template.events.find((e) => e.ordinal === 12));
  const render = () => {
    result.replaceChildren();
    if (!toSelect.value) {
      result.append(
        make("p", "journey-empty", "Scegli un arrivo dopo la partenza."),
      );
      return;
    }
    try {
      const journey = inspectJourney(
        line,
        tripSelect.value,
        fromSelect.value,
        toSelect.value,
      );
      const minutes = new Intl.NumberFormat("it-IT", {
        maximumFractionDigits: 1,
      }).format(journey.minutes);
      const headline = make("div", "journey-time");
      headline.append(
        make("strong", "", minutes),
        make("span", "", "minuti a bordo previsti"),
      );
      const endpoints = make("div", "journey-endpoints");
      [
        [journey.from, "Partenza"],
        [journey.to, "Arrivo"],
      ].forEach(([event, heading]) => {
        const item = make("div");
        item.append(
          make("span", "", heading),
          make("strong", "", label(event)),
          make(
            "time",
            "",
            clockSeconds(
              event === journey.from ? event.departure : event.arrival,
            ) + " circa",
          ),
        );
        endpoints.append(item);
      });
      const explanation = make(
        "p",
        "journey-explanation",
        journey.crossesFS
          ? `Compresi ${new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(journey.intermediateHoldMinutes)} minuti di sosta a FS. Il progetto prevede lo stesso bus ${journey.carrier}; restare a bordo deve essere autorizzato.`
          : `Un tratto del giro scelto, sul bus ${journey.carrier} del modello.`,
      );
      const actions = make("div", "journey-inspect-actions");
      [
        ["Partenza sulla mappa", journey.from.departure],
        ["Arrivo sulla mappa", journey.to.arrival],
      ].forEach(([text, minute]) => {
        const button = make("button", "", text);
        button.type = "button";
        button.addEventListener("click", () => onInspect(journey.trip, minute));
        actions.append(button);
      });
      result.dataset.trip = journey.trip;
      result.dataset.from = eventKey(journey.from);
      result.dataset.to = eventKey(journey.to);
      result.append(headline, endpoints, explanation, actions);
    } catch (error) {
      result.append(make("p", "journey-empty", error.message));
    }
  };
  fromSelect.addEventListener("change", () => {
    refreshDestinations();
    render();
  });
  toSelect.addEventListener("change", render);
  tripSelect.addEventListener("change", render);
  [tripSelect, fromSelect, toSelect].forEach((n) => (n.disabled = false));
  render();
}
