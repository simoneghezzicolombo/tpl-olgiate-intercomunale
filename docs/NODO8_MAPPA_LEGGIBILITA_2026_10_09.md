# Nodo8: spazio alla mappa, non ai pannelli

## Correzioni

- Una sola legenda WorldPop / ISTAT / DBGT, alta circa 82 px sul desktop.
  Fonti, quantità e distinzioni del modello conservate nei capitoli.
- Schede ordinarie larghe al massimo 460 px, corpo leggibile a 16 px.
  Niente riquadri dentro riquadri per i due conteggi degli edifici.
- Fondo della scheda edifici: metodo chiuso e avvertenza in circa 85 px,
  compresi margini e padding finale, senza i precedenti separatori distanziati.
- Indicatore della ricerca in cinque fasi compatto, circa 100 px;
  tutti i conteggi e la distinzione fra quantità e geometrie restano consultabili.
- Conclusione senza un secondo riepilogo flottante; azioni allineate,
  footer ridotto. Nessuna verifica o qualificazione cancellata.
- Inquadratura geografica basata sul vero ingombro della colonna di testo.
  Gli oggetti sono centrati nello spazio libero, non sotto una scheda opaca.

## Difetti funzionali corretti

Il controller Esplora scriveva opacità zero anche sui livelli condivisi quando
non era nel capitolo Esplora. Il suo osservatore veniva eseguito dopo quello
del racconto, spegnendo i tracciati KML D184/D185 e i livelli di popolazione.
Ora, fuori da Esplora, pulisce soltanto i propri livelli `explore-*`.

I selettori dei capitoli potevano catturare il `body[data-scene]` nei collegamenti
diretti. Ora sono limitati a `main .chapter[data-scene]`: controlli e animazioni
restano nel capitolo corretto anche entrando direttamente dalla sua URL.

## Evidenza preservata

Geometrie KML ufficiali intatte: 18 varianti, 7 D184 e 11 D185;
2.268 e 3.618 coordinate rispettivamente. Nessun percorso ridisegnato o
ricostruito collegando i punti fermata.

Nodo8 e fonti confermate immutate: 27 siti, 31 eventi per giro, 16 giri,
quattro carrier simulati; nessun cambiamento a copertura, orario, bilancio
chilometrico, autorizzazioni, continuità dei passeggeri o finanziamento.

## Verifiche

- 42 test Python e 8 sottotest.
- 36 test Node, inclusi ownership dei livelli, cornice geografica e deep link.
- Controllo browser di tracciati ufficiali, capitoli, dettagli e simulazione.
- Pubblicazione ancora limitata alle due pagine finali e 71 dipendenze.
  Prototipi e dati non pubblicati restano nel repository.

La registrazione della pubblicazione segue dopo il deploy verificato.
