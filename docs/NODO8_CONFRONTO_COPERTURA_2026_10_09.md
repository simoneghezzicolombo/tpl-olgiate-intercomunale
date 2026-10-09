# Confronto spaziale Nodo8 / riferimento D184-D185

Il confronto usa lo stesso grafo pedonale RT028, le stesse unità e pesi RT016,
gli stessi raccordi, velocità di 80 m/min e soglie 5/8/10 minuti.
Non sottrae il vecchio 68,73% V4 o il 77,56% della ricerca storica.

Prima di confrontare, il calcolo riproduce tutte le 18 percentuali della
proposta confermata, totale e cinque comuni, con tolleranza numerica 1e-7.
Le quattro fonti della proposta, geometria, calendario e autorizzazioni
restano invariate. Nessun vincitore, domanda o garanzia di servizio è inferito.

## Entro 10 minuti

| Ambito | Riferimento D184/D185 | Nodo8 | Differenza in punti percentuali |
| --- | ---: | ---: | ---: |
| Totale | 68,35% | 81,79% | +13,44 |
| Olgiate Molgora | 56,95% | 84,56% | +27,61 |
| Calco | 56,79% | 79,27% | +22,48 |
| Brivio | 89,99% | 90,18% | +0,19 |
| Santa Maria Hoè | 90,17% | 93,43% | +3,26 |
| La Valletta Brianza | 67,28% | 67,85% | +0,56 |

A 5 minuti Brivio perde 6,39 punti e Santa Maria Hoè 6,38 punti.
L'interfaccia conserva anche questi risultati negativi.

## Fonte e limiti

Il riferimento ha 44 cluster fisici e 70 identità del GTFS ufficiale strutturale
2025/26; non prova l'attivazione contemporanea di ogni fermata oggi.
La deviazione temporanea del Ponte di Brivio resta esclusa, come nella baseline V4.

Dodici coordinate esterne non si agganciano al grafo congelato. Non viene
inventato un raccordo: un limite geometrico inferiore, verificato su ogni arco
del grafo, prova che sono oltre 800 m da ogni unità core e non possono cambiare
queste soglie nel modello. Una fermata irrisolta più vicina blocca il calcolo.

I pesi RT016 sommano 45.828, come nel relativo summary congelato. Sono pesi del
substrato, non un nuovo conteggio dei residenti né passeggeri. Qui si confrontano
quote con identici denominatori; non si inferisce un numero di persone aggiuntive.

Non sono certificati accessibilità o sicurezza dei percorsi, nuove fermate,
frequenze, coincidenze o un miglioramento complessivo del servizio.

Artefatto: `assets/nodo8-coverage-comparison.json`.
Riproduzione: `python scripts/build_nodo8_coverage_comparison.py --check`.
Richiede lo snapshot originale in `cache/rt028-certified-34039162932`.

## Pubblicazione verificata

- Sorgente: `0ed84d723b721c896f9dff492a8534ecaf1a8919`.
- Pages: `5a24562e1a3b8bfcd68046077991bf6a471f86b8`.
- Workflow `37912527136`, concluso con successo.
- 43 test Python e 8 sottotest; 41 test Node.
- Hash HTTP dei 73 file pubblicati verificati; soltanto due pagine HTML.
- Browser: due barre per ogni comune, selector 5/8/10 minuti, cali a 5 minuti
  conservati e nessun overflow a 390 px. Nessun errore console.
- Fonte confermata Nodo8 intatta; nessun prototipo cancellato.
- Prova visiva: `cache/nodo8-website-preview/nodo8-coverage-comparison-published-20261008p.png`.

https://simoneghezzicolombo.github.io/tpl-olgiate-intercomunale/?v=20261008p#impatto
