/**
 * Linea 8 Olgiate Molgora - Interactive Dashboard Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // State Constants
  const PDB_TOTALE = 111419.0;
  const PDB_MORBIDA = 77010.0;
  const PDB_PUNTA = 34408.0;
  const GIORNI_ESERCIZIO = 303;
  const KM_MERATE = 90372.4;

  // Preset Scenarios
  const SCENARIOS = {
    scen0: {
      name: 'Scenario 0 (Baseline 1 Bus Spola A/R)',
      km: 22.4,
      cicli: 13,
      autobus: '1 Autobus',
      hint: 'Percorsi attuali percorsi in andata e ritorno (13 corse per ramo)',
      note: 'Coperto da D184+D185 con 23.000 km di risparmio residui per le punte.'
    },
    scen1: {
      name: 'Scenario 1 (1 Bus Anello Mondonico+Arlate)',
      km: 19.8,
      cicli: 13,
      autobus: '1 Autobus',
      hint: 'Chiusura ad anello via Mondonico e Arlate (13 cicli orari a 1 bus)',
      note: 'Coperto al 99% dalla sola morbida; preservate integralmente le corse di punta.'
    },
    scenC: {
      name: 'Scenario C (Ibrido Raccomandato: 2 Bus Punta / 1 Morbida)',
      km: 19.5,
      cicli: 19,
      autobus: '2 Bus Punta / 1 Morbida',
      hint: '6 ore di punta a 2 bus (12 cicli) + 7 ore morbida a 1 bus (7 cicli) = 19 cicli',
      note: 'Perfetta neutralità economica con 111.419 km/anno (+0,8% scostamento!).'
    },
    scen2: {
      name: 'Scenario 2 (Full Merate Style: 2 Bus Continuo Bidirezionale)',
      km: 19.8,
      cicli: 26,
      autobus: '2 Autobus Fissi (1 CW + 1 CCW)',
      hint: '1 Bus in Senso Orario continuo + 1 Bus in Senso Antiorario continuo per 13 ore',
      note: 'Servizio turn-up-and-go ogni 30 min in ogni frazione; richiede +44.500 km/anno.'
    }
  };

  // Frazioni Matrix
  const FRAZIONI_DATA = [
    {
      id: 'perego',
      nome: 'Perego Centro',
      ramo: 'Ovest',
      pop: 1850,
      deltaT: 0,
      rendimento: 'Infinito (0 min)',
      status: 'SI (Confermato)',
      tipo: 'Asse principale SP342 dir',
      desc: 'Già sul corridoio naturale tra Olgiate e Santa Maria Hoè. Nessun minuto di deviazione: inclusa d\'ufficio con massima priorità.'
    },
    {
      id: 'beverate',
      nome: 'Beverate',
      ramo: 'Est',
      pop: 1600,
      deltaT: 0,
      rendimento: 'Infinito (0 min)',
      status: 'SI (Confermato)',
      tipo: 'Asse principale SP72',
      desc: 'Già sul corridoio naturale tra Calco e Brivio. Nessun minuto di deviazione: confermata d\'ufficio nel tracciato principale.'
    },
    {
      id: 'mondonico',
      nome: 'Mondonico / Monticello',
      ramo: 'Ovest',
      pop: 920,
      deltaT: 2.5,
      rendimento: '368 ab./min',
      status: 'SI (Consigliato in Anello)',
      tipo: 'Chiusura anello Ovest',
      desc: 'Se percorso come ritorno da Santa Maria Hoè verso Olgiate FS, non è un vicolo cieco ma chiude l\'anello! Aggiunge solo 2,5 min a fronte di 920 residenti serviti.'
    },
    {
      id: 'arlate',
      nome: 'Arlate / S. Colombano',
      ramo: 'Est',
      pop: 1150,
      deltaT: 3.5,
      rendimento: '328 ab./min',
      status: 'SI (Consigliato in Anello)',
      tipo: 'Chiusura anello Est',
      desc: 'Ritorno ottimale da Brivio verso Olgiate FS via Calendone / Arlate. Chiude l\'anello est portando 1.150 residenti al TPL con rendimento eccellente.'
    },
    {
      id: 'calco_sup',
      nome: 'Calco Superiore',
      ramo: 'Est',
      pop: 580,
      deltaT: 4.5,
      rendimento: '129 ab./min',
      status: 'Al Limite',
      tipo: 'Deviazione collinare',
      desc: 'Salita su colle di Calco. +4,5 min rischia di portare il ciclo est a 33 min, erodendo il margine di coincidenza a Olgiate FS. Da verificare con micro-routing.'
    },
    {
      id: 'san_zeno',
      nome: 'San Zeno',
      ramo: 'Ovest',
      pop: 710,
      deltaT: 7.5,
      rendimento: '95 ab./min',
      status: 'NO (Sfora 60 min)',
      tipo: 'Deviazione a spola isolata',
      desc: 'Tratta a fondo cieco su strada stretta. +7,5 min porta il ciclo oltre i 62 minuti: bocciata per il servizio di linea orario, consigliato servizio a chiamata.'
    },
    {
      id: 'ravellino',
      nome: 'Ravellino (Colle B.za)',
      ramo: 'Ovest (Coda)',
      pop: 520,
      deltaT: 19.0,
      rendimento: '27 ab./min',
      status: 'NO (Scorporata dal Core)',
      tipo: 'Coda rurale montana',
      desc: 'Capolinea storico D184. Aggiunge 19 min di ciclo (totale 74 min), distruggendo il cadenzamento a 1 bus. Va gestita con corse dedicate scolastiche/biorarie.'
    },
    {
      id: 'caprino',
      nome: 'Caprino / Celana',
      ramo: 'Est (Coda)',
      pop: 1400,
      deltaT: 20.0,
      rendimento: '70 ab./min',
      status: 'NO (Scorporata dal Core)',
      tipo: 'Coda extra-provinciale',
      desc: 'Capolinea storico D185 oltre il ponte di Brivio. Aggiunge 20 min di ciclo. Da scorporare dal core orario e collegare con navette adducenti a Brivio o corse di punta.'
    }
  ];

  // DOM Elements
  const sliderKm = document.getElementById('sliderKm');
  const sliderCicli = document.getElementById('sliderCicli');
  const valKm = document.getElementById('valKm');
  const valCicli = document.getElementById('valCicli');
  const cicliHint = document.getElementById('cicliHint');

  const lightRed = document.getElementById('lightRed');
  const lightYellow = document.getElementById('lightYellow');
  const lightGreen = document.getElementById('lightGreen');
  const semaforoBadge = document.getElementById('semaforoBadge');
  const headlineProd = document.getElementById('headlineProd');
  const prodDetail = document.getElementById('prodDetail');
  const bCicliAnno = document.getElementById('bCicliAnno');
  const bAutobus = document.getElementById('bAutobus');

  const scenarioTabs = document.getElementById('scenarioTabs');
  const timetableBody = document.getElementById('timetableBody');
  const selectBusFilter = document.getElementById('selectBusFilter');
  const btnThemeToggle = document.getElementById('btnThemeToggle');

  const btnViewBoth = document.getElementById('btnViewBoth');
  const btnViewCW = document.getElementById('btnViewCW');
  const btnViewCCW = document.getElementById('btnViewCCW');
  const explainerText = document.getElementById('explainerText');
  const frazioniChips = document.getElementById('frazioniChips');
  const frazioneDetailBox = document.getElementById('frazioneDetailBox');

  // Theme Switcher
  btnThemeToggle.addEventListener('click', () => {
    document.body.classList.toggle('theme-light');
    document.body.classList.toggle('theme-dark');
    const isLight = document.body.classList.contains('theme-light');
    btnThemeToggle.querySelector('.theme-icon').textContent = isLight ? '☀️' : '🌙';
  });

  // Calculate & Update Traffic Light
  function updateSemaforo() {
    const km = parseFloat(sliderKm.value);
    const cicli = parseInt(sliderCicli.value, 10);
    valKm.textContent = km.toFixed(1);
    valCicli.textContent = cicli;

    const cicliAnno = cicli * GIORNI_ESERCIZIO;
    const kmAnno = km * cicliAnno;
    bCicliAnno.textContent = `${cicliAnno.toLocaleString('it-IT')} cicli`;
    headlineProd.textContent = `${Math.round(kmAnno).toLocaleString('it-IT')} km/anno`;

    const deltaKm = kmAnno - PDB_TOTALE;
    const deltaPct = (deltaKm / PDB_TOTALE) * 100;

    // Reset Lights
    lightRed.classList.remove('active');
    lightYellow.classList.remove('active');
    lightGreen.classList.remove('active');

    if (kmAnno <= PDB_MORBIDA) {
      // GREEN
      lightGreen.classList.add('active');
      semaforoBadge.className = 'status-badge status-green';
      semaforoBadge.textContent = '🟢 SEMAFORO VERDE (Coperto da Sola Morbida)';
      prodDetail.textContent = `Produzione coperta al 100% dalla morbida di PdB (${Math.round(PDB_MORBIDA).toLocaleString('it-IT')} km). Tutte le 34.408 km di corse di punta rimangono intatte!`;
    } else if (kmAnno <= PDB_TOTALE) {
      // YELLOW
      lightYellow.classList.add('active');
      semaforoBadge.className = 'status-badge status-yellow';
      semaforoBadge.textContent = '🟡 SEMAFORO GIALLO (Sostenibile a Saldo Zero)';
      const avanzo = PDB_TOTALE - kmAnno;
      prodDetail.textContent = `Interamente finanziabile all'interno del budget di 111.419 km/anno di D184+D185. Avanzano ${Math.round(avanzo).toLocaleString('it-IT')} km/anno per rinforzi scolastici e code rurali.`;
    } else {
      // RED
      lightRed.classList.add('active');
      semaforoBadge.className = 'status-badge status-red';
      semaforoBadge.textContent = '🔴 SEMAFORO ROSSO (Richiede Risorse Aggiuntive)';
      prodDetail.textContent = `Supera le risorse attuali di ${Math.round(deltaKm).toLocaleString('it-IT')} km/anno (${deltaPct > 0 ? '+' : ''}${deltaPct.toFixed(1)}%). Necessario cofinanziamento o rimodulazione oraria.`;
    }
  }

  // Scenario Tab Switching
  scenarioTabs.addEventListener('click', (e) => {
    const tab = e.target.closest('.scenario-tab');
    if (!tab) return;

    scenarioTabs.querySelectorAll('.scenario-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    const scenKey = tab.dataset.scenario;
    const scen = SCENARIOS[scenKey];
    if (!scen) return;

    sliderKm.value = scen.km;
    sliderCicli.value = scen.cicli;
    bAutobus.textContent = scen.autobus;
    cicliHint.textContent = scen.hint;

    updateSemaforo();
    renderTimetable();
  });

  // Slider Listeners
  sliderKm.addEventListener('input', updateSemaforo);
  sliderCicli.addEventListener('input', updateSemaforo);

  // Direction Switchers
  const dirButtons = [btnViewBoth, btnViewCW, btnViewCCW];
  dirButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      dirButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const dir = btn.dataset.dir;

      const westPulse = document.getElementById('busPulseWest');
      const eastPulse = document.getElementById('busPulseEast');

      if (dir === 'cw') {
        explainerText.textContent = 'Senso Orario (CW): FS -> Rovagnate -> Perego -> S.Maria Hoè -> Mondonico -> FS (Ovest: 25 min) seguito da FS -> Calco -> Beverate -> Brivio -> Arlate -> FS (Est: 30 min). Ideale per l\'adduzione rapida del mattino da Perego e Calco verso i treni per Milano.';
        westPulse.style.display = 'block';
        eastPulse.style.display = 'block';
      } else if (dir === 'ccw') {
        explainerText.textContent = 'Senso Antiorario (CCW): FS -> Mondonico -> S.Maria Hoè -> Perego -> Rovagnate -> FS (Ovest: 25 min) seguito da FS -> Arlate -> Brivio -> Beverate -> Calco -> FS (Est: 30 min). Perfetto per il rientro serale da Milano direttamente verso Mondonico e Arlate.';
        westPulse.style.display = 'block';
        eastPulse.style.display = 'block';
      } else {
        explainerText.textContent = 'Doppio Verso Stile Merate (D201 / D202): L\'anello percorso in entrambi i versi contemporaneamente o alternato permette a ogni residente di scegliere sempre la direzione più rapida sia all\'andata sia al ritorno senza fare il giro largo!';
        westPulse.style.display = 'block';
        eastPulse.style.display = 'block';
      }
    });
  });

  // Populate Frazioni Chips
  function initFrazioni() {
    frazioniChips.innerHTML = '';
    FRAZIONI_DATA.forEach((f, idx) => {
      const chip = document.createElement('button');
      chip.className = `frazione-chip ${idx === 2 ? 'active' : ''}`;
      chip.textContent = f.nome;
      chip.addEventListener('click', () => {
        frazioniChips.querySelectorAll('.frazione-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        showFrazioneDetail(f);
      });
      frazioniChips.appendChild(chip);
    });
    // Show Mondonico as default
    showFrazioneDetail(FRAZIONI_DATA[2]);
  }

  function showFrazioneDetail(f) {
    frazioneDetailBox.innerHTML = `
      <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
        <strong style="color:var(--text-primary); font-size:0.85rem;">${f.nome} (${f.ramo})</strong>
        <span style="font-weight:700; color:${f.status.startsWith('SI') ? 'var(--accent-green)' : (f.status.startsWith('Al') ? 'var(--accent-amber)' : 'var(--accent-red)')};">${f.status}</span>
      </div>
      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; margin:6px 0; font-family:var(--font-mono); font-size:0.75rem;">
        <div>Pop. WorldPop: <strong>${f.pop.toLocaleString('it-IT')} ab.</strong></div>
        <div>Δ Tempo Ciclo: <strong>${f.deltaT > 0 ? '+' : ''}${f.deltaT} min</strong></div>
        <div>Rendimento: <strong>${f.rendimento}</strong></div>
      </div>
      <p style="margin-top:4px;">${f.desc}</p>
    `;
  }

  // Timetable Generator
  function renderTimetable() {
    const filter = selectBusFilter.value;
    timetableBody.innerHTML = '';

    // Generate schedule from 06:30 to 19:30
    const runs = [];
    for (let h = 6; h <= 19; h++) {
      const isPeak = (h >= 7 && h <= 9) || (h >= 17 && h <= 19);
      if (filter === 'peak' && !isPeak) continue;
      if (filter === 'offpeak' && isPeak) continue;

      // In Scenario C: during peak we have 2 buses (CW and CCW). During offpeak we have 1 bus.
      // Bus 1 (CW)
      const depOvest = `${String(h).padStart(2, '0')}:30`;
      const passOvest = `${String(h).padStart(2, '0')}:43`;
      const transFS = `${String(h).padStart(2, '0')}:56`;
      const nextH = h + 1;
      const depEst = `${String(nextH).padStart(2, '0')}:00`;
      const passEst = `${String(nextH).padStart(2, '0')}:15`;
      const arrFS = `${String(nextH).padStart(2, '0')}:29`;

      runs.push({
        slot: `${String(h).padStart(2, '0')}:30 – ${String(nextH).padStart(2, '0')}:30`,
        bus: 'Bus 1 (Orario CW)',
        badgeClass: 'badge-bus-cw',
        depOvest,
        passOvest: `${passOvest} (S.Maria)`,
        transFS,
        passEst: `${passEst} (Brivio)`,
        arrFS,
        s8Milano: `Part. :08 / :38`,
        s8Lecco: `Part. :22 / :52`,
        isPeak
      });

      // If peak or Scenario 2, Bus 2 (CCW) is active
      if (isPeak || sliderCicli.value >= 24) {
        const depEst2 = `${String(h).padStart(2, '0')}:30`;
        const passEst2 = `${String(h).padStart(2, '0')}:44`;
        const transFS2 = `${String(h).padStart(2, '0')}:59`;
        const depOvest2 = `${String(nextH).padStart(2, '0')}:00`;
        const passOvest2 = `${String(nextH).padStart(2, '0')}:14`;
        const arrFS2 = `${String(nextH).padStart(2, '0')}:26`;

        runs.push({
          slot: `${String(h).padStart(2, '0')}:30 – ${String(nextH).padStart(2, '0')}:30`,
          bus: 'Bus 2 (Antiorario CCW)',
          badgeClass: 'badge-bus-ccw',
          depOvest: depEst2,
          passOvest: `${passEst2} (Arlate)`,
          transFS: transFS2,
          passEst: `${passOvest2} (Mondonico)`,
          arrFS: arrFS2,
          s8Milano: `Part. :08 / :38`,
          s8Lecco: `Part. :22 / :52`,
          isPeak
        });
      }
    }

    runs.forEach(r => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><strong>${r.slot}</strong></td>
        <td><span class="${r.badgeClass}">${r.bus}</span></td>
        <td>${r.depOvest}</td>
        <td>${r.passOvest}</td>
        <td><strong>${r.transFS}</strong></td>
        <td>${r.passEst}</td>
        <td><strong>${r.arrFS}</strong></td>
        <td><span class="train-sync-pill">🚆 S8 ${r.s8Milano}</span></td>
        <td><span class="train-sync-pill">🚆 S8 ${r.s8Lecco}</span></td>
      `;
      timetableBody.appendChild(row);
    });
  }

  selectBusFilter.addEventListener('change', renderTimetable);

  // Initial Boot
  initFrazioni();
  updateSemaforo();
  renderTimetable();
});
