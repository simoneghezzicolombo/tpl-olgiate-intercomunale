import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  makeNodo8Features,
  validateNodo8,
  NODO8_SCENES,
} from "../dietro-l-analisi/journey-nodo8.mjs";

const data = JSON.parse(
  readFileSync(
    new URL("../assets/nodo8-proposal.json", import.meta.url),
    "utf8",
  ),
);
test("overlay copies every confirmed road coordinate, not historical anchors", () => {
  const before = JSON.stringify(data);
  const shown = makeNodo8Features(data);
  assert.equal(shown.routes.features.length, 2);
  shown.routes.features.forEach((feature, index) => {
    assert.deepEqual(
      feature.geometry.coordinates,
      data.routes[index].coordinates,
    );
    assert.equal(feature.properties.wing, data.routes[index].wing);
    assert.equal(feature.properties.source, data.sources.geometry.path);
  });
  assert.equal(JSON.stringify(data), before);
});
test("27 distinct sites, four new sites, and two-event sites remain explicit", () => {
  const shown = makeNodo8Features(data).sites.features;
  assert.equal(shown.length, 27);
  assert.equal(new Set(shown.map((site) => site.properties.site_id)).size, 27);
  assert.equal(
    shown.filter((site) => site.properties.proposed_new_site).length,
    4,
  );
  assert.equal(
    shown.reduce((count, site) => count + site.properties.occurrence_count, 0),
    28,
  );
  assert.equal(
    shown.find((site) => site.properties.name === "Olgiate sud").properties
      .occurrence_count,
    2,
  );
  assert.equal(
    shown.find((site) => site.properties.name === "San Zeno/Via Cantu")
      .properties.occurrence_count,
    2,
  );
  assert.ok(
    shown.every((site) => site.properties.boarding_authorised === false),
  );
});
test("historical finalist and time scenes are not current-proposal scenes", () => {
  assert.deepEqual(NODO8_SCENES, ["nodo8", "nodo8-time", "end"]);
  assert.ok(!NODO8_SCENES.includes("finalists"));
  assert.ok(!NODO8_SCENES.includes("time"));
});
test("changed authority, incomplete sites or calendar fail closed", () => {
  for (const change of [
    (value) => {
      value.authority.primary_selection_authorised = true;
    },
    (value) => {
      value.authority.runner_up_selection_authorised = true;
    },
    (value) => {
      value.authority.public_operating_timetable_authorised = true;
    },
    (value) => {
      value.sites.pop();
    },
    (value) => {
      value.trips.pop();
    },
    (value) => {
      value.calendar.service_year = 2028;
    },
  ]) {
    const changed = structuredClone(data);
    change(changed);
    assert.throws(() => validateNodo8(changed));
  }
});
