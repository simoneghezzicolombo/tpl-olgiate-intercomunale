# Nodo8: leggibilità a colpo d’occhio

Revisione di presentazione `20261008j`, 8 ottobre 2026.

## Richiesta e confine

Semplificare significa rendere immediati contenuti e strumenti, non eliminare
parti della proposta o della ricerca. Nessuna modifica al percorso, alle fermate
previste, agli orari, al calendario, alle assegnazioni dei bus o alle autorità.

## Cosa cambia

- Pagina principale: titoli formulati come domande o azioni, icone per percorso,
  frequenza e fermate; distinzione tra titolo e spiegazione dell’orario.
- Schemi: vista concettuale dei luoghi come ingresso; schema completo sempre
  disponibile nella seconda scheda, con elenco ordinato, zoom e download SVG.
- San Zeno e Olgiate sud: un solo punto grafico centrato per ogni sito.
  I numeri `1·14` e `15·28` conservano i due eventi distinti; scegliere il punto
  apre una tabella con entrambi i passaggi, per tutte le 16 corse.
- Racconto: conservati i 12 capitoli scritti e il tredicesimo capitolo Esplora
  generato dal programma. Le fasi del metodo diventano sequenze visive; numeri,
  fonti e limiti restano consultabili, compresi residui della popolazione,
  tutti i filtri di ricerca e le quattro ipotesi FIG/TWO storiche.
- Pannelli sulla mappa: caratteri leggibili e italiano corrente. Nessun termine
  come seed/thinning nella descrizione delle fasi di ricerca.
- Esplora: conservati i quattro bus e tutti i dieci livelli. Controlli organizzati
  per abitanti, accesso alle fermate e reti. I readout duplicati non coprono il
  testo sui telefoni; gli stessi dati restano nel capitolo e negli approfondimenti.

## Distinzioni conservate

26 siti nonhub nel disegno completo + Olgiate FS = 27 siti distinti.
28 eventi nonhub nel registro + tre ruoli FS = 31 eventi per corsa.
L’accorpamento grafico non accorpa tempi, direzioni, eventi passeggeri o garanzie.

La simulazione non è GPS. I quattro carrier non sono una flotta acquisita.
La continuità fisica del mezzo non autorizza la permanenza dei passeggeri.
Le punte sono sfalsate lungo la stessa linea; non sono H30 simultaneo ovunque
o nei due versi. La copertura è potenziale, non domanda, incremento certificato
o numero di passeggeri. Costi, finanziamento e autorizzazioni restano da verificare.

## Verifiche

- 41 test Python e 8 sottotest; 31 test Node.
- Proiezione JSON invariata e conforme a tutte le quattro fonti confermate.
- Due fermate condivise interattive; tabella San Zeno con 16 righe e due colonne
  di passaggio verificate nel browser.
- Esplora: quattro carrier, dieci livelli, selezione giornata e ora 07:35 verificati.
- Controllo responsive a 390 px, senza overflow della pagina; lo schema completo
  può scorrere all’interno del proprio contenitore.
- Pubblicazione limitata alle due pagine finali e alle 71 dipendenze autorizzate.
  Prototipi e dati storici restano nel repository.

La conferma del deploy e della verifica pubblica sarà riportata dopo l’esecuzione.
