# S8 nella mappa di Nodo8

Il livello «S8 · tracciato e treni» è facoltativo e spento all'apertura.
Usa la stessa mappa e lo stesso orologio dei bus. Non crea una seconda
mappa o un secondo ciclo di animazione. È disponibile nella scheda dei bus
e in «Livelli e confronto»; spegnimento, uscita e scorrimento fuori da
Esplora rimuovono treni e tracciato.

## Evidenza e limiti

- 74 corse S8 del **1 ottobre 2026**, 37 per direzione. Inventario
  `RT031_ALL_STATION_DATED_RAIL_INVENTORY_V3`, già riconciliato con RFI.
- Le tre chiamate di ciascuna corsa sono copiate dal medesimo archivio
  ufficiale Trenord GTFS, verificato per SHA256. Soste e orari di arrivo
  e partenza restano distinti.
- Tratto locale **Cernusco-Merate → Olgiate-Calco-Brivio → Airuno**.
  Non è l'intera S8 Milano–Lecco. I treni fuori dal tratto non vengono
  disegnati e non si inventano orari alle estremità della geometria.
- Geometria OpenStreetMap scaricata il **9 ottobre 2026** dall'API
  ufficiale in cinque riquadri. URL e SHA256 dei file sono nell'asset.
  Percorso connesso sui binari principali, 129 vertici complessivi;
  nessuna corda fra stazioni o riparazione di archi mancanti.
- Le coordinate GTFS sono associate al corridoio ferroviario entro
  150 metri, senza connettori artificiali. La scelta di un corridoio
  connesso fra binari paralleli **non certifica binario o piattaforma**.
- Posizione in marcia interpolata per distanza sui vertici reali fra
  partenza e arrivo. Non è una traiettoria osservata, velocità reale,
  GPS, ritardo o cancellazione live.
- L'orario Nodo8 rimane una **proposta 2027**. L'accostamento visivo
  all'orario ferroviario 2026 non garantisce coincidenze né validità 2027.

Colore richiesto: `#f8b1b0`. Icona del treno 24 × 30 px, più piccola
del bus 34 × 42 px. Freccia e descrizione accessibile indicano il senso.
Le icone hanno uno scostamento visivo laterale di 13 px per non sovrapporsi
quando si incrociano: non indica binari diversi o posizioni misurate.

## Riproduzione

`python scripts/build_nodo8_s8_simulation.py --check` riproduce l'asset
con i cinque snapshot OSM e il GTFS congelato in cache. Non riscarica
silenziosamente dati nuovi. Mancanza di geometria connessa, scarto del
GTFS o incongruenza degli orari falliscono chiusi.

`node --test tests/test_nodo8_playback.mjs` verifica tutte le chiamate,
entrambe le direzioni, soste, interpolazione sui vertici, riavvolgimento,
assenza di un timer indipendente e rifiuto di dati incompatibili.

Il registro della proposta, le fermate Nodo8, le 16 corse e tutti i flag
di autorizzazione restano invariati.

## Pubblicazione verificata

- Implementazione: `e3207c112d579b937bb1e6dc94aaeb25befd65c6`.
- Pages: `879c96d2c7b4ae0c3e6aaa8d22ed7acd4a686a32`.
- CI: `37915397006`, conclusione `success`.
- Versione cache: `20261008q`.
- 43 test Python, 8 subtest e 45 test Node passati. Asset ferroviario
  riprodotto byte per byte dal builder; registro Nodo8 ancora conforme
  alle quattro fonti confermate.
- SHA256 verificati via HTTP per tutti i 75 file pubblicati, soltanto due
  pagine HTML. Nessun file storico eliminato, 106 percorsi non selezionati
  preservati nel ramo Pages.
- Verifica browser pubblico: livello spento all'ingresso; alle 07:29:30
  compaiono le due corse verso Milano e Lecco; pausa, avanzamento,
  cambio livello e uscita rispettano l'orologio unico. Controllo locale
  a larghezza 390 px senza overflow orizzontale.
