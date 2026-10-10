import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  playbackWindow,
  adjacentEvent,
  buildLine,
  statesAt,
  vehicleState,
  positionBetween,
  diagramStops,
  clockSeconds,
  siteTimetable,
  servicePhase,
} from "../nodo8-line.mjs";
import { readStopSelection, stopLink } from "../nodo8-stop-times.mjs";
import { inspectJourney, eventKey, journeyDurationLabel } from "../nodo8-journey-inspector.mjs";
import { buildRail, trainsAt, S8_COLOUR, installS8 } from "../nodo8-s8.mjs";
import { buildCurrent, currentTripsAt, currentPosition } from "../nodo8-current.mjs";
import { mountPlayer } from "../nodo8-player.mjs";
const currentData = JSON.parse(readFileSync(new URL("../assets/nodo8-current-simulation.json", import.meta.url), "utf8"));
test("existing-service simulation keeps dated stop occurrences, arrival and departure clocks", () => {
  const data = buildCurrent(currentData);
  assert.equal(data.service_date,"2026-05-06");
  for (const trip of data.trips) {
    for (const call of trip.calls) for (const minute of [call.arrival_min,call.departure_min]) {
      const state = currentTripsAt(data,minute).find(t=>t.id===trip.id);
      assert.equal(state.status,"stop");
      assert.deepEqual(state.coordinates,currentPosition(data.shapes[trip.shape_id],call.distance));
    }
    assert.ok(!currentTripsAt(data,trip.calls[0].arrival_min-0.001).some(t=>t.id===trip.id));
    assert.ok(!currentTripsAt(data,trip.calls.at(-1).departure_min+0.001).some(t=>t.id===trip.id));
  }
});
test("existing-service movement follows exact GTFS shapes, filters and reverses on the bus clock", () => {
  const data = buildCurrent(currentData);
  for (const trip of data.trips) {
    const a=trip.calls[0],b=trip.calls[1],minute=(a.departure_min+b.arrival_min)/2;
    const state=currentTripsAt(data,minute).find(t=>t.id===trip.id);
    assert.equal(state.status,"moving");
    const expected=currentPosition(data.shapes[trip.shape_id],(a.distance+b.distance)/2);
    state.coordinates.forEach((value,axis)=>assert.ok(Math.abs(value-expected[axis])<1e-10));
    for (const route of ["D184","D185"]) assert.ok(currentTripsAt(data,minute,route).every(t=>t.route===route));
  }
  const expected=currentTripsAt(data,415);currentTripsAt(data,900);assert.deepEqual(currentTripsAt(data,415),expected);
  const source=readFileSync(new URL("../nodo8-current.mjs",import.meta.url),"utf8");
  assert.doesNotMatch(source,/setInterval|requestAnimationFrame/);
  const overlay=readFileSync(new URL("../dietro-l-analisi/journey-nodo8.mjs",import.meta.url),"utf8");
  assert.match(overlay,/current\?\.render\(\{minute:state\.minute/);
});
test("current service cannot be relabelled latest, GPS, a fleet or unjoined shape", () => {
  for (const mutate of [d=>d.service_date="2026-10-09",d=>d.semantics.latest_2026_27_timetable=true,
    d=>d.semantics.live=true,d=>d.semantics.vehicle_identity_certified=true,d=>d.trips.pop(),
    d=>d.trips[0].shape_id="invented",d=>d.trips[0].calls[1].arrival_min=0]) {
    const copy=structuredClone(currentData);mutate(copy);assert.throws(()=>buildCurrent(copy));
  }
  assert.throws(()=>currentTripsAt(buildCurrent(currentData),NaN));
  assert.throws(()=>currentTripsAt(buildCurrent(currentData),455,"unknown"));
});
const s8Data = JSON.parse(readFileSync(new URL("../assets/nodo8-s8-simulation.json", import.meta.url), "utf8"));
test("S8 preserves all 74 dated calls, both directions, and smaller dedicated icons", () => {
  const rail = buildRail(s8Data);
  assert.equal(S8_COLOUR, "#f8b1b0");
  for (const train of rail.trains) {
    for (const call of train.calls) {
      for (const minute of [call.arrival_min, call.departure_min]) {
        const state = trainsAt(rail, minute).find(t => t.id === train.id);
        assert.deepEqual(state.coordinates, rail.stations.get(call.station_id).coordinates);
        assert.equal(state.status, "station");
      }
    }
    assert.ok(!trainsAt(rail, train.calls[0].arrival_min - 0.001).some(t => t.id === train.id));
    assert.ok(!trainsAt(rail, train.calls.at(-1).departure_min + 0.001).some(t => t.id === train.id));
  }
  assert.deepEqual(new Set(trainsAt(rail, 449).map(t => t.direction)), new Set(["MILANO", "LECCO"]));
  const module = readFileSync(new URL("../nodo8-s8.mjs", import.meta.url), "utf8");
  assert.match(module, /width="24" height="30"/);
  assert.doesNotMatch(module, /requestAnimationFrame|setInterval/);
});
test("S8 interpolates only along frozen railway vertices, and is reversible on the shared clock", () => {
  const rail = buildRail(s8Data);
  for (const train of rail.trains) {
    const minute = (train.calls[0].departure_min + train.calls[1].arrival_min) / 2;
    const state = trainsAt(rail, minute).find(t => t.id === train.id);
    assert.equal(state.status, "moving");
    const segment = rail.segments.find(s =>
      (s.from_id === train.calls[0].station_id && s.to_id === train.calls[1].station_id) ||
      (s.to_id === train.calls[0].station_id && s.from_id === train.calls[1].station_id));
    assert.ok(segment.coordinates.some((a, i) => {
      const b = segment.coordinates[i + 1];
      return b && state.coordinates.every((v, axis) => v >= Math.min(a[axis], b[axis]) - 1e-10 && v <= Math.max(a[axis], b[axis]) + 1e-10);
    }));
    const before = trainsAt(rail, minute);
    trainsAt(rail, minute + 20);
    assert.deepEqual(trainsAt(rail, minute), before);
  }
});
test("S8 fails closed on invented times, directions, guarantees or railway endpoints", () => {
  for (const mutate of [d => d.semantics.live = true, d => d.semantics.timetable_2027_certified = true,
    d => d.semantics.connection_guaranteed = true, d => d.trains.pop(), d => d.trains[0].direction = "UNKNOWN",
    d => d.trains[0].calls[1].arrival_min = 0, d => d.segments[0].coordinates[0] = [0, 0]]) {
    const copy = structuredClone(s8Data); mutate(copy); assert.throws(() => buildRail(copy));
  }
  assert.throws(() => trainsAt(buildRail(s8Data), NaN));
  const explorer = readFileSync(new URL("../dietro-l-analisi/journey-explore-v2.js", import.meta.url), "utf8");
  assert.match(explorer, /s8: false/);
  const overlay = readFileSync(new URL("../dietro-l-analisi/journey-nodo8.mjs", import.meta.url), "utf8");
  assert.match(overlay, /rail\?\.render\(\{minute: state\.minute, visible: railVisible\(\)\}\)/);
});
test("S8 marker receives coordinates before MapLibre addTo and toggles without residue", async () => {
  const saved = {fetch:globalThis.fetch, window:globalThis.window, document:globalThis.document};
  const attached = new Set(), paints = [];
  const status = {textContent:"",hidden:true};
  class Marker {
    constructor({element}) {this.element = element;}
    setLngLat(coordinates) {this.coordinates = coordinates; return this;}
    addTo() {assert.ok(this.coordinates); attached.add(this); return this;}
    remove() {attached.delete(this);}
  }
  try {
    globalThis.fetch = async () => ({ok:true,json:async()=>s8Data});
    globalThis.window = {maplibregl:{Marker}};
    globalThis.document = {documentElement:{dataset:{}},getElementById:()=>status,
      createElement:()=>({setAttribute(){},querySelector:()=>({textContent:""})})};
    const rail = await installS8({addSource(){},addLayer(){},setPaintProperty:(...args)=>paints.push(args)});
    rail.render({minute:449,visible:true});
  assert.equal(attached.size,trainsAt(buildRail(s8Data),449).length);
    assert.equal(document.documentElement.dataset.s8TrainCount,String(attached.size));
    rail.render({minute:455,visible:false});
    assert.equal(attached.size,0);
    assert.equal(paints.at(-1)[2],0);
    assert.equal(status.hidden,true);
  } finally {Object.assign(globalThis,saved);}
});
test("journey durations show minutes and seconds from the unrounded ledger value", () => {
  assert.equal(journeyDurationLabel(14.2), "14 min 12 s");
  assert.equal(journeyDurationLabel(14.161), "14 min 10 s");
  assert.equal(journeyDurationLabel(1.999), "2 min 00 s");
  assert.equal(journeyDurationLabel(0), "0 min 00 s");
  assert.throws(() => journeyDurationLabel(NaN));
  assert.throws(() => journeyDurationLabel(-1));
});
const data = JSON.parse(
  readFileSync(
    new URL("../assets/nodo8-proposal.json", import.meta.url),
    "utf8",
  ),
);
const line = buildLine(data);
const carrier = (n) =>
  line.vehicles.find((v) => v.blocks.some((t) => t.number === n));

test("journey inspector binds two ordered events in one trip and includes FS hold explicitly", () => {
  const before = JSON.stringify(data);
  for (const trip of line.trips) {
    const journey = inspectJourney(
      line,
      trip.number,
      eventKey(trip.events[1]),
      eventKey(trip.events[16]),
    );
    assert.equal(
      journey.minutes,
      trip.events[16].arrival - trip.events[1].departure,
    );
    assert.equal(
      journey.intermediateHoldMinutes,
      trip.events[15].departure - trip.events[15].arrival,
    );
    assert.equal(journey.carrier, carrier(trip.number).id);
    assert.equal(journey.passengerContinuityAuthorised, false);
    assert.equal(
      inspectJourney(
        line,
        trip.number,
        eventKey(trip.events[1]),
        eventKey(trip.events[14]),
      ).crossesFS,
      false,
    );
    assert.throws(() =>
      inspectJourney(
        line,
        trip.number,
        eventKey(trip.events[14]),
        eventKey(trip.events[1]),
      ),
    );
    assert.throws(() =>
      inspectJourney(
        line,
        trip.number,
        eventKey(trip.events[1]),
        eventKey(trip.events[1]),
      ),
    );
  }
  assert.throws(() => inspectJourney(line, 17, "unknown", "unknown"));
  assert.throws(() =>
    inspectJourney(line, 1, "unknown", eventKey(line.trips[0].events[12])),
  );
  assert.equal(JSON.stringify(data), before);
});

test("stop timetables copy all ledger events, including two occurrences and three FS roles", () => {
  const before = JSON.stringify(data);
  for (const site of line.sites.values()) {
    const shown = siteTimetable(line, site.site_id);
    assert.equal(shown.rows.length, 16);
    shown.rows.forEach((row, index) => {
      assert.equal(row.trip, index + 1);
      assert.deepEqual(
        row.events,
        line.trips[index].events.filter((e) => e.siteId === site.site_id),
      );
    });
    assert.equal(
      shown.columns.length,
      site.hub_service_roles.length ? 3 : site.ordered_occurrences.length,
    );
  }
  const hub = [...line.sites.values()].find((s) => s.hub_service_roles.length);
  assert.deepEqual(
    siteTimetable(line, hub.site_id).columns.map((c) => c.role),
    [
      "FULL_TRIP_START_FS",
      "INTERMEDIATE_FS_STAY_ONBOARD_DESIGN",
      "FULL_TRIP_END_FS",
    ],
  );
  assert.throws(() => siteTimetable(line, "missing"));
  assert.equal(JSON.stringify(data), before);
});

test("the progress strip distinguishes passenger start, both loops, FS wait and final arrival", () => {
  for (const trip of line.trips) {
    assert.equal(servicePhase(line, trip.number, trip.start), 0);
    assert.equal(servicePhase(line, trip.number, trip.events[1].arrival), 1);
    assert.equal(servicePhase(line, trip.number, trip.events[15].arrival), 2);
    assert.equal(servicePhase(line, trip.number, trip.events[15].departure), 3);
    assert.equal(servicePhase(line, trip.number, trip.end), 4);
    assert.throws(() => servicePhase(line, trip.number, trip.end + 1));
  }
});

test("stop deep links accept only certified IDs and correctly encode punctuation", () => {
  for (const site of line.sites.values()) {
    const url = new URL(stopLink(site.site_id), "https://example.test/tpl/");
    assert.equal(readStopSelection(line, url.href), site.site_id);
    assert.equal(url.hash, "#stopDetail");
  }
  assert.equal(
    readStopSelection(line, "https://example.test/?v=20261008e"),
    null,
  );
  assert.throws(() =>
    readStopSelection(line, "https://example.test/?site=not-certified"),
  );
});
test("one continuous road path retains all vertices and ordered occurrences", () => {
  assert.deepEqual(line.coordinates, [
    ...data.routes.find((r) => r.wing === "east_A").coordinates,
    ...data.routes.find((r) => r.wing === "west_B").coordinates.slice(1),
  ]);
  assert.equal(line.coordinates.length, 1436);
  assert.equal(line.trips.length, 16);
  line.trips.forEach((t) => {
    assert.equal(t.events.length, 31);
    assert.deepEqual(
      t.events.filter((e) => e.occurrenceId).map((e) => e.ordinal),
      Array.from({ length: 28 }, (_, i) => i + 1),
    );
    t.events
      .filter((e) => e.occurrenceId)
      .forEach((e) =>
        assert.deepEqual(
          e.coordinates,
          line.sites.get(e.siteId).coordinates_lon_lat,
        ),
      );
  });
});
test("all 448 stop dwell intervals are stationary at the exact event vertex", () => {
  line.trips.forEach((t) =>
    t.events
      .filter((e) => e.occurrenceId)
      .forEach((e) => {
        assert.ok(Math.abs(e.departure - e.arrival - 0.5) < 1e-8);
        for (const m of [e.arrival, e.arrival + 0.1, e.departure - 0.000001]) {
          const s = vehicleState(line, carrier(t.number), m);
          assert.equal(s.status, "stop");
          assert.equal(s.event.occurrenceId, e.occurrenceId);
          assert.deepEqual(s.coordinates, e.coordinates);
          assert.equal(s.trip, t.number);
        }
        assert.equal(
          vehicleState(line, carrier(t.number), e.departure).status,
          "moving",
        );
      }),
  );
});
test("intermediate FS is a stationary continuation of the same carrier and full trip", () => {
  line.trips.forEach((t) => {
    const fs = t.events[15],
      v = carrier(t.number);
    assert.equal(fs.node, line.middle);
    for (const m of [
      fs.arrival,
      (fs.arrival + fs.departure) / 2,
      fs.departure - 0.000001,
    ]) {
      const s = vehicleState(line, v, m);
      assert.equal(s.status, "fs-hold");
      assert.equal(s.id, v.id);
      assert.equal(s.trip, t.number);
      assert.deepEqual(s.coordinates, line.coordinates[0]);
    }
    const before = vehicleState(line, v, fs.arrival - 0.000001),
      after = vehicleState(line, v, fs.departure);
    assert.equal(before.status, "moving");
    assert.equal(after.status, "moving");
    assert.equal(before.id, after.id);
    assert.equal(before.trip, after.trip);
    assert.equal(after.next.ordinal, 15);
  });
});
test("terminal recovery is not passenger continuation or another service", () => {
  line.trips.forEach((t) => {
    const v = carrier(t.number),
      s = vehicleState(line, v, t.end);
    assert.equal(s.status, "recovery");
    assert.equal(s.event, null);
    assert.equal(s.next, null);
    assert.deepEqual(s.coordinates, line.coordinates.at(-1));
    assert.equal(vehicleState(line, v, t.end + 10).status, "off-service");
    assert.equal(vehicleState(line, v, t.end + 10).coordinates, null);
  });
});
test("07:35 has four complete-trip carriers, never separate wing fleets", () => {
  const states = statesAt(line, 455);
  assert.deepEqual(
    states.map((s) => s.trip),
    [1, 2, 3, 4],
  );
  assert.ok(states.every((s) => s.coordinates));
  assert.deepEqual(
    line.vehicles.map((v) => v.blocks.map((b) => b.number)),
    [
      [1, 5, 9, 13],
      [2, 6, 10, 14],
      [3, 7, 11, 15],
      [4, 8, 12, 16],
    ],
  );
  assert.ok(
    statesAt(line, line.end).every(
      (s) => s.status === "off-service" && s.coordinates === null,
    ),
  );
});
test("interpolation follows each road vertex rather than a stop-to-stop chord", () => {
  for (const t of line.trips.slice(0, 1)) {
    for (let i = 1; i < t.events.length; i++) {
      const a = t.events[i - 1],
        b = t.events[i];
      const total = line.lengths[b.node] - line.lengths[a.node];
      for (let n = a.node + 1; n < b.node; n++) {
        const f = (line.lengths[n] - line.lengths[a.node]) / total;
        const p = positionBetween(line, a.node, b.node, f);
        assert.ok(Math.abs(p[0] - line.coordinates[n][0]) < 1e-10);
        assert.ok(Math.abs(p[1] - line.coordinates[n][1]) < 1e-10);
      }
    }
  }
});
test("metro/locality diagrams preserve repeated events and cover every ordinal exactly once", () => {
  for (const simplified of [false, true]) {
    const entries = diagramStops(line, simplified);
    assert.deepEqual(
      entries.flatMap((e) => e.ordinals),
      Array.from({ length: 28 }, (_, i) => i + 1),
    );
    assert.equal(entries.filter((e) => e.display === "Olgiate Aldo Moro").length, 2);
    assert.equal(
      entries.filter((e) => e.display === "San Zeno / Via Cantù").length,
      2,
    );
  }
  assert.equal(diagramStops(line).length, 28);
  assert.equal(new Set(diagramStops(line).map((e) => e.siteId)).size, 26);
});
test("missing/reordered/invalid clocks, roads, authority or carrier assignment fail closed", () => {
  const changes = [
    (d) => {
      delete d.playback;
    },
    (d) => {
      d.playback.ledger[0].events[1].board_event_min = 300;
    },
    (d) => {
      d.playback.ledger[0].events.reverse();
    },
    (d) => {
      d.playback.ledger[0].events[1].full_path_edge_index++;
    },
    (d) => {
      d.playback.vehicles[0].trips[0].fs_end_min++;
    },
    (d) => {
      d.playback.vehicles[0].same_model_vehicle_through_intermediate_fs = false;
    },
    (d) => {
      d.playback.vehicles[0].trips.pop();
    },
    (d) => {
      d.authority.primary_selection_authorised = true;
    },
    (d) => {
      d.routes[0].coordinates[0][0] += 0.1;
    },
  ];
  changes.forEach((change) => {
    const d = structuredClone(data);
    change(d);
    assert.throws(() => buildLine(d));
  });
  for (const m of [NaN, line.start - 0.001, line.end + 0.001])
    assert.throws(() => statesAt(line, m));
});
test("half-second/second clocks do not round to an invented earlier arrival", () => {
  assert.equal(clockSeconds(458.3027038045449), "07:38:18");
  assert.equal(clockSeconds(365), "06:05:00");
});
test("presentation does not mutate the certified payload", () => {
  const before = JSON.stringify(data);
  const l = buildLine(data);
  diagramStops(l, true);
  statesAt(l, 455);
  assert.equal(JSON.stringify(data), before);
});
test("every minute in the complete design day has a well-defined state", () => {
  for (let m = line.start; m <= line.end; m++) {
    const states = statesAt(line, m);
    assert.equal(states.length, 4);
    states.forEach((s) => {
      assert.ok(
        ["moving", "stop", "fs-hold", "recovery", "off-service"].includes(
          s.status,
        ),
      );
      assert.equal(s.coordinates === null, s.status === "off-service");
      if (s.coordinates) assert.ok(s.coordinates.every(Number.isFinite));
    });
  }
});
test("single-trip view stops at passenger arrival, day view keeps certified recovery", () => {
  const first = playbackWindow(line, "1"),
    last = playbackWindow(line, "16"),
    day = playbackWindow(line, "all");
  assert.equal(first.start, line.trips[0].start);
  assert.equal(first.end, line.trips[0].end);
  assert.equal(last.end, line.trips[15].end);
  assert.equal(day.end, last.end + 10);
  assert.equal(day.trip, null);
  assert.throws(() => playbackWindow(line, "17"));
});
test("event stepping preserves FS role and repeated-stop occurrence order", () => {
  const events = line.trips[0].events;
  assert.equal(
    adjacentEvent(line, "1", events[14].arrival, 1).role,
    "INTERMEDIATE_FS_STAY_ONBOARD_DESIGN",
  );
  assert.equal(adjacentEvent(line, "1", events[15].arrival, 1).ordinal, 15);
  assert.equal(adjacentEvent(line, "1", events[15].arrival, -1).ordinal, 14);
  assert.equal(
    adjacentEvent(line, "1", events.at(-1).arrival, 1).role,
    "FULL_TRIP_END_FS",
  );
});

// These controls only need element ownership, attributes and event dispatch.
// Keep the fixture local so no browser library or active animation is required.
class PlayerElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.parent = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.dataset = {};
    this.style = {};
    this.className = "";
    this._text = "";
    this._value = "";
    this.disabled = false;
    this.hidden = false;
    this.classList = {
      contains: (name) => this.className.split(/\s+/).includes(name),
      add: (name) => {
        if (!this.classList.contains(name))
          this.className = `${this.className} ${name}`.trim();
      },
      toggle: (name, enabled) => {
        const names = this.className.split(/\s+/).filter((n) => n && n !== name);
        if (enabled) names.push(name);
        this.className = names.join(" ");
      },
    };
  }
  append(...children) {
    children.forEach((child) => {
      child.remove();
      child.parent = this;
      this.children.push(child);
    });
  }
  replaceChildren(...children) {
    this.children.forEach((child) => { child.parent = null; });
    this.children = [];
    this._text = "";
    this.append(...children);
  }
  remove() {
    if (!this.parent) return;
    this.parent.children = this.parent.children.filter((child) => child !== this);
    this.parent = null;
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, listener) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(listener);
  }
  dispatch(name) {
    this.listeners.get(name)?.forEach((listener) => listener({ target: this }));
  }
  click() { if (!this.disabled) this.dispatch("click"); }
  get value() { return this._value; }
  set value(value) { this._value = String(value); }
  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this.replaceChildren();
    this._text = String(value);
  }
}

const playerElement = (host, className) =>
  host.classList.contains(className)
    ? host
    : host.children.map((child) => playerElement(child, className)).find(Boolean);

function withPlayerDom(check) {
  const names = ["document", "window", "requestAnimationFrame", "cancelAnimationFrame"];
  const saved = new Map(names.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  const frames = new Map();
  let nextFrame = 0;
  try {
    globalThis.document = {
      createElement: (tag) => new PlayerElement(tag),
      addEventListener() {},
      hidden: false,
    };
    globalThis.window = {};
    globalThis.requestAnimationFrame = (callback) => {
      const id = ++nextFrame;
      frames.set(id, callback);
      return id;
    };
    globalThis.cancelAnimationFrame = (id) => frames.delete(id);
    const host = new PlayerElement("div");
    host.id = "test-player";
    check({
      host,
      frames,
      stepFrame: (now) => {
        const pending = [...frames.values()];
        frames.clear();
        pending.forEach((callback) => callback(now));
      },
    });
  } finally {
    saved.forEach((descriptor, name) => {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    });
  }
}

test("presentation stop holds the shared clock for 600ms, never adds dwell or skips crossed events",()=>{
  withPlayerDom(({host,stepFrame,frames})=>{
    let active=true,state;
    const stops=[500.1,500.2,500.3];
    const player=mountPlayer(host,line,update=>{state=update;},{overviewOnly:true,initialMinute:500,
      nextPresentationStop:(from,to)=>active ? stops.find(m=>m>from&&m<=to)??null : null});
    const speed=playerElement(host,"n8-speed").children.find(c=>c.tagName==="select");
    speed.value=300;speed.dispatch("change");
    player.toggle();stepFrame(0);stepFrame(1000);
    assert.equal(state.minute,500.1);assert.equal(state.presentationStop,true);
    assert.deepEqual(state.states,statesAt(line,500.1));
    stepFrame(1500);assert.equal(state.minute,500.1);
    stepFrame(1600);assert.equal(state.presentationStop,false);assert.equal(state.minute,500.1);
    stepFrame(1700);assert.equal(state.minute,500.2);assert.equal(state.presentationStop,true);
    active=false;stepFrame(1750);assert.equal(state.presentationStop,false);
    stepFrame(1850);assert.equal(state.minute,500.7,"hidden network does not cause holds");
    player.jump(500);assert.equal(state.playing,false);assert.equal(state.presentationStop,false);
    assert.equal(frames.size,0);assert.equal(player.getMinute(),500);
    active=true;player.toggle();stepFrame(2000);stepFrame(2100);
    assert.equal(state.minute,500.1);
    player.pause();assert.equal(frames.size,0);
    player.toggle();assert.equal(state.presentationStop,false);
    stepFrame(2200);stepFrame(2300);assert.equal(state.minute,500.2);
    player.pause();
  });
});

test("public stop rename keeps source identities, coordinates and data unchanged",()=>{
  const before=JSON.stringify(data);
  const renamed=buildLine(data);
  const events=renamed.trips[0].events.filter(e=>e.siteId==="RT031::P2V2S_0031_PROJECTED_ROAD_POINT");
  assert.equal(events.length,2);
  assert.ok(events.every(e=>e.name==="Olgiate Aldo Moro"));
  assert.equal(JSON.stringify(data),before);
});

test("overview player forces the four-bus day and omits trip controls and repeated explanations", () => {
  withPlayerDom(({ host }) => {
    let state;
    const player = mountPlayer(host, line, (update) => { state = update; }, {
      compact: true,
      brief: true,
      overviewOnly: true,
      initialSelection: "16",
    });
    assert.equal(state.selection, "all");
    assert.equal(state.followedTrip, null);
    assert.equal(player.getMinute(), 455);
    assert.deepEqual(state.states.map((bus) => bus.id), ["B1", "B2", "B3", "B4"]);
    assert.ok(state.states.every((bus) => bus.coordinates && bus.trip));
    assert.equal(playerElement(host, "n8-fleet").children.length, 4);
    for (const className of [
      "n8-player-title", "n8-player-modes", "n8-trip-select",
      "n8-current-event", "n8-event-navigation", "n8-player-details",
      "n8-route-continuity", "n8-playback-note", "n8-trip-progress",
      "n8-service-phases", "n8-vehicle-trip", "n8-vehicle-progress",
    ]) assert.equal(playerElement(host, className), undefined, className);
    assert.doesNotMatch(host.textContent, /Scegli la corsa|Come funziona|non dati GPS|prosecuzione sullo stesso bus/);
    assert.equal(playerElement(host, "n8-clock").textContent, "07:35:00");
    assert.ok(playerElement(host, "n8-play"));
    assert.ok(playerElement(host, "n8-reset"));
    const speed = playerElement(host, "n8-speed").children.find((child) => child.tagName === "select");
    assert.deepEqual(speed.children.map((option) => option.value), ["30", "120", "300"]);
  });
});

test("overview bus focus preserves all buses, playback, minute and slider bounds", () => {
  withPlayerDom(({ host }) => {
    let state;
    const focused = [];
    const player = mountPlayer(host, line, (update) => { state = update; }, {
      overviewOnly: true,
      onVehicleFocus: (id, bus) => focused.push({ id, bus }),
    });
    const range = host.children.find((child) => child.tagName === "input");
    const before = { min: range.min, max: range.max, value: range.value };
    const rows = playerElement(host, "n8-fleet").children;
    playerElement(host, "n8-play").click();
    rows[0].click();
    assert.equal(state.selection, "all");
    assert.equal(state.followedTrip, null);
    assert.equal(state.playing, true);
    assert.equal(player.getMinute(), 455);
    assert.deepEqual({ min: range.min, max: range.max, value: range.value }, before);
    assert.deepEqual(state.states, statesAt(line, 455));
    assert.equal(focused.length, 1);
    assert.equal(focused[0].id, "B1");
    assert.deepEqual(focused[0].bus, statesAt(line, 455)[0]);
    assert.equal(state.focusedVehicle, "B1");
    assert.equal(rows[0].getAttribute("aria-pressed"), "true");
    player.selectTrip(1);
    assert.equal(state.selection, "all");
    assert.equal(state.playing, true);
    assert.equal(player.getMinute(), 455);
    player.focusVehicle("B4");
    assert.equal(host.dataset.focusedVehicle, "B4");
    assert.equal(rows[0].getAttribute("aria-pressed"), "false");
    assert.equal(rows[3].getAttribute("aria-pressed"), "true");
    assert.equal(focused.length, 1, "programmatic focus does not repeat map callbacks");
    player.focusVehicle(null);
    assert.equal(host.dataset.focusedVehicle, undefined);
    assert.equal(state.focusedVehicle, null);
    assert.equal(player.getMinute(), 455);
    player.pause();
  });
});

test("overview slider, accelerated speeds, play/pause and reset use the unchanged day clock", () => {
  withPlayerDom(({ host, frames, stepFrame }) => {
    let state;
    const player = mountPlayer(host, line, (update) => { state = update; }, { overviewOnly: true });
    const range = host.children.find((child) => child.tagName === "input");
    const play = playerElement(host, "n8-play");
    const speed = playerElement(host, "n8-speed").children.find((child) => child.tagName === "select");
    const day = playbackWindow(line, "all");
    assert.equal(Number(range.min), day.start);
    assert.equal(Number(range.max), day.end);
    range.value = 500;
    range.dispatch("input");
    assert.equal(player.getMinute(), 500);
    assert.equal(state.playing, false);
    play.click();
    stepFrame(0);
    stepFrame(1000);
    assert.equal(player.getMinute(), 500.5, "default ×30 advances thirty simulated seconds");
    range.value = 500;
    range.dispatch("input");
    assert.equal(state.playing, false, "dragging the clock pauses playback");
    speed.value = 120;
    speed.dispatch("change");
    play.click();
    assert.equal(state.playing, true);
    assert.equal(play.getAttribute("aria-pressed"), "true");
    stepFrame(2000);
    stepFrame(3000);
    assert.equal(player.getMinute(), 502, "one real second advances two minutes at ×120");
    assert.equal(playerElement(host, "n8-clock").textContent, clockSeconds(502));
    speed.value = 300;
    speed.dispatch("change");
    stepFrame(4000);
    stepFrame(5000);
    assert.equal(player.getMinute(), 507, "speed changes preserve the clock and apply ×300");
    play.click();
    assert.equal(state.playing, false);
    assert.equal(play.getAttribute("aria-pressed"), "false");
    assert.equal(frames.size, 0);
    playerElement(host, "n8-reset").click();
    assert.equal(player.getMinute(), day.start);
    assert.equal(range.value, String(day.start));
    assert.equal(state.playing, false);
    range.value = day.end + 100;
    range.dispatch("input");
    assert.equal(player.getMinute(), day.end);
    assert.equal(state.completed, true);
    play.click();
    assert.equal(player.getMinute(), day.start);
    assert.equal(state.selection, "all");
    assert.equal(state.playing, true);
    player.pause();
  });
});

test("default and brief root players retain the trip picker, explanations and single-trip following", () => {
  for (const brief of [false, true]) withPlayerDom(({ host }) => {
    let state;
    const player = mountPlayer(host, line, (update) => { state = update; }, { brief });
    assert.equal(state.selection, "1");
    assert.equal(state.followedTrip, 1);
    assert.equal(player.getMinute(), line.trips[0].start);
    assert.ok(playerElement(host, "n8-player-title"));
    assert.ok(playerElement(host, "n8-player-modes"));
    assert.ok(playerElement(host, "n8-trip-select"));
    assert.ok(playerElement(host, "n8-event-navigation"));
    const details = playerElement(host, "n8-player-details");
    assert.ok(playerElement(details, "n8-speed"));
    assert.ok(playerElement(details, "n8-playback-note"));
    assert.ok(playerElement(details, "n8-route-continuity"));
    assert.match(host.textContent, /Scegli la corsa/);
    assert.match(host.textContent, /non dati GPS/);
    player.selectTrip("all");
    player.jump(455);
    playerElement(host, "n8-fleet").children[0].click();
    assert.equal(state.selection, "1");
    assert.equal(state.followedTrip, 1);
    assert.equal(player.getMinute(), 455);
    const select = playerElement(host, "n8-trip-select").children.find((child) => child.tagName === "select");
    select.value = "16";
    select.dispatch("change");
    assert.equal(state.selection, "16");
    assert.equal(state.followedTrip, 16);
    assert.equal(player.getMinute(), line.trips[15].start);
  });
});
