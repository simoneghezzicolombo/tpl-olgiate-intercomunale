# Gate B — Real spatial integrity

**Stato:** **PASS**  
**Checkpoint:** `AUDIT_CHECKPOINT_2_REAL_SPATIAL`  
**Verbale:** `docs/GATE_B_PASS.md`

Gate B sostituisce integralmente la precedente modellazione spaziale sintetica. Gli output legacy basati su nuclei insediativi manuali, `np.random`, quote inserite a mano, fermate hard-coded o distanze euclidee non sono ammessi come evidenza.

## Input ammessi

- confini comunali ISTAT 2026 dei cinque comuni core;
- WorldPop 2020 100 m reale, con valore raw preservato;
- POSAS ISTAT 2025 per i totali comunali;
- OpenStreetMap acquisito via Overpass con estensione derivata dall'intera geometria ufficiale dei cinque comuni e buffer metrico UTM di 500 m, maggiore del contesto stradale Gate B di 350 m;
- Copernicus DEM GLO-30, trattato correttamente come DSM;
- `stops.txt` del GTFS ufficiale Agenzia TPL Como-Lecco-Varese come fonte primaria delle fermate.

## Popolazione

Ogni cella popolata del raster WorldPop conserva `worldpop_2020_raw`. La variabile `pop_calibrated_2025` è distinta e classificata `ESTIMATE`: per ogni comune il raster viene moltiplicato per un unico fattore in modo da quadrare esattamente con il totale POSAS 2025. Il totale comunale POSAS è letto dalla riga ufficiale `Età=999` e viene verificato indipendentemente contro la somma delle età 0–100, così da impedire il doppio conteggio della riga aggregata. La calibrazione non modifica la distribuzione relativa interna a ciascun comune.

## Grafo pedonale

Il grafo deriva dalle geometrie stradali OSM reali. Sono esclusi motorway, trunk, construction, proposed, raceway e gli archi con accesso pedonale esplicitamente vietato. Le coordinate sono proiettate in UTM 32N per le distanze metriche.

Le quote dei nodi derivano dal Copernicus DSM GLO-30. Il metodo approvato applica un filtro mediano locale 3×3 e successiva interpolazione bilineare continua. Questo riduce l'influenza puntuale di edifici e vegetazione ed evita i falsi gradini altimetrici prodotti dal precedente nearest-pixel sampling sui segmenti OSM corti. Il DSM non viene comunque trattato come DTM bare-earth.

I tempi di cammino sono direzionali e usano la funzione di Tobler sulla pendenza del singolo arco. Per il collegamento cella→grafo è ammesso un connettore massimo di 300 m a 4,8 km/h; la quota di popolazione che richiede connettori maggiori viene esclusa e riportata come controllo di qualità.

La suite impone inoltre guardrail contro il ritorno dell'artefatto DSM: p95 della pendenza assoluta <30%, p99 <50% e meno del 5% degli archi con |slope| >30%.

## Fermate

Le fermate sono selezionate dal GTFS ufficiale entro i cinque comuni, con un buffer geometrico di 150 m per i casi di bordo. Vengono agganciate al grafo OSM con soglia massima di 250 m. OSM `bus_stop` resta solo un possibile cross-check e non definisce il set istituzionale delle fermate.

Spot-check obbligatori su cinque punti GTFS pubblicati:

- `300407` Olgiate Molgora, stazione FS;
- `300063` Brivio, capolinea;
- `300089` Calco, via Statale;
- `300782` Santa Maria Hoè;
- `300804` Rovagnate, La Pesa.

## Accessibilità

Per ogni cella WorldPop viene calcolato il tempo minimo verso una **localizzazione di fermata presente nel GTFS ufficiale** sul grafo pedonale slope-adjusted. Le soglie di audit sono 5, 8, 10 e 12 minuti. Il valore di popolazione della cella è attribuito in base al punto rappresentativo centrale del pixel raster; questa approssimazione è documentata e non viene confusa con una localizzazione puntuale dei residenti.

Gate B misura quindi l'accessibilità spaziale all'infrastruttura di fermata ufficiale. Non implica che ogni fermata abbia un servizio attivo, una determinata frequenza o un servizio utile in ciascuna fascia oraria. La validazione di route, calendari, corse e orari appartiene a Gate C.

## Condizioni minime per PASS

Gate B è PASS perché sono state verificate contemporaneamente:

1. acquisizione OSM che copre l'intera geometria dei cinque comuni;
2. separazione raw WorldPop 2020 / calibrazione 2025;
3. quadratura esatta con POSAS per tutti i comuni senza doppio conteggio della riga aggregata;
4. grafo OSM sufficientemente connesso e pendenze DSM sottoposte a red-team e guardrail;
5. fermate provenienti dal GTFS ufficiale e 5/5 spot-check superati;
6. almeno l'85% della popolazione calibrata collegabile al grafo entro il limite di 300 m, osservato 100%;
7. coperture 5/8/10/12 minuti monotone e comprese tra 0 e 100%;
8. suite CI completa su clone pulito;
9. red-team persistente con sensitivity analysis su connettori, pendenza e controfattuale flat;
10. artifact di audit prodotto dal run validato.

Il verdetto autorevole, i numeri validati e i limiti epistemici sono registrati in `docs/GATE_B_PASS.md`.