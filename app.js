const DATA = window.TRA_PAESI_DATA;
const BASELINE = DATA.baseline;
const PACKAGES = DATA.packages;
const FINALISTS = DATA.finalists;

const fmt = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt0 = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 });
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(hover:hover) and (pointer:fine)").matches;

let currentThreshold = "10";
let currentGlobal = BASELINE.global[10];
let activePackage = "16";
let activeTopology = "loops";
let selected = [];

function transition(update) {
  if (!reducedMotion && document.startViewTransition) return document.startViewTransition(update);
  update();
  return null;
}

function slug(value) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function pp(value) {
  return `${fmt.format(value * 100)}%`;
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

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function stateUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("threshold", currentThreshold);
  url.searchParams.set("pkg", activePackage);
  url.searchParams.set("topology", activeTopology);
  if (selected.length) url.searchParams.set("compare", selected.join(","));
  else url.searchParams.delete("compare");
  return url;
}

function syncUrl() {
  const url = stateUrl();
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

async function copyStateLink() {
  const url = stateUrl().toString();
  try {
    await navigator.clipboard.writeText(url);
    showToast("Link di questa vista copiato");
  } catch {
    const area = document.createElement("textarea");
    area.value = url;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    showToast("Link copiato");
  }
}

function loadUrlState() {
  const params = new URLSearchParams(location.search);
  const threshold = params.get("threshold");
  const pkg = params.get("pkg");
  const topology = params.get("topology");
  const compare = params.get("compare");

  if (["5", "8", "10", "12"].includes(threshold)) currentThreshold = threshold;
  if (PACKAGES[pkg]) activePackage = pkg;
  if (["loops", "fig"].includes(topology)) activeTopology = topology;
  if (compare) {
    const ids = compare.split(",").filter(id => FINALISTS[id]);
    selected = [...new Set(ids)].slice(0, 2);
  }
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
    document.querySelector("#rangeStoryTitle").textContent = `${fmt.format(gap)} punti separano ${low.name} da ${high.name}.`;
    document.querySelector("#rangeStoryBody").textContent = `Con ${key} minuti a piedi, ${high.name} raggiunge il ${fmt.format(high.values[key])}% della popolazione localizzata. ${low.name} si ferma al ${fmt.format(low.values[key])}%.`;
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
  syncUrl();
}

function uniqueNonHubAnchors(pkg) {
  return new Set(pkg.routes.flatMap(route => route.anchors.filter(a => a.kind !== "hub").map(a => a.id))).size;
}

function routeSequence(route) {
  return `
    <article class="route-card">
      <div class="route-card-head">
        <div><span class="route-number">Ramo ${route.ordinal}</span><strong>${route.trips} corse · ogni ora a :${String(route.phase).padStart(2, "0")}</strong></div>
        <div class="route-runtime"><b>${fmt.format(route.publicRuntime)}′</b><span>giro pubblico</span></div>
      </div>
      <div class="anchor-sequence">
        ${route.anchors.map((anchor, index) => `
          <div class="anchor ${anchor.kind}" title="${anchor.id}">
            <span class="anchor-dot" aria-hidden="true"></span>
            <div><strong>${anchor.label}</strong>${anchor.detail ? `<small>${anchor.detail}</small>` : ""}</div>
          </div>
          ${index < route.anchors.length - 1 ? '<span class="anchor-link" aria-hidden="true"></span>' : ""}
        `).join("")}
      </div>
      <div class="route-footer"><span>${route.firstDeparture} → ${route.lastDeparture}</span><span>rientro ultimo giro ${route.lastEnd}</span><span>technical closure ${fmt.format(route.technicalClosureMin)}′</span></div>
    </article>
  `;
}

function departureTimes(route) {
  const [startH, startM] = route.firstDeparture.split(":").map(Number);
  const [endH] = route.lastDeparture.split(":").map(Number);
  return Array.from({ length: endH - startH + 1 }, (_, i) => `${String(startH + i).padStart(2, "0")}:${String(startM).padStart(2, "0")}`);
}

function renderRhythm(pkg) {
  const phases = pkg.routes.map(r => r.phase);
  const marks = pkg.routes.map(route => `
    <span class="minute-mark route-${route.ordinal}" style="left:${(route.phase / 60) * 100}%" aria-label="Ramo ${route.ordinal}, minuto ${route.phase}">
      <i></i><b>:${String(route.phase).padStart(2, "0")}</b><small>R${route.ordinal}</small>
    </span>
  `).join("");
  const ticks = [0, 15, 30, 45, 60].map(n => `<span class="minute-tick" style="left:${(n / 60) * 100}%"><i></i><small>${String(n).padStart(2, "0")}</small></span>`).join("");
  document.querySelector("#minuteRuler").innerHTML = `<div class="ruler-line"></div>${ticks}${marks}`;

  if (pkg.combinedRegular) {
    document.querySelector("#rhythmExplanation").textContent = `I due rami partono insieme al minuto :${String(phases[0]).padStart(2, "0")}. Ogni ramo resta perfettamente H60 e il nodo vede un unico gruppo di partenze ogni ora.`;
  } else {
    document.querySelector("#rhythmExplanation").textContent = `Ogni ramo è perfettamente H60, ma al nodo le partenze si concentrano a :${String(phases[1]).padStart(2, "0")} e :${String(phases[0]).padStart(2, "0")}: 4 minuti fra i due rami, poi 56 minuti fino al gruppo successivo.`;
  }

  document.querySelector("#departureStrip").innerHTML = pkg.routes.map(route => `
    <div class="departure-row">
      <div><b>Ramo ${route.ordinal}</b><span>${route.trips} partenze</span></div>
      <div class="departure-times">${departureTimes(route).map(time => `<time>${time}</time>`).join("")}</div>
    </div>
  `).join("");
}

function renderStress(pkg) {
  const order = ["low", "mid", "high"];
  document.querySelector("#stressGrid").innerHTML = order.map(key => {
    const p = pkg.robustness[key];
    return `
      <article class="stress-card">
        <span>${p.label}</span>
        <strong>${pp(p.bidirectional)}</strong>
        <p>retention bidirezionale peggiore</p>
        <dl><div><dt>treno → bus</dt><dd>${pp(p.railToBus)}</dd></div><div><dt>bus → treno</dt><dd>${pp(p.busToRail)}</dd></div><div><dt>veicoli max</dt><dd>${p.vehicles}</dd></div><div><dt>veicoli extra</dt><dd>${p.extraVehicles}</dd></div></dl>
      </article>
    `;
  }).join("");
}

function topologyMessage() {
  const label = activeTopology === "loops" ? "Due anelli indipendenti" : "Figure-8 interlineato";
  const counterpart = activeTopology === "loops" ? "figure-8" : "due anelli";
  return `<span class="truth-badge">${label}</span><p><strong>Nel servizio pubblico certificato non cambia nulla rispetto a ${counterpart}.</strong> Sequenze, partenze esatte, runtime, km e profili Stage F coincidono a parità di pacchetto. Qui cambia la semantica operativa, non la rete mostrata al passeggero.</p>`;
}

function renderNetwork(pkgKey = activePackage, topology = activeTopology) {
  activePackage = pkgKey;
  activeTopology = topology;
  const pkg = PACKAGES[pkgKey];
  const topologyLabel = topology === "loops" ? "Due anelli" : "Figure-8";

  transition(() => {
    document.querySelector("#networkTitle").textContent = pkg.label;
    document.querySelector("#routeDiagrams").innerHTML = pkg.routes.map(routeSequence).join("");
    document.querySelector("#topologyTruth").innerHTML = topologyMessage();
    document.querySelector("#explorerStatus").innerHTML = `<strong>${topologyLabel}</strong><span>${pkg.spanStart}–${pkg.spanEnd} · ${pkg.exactTrips} corse</span>`;
    document.querySelector("#serviceFingerprint").innerHTML = `
      <p class="micro-label">Impronta del servizio</p>
      <div class="fingerprint-hero"><strong>${pkg.spanLabel}</strong><span>finestra di servizio</span></div>
      <dl class="fingerprint-list">
        <div><dt>corse pubbliche esatte</dt><dd>${pkg.exactTrips}</dd></div>
        <div><dt>anchor non-hub distinti</dt><dd>${uniqueNonHubAnchors(pkg)}</dd></div>
        <div><dt>km / anno</dt><dd>${fmt0.format(pkg.annualKm)}</dd></div>
        <div><dt>copertura 10′</dt><dd>${fmt.format(pkg.coverage10 * 100)}%</dd></div>
        <div><dt>reach bidirezionale</dt><dd>${fmt.format(pkg.reach * 100)}%</dd></div>
        <div><dt>block slack</dt><dd>${fmt.format(pkg.blockSlack)}′</dd></div>
        <div><dt>field check pendenti</dt><dd>${pkg.fieldChecks}</dd></div>
        <div><dt>technical closure</dt><dd>0′</dd></div>
      </dl>
    `;
    document.querySelectorAll("[data-network-package]").forEach(btn => {
      const active = btn.dataset.networkPackage === pkgKey;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
    document.querySelectorAll("[data-network-topology]").forEach(btn => {
      const active = btn.dataset.networkTopology === topology;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
    document.querySelectorAll("[data-span]").forEach(btn => {
      const active = btn.dataset.span === pkgKey;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
  });
  renderRhythm(pkg);
  renderStress(pkg);
  renderSpan(pkgKey, false);
  syncUrl();
}

function renderSpan(key, animate = true) {
  const pkg = PACKAGES[key];
  const other = PACKAGES[key === "16" ? "18.5" : "16"];
  const kmDelta = Math.abs(pkg.annualKm - other.annualKm);
  const reachDelta = Math.abs((pkg.reach - other.reach) * 100);
  const covDelta = Math.abs((pkg.coverage10 - other.coverage10) * 100);
  const slackDelta = Math.abs(pkg.blockSlack - other.blockSlack);
  const content = key === "16" ? `
    <h4>16h: il pacchetto più compatto</h4>
    <p>Finestra ${pkg.spanStart}–${pkg.spanEnd}. Produce ${pkg.exactTrips} corse pubbliche esatte: i due rami partono entrambi a :39. Rispetto al pacchetto 18h30 usa ${fmt0.format(kmDelta)} km/anno in meno e mantiene ${fmt.format(covDelta)} p.p. in più di copertura a 10′ nel set finalistico.</p>
    <div class="delta-line"><span class="delta-chip">${pkg.exactTrips} corse</span><span class="delta-chip">rami entrambi :39</span><span class="delta-chip">${pkg.fieldChecks} field check</span></div>
  ` : `
    <h4>18h30: il pacchetto più esteso</h4>
    <p>Finestra ${pkg.spanStart}–${pkg.spanEnd}. Produce ${pkg.exactTrips} corse pubbliche esatte. I rami partono a :03 e :07. Rispetto al 16h aggiunge ${fmt0.format(kmDelta)} km/anno, ${fmt.format(reachDelta)} p.p. di reach bidirezionale e ${fmt.format(slackDelta)} minuti di block slack, con ${fmt.format(covDelta)} p.p. in meno di copertura a 10′.</p>
    <div class="delta-line"><span class="delta-chip">${pkg.exactTrips} corse</span><span class="delta-chip">rami :03 + :07</span><span class="delta-chip">${pkg.fieldChecks} field check</span></div>
  `;
  const update = () => { document.querySelector("#spanExplainer").innerHTML = content; };
  if (animate) transition(update); else update();
}

function finalistLabel(id) {
  const f = FINALISTS[id];
  return `${f.topologyLabel} · ${PACKAGES[f.packageKey].spanLabel}`;
}

function updatePresetState() {
  const sorted = [...selected].sort().join(",");
  document.querySelectorAll("[data-preset]").forEach(btn => {
    const preset = btn.dataset.preset.split(",").sort().join(",");
    btn.classList.toggle("active", selected.length === 2 && sorted === preset);
  });
}

function updateDock() {
  const dock = document.querySelector("#decisionDock");
  const text = document.querySelector("#dockText");
  dock.classList.toggle("visible", selected.length > 0);
  if (!selected.length) text.textContent = "Nessuna finalista selezionata";
  else if (selected.length === 1) text.textContent = `${finalistLabel(selected[0])} · scegli il confronto`;
  else text.textContent = `${finalistLabel(selected[0])} ↔ ${finalistLabel(selected[1])}`;
}

function updateSelection() {
  document.querySelectorAll(".candidate-card").forEach(card => {
    const active = selected.includes(card.dataset.candidate);
    card.classList.toggle("selected", active);
    card.setAttribute("aria-pressed", String(active));
  });
  const a = selected[0] ? FINALISTS[selected[0]] : null;
  const b = selected[1] ? FINALISTS[selected[1]] : null;
  document.querySelector("#slotA p").textContent = a ? finalistLabel(selected[0]) : "Scegli una finalista";
  document.querySelector("#slotB p").textContent = b ? finalistLabel(selected[1]) : "Scegli una seconda finalista";
  const hint = document.querySelector("#selectionHint");
  hint.textContent = selected.length === 0 ? "Scegline due per vedere soltanto ciò che cambia." : selected.length === 1 ? "Una scelta fatta. Ora scegli con cosa confrontarla." : "Due finaliste selezionate. Il confronto è pronto.";
  updatePresetState();
  updateDock();
  renderComparison(a, b, selected[0], selected[1]);
  syncUrl();
}

function diffRow(label, left, right, note = "") {
  return `<div class="diff-row"><div class="diff-value">${left}</div><div class="diff-label">${label}${note ? `<small>${note}</small>` : ""}</div><div class="diff-value right">${right}</div></div>`;
}

function packageRouteSummary(pkg) {
  return pkg.routes.map(r => `R${r.ordinal}: ${r.anchors.filter(a => a.kind !== "hub").map(a => a.label).join(" → ")}`).join(" · ");
}

function renderComparison(a, b, idA, idB) {
  const target = document.querySelector("#comparisonResult");
  if (!a || !b) {
    target.className = "comparison-result empty";
    target.innerHTML = "<p>Seleziona due alternative. Ti mostrerò solo ciò che cambia fra loro.</p>";
    return;
  }

  const pa = PACKAGES[a.packageKey];
  const pb = PACKAGES[b.packageKey];
  const samePackage = a.packageKey === b.packageKey;
  const sameTopology = a.topology === b.topology;
  target.className = "comparison-result";

  if (samePackage && !sameTopology) {
    target.innerHTML = `
      <div class="equivalence-callout">
        <span class="micro-label">Risultato del confronto</span>
        <h3>Per chi viaggia, queste due finaliste sono identiche nel diagnostic PASS.</h3>
        <p>Cambiano <strong>${a.topologyLabel}</strong> e <strong>${b.topologyLabel}</strong>. Non cambiano sequenze degli anchor, partenze esatte, runtime, ${fmt0.format(pa.annualKm)} km/anno, stress test Stage F o technical closure.</p>
      </div>
      <div class="comparison-grid compact-compare">
        <div class="comparison-head"><span>Finalista A</span><h3>${finalistLabel(idA)}</h3></div>
        <div class="comparison-head"><span>Finalista B</span><h3>${finalistLabel(idB)}</h3></div>
        ${diffRow("semantica operativa", a.topologyLabel, b.topologyLabel)}
        <div class="same-note"><strong>Cosa implica:</strong> con l'evidenza finalistico-passenger-facing attuale, la scelta fra queste due non può essere giustificata dicendo che una offre più fermate, più corse o maggiore robustezza. Quei contenuti coincidono.</div>
      </div>
    `;
    return;
  }

  let rows = "";
  if (!samePackage) {
    rows += diffRow("finestra", `${pa.spanStart}–${pa.spanEnd}`, `${pb.spanStart}–${pb.spanEnd}`);
    rows += diffRow("corse pubbliche", pa.exactTrips, pb.exactTrips);
    rows += diffRow("ritmo al nodo", pa.routes.map(r => `:${String(r.phase).padStart(2,"0")}`).join(" + "), pb.routes.map(r => `:${String(r.phase).padStart(2,"0")}`).join(" + "));
    rows += diffRow("anchor distinti", uniqueNonHubAnchors(pa), uniqueNonHubAnchors(pb), "non-hub");
    rows += diffRow("km / anno", fmt0.format(pa.annualKm), fmt0.format(pb.annualKm));
    rows += diffRow("copertura 10′", `${fmt.format(pa.coverage10 * 100)}%`, `${fmt.format(pb.coverage10 * 100)}%`);
    rows += diffRow("worst comune 10′", `${fmt.format(pa.worstMunicipality10 * 100)}%`, `${fmt.format(pb.worstMunicipality10 * 100)}%`);
    rows += diffRow("reach bidirez.", `${fmt.format(pa.reach * 100)}%`, `${fmt.format(pb.reach * 100)}%`);
    rows += diffRow("block slack", `${fmt.format(pa.blockSlack)}′`, `${fmt.format(pb.blockSlack)}′`);
    rows += diffRow("stress worst bidir.", pp(Math.min(...Object.values(pa.robustness).map(x => x.bidirectional))), pp(Math.min(...Object.values(pb.robustness).map(x => x.bidirectional))), "engineering");
    rows += diffRow("field check", pa.fieldChecks, pb.fieldChecks);
  }
  if (!sameTopology) rows += diffRow("topologia", a.topologyLabel, b.topologyLabel);

  const routeChanged = !samePackage;
  target.innerHTML = `
    <div class="comparison-grid">
      <div class="comparison-head"><span>Finalista A</span><h3>${finalistLabel(idA)}</h3></div>
      <div class="comparison-head"><span>Finalista B</span><h3>${finalistLabel(idB)}</h3></div>
      ${rows}
      ${routeChanged ? `<div class="route-change-note"><span class="micro-label">La differenza più importante</span><h4>Non cambia soltanto la durata. Cambiano anche i percorsi.</h4><div class="route-change-columns"><p><strong>A</strong>${packageRouteSummary(pa)}</p><p><strong>B</strong>${packageRouteSummary(pb)}</p></div></div>` : ""}
      <div class="same-note"><strong>Quello che non cambia:</strong> H60 per ogni ramo, massimo 2 veicoli nei profili Stage F, 0 veicoli aggiuntivi e technical closure pari a 0 minuti.</div>
    </div>
  `;
}

function bindInteractions() {
  document.querySelectorAll("[data-threshold]").forEach(btn => btn.addEventListener("click", () => renderBaseline(btn.dataset.threshold)));
  document.querySelectorAll("[data-network-package]").forEach(btn => btn.addEventListener("click", () => renderNetwork(btn.dataset.networkPackage, activeTopology)));
  document.querySelectorAll("[data-network-topology]").forEach(btn => btn.addEventListener("click", () => renderNetwork(activePackage, btn.dataset.networkTopology)));
  document.querySelectorAll("[data-span]").forEach(btn => btn.addEventListener("click", () => {
    renderNetwork(btn.dataset.span, activeTopology);
    document.querySelector("#rete").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  }));

  document.querySelectorAll(".candidate-card").forEach(card => {
    card.addEventListener("click", () => {
      const id = card.dataset.candidate;
      if (selected.includes(id)) selected = selected.filter(x => x !== id);
      else if (selected.length < 2) selected.push(id);
      else selected = [selected[1], id];
      transition(updateSelection);
      if (selected.length === 2) setTimeout(() => document.querySelector("#confronta").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" }), reducedMotion ? 0 : 100);
    });
    card.addEventListener("pointerenter", () => {
      const matrix = document.querySelector("#candidateMatrix");
      matrix.classList.add(`hover-${card.dataset.topology}`);
      matrix.classList.add(`hover-${card.dataset.spanRow.replace(".", "-")}`);
    });
    card.addEventListener("pointerleave", () => { document.querySelector("#candidateMatrix").className = "candidate-matrix"; });
  });

  document.querySelectorAll("[data-preset]").forEach(btn => btn.addEventListener("click", () => {
    selected = btn.dataset.preset.split(",");
    transition(updateSelection);
    const packageKeys = selected.map(id => FINALISTS[id].packageKey);
    if (packageKeys[0] === packageKeys[1]) renderNetwork(packageKeys[0], activeTopology);
    setTimeout(() => document.querySelector("#comparisonResult").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" }), reducedMotion ? 0 : 100);
  }));

  document.querySelector("#clearComparison").addEventListener("click", () => { selected = []; transition(updateSelection); });
  document.querySelector("#swapComparison").addEventListener("click", () => { if (selected.length === 2) { selected.reverse(); transition(updateSelection); } });
  document.querySelector("#shareComparison").addEventListener("click", copyStateLink);
  document.querySelector("#dockShare").addEventListener("click", copyStateLink);
  document.querySelector("#dockCompare").addEventListener("click", () => document.querySelector("#confronta").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" }));
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
  }, { threshold: 0.1, rootMargin: "0px 0px -5%" });
  nodes.forEach(node => observer.observe(node));
}

function setupScrollUI() {
  const header = document.querySelector("#siteHeader");
  const progress = document.querySelector("#readingProgress");
  let ticking = false;
  function updateScroll() {
    const y = window.scrollY;
    const max = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    header.classList.toggle("scrolled", y > 20);
    progress.style.width = `${Math.min(100, Math.max(0, y / max * 100))}%`;
    ticking = false;
  }
  addEventListener("scroll", () => { if (!ticking) { requestAnimationFrame(updateScroll); ticking = true; } }, { passive: true });
  updateScroll();

  const navLinks = [...document.querySelectorAll(".topnav a")];
  const sections = navLinks.map(link => document.querySelector(link.getAttribute("href"))).filter(Boolean);
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(e => e.isIntersecting).sort((a,b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      navLinks.forEach(link => link.classList.toggle("active", link.getAttribute("href") === `#${visible.target.id}`));
    }, { rootMargin: "-30% 0px -55%", threshold: [0, .2, .5] });
    sections.forEach(section => observer.observe(section));
  }
}

function setupHeroMotion() {
  if (!finePointer || reducedMotion) return;
  const hero = document.querySelector("#heroVisual");
  hero.addEventListener("pointermove", event => {
    const rect = hero.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    hero.style.setProperty("--ry", `${(x - .5) * 2.2}deg`);
    hero.style.setProperty("--rx", `${(.5 - y) * 2.2}deg`);
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

loadUrlState();
renderBaseline(currentThreshold, false);
renderNetwork(activePackage, activeTopology);
updateSelection();
bindInteractions();
setupReveal();
setupScrollUI();
setupHeroMotion();