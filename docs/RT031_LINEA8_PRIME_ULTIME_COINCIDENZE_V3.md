# Linea 8: prime e ultime coincidenze sul giorno ferroviario congelato

## Fonte e confini

Confronto con i 74 eventi S8 del **3 settembre 2026** già nel repository (`outputs/phase2/s8_events.csv`, contratto `s8_interchange_contract.json`). La fonte originaria è il GTFS ufficiale indicato dal contratto, ma in questo audit non viene riscaricato. **Non è una verifica dell'orario ferroviario vigente oggi.**

Si usano separatamente le tre ipotesi di trasferimento pedonale esistenti (1,5/2/3 minuti). Non si adotta lo score storico del contratto, non si calcolano probabilità o pesi passeggeri. Ogni abbinamento richiede `arrivo bus + cammino <= partenza treno`, oppure `arrivo treno + cammino <= partenza bus`. Un abbinamento con attesa lunga non diventa una buona coincidenza per definizione.

## Il problema trovato e il miglioramento possibile

Nel calendario base da **109.285,990 km/anno**, l'ala ovest partita alle 07 arriva in FS circa alle 07:25:29. Il treno verso Milano delle **07:26 non è raggiungibile neppure con l'ipotesi pedonale più favorevole**: il primo raggiungibile nel modello è quello delle 07:56. L'ala est anticipata di 15 minuti arriva invece circa alle 07:11 e può raggiungere il 07:26.

Sono confrontati 180 casi: tre calendari, trenta anticipi interi di 0–29 minuti, applicati a tutta la giornata oppure solo alle corse mattutine. Si mantiene lo sfasamento est −15 minuti. Nessuna fase è selezionata.

Per il calendario base, anticipare **solo le corse mattutine di 3–8 minuti** consente contemporaneamente nel modello:

- prima coincidenza dell'ala ovest con il **07:26 per Milano**, anche assumendo tre minuti pedonali;
- nessun intervallo ottimistico da/per FS superiore a 60 minuti;
- ultime partenze invariate: **19:00 ovest e 18:45 est**;
- chilometri invariati e tre mezzi nel modello con 5/10/15 minuti aggiuntivi per giro d'ala.

Il margine residuo prima di quel treno varia però soltanto da **0,524 a 5,524 minuti**, da destinare a tutte le soste e agli scostamenti rispetto al tempo stradale. Non è una coincidenza robusta certificata. Anticipi di 10 minuti migliorano il margine ma producono già un intervallo massimo di circa **61,94 minuti** nella transizione mattutina; quindi non si nasconde il costo dell'anticipo.

## Cosa succede alla sera e alla prima mattina

Nel caso base con anticipo soltanto mattutino, il modello con tre minuti pedonali conserva l'ultimo treno **in arrivo da Milano** (direzione ferroviaria LECCO) delle **18:32** con proseguimento su entrambe le ali. I treni successivi in arrivo da Milano non hanno un bus successivo in questo calendario. È un limite concreto dell'ampiezza del servizio.

Il calendario che sposta le ultime corse al mattino può invece raggiungere, con anticipi mattutini analoghi, il **06:56 per Milano**, ma l'ultimo arrivo **da Milano** con proseguimento torna alle **18:02**. Costa **109.398,265 km/anno** prima degli extra. Non viene adottato: il miglioramento del mattino è pagato con la sera.

Aggiungere le corse del mattino mantenendo la sera costa **115.800,435 km/anno**, oltre il cap prima ancora del deposito. L'anticipo di pochi minuti non risolve da solo questa differenza.

## Deposito e dati ancora necessari

Nella ricerca mirata in `data` e `config` non è emerso un input georeferenziato di deposito utilizzabile da questo audit. Il residuo del calendario base resta **2.133,010 km/anno (8,204 km/giorno)**: non si assume che basti né si pone a zero il riposizionamento. Servono deposito/uscite-rientri effettivi e tempi di fermata per chiudere il conto operativo.

Le corse e le coincidenze restano ipotetiche: salita/discesa nelle occorrenze, siti nuovi, idoneità del bus, restrizioni complete, continuità passeggeri a FS e orario attuale richiedono verifica. Le fasce locali possono spostarsi con l'anticipo: non si certifica H30 nell'intera punta 07–09 per ogni luogo.

## Evidenza riproducibile

`outputs/phase2/rt031_line8_local_shortcuts_v3/rail_boundaries.json` conserva hash, partenze, blocchi condizionali, massimo intervallo con eventi testimoni, prime/ultime coincidenze per ala e direzione, profili pedonali separati, attese massime e conteggi senza proseguimento. Non si aggregano questi conteggi in probabilità.

`actual_timetable_certified=false`; `empirical_probability_computed=false`; `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
