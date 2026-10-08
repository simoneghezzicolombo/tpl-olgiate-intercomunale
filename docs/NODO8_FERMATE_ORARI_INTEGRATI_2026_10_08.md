# Nodo8 — fermate, orario e racconto collegati

Release UI `20261008e`. Estensione della revisione precedente, non modifica
della proposta di trasporto o del registro nominale.

## Cosa cambia

- «Quando passa qui?» mostra tutti i 16 giri per ciascuno dei 27 siti,
  copiando arrivo e ripartenza dal registro già validato. I due eventi di
  San Zeno e Olgiate sud restano colonne distinte. A FS sono separati
  partenza, arrivo intermedio con ripartenza e arrivo finale.
- Ogni ora apre la simulazione del giro e dell’evento corrispondenti,
  senza arrotondare l’istante usato dal player. La mappa torna alla vista
  completa e chiude il popup, così il mezzo non resta fuori campo.
- I numeri dell’elenco sono gli ordinali dei passaggi, coerenti con lo
  schema delle fermate. FS ha un’etichetta dedicata; i siti ripetuti
  mostrano entrambi gli ordinali, non due identità inventate.
- Link diretto condivisibile per ogni sito. I parametri vengono accettati
  solo se l’identità appartiene alla linea validata; un ID non presente
  mostra un avviso e non genera una tabella o una fermata sostitutiva.
- Il player del giro mostra cinque fasi: partenza FS, primo anello,
  sosta FS, secondo anello, arrivo FS. I passaggi sono determinati dagli
  eventi del giro; il recupero terminale non è una prosecuzione passeggeri.
- In Esplora si può scegliere una fermata da un menu accessibile da
  tastiera. Il popup rimanda direttamente allo stesso sito nella vetrina.
- I comandi di D184/D185 e delle alternative precedenti restano dentro
  i rispettivi capitoli, senza pannelli fissi sul testo. Le alternative
  sono esplicitamente storiche, non «linee finali». L’etichetta KML/GTFS
  viene aggiornata solo dopo il caricamento e la validazione del KML.
- L’ingresso in Esplora gestisce il caso di un collegamento diretto
  appena impaginato: il bottone visibile non ignora il primo clic quando
  il direttore dello scroll non ha ancora aggiornato la scena.

## Limiti invariati

Orari nominali al secondo circa, non un orario pubblico autorizzato.
Base feriale 2027 prima di eccezioni locali; sabato distinto. Nessuna
garanzia aggiunta di coincidenza ferroviaria, traffico, accessibilità,
transitabilità, passeggeri o finanziamento. B1–B4 rimangono carrier di
modello. Geometria, dati della proposta e flag di autorizzazione invariati.

## Verifiche

32 test Python e 26 test Node mirati. Riproducibilità delle quattro fonti,
hash degli asset storici, corrispondenza di tutte le celle con gli eventi
del registro, fasi di tutti i giri, validazione dei link e confine della
pubblicazione a due sole pagine.

Controlli browser locali: 16 righe e due colonne-evento a San Zeno;
secondo evento del giro 4 → B4 fermo all’evento 14; tre ruoli a FS;
viewport 390×844 senza overflow orizzontale della pagina, tabella FS
scorribile; ID non valido senza tabella sostitutiva; quattro bus ancora
presenti in Esplora; pannelli storici nel flusso e fonte KML/GTFS corretta;
selettore della fermata e relativo collegamento alla vetrina.

L’esito pubblico della pipeline viene registrato dopo il deploy.
