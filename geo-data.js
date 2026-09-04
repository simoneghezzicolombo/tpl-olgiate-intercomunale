window.TRA_PAESI_GEO = Object.freeze({
  provenance: {
    finalists: "aa16a9934a78be9a3ee1230996fcaf72c5657f92",
    currentServiceV4: "95d99b52bff4558c6ab40b5514fa6d09ba3b1e50",
    currentGtfsFrozen: "4ab527827456eb40572a72b4c7b87f8fe5f4dcac",
    stationCoordinate: "OSM node 7788578506 / Wikidata Q3970347, verified 2026-09-04",
    geometryContract: "Road-following geometries are reconstructed for visualization from certified/frozen stop order. They are not official route alignments."
  },
  center: [45.7365, 9.3995],
  initialBounds: [[45.716, 9.345], [45.750, 9.447]],
  hub: {
    id: "rail:S01514",
    name: "Olgiate-Calco-Brivio FS",
    municipality: "Olgiate Molgora",
    lat: 45.72918,
    lon: 9.40384,
    kind: "hub",
    source: "OSM/Wikidata coordinate, diagnostic rail anchor identity"
  },
  proposedStops: {
    "existing:EX_033": { id:"existing:EX_033", name:"S. Maria Hoè · Tremonte / via Leopardi", municipality:"Santa Maria Hoè", lat:45.74118, lon:9.38096, kind:"existing", source:"certified stop universe" },
    "P2V2S_0089": { id:"P2V2S_0089", name:"Bernaga inferiore", municipality:"La Valletta Brianza", lat:45.734210392424224, lon:9.35294110962455, kind:"proposed", source:"certified Phase 2 candidate" },
    "existing:EX_027": { id:"existing:EX_027", name:"Perego · S.S. 342 / via S. Caterina", municipality:"La Valletta Brianza", lat:45.738567, lon:9.362733, kind:"existing", source:"certified stop universe" },
    "existing:EX_018": { id:"existing:EX_018", name:"Olgiate Molgora · via Statale", municipality:"Olgiate Molgora", lat:45.728633, lon:9.400417, kind:"existing", source:"certified stop universe" },
    "existing:EX_008": { id:"existing:EX_008", name:"Brivio · Beverate paese", municipality:"Brivio", lat:45.73735, lon:9.427967, kind:"existing", source:"certified stop universe" },
    "P2V2S_0039": { id:"P2V2S_0039", name:"Olgiate Molgora · corridoio sud-ovest", municipality:"Olgiate Molgora", lat:45.72364262142197, lon:9.392917194407225, kind:"proposed", source:"certified Phase 2 candidate" },
    "P2V2S_0027": { id:"P2V2S_0027", name:"Olgiate Molgora · area centro sportivo", municipality:"Olgiate Molgora", lat:45.719573868777296, lon:9.401297845150202, kind:"proposed", source:"certified Phase 2 candidate" },
    "existing:EX_042": { id:"existing:EX_042", name:"Rovagnate · semaforo", municipality:"La Valletta Brianza", lat:45.737133, lon:9.370467, kind:"existing", source:"certified stop universe" },
    "P2V2S_0103": { id:"P2V2S_0103", name:"Bruggione", municipality:"Olgiate Molgora", lat:45.73682948513192, lon:9.397919695864566, kind:"proposed", source:"certified Phase 2 candidate" },
    "existing:EX_032": { id:"existing:EX_032", name:"S. Maria Hoè · Alpino", municipality:"Santa Maria Hoè", lat:45.743617, lon:9.374617, kind:"existing", source:"certified stop universe" }
  },
  proposedPackages: {
    "16": [
      { id:"16-r1", ordinal:1, label:"Ramo 1 · Valletta / Santa Maria Hoè", phase:39, runtime:24.099655211, trips:16, first:"06:39", last:"21:39", end:"22:03", anchors:["rail:S01514","existing:EX_033","P2V2S_0089","existing:EX_027","rail:S01514"] },
      { id:"16-r2", ordinal:2, label:"Ramo 2 · Olgiate / Beverate", phase:39, runtime:24.01897326, trips:16, first:"06:39", last:"21:39", end:"22:03", anchors:["rail:S01514","existing:EX_018","existing:EX_008","P2V2S_0039","P2V2S_0027","rail:S01514"] }
    ],
    "18.5": [
      { id:"185-r1", ordinal:1, label:"Ramo 1 · Olgiate / Beverate", phase:7, runtime:13.999008327, trips:18, first:"06:07", last:"23:07", end:"23:21", anchors:["rail:S01514","existing:EX_018","existing:EX_008","rail:S01514"] },
      { id:"185-r2", ordinal:2, label:"Ramo 2 · Valletta / Bruggione / Santa Maria Hoè", phase:3, runtime:22.40124738, trips:18, first:"06:03", last:"23:03", end:"23:25", anchors:["rail:S01514","existing:EX_042","P2V2S_0103","existing:EX_032","rail:S01514"] }
    ]
  },
  currentStops: {
    "300194": {name:"Ravellino",lat:45.772420,lon:9.368830}, "L00808": {name:"Colle Brianza · Nava",lat:45.763100,lon:9.362467}, "L00807": {name:"Colle Brianza · Piecastello",lat:45.759400,lon:9.361683}, "L00873": {name:"Hoè",lat:45.748600,lon:9.368017}, "L00782": {name:"Santa Maria Hoè",lat:45.744333,lon:9.373583}, "L00902": {name:"Santa Maria Hoè · Alpino",lat:45.743567,lon:9.374367}, "L00879": {name:"Rovagnate · Vinicola Ghezzi",lat:45.739800,lon:9.364650}, "L00872": {name:"Perego · S.S. 342 / via S. Caterina",lat:45.738483,lon:9.362667}, "L00878": {name:"Rovagnate · semaforo",lat:45.737133,lon:9.370467}, "L00804": {name:"Rovagnate · la pesa",lat:45.737217,lon:9.374867}, "L00871": {name:"Santa Maria Hoè · Alduno",lat:45.734700,lon:9.382517}, "L00803": {name:"Olgiate Molgora · Monticello Scarpone",lat:45.731300,lon:9.390150}, "300407": {name:"Olgiate Molgora · stazione FS",lat:45.733710,lon:9.405760},
    "300803": {name:"Olgiate Molgora · Monticello Scarpone",lat:45.731330,lon:9.390270}, "300871": {name:"Santa Maria Hoè · Alduno",lat:45.735000,lon:9.382200}, "300804": {name:"Rovagnate · la pesa",lat:45.737250,lon:9.374517}, "300878": {name:"Rovagnate · semaforo",lat:45.737167,lon:9.369383}, "300872": {name:"Perego · S.S. 342 / via S. Caterina",lat:45.738567,lon:9.362733}, "300879": {name:"Rovagnate · Vinicola Ghezzi",lat:45.739700,lon:9.364717}, "300902": {name:"Santa Maria Hoè · Alpino",lat:45.743617,lon:9.374617}, "300782": {name:"Santa Maria Hoè",lat:45.744283,lon:9.373817}, "300873": {name:"Hoè",lat:45.748667,lon:9.367717}, "300807": {name:"Colle Brianza · Piecastello",lat:45.759617,lon:9.361850}, "300808": {name:"Colle Brianza · Nava",lat:45.763200,lon:9.362617}, "300969": {name:"Ravellino · via San Rocco",lat:45.770180,lon:9.367440},
    "L00407": {name:"Olgiate Molgora · stazione FS",lat:45.729170,lon:9.404410}, "L00729": {name:"Calco · via Virgilio / pensilina",lat:45.724950,lon:9.410183}, "L00397": {name:"Calco · via Virgilio",lat:45.724950,lon:9.414367}, "300086": {name:"Brivio · Beverate Cariplo",lat:45.740400,lon:9.423083}, "300398": {name:"Brivio · Beverate paese",lat:45.737350,lon:9.427967}, "300487": {name:"Brivio · Beverate tre strade",lat:45.734650,lon:9.426850}, "300087": {name:"Brivio · Vaccarezza",lat:45.736850,lon:9.436083}, "300406": {name:"Brivio · via Como",lat:45.742417,lon:9.439367}, "300063": {name:"Brivio · capolinea",lat:45.741333,lon:9.445700}, "L00405": {name:"Cisano · sosta",lat:45.739967,lon:9.451383}, "L00486": {name:"Cisano · via Torchio",lat:45.741183,lon:9.461650}, "L00062": {name:"Cisano · bivio Brivio",lat:45.740633,lon:9.471733}, "L00404": {name:"Cisano · corso Mazzini",lat:45.740117,lon:9.475100}, "L00484": {name:"Cisano · municipio",lat:45.739667,lon:9.478250}, "L00483": {name:"Caprino · Bosco",lat:45.741250,lon:9.483483}, "L00402": {name:"Caprino · piazza Marconi",lat:45.744783,lon:9.482233},
    "300402": {name:"Caprino · piazza Marconi",lat:45.744850,lon:9.482017}, "300483": {name:"Caprino · Bosco",lat:45.741283,lon:9.483367}, "300403": {name:"Caprino · Cava",lat:45.738867,lon:9.484067}, "300484": {name:"Cisano · municipio",lat:45.739683,lon:9.478567}, "300404": {name:"Cisano · corso Mazzini",lat:45.740283,lon:9.474517}, "300062": {name:"Cisano · bivio Brivio",lat:45.740850,lon:9.470500}, "300405": {name:"Cisano · sosta",lat:45.739883,lon:9.451267}, "L00063": {name:"Brivio · capolinea",lat:45.742450,lon:9.445850}, "L00406": {name:"Brivio · via Como",lat:45.742267,lon:9.439133}, "L00087": {name:"Brivio · Vaccarezza",lat:45.737017,lon:9.436200}, "L00487": {name:"Brivio · Beverate quattro strade",lat:45.734767,lon:9.426933}, "L00398": {name:"Brivio · Beverate paese",lat:45.737317,lon:9.428150}, "L00086": {name:"Brivio · Beverate Cariplo",lat:45.740517,lon:9.423083}, "300956": {name:"Calco · via Nazionale 85",lat:45.736600,lon:9.419670}, "300634": {name:"Calco · via Nazionale",lat:45.729600,lon:9.417783}, "300397": {name:"Calco · via Virgilio",lat:45.724950,lon:9.414950}, "300729": {name:"Calco · via Virgilio / pensilina",lat:45.725017,lon:9.409950}
  },
  currentPatterns: [
    { id:"D184-in", route:"D184", direction:"Ravellino → Olgiate FS", tripCount:5, stopIds:["300194","L00808","L00807","L00873","L00782","L00902","L00879","L00872","L00878","L00804","L00871","L00803","300407"] },
    { id:"D184-out", route:"D184", direction:"Olgiate FS → Ravellino", tripCount:4, stopIds:["300407","300803","300871","300804","300878","300872","300879","300902","300782","300873","300807","300808","300969"] },
    { id:"D185-out", route:"D185", direction:"Olgiate FS → Caprino", tripCount:9, stopIds:["L00407","L00729","L00397","300086","300398","300487","300087","300406","300063","L00405","L00486","L00062","L00404","L00484","L00483","L00402"] },
    { id:"D185-in", route:"D185", direction:"Caprino → Olgiate FS", tripCount:7, stopIds:["300402","300483","300403","300484","300404","300062","300405","L00063","L00406","L00087","L00487","L00398","L00086","300956","300634","300397","300729","300407"] }
  ]
});