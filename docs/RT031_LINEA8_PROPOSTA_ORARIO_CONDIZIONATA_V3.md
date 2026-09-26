# Linea 8 — proposta tecnica d'orario condizionata, non selezionata

## Cosa abbiamo finalmente costruito

Un esempio completo di partenze e blocchi su entrambe le ali che incorpora **30 secondi per ogni occorrenza di fermata ipotizzata e +10% sul tempo di marcia**. Non è più il calendario a soste zero. Mantiene la geometria e le identità incontrate, senza tagli territoriali, e totalizza **109.285,990 km/anno** su 260 giorni ipotetici, prima degli extra.

L'esempio è un testimone di fattibilità nel modello, **non il migliore selezionato**. La ricerca comprende per ogni ala tutte le 900 coppie di anticipo mattutino/resto giornata fra 0 e 29 minuti. Con soste di mezzo minuto risultano 66 coppie per l'ovest e 91 per l'est che rispettano i confini ferroviari e il limite ottimistico di 60 minuti. Nessun punteggio aggregato o preferenza normativa determina un vincitore.

## Orario esemplificativo da FS, uguale per le due ali

| Partenze | Orientamento |
|---|---|
| 06:42, 07:12, 07:42, 08:12 | Ovest A, est B: favorisce Olgiate sud/San Zeno verso FS |
| 08:40, 09:40, 10:40, 11:40, 12:40, 13:40, 14:40, 15:40 | Ovest B, est A |
| 16:40, 17:10, 17:40, 18:10 | Ovest B, est A |
| 18:40 | Ovest B, est A |

Sono **17 corse per ala**, 34 giri d'ala complessivi. Rimane un concept di linea pubblica unica; la continuità passeggeri fra le ali a FS non è garantita dal fatto di utilizzare lo stesso marchio o veicolo.

**Le punte sono anticipate rispetto al riferimento 07–09/17–19. Non affermiamo che questo orario soddisfi H30 in tutte quelle ore per ogni fermata.** Mantiene i gruppi di partenze a 30 minuti e non produce intervalli ottimistici da/per FS superiori a 60 minuti, sotto le ipotesi descritte. Il consenso su fasce e promessa di servizio resta necessario; la proposta non è adottata automaticamente.

## Coincidenze e risorse del modello

- Prime corse in FS circa **07:17:31 ovest e 07:17:28 est**. Con tre minuti a piedi, margine residuo circa **5,5 minuti** prima del treno campione delle **07:26 per Milano**.
- Ultima partenza alle **18:40**: compatibile nel modello con il treno campione **da Milano** in arrivo alle **18:32**, lasciando cinque minuti dopo il trasferimento pedonale ipotizzato.
- **Quattro veicoli** nella copertura minima delle corse con 5, 10 o 15 minuti di recupero aggiuntivo a ogni ala. Il conto comprende le soste e il rallentamento dichiarati; non comprende deposito, turni autisti o manovre reali non rappresentate.
- Residuo chilometrico **2.133,010 km/anno**, cioè **8,204 km/giorno**. Senza il deposito effettivo non sappiamo se basti. Quattro mezzi possono incidere sui costi anche senza maggiori km.

I treni sono quelli congelati del **3 settembre 2026**, non un aggiornamento del servizio odierno. L'esempio è riproducibile in `joint_phases.json` con partenze, archi upstream e blocchi. I margini non sono probabilità di coincidenza né certificazioni di robustezza.

## Confronto con orientamento costante

Sono state verificate anche le quattro ali mantenute nello stesso senso tutto il giorno. Esistono fasi che rispettano i medesimi confini ferroviari nel modello e nessuna identità ipotetica viene persa rispetto ai due orientamenti dell'ala. Questo evita il cambio di senso, ma mantiene per alcuni luoghi tempi ipotetici verso FS di circa **31–33 minuti** con le soste e il rallentamento. Non viene dichiarata equivalenza passeggeri solo perché la copertura geografica è conservata.

I costi delle ali sono registrati separatamente: una combinazione a senso costante non eredita automaticamente il costo della proposta variabile. Non viene selezionata una coppia per sola semplicità.

## Condizioni che impediscono ancora una proposta approvata

Con **un minuto per occorrenza e +10% di marcia**, nessuna coppia di anticipi esaminata sull'ala ovest soddisfa insieme i confini ferroviari e gli intervalli massimi di 60 minuti. Il testimone da mezzo minuto non può quindi essere chiamato robusto sull'intera griglia precedente.

Occorrono: conferma delle fasce di punta, fermate/occorrenze effettivamente servibili, tempi osservati che verifichino l'ipotesi di sosta, idoneità autobus e restrizioni complete, verifica dell'orario ferroviario applicabile e km di deposito. Non cambiamo cap né introduciamo pesi per aggirare questi punti.

La conclusione progettuale è concreta ma condizionata: **geometria inclusiva + 17 corse per ala + orario ricalcolato insieme alle soste può stare nel conto dei km; richiede quattro mezzi nell'esempio e una modifica dichiarata delle fasce.** Se tali condizioni non sono accettabili, questo esempio non è la soluzione richiesta.

`actual_timetable_certified=false`; `requested_peak_windows_certified=false`; `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
