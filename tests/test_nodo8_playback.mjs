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
    assert.equal(entries.filter((e) => e.display === "Olgiate sud").length, 2);
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
