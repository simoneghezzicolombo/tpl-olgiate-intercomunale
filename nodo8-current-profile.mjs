// A derived animation clock. Source GTFS clocks remain evidence, and this
// engineering display ceiling is neither a road limit nor a speed certificate.
export const CURRENT_PROFILE_SEGMENT_MEAN_CEILING_KMH = 90;
const SPEED_ROUNDOFF_KMH = 1e-8;
const PROFILE_SEMANTICS = Object.freeze({
  profile:"MAXIMUM_CARDINALITY_SOURCE_ANCHORS_WITH_CHAINAGE_INTERPOLATION",
  tie_break:"LEXICOGRAPHIC_ASCENDING_SOURCE_CALL_INDICES",
  source_clocks_unchanged:true,
  official_timetable_repaired:false,
  actual_vehicle_speed_certified:false,
  inferred_dwell:false,
  mean_segment_ceiling_kmh:CURRENT_PROFILE_SEGMENT_MEAN_CEILING_KMH,
  numerical_speed_tolerance_kmh:SPEED_ROUNDOFF_KMH,
});

function lexicallyEarlier(a, b) {
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i];
  return false;
}

function interval(sourceCalls, chainages, from, to) {
  const seconds = (sourceCalls[to].arrival_min - sourceCalls[from].departure_min) * 60;
  const metres = chainages[to] - chainages[from];
  return {from_index:from, to_index:to, from_sequence:sourceCalls[from].sequence, to_sequence:sourceCalls[to].sequence,
    departure_min:sourceCalls[from].departure_min, arrival_min:sourceCalls[to].arrival_min,
    metres, seconds, mean_kmh:seconds > 0 ? metres / seconds * 3.6 : null};
}

const compatible = evidence => evidence.seconds > 0 && evidence.metres > 0 &&
  evidence.mean_kmh <= CURRENT_PROFILE_SEGMENT_MEAN_CEILING_KMH + SPEED_ROUNDOFF_KMH;

// No model calls are emitted on failure: downstream renderers must not turn
// an impossible endpoint window or collapsed geometry into a moving marker.
export function reconcileCurrentDisplayProfile(sourceCalls, geometricCalls) {
  const failure = (reason, evidence = {}) => ({contract:"nodo8_current_display_profile_v1", semantics:{...PROFILE_SEMANTICS},
    feasible:false, failure:reason, evidence, kept_anchor_indices:[], dropped_anchor_indices:[], calls:[], legs:[], anchor_intervals:[]});
  if (!Array.isArray(sourceCalls) || !Array.isArray(geometricCalls) || sourceCalls.length < 2 || sourceCalls.length !== geometricCalls.length)
    return failure("INCOMPLETE_SOURCE_OR_GEOMETRIC_CALLS");
  if (sourceCalls.some((c, i) => !c || !Number.isFinite(c.arrival_min) || !Number.isFinite(c.departure_min) ||
      !Number.isFinite(c.sequence) || c.departure_min !== c.arrival_min ||
      c.stop_id !== geometricCalls[i]?.stop_id || c.sequence !== geometricCalls[i]?.sequence ||
      (i && c.sequence <= sourceCalls[i - 1].sequence)))
    return failure("UNSUPPORTED_SOURCE_CALL_OR_OCCURRENCE_ORDER");
  const chainages = geometricCalls.map(c => c.display_chainage_metres ?? c.chainage_metres);
  if (chainages.some((s, i) => !Number.isFinite(s) || s < 0 || (i && s <= chainages[i - 1])))
    return failure("GEOMETRIC_CALL_ORDER_NOT_STRICT", {chainages});
  const endpoint = interval(sourceCalls, chainages, 0, sourceCalls.length - 1);
  if (!compatible(endpoint)) return failure("ENDPOINT_WINDOW_EXCEEDS_DISPLAY_CEILING", endpoint);

  // Every DAG edge is a compatible pair of actual source clock anchors. The
  // longest path retains the most source anchors; lexicographic comparison of
  // equal-cardinality index sequences makes the result deterministic.
  const paths = Array(sourceCalls.length).fill(null); paths[0] = [0];
  for (let to = 1; to < sourceCalls.length; to++) {
    for (let from = 0; from < to; from++) {
      if (!paths[from] || !compatible(interval(sourceCalls, chainages, from, to))) continue;
      const candidate = [...paths[from], to], incumbent = paths[to];
      if (!incumbent || candidate.length > incumbent.length ||
          (candidate.length === incumbent.length && lexicallyEarlier(candidate, incumbent))) paths[to] = candidate;
    }
  }
  const kept_anchor_indices = paths.at(-1);
  if (!kept_anchor_indices) return failure("NO_COMPATIBLE_ENDPOINT_ANCHOR_PATH", endpoint);
  const retained = new Set(kept_anchor_indices);
  const dropped_anchor_indices = sourceCalls.map((_, i) => i).filter(i => !retained.has(i));
  const calls = sourceCalls.map((source, i) => ({stop_id:source.stop_id, sequence:source.sequence,
    chainage_metres:chainages[i], source_arrival_min:source.arrival_min, source_departure_min:source.departure_min,
    source_clock_retained:retained.has(i)}));
  const anchor_intervals = [];
  for (let anchor = 0; anchor < kept_anchor_indices.length - 1; anchor++) {
    const from = kept_anchor_indices[anchor], to = kept_anchor_indices[anchor + 1], evidence = interval(sourceCalls, chainages, from, to);
    anchor_intervals.push(evidence);
    for (let i = from; i <= to; i++) {
      const sourceTime = sourceCalls[i].arrival_min;
      const modelTime = retained.has(i) ? sourceTime : evidence.departure_min +
        (chainages[i] - chainages[from]) / evidence.metres * (evidence.arrival_min - evidence.departure_min);
      calls[i].display_arrival_min = modelTime;
      calls[i].display_departure_min = modelTime;
      calls[i].timing_basis = retained.has(i) ? "SOURCE_CLOCK_ANCHOR" : "CHAINAGE_INTERPOLATION_BETWEEN_RETAINED_SOURCE_CLOCKS";
      calls[i].interpolation_anchor_indices = retained.has(i) ? [i, i] : [from, to];
      calls[i].display_time_shift_seconds = (modelTime - sourceTime) * 60;
    }
  }
  const legs = calls.slice(0, -1).map((from, i) => {
    const to = calls[i + 1], seconds = (to.display_arrival_min - from.display_departure_min) * 60;
    const metres = to.chainage_metres - from.chainage_metres;
    const source = interval(sourceCalls, chainages, i, i + 1);
    return {from_index:i, to_index:i + 1, from_stop_id:from.stop_id, to_stop_id:to.stop_id,
      from_sequence:from.sequence, to_sequence:to.sequence, metres, seconds, mean_kmh:seconds > 0 ? metres / seconds * 3.6 : null,
      source_seconds:source.seconds, source_mean_kmh:source.mean_kmh};
  });
  if (legs.some(l => !compatible(l))) return failure("NUMERIC_PROFILE_FAILED_DISPLAY_CEILING", {legs});
  return {contract:"nodo8_current_display_profile_v1", semantics:{...PROFILE_SEMANTICS}, feasible:true,
    kept_anchor_indices, dropped_anchor_indices, calls, legs, anchor_intervals,
    summary:{calls:calls.length, retained_source_clock_anchors:kept_anchor_indices.length, derived_internal_clocks:dropped_anchor_indices.length,
      source_legs_over_ceiling:legs.filter(l => l.source_mean_kmh > CURRENT_PROFILE_SEGMENT_MEAN_CEILING_KMH + SPEED_ROUNDOFF_KMH).length,
      model_legs_over_ceiling:legs.filter(l => l.mean_kmh > CURRENT_PROFILE_SEGMENT_MEAN_CEILING_KMH + SPEED_ROUNDOFF_KMH).length,
      max_model_mean_kmh:Math.max(...legs.map(l => l.mean_kmh)),
      max_absolute_time_shift_seconds:Math.max(...calls.map(c => Math.abs(c.display_time_shift_seconds)))}};
}

export function reconcileCurrentDisplayProfiles(data, geometry) {
  const sourceTrips = new Map(data.trips.map(t => [t.id, t]));
  const trips = geometry.trips.map(trip => {
    const source = sourceTrips.get(trip.id);
    return {id:trip.id, route:trip.route, shape_id:trip.shape_id,
      ...reconcileCurrentDisplayProfile(source?.calls, trip.calls)};
  });
  const feasible = trips.filter(t => t.feasible);
  const sum = field => feasible.reduce((total, t) => total + t.summary[field], 0);
  return {contract:"nodo8_current_display_profiles_v1", semantics:{...PROFILE_SEMANTICS}, trips,
    summary:{trips:trips.length, feasible_trips:feasible.length, infeasible_trips:trips.length - feasible.length,
      calls:sum("calls"), retained_source_clock_anchors:sum("retained_source_clock_anchors"), derived_internal_clocks:sum("derived_internal_clocks"),
      source_legs_over_ceiling:sum("source_legs_over_ceiling"), model_legs_over_ceiling:sum("model_legs_over_ceiling"),
      max_model_mean_kmh:feasible.length ? Math.max(...feasible.map(t => t.summary.max_model_mean_kmh)) : null,
      max_absolute_time_shift_seconds:feasible.length ? Math.max(...feasible.map(t => t.summary.max_absolute_time_shift_seconds)) : null}};
}
