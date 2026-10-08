# Nodo8 — redesign completo della vetrina e del racconto

Release di presentazione: `20261008f`. Non modifica la proposta di trasporto.

## Cambiamenti consegnati

- Vetrina ricostruita con un unico sistema visivo avorio/verde/terracotta, nuova gerarchia editoriale, percorso geografico reale in apertura e navigazione coordinata con il racconto.
- Mappa con vista ampliabile, ricerca dei siti, orari per singolo evento e collegamenti diretti tra le due pagine. Il ridimensionamento conserva la vista scelta.
- Nuova esplorazione di una relazione nello stesso giro: due eventi ordinati, durata nominale, sosta intermedia a FS esplicita e pulsanti che mostrano partenza/arrivo sul tracciato. Non è un pianificatore di viaggi garantiti o una ricerca del viaggio ottimo.
- Player comune alle due pagine: giro completo oppure quattro mezzi B1–B4; schede selezionabili, avanzamento del giro, fermate/sosta FS, controlli e metodo in sezioni espandibili. Nessuna separazione in due linee.
- Schemi metropolitana e località coordinati, sequenza consultabile ed esportazione SVG conservata.
- Racconto riorganizzato in tre atti: territorio, alternative, proposta. Ricerca storica e proposta attuale rimangono semanticamente distinte.
- Layout responsive, etichette esplicite dei selettori, navigazione tastiera, preferenza di movimento ridotto e sospensione delle animazioni decorative quando la pagina è nascosta.

## Evidenza immutabile

`assets/nodo8-proposal.json` e i quattro upstream certificati non sono stati modificati. Restano 27 siti, 28 eventi fuori FS, tre ruoli FS per giro, 16 giri completi, quattro identificativi di mezzo nominale e 110.229,936 km commerciali feriali nella base 2027.

La continuità fisica del mezzo non certifica la permanenza passeggeri. Copertura pedonale potenziale non significa domanda o miglioramento certificato rispetto alle linee attuali. Nessuna autorizzazione, budget decisorio, incertezza, probabilità di mancata coincidenza o metrica di domanda viene aggiunta.

## Verifica locale

- 39 test Python e 27 test Node passati; sei subtest Python aggiuntivi.
- Builder della proiezione: corrispondenza con tutte e quattro le fonti confermate.
- Verifiche nel browser a 1280 px e 390 px: relazione nominale attraverso FS, fermate ripetute, mappa ampliabile/ESC, quattro bus alle 07:35, selezione B3 e popup Calco Centro con link alla vetrina. Nessun overflow orizzontale osservato nei layout verificati.
- Caricamento del JSON bloccato deliberatamente: orologio non inventato (`—:—`), nessuna anteprima o viaggio sostitutivo, selettori disabilitati. Blocco e dimensioni di test rimossi.
- Pubblicazione limitata alle due pagine finali e 70 dipendenze esplicite. Le pagine ritirate sono conservate in Git e non entrano nell’artefatto Pages.

## Verifica pubblica completata

- Sorgente del redesign: `6d2467f30eaef63d424e511ed1489d73e6ba85de`.
- Revisione Pages: `cfc946ea31b943e7ca8cdf8281cfa42af4a9fc0a`.
- Pipeline [37790663062](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/37790663062): build e deploy completati con successo.
- Manifest pubblico della nuova revisione: esattamente due HTML; tutti i 70 file HTTP confrontati con i rispettivi SHA-256, nessuna divergenza.
- Vecchia mappa `outputs/maps/mappa_interattiva_rete_tpl_olgiate.html`: HTTP 404; sorgente conservata nel commit Pages. Nessun file del repository eliminato.
- Browser pubblico: nuova vetrina con anteprima del tracciato reale e relazione FS→Calco Centro; Esplora del racconto con B1–B4 alle 07:35 e quattro comandi per seguire i rispettivi giri. Nessun errore console osservato nel racconto.
- Anteprime locali salvate nella cache: `nodo8-redesign-published-20261008f.png` e `nodo8-story-buses-published-20261008f.png`.
