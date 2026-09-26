# RT031 — Mappa dell'esperienza pregressa

Questa è una **mappa di lettura**, non un nuovo modello o una nuova decisione.
Prima di presentare una variante come migliore, riusare le fonti qui sotto
e distinguere principio, ipotesi, evidenza certificata e lacuna.

| Filone già esplorato | Fonte | Cosa resta valido | Cosa non si può promuovere a fatto |
| --- | --- | --- | --- |
| Utilità del servizio, frequenza/span, cadenzamento, S8, affidabilità, direttezza, fermate, semplicità, equità | [Best practice Phase 2](PHASE2_TRANSIT_BEST_PRACTICES.md), BP-01–BP-12 | Riferimento normativo di progetto; non basta massimizzare copertura pedonale o minimizzare km | I pesi della GJT o una probabilità empirica di coincidenza persa non sono osservati per RT031 |
| Otto con Olgiate FS come cerniera, ovest/est e due versi | [Concept originario](02_concetto_linea_8_e_nodo_olgiate.md), [CW/CCW](03_modello_circolare_doppio_verso_merate.md) | Ipotesi topologica seria; il doppio verso nasce proprio per evitare il giro lungo verso/da FS | 55 minuti/ciclo, 5 minuti di recupero, 112.261 km/anno e coincidenze «perfette» non sono prestazioni certificate della linea oggi candidata |
| Domanda di progetto e famiglie alternative | [Specifica Phase 2](PHASE2_SERVICE_DESIGN_SPEC.md) | Valutare intero viaggio, orario e alternative non-8 sullo stesso substrato | La vecchia clausola di scelta basata su GJT non autorizza a fabbricare OD spazializzata o GJT mancante |
| Stop-pattern e ricerca | [Audit RT-006](PHASE2_NETWORK_DESIGN_CODE_AUDIT_V3.md) | Corridoio, fermate passeggeri, orario e instradamento sono oggetti distinti; riuso fermate esistenti, nuove fermate da verificare | Quattro vecchi finalisti e seed EAST/WEST non diventano soluzioni solo perché instradabili |
| Audit delle prime raccomandazioni | [Gate F](GATE_F_PASS.md) | FIG8 rimane nell'inventario dei concept, non è bocciata | Gli output legacy hardcoded e gli scenari iniziali non certificano una topologia vincente |
| Sufficienza per decisione finale | [Gate V3](PHASE2_FINAL_DECISION_SUFFICIENCY_GATE_V3.md), [audit torneo](PHASE2_TOURNAMENT_CONTRACT_AUDIT_AND_NONDECISIONAL_FRONTIER_RT001_V3.md) | V3 può confrontare solo metriche supportate, con robustezza ingegneristica deterministica | Né OD comunale non disaggregata, né miss deterministici sono GJT per passeggero o probabilità empiriche; budget e banda restano del decisore |
| Esplorazione RT031 recente | [Trade-off Arlate/Rovagnate](RT031_ARLATE_ROVAGNATE_TRADEOFF_V3.md), [audit macchina](../outputs/phase2/rt031_arlate_rovagnate_convergence_v3/convergence_audit_v3.json) | Sette linee singole non dominate nel pool; copertura pedonale 5/8/10 minuti, km e retention confrontabili | La maggiore copertura di un percorso non dimostra frequenza, tempo frazione→FS, continuità al nodo o superiorità dell'8 |
| Figura a otto con cerniera FS verificata | [Diagnostica fisica e accesso](RT031_HUB_SPLIT_FIG8_DIAGNOSTIC_V3.md) | Percorsi fisici legali nei due versi e accesso pedonale dei pattern tipizzati; Via Statale migliora Olgiate | Identità di linea dichiarata non equivale a servizio congiunto orariato, né a copertura delle frazioni senza fermata identificata |
| Preferenza attuale del committente | [Sequenza e intenti](../config/rt031_caller_locality_itinerary_preference_v3.json) | Un'unica linea riconoscibile, 8 ovest/est come ipotesi preferita, Olgiate prioritaria, frazioni e servizio affidabile/frequente | Non è un percorso fisico certificato, un peso numerico, un budget, una selezione PRIMARY o RUNNER-UP |

## Regola di riuso per il prossimo confronto

Non riaprire la discussione sui principi già codificati. Verificare invece,
per la figura 8 e le alternative comparabili, **eventi ordinati nei due versi,
tempo frazione→FS e ritorno, passaggio/continuità a FS, orario cadenzato e span,
buffer/dwell/flotta, accesso nei cinque comuni e stato fisico delle fermate**.
Usare solo misure effettivamente prodotte; ciò che manca resta `UNRESOLVED`.
Il confronto non autorizza da solo la selezione di una rete.
