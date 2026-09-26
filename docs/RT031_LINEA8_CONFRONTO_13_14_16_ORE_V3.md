# Linea 8: confronto 13, 14 e 16 ore, senza perdita delle identità del riferimento

## Risultato e limite decisionale

Su richiesta dell'utente si confrontano anche 13 e 14 ore: nessuna fascia viene adottata automaticamente.
Il nuovo cammino stradale conserva tutte le 25 identità di fermata del riferimento in entrambi gli orientamenti e incontra anche Vaccarezza. Include i punti ipotetici Olgiate sud e San Zeno/Via Cantù, come esigenze separate, rispettivamente nelle ali ovest ed est.
Non costituisce un elenco di 28 fermate approvate: 26 sono identità incontrate presso i nodi del grafo; due sono esigenze di nuovi siti. Mancano eventi direzionali di salita/discesa approvati.

La coppia di percorsi misura 49,679290 km: 24,517347 km nell'orientamento A e 25,161943 km nel B. Il riferimento più veloce misurava 50,918670 km per coppia. Risparmio stradale circa 2,43%, senza perdita di identità. Non è dimostrato l'ottimo globale: ordine ottimizzato sul rilassamento a tratti indipendenti, poi cammino minimo contestuale per quell'ordine.

## Confronto di volume, non orario certificato

Assunzioni esplorative comuni: 260 giorni/anno, quattro ore di punta a due giri completi/ora complessivi, una corsa/ora nel resto; entrambi gli orientamenti equipartiti nell'anno. Il tetto proviene dal contratto di politica esistente (111.419 km/anno).

| Fascia | Giri completi complessivi/giorno | Km annui prima degli extra | Residuo sul tetto |
|---|---:|---:|---:|
| 13 ore | 17 | 109.791,231 | +1.627,769 |
| 14 ore | 18 | 116.249,539 | −4.830,539 |
| 16 ore | 20 | 129.166,154 | −17.747,154 |

**Questi volumi NON dimostrano H30 in punta/H60 nel resto per ogni direzione o viaggio utile verso FS.** Alternare gli orientamenti può raddoppiare l'attesa direzionale; attraversare FS due volte non equivale a una frequenza utile doppia. A 13 ore, 17 giri richiedono inoltre un'allocazione 9/8 e 8/9 fra giorni per ottenere le distanze medie indicate. Orari di prima/ultima corsa, sequenze di servizio e stabilità del calendario non sono risolti.

Il margine di 13 ore è appena 6,261 km/giorno per deposito e altri extra. Non è un bilancio operativo chiuso. Tempi stradali di circa 51,20 e 52,36 minuti, esclusi fermate e recuperi; flotta e robustezza non certificate. Il confronto non decide quali ore eliminare né modifica weekend o giorni annui.

## Copertura potenziale condizionata

Stesso substrato pedonale e pesi di popolazione del riferimento; ipotizza utilizzabili tutti i siti e le due nuove esigenze. Non è domanda osservata né garanzia di viaggio.

| Comune | Popolazione modellata entro 10 minuti a piedi | Delta sul riferimento, punti percentuali |
|---|---:|---:|
| Brivio | 89,09% | +7,21 |
| Calco | 68,21% | 0 |
| Olgiate Molgora | 84,56% | 0 |
| Santa Maria Hoè | 95,75% | 0 |
| La Valletta Brianza | 67,85% | 0 |
| Totale | 79,16% | +1,37 |

Nessun peggioramento anche alle soglie 5 e 8 minuti. La conservazione delle identità è un confronto specifico, non un nuovo vincolo per ogni ricerca futura.

## Controlli e cosa resta da chiudere

La ricerca conserva il nodo corrente, l'arco entrante e il progresso dei waypoint: la memoria di svolta non si azzera alle fermate né al passaggio intermedio in FS. Il test sintetico respinge il raccordo vietato che unisce due tratti singolarmente validi. Nessuna sovrapposizione con i due via-way noti nel certificato successor; questo NON certifica la completezza delle restrizioni storiche o l'idoneità autobus. Non si certifica nemmeno il raccordo fra giri successivi in FS.

Sono inoltre confrontati tutti i 10 siti convenzionali route-ready dell'inventario Brivio, con tre cammini ciascuno e due comparatori: 32 risultati, uno scartato per svolta vietata. La frontiera sui 31 validi conserva chilometri, tempi direzionali, accessibilità di ogni comune a 5/8/10 minuti e inclusione delle identità; nessun peso o vincitore.

Il passo necessario è trasformare questa geometria in sequenze direzionali di fermata e un orario verso FS, esplicitando H30/H60 utile, recuperi e raccordi fra corse; poi aggiungere i km effettivi di deposito. Solo così si può stabilire se lo scenario 13 ore è davvero esercibile entro il tetto, o quanta ulteriore riduzione serve.

Artefatti: `outputs/phase2/rt031_line8_local_shortcuts_v3/full_retention_context.json`, `.geojson`, `.png`; `brivio_existing_sites.json`; `brivio_existing_sites_walk.json`. Gli hash upstream sono nei JSON. Mappa statica tratta dalla geometria del grafo, non disegnata a mano.

`network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`; `decision_budget_km=null`; `uncertainty_band_min=null`.
