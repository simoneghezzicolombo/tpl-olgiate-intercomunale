# Nodo8 — revisione dell’esperienza e quattro bus in Esplora

## Ambito

Revisione della vetrina e dello scrollytelling, senza modificare la proposta
di trasporto, la geometria, i siti, il calendario, il registro orario o le
autorizzazioni. Restano pubblicabili solo la vetrina e Dietro l’analisi;
i prototipi esclusi restano nel repository.

## Esperienza

- La vetrina segue inizialmente un giro completo; la vista dell’intera
  giornata resta disponibile. La scelta di un giro dalla tabella apre la
  simulazione corrispondente. Il cursore raggiunge l’arrivo finale esatto,
  prima del recupero terminale, e la riproduzione si arresta.
- Fermate ricercabili, passaggi ripetuti distinti, navigazione mobile
  completa. Schema delle fermate e otto stilizzato delle località differenti,
  ingrandimento facoltativo, sequenza testuale e download SVG.
- Nel racconto, i comandi dell’orario restano nel flusso del capitolo, senza
  coprirne il testo. Indice dei 13 capitoli e tracciato SVG locale su mobile.
- In Esplora, «Bus in movimento» e «Livelli e confronto» sono pannelli
  separati. Il primo parte in pausa alle 07:35 nella vista giornata, con
  quattro carrier occupati. Consente riproduzione, pausa, scelta dell’ora,
  selezione di un giro e ritorno rapido ai quattro mezzi alle 07:35.
- Spegnere Nodo8, lasciare Esplora o nascondere i comandi interrompe la
  riproduzione. Non vengono mostrati bus della proposta nei capitoli storici.

## Semantica della simulazione

Lo stesso modello puro e lo stesso registro alimentano tutte le viste.
B1–B4 identificano carrier di modello, non mezzi assegnati o flotte per ala.
Ogni corsa segue FS → primo anello → FS intermedia → secondo anello → FS finale.
Posizioni interpolate per distanza sui 1.436 vertici originali, soste nominali
di 30 secondi e attese FS dal registro. La vista giornata include il recupero
terminale documentato, non prosecuzioni passeggeri o corse a vuoto inventate.
Il numero di bus visibili cambia nel corso della giornata.

Non è GPS live né una misura osservata di velocità, traffico o passeggeri.
La continuità passeggeri resta progettata e da autorizzare. In caso di errore
WebGL, il capitolo orario può usare il tracciato SVG dello stesso dataset già
validato, mantenendo esplicito l’errore della mappa. Se il dataset non è valido,
non si costruiscono bus o dati sostitutivi.

## Verifiche locali

30 test Python della vetrina, dello scrollytelling e della pubblicazione;
23 test Node del modello, dell’overlay e della preparazione mappa: tutti verdi.
Il builder conferma corrispondenza con le quattro fonti della proposta.
I 37 asset storici preservati superano il controllo SHA-256.

Controlli browser: quattro marker alle 07:35, avanzamento dell’orologio e
movimento, fermata esatta nel giro 4, spegnimento del livello, uscita con
pausa/rimozione marker, collegamento diretto al capitolo Esplora, arrivo
finale esatto nella vetrina, schema distinto ed esportazione SVG 1200×820,
viewport mobile 390×844 senza overflow orizzontale e player nel flusso,
fallback SVG con caricamento MapLibre deliberatamente bloccato.

Release UI: `20261008d`. L’esito della pubblicazione viene registrato
separatamente dopo il completamento della pipeline Pages.
