# Linea 8 — un solo orario di progetto sulla geometria confermata

**Geometria confermata dal committente. Orario proposto per chiudere la progettazione temporale, non ancora approvato per l’esercizio.**

## La proposta

- Stessi due percorsi completi e stessi 28 siti. Nessuna nuova variante o esclusione territoriale.
- **H30 nelle punte 07–09 e 16:55–18:55**, verificato nei due sensi di viaggio di ciascun sito attraverso i nove scenari di marcia/sosta.
- **H120 solo 10–16; H60 nel resto fuori punta.** Sono massimi di attesa del passeggero pronto a partire, non una promessa di collegamento con ogni treno.
- Prime partenze FS **06:30 ovest / 06:35 est**; ultime **19:40 entrambe**. Le ultime corse arrivano ai siti e rientrano a FS dopo tale ora.
- **17 corse per ala, 34 totali; 122.339,721 km/anno su 260 giorni ipotizzati**. Restano +10.920,721 km (+9,80%) sul riferimento, prima di deposito e altri extra. Nessun aumento approvato.
- Quattro mezzi nel caso nominale con recuperi, fino a sei negli stress. Flotta e turni da validare con l’operatore.

## Partenze da Olgiate FS

La tabella affianca gli elenchi delle due ali: **una riga non indica lo stesso autobus né una coincidenza fra ali**. Nessuna permanenza a bordo attraverso FS è garantita da questa tabella.

| Corsa nell’ala | Ovest: Olgiate sud, La Valletta, Santa Maria | Est: San Zeno, Calco, Arlate, Brivio |
|---|---:|---:|
| 1 | 06:30 | 06:35 |
| 2 | 07:00 | 07:05 |
| 3 | 07:30 | 07:35 |
| 4 | 08:00 | 08:05 |
| 5 | 08:30 | 08:35 |
| 6 | 09:00 | 09:05 |
| 7 | 10:00 | 10:05 |
| 8 | 11:35 | 12:05 |
| 9 | 13:35 | 13:35 |
| 10 | 15:35 | 15:35 |
| 11 | 16:35 | 16:35 |
| 12 | 17:05 | 17:05 |
| 13 | 17:35 | 17:35 |
| 14 | 18:05 | 18:05 |
| 15 | 18:35 | 18:35 |
| 16 | 19:05 | 19:05 |
| 17 | 19:40 | 19:40 |

### Regola da ricordare

Al mattino ovest ai minuti **:00/:30**, est **:05/:35**. Dalle 10 entrambe usano **:05/:35**, con una sola eccezione ordinaria: **ovest 10:00**; ultime partenze **19:40** esplicitamente fuori schema. Nelle ore centrali non sono serviti tutti gli slot: valgono le partenze della tabella, non una frequenza semioraria continua.

Questa è la minima quantità di eccezioni nel dominio verificato, a stessi km, percorsi e finestre di punta. Non si pagano i 3.682 km aggiuntivi della precedente variante senza eccezioni ordinarie, né si anticipano le punte per far tornare i conti.

## Coincidenze: verifica datata, non soltanto il vecchio calendario

È stato riscaricato il [GTFS ufficiale Regione Lombardia/Trenord](https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip) il 27 settembre 2026. I **74 eventi S8** a Olgiate attivi il **28 settembre** hanno gli stessi minuti del vecchio giorno di confronto; la verifica dei cinque feriali fino al **2 ottobre** conferma lo stesso quadro. Gli identificativi di corsa sono quelli attivi nel nuovo periodo, non quelli scaduti il 14 settembre. Il fatto che lo ZIP abbia lo stesso hash non lo rende scaduto: contiene più periodi di servizio.

Confermati tutti i **297 controlli per sito** sugli obiettivi ereditati: cinque treni verso Milano, **07:26, 07:56, 08:26, 08:56, 09:26**, e sei arrivi da Milano/direzione Lecco, **16:32, 17:02, 17:32, 18:02, 18:32, 19:32**. Il treno 06:56 non fa parte di questi cinque obiettivi: non va promesso implicitamente.

I margini restano ipotesi ingegneristiche: tre minuti di trasferimento; per gli arrivi ferroviari di punta partenza bus tra tre e otto minuti dopo. Non sono garanzie rispetto ai ritardi reali. La verifica annuale, festiva e del sabato rimane distinta dai cinque feriali controllati.

### Corse centrali e serali: cosa offre ciascuna

La tabella mostra l’ultimo arrivo da Milano compatibile con almeno tre minuti di trasferimento e il primo treno verso Milano raggiungibile dopo il ritorno dell’ala in **tutti** gli scenari modellati. Non somma corse diverse per inventare un viaggio. In direzione Lecco il registro macchina contiene lo stesso controllo.

| Ala / partenza FS | Arrivo treno da Milano utilizzabile | Attesa treno→bus, min inclusi 3 di trasferimento | Rientro FS nominale | Treno verso Milano dopo il giro |
|---|---:|---:|---:|---:|
| Ovest 10:00 | 09:32 | 28 | 10:41 | 10:56 |
| Est 10:05 | 10:02 | 3 | 10:45 | 10:56 |
| Ovest 11:35 | 11:32 | 3 | 12:16 | 12:56 |
| Est 12:05 | 12:02 | 3 | 12:45 | 12:56 |
| Est 13:35 | 13:32 | 3 | 14:15 | 14:26 |
| Ovest 13:35 | 13:32 | 3 | 14:16 | 14:56 |
| Est 15:35 | 15:32 | 3 | 16:15 | 16:26 |
| Ovest 15:35 | 15:32 | 3 | 16:16 | 16:56 |
| Est 16:35 | 16:32 | 3 | 17:15 | 17:26 |
| Ovest 16:35 | 16:32 | 3 | 17:16 | 17:56 |
| Est 17:05 | 17:02 | 3 | 17:45 | 17:56 |
| Ovest 17:05 | 17:02 | 3 | 17:46 | 18:26 |
| Est 17:35 | 17:32 | 3 | 18:15 | 18:26 |
| Ovest 17:35 | 17:32 | 3 | 18:16 | 18:56 |
| Est 18:05 | 18:02 | 3 | 18:45 | 18:56 |
| Ovest 18:05 | 18:02 | 3 | 18:46 | 19:26 |
| Est 18:35 | 18:32 | 3 | 19:15 | 19:26 |
| Ovest 18:35 | 18:32 | 3 | 19:16 | 19:56 |
| Est 19:05 | 19:02 | 3 | 19:45 | 19:56 |
| Ovest 19:05 | 19:02 | 3 | 19:46 | 20:26 |
| Est 19:40 | 19:32 | 8 | 20:20 | 20:56 |
| Ovest 19:40 | 19:32 | 8 | 20:21 | 20:56 |

## Cosa viene chiuso e cosa no

**Chiuso come base progettuale:** geometria attuale, nessuna ricerca generale di nuovi tracciati; un solo orario proposto, 34 corse con contabilità completa, punte non anticipate e regolarità con eccezioni dichiarate.

**Da accettare esplicitamente:** compromesso H120 10–16 e servizio da 122.340 km. La conferma della geometria non approva automaticamente questi due aspetti. Non dichiariamo che tutti i viaggi centrali siano poco importanti o che il tetto 111.419 sia rispettato.

**Prima dell’esercizio:** orari osservati/turni/flotta, paline e sei manovre, interscambio fisico, calendario reale, deposito e aggiornamenti ferroviari oltre le date controllate. Questi controlli possono richiedere aggiustamenti locali, non riaprono automaticamente tutta la geometria. I viaggi lunghi già riportati rimangono un limite noto della geometria accettata.

[Geometria confermata](../config/rt031_geometry_confirmation_and_timetable_closure_v3.json) · [Tracciato invariato](../outputs/phase2/rt031_line8_local_shortcuts_v3/deep_offpeak_witness.png) · [Orario, eventi e blocchi macchina](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_geometry_timetable.json) · [Registro delle coincidenze](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_geometry_rail_connections.json)
