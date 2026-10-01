# Linea 8 — continuità fra le ali e viaggi intercomunali

**Chiarimento successivo: il committente richiede lo stesso percorso completo per tutte le corse, senza corse limitate a FS.** L’audit qui sotto resta diagnostica del precedente schema a corse d’ala, non la soluzione richiesta. Il requisito di alternare ogni riuso fisico del mezzo non equivale a definire tutte le corse commerciali sull’otto completo. [Ricostruzione nel contratto corretto](RT031_LINEA8_PERCORSO_UNICO_COMPLETO_V3.md).

**Scelte registrate:** sì alla nuova fermata nell’area di Arlate (N1212) come scelta di progetto; no a N0655 in Via Indipendenza a Olgiate, segnalata dal committente sul cavalcavia. Non viene spostata automaticamente prima o dopo. Olgiate sud e San Zeno già presenti restano inclusi. La verifica delle manovre è rimandata, non cancellata.

La base del confronto storico comprende **29 siti di progetto**, non 29 paline autorizzate: i 28 precedenti più Arlate. **31 giri d’ala e 111.460,883 km di servizio/anno su 260 giorni ipotizzati**, senza nuove deviazioni. L’aggiunta mantiene nei test H30 nelle punte, limiti centrali e 308 controlli ferroviari per sito. Il residuo ferroviario minimo rimane circa 50 secondi oltre i tre minuti ipotizzati per il cambio.

Il sito **29** è Arlate — Via Nuova Provinciale: coordinate indicative del nodo stradale **45.727365, 9.442071**, non il progetto di una palina. Il registro completo aggiornato e gli eventi ricalcolati delle 31 corse sono nel file macchina collegato in fondo.

Copertura potenziale a piedi entro dieci minuti, con **solo** la nuova Arlate:

| Comune | Base precedente | Progetto con Arlate |
|---|---:|---:|
| Brivio | 89.09% | 90.18% |
| Calco | 68.21% | 75.75% |
| Olgiate Molgora | 84.56% | 84.56% |
| Santa Maria Hoe | 95.75% | 95.75% |
| La Valletta Brianza | 67.85% | 67.85% |

Sono percentuali di accessibilità spaziale potenziale, non previsioni di passeggeri. Il beneficio della proposta esclusa a Olgiate non viene più conteggiato.

## Una linea unica non è soltanto il nome

L’intento del committente è **una Linea 8 riconoscibile anche per gli spostamenti tra paesi**. Il modello precedente aveva due elenchi di partenze indipendenti da FS. Ora ogni prosecuzione studiata indica autobus, corsa successiva, identità di servizio e permesso **proposto** di rimanere a bordo. Un semplice riuso dello stesso mezzo non viene contato come viaggio diretto.

Le prosecuzioni sono **testimoni ingegneristici, non ancora un orario pubblico adottato**. Il passeggero deve poter effettivamente restare a bordo durante la sosta e il collegamento stradale a FS; né questo, né accessi, manovre o restrizioni complete sono già certificati.

## Risultato sullo stesso orario, senza nuovi km

| Condizione | Mezzi nominali | Mezzi nel caso più severo | Significato |
|---|---:|---:|---|
| Due ali con riuso libero del mezzo | 4 | 6 | Nessuna continuità passeggeri implicita |
| Ogni concatenamento del mezzo deve alternare ala | 5 | 7 | Alternanza sistematica; le soste possono comunque essere lunghe |

La seconda riga è un confronto, **non l’approvazione di un quinto o settimo autobus**. Ogni mezzo può iniziare e terminare il servizio: nemmeno l’alternanza sistematica promette una prosecuzione dopo l’ultima corsa di ciascun blocco. I 27 minimi per scenario non sono un unico piano operativo valido in ogni scenario.

### Quattro mezzi: quante prosecuzioni, con quale sosta a FS?

La tabella è la frontiera esatta del dominio a partenze fissate. Non usa pesi tra passeggeri o comuni né una soglia arbitraria di attesa accettabile. Il numero conta concatenamenti fra corse, **non percentuale di passeggeri serviti**.

| Prosecuzioni fra ali al giorno | Peggiore sosta a bordo a FS, nominale |
|---|---:|
| 0 | 0.00 min |
| 10 | 19.84 min |
| 18 | 23.61 min |
| 20 | 24.84 min |
| 22 | 53.61 min |
| 24 | 108.61 min |
| 26 | 199.84 min |

**Esempio concreto a 20 prosecuzioni:** quattro blocchi mezzo, soste a FS da 14.84 a 24.84 minuti. Gli altri 11 giri d’ala **non** hanno una prosecuzione diretta verso l’altra ala in questo esempio. Le sette concatenazioni sullo stesso lato sono movimenti/riusi del mezzo, non viaggi intercomunali garantiti.

La soglia di circa 25 minuti è un **risultato di questo esempio**, non una preferenza già approvata. Il massimo di 26 prosecuzioni richiede invece fino a 199,84 minuti di sosta: **non è una proposta di buon servizio**, anche se tecnicamente il mezzo potrebbe proseguire.

### Concatenamenti passeggeri dell’esempio a 20

Le ore sono le partenze delle due corse da FS. Fra esse il mezzo percorre la prima ala, rientra a FS, sosta e parte nell’altra. Non sono due partenze consecutive a distanza di pochi minuti.

| Prima ala: partenza FS | Rientro FS nominale | Prosegue nell’altra ala alle | Sosta a FS |
|---|---|---|---|
| Ovest 06:30 | 07:11 | 07:35 | 23.6 min |
| Est 06:35 | 07:15 | 07:30 | 14.8 min |
| Ovest 07:00 | 07:41 | 08:05 | 23.6 min |
| Est 07:05 | 07:45 | 08:00 | 14.8 min |
| Ovest 07:30 | 08:11 | 08:35 | 23.6 min |
| Est 07:35 | 08:15 | 08:30 | 14.8 min |
| Ovest 08:00 | 08:41 | 09:05 | 23.6 min |
| Est 08:05 | 08:45 | 09:00 | 14.8 min |
| Est 10:35 | 11:15 | 11:35 | 19.8 min |
| Ovest 11:35 | 12:16 | 12:35 | 18.6 min |
| Est 16:35 | 17:15 | 17:35 | 19.8 min |
| Ovest 16:35 | 17:16 | 17:35 | 18.6 min |
| Est 17:05 | 17:45 | 18:05 | 19.8 min |
| Ovest 17:05 | 17:46 | 18:05 | 18.6 min |
| Est 17:35 | 18:15 | 18:35 | 19.8 min |
| Ovest 17:35 | 18:16 | 18:35 | 18.6 min |
| Est 18:05 | 18:45 | 19:05 | 19.8 min |
| Ovest 18:05 | 18:46 | 19:05 | 18.6 min |
| Est 18:35 | 19:15 | 19:40 | 24.8 min |
| Ovest 18:35 | 19:16 | 19:40 | 23.6 min |

### Tempi per chi non va in stazione

Viaggi diretti nominali nell’esempio a 20, con imbarco in punta mattutina 07–09; includono **tutta la sosta a FS**. Non sono tempi porta-a-porta, frequenze garantite fra le ali o medie ponderate per domanda. Ogni viaggio conserva gli identificativi delle due occorrenze.

| Collegamento | Durata a bordo, compresa sosta FS | Sosta FS compresa |
|---|---|---|
| Rovagnate AGIP → Brivio Via Como | 68.5–68.5 min | 23.6–23.6 min |
| Brivio Via Como → Rovagnate AGIP | 50.5–50.5 min | 14.8–14.8 min |
| Olgiate sud → nuova Arlate | 49.7–49.7 min | 23.6–23.6 min |
| Nuova Arlate → Olgiate sud | 36.9–36.9 min | 14.8–14.8 min |
| San Zeno → Olgiate sud | 21.8–21.8 min | 14.8–14.8 min |

**Restare a bordo elimina il cambio, non accorcia automaticamente il viaggio.** L’H30 già verificato riguarda i viaggi verso/dalla stazione: non viene esteso per etichetta a tutti i viaggi fra ali. Il registro pubblica anche le corse senza prosecuzione.

## Stress: non confondere quattro mezzi nominali con una garanzia

Con sei blocchi fissi compatibili con tutti i nove scenari e 15 minuti di recupero, la frontiera cambia: 16 prosecuzioni richiedono fino a 62,87 minuti di sosta nel caso di arrivo più anticipato; il recupero è verificato anche con l’arrivo più tardo. Il massimo di 24 richiede 332,87 minuti. Non sono probabilità di ritardo e non sono prestazioni da proporre al pubblico. Un blocco valido nel nominale non è automaticamente valido nello stress.

## Abbiamo provato anche a spostare le corse centrali

Enumerate **6 combinazioni ovest × 84 est = 504**, spostando soltanto le due partenze centrali ovest e le tre est ogni cinque minuti. Rimangono fermi punte, prime/ultime, 31 corse e i limiti fra partenze di 155/120 minuti. Anche in questo dominio il minimo per concatenamenti sempre alternati è **5 nominali / 7 severi**. È una prova su una rilassata necessaria, non la certificazione di tutti i 504 orari: includere anche eventuali casi non ammissibili rende il limite inferiore prudente. La base invariata, già verificata, raggiunge entrambi i minimi. Non è un’impossibilità globale su altri orari o requisiti.

## Ricontrollo congiunto: anche le partenze di punta possono muoversi

Non ci siamo fermati ai 504 casi centrali: il modello congiunto considera **317 partenze possibili e 21904 concatenamenti**. Le partenze possono cambiare ogni cinque minuti anche in punta, ma restano H30 per sito, gli obiettivi ferroviari ricalcolati con Arlate, 31 corse, prime/ultime, limiti centrali 155/120 e quattro mezzi nominali. Non è imposta la regolarità dei minuti.

Esito: **nessuna soluzione con concatenamenti sempre alternati** nel dominio dichiarato. Non è quindi solo un difetto dei minuti della tabella corrente.

**Confronto separato, non approvato, con cinque mezzi:** anche ottimizzando la peggiore sosta, il minimo nel dominio è **188.61 minuti** per concatenamenti tutti alternati. La verifica ricalcola le opportunità passeggeri e ricostruisce blocchi interi: non accetta flussi frazionari del risolutore come autobus. Questo dimostra perché aggiungere un autobus non basta a produrre una buona linea continua.

Queste sono prove su un requisito **più forte del solo nome unico**: ogni riuso del mezzo deve passare nell’altra ala. Una linea unica può invece avere alcune corse limitate a FS e cicli completi dichiarati: il modello non deve imporre l’alternanza sistematica al committente come se ne fosse l’unica interpretazione.

## Conseguenza progettuale

L’aggiunta di Arlate e l’esclusione di Via Indipendenza sono chiuse come indirizzo. La geometria e la produzione a 31 corse non vengono riaperte da questo audit. **Non è invece chiusa una linea intercomunale sempre continua e rapida:** il successivo chiarimento richiede che ogni corsa commerciale comprenda entrambe le ali e respinge corse limitate a FS. I contratti esaminati in questo audit non sono identici all’alternanza obbligatoria di ogni riuso del mezzo. Un mezzo in più, da solo, non dimostra che i viaggi diventino rapidi. Nessun incremento di flotta, nuova regola ferroviaria o orario alternativo è adottato qui.

Rigenerazione: `python -m scripts.phase2_audit_rt031_line8_through_service_v3` con `PYTHONPATH` su radice repository e `src`. Test: `python -m unittest discover -s tests -p test_phase2_rt031_line8_through_service_v3.py`.

[Scelte del committente](../config/rt031_stop_choices_and_through_line_v3.json) · [Frontiere, blocchi, eventi e viaggi (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/through_service_fixed_31.json.gz) · [Base a 31 corse](RT031_LINEA8_ORARIO_31_CORSE_V3.md)
