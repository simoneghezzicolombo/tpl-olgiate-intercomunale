# Nodo8: audit delle interazioni e della fascia S8

## Problemi riscontrati e correzioni

1. Il popup Nodo8 rimaneva aperto tornando al racconto, anche se la mappa non era più interattiva. Ora si chiude quando il contesto non è attivo. La chiusura ripristina il focus quando opportuno; non sottrae il focus a un altro controllo già selezionato.
2. Le schede D184/D185 e degli altri livelli conservavano uno stile diverso e non gestivano Esc come i popup Nodo8. Ora hanno superficie opaca chiara, contrasto leggibile, titolo di dialogo, chiusura da 44 px e Esc che chiude la scheda senza uscire da Esplora. Una fermata D185 è etichettata D185, non indistintamente D184/D185.
3. L'area cliccabile di un tracciato Nodo8 poteva intercettare il clic su un punto di un altro livello. Ora i punti fermata e pedonali precedono le aree dei tracciati nell'ispezione.
4. Il ridimensionamento poteva riattivare il racconto e perdere Esplora. I refresh del direttore narrativo non sostituiscono una sessione interattiva. Il cambio di dimensioni reinquadra i livelli, senza cambiare orario o selezioni. Tutte le schede narrative sono invisibili durante Esplora, mantenendo il layout. Al ritorno si ripristina il capitolo effettivamente visibile; i collegamenti espliciti ai capitoli continuano a uscire dalla mappa.
5. La regola globale `touch-action:pan-y!important` prevaleva sulle interazioni mobili di MapLibre. Esplora ora usa `touch-action:none!important`, il racconto mantiene lo scorrimento. La mappa è esposta alle tecnologie assistive solo nel contesto interattivo.
6. Lo slider era limitato al giorno dei bus, 06:05–21:18 circa. Nove corse S8 erano interamente fuori dalla finestra raggiungibile; diciassette avevano almeno una parte fuori. Accendendo S8 il confronto si estende ai limiti effettivi del suo dataset: 05:06–00:26 del giorno successivo. Questa fascia rimane disponibile anche nascondendo successivamente S8, per non spostare il clock. Il giorno successivo è indicato nel titolo del clock e nei valori accessibili. Nodo8 non viene estesa: fuori dai suoi blocchi i bus sono fuori corsa, senza posizione inventata. Il modello puro `statesAt` conserva il suo rifiuto dei clock fuori dal giorno dei bus.

## Invarianti

- Nessun nuovo clock, timer di simulazione, orario di servizio, fermata, geometria o veicolo operativo introdotto.
- D184/D185: 34 corse e 422 eventi; restano 374 clock conservati e 48 intermedi derivati, non orari ufficiali riparati.
- S8: 74 corse, 37 per direzione, snapshot 1 ottobre 2026, non GPS, validità 2027 o coincidenze certificate.
- Il confronto accosta fonti di date diverse; non dichiara che siano una giornata operativa simultanea.
- FS resta nel punto geografico e OSM tenue. Fonte e autorità della proposta, calendarizzazione 2027 e copertura immutati. Nessuna scelta normativa o autorizzazione aggiunta.

## Verifica locale

- 107 test Node, 44 test Python e 8 subtest superati; controlli dei builder e degli hash sorgente superati.
- Popup fermata D185 Calco / via Virgilio verificato nel browser: superficie `rgb(245,242,233)`, testo `rgb(21,61,52)`.
- Telefono simulato, 375×812 e 812×375 CSS px: Esplora e riproduzione conservati durante la rotazione; nessuna scheda narrativa visibile sulla mappa. Popup Aldo Moro conserva due eventi e sta dentro il viewport; Esc non esce da Esplora.
- `touch-action:none` e accessibilità del contenitore verificati nel browser. Il backend non supporta l'iniezione di gesti touch: non si dichiara prova su telefono fisico.
- S8: accensione allarga i limiti da 365–1278,3027 a 306–1466 minuti, senza spostare le 07:35 selezionate. Alle 00:26 risulta ancora una corsa S8, i quattro bus Nodo8 sono fuori corsa; spegnere S8 mantiene orario e fascia.
- Nessun errore console osservato nelle prove locali.

## Pubblicazione verificata

- Sorgente: `ec542ca7508c10766fc2c336072a14663eb59ce1`.
- Pages: `11408c8aa67ead1558279b5cc6ac30d7953ac656`, senza eliminazioni delle sorgenti precedenti.
- CI `Publish final Nodo8 only`, esecuzione `38063492766`: successo.
- Verificati via HTTP tutti gli 88 file pubblicati, con zero differenze rispetto agli hash del manifest; solo due pagine HTML.
- Browser pubblico: S8 raggiungibile alle 00:26 del giorno successivo, una corsa ancora attiva, quattro bus Nodo8 fuori corsa. Popup D185 / via Virgilio leggibile; Esc lascia Esplora attiva e chiude il popup. Ritorno al racconto: nessun popup residuo, contenitore della mappa di nuovo escluso dalle tecnologie assistive.
- Prova visiva locale esclusa dalla pubblicazione: `cache/nodo8-website-preview/nodo8-d185-readable-20261010g-public.png`.
