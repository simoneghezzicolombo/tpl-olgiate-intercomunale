# Nodo8: ricostruzione delle animazioni e usabilità

Data: 10 ottobre 2026. Questa revisione riguarda la presentazione del sito e il modello di animazione delle linee esistenti. Non modifica percorso, fermate, orario, calendario, chilometri o autorizzazioni della proposta Nodo8.

## Correzione effettiva delle sparizioni

Il precedente renderer sospendeva l'icona nei 48 intervalli del GTFS che, combinati con la geometria, producevano velocità medie implicite implausibili. L'avvertenza non risolveva l'esperienza della mappa.

Il nuovo modello separa rigorosamente tre elementi:

1. `assets/nodo8-current-simulation.json`: proiezione immutata della fonte ufficiale, con gli orari originali.
2. `assets/nodo8-current-playback.json`: geometria delle occorrenze e profilo temporale derivato, riproducibile, esclusivamente per l'animazione.
3. `nodo8-current-playback.mjs`: validazione delle evidenze e interpolazione lungo i vertici della shape ufficiale, sullo stesso orologio di Nodo8 e S8.

Tutte le 34 corse sono presenti durante la rispettiva finestra originale. Non sono identificazioni di autobus fisici, posizioni GPS o osservazioni di velocità. Non viene riscritto alcun orario ufficiale.

## Fonti e giorno rappresentato

- [GTFS pubblicato dall'Agenzia](https://halleyweb.com/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/172): archivio 2025/26, versione `20251217`, validità 1 gennaio–8 giugno 2026. SHA-256 `f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b`.
- [Avviso ufficiale sulla chiusura del ponte di Brivio](https://bergamo.arriva.it/notice/linea-d185-chiusura-ponte-di-brivio/): deviazione D185 dal 4 maggio 2026.
- Il calendario e le eccezioni del GTFS sono controllati per martedì **28 aprile 2026**, precedente alla deviazione. Le 15 corse D184 e 19 D185, con ID, direzione e shape, coincidono esattamente con le 34 della precedente proiezione del 6 maggio, che rimane immutata. Il cambio del giorno visualizzato non è una semplice sostituzione di etichetta.
- Non è l'orario più recente 2026/27. Quest'ultimo rimane la fonte separata del confronto delle partenze da FS. Il sito distingue esplicitamente i due confronti.
- La proiezione raw ha SHA-256 `25cbd96b4939acb02fc018448bb20a3e9b605b4aa924a348638ed2fa7848ce97`, normalizzando CRLF a LF. Il riferimento di stazione è nella proposta immutata, SHA-256 normalizzato `dd9b8bda3f5dc0bc039d0ab5874f8a64ff9f76db860f625657997fb7af34a8c9`.

I PDF storici sono stati controllati, ma non forniscono un insieme completo di ancore collegabile senza ambiguità alle corse GTFS: il D184 contiene differenze di etichette/orari; il file D185 denominato `inv25` presenta un calendario estivo e orari diversi. Non sono usati per inventare una correzione ufficiale. Il GTFS non contiene la colonna `timepoint`; non è certificato il meccanismo del produttore che ha generato le incongruenze.

## Geometria e FS

Le fermate sono riferite alle rispettive shape con un adattamento monotono globale a minimi quadrati. L'ordine delle occorrenze resta parte dello stato: non si seleziona una proiezione indipendente che potrebbe saltare all'indietro o confondere un ritorno con una partenza. Nessun vertice della shape è modificato e non si usano segmenti diretti fra paline.

410 delle 422 occorrenze si allineano entro 1,891 metri. Le 12 occorrenze terminali del codice `300407` hanno invece un riferimento sorgente a circa 500 metri dalla stazione ferroviaria. È adottata una politica **esplicita di visualizzazione**, non una certificazione della palina:

- Nei ritorni, soltanto su tre shape e direzioni dichiarate, il bus termina all'estremo della sua shape ufficiale, distante 4–7 metri dal riferimento FS congelato. Il controllo fallisce se l'estremo supera 50 metri dal riferimento.
- Le dieci partenze originate su FS via Statale restano sull'estremo della shape lungo la Statale. Non si inventa un raccordo da/per il piazzale ferroviario.
- Coordinate raw, scarto geometrico e ruolo di ogni occorrenza rimangono nell'evidenza derivata. `physical_stop_relocated=false`.
- Il livello dei minuti a piedi continua a usare le coordinate GTFS originali delle paline: gli ancoraggi dell'animazione non modificano la copertura.

## Profilo temporale stimato

L'algoritmo conserva partenza e arrivo finale e il massimo numero di ancore temporali interne compatibili con il riferimento geometrico e un tetto ingegneristico di 90 km/h medi per intervallo. Le parità sono risolte con l'ordine lessicografico degli indici sorgente, senza pesi o preferenze territoriali.

- 422 occorrenze complessive.
- **374 orari sorgente conservati**, inclusi tutti gli estremi di corsa.
- **48 tempi interni stimati** per distanza lungo la shape fra ancore conservate.
- 34 corse fattibili nel modello grafico; zero intervalli derivati sopra il tetto.
- Massima media derivata: 82,627 km/h; massimo scostamento interno: 213,068 secondi. Sono valori del modello, non velocità osservate o ammesse su quelle strade.

Il tetto non è un limite stradale, una certificazione fisica o una prova di puntualità. Il modello non ricostruisce accelerazioni, traffico o soste non osservate. Nella fonte, tutte le 422 occorrenze hanno arrivo uguale a partenza: non sono aggiunti tempi di sosta. Se gli estremi di una corsa fossero incompatibili, il profilo fallirebbe senza modificarli. Le 48 stime sono marcate separatamente, con gli orari raw sempre disponibili.

## Interfaccia

- La pagina principale apre con D184/D185 → Nodo8 e il confronto di vicinanza a piedi, qualificato come modello di popolazione, non passeggeri. Quattro accessi immediati portano a percorso, orari, copertura e racconto.
- Restano tutte le sezioni e le funzioni; sono rese più leggibili anche su schermi piccoli.
- Nell'esplorazione, i controlli possono essere ridotti a orologio, reti attive e riproduzione. La mappa e il medesimo orologio continuano a funzionare: nessuna seconda simulazione.
- Le schede fermata mostrano in breve i tempi da/verso FS in minuti e secondi, preservando le occorrenze ripetute e raccogliendo il metodo in una sezione chiusa.
- I quattro bus Nodo8 sono selezionabili da tastiera o dalla mappa senza restringere la vista a una corsa. Mantengono lo stesso colore di linea anche in sosta, con un bordo distinto: non diventano D185.
- La mappa interattiva è piana e più leggibile; il racconto conserva le sue viste inclinate. S8, linee esistenti e minuti a piedi delle sole reti attive restano disponibili.
- Giorni, fonti, stime e limiti sono raccolti in `Dati e metodo`, senza ripeterli accanto a ogni comando.

## Verifiche

Prima della pubblicazione: 91 test Node, 44 test Python e 8 sottotest verdi. Il builder del sito conferma le quattro fonti della proposta; il nuovo builder riproduce esattamente il modello derivato e verifica il calendario nell'archivio fissato per hash. La pubblicazione continua a contenere soltanto due pagine HTML e le dipendenze ammesse, preservando nel repository i siti ritirati.

Controllati in browser: scheda fermata e chiusura con Escape, focus bus senza cambio della corsa, riduzione dei controlli con riproduzione ancora attiva e pausa sullo stesso orologio. Controllate larghezze 320, 375 e 768 px senza overflow orizzontale della pagina principale. Proposta e proiezione GTFS raw restano immutate.
