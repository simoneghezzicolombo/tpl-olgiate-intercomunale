window.TRA_PAESI_DATA = Object.freeze({
  evidence: {
    diagnostic: "aa16a9934a78be9a3ee1230996fcaf72c5657f92",
    stageD: "d41bb678382d018929c1c6b46542f12549f20d4f",
    stageF: "746a17c796f8e5fc24a636e47d304cd9293f2a43",
    validatedOn: "2026-09-04",
    finalists: 4,
    publicTrips: 136,
    routeRows: 8,
    stageFRows: 12
  },
  baseline: {
    global: { 5: 40.1865, 8: 60.8887, 10: 68.7306, 12: 74.71 },
    municipalities: [
      { name: "Brivio", values: { 5: 62.0679, 8: 90.0864, 10: 95.1953, 12: 97.8266 } },
      { name: "Calco", values: { 5: 26.7561, 8: 49.6327, 10: 52.4595, 12: 60.8558 } },
      { name: "La Valletta Brianza", values: { 5: 43.8262, 8: 56.4825, 10: 63.9647, 12: 69.2725 } },
      { name: "Olgiate Molgora", values: { 5: 20.7753, 8: 43.8136, 10: 59.8904, 12: 68.3977 } },
      { name: "Santa Maria Hoè", values: { 5: 80.6623, 8: 91.5244, 10: 94.0004, 12: 94.4813 } }
    ]
  },
  packages: {
    "16": {
      key: "16",
      label: "Pacchetto 16h",
      spanLabel: "16 ore",
      spanStart: "06:00",
      spanEnd: "22:00",
      spanMinutes: 960,
      annualKm: 102915.827244,
      coverage5: 13.41,
      coverage8: 29.28,
      coverage10: 37.3312355625,
      worstMunicipality10: 17.2487715439,
      reach: 33.5054280496,
      stageERetention: 1,
      blockSlack: 5.900345,
      fieldChecks: 3,
      exactTrips: 32,
      combinedPhases: [39],
      combinedPhaseGaps: [60],
      combinedRegular: true,
      topologyPubliclyIdentical: true,
      routes: [
        {
          ordinal: 1,
          routeId: "R2_23d58cd05658247380d7",
          phase: 39,
          publicRuntime: 24.099655211,
          trips: 16,
          firstDeparture: "06:39",
          lastDeparture: "21:39",
          firstEnd: "07:03",
          lastEnd: "22:03",
          perfectClockface: true,
          technicalClosureMin: 0,
          anchors: [
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" },
            { id: "existing:EX_033", label: "S. Maria Hoè · Tremonte / via Leopardi", kind: "existing" },
            { id: "P2V2S_0089", label: "Bernaga inferiore", detail: "fermata candidata", kind: "proposed" },
            { id: "existing:EX_027", label: "Perego · S.S. 342 / via S. Caterina", kind: "existing" },
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" }
          ]
        },
        {
          ordinal: 2,
          routeId: "R2_65db885119e69d50c7d4",
          phase: 39,
          publicRuntime: 24.01897326,
          trips: 16,
          firstDeparture: "06:39",
          lastDeparture: "21:39",
          firstEnd: "07:03",
          lastEnd: "22:03",
          perfectClockface: true,
          technicalClosureMin: 0,
          anchors: [
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" },
            { id: "existing:EX_018", label: "Olgiate Molgora · via Statale", kind: "existing" },
            { id: "existing:EX_008", label: "Brivio · Beverate paese", kind: "existing" },
            { id: "P2V2S_0039", label: "Olgiate Molgora", detail: "fermata candidata 0039", kind: "proposed" },
            { id: "P2V2S_0027", label: "Olgiate Molgora · area centro sportivo", detail: "fermata candidata", kind: "proposed" },
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" }
          ]
        }
      ],
      robustness: {
        low:  { label: "Frizione bassa", bidirectional: 1, railToBus: 1, busToRail: 1, vehicles: 2, extraVehicles: 0 },
        mid:  { label: "Frizione media", bidirectional: 1, railToBus: 1, busToRail: 1, vehicles: 2, extraVehicles: 0 },
        high: { label: "Frizione alta", bidirectional: 0.5, railToBus: 0.5, busToRail: 1, vehicles: 2, extraVehicles: 0 }
      }
    },
    "18.5": {
      key: "18.5",
      label: "Pacchetto 18h30",
      spanLabel: "18 ore e 30",
      spanStart: "05:30",
      spanEnd: "00:00",
      spanMinutes: 1110,
      annualKm: 108661.124675,
      coverage5: 13.17,
      coverage8: 27.99,
      coverage10: 36.7052696251,
      worstMunicipality10: 17.19969483,
      reach: 35.021925987,
      stageERetention: 0,
      blockSlack: 11.598753,
      fieldChecks: 1,
      exactTrips: 36,
      combinedPhases: [3, 7],
      combinedPhaseGaps: [4, 56],
      combinedRegular: false,
      topologyPubliclyIdentical: true,
      routes: [
        {
          ordinal: 1,
          routeId: "R2_b2032eeb31cba06561f0",
          phase: 7,
          publicRuntime: 13.999008327,
          trips: 18,
          firstDeparture: "06:07",
          lastDeparture: "23:07",
          firstEnd: "06:21",
          lastEnd: "23:21",
          perfectClockface: true,
          technicalClosureMin: 0,
          anchors: [
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" },
            { id: "existing:EX_018", label: "Olgiate Molgora · via Statale", kind: "existing" },
            { id: "existing:EX_008", label: "Brivio · Beverate paese", kind: "existing" },
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" }
          ]
        },
        {
          ordinal: 2,
          routeId: "R2_2ffb6743b10bb3f0a97d",
          phase: 3,
          publicRuntime: 22.40124738,
          trips: 18,
          firstDeparture: "06:03",
          lastDeparture: "23:03",
          firstEnd: "06:25",
          lastEnd: "23:25",
          perfectClockface: true,
          technicalClosureMin: 0,
          anchors: [
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" },
            { id: "existing:EX_042", label: "Rovagnate · semaforo", kind: "existing" },
            { id: "P2V2S_0103", label: "Bruggione", detail: "fermata candidata", kind: "proposed" },
            { id: "existing:EX_032", label: "S. Maria Hoè · Alpino", kind: "existing" },
            { id: "rail:S01514", label: "Olgiate-Calco-Brivio FS", kind: "hub" }
          ]
        }
      ],
      robustness: {
        low:  { label: "Frizione bassa", bidirectional: 0.485714286, railToBus: 0.739130435, busToRail: 0.485714286, vehicles: 2, extraVehicles: 0 },
        mid:  { label: "Frizione media", bidirectional: 0.485714286, railToBus: 0.739130435, busToRail: 0.485714286, vehicles: 2, extraVehicles: 0 },
        high: { label: "Frizione alta", bidirectional: 0.485714286, railToBus: 0.739130435, busToRail: 0.485714286, vehicles: 2, extraVehicles: 0 }
      }
    }
  },
  finalists: {
    loops16:  { alias: "TT-TWO-16", topology: "two_independent_loops", topologyLabel: "Due anelli indipendenti", packageKey: "16", timetable: "D4RT001V3_a81a3718416f5cb2" },
    fig16:    { alias: "TT-FIG-16", topology: "interlined_figure8", topologyLabel: "Figure-8 interlineato", packageKey: "16", timetable: "D4RT001V3_a83abc3b41a4ee68" },
    loops185: { alias: "TT-TWO-18.5", topology: "two_independent_loops", topologyLabel: "Due anelli indipendenti", packageKey: "18.5", timetable: "D4RT001V3_a87577dd79b3cb3e" },
    fig185:   { alias: "TT-FIG-18.5", topology: "interlined_figure8", topologyLabel: "Figure-8 interlineato", packageKey: "18.5", timetable: "D4RT001V3_c7318c775dcc1931" }
  }
});

(() => {
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "geo-map.css";
  document.head.appendChild(css);
  const dataScript = document.createElement("script");
  dataScript.src = "geo-data.js";
  dataScript.onload = () => {
    const mapScript = document.createElement("script");
    mapScript.src = "geo-map.js";
    document.head.appendChild(mapScript);
  };
  document.head.appendChild(dataScript);
})();
