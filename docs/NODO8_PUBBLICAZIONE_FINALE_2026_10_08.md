# Pubblicazione finale Nodo8 — 8 ottobre 2026

La pubblicazione contiene due sole pagine HTML, appartenenti allo stesso sito:
`index.html` (vetrina Nodo8) e `dietro-l-analisi/index.html` (scrollytelling).
Sono inclusi solo i 60 file di dipendenza esplicitamente elencati in
`config/nodo8_publication_allowlist.json`, oltre al manifest generato.

Non è più pubblicato l’intero ramo del repository. GitHub Pages usa un workflow
che costruisce e distribuisce un artifact selettivo. Fonti e prototipi esclusi
restano in Git, anche nel ramo `gh-pages`: non vengono cancellati.
La vecchia mappa `outputs/maps/mappa_interattiva_rete_tpl_olgiate.html` rimane
nel repository ma non compare nel pacchetto e il suo vecchio URL non deve essere
raggiungibile come pagina pubblicata.

Il workflow `nodo8-final-pages.yml` parte dal ramo `gh-pages`, già ammesso
dall’ambiente `github-pages`. Non si ampliano le regole di accesso dell’ambiente.
Non si effettuano push forzati, eliminazioni di rami o modifiche a `main`.
Il sito mantiene URL e HTTPS esistenti.

Il commit di pubblicazione è preparato da
`scripts/prepare_nodo8_pages_commit.py`: confronta gli alberi Git e richiede
che tutti i percorsi non selezionati conservino gli stessi blob.
Il builder rifiuta directory di output non vuote, percorsi non sicuri,
file mancanti, dipendenze HTML mancanti o qualsiasi terza pagina HTML.

Controlli:

```powershell
python -m unittest discover -s tests -p test_nodo8_publication.py -v
node --test tests/test_nodo8_journey.mjs
python scripts/build_nodo8_publication.py --output cache/nodo8-final-pages-preview
```

La configurazione segue il [workflow personalizzato di GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
Il manifest pubblico elenca i file effettivamente distribuiti e la revisione
del workflow. La pubblicazione non cambia percorso, fermate, orario, calendario,
autorità di selezione o stato di autorizzazione del servizio.

## Riscontro della pubblicazione

Deploy [37746851146](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/37746851146)
riuscito, revisione `c5cd3da2f4416d7c4fa22a87c51e0210dcf8b66c`.
Vetrina, scrollytelling e manifest pubblico rispondono 200.
La vecchia mappa e il vecchio `geo-data.js` alla radice rispondono 404.
La mappa ritirata è ancora nel ramo `gh-pages`, con lo stesso blob Git.
Verificati anche nel browser 27 siti, 16 giri e 13 capitoli con Nodo8 caricata.
Il [riscontro macchina](../config/nodo8_pages_publication_result_20261008.json)
registra controlli, revisioni e assenza di eliminazioni.
