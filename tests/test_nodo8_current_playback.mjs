import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {buildCurrentPlayback,currentPlaybackTripsAt} from "../nodo8-current-playback.mjs";
import {buildCurrent,currentPositionQuality,currentTripsAt} from "../nodo8-current.mjs";
import {positionOnCurrentShape} from "../nodo8-current-geometry.mjs";

const read = path => JSON.parse(readFileSync(new URL("../"+path,import.meta.url),"utf8"));
const source = buildCurrent(read("assets/nodo8-current-simulation.json"));
const asset = read("assets/nodo8-current-playback.json"), proposal = read("assets/nodo8-proposal.json");
const model = buildCurrentPlayback(source,asset,proposal);

test("playback reproduces immutable evidence and a calendar-checked ordinary day before the diversion",()=>{
  const before=JSON.stringify(source), proposalBefore=JSON.stringify(proposal);
  buildCurrentPlayback(source,asset,proposal);
  assert.equal(JSON.stringify(source),before);assert.equal(JSON.stringify(proposal),proposalBefore);
  assert.equal(asset.display_service_date,"2026-04-28");
  assert.equal(asset.source_service_date,"2026-05-06");
  assert.deepEqual(asset.calendar_check.trip_ids,source.trips.map(t=>t.id).sort());
  for (const record of [asset.sources.raw_gtfs_projection,asset.sources.station_reference]) {
    const bytes=readFileSync(new URL("../"+record.path,import.meta.url),"utf8").replaceAll("\r\n","\n");
    assert.equal(createHash("sha256").update(bytes).digest("hex"),record.sha256);
  }
  assert.deepEqual([model.profiles.summary.trips,model.profiles.summary.retained_source_clock_anchors,
    model.profiles.summary.derived_internal_clocks,model.profiles.summary.model_legs_over_ceiling],[34,374,48,0]);
});

test("all 34 buses remain present continuously during their original trip windows, including the 48 bad source intervals",()=>{
  for(const trip of model.trips) {
    const first=trip.calls[0].arrival_min,last=trip.calls.at(-1).departure_min;
    for(let minute=first;minute<=last;minute+=1/6) {
      const state=currentPlaybackTripsAt(model,minute).find(t=>t.id===trip.id);
      assert.ok(state,trip.id+" "+minute);assert.ok(state.coordinates.every(Number.isFinite));
    }
    for(let i=1;i<trip.calls.length;i++) {
      const minute=(trip.calls[i-1].departure_min+trip.calls[i].arrival_min)/2;
      const raw=currentTripsAt(source,minute).find(t=>t.id===trip.id);
      if(!currentPositionQuality(source,{...raw,minute}).displayable)
        assert.ok(currentPlaybackTripsAt(model,minute).some(t=>t.id===trip.id));
    }
    assert.ok(!currentPlaybackTripsAt(model,first-.001).some(t=>t.id===trip.id));
    assert.ok(!currentPlaybackTripsAt(model,last+.001).some(t=>t.id===trip.id));
  }
});

test("call positions and intermediate animation times follow exact shape geometry, never stop-to-stop chords",()=>{
  for(const trip of model.trips) {
    for(const call of trip.displayCalls) {
      const state=currentPlaybackTripsAt(model,call.display_arrival_min).find(t=>t.id===trip.id);
      assert.deepEqual(state.coordinates,call.geometry.display_coordinates);
      if(call.source_clock_retained)assert.equal(call.display_arrival_min,call.source_arrival_min);
      else assert.equal(call.timing_basis,"CHAINAGE_INTERPOLATION_BETWEEN_RETAINED_SOURCE_CLOCKS");
    }
    for(let i=1;i<trip.displayCalls.length;i++) {
      const a=trip.displayCalls[i-1],b=trip.displayCalls[i],minute=(a.display_departure_min+b.display_arrival_min)/2;
      const state=currentPlaybackTripsAt(model,minute).find(t=>t.id===trip.id);
      const expected=positionOnCurrentShape(model.geometry.shapes[trip.shape_id],(a.chainage_metres+b.chainage_metres)/2);
      state.coordinates.forEach((value,axis)=>assert.ok(Math.abs(value-expected[axis])<1e-10));
    }
  }
});

test("display profile cannot be relabelled official, GPS, latest, physically certified or a changed source",()=>{
  for(const mutate of [a=>a.semantics.live=true,a=>a.semantics.official_timetable_repaired=true,
    a=>a.semantics.actual_vehicle_speed_certified=true,a=>a.display_service_date="2026-10-10",
    a=>a.calendar_check.trip_ids.pop(),a=>a.geometry.trips[0].calls[1].display_chainage_metres+=20,
    a=>a.profiles.trips[0].calls[1].display_arrival_min+=1,a=>a.profiles.trips.pop(),
    a=>a.sources.raw_gtfs_projection.sha256="0".repeat(64),
    a=>a.sources.station_reference.sha256="0".repeat(64),
    a=>a.source_audit.published_pdf_clock_anchors_used=true,
    a=>a.source_audit.source_clock_export_mechanism_certified=true,
    a=>a.summary.derived_internal_clocks=0]) {
    const copy=structuredClone(asset);mutate(copy);assert.throws(()=>buildCurrentPlayback(source,copy,proposal));
  }
  assert.throws(()=>currentPlaybackTripsAt(model,NaN));
  assert.throws(()=>currentPlaybackTripsAt(model,455,"invented"));
  const before=currentPlaybackTripsAt(model,455);currentPlaybackTripsAt(model,1000);
  assert.deepEqual(currentPlaybackTripsAt(model,455),before);
  assert.ok(currentPlaybackTripsAt(model,455,"D184").every(t=>t.route==="D184"));
});
