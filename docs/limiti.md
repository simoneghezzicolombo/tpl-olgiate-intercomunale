# Limiti dello Studio, Assunzioni e Margini di Incertezza

## 1. Classificazione Epistemica dei Dati Utilizzati

Come richiesto dai criteri di rigore scientifico del progetto, tutti i dati e le stime vengono classificati secondo quattro categorie esplicite:

| Categoria | Definizione | Elementi nel Progetto |
| :--- | :--- | :--- |
| **FACT (Fatto accertato)** | Dati ufficiali verificati da fonti primarie pubbliche | Totali demografici ISTAT 2025; Flussi passeggeri SFR Trenord 2015-2025; Budget km del Programma di Bacino Agenzia TPL (111.419 km); Orari ferroviari S8 vigenti RFI; Orari ufficiali attuali Arriva D184/D185. |
| **ESTIMATE (Stima statistica)** | Valori derivati da modelli consolidati su basi campionarie | Griglia spaziale di popolazione WorldPop riscalata sui 5 comuni; Tempi di cammino pedonale corretti per pendenza con formula di Tobler; Matrice del pendolarismo ISTAT aggiornata al 2024/2025. |
| **ASSUMPTION (Assunzione di calcolo)** | Ipotesi operative dichiarate e testate | Velocità pedonale base in piano di 4,8 km/h (80 m/min); Detour factor viario medio di 1,25; Dwell time alle fermate di 20 secondi; 303 giorni feriali annui di servizio; Finestra ideale di coincidenza ferro-gomma tra 4 e 16 minuti. |
| **MODEL OUTPUT (Risultato del modello)** | Valori calcolati dagli algoritmi di routing e simulazione | Runtime di ciclo (55 min); Fabbisogni chilometrici per scenario; Frontiera di Pareto; Graduatoria dei rendimenti marginali delle deviazioni. |

---

## 2. Limiti Noti e Margini di Incertezza

### A. Condizioni di Traffico e Congestione Stradale
- Il routing e i tempi di percorrenza sono stati calibrati sui tempi effettivi registrati dall'orario reale estivo/invernale di Arriva (55 min di marcia per l'8 completo).
- Nelle ore di punta più intense (07:30–08:30 e 18:00–19:00), la presenza di code lungo la **SP342 dir (tra Rovagnate e Olgiate)** o all'innesto della **SP72 a Calco** può introdurre ritardi stimati in 2–4 minuti.
- Il buffer di recupero di **5,0 minuti netti alla stazione di Olgiate FS** è dimensionato esattamente per assorbire questa variabilità, ma richiederà preferenziamento semaforico negli incroci più congestionati.

### B. Geometria dei Mezzi nel Borgo Storico di Mondonico
- Come evidenziato in `outputs/field_checks.csv`, la strettoia all'ingresso di Mondonico presenta una larghezza compresa tra 3,3 e 3,6 metri.
- Il modello assume l'impiego di **autobus suburbani corti (10,5 metri)** o **midibus (8,5–9,0 metri)**. Qualora l'ente gestore intendesse utilizzare autobus standard da 12 metri o 18 metri, la fermata di Mondonico dovrà essere attestata all'imbocco di via Molgora su via Como, con un incremento di cammino a piedi di circa 150 metri per gli abitanti del borgo.

### C. Risoluzione Spaziale del DEM
- La correzione altimetrica di Tobler è stata applicata utilizzando il Copernicus DEM a 30 metri di risoluzione.
- Micro-dislivelli (gradinate pedonali secondarie, rampe locali) potrebbero presentare pendenze puntuali leggermente diverse da quelle modellate, pur non alterando l'ordine di grandezza dei bacini a 8–10 minuti.

### D. Costi Contrattuali Unitari
- Come richiesto dalle istruzioni metodologiche ("Se non esiste un costo unitario sufficientemente affidabile: NON INVENTARLO"), lo studio esprime la sostenibilità economica in termini di **bus-km annuali**, **ore-veicolo** e **mezzi impegnati**.
- L'esatto costo monetario in Euro dipenderà dal corrispettivo chilometrico applicato nella nuova gara d'appalto dell'Agenzia del TPL di Como, Lecco e Varese (indicativamente compreso tra 2,40 e 3,10 €/bus-km per il servizio interurbano/suburbano lombardo).
