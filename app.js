const BASELINE = {
  global: { 5: 40.1865, 8: 60.8887, 10: 68.7306, 12: 74.71 },
  municipalities: [
    { name: "Brivio", values: { 5: 62.0679, 8: 90.0864, 10: 95.1953, 12: 97.8266 } },
    { name: "Calco", values: { 5: 26.7561, 8: 49.6327, 10: 52.4595, 12: 60.8558 } },
    { name: "La Valletta Brianza", values: { 5: 43.8262, 8: 56.4825, 10: 63.9647, 12: 69.2725 } },
    { name: "Olgiate Molgora", values: { 5: 20.7753, 8: 43.8136, 10: 59.8904, 12: 68.3977 } },
    { name: "Santa Maria Hoè", values: { 5: 80.6623, 8: 91.5244, 10: 94.0004, 12: 94.4813 } }
  ]
};

const SPANS = {
  "16": {
    label: "16 ore",
    km: 102916,
    coverage5: 13.41,
    coverage8: 29.28,
    coverage10: 37.33,
    reach: 33.51,
    slack: 5.90,
    s8: "1,00",
    fieldChecks: 3,
    intro: "La variante compatta usa meno chilometri e conserva un vantaggio marginale nelle misure di copertura del set finalistico.",
    chips: ["−5.745 km/anno", "+0,61 p.p. copertura 10′", "16 ore di servizio"]
  },
  "18.5": {
    label: "18 ore e 30",
    km: 108661,
    coverage5: 13.17,
    coverage8: 27.99,
    coverage10: 36.72,
    reach: 35.02,
    slack: 11.63,
    s8: "0",
    fieldChecks: 1,
    intro: "La variante estesa compra due ore e mezza di servizio in più, maggiore reach bidirezionale e più margine operativo, usando più chilometri.",
    chips: ["+2h30 di servizio", "+1,51 p.p. reach bidirezionale", "+5,73 min di block slack"]
  }
};

const CANDIDATES = {
  loops16: { id: "loops16", topology: "Due anelli", spanKey: "16", label: "Due anelli · 16h" },
  fig16: { id: "fig16", topology: "Figure-8", spanKey: "16", label: "Figure-8 · 16h" },
  loops185: { id: "loops185", topology: "Due anelli", spanKey: "18.5", label: "Due anelli · 18h30" },
  fig185: { id: "fig185", topology: "Figure-8", spanKey: "18.5", label: "Figure-8 · 18h30" }
};

const fmt = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmtInt = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 });
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(hover:hover) and (pointer:fine)").matches;
let currentThreshold = "10";
let currentGlobal = BASELINE.global[10];
let selected = [];

function transition(update) {
  if (!reducedMotion && document.startViewTransition) return document.startViewTransition(update);
  update();
  return null;
}

function animateNumber(el, from, to, suffix = "%") {
  if (reducedMotion || Math.abs(from - to) < 0.01) {
    el.textContent = `${fmt.format(to)}${suffix}`;
    return;
  }
  const start = performance.now();
  const duration = 420;
  const ease = t => 1 - Math.pow(1 - t, 3);
  function frame(now) {
    const p = Math.min(1, (now - start) / duration);
    el.textContent = `${fmt.format(from + (to - from) * ease(p))}${suffix}`;
    if (p < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function slug(value) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function renderBaseline(threshold = "10", animate = true) {
  const key = String(threshold);
  const global = BASELINE.global[key];
  const rows = [...BASELINE.municipalities].sort((a, b) => b.values[key] - a.values[key]);
  const high = rows[0];
  const low = rows[rows.length - 1];
  const gap = high.values[key] - low.values[key];

  const update = () => {
    const globalEl = document.querySelector("#globalCoverage");
    if (animate) animateNumber(globalEl, currentGlobal, global);
    else globalEl.textContent = `${fmt.format(global)}%`;
    document.querySelector("#globalCoverageLabel").textContent = `entro ${key} minuti a piedi`;
    document.querySelector("#municipalityBars").innerHTML = rows.map(row => `
      <div class="bar-row" style="view-transition-name:bar-${slug(row.name)}">
        <span class="bar-label">${row.name}</span>
        <span class="bar-track" aria-hidden="true"><i class="bar-fill" style="width:${row.values[key]}%"></i></span>
        <strong class="bar-value">${fmt.format(row.values[key])}%</strong>
      </div>
    `).join("");
    document.querySelector("#rangeStoryTitle").textContent = `Tra ${low.name} e ${high.name} ci sono ${fmt.format(gap)} punti.`;
    document.querySelector("#rangeStoryBody").textContent = `Con una soglia di ${key} minuti, ${high.name} raggiunge il ${fmt.format(high.values[key])}% della popolazione localizzata. ${low.name} si ferma al ${fmt.format(low.values[key])}%.`;
    document.querySelector("#rangeMin").textContent = fmt.format(low.values[key]);
    document.querySelector("#rangeMax").textContent = fmt.format(high.values[key]);
    document.querySelector("#rangeGap").textContent = fmt.format(gap);
    document.querySelectorAll("[data-threshold]").forEach(btn => {
      const active = btn.dataset.threshold === key;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
  };

  if (animate && currentThreshold !== key) transition(update); else update();
  currentThreshold = key;
  currentGlobal = global;
}

document.querySelectorAll("[data-threshold]").forEach(btn => {
  btn.setAttribute("aria-pressed", String(btn.classList.contains("active")));
  btn.addEventListener("click", () => renderBaseline(btn.dataset.threshold));
});

function renderSpan(key) {
  const span = SPANS[key];
  transition(() => {
    document.querySelector("#spanExplainer").innerHTML = `
      <h4>${span.label}: cosa compra, cosa costa</h4>
      <p>${span.intro}</p>
      <div class="delta-line">${span.chips.map(x => `<span class="delta-chip">${x}</span>`).join("")}</div>
    `;
    document.querySelectorAll("[data-span]").forEach(btn => {
      const active = btn.dataset.span === key;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
  });
}

document.querySelectorAll("[data-span]").forEach(btn => btn.addEventListener("click", () => renderSpan(btn.dataset.span)));

function updatePresetState() {
  const sorted = [...selected].sort().join(",");
  document.querySelectorAll("[data-preset]").forEach(btn => {
    const preset = btn.dataset.preset.split(",").sort().join(",");
    btn.classList.toggle("active", selected.length === 2 && sorted === preset);
  });
}

function updateSelection() {
  document.querySelectorAll(".candidate-card").forEach(card => {
    const active = selected.includes(card.dataset.candidate);
    card.classList.toggle("selected", active);
    card.setAttribute("aria-pressed", String(active));
  });
  const a = selected[0] ? CANDIDATES[selected[0]] : null;
  const b = selected[1] ? CANDIDATES[selected[1]] : null;
  document.querySelector("#slotA p").textContent = a ? a.label : "Scegli una finalista";
  document.querySelector("#slotB p").textContent = b ? b.label : "Scegli una seconda finalista";
  const hint = document.querySelector("#selectionHint");
  hint.textContent = selected.length === 0 ? "Scegline due per vedere soltanto ciò che cambia." : selected.length === 1 ? "Una scelta fatta. Ora scegli con cosa confrontarla." : "Due alternative selezionate. Il confronto è pronto.";
  updatePresetState();
  renderComparison(a, b);
}

document.querySelectorAll(".candidate-card").forEach(card => {
  card.addEventListener("click", () => {
    const id = card.dataset.candidate;
    if (selected.includes(id)) selected = selected.filter(x => x !== id);
    else if (selected.length < 2) selected.push(id);
    else selected = [selected[1], id];
    transition(updateSelection);
    if (selected.length === 2) {
      window.setTimeout(() => document.querySelector("#confronta").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" }), reducedMotion ? 0 : 100);
    }
  });

  card.addEventListener("pointerenter", () => {
    const matrix = document.querySelector("#candidateMatrix");
    matrix.classList.add(`hover-${card.dataset.topology}`);
    matrix.classList.add(`hover-${card.dataset.spanRow.replace(".", "-")}`);
  });
  card.addEventListener("pointerleave", () => {
    document.querySelector("#candidateMatrix").className = "candidate-matrix";
  });
});

document.querySelectorAll("[data-preset]").forEach(btn => {
  btn.addEventListener("click", () => {
    selected = btn.dataset.preset.split(",");
    transition(updateSelection);
    window.setTimeout(() => document.querySelector("#comparisonResult").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" }), reducedMotion ? 0 : 100);
  });
});

document.querySelector("#clearComparison").addEventListener("click", () => {
  selected = [];
  transition(updateSelection);
});

document.querySelector("#swapComparison").addEventListener("click", () => {
  if (selected.length === 2) {
    selected.reverse();
    transition(updateSelection);
  }
});

function diffRow(label, left, right, leftClass = "", rightClass = "") {
  return `<div class="diff-row"><div class="diff-value ${leftClass}">${left}</div><div class="diff-label">${label}</div><div class="diff-value right ${rightClass}">${right}</div></div>`;
}

function renderComparison(a, b) {
  const target = document.querySelector("#comparisonResult");
  if (!a || !b) {
    target.className = "comparison-result empty";
    target.innerHTML = "<p>Seleziona due alternative sopra. Ti mostrerò solo ciò che cambia fra loro.</p>";
    return;
  }

  target.className = "comparison-result";
  const sa = SPANS[a.spanKey];
  const sb = SPANS[b.spanKey];
  const sameSpan = a.spanKey === b.spanKey;
  const sameTopology = a.topology === b.topology;
  let rows = "";

  if (!sameSpan) {
    rows += diffRow("servizio", sa.label, sb.label);
    rows += diffRow("km / anno", fmtInt.format(sa.km), fmtInt.format(sb.km));
    rows += diffRow("copertura 10′", `${fmt.format(sa.coverage10)}%`, `${fmt.format(sb.coverage10)}%`, sa.coverage10 > sb.coverage10 ? "diff-better" : "", sb.coverage10 > sa.coverage10 ? "diff-better" : "");
    rows += diffRow("reach bidirez.", `${fmt.format(sa.reach)}%`, `${fmt.format(sb.reach)}%`, sa.reach > sb.reach ? "diff-better" : "", sb.reach > sa.reach ? "diff-better" : "");
    rows += diffRow("block slack", `${fmt.format(sa.slack)} min`, `${fmt.format(sb.slack)} min`, sa.slack > sb.slack ? "diff-better" : "", sb.slack > sa.slack ? "diff-better" : "");
  }
  if (!sameTopology) rows += diffRow("struttura", a.topology, b.topology);

  const same = [];
  if (sameSpan) same.push(`stessa estensione di servizio (${sa.label}) e stessi indicatori aggregati oggi disponibili`);
  if (sameTopology) same.push(`stessa famiglia di esercizio (${a.topology})`);

  target.innerHTML = `
    <div class="comparison-grid">
      <div class="comparison-head"><span>Alternativa A</span><h3>${a.label}</h3></div>
      <div class="comparison-head"><span>Alternativa B</span><h3>${b.label}</h3></div>
      ${rows}
      ${same.length ? `<div class="same-note"><strong>Quello che non cambia:</strong> ${same.join("; ")}.</div>` : ""}
      ${!sameTopology ? `<div class="pending-diff"><strong>Il confronto strutturale non viene riempito per supposizione.</strong> Sequenze, overlap, ritorno pubblico, eventuale chiusura tecnica e regolarità delle partenze saranno inseriti dal diagnostic source-closed di A.</div>` : ""}
    </div>
  `;
}

function setupReveal() {
  const nodes = document.querySelectorAll(".reveal");
  if (reducedMotion || !("IntersectionObserver" in window)) {
    nodes.forEach(node => node.classList.add("revealed"));
    return;
  }
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -4%" });
  nodes.forEach(node => observer.observe(node));
}

function setupScrollUI() {
  const header = document.querySelector("#siteHeader");
  const progress = document.querySelector("#readingProgress");
  let ticking = false;

  function updateScroll() {
    const y = window.scrollY;
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    header.classList.toggle("scrolled", y > 20);
    progress.style.width = `${Math.min(100, Math.max(0, (y / max) * 100))}%`;
    ticking = false;
  }

  window.addEventListener("scroll", () => {
    if (!ticking) {
      requestAnimationFrame(updateScroll);
      ticking = true;
    }
  }, { passive: true });
  updateScroll();

  const navLinks = [...document.querySelectorAll(".topnav a")];
  const sections = navLinks.map(link => document.querySelector(link.getAttribute("href"))).filter(Boolean);
  if ("IntersectionObserver" in window) {
    const sectionObserver = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      navLinks.forEach(link => link.classList.toggle("active", link.getAttribute("href") === `#${visible.target.id}`));
    }, { rootMargin: "-30% 0px -55%", threshold: [0, .2, .5] });
    sections.forEach(section => sectionObserver.observe(section));
  }
}

function setupHeroMotion() {
  if (!finePointer || reducedMotion) return;
  const hero = document.querySelector("#heroVisual");
  if (!hero) return;
  hero.addEventListener("pointermove", event => {
    const rect = hero.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    hero.style.setProperty("--ry", `${(x - .5) * 3.2}deg`);
    hero.style.setProperty("--rx", `${(.5 - y) * 3.2}deg`);
    hero.style.setProperty("--mx", `${x * 100}%`);
    hero.style.setProperty("--my", `${y * 100}%`);
  });
  hero.addEventListener("pointerleave", () => {
    hero.style.setProperty("--ry", "0deg");
    hero.style.setProperty("--rx", "0deg");
    hero.style.setProperty("--mx", "50%");
    hero.style.setProperty("--my", "50%");
  });
}

renderBaseline("10", false);
renderSpan("16");
updateSelection();
setupReveal();
setupScrollUI();
setupHeroMotion();
