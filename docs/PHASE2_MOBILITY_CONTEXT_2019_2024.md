# Phase 2 — Contesto mobilità, popolazione, occupati e studio 2019–2024

## Scopo

Questo documento completa l'audit OD 2011→2021 con dati che aiutano a distinguere:

- trasformazioni strutturali già visibili prima del Covid;
- anomalie specifiche del 2021;
- cambiamenti nella popolazione residente;
- cambiamenti nel numero di occupati residenti;
- ruolo della mobilità per studio.

**Questi dati non vengono forzati dentro la matrice OD 2011→2021.** Sono un livello di contesto separato e ogni serie conserva la propria definizione statistica.

## 1. Fonti e disponibilità effettiva

### Mobilità comunale 2019

Dataflow ISTAT SDMX:

`DF_DCSS_ISTR_LAV_PEN_2_TV_5`

Indicatore: popolazione residente che si sposta giornalmente per studio o lavoro.

Il dato distingue:

- `WK`: lavoro;
- `STD`: studio;
- `SMPUR`: stesso comune;
- `OMPUR`: fuori comune.

Per tutti i 15 comuni del Meratese è verificata l'identità:

`totale = lavoro + studio = stesso comune + fuori comune`.

Output:

`outputs/phase2/mobility_context_meratese_2019.csv`

### Popolazione residente 2019–2024

Dataflow ISTAT:

`DF_DCSS_FAM_POP_TV_1`, indicatore `RESPOP_AV`.

La serie è disponibile annualmente dal 2019 al 2024 per tutti i comuni analizzati.

### Occupati residenti

Dataflow ISTAT:

`DF_DCSS_ISTR_LAV_PEN_2_TV_3`

Sono utilizzati esclusivamente:

- `CUR_ACT_STAT = 1`, occupato;
- sesso totale;
- cittadinanza totale;
- istruzione totale;
- destinazione e motivo non selettivi;
- `AGE_NOCLASS = Y_GE15`, aggregato pubblicato direttamente per la popolazione di 15 anni e più.

L'aggregato è identificato per **2019, 2021, 2022, 2023 e 2024**. Nel tracciato interrogato il 2020 non è pubblicato con lo stesso aggregato, quindi resta vuoto e non viene interpolato.

Output:

`outputs/phase2/mobility_context_population_employment_2019_2024.csv`

### Studenti dopo il 2019

Una serie comunale pubblica equivalente al dato 2019 `REAS_COMMUTING = STD` **non è stata identificata** per gli anni successivi.

Gli allegati pubblici ISTAT sulla popolazione insistente 2019–2023 sono stati scaricati e scanditi integralmente cercando codici e nomi dei 15 comuni del Meratese. Il numero di corrispondenze è **zero**: gli allegati pubblici espongono aggregati territoriali superiori, non una tavola comunale completa utilizzabile direttamente per Olgiate, Merate e gli altri comuni.

Non vengono quindi inventati valori comunali 2020–2023 per gli studenti.

Il database integrato ARCH.I.M.E.DE. consente analisi molto più granulari, ma l'accesso ai microdati non equivale a un normale dataset open scaricabile e non viene trattato come tale in questa Phase 2.

## 2. Il ponte 2019 cambia l'interpretazione del 2021

Per i cinque comuni core, usando nel 2019 **solo il motivo lavoro**:

| Comune | lavoro 2011 | lavoro 2019 | lavoro 2021 | self-containment 2011 | 2019 | 2021 |
|---|---:|---:|---:|---:|---:|---:|
| Brivio | 1.806 | 1.761 | 1.662 | 25,86% | 20,44% | 19,43% |
| Calco | 2.123 | 2.404 | 2.173 | 15,12% | 13,35% | 12,84% |
| **Olgiate Molgora** | **2.285** | **2.481** | **2.287** | **16,72%** | **14,51%** | **14,25%** |
| Santa Maria Hoè | 896 | 906 | 836 | 18,86% | 14,02% | 13,40% |
| La Valletta Brianza | 1.813 | 1.870 | 1.796 | 20,79% | 14,44% | 15,31% |
| **Totale** | **8.923** | **9.422** | **8.754** | **19,23%** | **15,26%** | **15,02%** |

Il 2019 non fornisce la stessa OD completa del 2011 e 2021, quindi la tabella non viene trattata come una singola serie omogenea di destinazioni. È però un ponte molto informativo sul lato dei residenti.

### Risultato principale

Tra 2011 e 2019 il numero di residenti che si spostano quotidianamente per lavoro nei cinque comuni **aumenta del 5,6%**.

Tra 2019 e 2021 il numero osservato nella matrice lavoro 2021 è invece inferiore del **7,1%**.

Il self-containment, però, era già passato:

**19,23% nel 2011 → 15,26% nel 2019 → 15,02% nel 2021.**

Questo suggerisce una distinzione molto importante:

- la **riduzione del lavoro nel proprio comune** non nasce nel 2021, ma è in larga misura già visibile prima della pandemia;
- il forte calo del volume osservato tra 2019 e 2021 è invece molto più compatibile con l'effetto combinato di Covid, lavoro da remoto e diversa metodologia della matrice 2021.

Non è una dimostrazione causale, ma evita di attribuire al Covid un processo di esternalizzazione che era già in corso.

## 3. Olgiate Molgora

### Residenti che si muovono nel 2019

Nel 2019 Olgiate registra:

- 3.618 residenti che si spostano quotidianamente per studio o lavoro;
- 2.481 per lavoro;
- 1.137 per studio;
- 2.723 fuori comune;
- 895 nello stesso comune.

Per il lavoro:

- 2.121 fuori comune;
- 360 nello stesso comune;
- self-containment lavoro: **14,51%**.

Per lo studio:

- 602 fuori comune;
- 535 nello stesso comune;
- quota di studenti residenti che studia nel comune: **47,1%**.

### Tra 2011, 2019 e 2021

Per il lavoro residente:

- 2011: 2.285;
- 2019: 2.481, **+8,6% rispetto al 2011**;
- 2021: 2.287, **−7,8% rispetto al 2019** e quasi identico al 2011.

Il self-containment passa:

**16,72% → 14,51% → 14,25%.**

Quindi il dato 2021 da solo avrebbe potuto far pensare a una diminuzione strutturale della mobilità lavorativa. Il 2019 mostra invece che, prima del Covid, il numero dei residenti che si spostavano per lavoro era cresciuto sensibilmente.

## 4. Popolazione e occupati: il cambiamento non è spiegato da una forte crescita demografica

### Cinque comuni core

Popolazione residente:

- 2019: **23.142**;
- 2024: **22.914**;
- variazione: **−1,0%**.

Occupati residenti di 15 anni e più:

- 2019: **10.401**;
- 2021: **10.438**;
- 2024: **10.791**;
- 2019→2024: **+3,7%**.

Quindi la popolazione complessiva cala leggermente, mentre il numero di occupati residenti cresce.

Nel 2019 i 9.422 residenti che si spostano quotidianamente per lavoro rappresentano circa il **90,6%** dei 10.401 occupati residenti. Nel 2021 i 8.754 lavoratori della matrice rappresentano circa l'**83,9%** dei 10.438 occupati residenti.

Questa differenza è coerente con il fatto che nel 2021 una quota maggiore di occupati possa non essere classificata come pendolare verso il luogo abituale di lavoro, anche per lavoro da casa, minore frequenza fisica e diversa definizione statistica.

### Intero Meratese, 15 comuni

Popolazione:

- 2019: **74.955**;
- 2024: **75.345**;
- variazione: **+0,5%**.

Occupati residenti:

- 2019: **33.189**;
- 2024: **34.954**;
- variazione: **+5,3%**.

Il territorio è quindi demograficamente quasi stabile, mentre aumenta il numero di occupati residenti.

Questo è fondamentale per interpretare la mobilità: **le trasformazioni osservate non possono essere spiegate semplicemente da un aumento o calo generalizzato dei residenti.**

## 5. Olgiate, Merate, Cernusco e Osnago 2019–2024

| Comune | popolazione 2019 | 2024 | Δ pop. | occupati 2019 | 2024 | Δ occupati |
|---|---:|---:|---:|---:|---:|---:|
| **Olgiate Molgora** | 6.392 | 6.332 | −0,9% | 2.746 | 2.880 | **+4,9%** |
| **Merate** | 14.492 | 14.954 | +3,2% | 6.083 | 6.575 | **+8,1%** |
| **Cernusco Lombardone** | 3.824 | 3.853 | +0,8% | 1.621 | 1.734 | **+7,0%** |
| **Osnago** | 4.787 | 4.769 | −0,4% | 2.116 | 2.260 | **+6,8%** |

Questo ridimensiona l'ipotesi semplice secondo cui eventuali cambiamenti di mobilità derivino dalla crescita della popolazione nei comuni lungo la ferrovia. Olgiate e Osnago, per esempio, hanno una popolazione 2024 leggermente inferiore al 2019 ma più occupati residenti.

La ferrovia resta una possibile componente interpretativa della geografia degli spostamenti, non una spiegazione già dimostrata.

## 6. Merate e la funzione scolastica nel 2019

Il dato studio evidenzia una differenza funzionale netta.

Nel 2019 Merate ha:

- 2.491 studenti residenti che si spostano quotidianamente;
- 1.702 che studiano nel comune;
- 789 che studiano fuori comune.

Quindi circa il **68,3%** degli studenti residenti di Merate studia a Merate.

Olgiate ha:

- 1.137 studenti residenti;
- 535 nello stesso comune;
- quota interna: **47,1%**.

Questo conferma che il ruolo territoriale di Merate non può essere valutato solo attraverso la matrice del lavoro: scuola e servizi producono una centralità diversa da quella occupazionale.

Non disponendo di una serie comunale pubblica equivalente per gli studenti dopo il 2019, questo risultato viene mantenuto come fotografia pre-Covid e non proiettato arbitrariamente sugli anni successivi.

## 7. Contesto nazionale 2019–2023

Gli allegati sulla popolazione insistente mostrano, a livello nazionale, la seguente consistenza per il segnale lavoro, limitandosi alla riga totale e rimuovendo le ripetizioni per sottogruppi e percentuali:

| Anno | stesso comune | altro comune | somma |
|---|---:|---:|---:|
| 2019 | 9.465.508 | 14.323.082 | 23.788.590 |
| 2020 | 10.517.206 | 13.061.426 | 23.578.632 |
| 2021 | 10.562.290 | 13.702.038 | 24.264.328 |
| 2022 | 10.903.169 | 14.105.705 | 25.008.874 |
| 2023 | 11.107.195 | 14.341.273 | 25.448.468 |

Questa serie non è una misura pura dei viaggi fisici quotidiani e non deve essere usata per sostituire una matrice comunale OD. Serve però a mostrare che il sistema integrato ISTAT registra una ripresa e crescita della presenza lavorativa dopo il 2020.

Per scuola e università, gli stessi allegati mostrano una traiettoria diversa e tendenzialmente decrescente negli ultimi anni. Anche questo rafforza la necessità di separare lavoro e studio invece di usare un unico totale indistinto.

## 8. Implicazioni per l'analisi territoriale

La lettura congiunta dei dati suggerisce quattro punti robusti:

1. **Il Meratese non cresce molto in popolazione**, ma cresce la sua popolazione occupata.
2. **La maggiore dipendenza da luoghi di lavoro esterni è già visibile entro il 2019**, quindi non è semplicemente un artefatto Covid.
3. **Il 2021 comprime il numero di pendolari osservati rispetto al 2019**, mentre gli occupati residenti non diminuiscono. Questo rende plausibile una forte componente pandemia/metodologia nel livello assoluto della matrice 2021.
4. L'organizzazione territoriale è differenziata: Merate mantiene una forte funzione scolastica, mentre Olgiate e gli altri comuni core sono molto più dipendenti da reti lavorative sovracomunali.

La domanda successiva non dovrebbe quindi essere soltanto “quanto conta la stazione?”, ma:

> come si sta trasformando il sistema intercomunale di residenza, lavoro, studio e accesso ai poli, e quali nodi di trasporto possono servire meglio questa struttura sempre più sovracomunale?

## 9. Limiti e dati non identificabili

- Il 2019 comunale distingue lavoro/studio e dentro/fuori comune, ma non fornisce in questo dataflow la matrice completa delle destinazioni.
- Gli allegati pubblici 2019–2023 della popolazione insistente non contengono righe comunali per i 15 comuni target.
- Non è stata identificata una serie comunale pubblica 2020–2024 equivalente per gli studenti residenti pendolari.
- Gli occupati 2020 non sono pubblicati nel dataflow interrogato con l'aggregato `Y_GE15` e restano quindi `NA`.
- Nessun valore mancante viene interpolato o ricostruito.

## 10. Output e riproducibilità

- `scripts/phase2_fetch_mobility_context.py`
- `outputs/phase2/mobility_context_audit.json`
- `outputs/phase2/mobility_context_meratese_2019.csv`
- `outputs/phase2/mobility_context_population_employment_2019_2024.csv`
- `outputs/phase2/mobility_context_national_2019_2023.csv`
- `outputs/phase2/mobility_context_workbook_scan.json`

La pipeline valida algebraicamente tutti i dati comunali 2019 e mantiene separati questi output dalla matrice OD auditata 2011→2021.
