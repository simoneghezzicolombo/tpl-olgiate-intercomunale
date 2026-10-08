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

test("circular stop schema preserves all 28 ordered selections and three FS roles", async () => {
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
    assert.equal(groups.length, 28);
    assert.deepEqual(
      groups.map((g) => g.getAttribute("data-occurrence")),
      line.trips[0].events.filter((e) => e.ordinal).map((e) => e.occurrenceId),
    );
    assert.deepEqual(
      groups.map((g) =>
        Number(g.querySelectorAll(".n8-diagram-number")[0].textContent),
      ),
      Array.from({ length: 28 }, (_, i) => i + 1),
    );
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
    assert.equal(prevented, 56);
    assert.deepEqual(
      selected,
      line.trips[0].events
        .filter((e) => e.ordinal)
        .flatMap((e) => [e.siteId, e.siteId, e.siteId]),
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

test("conceptual localities have inward labels, one connector each, and only upper counterclockwise arrows", async () => {
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
        "Vaccarezza",
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
    for (const group of groups) {
      const loop = loops.find(
        (e) => e.getAttribute("data-loop") === group.getAttribute("data-loop"),
      );
      const text = group.querySelectorAll(".n8-diagram-name")[0];
      assert.ok(
        Math.hypot(
          Number(text.getAttribute("x")) - Number(loop.getAttribute("cx")),
          Number(text.getAttribute("y")) - Number(loop.getAttribute("cy")),
        ) < Number(loop.getAttribute("r")),
      );
    }
    assert.equal(image.querySelectorAll(".n8-diagram-connector").length, 1);
    assert.equal(
      image.querySelectorAll(".n8-diagram-connector")[0].getAttribute("d"),
      "M600 640 V708 M600 798 V870",
    );
    const arrows = image.querySelectorAll(".n8-diagram-arrow");
    assert.equal(arrows.length, 3);
    assert.ok(
      arrows.every(
        (e) => e.getAttribute("data-direction") === "counterclockwise",
      ),
    );
    assert.ok(
      arrows.every(
        (e) =>
          Number(
            e.getAttribute("transform").match(/translate\([^ ]+ ([^)]+)\)/)[1],
          ) < 640,
      ),
    );
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
