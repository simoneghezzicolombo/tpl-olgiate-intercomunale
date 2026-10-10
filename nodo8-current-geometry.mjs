// Geometric reconstruction on the exact, unchanged GTFS trip shape.
// This is a linear-reference estimate, not GPS or a repair of source clocks.
const EARTH_RADIUS_METRES = 6371000;
const RAD = Math.PI / 180;

export function currentGeodesicMetres(a, b) {
  const lat = (b[1] - a[1]) * RAD, lon = (b[0] - a[0]) * RAD;
  const h = Math.sin(lat / 2) ** 2 + Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) * Math.sin(lon / 2) ** 2;
  return 2 * EARTH_RADIUS_METRES * Math.asin(Math.min(1, Math.sqrt(h)));
}

const finiteCoordinate = c => Array.isArray(c) && c.length === 2 && c.every(Number.isFinite);

export function indexCurrentShape(shape) {
  if (!Array.isArray(shape?.coordinates) || shape.coordinates.length < 2 || !shape.coordinates.every(finiteCoordinate))
    throw new Error("Invalid source shape coordinates");
  const coordinates = shape.coordinates;
  const reference = coordinates.reduce((a, c) => [a[0] + c[0] / coordinates.length, a[1] + c[1] / coordinates.length], [0, 0]);
  const xScale = EARTH_RADIUS_METRES * RAD * Math.cos(reference[1] * RAD), yScale = EARTH_RADIUS_METRES * RAD;
  const project = c => [(c[0] - reference[0]) * xScale, (c[1] - reference[1]) * yScale];
  const points = coordinates.map(project), distances = [0];
  for (let i = 1; i < coordinates.length; i++) distances.push(distances[i - 1] + currentGeodesicMetres(coordinates[i - 1], coordinates[i]));
  if (!distances.at(-1)) throw new Error("Degenerate source shape");
  return {coordinates, distances, points, project, reference, sourceDistances:shape.distances};
}

function locateCurrentShape(index, distance) {
  if (!Number.isFinite(distance)) throw new Error("Invalid geometric chainage");
  const target = Math.max(0, Math.min(index.distances.at(-1), distance));
  let lo = 0, hi = index.distances.length - 1;
  while (lo < hi) {const mid = (lo + hi) >>> 1; if (index.distances[mid] < target) lo = mid + 1; else hi = mid;}
  if (!lo) return {segment_index:0, fraction:0, chainage_metres:target};
  const segment_index = lo - 1, span = index.distances[lo] - index.distances[segment_index];
  return {segment_index, fraction:span ? (target - index.distances[segment_index]) / span : 0, chainage_metres:target};
}

export function positionOnCurrentShape(index, distance) {
  const {segment_index, fraction} = locateCurrentShape(index, distance);
  const a = index.coordinates[segment_index], b = index.coordinates[segment_index + 1];
  return a.map((v, axis) => v + fraction * (b[axis] - v));
}

// Only used as a secondary tie-breaker and to report the old offset. It cannot
// improve the primary geometric objective or alter any supplied source value.
function sourceLocation(index, sourceDistance) {
  const distances = index.sourceDistances;
  if (!Array.isArray(distances) || distances.length !== index.coordinates.length || !Number.isFinite(sourceDistance) ||
      distances.some((d, i) => !Number.isFinite(d) || (i && d < distances[i - 1]))) return null;
  const target = Math.max(distances[0], Math.min(distances.at(-1), sourceDistance));
  let lo = 0, hi = distances.length - 1;
  while (lo < hi) {const mid = (lo + hi) >>> 1; if (distances[mid] < target) lo = mid + 1; else hi = mid;}
  if (!lo) return {chainage_metres:0, coordinates:index.coordinates[0]};
  const fraction = distances[lo] > distances[lo - 1] ? (target - distances[lo - 1]) / (distances[lo] - distances[lo - 1]) : 0;
  return {chainage_metres:index.distances[lo - 1] + fraction * (index.distances[lo] - index.distances[lo - 1]),
    coordinates:index.coordinates[lo - 1].map((v, axis) => v + fraction * (index.coordinates[lo][axis] - v))};
}

function squaredOffset(point, candidate) {return (point[0] - candidate.x) ** 2 + (point[1] - candidate.y) ** 2;}

function isBetter(cost, tie, bestCost, bestTie) {
  const tolerance = 1e-10 * Math.max(1, Math.abs(cost), Math.abs(bestCost));
  return cost < bestCost - tolerance || (Math.abs(cost - bestCost) <= tolerance && tie < bestTie);
}

// The constrained least-squares optimum partitions consecutive calls into
// blocks sharing a path position. Each block optimum is a vertex or the
// projection of that block's centroid on one segment. Enumerating those
// positions and applying a prefix-minimum DP therefore retains the continuous
// optimum, including equality constraints; it does not merely snap to vertices.
export function matchCurrentCalls(index, calls) {
  if (!Array.isArray(calls) || calls.length < 1 || !calls.every(c => finiteCoordinate(c.coordinates)) ||
      calls.some((c, i) => i && !(c.sequence > calls[i - 1].sequence)))
    throw new Error("Invalid ordered source calls");
  const projected = calls.map(c => index.project(c.coordinates));
  const candidates = index.points.map((p, i) => ({s:index.distances[i], x:p[0], y:p[1]}));
  for (let from = 0; from < projected.length; from++) {
    let x = 0, y = 0;
    for (let to = from; to < projected.length; to++) {
      x += projected[to][0]; y += projected[to][1];
      const count = to - from + 1, cx = x / count, cy = y / count;
      for (let segment = 0; segment < index.points.length - 1; segment++) {
        const a = index.points[segment], b = index.points[segment + 1], dx = b[0] - a[0], dy = b[1] - a[1];
        const lengthSquared = dx * dx + dy * dy;
        if (!lengthSquared) continue;
        const fraction = ((cx - a[0]) * dx + (cy - a[1]) * dy) / lengthSquared;
        if (fraction <= 0 || fraction >= 1) continue; // Already represented by vertices.
        candidates.push({s:index.distances[segment] + fraction * (index.distances[segment + 1] - index.distances[segment]),
          x:a[0] + fraction * dx, y:a[1] + fraction * dy});
      }
    }
  }
  candidates.sort((a, b) => a.s - b.s);
  const positions = candidates.filter((c, i) => !i || c.s !== candidates[i - 1].s);
  const n = positions.length, predecessors = [];
  let previousCost = new Float64Array(n), previousTie = new Float64Array(n);
  const sources = calls.map(c => sourceLocation(index, c.distance));
  for (let call = 0; call < calls.length; call++) {
    const cost = new Float64Array(n), tie = new Float64Array(n), back = new Int32Array(n);
    let best = 0;
    for (let position = 0; position < n; position++) {
      if (call && isBetter(previousCost[position], previousTie[position], previousCost[best], previousTie[best])) best = position;
      cost[position] = squaredOffset(projected[call], positions[position]) + (call ? previousCost[best] : 0);
      tie[position] = (sources[call] ? (positions[position].s - sources[call].chainage_metres) ** 2 : 0) + (call ? previousTie[best] : 0);
      back[position] = call ? best : -1;
    }
    predecessors.push(back); previousCost = cost; previousTie = tie;
  }
  let best = 0;
  for (let position = 1; position < n; position++) if (isBetter(previousCost[position], previousTie[position], previousCost[best], previousTie[best])) best = position;
  const objective = previousCost[best], matched = new Array(calls.length);
  for (let call = calls.length - 1; call >= 0; call--) {
    const chainage_metres = positions[best].s, coordinates = positionOnCurrentShape(index, chainage_metres);
    matched[call] = {...locateCurrentShape(index, chainage_metres), coordinates,
      stop_id:calls[call].stop_id, sequence:calls[call].sequence,
      offset_metres:currentGeodesicMetres(calls[call].coordinates, coordinates),
      source_chainage_metres:sources[call]?.chainage_metres ?? null,
      source_offset_metres:sources[call] ? currentGeodesicMetres(calls[call].coordinates, sources[call].coordinates) : null};
    best = predecessors[call][best];
  }
  return {calls:matched, objective_squared_local_metres:objective,
    matching:"GLOBAL_MONOTONE_LEAST_SQUARES_ON_EXACT_SHAPE",
    metric:"FIXED_LOCAL_EQUIRECTANGULAR_METRES",
    tie_break:"SOURCE_CHAINAGE_ONLY_FOR_EQUAL_GEOMETRIC_OBJECTIVE",
    candidate_count:n};
}

export function reconstructCurrentGeometry(data) {
  const shapes = Object.fromEntries(Object.entries(data.shapes).map(([id, shape]) => [id, indexCurrentShape(shape)]));
  const patterns = new Map();
  const trips = data.trips.map(trip => {
    const key = JSON.stringify([trip.shape_id, trip.calls.map(c => [c.stop_id, c.sequence, c.coordinates, c.distance])]);
    if (!patterns.has(key)) patterns.set(key, matchCurrentCalls(shapes[trip.shape_id], trip.calls));
    const matching = patterns.get(key);
    const legs = trip.calls.slice(0, -1).map((from, i) => {
      const to = trip.calls[i + 1], a = matching.calls[i], b = matching.calls[i + 1];
      const seconds = (to.arrival_min - from.departure_min) * 60;
      const sourceMetres = a.source_chainage_metres === null || b.source_chainage_metres === null ? null :
        b.source_chainage_metres - a.source_chainage_metres;
      const metres = b.chainage_metres - a.chainage_metres;
      return {from_sequence:from.sequence, to_sequence:to.sequence, from_stop_id:from.stop_id, to_stop_id:to.stop_id,
        source_seconds:seconds, source_metres:sourceMetres, metres,
        source_mean_kmh:seconds > 0 && sourceMetres !== null ? sourceMetres / seconds * 3.6 : null,
        mean_kmh:seconds > 0 ? metres / seconds * 3.6 : null};
    });
    return {id:trip.id, route:trip.route, shape_id:trip.shape_id, ...matching, legs};
  });
  const calls = trips.flatMap(t => t.calls), legs = trips.flatMap(t => t.legs);
  return {shapes, trips, summary:{trips:trips.length, shapes:Object.keys(shapes).length, patterns:patterns.size,
    calls:calls.length, legs:legs.length,
    max_source_offset_metres:Math.max(...calls.map(c => c.source_offset_metres ?? 0)),
    max_offset_metres:Math.max(...calls.map(c => c.offset_metres)),
    mean_source_offset_metres:calls.reduce((s, c) => s + (c.source_offset_metres ?? 0), 0) / calls.length,
    mean_offset_metres:calls.reduce((s, c) => s + c.offset_metres, 0) / calls.length,
    source_legs_over_90:legs.filter(l => l.source_mean_kmh > 90).length,
    legs_over_90:legs.filter(l => l.mean_kmh > 90).length,
    max_source_mean_kmh:Math.max(...legs.map(l => l.source_mean_kmh ?? 0)),
    max_mean_kmh:Math.max(...legs.map(l => l.mean_kmh ?? 0))}};
}

const FROZEN_FS_COORDINATES = [9.4044416, 45.7291436];
const FROZEN_FS_GEOMETRY_SHA = "47148a1aa91c1e290084718f93da47b23bb4e05f90e07a1d1af6412f590fe4e3";
const FROZEN_GTFS_SHA = "f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b";
const FS_RETURN_RULES = new Set(["D184|1|+++D84++012", "D185|0|+++E03++011", "D185|0|+++E03++051"]);
export const CURRENT_FS_DISPLAY_ANCHOR_LIMIT_METRES = 50;

// The frozen proposal supplies a station reference, not permission to relocate
// a physical stop or certification of a platform. Keep that distinction in the
// derived record, including the proposal's physical_boarding_authorised=false.
export function currentFsStationEvidence(proposal) {
  const station = proposal?.sites?.find(s => s.site_id === "FROZEN::L00407");
  if (proposal?.contract !== "nodo8_showcase_v1" || !station || station.kind !== "INVENTORY_HUB" ||
      station.physical_boarding_authorised !== false || !finiteCoordinate(station.coordinates_lon_lat) ||
      !station.coordinates_lon_lat.every((v, i) => v === FROZEN_FS_COORDINATES[i]) ||
      proposal.sources?.geometry?.sha256 !== FROZEN_FS_GEOMETRY_SHA)
    throw new Error("Unsupported frozen FS station reference");
  return {path:"assets/nodo8-proposal.json", site_id:station.site_id, coordinates:[...station.coordinates_lon_lat],
    geometry_source:{...proposal.sources.geometry}, physical_boarding_authorised:false};
}

// Opt-in, direction/occurrence-specific display policy. Only the last 300407
// call of these exact return shapes uses its own official shape endpoint near
// the frozen station. Outbound 300407 remains at the shape's Statale start;
// no rail-to-Statale leg, new shape vertex or physical stop is invented.
export function applyDisplayOccurrenceAnchors(data, geometry, stationEvidence) {
  if (data.source?.sha256 !== FROZEN_GTFS_SHA || stationEvidence?.path !== "assets/nodo8-proposal.json" ||
      stationEvidence.site_id !== "FROZEN::L00407" || stationEvidence.physical_boarding_authorised !== false ||
      stationEvidence.geometry_source?.sha256 !== FROZEN_FS_GEOMETRY_SHA ||
      !finiteCoordinate(stationEvidence.coordinates) || !stationEvidence.coordinates.every((v, i) => v === FROZEN_FS_COORDINATES[i]))
    throw new Error("Unsupported FS display anchor evidence");
  const sources = new Map(data.trips.map(t => [t.id, t]));
  let anchored = 0, stataleStarts = 0;
  const trips = geometry.trips.map(trip => {
    const source = sources.get(trip.id), index = geometry.shapes[trip.shape_id];
    if (!source || source.shape_id !== trip.shape_id || source.calls.length !== trip.calls.length || !index ||
        trip.calls.some((c, i) => c.stop_id !== source.calls[i].stop_id || c.sequence !== source.calls[i].sequence))
      throw new Error("Display anchor trip occurrence mismatch");
    const calls = trip.calls.map((matched, occurrence) => {
      const raw = source.calls[occurrence], last = occurrence === trip.calls.length - 1;
      const endpoint = index.coordinates.at(-1), stationOffset = currentGeodesicMetres(endpoint, stationEvidence.coordinates);
      const terminalAnchor = raw.stop_id === "300407" && last &&
        FS_RETURN_RULES.has(`${source.route}|${source.direction_id}|${source.shape_id}`) &&
        stationOffset <= CURRENT_FS_DISPLAY_ANCHOR_LIMIT_METRES;
      const stataleStart = raw.stop_id === "300407" && occurrence === 0 &&
        currentGeodesicMetres(raw.coordinates, index.coordinates[0]) < 1 &&
        currentGeodesicMetres(index.coordinates[0], stationEvidence.coordinates) > CURRENT_FS_DISPLAY_ANCHOR_LIMIT_METRES;
      const display_chainage_metres = terminalAnchor ? index.distances.at(-1) : matched.chainage_metres;
      const display_coordinates = terminalAnchor ? endpoint : matched.coordinates;
      anchored += Number(terminalAnchor); stataleStarts += Number(stataleStart);
      return {...matched, display_chainage_metres, display_coordinates,
        display_source_coordinates:raw.coordinates,
        display_source_offset_metres:currentGeodesicMetres(raw.coordinates, display_coordinates),
        display_role:terminalAnchor ? "FS_RAIL_RETURN_SHAPE_ENDPOINT" : stataleStart ? "FS_VIA_STATALE_SHAPE_START" : "ORDERED_GTFS_STOP_OCCURRENCE",
        display_anchor_policy:terminalAnchor ? "LAST_300407_ON_OWN_SHAPE_ENDPOINT_WITHIN_50M_OF_FROZEN_FS" : "MONOTONE_GEOMETRIC_REFERENCE",
        ...(terminalAnchor ? {display_anchor_evidence:{station:stationEvidence, trip_id:trip.id, shape_id:trip.shape_id,
          route:source.route, direction_id:source.direction_id, source_stop_id:raw.stop_id, source_sequence:raw.sequence,
          source_label:raw.name, source_coordinates:raw.coordinates, shape_vertex_index:index.coordinates.length - 1,
          endpoint_station_offset_metres:stationOffset, maximum_endpoint_station_offset_metres:CURRENT_FS_DISPLAY_ANCHOR_LIMIT_METRES,
          physical_stop_relocated:false, physical_stop_certified:false}} : {})};
    });
    const legs = trip.legs.map((leg, i) => {
      const display_metres = calls[i + 1].display_chainage_metres - calls[i].display_chainage_metres;
      if (!(display_metres > 0)) throw new Error("Display anchors do not preserve strictly ordered geometric calls");
      return {...leg, display_metres, display_mean_kmh:leg.source_seconds > 0 ? display_metres / leg.source_seconds * 3.6 : null};
    });
    return {...trip, calls, legs};
  });
  const calls = trips.flatMap(t => t.calls), legs = trips.flatMap(t => t.legs);
  return {...geometry, trips, display_anchor_summary:{anchored_return_calls:anchored, unchanged_statale_departure_calls:stataleStarts,
    max_display_source_offset_metres:Math.max(...calls.map(c => c.display_source_offset_metres)),
    source_clock_display_legs_over_90:legs.filter(l => l.display_mean_kmh > 90).length,
    max_source_clock_display_mean_kmh:Math.max(...legs.map(l => l.display_mean_kmh ?? 0))}};
}
