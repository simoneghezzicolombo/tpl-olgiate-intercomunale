/* Pure presentation model. No route search, timetable synthesis or live tracking. */
const fail = (message) => {
  throw new Error("Nodo8 playback: " + message);
};
const samePoint = (a, b) =>
  a?.length === 2 && b?.length === 2 && a.every((v, i) => v === b[i]);
const near = (a, b) =>
  Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) < 1e-7;
export const clockSeconds = (minute) => {
  const s = Math.floor(minute * 60 + 1e-7);
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60]
    .map((v) => String(v).padStart(2, "0"))
    .join(":");
};
const distance = (a, b) => {
  const rad = Math.PI / 180,
    lat = (b[1] - a[1]) * rad,
    lon = (b[0] - a[0]) * rad;
  const h =
    Math.sin(lat / 2) ** 2 +
    Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(lon / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
};
export function buildLine(data) {
  const p = data.playback;
  if (
    p?.contract !== "nodo8_nominal_event_playback_v1" ||
    p.ledger?.length !== 16 ||
    p.vehicles?.length !== 4 ||
    p.physical_vehicle_and_passenger_continuity_certified !== false ||
    data.authority?.public_operating_timetable_authorised !== false ||
    data.authority?.network_selected !== false ||
    data.authority?.primary_selection_authorised !== false ||
    data.authority?.runner_up_selection_authorised !== false
  )
    fail("unsupported source contract");
  const first = data.routes.find((r) => r.wing === "east_A")?.coordinates;
  const second = data.routes.find((r) => r.wing === "west_B")?.coordinates;
  if (
    !first ||
    !second ||
    !samePoint(first.at(-1), second[0]) ||
    !samePoint(first[0], second.at(-1))
  )
    fail("discontinuous complete route");
  const coordinates = [...first, ...second.slice(1)],
    middle = first.length - 1;
  if (
    coordinates.some(
      (c) => c.length !== 2 || c.some((v) => !Number.isFinite(v)),
    )
  )
    fail("invalid road coordinate");
  const lengths = [0];
  for (let i = 1; i < coordinates.length; i++)
    lengths.push(lengths.at(-1) + distance(coordinates[i - 1], coordinates[i]));
  const sites = new Map(data.sites.map((s) => [s.site_id, s]));
  const occurrenceMap = new Map(
    data.sites.flatMap((s) =>
      s.ordered_occurrences.map((e) => [
        e.occurrence_id,
        { site: s, event: e },
      ]),
    ),
  );
  if (occurrenceMap.size !== 28 || sites.size !== 27)
    fail("stop/event cardinality changed");
  const trips = p.ledger.map((ledger, i) => {
    if (
      !near(ledger.first_fs_min, data.trips[i].first_fs_min) ||
      !near(ledger.second_fs_min, data.trips[i].second_fs_min) ||
      ledger.events.length !== 31
    )
      fail("ledger mismatch");
    const events = ledger.events.map((event, index) => {
      let node,
        arrival,
        departure,
        name,
        siteId,
        occurrenceId = null,
        ordinal = null;
      if (event.role === "DESIGN_STOP_OCCURRENCE") {
        const entry = occurrenceMap.get(event.occurrence_id);
        if (
          !entry ||
          entry.site.site_id !== event.site_id ||
          event.physical_boarding_authorised !== false
        )
          fail("unknown occurrence");
        node = event.full_path_edge_index;
        if (
          node !==
            entry.event.path_node_index +
              (event.wing === "west_B" ? middle : 0) ||
          !samePoint(coordinates[node], entry.site.coordinates_lon_lat)
        )
          fail("occurrence/road vertex mismatch");
        arrival = event.alight_event_min;
        departure = event.board_event_min;
        name = entry.site.name;
        siteId = event.site_id;
        occurrenceId = event.occurrence_id;
        ordinal = entry.event.ordered_nonhub_event_number;
      } else {
        name = "Olgiate FS";
        siteId = data.sites.find((s) => s.hub_service_roles.length)?.site_id;
        if (event.role === "FULL_TRIP_START_FS" && index === 0) {
          node = 0;
          arrival = departure = event.time_min;
        } else if (
          event.role === "INTERMEDIATE_FS_STAY_ONBOARD_DESIGN" &&
          index === 15 &&
          event.physical_continuity_certified === false
        ) {
          node = middle;
          arrival = event.arrival_min;
          departure = event.departure_min;
        } else if (event.role === "FULL_TRIP_END_FS" && index === 30) {
          node = coordinates.length - 1;
          arrival = departure = event.arrival_min;
        } else fail("unsupported service-event order");
      }
      if (
        !Number.isInteger(node) ||
        !Number.isFinite(arrival) ||
        !Number.isFinite(departure) ||
        departure < arrival
      )
        fail("invalid event clock");
      return {
        node,
        arrival,
        departure,
        name,
        siteId,
        occurrenceId,
        ordinal,
        role: event.role,
        coordinates: coordinates[node],
      };
    });
    events.forEach((e, j) => {
      if (
        j &&
        (e.node <= events[j - 1].node || e.arrival < events[j - 1].departure)
      )
        fail("nonmonotonic sequence");
    });
    if (
      !near(events.at(-1).arrival, data.trips[i].return_fs_min) ||
      !near(events[15].departure, ledger.second_fs_min)
    )
      fail("trip boundaries differ");
    if (
      events.filter((e) => e.occurrenceId).some((e, j) => e.ordinal !== j + 1)
    )
      fail("occurrence order differs");
    return {
      number: i + 1,
      events,
      start: events[0].departure,
      end: events.at(-1).arrival,
    };
  });
  const assigned = new Set();
  const vehicles = p.vehicles.map((v) => {
    if (
      !/^B[1-4]$/.test(v.model_vehicle_id) ||
      v.same_model_vehicle_through_intermediate_fs !== true
    )
      fail("invalid carrier assignment");
    const blocks = v.trips.map((b) => {
      const t = trips[b.full_trip_number - 1];
      if (
        !t ||
        assigned.has(t.number) ||
        !near(t.start, b.fs_start_min) ||
        !near(t.end, b.fs_end_min) ||
        !near(t.events[15].arrival, b.intermediate_fs_arrival_min) ||
        !near(t.events[15].departure, b.intermediate_fs_departure_min) ||
        !near(
          b.released_after_terminal_recovery_min - t.end,
          p.terminal_recovery_min,
        )
      )
        fail("block/event mismatch");
      assigned.add(t.number);
      return { ...t, release: b.released_after_terminal_recovery_min };
    });
    blocks.forEach((b, i) => {
      if (i && b.start < blocks[i - 1].release)
        fail("overlapping occupation of same carrier");
    });
    return { id: v.model_vehicle_id, blocks };
  });
  if (assigned.size !== 16 || new Set(vehicles.map((v) => v.id)).size !== 4)
    fail("incomplete carrier assignment");
  return {
    coordinates,
    lengths,
    trips,
    vehicles,
    middle,
    start: trips[0].start,
    end: Math.max(...vehicles.flatMap((v) => v.blocks.map((b) => b.release))),
    sites,
  };
}

export function positionBetween(line, from, to, fraction) {
  if (fraction <= 0) return line.coordinates[from];
  if (fraction >= 1) return line.coordinates[to];
  const target =
    line.lengths[from] + fraction * (line.lengths[to] - line.lengths[from]);
  let lo = from + 1,
    hi = to;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    if (line.lengths[m] < target) lo = m + 1;
    else hi = m;
  }
  const a = line.coordinates[lo - 1],
    b = line.coordinates[lo],
    d = line.lengths[lo] - line.lengths[lo - 1];
  const f = d ? (target - line.lengths[lo - 1]) / d : 0;
  return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])];
}
export function vehicleState(line, vehicle, minute) {
  const trip = vehicle.blocks.find(
    (b) => minute >= b.start && minute < b.release,
  );
  const base = {
    id: vehicle.id,
    trip: trip?.number ?? null,
    coordinates: null,
    event: null,
    next: null,
  };
  if (!trip)
    return {
      ...base,
      status: "off-service",
      label: "Fuori corsa · posizione non modellata",
      nextTrip: vehicle.blocks.find((b) => b.start > minute)?.number ?? null,
    };
  if (minute >= trip.end)
    return {
      ...base,
      status: "recovery",
      label: "Recupero terminale · giro concluso",
      coordinates: line.coordinates.at(-1),
      until: trip.release,
    };
  const event = trip.events.find(
    (e) => minute >= e.arrival && minute < e.departure,
  );
  if (event)
    return {
      ...base,
      status:
        event.role === "INTERMEDIATE_FS_STAY_ONBOARD_DESIGN"
          ? "fs-hold"
          : "stop",
      label: event.name,
      event,
      coordinates: event.coordinates,
      until: event.departure,
    };
  for (let i = 1; i < trip.events.length; i++) {
    const a = trip.events[i - 1],
      b = trip.events[i];
    if (minute >= a.departure && minute < b.arrival)
      return {
        ...base,
        status: "moving",
        label: "Verso " + b.name,
        next: b,
        coordinates: positionBetween(
          line,
          a.node,
          b.node,
          (minute - a.departure) / (b.arrival - a.departure),
        ),
        until: b.arrival,
      };
  }
  fail("clock not covered by events");
}
export const statesAt = (line, minute) => {
  if (!Number.isFinite(minute) || minute < line.start || minute > line.end)
    fail("clock outside model day");
  return line.vehicles.map((v) => vehicleState(line, v, minute));
};

/* Presentation bounds only: a selected passenger trip ends before terminal recovery. */
export function playbackWindow(line, selection = "1") {
  if (selection === "all")
    return { start: line.start, end: line.end, trip: null };
  const trip = line.trips.find((t) => t.number === Number(selection));
  if (!trip) fail("unknown displayed trip");
  return { start: trip.start, end: trip.end, trip };
}
export function adjacentEvent(line, selection, minute, direction) {
  const { trip } = playbackWindow(line, selection);
  const events = trip
    ? trip.events
    : line.trips.flatMap((t) => t.events).sort((a, b) => a.arrival - b.arrival);
  return direction > 0
    ? (events.find((e) => e.arrival > minute + 1e-7) ?? events.at(-1))
    : (events.findLast((e) => e.arrival < minute - 1e-7) ?? events[0]);
}

/* Editorial labels only; occurrence identity/order always come from the ledger. */
const names = [
  "San Zeno / Via Cantù",
  "Calco / Via Nazionale",
  "Beverate / Cariplo",
  "Beverate / Paese",
  "Beverate / Quattro Strade",
  "Vaccarezza",
  "Brivio / Via Como",
  "Brivio / Via Bergamo",
  "Arlate / N1212",
  "Arlate / Cantina Pirovano",
  "Arlate / Madonnina",
  "Calco Centro / Municipio",
  "Calco / Via Virgilio",
  "San Zeno / Via Cantù",
  "Olgiate sud",
  "Scarpone",
  "Alduno",
  "Rovagnate / Statale–AGIP",
  "Rovagnate / Via Lombardia",
  "Perego / Statale–S. Caterina",
  "Rovagnate / Vinicola Ghezzi",
  "Santa Maria Hoè",
  "Tremonte / Via Trento",
  "Tremonte / Giovanni XXIII",
  "SP58 / Via Cenisio",
  "Olgiate / Via della Salute",
  "Olgiate / Via Statale",
  "Olgiate sud",
];
const groups = [
  [1, "San Zeno / Via Cantù"],
  [2, "Calco / Via Nazionale"],
  [3, "Beverate", 5],
  [6, "Vaccarezza"],
  [7, "Brivio", 8],
  [9, "Arlate", 11],
  [12, "Calco Centro"],
  [13, "Calco / Via Virgilio"],
  [14, "San Zeno / Via Cantù"],
  [15, "Olgiate sud"],
  [16, "Scarpone"],
  [17, "Alduno"],
  [18, "Rovagnate / Statale", 19],
  [20, "Perego / Statale"],
  [21, "Rovagnate / Vinicola"],
  [22, "Santa Maria Hoè"],
  [23, "Tremonte", 24],
  [25, "SP58 / Via Cenisio"],
  [26, "Olgiate / Via della Salute"],
  [27, "Olgiate / Via Statale"],
  [28, "Olgiate sud"],
];
export function diagramStops(line, localities = false) {
  const events = line.trips[0].events.filter((e) => e.occurrenceId);
  if (!localities)
    return events.map((e) => ({
      ...e,
      display: names[e.ordinal - 1],
      ordinals: [e.ordinal],
    }));
  return groups.map(([first, display, last = first]) => ({
    ...events[first - 1],
    display,
    ordinals: Array.from({ length: last - first + 1 }, (_, i) => first + i),
  }));
}
