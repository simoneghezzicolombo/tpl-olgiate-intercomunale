# Linea 8: partenze delle ali e blocchi veicolo condizionali

## Passo concreto

La separazione delle partenze a FS non richiede due nomi di linea né strade nuove. È un confronto operativo interno alla Linea 8, non una continuità passeggeri automaticamente garantita fra le ali.

Abbiamo scomposto i cammini nei quattro giri FS–ala–FS e verificato nove combinazioni: tre calendari di partenze, ciascuno con ala est anticipata di 15 minuti, simultanea o posticipata di 15. È una griglia dichiarata di confronto, non l'ottimo assoluto né una fase selezionata rispetto ai treni.

## Mattino, sera e chilometri

| Calendario di confronto | Km/anno prima degli extra | Residuo entro 111.419 |
|---|---:|---:|
| 17 corse per ala, riferimento ovest 07–19 | 109.285,990 | 2.133,010 |
| Aggiunta di una corsa mattutina per entrambe le ali | 115.800,435 | −4.381,435 |
| Ultima corsa delle 19 spostata alle 06:30 su entrambe le ali | 109.398,265 | 2.020,735 |

260 giorni ipotetici; i tre sfasamenti dell'ala est non cambiano questi km. Spostare l'ultima corsa modifica leggermente la distanza perché cambia anche l'orientamento. Nessun extra di deposito è imputato a zero come fatto operativo.

Con l'ala est anticipata di 15 minuti, il primo scenario produce le seguenti **prime opportunità geometriche**, senza soste:

- Olgiate sud → FS: salita circa **07:22**, arrivo FS circa **07:25**.
- San Zeno → FS: salita circa **07:09**, arrivo FS circa **07:11**. Il precedente giro completo sequenziale dava salita circa 07:49: l'anticipo è di circa 40 minuti, senza km aggiuntivi.

Spostando invece le ultime corse al mattino, le prime opportunità diventano circa **06:52 da Olgiate sud e 06:39 da San Zeno**; gli ultimi giri partono però da FS alle **18:30 sull'ala ovest e 18:15 sull'est**. È un taglio serale esplicito, non una soluzione che conserva tutti gli orari. Non viene adottato automaticamente.

Le cadenze ripetono 30 minuti in punta e 60 in morbida nelle rispettive griglie di partenza, ma lo sfasamento sposta anche i confini delle punte. Non si certifica H30 locale per l'intera fascia 07–09/17–19, né la coincidenza con un treno. Le fermate/lati devono essere validati; ogni occorrenza conserva la propria identità.

## Mezzi: il risultato non dipende soltanto dai km

Le ali richiedono circa 25,48–26,34 minuti stradali. In un ciclo di 30 minuti restano quindi soltanto **3,66–4,52 minuti per tutte le soste e gli altri tempi aggiuntivi**.

Abbiamo costruito blocchi mediante copertura minima esatta del grafo aciclico dei collegamenti fra corse: tutte iniziano e finiscono in FS; un collegamento richiede tempo sufficiente e svolta consentita dalle restrizioni via-node rappresentate. Ogni blocco viene rigiocato nei test. È una soluzione esatta per quel modello, non per l'esercizio reale.

| Tempo aggiuntivo ipotetico per ogni giro d'ala | Partenze simultanee | Est sfalsata di ±15 minuti |
|---|---:|---:|
| 0 minuti, limite ottimistico | 2 mezzi | 2 mezzi |
| 5 minuti | 4 mezzi | 3 mezzi |
| 10 minuti | 4 mezzi | 3 mezzi |
| 15 minuti | 4 mezzi | 3 mezzi |

I valori 5/10/15 provengono dalla sensibilità già dichiarata nel repository; qui sono applicati **a ogni ala**, non una volta all'intero otto. Non sono misure osservate di sosta/recupero. Le opportunità passeggeri restano calcolate a soste zero: questi blocchi non aggiornano ancora gli orari intermedi. Autisti, deposito, manovre reali, restrizioni complete e coincidenze non sono certificati.

## Cosa si può concludere

Le partenze separate e sfalsate meritano la verifica operativa: anticipano l'ala est a km invariati ed evitano il picco di quattro mezzi nel modello con margini aggiuntivi. Ma **non promettiamo due mezzi affidabili**, né risolviamo la prima mattina di tutta la rete con il solo anticipo dell'est.

Per conservare anche una corsa più precoce su entrambe le ali senza rinunciare alla sera, questo dominio supera il tetto di circa 4.381 km prima degli extra. Il trade-off ora è quantificato: anticipare rinunciando all'ultima corsa, oppure trovare ulteriore risparmio/copertura finanziaria. Il residuo del caso base è 8,204 km/giorno, quello con spostamento 7,772; il deposito effettivo può assorbirli.

Nessuno dei nove casi è selezionato. La geometria e le identità incontrate non sono cambiate; il conteggio non trasforma un passaggio sul grafo in fermata autorizzata.

## Artefatti

`outputs/phase2/rt031_line8_local_shortcuts_v3/independent_wings.json` contiene hash upstream, archi di ciascuna ala, occorrenze, nove calendari, opportunità da/per FS, giunzioni e blocchi riproducibili.
Script: `scripts/phase2_audit_rt031_line8_independent_wings_v3.py`.

`network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
