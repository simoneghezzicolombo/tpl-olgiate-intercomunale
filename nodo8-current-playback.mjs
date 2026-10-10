/* A derived animation model, separate from the immutable official GTFS projection. */
import { reconstructCurrentGeometry, currentFsStationEvidence, applyDisplayOccurrenceAnchors, positionOnCurrentShape } from "./nodo8-current-geometry.mjs?v=20261010b";
import { reconcileCurrentDisplayProfiles } from "./nodo8-current-profile.mjs?v=20261010b";

const plain = value => JSON.parse(JSON.stringify(value));
function equalEvidence(actual, expected, path = "model") {
  if (typeof expected === "number") {
    if (!Number.isFinite(actual) || Math.abs(actual - expected) > 1e-7 * Math.max(1, Math.abs(expected)))
      throw new Error("Reconciled display evidence mismatch: " + path);
  } else if (expected === null || typeof expected !== "object") {
    if (actual !== expected) throw new Error("Reconciled display evidence mismatch: " + path);
  } else {
    if (!actual || Array.isArray(actual) !== Array.isArray(expected) ||
        JSON.stringify(Object.keys(actual).sort()) !== JSON.stringify(Object.keys(expected).sort()))
      throw new Error("Reconciled display evidence shape mismatch: " + path);
    for (const key of Object.keys(expected)) equalEvidence(actual[key], expected[key], path + "." + key);
  }
}

export function buildCurrentPlayback(source, asset, proposal) {
  if (asset?.contract !== "nodo8_existing_service_reconciled_playback_v2" ||
      asset.display_service_date !== "2026-04-28" || asset.source_service_date !== source.service_date ||
      asset.source_service_date !== "2026-05-06" ||
      asset.sources?.raw_gtfs_projection?.path !== "assets/nodo8-current-simulation.json" ||
      asset.sources.raw_gtfs_projection.sha256 !== "25cbd96b4939acb02fc018448bb20a3e9b605b4aa924a348638ed2fa7848ce97" ||
      asset.sources.raw_gtfs_projection.sha256_semantics !== "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF" ||
      asset.sources.station_reference?.path !== "assets/nodo8-proposal.json" ||
      asset.sources.station_reference.sha256 !== "dd9b8bda3f5dc0bc039d0ab5874f8a64ff9f76db860f625657997fb7af34a8c9" ||
      asset.sources.station_reference.sha256_semantics !== "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF" ||
      asset.sources.official_gtfs?.sha256 !== source.source?.sha256 ||
      source.source?.sha256 !== "f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b" ||
      asset.calendar_check?.service_date !== asset.display_service_date ||
      asset.calendar_check.archive_sha256 !== source.source.sha256 ||
      JSON.stringify(asset.calendar_check.route_counts) !== JSON.stringify({D184:15,D185:19}) ||
      JSON.stringify(asset.calendar_check.trip_ids) !== JSON.stringify(source.trips.map(t => t.id).sort()))
    throw new Error("Unsupported reconciled current-service display contract");
  for (const key of ["live","latest_2026_27_timetable","vehicle_identity_certified","official_timetable_repaired",
    "physical_stop_relocated","actual_vehicle_speed_certified"])
    if (asset.semantics?.[key] !== false) throw new Error("Display estimates relabelled as operating evidence");
  for (const key of ["source_clocks_unchanged","derived_intermediate_times"])
    if (asset.semantics?.[key] !== true) throw new Error("Source/display clock distinction missing");
  const station = currentFsStationEvidence(proposal);
  const geometry = plain(applyDisplayOccurrenceAnchors(source, reconstructCurrentGeometry(source), station));
  const profiles = reconcileCurrentDisplayProfiles(source, geometry);
  equalEvidence(asset.sources.official_gtfs,source.source,"official_gtfs");
  equalEvidence(asset.source_audit,{
    clock_evidence:"UNCHANGED_FROZEN_OFFICIAL_GTFS_STOP_TIMES",
    timetable_timepoint_column_present:false,
    source_calls:422,
    source_calls_with_distinct_arrival_departure:0,
    source_clock_export_mechanism_certified:false,
    published_pdf_clock_anchors_used:false,
    display_profile_anchor_basis:"MAXIMUM_COMPATIBLE_SUBSET_OF_SOURCE_CLOCKS",
  },"source_audit");
  equalEvidence(asset.station_reference,station,"station_reference");
  equalEvidence(asset.geometry,geometry,"geometry");
  equalEvidence(asset.profiles,profiles,"profiles");
  equalEvidence(asset.summary,profiles.summary,"summary");
  if (profiles.summary.trips !== 34 || profiles.summary.feasible_trips !== 34 ||
      profiles.summary.calls !== 422 || profiles.summary.retained_source_clock_anchors !== 374 ||
      profiles.summary.derived_internal_clocks !== 48 || profiles.summary.model_legs_over_ceiling !== 0 ||
      geometry.display_anchor_summary.anchored_return_calls !== 12)
    throw new Error("Incomplete reconciled current-service display");
  const geometricTrips = new Map(geometry.trips.map(t => [t.id,t]));
  const profileTrips = new Map(profiles.trips.map(t => [t.id,t]));
  return {source,asset,geometry,profiles,trips:source.trips.map(t => ({...t,
    displayCalls:profileTrips.get(t.id).calls.map((c,i) => ({...c,
      geometry:geometricTrips.get(t.id).calls[i], sourceCall:t.calls[i]}))}))};
}

const callLabel = call => call.geometry.display_role === "FS_RAIL_RETURN_SHAPE_ENDPOINT" ? "Olgiate FS · arrivo" :
  call.geometry.display_role === "FS_VIA_STATALE_SHAPE_START" ? "Olgiate · FS via Statale" : call.sourceCall.name;

// Playback punctuation, not inferred operating dwell. Same clock for every network.
export function nextCurrentPresentationStop(model, from, to, selection = "ALL") {
  if (!Number.isFinite(from) || !Number.isFinite(to) || to < from ||
      !["ALL", "D184", "D185"].includes(selection)) throw new Error("Invalid presentation interval");
  let next = null;
  for (const trip of model.trips) {
    if (selection !== "ALL" && selection !== trip.route) continue;
    for (const call of trip.displayCalls) {
      const minute = call.display_arrival_min;
      if (minute > from && minute <= to && (next === null || minute < next)) next = minute;
    }
  }
  return next;
}

export function currentPlaybackTripsAt(model, minute, selection = "ALL") {
  if (!Number.isFinite(minute) || !["ALL","D184","D185"].includes(selection)) throw new Error("Invalid display clock or line");
  const states = [];
  for (const trip of model.trips) {
    if (selection !== "ALL" && selection !== trip.route) continue;
    const calls = trip.displayCalls;
    if (minute < calls[0].display_arrival_min || minute > calls.at(-1).display_departure_min) continue;
    for (let i = 0; i < calls.length; i++) {
      const call = calls[i], next = calls[i + 1];
      if (minute >= call.display_arrival_min && minute <= call.display_departure_min) {
        states.push({...trip,coordinates:[...call.geometry.display_coordinates],status:"stop",label:callLabel(call),
          timing_basis:call.timing_basis,derived_position:true});
        break;
      }
      if (next && minute > call.display_departure_min && minute < next.display_arrival_min) {
        const fraction = (minute - call.display_departure_min) / (next.display_arrival_min - call.display_departure_min);
        const chainage = call.chainage_metres + fraction * (next.chainage_metres - call.chainage_metres);
        states.push({...trip,coordinates:positionOnCurrentShape(model.geometry.shapes[trip.shape_id],chainage),
          status:"moving",label:"Verso " + callLabel(next),derived_position:true,
          timing_basis:"RECONCILED_DISPLAY_PROFILE"});
        break;
      }
    }
  }
  return states;
}
