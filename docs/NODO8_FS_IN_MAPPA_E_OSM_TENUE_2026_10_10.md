# FS dentro la mappa e sfondo OSM tenue

Revisione `20261010d`, 10 ottobre 2026. Solo presentazione e interazione: nessuna modifica alla proposta, alle fonti di servizio o ai relativi orari, fermate, geometrie e chilometri.

## FS non è un segnaposto animato

Eliminato il vecchio elemento HTML `.hub-marker`, comprese le regole CSS che interpolavano la sua trasformazione. Quel badge aveva un ciclo di aggiornamento diverso dal disegno della mappa e appariva scivolare durante i cambi di vista.

La scritta FS è ora un glifo locale disegnato dal motore della mappa, centrato dentro il punto bianco della stazione. Punto e scritta condividono la stessa sorgente geografica. Non dipendono da font/glyph server remoto, dall'orologio o da una posizione di autobus.

La fonte storica `hub` rimane immutata. Nelle scene della proposta e in Esplora si usa una sorgente separata, `nodo8-station`, alla coordinata del sito confermato `FROZEN::L00407`: **9.4044416, 45.7291436**. Nelle scene storiche resta il riferimento storico. Una sola coppia punto/scritta è visibile alla volta, senza duplicazioni. Il punto della stazione resta visibile anche spegnendo le linee ed è cliccabile per aprire le informazioni della proposta. La descrizione accessibile della mappa identifica FS senza introdurre un nuovo badge visivo.

## Sfondo e interazioni

- OSM in Esplora passa da opacità 0,55 e luminosità massima 0,95 a **0,16 e 0,38**. Lo sfondo è molto tenue, con percorsi, fermate e veicoli in primo piano. L'attribuzione resta presente.
- Cambiare pannello da Orario a Mappa non ferma più la riproduzione: livelli e mezzi continuano sul medesimo orologio. Non viene introdotto un altro timer.
- Le aree cliccabili di riduzione del pannello e chiusura delle schede sono 44×44 px. Gli orari delle quattro schede bus passano da 9 a 11 px, conservando cifre tabulari e righe compatte.
- Rimangono tutti i livelli, le funzionalità e i dettagli tecnici raccolti nella sezione dedicata.

## Verifica

96 test Node, 44 test Python e 8 sottotest superati. Test specifici per il glifo nel punto della mappa, assenza di marker FS HTML, unicità e immutabilità della coordinata di stazione, sfondo tenue e continuità dell'orologio al cambio di pannello.

Browser locale: zero `.hub-marker`, coordinata della stazione riprodotta dal sito confermato; FS visivamente centrato nel punto. In riproduzione, il passaggio a Mappa e l'accensione S8/D184/D185 mantengono il tempo in avanzamento; il ritorno a Orario conserva lo stato. Nessun errore o avviso nella console durante la verifica. Anteprima mobile a 320 px senza overflow orizzontale, bersaglio di riduzione 44×44 px; dimensioni temporanee ripristinate al termine.
