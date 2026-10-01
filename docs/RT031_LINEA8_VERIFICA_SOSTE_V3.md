# Linea 8: verifica delle soste e correzione della lettura delle coincidenze

## Risultato decisivo

**L'anticipo mattutino di 3–8 minuti precedentemente individuato non supera la sensibilità di 30 secondi a ogni fermata ipotizzata.** Non deve essere presentato come soluzione affidabile per il 07:26 verso Milano. Rimane un risultato corretto e limitato al modello a soste zero.

Sull'ala ovest sono ipotizzate 15 occorrenze non-FS di fermata; sull'est 12 o 13 secondo il verso. Un'identità incontrata nel grafo non è una fermata autorizzata: qui ogni nodo di sosta distinto è un'ipotesi esplicita. Due identità allo stesso progressivo ricevono una sola sosta, mentre due passaggi distinti allo stesso nodo restano due occorrenze.

| Sensibilità, marcia nominale | Aggiunta all'ala ovest | Anticipi solo mattutini che raggiungono il 07:26 con 3 min a piedi e mantengono intervalli ≤60 min |
|---|---:|---|
| Nessuna sosta | 0 min | 3–8 min |
| 30 secondi per occorrenza | 7,5 min | Nessuno nel dominio 0–29 min |
| 60 secondi per occorrenza | 15 min | Nessuno nel dominio 0–29 min |

Con 30 secondi per occorrenza e anticipo di 10 minuti, l'ala ovest arriva circa alle **07:22:59**: dopo tre minuti pedonali resta circa **un secondo** prima del 07:26. L'intervallo massimo da/per FS nella transizione diventa **68,94 minuti**. Un anticipo di 8 minuti non raggiunge quel treno e produce già **66,94 minuti** di intervallo massimo.

Queste cifre non sono ritardi osservati né probabilità. Non dimostrano che ogni orario sia impossibile: confutano la robustezza della specifica famiglia con solo anticipo mattutino, altre partenze ferme e sfasamento est −15 minuti. Altre fasi, corse di raccordo o distribuzioni temporali non sono escluse da questo risultato.

## Metodo e risorse

Si riusa la griglia ingegneristica preesistente in `engineering_cycle_sensitivity`: fattori di marcia 0,9/1,0/1,1; soste 0/0,5/1 minuto; recuperi 5/10/15 minuti per ala. 27 sensibilità × 30 anticipi = **810 casi**. I tempi di salita ipotetici includono la sosta del nodo corrente; il recupero a FS viene applicato ai blocchi, non all'arrivo passeggeri in stazione.

I blocchi sono ricalcolati sui tempi comprensivi delle soste, non riutilizzati dal modello ottimistico. Nella sensibilità nominale con 30 secondi e recupero di cinque minuti, tre veicoli possono coprire le corse del modello, ma **avere abbastanza mezzi non corregge né la coincidenza né il buco di servizio**. Non si assume che quei tempi siano già misurati o calibrati.

I chilometri restano 109.285,990 annui prima degli extra: i problemi di orario non spariscono perché il conto chilometrico è entro il tetto. Soste e recuperi aumentano anche il tempo di lavoro; non equivalgono a costo operativo invariato.

## Stato della proposta

Il tracciato e la copertura potenziale restano una base progettuale; l'orario sotto 111.419 km **non è ancora una proposta operativa chiusa**. Non si confermano il 07:26, H30/H60 utile e tre mezzi come pacchetto affidabile sulla sola evidenza attuale.

Per la verifica finale occorrono un elenco reale di fermate/occorrenze, tempi di marcia e sosta osservati, manovre/trasferimenti a FS e deposito effettivo. Il modulo storico presente nel repo distingue correttamente orari programmati e osservazioni: l'uguaglianza arrivo/partenza in GTFS non autorizza soste reali nulle. Non si inventano dati per superare la verifica.

La prossima eventuale ricerca d'orario dovrà includere soste esplicite fin dall'inizio e confrontare insieme punta, transizione, sera e risorse. Gli 810 casi sono una diagnosi di questa famiglia, non una raccomandazione di taglio territoriale o serale.

Evidenza: `outputs/phase2/rt031_line8_local_shortcuts_v3/dwell_sensitivity.json`; script `scripts/phase2_audit_rt031_line8_dwell_sensitivity_v3.py`.

`observed_dwell_available=false`; `actual_timetable_certified=false`; `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
