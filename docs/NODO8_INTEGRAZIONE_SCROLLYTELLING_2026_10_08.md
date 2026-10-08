# Nodo8 e Dietro l’analisi — integrazione dell’8 ottobre 2026

Due pagine collegate, con funzioni distinte:

- `index.html`: vetrina della proposta Nodo8, con percorso reale, 27 siti, 16 giri, copertura per comune e compromessi.
- `dietro-l-analisi/index.html`: lo scrollytelling originale di Tra Paesi, conservato e prolungato fino a Nodo8.

Il percorso dell’analisi conserva griglia WorldPop, sezioni ISTAT, edifici, cammino,
grafo, KML/GTFS e ricerca precedente. Le quattro alternative FIG/TWO sono
esplicitamente storiche. Seguono i nuovi capitoli Nodo8, orario e limiti.
Nella mappa esplorabile Nodo8 è accesa all’ingresso; le alternative precedenti
sono un controllo separato, inizialmente spento.

## Fonti e separazione dei dati

Lo scrollytelling proviene da `origin/gh-pages`, commit
`104e8f2f0a801cffb15698aa06a8c2bd98c0dc6e`. Non era presente nel checkout del
ramo decisionale. Sono stati importati runtime e asset originali; il file
`geo-data.js` è conservato come `dietro-l-analisi/legacy-geo-data.js`.
`upstream-import.json` registra 37 asset territoriali/librerie: i loro byte sono
stati confrontati con l’archivio di quel commit, non soltanto con il nuovo checkout.

Nodo8 usa invece `assets/nodo8-proposal.json`, prodotto dallo script
`scripts/build_nodo8_website_data.py` dalle tre fonti confermate, con hash.
Questi tre digest normalizzano soltanto CRLF→LF, con semantica dichiarata
nell’asset: coincidono con i byte delle fonti tracciate in Git e non dipendono
dalla conversione degli a capo del checkout Windows. Non sono nuovi hash
di certificazione upstream. I 37 asset storici importati mantengono invece
i byte originali, senza normalizzazione.
Il nuovo modulo `journey-nodo8.mjs` aggiunge sorgenti MapLibre proprie,
`nodo8-routes` e `nodo8-sites`: non sovrascrive gli asset o i percorsi storici.
Le due geometrie sono ali della stessa linea; i siti con più eventi conservano
le occorrenze distinte anche nelle schede.

Le vecchie animazioni orarie non vengono usate per rappresentare Nodo8.
Le percentuali storiche e la copertura RT028 di Nodo8 non formano un confronto
omogeneo: nessun guadagno, domanda o probabilità empirica viene inventato.
Percorso, orario, calendario e autorità del progetto non vengono modificati.

## Verifica e avvio locale

```powershell
python scripts/build_nodo8_website_data.py --check
python -m pytest tests/test_nodo8_website.py tests/test_nodo8_scrollytelling.py -q
node --test tests/test_nodo8_journey.mjs
python -m http.server 63442 --bind 127.0.0.1
```

- Vetrina: http://127.0.0.1:63442/
- Racconto: http://127.0.0.1:63442/dietro-l-analisi/
- Capitolo Nodo8: http://127.0.0.1:63442/dietro-l-analisi/#nodo8

I test controllano collegamenti/asset locali, byte storici preservati,
geometrie identiche alle fonti, 27 siti/quattro nuovi/28 eventi, autorità false
e calendario; non sono prove di esercizio del servizio.

Esito: 20 test Python e quattro JavaScript passati. Verificati nel browser
caricamento dei 13 capitoli, navigazione tra pagine, attivazione di Nodo8,
toggle percorso/siti, ritorno dalla modalità mappa e layout mobile senza
overflow orizzontale. La mancanza del JSON della proposta e del runtime WebGL
è stata simulata: messaggi espliciti, senza sostituire Nodo8 con vecchie alternative.
I controlli di navigazione sono utilizzabili anche da tastiera; le aree dei
punti-capitolo sono state aumentate senza cambiare la geometria.

Questa è un’integrazione locale, non un aggiornamento già pubblicato su GitHub
Pages. Non viene effettuato un push sul ramo di pubblicazione né inviata una
proposta esterna. La versione pubblica va aggiornata con un passaggio di
pubblicazione esplicito dopo la verifica della vetrina.
