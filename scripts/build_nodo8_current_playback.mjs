// Derived playback only: the frozen raw projection is never rewritten.
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {createHash} from "node:crypto";
import {readFileSync, writeFileSync} from "node:fs";
import {resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {reconstructCurrentGeometry, applyDisplayOccurrenceAnchors, currentFsStationEvidence} from "../nodo8-current-geometry.mjs";
import {reconcileCurrentDisplayProfiles} from "../nodo8-current-profile.mjs";

const ROOT = new URL("../", import.meta.url);
const RAW_PATH = "assets/nodo8-current-simulation.json";
const PROPOSAL_PATH = "assets/nodo8-proposal.json";
const OUT = new URL("assets/nodo8-current-playback.json", ROOT);
const RAW_SHA256 = "25cbd96b4939acb02fc018448bb20a3e9b605b4aa924a348638ed2fa7848ce97";
const GTFS_SHA256 = "f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b";
const HASH_SEMANTICS = "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF";
const normaliseLf = bytes => bytes.toString("utf8").replaceAll("\r\n", "\n");
const digest = bytes => createHash("sha256").update(normaliseLf(bytes), "utf8").digest("hex");
const plainJson = value => JSON.parse(JSON.stringify(value));

export function buildCurrentPlayback() {
  const rawUrl = new URL(RAW_PATH, ROOT), proposalUrl = new URL(PROPOSAL_PATH, ROOT);
  const rawBytes = readFileSync(rawUrl), proposalBytes = readFileSync(proposalUrl);
  assert.equal(digest(rawBytes), RAW_SHA256, "The immutable dated GTFS projection has changed");
  const data = JSON.parse(rawBytes.toString("utf8")), proposal = JSON.parse(proposalBytes.toString("utf8"));
  assert.equal(data.source.sha256, GTFS_SHA256, "The raw projection must cite the frozen official GTFS");
  assert.equal(data.service_date, "2026-05-06", "The raw snapshot date must remain unchanged");
  const sourceDataBefore = JSON.stringify(data), proposalBefore = JSON.stringify(proposal);
  const python = process.env.NODO8_PYTHON || (process.platform === "win32" ? "python" : "python3");
  const calendar_check = JSON.parse(execFileSync(python,
    [fileURLToPath(new URL("scripts/check_nodo8_current_reference_day.py", ROOT))],
    {cwd:fileURLToPath(ROOT), encoding:"utf8", stdio:["ignore", "pipe", "pipe"]}));
  assert.equal(calendar_check.service_date, "2026-04-28");
  assert.equal(calendar_check.archive_sha256, GTFS_SHA256);
  assert.deepEqual(calendar_check.route_counts, data.route_counts);
  assert.deepEqual(calendar_check.trip_ids, data.trips.map(trip => trip.id).sort());
  const station_reference = currentFsStationEvidence(proposal);
  const geometry = applyDisplayOccurrenceAnchors(data, reconstructCurrentGeometry(data), station_reference);
  const profiles = reconcileCurrentDisplayProfiles(data, geometry);
  assert.deepEqual([profiles.summary.trips, profiles.summary.feasible_trips, profiles.summary.infeasible_trips], [34, 34, 0]);
  assert.deepEqual([profiles.summary.calls, profiles.summary.retained_source_clock_anchors,
    profiles.summary.derived_internal_clocks, profiles.summary.model_legs_over_ceiling], [422, 374, 48, 0]);
  assert.equal(geometry.display_anchor_summary.anchored_return_calls, 12);
  assert.equal(geometry.display_anchor_summary.unchanged_statale_departure_calls, 10);
  assert.equal(JSON.stringify(data), sourceDataBefore, "Reconstruction must not mutate source data");
  assert.equal(JSON.stringify(proposal), proposalBefore, "Reconstruction must not mutate the frozen station evidence");
  assert.deepEqual(readFileSync(rawUrl), rawBytes, "The raw projection bytes must remain unchanged");
  assert.deepEqual(readFileSync(proposalUrl), proposalBytes, "The proposal bytes must remain unchanged");
  return {
    contract:"nodo8_existing_service_reconciled_playback_v2",
    display_service_date:calendar_check.service_date,
    source_service_date:data.service_date,
    sources:{
      raw_gtfs_projection:{path:RAW_PATH, sha256:RAW_SHA256, sha256_semantics:HASH_SEMANTICS},
      official_gtfs:{...data.source},
      station_reference:{path:PROPOSAL_PATH, sha256:digest(proposalBytes), sha256_semantics:HASH_SEMANTICS},
    },
    station_reference,
    calendar_check,
    source_audit:{
      clock_evidence:"UNCHANGED_FROZEN_OFFICIAL_GTFS_STOP_TIMES",
      timetable_timepoint_column_present:false,
      source_calls:422,
      source_calls_with_distinct_arrival_departure:0,
      source_clock_export_mechanism_certified:false,
      published_pdf_clock_anchors_used:false,
      display_profile_anchor_basis:"MAXIMUM_COMPATIBLE_SUBSET_OF_SOURCE_CLOCKS",
    },
    semantics:{
      live:false,
      latest_2026_27_timetable:false,
      vehicle_identity_certified:false,
      official_timetable_repaired:false,
      source_clocks_unchanged:true,
      derived_intermediate_times:true,
      physical_stop_relocated:false,
      actual_vehicle_speed_certified:false,
    },
    geometry:plainJson(geometry),
    profiles,
    summary:{...profiles.summary},
  };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const arguments_ = process.argv.slice(2);
  if (arguments_.some(argument => argument !== "--check")) throw new Error("Only --check is supported");
  const asset = buildCurrentPlayback(), payload = JSON.stringify(asset) + "\n";
  if (arguments_.includes("--check")) {
    assert.equal(normaliseLf(readFileSync(OUT)), payload, "The playback asset does not reproduce the frozen sources and model");
  } else {
    writeFileSync(OUT, payload, "utf8");
  }
  console.log(JSON.stringify({action:arguments_.includes("--check") ? "checked" : "built",
    asset:"assets/nodo8-current-playback.json", display_service_date:asset.display_service_date,
    ...asset.summary, fs_return_display_anchors:asset.geometry.display_anchor_summary.anchored_return_calls}));
}
