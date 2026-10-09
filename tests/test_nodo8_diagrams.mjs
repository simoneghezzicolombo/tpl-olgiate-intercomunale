import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildLine } from "../nodo8-line.mjs";
import {
  renderDiagram,
  makeBusMarker,
  updateBusMarker,
} from "../nodo8-experience.mjs";

const data = JSON.parse(
  readFileSync(
    new URL("../assets/nodo8-proposal.json", import.meta.url),
    "utf8",
  ),
);
const line = buildLine(data);

// A small DOM adapter keeps these route/accessibility checks dependency free.
// Browser layout and the actual SVG font metrics are checked separately.
class Element {
  constructor(tag) {
    this.tagName = tag;
    this.attributes = new Map();
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.style = {};
    this.ownText = "";
    this.classList = {
      toggle: (name, force) => {
        const values = new Set(this.className.split(" ").filter(Boolean));
        const enabled = force ?? !values.has(name);
        enabled ? values.add(name) : values.delete(name);
        this.className = [...values].join(" ");
        return enabled;
      },
    };
  }
  set className(value) {
    this.setAttribute("class", value);
  }
  get className() {
    return this.getAttribute("class") ?? "";
  }
  set textContent(value) {
    this.ownText = String(value);
    this.children = [];
  }
  get textContent() {
    return this.ownText + this.children.map((e) => e.textContent).join("");
  }
  get firstChild() {
    return this.children[0];
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  insertBefore(child, before) {
    this.children.splice(this.children.indexOf(before), 0, child);
  }
  addEventListener(name, handler) {
    this.listeners.set(name, handler);
  }
  async trigger(name, event = {}) {
    await this.listeners.get(name)?.(event);
  }
  click() {
    return this.trigger("click");
  }
  querySelectorAll(selector) {
    const matches = (e) =>
      selector.startsWith(".")
        ? e.className.split(" ").includes(selector.slice(1))
        : selector === "[role=button]"
          ? e.getAttribute("role") === "button"
          : e.tagName === selector;
    return this.children.flatMap((e) => [
      ...(matches(e) ? [e] : []),
      ...e.querySelectorAll(selector),
    ]);
  }
  cloneNode(deep) {
    const copy = new Element(this.tagName);
    copy.attributes = new Map(this.attributes);
    copy.ownText = this.ownText;
    if (deep) copy.children = this.children.map((e) => e.cloneNode(true));
    return copy;
  }
}

async function withDOM(run) {
  const previous = { document: globalThis.document, window: globalThis.window };
  globalThis.document = {
    createElement: (tag) => new Element(tag),
    createElementNS: (_namespace, tag) => new Element(tag),
  };
  globalThis.window = {
    matchMedia: () => ({ matches: false, addEventListener() {} }),
  };
  try {
    await run();
  } finally {
    Object.assign(globalThis, previous);
  }
}

const container = (id) => Object.assign(new Element("div"), { id });
const drawing = (host) => host.querySelectorAll("svg")[0];

test("circular stop schema shows 26 unique nonhub sites while preserving 28 ordered events and three FS roles", async () => {
  await withDOM(async () => {
    const before = JSON.stringify(data),
      host = container("stops"),
      selected = [];
    renderDiagram(host, line, {
      onSelect: (site) => selected.push(site.site_id),
    });
    const image = drawing(host),
      groups = image.querySelectorAll(".n8-diagram-stop");
    assert.equal(
      image
        .querySelectorAll(".n8-diagram-line")
        .filter((e) => e.tagName === "circle").length,
      2,
    );
    assert.equal(groups.length, 26);
    const representativeEvents = line.trips[0].events.filter(
      (e) => e.ordinal && ![14, 28].includes(e.ordinal),
    );
    assert.deepEqual(
      groups.map((g) => g.getAttribute("data-occurrence")),
      representativeEvents.map((e) => e.occurrenceId),
    );
    assert.deepEqual(
      groups.flatMap((g) => g.getAttribute("data-ordinals").split(" ").map(Number)).sort((a, b) => a - b),
      Array.from({ length: 28 }, (_, i) => i + 1),
    );
    assert.equal(new Set(groups.map((g) => g.getAttribute("data-site"))).size, 26);
    const shared = image.querySelectorAll(".n8-diagram-stop--shared");
    assert.equal(shared.length, 2);
    assert.deepEqual(shared.map((g) => g.getAttribute("data-ordinals")), ["1 14", "15 28"]);
    assert.deepEqual(shared.map((g) => g.querySelectorAll(".n8-diagram-number")[0].textContent), ["1·14", "15·28"]);
    for (const [i, group] of shared.entries()) {
      const dot = group.querySelectorAll("circle")[0];
      const name = group.querySelectorAll(".n8-diagram-name")[0];
      assert.equal(dot.getAttribute("cx"), "600");
      assert.equal(dot.getAttribute("cy"), i ? "960" : "820");
      assert.equal(name.getAttribute("x"), "600");
      assert.equal(name.getAttribute("text-anchor"), "middle");
      assert.equal(group.getAttribute("data-occurrences").split(" ").length, 2);
    }
    let prevented = 0;
    for (const group of groups) {
      assert.equal(group.getAttribute("role"), "button");
      assert.equal(group.getAttribute("tabindex"), "0");
      await group.trigger("click");
      await group.trigger("keydown", {
        key: "Enter",
        preventDefault() {
          prevented++;
        },
      });
      await group.trigger("keydown", {
        key: " ",
        preventDefault() {
          prevented++;
        },
      });
    }
    assert.equal(prevented, 52);
    assert.deepEqual(
      selected,
      representativeEvents.flatMap((e) => [e.siteId, e.siteId, e.siteId]),
    );
    const list = host.querySelectorAll(".n8-ordered-list")[0];
    assert.equal(list.children.length, 31);
    assert.match(list.children[0].textContent, /FS · partenza/);
    assert.match(list.children[15].textContent, /FS · sosta e prosecuzione/);
    assert.match(list.children[30].textContent, /FS · arrivo/);
    assert.equal(image.textContent.includes("\u2014"), false);
    assert.equal(JSON.stringify(data), before);
  });
});

test("conceptual localities form two mirrored regular pentagons, with arrows on both loops", async () => {
  await withDOM(async () => {
    const host = container("localities");
    renderDiagram(host, line, { localities: true });
    const image = drawing(host),
      groups = image.querySelectorAll(".n8-diagram-locality");
    assert.deepEqual(
      groups.map((g) => g.getAttribute("data-locality")),
      [
        "San Zeno",
        "Beverate",
        "Brivio",
        "Arlate",
        "Calco",
        "Canova / Beolco",
        "Monticello",
        "Santa Maria Hoè",
        "Perego",
        "Rovagnate",
      ],
    );
    const loops = image
      .querySelectorAll(".n8-diagram-line")
      .filter((e) => e.tagName === "circle");
    assert.equal(loops.length, 2);
    const points = groups.map(group => {
      const dot = group.querySelectorAll(".n8-locality-node")[0];
      return {x: Number(dot.getAttribute("cx")), y: Number(dot.getAttribute("cy"))};
    });
    for (const [index, cy] of [[0, 350], [1, 1120]]) {
      const pentagon = points.slice(index * 5, index * 5 + 5);
      assert.ok(Math.abs(pentagon.reduce((sum, p) => sum + p.x, 0) / 5 - 600) < 1e-9);
      assert.ok(Math.abs(pentagon.reduce((sum, p) => sum + p.y, 0) / 5 - cy) < 1e-9);
      const expectedChord = 480 * Math.sin(Math.PI / 5);
      pentagon.forEach((p, i) => {
        const next = pentagon[(i + 1) % 5];
        assert.ok(Math.abs(Math.hypot(p.x - 600, p.y - cy) - 240) < 1e-9);
        assert.ok(Math.abs(Math.hypot(p.x - next.x, p.y - next.y) - expectedChord) < 1e-9);
        assert.ok(Math.abs(p.x - points[5 + i].x) < 1e-9);
      });
    }
    for (let i = 0; i < 5; i++) assert.ok(Math.abs(points[i].y + points[i + 5].y - 1470) < 1e-9);
    for (const group of groups) {
      const dot = group.querySelectorAll(".n8-locality-node")[0];
      const text = group.querySelectorAll(".n8-diagram-name")[0];
      assert.equal(text.getAttribute("text-anchor"), "middle");
      assert.equal(text.getAttribute("x"), dot.getAttribute("cx"));
      assert.equal(Number(dot.getAttribute("r")), 82);
      assert.ok(
        Math.abs(
          Number(text.getAttribute("y")) - Number(dot.getAttribute("cy")),
        ) < 20,
      );
      assert.ok(
        text.children.every(
          (span) => span.getAttribute("x") === dot.getAttribute("cx"),
        ),
      );
    }
    assert.equal(image.querySelectorAll(".n8-diagram-connector").length, 1);
    assert.equal(
      image.querySelectorAll(".n8-diagram-connector")[0].getAttribute("d"),
      "M600 590 V692 M600 782 V880",
    );
    const arrows = image.querySelectorAll(".n8-diagram-arrow");
    assert.equal(arrows.length, 10);
    assert.ok(
      arrows.slice(0, 5).every(
        (e) => e.getAttribute("data-direction") === "counterclockwise",
      ),
    );
    assert.ok(
      arrows.slice(0, 5).every(
        (e) =>
          Number(
            e.getAttribute("transform").match(/translate\([^ ]+ ([^)]+)\)/)[1],
          ) < 640,
      ),
    );
    assert.ok(arrows.slice(5).every(e => e.getAttribute("data-direction") === "clockwise"));
    assert.ok(arrows.slice(5).every(e => Number(e.getAttribute("transform").match(/translate\([^ ]+ ([^)]+)\)/)[1]) > 800));
    assert.ok(!image.querySelectorAll(".n8-diagram-locality").some(e => e.getAttribute("data-locality") === "Vaccarezza"));
    assert.match(image.textContent, /Riferimenti territoriali, non fermate/);
    assert.equal(image.querySelectorAll(".n8-diagram-number").length, 0);
    assert.equal(image.textContent.includes("ALA EST"), false);
    assert.equal(image.textContent.includes("ALA OVEST"), false);
  });
});

test("diagram SVG download includes styles and dimensions and removes interactive roles", async () => {
  await withDOM(async () => {
    const previous = {
      fetch: globalThis.fetch,
      XMLSerializer: globalThis.XMLSerializer,
      setTimeout: globalThis.setTimeout,
    };
    const previousCreate = URL.createObjectURL,
      previousRevoke = URL.revokeObjectURL;
    const blobs = [],
      filenames = [];
    globalThis.fetch = async () => ({
      ok: true,
      text: async () => ".n8-diagram-line { stroke: green; }",
    });
    globalThis.XMLSerializer = class {
      serializeToString(element) {
        const serialise = (e) =>
          `<${e.tagName} ${[...e.attributes].map(([k, v]) => `${k}="${v}"`).join(" ")}>${e.ownText}${e.children.map(serialise).join("")}</${e.tagName}>`;
        return serialise(element);
      }
    };
    globalThis.setTimeout = (handler) => {
      handler();
      return 0;
    };
    URL.createObjectURL = (blob) => {
      blobs.push(blob);
      return "blob:diagram";
    };
    URL.revokeObjectURL = () => {};
    const createElement = document.createElement;
    document.createElement = (tag) => {
      const element = createElement(tag);
      if (tag === "a") element.click = () => filenames.push(element.download);
      return element;
    };
    try {
      for (const localities of [false, true]) {
        const host = container("export" + localities);
        renderDiagram(host, line, { localities, onSelect() {} });
        const button = host
          .querySelectorAll("button")
          .find((e) => e.textContent.startsWith("Scarica"));
        await button.trigger("click");
        assert.equal(button.disabled, false);
      }
      assert.deepEqual(filenames, ["nodo8-fermate.svg", "nodo8-localita.svg"]);
      for (const [i, blob] of blobs.entries()) {
        const payload = await blob.text();
        assert.match(payload, /<style[^>]*>\.n8-diagram-line/);
        assert.match(payload, /xmlns="http:\/\/www.w3.org\/2000\/svg"/);
        assert.match(payload, /width="1200"/);
        assert.match(payload, new RegExp(`height="${i ? 1510 : 1760}"`));
        assert.match(payload, /role="img"/);
        assert.equal(payload.includes('role="button"'), false);
        assert.equal(payload.includes('tabindex="0"'), false);
      }
    } finally {
      Object.assign(globalThis, previous);
      URL.createObjectURL = previousCreate;
      URL.revokeObjectURL = previousRevoke;
    }
  });
});

test("raw stop punctuation is cleaned only for displayed marker text", async () => {
  await withDOM(async () => {
    const marker = makeBusMarker("B1"),
      state = { id: "B1", trip: 1, status: "stop", label: "Arlate\u2014N1212" };
    updateBusMarker(marker, state);
    assert.equal(state.label, "Arlate\u2014N1212");
    assert.match(marker.title, /Arlate, N1212/);
    assert.equal(marker.getAttribute("aria-label").includes("\u2014"), false);
  });
});
