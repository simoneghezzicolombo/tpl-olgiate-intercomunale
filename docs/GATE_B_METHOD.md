# Gate B — Real spatial integrity

**Stato:** IN VALIDAZIONE  
**Checkpoint:** `AUDIT_CHECKPOINT_2_REAL_SPATIAL`

Gate B sostituisce integralmente la precedente modellazione spaziale sintetica. Gli output legacy basati su nuclei insediativi manuali, `np.random`, quote inserite a mano, fermate hard-coded o distanze euclidee non sono ammessi come evidenza.

## Input ammessi

- confini comunali ISTAT 2026 dei cinque comuni core;
- WorldPop 2020 100 m reale, con valore raw preservato;
- POSAS ISTAT 2025 per i totali comunali;
- OpenStreetMap acquisito via Overpass con estensione derivata dall'intera geometria ufficiale dei cinque comuni e buffer metrico UTM di 500 m, maggiore del contesto stradale Gate B di 350 m;
- Copernicus DEM GLO-30, trattato correttamente come DSM;
- `stops.txt` del GTFS ufficiale Agenzia TPL Como-Lecco-Varese come fonte primaria delle fermate.

## Popolazione

Ogni cella popolata del raster WorldPop conserva `worldpop_2020_raw`. La variabile `pop_calibrated_2025` è distinta e classificata `DERIVED`: per ogni comune il raster viene moltiplicato per un unico fattore in modo da quadrare esattamente con il totale POSAS 2025. La calibrazione non modifica la distribuzione relativa interna a ciascun comune.

## Grafo pedonale

Il grafo deriva dalle geometrie stradali OSM reali. Sono esclusi motorway, trunk, construction, proposed, raceway e gli archi con accesso pedonale esplicitamente vietato. Le coordinate sono proiettate in UTM 32N per le distanze metriche.

Le quote dei nodi sono campionate dal Copernicus DSM mediante mediana locale 3×3. Questa procedura riduce l'influenza puntuale di edifici e vegetazione, ma non trasforma il DSM in un DTM bare-earth. La distinzione resta esplicita.

I tempi di cammino sono direzionali e usano la funzione di Tobler sulla pendenza del singolo arco. Per il collegamento cella→grafo è ammesso un connettore massimo di 300 m a 4,8 km/h; la quota di popolazione che richiede connettori maggiori viene esclusa e riportata come controllo di qualità.

## Fermate

Le fermate sono selezionate dal GTFS ufficiale entro i cinque comuni, con un buffer geometrico di 150 m per i casi di bordo. Vengono agganciate al grafo OSM con soglia massima di 250 m. OSM `bus_stop` resta solo un possibile cross-check e non definisce il set istituzionale delle fermate.

Spot-check obbligatori su cinque punti GTFS pubblicati:

- `300407` Olgiate Molgora, stazione FS;
- `300063` Brivio, capolinea;
- `300089` Calco, via Statale;
- `300782` Santa Maria Hoè;
- `300804` Rovagnate, La Pesa.

## Accessibilità

Per ogni cella WorldPop viene calcolato il tempo minimo verso una fermata GTFS sul grafo pedonale slope-adjusted. Le soglie di audit sono 5, 8, 10 e 12 minuti. Il valore di popolazione della cella è attribuito in base al punto rappresentativo centrale del pixel raster; questa approssimazione è documentata e non viene confusa con una localizzazione puntuale dei residenti.

## Condizioni minime per PASS

Gate B non può essere dichiarato PASS finché non sono contemporaneamente verificati:

1. acquisizione OSM che copre l'intera geometria dei cinque comuni;
2. separazione raw WorldPop 2020 / calibrazione 2025;
3. quadratura esatta con POSAS per tutti i comuni;
4. grafo OSM sufficientemente connesso e con pendenze reali dal DSM;
5. fermate provenienti dal GTFS ufficiale e spot-check superati;
6. almeno l'85% della popolazione calibrata collegabile al grafo entro il limite di 300 m;
7. coperture 5/8/10/12 minuti monotone e comprese tra 0 e 100%;
8. suite CI completa su clone pulito.

Il PASS finale viene assegnato solo dopo revisione dei risultati numerici e dei failure reali della CI.
