// Dated S8 calls and real local rail vertices. No live data or connection scoring.
export const S8_COLOUR = "#f8b1b0";
const metres = (a, b) => Math.hypot((a[0] - b[0]) * Math.cos((a[1] + b[1]) * Math.PI / 360), a[1] - b[1]) * 111195;

export function buildRail(data) {
  if (data.contract !== "nodo8_s8_local_simulation_v1" || data.colour !== S8_COLOUR ||
      data.scope !== "LOCAL_CERNUSCO_MERATE_OLGIATE_AIRUNO_NOT_FULL_S8" ||
      data.service_date !== "2026-10-01" || data.trains?.length !== 74 ||
      data.semantics?.live !== false || data.semantics?.timetable_2027_certified !== false ||
      data.semantics?.connection_guaranteed !== false || data.semantics?.platform_assignment_certified !== false)
    throw new Error("Unsupported S8 simulation contract");
  const stations = new Map(data.stations.map(s => [s.id, s]));
  if (stations.size !== 3 || data.segments.length !== 2) throw new Error("Incomplete local railway");
  const segments = data.segments.map(segment => {
    const coordinates = segment.coordinates;
    if (coordinates.length < 3 || !stations.has(segment.from_id) || !stations.has(segment.to_id) ||
        !coordinates.every(c => c.length === 2 && c.every(Number.isFinite)) ||
        JSON.stringify(coordinates[0]) !== JSON.stringify(stations.get(segment.from_id).coordinates) ||
        JSON.stringify(coordinates.at(-1)) !== JSON.stringify(stations.get(segment.to_id).coordinates))
      throw new Error("Invalid railway endpoints");
    const cumulative = [0];
    for (let i = 1; i < coordinates.length; i++) cumulative.push(cumulative.at(-1) + metres(coordinates[i - 1], coordinates[i]));
    return {...segment, cumulative, total: cumulative.at(-1)};
  });
  const ids = new Set();
  for (const t of data.trains) {
    const expected = t.direction === "LECCO" ? ["S01513", "S01514", "S01515"] :
      t.direction === "MILANO" ? ["S01515", "S01514", "S01513"] : [];
    if (ids.has(t.id) || expected.length !== 3 || t.calls.length !== 3 ||
        t.calls.some((c, i) => c.station_id !== expected[i] || !Number.isFinite(c.arrival_min) ||
          !Number.isFinite(c.departure_min) || c.departure_min < c.arrival_min ||
          (i > 0 && c.arrival_min <= t.calls[i - 1].departure_min)))
      throw new Error("Invalid dated S8 call sequence");
    ids.add(t.id);
  }
  for (const d of ["MILANO", "LECCO"])
    if (data.trains.filter(t => t.direction === d).length !== 37) throw new Error("Incomplete direction inventory");
  return {...data, stations, segments};
}

export function railPosition(segment, fraction) {
  const target = Math.max(0, Math.min(1, fraction)) * segment.total;
  const i = Math.max(1, segment.cumulative.findIndex(d => d >= target));
  const span = segment.cumulative[i] - segment.cumulative[i - 1];
  const f = span ? (target - segment.cumulative[i - 1]) / span : 0;
  return segment.coordinates[i - 1].map((v, axis) => v + (segment.coordinates[i][axis] - v) * f);
}

export function trainsAt(rail, minute) {
  if (!Number.isFinite(minute)) throw new Error("Invalid simulation clock");
  const states = [];
  for (const train of rail.trains) {
    const calls = train.calls;
    // No extension beyond the three supported station calls.
    if (minute < calls[0].arrival_min || minute > calls.at(-1).departure_min) continue;
    let coordinates, status;
    for (let i = 0; i < calls.length; i++) {
      const call = calls[i], next = calls[i + 1];
      if (minute >= call.arrival_min && minute <= call.departure_min) {
        coordinates = rail.stations.get(call.station_id).coordinates;
        status = "station";
        break;
      }
      if (next && minute > call.departure_min && minute < next.arrival_min) {
        const segment = rail.segments.find(s =>
          (s.from_id === call.station_id && s.to_id === next.station_id) ||
          (s.to_id === call.station_id && s.from_id === next.station_id));
        if (!segment) throw new Error("Missing railway segment");
        const f = (minute - call.departure_min) / (next.arrival_min - call.departure_min);
        coordinates = railPosition(segment, segment.from_id === call.station_id ? f : 1 - f);
        status = "moving";
        break;
      }
    }
    if (coordinates) states.push({...train, coordinates, status});
  }
  return states;
}

export async function installS8(map) {
  const response = await fetch("../assets/nodo8-s8-simulation.json?v=20261008q");
  if (!response.ok) throw new Error("S8 data unavailable");
  const rail = buildRail(await response.json());
  map.addSource("s8-local", {type: "geojson", data: {type: "FeatureCollection", features:
    rail.segments.map(s => ({type: "Feature", properties: {}, geometry: {type: "LineString", coordinates: s.coordinates}}))}});
  map.addLayer({id: "s8-local-route", type: "line", source: "s8-local", layout: {"line-cap": "round", "line-join": "round"},
    paint: {"line-color": S8_COLOUR, "line-width": 3, "line-opacity": 0}}, "nodo8-glow");
  const markers = new Map();
  return {
    localCoordinates: rail.segments.flatMap(s => s.coordinates),
    render({minute, visible}) {
      map.setPaintProperty("s8-local-route", "line-opacity", visible ? 0.9 : 0);
      const states = visible ? trainsAt(rail, minute) : [];
      const present = new Set(states.map(t => t.id));
      for (const [id, entry] of markers) if (!present.has(id)) {entry.marker.remove(); markers.delete(id);}
      for (const state of states) {
        if (!markers.has(state.id)) {
          const icon = document.createElement("div");
          icon.className = "s8-train-marker";
          icon.setAttribute("role", "img");
          icon.innerHTML = '<svg viewBox="0 0 24 30" width="24" height="30" aria-hidden="true"><rect x="3" y="1" width="18" height="24" rx="5" fill="#f8b1b0" stroke="#173c33" stroke-width="1.5"/><rect x="6" y="6" width="12" height="7" rx="2" fill="#173c33"/><text x="12" y="20" text-anchor="middle" font-size="7" font-weight="800" fill="#173c33">S8</text><path d="M7 29l3-4m7 4l-3-4" stroke="#f8b1b0" stroke-width="2"/></svg><span class="s8-train-direction"></span>';
          // Screen-space separation only, not a physical track assignment.
          const marker = new window.maplibregl.Marker({element: icon, anchor: "center",
            offset: [state.direction === "LECCO" ? 13 : -13, 0]});
          markers.set(state.id, {marker, icon});
          marker.setLngLat(state.coordinates).addTo(map);
        }
        const entry = markers.get(state.id);
        const label = `S8 ${state.number} verso ${state.direction === "LECCO" ? "Lecco" : "Milano"} · ${state.status === "station" ? "in stazione" : "posizione interpolata"}`;
        entry.icon.setAttribute("aria-label", label);
        entry.icon.title = label;
        entry.icon.querySelector("span").textContent = state.direction === "LECCO" ? "↑" : "↓";
        entry.marker.setLngLat(state.coordinates);
      }
      document.documentElement.dataset.s8Visible = String(visible);
      document.documentElement.dataset.s8TrainCount = String(states.length);
      const status = document.getElementById("s8SimulationStatus");
      if (status) {
        status.hidden = !visible;
        const label = `${states.length} ${states.length === 1 ? "treno nel tratto locale" : "treni nel tratto locale"} · verso Milano e Lecco`;
        if (status.textContent !== label) status.textContent = label;
      }
    },
  };
}
