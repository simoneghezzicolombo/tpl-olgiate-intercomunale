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

function renderBaseline(threshold = "10") {
  const global = BASELINE.global[threshold];
  document.querySelector("#globalCoverage").textContent = `${fmt.format(global)}%`;
  document.querySelector("#globalCoverageLabel").textContent = `entro ${threshold} minuti a piedi`;
  const rows = [...BASELINE.municipalities].sort((a, b) => b.values[threshold] - a.values[threshold]);
  document.querySelector("#municipalityBars").innerHTML = rows.map(row => `
    <div class="bar-row">
      <span class="bar-label">${row.name}</span>
      <span class="bar-track" aria-hidden="true"><i class="bar-fill" style="width:${row.values[threshold]}%"></i></span>
      <strong class="bar-value">${fmt.format(row.values[threshold])}%</strong>
    </div>
  `).join("");
}

document.querySelectorAll("[data-threshold]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("[data-threshold]").forEach(b => b.classList.toggle("active", b === btn));
    renderBaseline(btn.dataset.threshold);
  });
});

function renderSpan(key) {
  const span = SPANS[key];
  document.querySelector("#spanExplainer").innerHTML = `
    <h4>${span.label}: cosa compra, cosa costa</h4>
    <p>${span.intro}</p>
    <div class="delta-line">${span.chips.map(x => `<span class="delta-chip">${x}</span>`).join("")}</div>
  `;
  document.querySelectorAll("[data-span]").forEach(btn => btn.classList.toggle("active", btn.dataset.span === key));
}

document.querySelectorAll("[data-span]").forEach(btn => btn.addEventListener("click", () => renderSpan(btn.dataset.span)));

let selected = [];

function updateSelection() {
  document.querySelectorAll(".candidate-card").forEach(card => card.classList.toggle("selected", selected.includes(card.dataset.candidate)));
  const a = selected[0] ? CANDIDATES[selected[0]] : null;
  const b = selected[1] ? CANDIDATES[selected[1]] : null;
  document.querySelector("#slotA p").textContent = a ? a.label : "Scegli una finalista";
  document.querySelector("#slotB p").textContent = b ? b.label : "Scegli una seconda finalista";
  renderComparison(a, b);
}

document.querySelectorAll(".candidate-card").forEach(card => {
  card.addEventListener("click", () => {
    const id = card.dataset.candidate;
    if (selected.includes(id)) selected = selected.filter(x => x !== id);
    else if (selected.length < 2) selected.push(id);
    else selected = [selected[1], id];
    updateSelection();
    if (selected.length === 2) document.querySelector("#confronta").scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

document.querySelector("#clearComparison").addEventListener("click", () => { selected = []; updateSelection(); });
document.querySelector("#swapComparison").addEventListener("click", () => { if (selected.length === 2) { selected.reverse(); updateSelection(); } });

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

renderBaseline("10");
renderSpan("16");
updateSelection();
