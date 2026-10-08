# Nodo8 — esperienza pubblica unificata

La vetrina e lo scrollytelling sono le due pagine dello stesso sito finale. Il nome, i collegamenti, il modello orario e l’identità della linea sono condivisi. Non cambiano proposta, geometria, orario, calendario o autorizzazioni.

## Una linea, non due servizi

Il tracciato ha un solo colore per l’intero otto. I filtri est/ovest sono rimossi dalla vetrina; le partenze sono descritte come inizio del giro e prosecuzione dalla stessa FS. Le chiavi tecniche `east_A`/`west_B` rimangono nelle fonti senza diventare identità di linee pubbliche.

## Ricostruzione dei bus

`scripts/build_nodo8_website_data.py` copia il registro nominale degli eventi dal design handoff e i blocchi nominali dall’accounting dei mezzi, entrambi del 1 ottobre. Le quattro fonti sono fissate per hash nell’asset. `nodo8-line.mjs` verifica la continuità della geometria completa, l’identità e l’ordine degli eventi, le coordinate dei vertici, gli orari e l’assegnazione non sovrapposta di tutti i 16 giri.

- Un mezzo di modello mantiene il proprio ID per il giro completo, anche attraverso FS intermedia. B1–B4 non rappresentano flotte per ala né disponibilità certificata.
- Arrivi e ripartenze provengono dal registro: 448 soste fuori FS da 30 secondi nominali; sosta intermedia variabile a FS; recupero terminale nominale di 10 minuti, distinto dalla prosecuzione del servizio passeggeri.
- Tra due eventi temporizzati il veicolo percorre tutti i vertici stradali in ordine, con interpolazione proporzionale alla distanza. Non è una misura della velocità entro il singolo tratto, del traffico, del GPS o della domanda.
- Tra i giri e dopo il recupero non viene inventata una posizione o una corsa a vuoto. Il lettore può riprodurre, fermare, cambiare velocità, spostare il tempo e seguire un giro completo.
- La riproduzione parte in pausa, si interrompe quando la pagina non è visibile e non sostituisce le alternative storiche dello scrollytelling.

## Due schemi, stesso ordine

Lo schema metropolitano contiene 28 eventi fuori FS e i tre ruoli della stazione; rappresenta 27 siti distinti, non 31 fermate fisiche. San Zeno e Olgiate sud compaiono due volte perché hanno due eventi, esplicitamente distinguibili. I quattro nuovi siti sono evidenziati; selezionare un evento apre lo stesso sito sulla mappa, conservando nel dettaglio i suoi eventi separati.

Lo schema sintetico raggruppa solo eventi adiacenti per località/corridoio: 21 gruppi, senza aggiungere località non documentate. Non promette la copertura di ogni frazione o un passaggio dentro ogni centro storico. Entrambi sono non geografici, hanno frecce nell’ordine di servizio e possono essere scaricati in SVG con gli stili inclusi.

## Verifica e pubblicazione

Comandi mirati: `node --test tests/test_nodo8_journey.mjs tests/test_nodo8_playback.mjs`; `python -m pytest tests/test_nodo8_website.py tests/test_nodo8_scrollytelling.py tests/test_nodo8_publication.py -q`; `python scripts/build_nodo8_website_data.py --check`.

Verificati nel browser: sosta esatta, prosecuzione a FS, riproduzione/pausa, selezione di Calco dal diagramma tramite tastiera, export SVG, layout a 390 px senza overflow, geometria e bus senza Leaflet/CDN, fallimento chiuso senza JSON. Le librerie e i 37 asset storici conservati mantengono i digest originali.

La pubblicazione rimane un’allowlist di esattamente due pagine HTML e 63 dipendenze. I prototipi esclusi rimangono in Git; nessun altro sito viene ripubblicato. Nessuna selezione, autorizzazione d’esercizio o approvazione delle fermate viene introdotta da queste modifiche.
