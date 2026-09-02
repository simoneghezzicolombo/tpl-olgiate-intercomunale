# Rapporto Finale di Sintesi Trasportistica e Territoriale
## Progetto: Rete TPL Intercomunale a Doppia Circolare Integrata con il Nodo Ferroviario Olgiate-Calco-Brivio FS

**Codice Studio**: `tpl-olgiate-intercomunale`  
**Data di Rilascio**: Settembre 2026  
**Autore**: Studio di Pianificazione e Data Science dei Trasporti  

---

## 1. Risposte Quantitative alle 18 Domande Decisionali

### 1. Dove dovrebbe passare la circolare?
La circolare deve configurarsi come una **rete a doppio anello a forma di "8"**, incernierata sulla **stazione ferroviaria di Olgiate-Calco-Brivio FS**:
- **Anello Ovest (9,5 km, 26 min)**: Olgiate FS → via Sommi Picenardi (Municipio) → SP342 dir → Rovagnate Centro → Perego Centro → Santa Maria Hoè Centro → Monticello di Olgiate → Mondonico Borgo → Olgiate FS.
- **Anello Est (10,3 km, 29 min)**: Olgiate FS → Calco Centro (via Nazionale) → Beverate Centro (Scuole) → Brivio Castello / Porto Adda → Arlate (San Colombano) → Calco Sud → Olgiate FS.

### 2. Quali frazioni conviene includere?
Conviene includere tassativamente:
- **Perego e Beverate**: confermate d'ufficio a costo marginale zero (sono situate direttamente sugli assi principali SP342 dir e SP72).
- **Mondonico (Olgiate)** e **Arlate (Calco)**: non come deviazioni a fondo cieco, ma come **rami di ritorno che chiudono i due anelli**, con rendimenti record rispettivamente di **613,3** e **1.150,0 residenti serviti per minuto di ciclo**.
- **Monticello di Olgiate** e **Rovagnate Centro**.

### 3. Quali deviazioni non valgono il tempo necessario?
- **San Zeno (Olgiate)**: deviazione a fondo cieco da +7,5 minuti (+12,9 km). Rendimento basso (94,7 ab/min) e soprattutto **sfora il vincolo di 60 min** (ciclo a 62,5 min). Bocciata per la linea fissa; consigliato servizio a chiamata (DRT).
- **Calco Superiore**: deviazione collinare da +4,5 minuti (128,9 ab/min). Porta il ciclo est a 33,5 min, riducendo il margine a Olgiate FS a soli 30 secondi. Rischio critico di collasso delle coincidenze ferroviarie.
- **Ravellino (+19 min)** e **Caprino/Celana (+20 min)**: dilatano il ciclo a 74–75 minuti, incompatibili con il cadenzamento a un solo mezzo.

### 4. Quanta popolazione serviamo realmente?
Applicando la rete pedonale reale slope-adjusted (corretta per le pendenze con Tobler's function) e la griglia demografica WorldPop calibrata sui totali ISTAT 2025:
- **Entro 5 minuti a piedi**: **9.180 residenti** (38,9% del bacino).
- **Entro 8 minuti a piedi**: **14.650 residenti** (62,6% del bacino).
- **Entro 10 minuti a piedi**: **17.350 residenti** (**75,7% dell'intera popolazione** dei 5 comuni).

### 5. Quanta popolazione oggi scarsamente servita guadagniamo?
Guadagniamo **2.150 nuovi residenti serviti entro 10 min a piedi** che oggi non hanno alcun servizio o dispongono solo di isolate corse scolastiche:
- **Mondonico e Monticello**: +920 residenti.
- **Arlate e San Colombano**: +1.150 residenti.
- Nuclei residenziali intermedi di Olgiate Sud e Beverate Est: +80 residenti.

### 6. Quante persone raggiungerebbero più facilmente Olgiate FS?
Oggi solo **4.579 residenti** vivono entro 15 minuti a piedi dalla stazione. Con la Linea 8 attiva:
- **Tutti i 17.350 residenti** coperti dalla linea raggiungono Olgiate FS con un viaggio in bus di durata compresa tra **5 e 18 minuti**.
- Secondo la matrice OD, il sistema intercetta potenzialmente oltre **4.470 spostamenti pendolari giornalieri** orientati su Olgiate FS e sulla direttrice S8 verso Milano e Lecco.

### 7. Quanto deve durare un giro?
Il tempo di marcia effettivo (comprensivo di dwell time alle fermate calibrate sulla domanda) è di:
- Anello Ovest: **26,0 minuti**.
- Anello Est: **29,0 minuti**.
- **Tempo di marcia totale dell'8**: **55,0 minuti**.

### 8. È realisticamente possibile un giro entro 60 minuti?
**SÌ, è pienamente e realisticamente possibile.**
Con 55 minuti di marcia, rimangono **5,0 minuti netti di sosta/buffer tecnico** alla stazione di Olgiate FS per assorbire la variabilità del traffico e garantire puntualità ferrea sulle coincidenze ferroviarie S8.

### 9. Servono 2 autobus o più?
Dipende dallo scenario di esercizio:
- **1 Autobus**: sufficiente per il servizio cadenzato a 60 minuti (Scenario 1, 13 corse/giorno a verso alternato).
- **2 Autobus**: necessari per il **servizio continuo contemporaneo a doppio verso (Orario CW + Antiorario CCW)** stile Merate (Scenario 2 a 26 corse/giorno, oppure **Scenario 4 Ibrido con 2 autobus nelle 6 ore di punta e 1 in morbida**).

### 10. Quale frequenza è ottenibile?
- Nello **Scenario 4 Ibrido (Raccomandato)**:
  - Nelle 6 ore di punta (06:30–09:30 e 16:30–19:30): **frequenza ogni 30 minuti per fermata** (un bus orario e uno antiorario ogni ora).
  - Nelle 7 ore di morbida diurna (09:30–16:30): **frequenza ogni 60 minuti**.
  - A Olgiate FS: un transito bus ogni 15 minuti in punta, ogni 30 minuti in morbida.

### 11. Quanti bus-km/anno servono?
- Scenario 1 (1 Bus orario): **77.992 bus-km/anno**.
- Scenario 2 (2 Bus continui 13h): **155.984 bus-km/anno**.
- **Scenario 4 Ibrido Raccomandato**: **112.261 bus-km/anno**.

### 12. Quanti degli attuali bus-km D184+D185 possono essere riutilizzati?
Il Programma di Bacino assegna oggi a D184+D185 **111.419 bus-km/anno**.
Nello Scenario 4 (112.261 km/anno), **il 99,2% della produzione è interamente coperto dalle risorse storiche esistenti**.
Lo scostamento è di appena **+842 km/anno (+0,75%)**, ovvero **perfetta neutralità economica a saldo zero**.

### 13. Come preserviamo Ravellino e Caprino?
Le code rurali non devono essere sacrificate, ma scorporate dal ciclo ad alta frequenza del core:
- **Ravellino (D184)**: mantenimento delle corse di punta scolastiche/pendolari del mattino e primo pomeriggio (circa 4 corse/giorno) e collegamento cadenzato biorario o a chiamata in morbida con coincidenza a Santa Maria Hoè.
- **Caprino Bergamasco / Celana (D185)**: navetta di adduzione dedicata sul ponte di Brivio (post-riapertura) o prolungamento delle sole corse di rinforzo negli orari scolastici del Collegio Celana.

### 14. Quanto migliora il collegamento con la S8?
Il miglioramento è radicale:
- Coincidenze utili giornaliere con i treni S8: da **24 corse attuali** a **88 corse nello Scenario 4** (+267%).
- Percentuale di treni S8 alimentati: dal **50%** al **100% nelle ore di punta**.
- Tempo medio di attesa all'interscambio ferro-gomma: **9,8 minuti** (Mediana: **9,5 min**, P90: **12,0 min**).
- Indice sintetico di interscambio: sale da **43,0 a 80,5 su 100**.

### 15. La soluzione bidirezionale è migliore dell'attuale D184+D185?
**Decisamente SÌ.**
Una linea circolare monodirezionale penalizza sistematicamente metà degli utenti (costretti a fare l'intero anello di 50 min al ritorno). La soluzione a doppio verso (stile Merate D201/D202) garantisce tempi minimi sia all'andata che al ritorno, dimezzando i tempi di permanenza a bordo per i residenti di Mondonico, Santa Maria Hoè, Brivio e Arlate.

### 16. Quale alternativa dà il miglior rapporto servizio/costo?
Lo **SCENARIO 4 (Ibrido di Punta a Saldo Zero)**:
- Assicura il servizio a doppio verso nelle fasce orarie in cui si concentra il 75% della domanda pendolare e studentesca.
- Mantiene il servizio orario cadenzato nella morbida.
- Richiede **zero risorse finanziarie aggiuntive** rispetto ai contratti vigenti di D184+D185.

### 17. Dove servono verifiche fisiche delle strade?
Sono stati censiti **5 punti critici** in `outputs/field_checks.csv`:
1. *Mondonico*: verifica larghezza strettoia borgo (tra 3,3 e 3,6m) per idoneità bus 10,5m vs midibus 8,5m.
2. *Arlate*: verifica raggio di svolta e visibilità all'innesto tra via San Gottardo e SP72.
3. *Calco Superiore*: tornante stretto via Volta (confermata impraticabilità per bus 12m).
4. *San Zeno*: confermata assenza di spazio di manovra/inversione per mezzi TPL.
5. *Ponte di Brivio*: verifica limiti di carico e cronoprogramma provinciale fine lavori.

### 18. Quali bisogni dobbiamo poi verificare con i residenti?
Tramite la proposta di questionario strutturata (`survey/questionario.md`):
- Minuti massimi accettabili di cammino a piedi per frazione e fascia d'età.
- Soglia di frequenza minima percepita come alternativa credibile all'auto privata (30' vs 60').
- Destinazioni extra-ferroviarie prioritarie (Ospedale Merate, poliambulatori, scuole).
- Barriere architettoniche e assenza di marciapiedi lungo le provinciali.

---

## 2. Matrice di Valutazione Analitica di Tutte le Frazioni

| Località / Frazione | Comune | Residenti Aggiuntivi (8 min) | Minuti Aggiuntivi Ciclo | Rendimento (ab./min) | POI Serviti | Decisione Motivata di Piano |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Perego Centro** | La Valletta Brianza | 1.850 | 0,0 min | $\infty$ | 5 | **INCLUSO D'UFFICIO**: Asse centrale SP342 dir a costo zero. |
| **Beverate Centro** | Brivio | 1.600 | 0,0 min | $\infty$ | 4 | **INCLUSO D'UFFICIO**: Asse centrale SP72 a costo zero. |
| **Rovagnate Centro** | La Valletta Brianza | 2.806 | 0,0 min | $\infty$ | 6 | **INCLUSO D'UFFICIO**: Asse portante Ovest. |
| **Santa Maria Hoè Centro** | Santa Maria Hoè | 2.109 | 0,0 min | $\infty$ | 5 | **INCLUSO D'UFFICIO**: Capolinea/Cerniera ala Ovest. |
| **Calco Centro / Naz.** | Calco | 3.730 | 0,0 min | $\infty$ | 8 | **INCLUSO D'UFFICIO**: Asse portante Est. |
| **Brivio Porto / Adda** | Brivio | 2.757 | 0,0 min | $\infty$ | 6 | **INCLUSO D'UFFICIO**: Capolinea/Cerniera ala Est. |
| **Arlate / S. Colombano** | Calco | **1.150** | **+1,0 min** (in anello) | **1.150,0** | 3 | **INCLUSO (RACCOMANDATO)**: Chiude l'anello Est risparmiando km a vuoto su SP72. |
| **Mondonico / Monticello** | Olgiate Molgora | **920** | **+1,5 min** (in anello) | **613,3** | 3 | **INCLUSO (RACCOMANDATO)**: Chiude l'anello Ovest da S. Maria verso Olgiate FS. |
| **Calco Superiore** | Calco | 580 | +4,5 min | 128,9 | 1 | **ESCLUSO DALL'ORARIO FISSO**: Rischio critico per il ciclo (buffer ridotto a 30s). |
| **San Zeno** | Olgiate Molgora | 710 | +7,5 min | 94,7 | 1 | **ESCLUSO**: Sfora a 62,5 min e manca piazzola di inversione. Servire con TPL a chiamata. |
| **Caprino Bergamasco** | Caprino Bergamasco | 1.400 | +20,0 min | 70,0 | 2 | **SCORPORATO DAL CORE**: Dilata ciclo a 75 min. Servire con navetta d'Adda o corse di punta. |
| **Ravellino** | Colle Brianza | 520 | +19,0 min | 27,4 | 1 | **SCORPORATO DAL CORE**: Dilata ciclo a 74 min. Mantenere solo corse scolastiche. |
