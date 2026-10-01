# Linea 8: correzioni richieste dopo l'esame della mappa

La scheda condizionata da 27 siti e 17 giri resta un confronto, non una proposta approvata. Le osservazioni dell'utente del 1 ottobre 2026 riaprono l'idoneità del percorso e chiariscono che l'H30 desiderato era nei due sensi di percorrenza. Non si conferma l'orario precedente come conforme a questa aspettativa.

## Audit stradale eseguito

Sono stati verificati sei confronti sul grafo congelato, conservando i 27 siti, l'ordine degli eventi, i confini stradali a FS e due eventi locali distinti. I primi quattro conservano anche gli ingressi locali; due ulteriori confronti liberano gli ingressi locali. In questo dominio, liberare questi ingressi non cambia i risultati. Nessuna inversione immediata; soltanto restrizioni via-node rappresentate.

| Esclusione delle vie indicate dall'utente | Differenza per giro completo |
|---|---:|
| Via Mirasole | +337,203 m |
| Piazza San Zenone | +1.517,404 m |
| Via Cartiglio e Via Tessitura | +37,003 m |
| Tutte e tre le correzioni insieme | +1.891,610 m |

La seconda esclusione non elimina San Zeno/Via Cantù: conserva lo stesso nodo e i suoi due eventi. Il costo indica che questo accesso richiede un riesame del punto e del percorso, non l'adozione del giro lungo. Escludere solo nomi specifici NON garantisce il corridoio principale richiesto, né l'assenza di altre strade strette. Il confronto Mirasole comprende Via Gabriele D'Annunzio e Via Aldo Moro, ma la sequenza della rotonda indicata deve ancora essere verificata. Rimangono, fra l'altro, tratti denominati Via Privata Spluga nello snapshot: nessuna nuova idoneità autobus viene dichiarata.

Gli artefatti comprendono tutte le shape confrontate. Non hanno un orario ricalcolato. L'eventuale moltiplicazione della distanza per 17 giri e 260 giorni è solo aritmetica: non produzione certificata di un nuovo servizio.

## Scambio fra una fermata di Santa Maria e una di Calco

Confrontare separatamente l'omissione di S.Maria Hoè e quella di Via Como/Alpino, con un possibile nuovo punto nel centro abitato di Calco lungo il percorso corretto. Nessuna delle due omissioni e nessuna posizione nuova viene adottata.

Il confronto storico a 29 siti mostra, per la sola omissione di Alpino, 2,843 punti di perdita comunale a 5 minuti a Santa Maria Hoè; per S.Maria Hoè 7,581 punti. NON sono perdite già ricalcolate sull'attuale esempio da 27 siti o sullo scambio con Calco. Occorre il conteggio congiunto sulla matrice pedonale e sul nuovo punto: vicinanza fra fermate e parità di numero non provano equivalenza territoriale.

## Ferrovia: quattro flussi, non solo due

Il nuovo audit nominale comprende ogni treno congelato e ogni ala: bus verso Milano, bus verso Lecco, arrivi da Milano verso bus e arrivi da Lecco verso bus. I rientri da Milano erano già nel modello; i treni diretti a Lecco sono proprio quelli provenienti da Milano. L'audit non confonde destinazione del treno e provenienza del passeggero.

Esempi degli arrivi da Lecco nell'orario ARCHIVIATO del 3 settembre 2026, con cammino assunto di 3 minuti:

| Arrivo da Lecco | Prossima partenza est | Prossima partenza ovest |
|---|---|---|
| 16:25 | 16:40 (15 min) | 17:00 (35 min) |
| 16:55 | 17:10 (15 min) | 17:00 (5 min) |
| 17:25 | 17:40 (15 min) | 17:35 (10 min) |
| 17:55 | 18:10 (15 min) | 18:05 (10 min) |

Il registro pubblica anche le attese lunghe e l'assenza di un evento successivo. Il test ereditato 3–8 minuti è esposto come assunzione, non una nuova soglia scelta dall'utente. Nessuna probabilità empirica, ponderazione OD o verifica di un orario ferroviario odierno. Questo è un audit dell'orario precedente, NON un orario per le correzioni stradali.

## Chiarimento di servizio

H30 nei due sensi significa una corsa ogni 30 minuti in ciascun senso, non una somma dei due sensi che dà un passaggio ogni 30 minuti. L'esempio est→ovest opera un solo senso delle ali; FS→fermata e fermata→FS non sono la prova di servizio orario e antiorario.

Servono una ricostruzione diretta indipendente dell'altro senso, gli eventi di fermata appropriati, una verifica di manovre e accosti e un confronto d'orario/risorse. Invertire un elenco di coordinate non basta. Duplicare tutte le corse con percorsi di pari lunghezza raddoppierebbe i km commerciali, non necessariamente il costo totale; l'H30 bidirezionale soltanto nelle punte non equivale a duplicare tutto il giorno. Nessuna delle espansioni viene adottata in questo audit.

L'utente accetta le soste a FS in linea di principio; non ha indicato una durata massima né autorizzato la perdita di continuità a bordo. Non si elimina la verifica ferroviaria per ottenere un esito positivo.

## Fonti e stato

- [Revisione machine-readable](../config/rt031_caller_street_and_rail_revision_v3.json).
- [Sei confronti stradali](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_street_exclusions.json) e [shape GeoJSON](../outputs/phase2/rt031_line8_local_shortcuts_v3/caller_street_exclusions.geojson).
- [148 righe ala/treno, entrambi i flussi](../outputs/phase2/rt031_line8_local_shortcuts_v3/conditional_four_rail_flows_nominal.json).
- [Fonte delle perdite storiche](../outputs/phase2/rt031_line8_local_shortcuts_v3/paired_cuts_fixed_order.json.gz).

`network_selected=false`, `primary_selection_authorised=false`, `runner_up_selection_authorised=false`, `decision_budget_km=null`, `uncertainty_band_min=null`. La mappa interattiva precedente mostra ancora il confronto originario, non questi bypass.
