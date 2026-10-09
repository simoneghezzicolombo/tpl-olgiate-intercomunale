# Esplora Nodo8: interfaccia e qualità della simulazione

## Interfaccia

Quattro interruttori indipendenti: Nodo8, S8, D184 e D185. Un solo orologio,
trascinabile su tutta la giornata del progetto. Nodo8 parte con tutti e quattro
i mezzi di modello alle 07:35. Una riga per mezzo mostra destinazione e prossimo
orario; selezionare la riga inquadra il bus senza restringere la simulazione.
Riproduzione accelerata e pausa restano disponibili.

Eliminati dall'esploratore il selettore di corsa, il selettore di fermata,
le alternative storiche e i punti candidati. Le fermate si aprono sulla mappa.
La stazione è un disco bianco con FS; il nome completo resta nell'etichetta
accessibile. Spiegazioni e date sono raccolte in Dati e metodo, chiuso inizialmente.
Le scene della ricerca storica e le funzionalità della pagina principale restano.

## Minuti a piedi delle sole reti accese

`assets/nodo8-active-walk.json`, contratto
`nodo8_active_network_population_walk_v1`, contiene tre vettori indipendenti:
Nodo8, D184 e D185. Il livello usa il minimo dei soli vettori accesi; senza reti
bus accese è vuoto. S8 non contribuisce. Spegnere le icone delle fermate non
modifica l'appartenenza delle fermate alla rete abilitata.

4.283 unità core RT016 sono unite alla matrice RT028 per identità esatta,
non per ordine di righe o prossimità alle vecchie sagome di edificio.
Grafo pedonale congelato, 80 m/min, connettori popolazione e fermata inclusi.
I tre vettori hanno 3.661 unità con cammino modellato e 622 senza connessione
modellata. Null non significa zero minuti e viene visualizzato in grigio.

Nodo8 riproduce tutte le 18 percentuali territoriali certificate a 5/8/10 minuti.
D184 usa 29 identità fermata delle proprie corse datate; D185 ne usa 43.
29 fermate D184 e 31 D185 si collegano al grafo; 12 esterne D185 no.
Questa è accessibilità spaziale potenziale del modello, non frequenza,
direzione utile, domanda osservata o accessibilità universale.

Ricostruzione deterministica:

```text
python scripts/build_nodo8_active_walk.py --check
node --test tests/test_nodo8_active_walk.mjs
```

## D184/D185: completezza non equivale a precisione fisica

L'asset congelato conserva tutte le corse GTFS attive il 6 maggio 2026:
15 D184 e 19 D185, 17 shape, 422 chiamate e 388 intervalli fra chiamate.
Non è il servizio 2026/27, una localizzazione GPS o un inventario di mezzi fisici.
Tracciati, chiamate e orari vengono dallo stesso archivio ufficiale, senza tempi
inventati dal nostro builder.

L'audit ha verificato 2.784 posizioni ai confini e all'interno degli intervalli,
oltre a 68 controlli fuori finestra. La copia/interpolazione rispetta il feed,
ma il feed ha incoerenze: 50 intervalli consecutivi durano 10 secondi;
48 dei 388 implicano oltre 90 km/h medi lungo la shape. Il caso estremo è
Celana -> Caprino-roccolino, 14:11:00 -> 14:11:10, circa 1.570 metri e 565 km/h.
Questi orari sono già nella fonte, non un errore di conversione minuti/secondi.
La fonte non contiene `timepoint`; non possiamo attribuire questi casi a un
flag esplicito di tempo stimato o dedurne il procedimento di esportazione.

`currentPositionQuality` applica un filtro di visualizzazione a 90 km/h medi:
negli intervalli sopra soglia non disegna l'icona, mantenendo la corsa nel
conteggio e mostrando quante posizioni non sono affidabili. È un controllo
prudenziale dell'animazione, non un limite legale, una prova di fattibilità
o una certificazione degli intervalli sotto soglia. Il dataset e
`currentTripsAt` restano immutati: nessun rallentamento correttivo inventato.

Tutte le 422 chiamate hanno arrivo uguale alla partenza: non viene aggiunta
una sosta artificiale. Coordinate fermata e posizione alla distanza GTFS sulla
shape possono discostarsi fino a circa 546,5 metri; 20 occorrenze superano
100 metri. Questi scarti restano diagnostici, non sono corretti con snap taciti.
Anche le posizioni visualizzate non sono quindi certificate come posizione
fisica esatta presso la palina. Per una simulazione operativa accurata servono
tempi intermedi e riferimenti spaziali della fonte riconciliati.

## Invarianti conservate

Nessuna modifica a percorso, fermate, corse, calendario, chilometri o autorità
della proposta. Nessun peso accessibilità-frequenza, passeggero stimato,
probabilità empirica di coincidenza o budget normativo nuovo.
Due sole pagine HTML pubblicate; prototipi e fonti ritirati restano in Git.

## Riscontro del rilascio 20261009b

Implementazione: `1593446951142dd83ca0bace51899aa6f54182f1`.
Pages: `946f2a0f504b46dbbd14ec91ed4007aa2662ad2e`.
[Workflow 37977750305](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/37977750305)
riuscito. Il manifest pubblico identifica questa revisione; tutti gli 83 file
pubblicati sono stati riscaricati e confrontati byte per byte via SHA-256.
Esattamente due pagine HTML; 106 percorsi Git non selezionati conservati.

66 test Node, 44 test Python e 8 subtest passati. Il builder pedonale in modalità
check riproduce l'asset. La proposta originale riproduce ancora tutte le fonti
certificate, senza modifiche di orario, siti, geometria o autorità.

Nel browser pubblico verificati: quattro righe bus e selezione all a 07:35,
assenza del selettore di corsa, dettagli tecnici chiusi, pannello interamente
visibile senza scorrimento a 1280x720, selezioni indipendenti, vettore pedonale
D184 da solo (4.283 punti), riproduzione x300 e pausa, nessun errore console.
Le verifiche locali coprono anche unione delle tre reti, D185 da sola, assenza
di reti bus (zero punti), focus del bus che conserva orologio e selezione.

Riscontro visivo locale:
`cache/nodo8-website-preview/nodo8-explorer-compact-published-20261009b.png`.
Questo riscontro documenta la pubblicazione, non aumenta il grado di precisione
fisica del GTFS o autorizza il servizio.
