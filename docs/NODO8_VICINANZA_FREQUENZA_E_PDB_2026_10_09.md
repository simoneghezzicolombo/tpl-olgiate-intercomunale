# Confronto per i residenti: vicinanza, corse e limiti

Entrambe le pagine aprono con le linee esistenti D184/D185 come situazione
attuale e presentano Nodo8 come proposta. In evidenza il passaggio del modello
entro 10 minuti: 68,35% → 81,79%. Il confronto per comune consente soglie
5/8/10 e due direzioni da FS, senza un indice ponderato.

## La soglia di cinque minuti

Totale: 38,9536% → 46,0608%, **+7,1072 punti**. Le diminuzioni nette sono
localizzate a Brivio (-6,3921) e Santa Maria Hoè (-6,3777).

Il diagnostico usa le stesse unità, pesi e grafo RT028 del confronto già
pubblicato; prima riproduce tutte le percentuali confermate. Distingue
perdite e guadagni lordi. Attribuisce ciascuna unità persa al gruppo storico
più vicino, con insiemi disgiunti: **non** è un effetto causale additivo della
cancellazione di ciascuna fermata. Le recuperabilità controfattuali si
sovrappongono e non vanno sommate. Non si inferiscono passeggeri o persone
aggiuntive dai pesi RT016.

Brivio: perdite lorde 6,4193, guadagni 0,0271. Il gruppo EX_036, palina
`L00063` di capolinea, descrive 4,6404 punti di perdita lorda. Non coincide
con il sito scelto di Via Bergamo/Scuola Materna. Beverate paese descrive
1,4570 punti: la località rimane, ma alcune unità superano di poco 5 minuti.

Santa Maria Hoè: perdite lorde 13,6027, guadagni 7,2250. Il gruppo EX_028
`Hoè`, IDs `300873/L00873`, descrive 8,6682 punti; è la località Hoè, non
la fermata di Santa Maria Hoè centro mantenuta nel progetto. EX_032
Alpino/Via Como, `300902/L00902`, descrive altri 3,7958 punti. Tremonte/
Via Leopardi descrive 1,1362 punti, senza implicare esclusione della frazione.
Le coordinate e le identità delle paline dei due versi non sono equivalenti.

Artefatto: `assets/nodo8-coverage-diagnostic.json`, generato da
`python scripts/build_nodo8_coverage_diagnostic.py --check`. Il confronto
originario rimane byte per byte invariato. La classificazione dei gruppi
non sostituisce l'approvazione di accosti o la verifica di un viaggio utile.

## Frequenza affiancata, non moltiplicata

I quadri ufficiali 2026/27 forniscono le partenze da Olgiate FS in un feriale
scolastico lunedì–venerdì: D184 8 verso ovest, D185 5 verso est. Maggiori gap
interni al quadro 377 e 380 minuti. I 16 giri confermati Nodo8 producono 16
ripartenze in ciascuna direzione di anello, massimo gap interno 120 minuti.
Le quattro banche H30 sono sfalsate, non simultanee ovunque o bidirezionali.

Non si attribuiscono questi conteggi a ogni fermata o residente. La copertura
è strutturale su GTFS 2025/26, le corse pubblicate sono 2026/27, la proposta
è 2027 e la simulazione animata D184/D185 è del 6 maggio 2026. Date e ruoli
restano separati. Questo non è una percentuale congiunta di accesso a servizio
frequente, una stima di domanda, una produzione annua o un ranking.

Fonte D184: PDF ufficiale edizione 14 settembre, pagina 1, SHA256
`a6dcee15654b84f2434ce4631ab3f53c7671cea2d87933f50af97b6f044418a1`.
Fonte D185: PDF edizione 5 ottobre, pagina 2, SHA256
`92d53932a2d108092ac6dbfcf760f685f61ad97f79afe032bb6dfb2da76bf4ef`.
Copie verificate in `cache/current_timetable_audit_20261007/`.

## Documento storico sul collegamento interprovinciale

Verificata visualmente la scheda LC-INT-008 a pagina 10 del PDF indicato
dal committente e la tabella di pagina 18. Il precedente riguarda il
capolinea Cisano FS e la prosecuzione per Celana nel bacino di Bergamo.
Non prova proprietà locale dei chilometri, trasferimenti di fondi automatici
o l'eliminazione del tratto Brivio–Cisano. La retorica di esclusiva destinazione
dei benefici non è un dato di domanda osservata.

PDF: `cache/PdB_COLCVA_Allegato2_SchedeInterventoLecco_20180608.pdf`, SHA256
`1184a6f4d661027cb23f83cac69f630c34ee92292755696ebcffd4bead859ba6`.
URL/pagina e delimitazioni sono in `assets/nodo8-service-comparison.json`.

Nessun cambio di percorso, fermata, orario, calendario, budget o autorità
decisionale. PRIMARY e RUNNER-UP rimangono non autorizzati.
