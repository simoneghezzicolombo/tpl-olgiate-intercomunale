# Phase 2 — Audit e trend OD lavoro ISTAT 2011 → 2021

## Stato

**Verdetto: `VALIDATED_WITH_SERIES_BREAK`**

È tecnicamente possibile costruire una matrice OD comunale 2011 per **motivo lavoro** confrontabile, nelle dimensioni territoriali fondamentali, con la matrice lavoro 2021. Il confronto non è però una serie longitudinale perfettamente omogenea: tra 2011 e 2021 cambia il sistema censuario e il 2021 cade in un periodo ancora influenzato da pandemia e lavoro da remoto.

Di conseguenza:

- i valori 2011 e 2021 possono essere confrontati come **differenze descrittive osservate**;
- non è metodologicamente corretto attribuire l'intera differenza a un cambiamento di comportamento dei residenti;
- ogni interpretazione causale deve usare anche il contesto 2019 e gli indicatori demografici/occupazionali più recenti documentati in `PHASE2_MOBILITY_CONTEXT_2019_2024.md`.

## 1. Fonti ufficiali

### 2011

Archivio ISTAT ufficiale:

`https://www.istat.it/storage/cartografia/matrici_pendolarismo/matrici_pendolarismo_2011.zip`

Nel file ZIP sono presenti:

- `MATRICE PENDOLARISMO 2011/matrix_pendo2011_10112014.txt`;
- `MATRICE PENDOLARISMO 2011/leggimi file matrix_pendo2011_10112014.doc`.

Il `leggimi` ufficiale è stato estratto e conservato in:

`outputs/phase2/istat2011_source_inspection/leggimi_official_extracted.txt`

Sono inoltre conservati inventario ZIP, checksum e campioni dei record `S` e `L` in `outputs/phase2/istat2011_source_inspection/`.

### 2021

Pagina ISTAT:

`https://www.istat.it/notizia/matrice-di-pendolarismo-per-lavoro/`

Archivio ufficiale:

`https://esploradati.istat.it/databrowser/DWL/PERMPOP/MATPEN/matrix_pendoLAVORO_2021.zip`

La matrice 2021 utilizzata dalla Phase 2 è già stata verificata in `docs/PHASE2_DEMAND_PROFILE_2021.md`.

## 2. Tracciato record ufficiale 2011

Il file 2011 contiene due tipi di record diversi.

| Record | Contenuto | Uso corretto |
|---|---|---|
| `S` | strati aggregati per residenza, sesso, motivo e luogo di studio/lavoro | **da usare per la matrice OD base** |
| `L` | disaggregazione aggiuntiva per mezzo, fascia oraria e durata | non va sommata ai record `S` |

Il file contiene 988.625 record `S` e 3.887.617 record `L`.

Per i record `S` le dimensioni rilevanti sono:

- tipo di residenza;
- provincia e comune di residenza;
- sesso;
- motivo: `1 = studio`, `2 = lavoro`;
- luogo: `1 = stesso comune`, `2 = altro comune italiano`, `3 = estero`;
- provincia e comune di destinazione;
- stato estero;
- numero di individui.

Il `leggimi` ufficiale stabilisce che, quando l'analisi utilizza soltanto le variabili dei record `S`, deve essere utilizzato il campo **Numero di individui**.

Posizioni ufficiali, numerazione a partire da 1:

| Campo | Colonne |
|---|---:|
| tipo record | 1 |
| tipo residenza | 3 |
| provincia residenza | 5–7 |
| comune residenza | 9–11 |
| sesso | 14 |
| motivo | 16 |
| luogo | 18 |
| provincia destinazione | 20–22 |
| comune destinazione | 24–26 |
| stato estero | 28–30 |
| stima individui | 39–50 |
| **numero di individui** | **51–60** |

## 3. Audit della precedente estrazione Gate A

Il file legacy:

`data/raw/od/matrice_pendolarismo_istat_2011_core.csv`

**non deve essere utilizzato per il confronto storico**.

L'audit ha identificato tre errori bloccanti nello script Gate A che lo ha prodotto:

1. offset fixed-width errati: sesso, motivo, luogo e codici di destinazione venivano letti una colonna prima della posizione ufficiale;
2. il flusso veniva letto da `line[40:50]`, invece del campo ufficiale `Numero di individui` alle colonne 51–60;
3. Perego e Rovagnate erano identificati con progressivi `067/072`, mentre i codici corretti nel 2011 sono `097066` e `097073`.

Lo script nuovo `scripts/phase2_audit_istat_od_2011.py` riparte quindi **direttamente dallo ZIP ISTAT originale**, senza utilizzare il CSV Gate A come input analitico.

## 4. Regole della matrice canonica 2011

La matrice canonica è costruita con le seguenti regole:

1. record `S` soltanto;
2. `motivo = 2`, quindi lavoro;
3. entrambi i sessi, che costituiscono strati disgiunti;
4. entrambi i tipi di residenza, anch'essi strati disgiunti;
5. destinazioni italiane soltanto, `luogo = 1/2`;
6. esclusione dei record `luogo = 3` all'estero, perché la matrice 2021 è limitata alle destinazioni in Italia;
7. somma del campo ufficiale `Numero di individui`;
8. armonizzazione amministrativa **prima** del groupby OD.

Sono stati selezionati 1.402 strati lavoro/domestici con origine nei cinque comuni, che diventano 856 coppie OD uniche dopo l'armonizzazione. Non esistono duplicati dello stesso strato `S`.

Output canonico:

`data/raw/od/matrice_pendolarismo_istat_2011_work_core_canonical.csv`

## 5. Armonizzazione amministrativa

Per la geografia dei cinque comuni è essenziale trattare la fusione di La Valletta Brianza prima dell'aggregazione:

- `097066` Perego → `097092` La Valletta Brianza;
- `097073` Rovagnate → `097092` La Valletta Brianza.

In questo modo un movimento Perego ↔ Rovagnate del 2011 diventa correttamente un movimento interno alla La Valletta Brianza attuale.

Sono state inoltre armonizzate tutte le variazioni amministrative effettivamente osservate tra le destinazioni dei cinque comuni, senza crosswalk inventati:

- Verderio Inferiore e Verderio Superiore → Verderio;
- Torre de' Busi, ricodificata dalla provincia di Lecco a quella di Bergamo;
- Cadrezzate e Osmate → Cadrezzate con Osmate;
- Bellagio e Civenna → Bellagio;
- Vermezzo e Zelo Surrigone → Vermezzo con Zelo;
- Brembilla e Gerosa → Val Brembilla.

Il test finale richiede che non rimanga alcun codice 2011 dismesso osservato nei flussi dei cinque comuni senza mappatura esplicita.

## 6. Compatibilità 2011 e 2021

### Dimensioni confrontabili

Sono confrontabili:

- comune di residenza;
- comune abituale di lavoro in Italia;
- motivo lavoro.

### Rotture di serie

Non sono omogenei:

- **2011:** conteggio censuario completo;
- **2021:** stima del Censimento permanente integrata con registri amministrativi;
- **2011:** spostamento quotidiano e ritorno giornaliero dichiarato al Censimento;
- **2021:** occupato che raggiunge il luogo abituale di lavoro almeno tre giorni alla settimana;
- il riferimento 2021 è il 31 dicembre 2021, in un contesto ancora influenzato da pandemia e smart working;
- il 2021 esclude le destinazioni di lavoro all'estero. Per questo sono state escluse anche nel 2011.

Il confronto è quindi valido per descrivere **come cambia la struttura osservata dei flussi**, non per misurare senza errore una variazione comportamentale pura.

## 7. Risultati principali

### 7.1 Lavoratori residenti nei cinque comuni

| Comune | 2011 | 2021 | Δ | Δ % |
|---|---:|---:|---:|---:|
| Brivio | 1.806 | 1.662 | −144 | −8,0% |
| Calco | 2.123 | 2.173 | +50 | +2,4% |
| **Olgiate Molgora** | **2.285** | **2.287** | **+2** | **+0,1%** |
| Santa Maria Hoè | 896 | 836 | −60 | −6,7% |
| La Valletta Brianza | 1.813 | 1.796 | −17 | −0,9% |
| **Totale** | **8.923** | **8.754** | **−169** | **−1,9%** |

Il primo risultato importante è quindi negativo rispetto all'ipotesi di un grande crollo: **la base dei lavoratori pendolari residenti nei cinque comuni è sostanzialmente stabile**.

### 7.2 Il vero cambiamento è la geografia del lavoro

| Componente | 2011 | 2021 | Δ | Δ % |
|---|---:|---:|---:|---:|
| lavoro nel proprio comune | 1.716 | 1.315 | −401 | −23,4% |
| lavoro in un altro dei cinque comuni | 1.259 | 1.055 | −204 | −16,2% |
| destinazioni esterne S8 | 1.759 | 1.882 | +123 | +7,0% |
| altre destinazioni esterne | 4.189 | 4.502 | +313 | +7,5% |

Complessivamente, il lavoro localizzato **all'interno del sistema dei cinque comuni**, includendo sia self sia altri comuni core, passa da 2.975 a 2.370 persone.

La quota sui residenti pendolari per lavoro scende:

- **33,34% nel 2011**;
- **27,07% nel 2021**.

Di conseguenza la quota diretta verso l'esterno sale dal 66,66% al 72,93%, **+6,27 punti percentuali**.

### 7.3 Self-containment

| Comune | 2011 | 2021 | Δ p.p. |
|---|---:|---:|---:|
| Brivio | 25,86% | 19,43% | −6,42 |
| Calco | 15,12% | 12,84% | −2,28 |
| **Olgiate Molgora** | **16,72%** | **14,25%** | **−2,46** |
| Santa Maria Hoè | 18,86% | 13,40% | −5,46 |
| La Valletta Brianza | 20,79% | 15,31% | −5,48 |
| **Totale cinque** | **19,23%** | **15,02%** | **−4,21** |

### 7.4 Milano, Lecco, Merate e corridoio S8

Aggregando le origini dei cinque comuni:

| Destinazione | 2011 | 2021 | Δ | Δ % |
|---|---:|---:|---:|---:|
| Milano | 618 | 571 | −47 | −7,6% |
| **Lecco** | **352** | **511** | **+159** | **+45,2%** |
| Merate | 801 | 680 | −121 | −15,1% |
| **S8 esterna complessiva** | **1.759** | **1.882** | **+123** | **+7,0%** |

Il cambiamento non è quindi semplicemente una crescita dei flussi verso Milano. Nel dato osservato cresce soprattutto Lecco e aumenta moderatamente il complesso delle destinazioni direttamente associate al corridoio ferroviario S8.

Questo risultato è **compatibile** con una crescente integrazione lungo il corridoio ferroviario, ma non dimostra un effetto causale della stazione. Cambiano contemporaneamente localizzazione dei posti di lavoro, composizione degli occupati, organizzazione territoriale e metodologia statistica.

### 7.5 Olgiate Molgora

Olgiate è particolarmente interessante perché il numero complessivo di lavoratori pendolari residenti è praticamente identico:

- 2011: 2.285;
- 2021: 2.287.

Cambia invece la distribuzione:

- lavoro a Olgiate: 382 → 326, −14,7%;
- lavoro in un altro comune core: 378 → 292, −22,8%;
- destinazioni S8 esterne: 522 → 554, +6,1%;
- Milano: 204 → 185, −9,3%;
- Lecco: 100 → 138, +38,0%;
- Merate: 211 → 217, +2,8%;
- Osnago: 37 → 62, +67,6%;
- Cernusco Lombardone: 60 → 59, sostanzialmente stabile.

Quindi **Olgiate non ha più lavoratori pendolari nel 2021 di quanti ne avesse nel 2011**, ma questi lavoratori risultano meno autocontenuti e più distribuiti su una rete territoriale esterna.

## 8. Cosa non possiamo concludere dal solo 2011 → 2021

Non è corretto concludere direttamente che:

- il lavoro locale sia realmente crollato del 23%;
- il Covid spieghi tutto;
- la S8 sia la causa della maggiore esternalizzazione;
- Merate abbia perso il 15% della propria attrattività reale in senso causale.

Per distinguere trasformazione strutturale e shock 2021 è necessario usare il ponte 2019. Questo è fatto nel documento `docs/PHASE2_MOBILITY_CONTEXT_2019_2024.md`.

## 9. Output riproducibili

- `scripts/phase2_audit_istat_od_2011.py`
- `data/raw/od/matrice_pendolarismo_istat_2011_work_core_canonical.csv`
- `outputs/phase2/od_2011_audit.json`
- `outputs/phase2/od_2011_core_summary.csv`
- `outputs/phase2/od_trend_2011_2021.csv`
- `outputs/phase2/od_trend_destinations_2011_2021.csv`
- `outputs/phase2/od_trend_internal_core_2011_2021.csv`
- `outputs/phase2/od_2011_destination_codes_not_in_2021.csv`

Il workflow `.github/workflows/phase2-od-2011-audit.yml` ricostruisce i dati da clean checkout e verifica, tra le altre cose:

- assenza di duplicati OD canonici;
- assenza di predecessori amministrativi non armonizzati;
- riconciliazione esatta dei totali 2021 con il profilo Phase 2 già verificato;
- totale 2021 dei cinque comuni pari a 8.754;
- assenza di codici storici osservati senza crosswalk esplicito.

## 10. Nota su analisi 2011 → 2019 precedenti

Qualsiasi precedente confronto che abbia usato il file sintetico/aggregato `pendolari_2011_in_out_self` come se rappresentasse **studio + lavoro** deve essere considerato superato. Quel prodotto era riferito al lavoro e non può essere confrontato direttamente con un totale 2019 studio+lavoro.

Il confronto corretto con il 2019 usa il nuovo 2011 work-only auditato e il campo 2019 `REAS_COMMUTING = WK`, documentato separatamente nel contesto 2019–2024.
