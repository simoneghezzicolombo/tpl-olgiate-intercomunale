# Linea 8: quadro ferroviario verificato e lavoro residuo sull'orario

**Aggiornamento successivo:** disponibile [una proposta verificata a 16 giri](RT031_LINEA8_PROPOSTA_ORARIO_16_GIRI_V3.md), 112.834 km/anno nel confronto a 260 giorni, con transizione della morbida fino alle 16:20 da confermare dal chiamante. Il confronto da 17 giri sotto resta una diagnosi storica, non l'orario della nuova scheda.

## Questione territoriale chiusa per il progetto

Il chiamante ha accettato **Calco Centro – Municipio in Via Italia**, al punto `45.7250958, 9.4180371`: si mantiene Santa Maria Hoè e si omette Via Como/Alpino. Una sola nuova fermata Calco, non dieci alternative simultanee. Inserita una sola occorrenza esplicita nel percorso est, tra gli archi effettivi del grafo.

**27 siti di progetto inclusa FS, 28 eventi non-FS per giro, percorso completo 27,123508 km.** Mirasole e Cartiglio/Tessitura esclusi nel modello; Piazza San Zenone mantenuta. Olgiate sud e San Zeno restano esigenze distinte. Una sola Linea 8 completa; nessuna seconda linea introdotta. Questo chiude la scelta di progetto dello scambio, NON la sicurezza della palina, l'accosto, le manovre o la legalità a storia completa.

## Tutti i treni, senza filtro S8

Scaricati il 1 ottobre 2026:

- [GTFS ufficiale regionale](https://dati.lombardia.it/download/3z4k-mxz9/application%2Fzip), con calendari ed eccezioni applicati alla data **2026-10-01**.
- [Quadro RFI completo 00–24 di Olgiate-Calco-Brivio](https://prm.rfi.it/qo_prm/QO_Partenze_SiPMR.aspx?Id=1805&alle=23.59&dalle=00.00&guid=&ora=00.00), validità dichiarata **14 giugno–12 dicembre 2026**.

L'estrazione comprende TUTTE le route chiamanti alla stazione e alle eventuali piattaforme figlie. Per questa data risultano **74 chiamate, 37 verso Milano e 37 verso Lecco, tutte S8**. Corrispondenza esatta con RFI per numero treno e orario di PARTENZA in stazione: nessuna chiamata extra da un lato o dall'altro. I riferimenti al RE 2811 nel precedente quadro RFI dicembre 2025–giugno 2026 NON sono importati come orari attuali.

Non confondere arrivo e partenza:

| Flusso | Cadenza prevalente da usare |
|---|---|
| Bus → treno verso Milano | Partenza treno ai minuti **:26 / :56** |
| Treno proveniente da Lecco → bus | Arrivo in stazione ai minuti **:25 / :55** |
| Bus → treno verso Lecco | Partenza treno ai minuti **:03 / :33** |
| Treno proveniente da Milano → bus | Arrivo in stazione ai minuti **:02 / :32** |

La cadenza non sostituisce il registro dei treni effettivi: primi/ultimi servizi e giorni festivi differiscono. Controlli di calendario: 1/2/3/5 ottobre **74**, domenica 4 ottobre **38** chiamate. Non viene adottato un calendario annuale della linea bus.

Il treno finale con partenza GTFS **24:03** conserva il suo tempo di servizio oltre mezzanotte; il confronto con il quadro RFI alle **00:03** usa soltanto l'orologio modulo 24 ore, non lo sposta all'inizio della giornata del modello. Disponibilità real-time, cancellazioni e ritardi non verificati.

## Coincidenze ricalcolate sul percorso corretto

Registro completo: **148 righe ala/treno**, ciascuna con bus→treno e treno→bus: 296 coppie di flusso. Le ali sono due sezioni della STESSA corsa completa, non linee separate. Ogni riga contiene arrivo/partenza del treno, vera origine/destinazione, successiva partenza bus, ultimo arrivo bus compatibile e attesa esplicita, anche quando lunga o assente.

Il vecchio esempio a **17 giri** serve SOLO come diagnosi del problema. Il numero ricevuto dal chiamante resta **16 giri**: nessun diciassettesimo giro o nuovo orario è adottato automaticamente. I tempi del percorso sono ricalcolati, non trapiantati dal vecchio tracciato: con le ipotesi ereditate (marcia ×1,1, dwell 0,5 minuti per evento) est **40,78 minuti**, ovest **38,30 minuti**. Il trasferimento FS di 3 minuti è un'ipotesi preesistente, non una misura osservata o un nuovo vincolo dichiarato dal chiamante.

Diagnosi del vecchio esempio, non prestazioni della proposta finale:

| Arrivi ferroviari nella finestra di lettura 16–20 | Attesa per l'ala est | Attesa per l'ala ovest |
|---|---:|---:|
| Provenienti da Milano, diretti a Lecco | **8–38 min** | **3–58 min** |
| Provenienti da Lecco, diretti a Milano | **15–45 min**, un arrivo senza bus successivo | **5–35 min** |

Anche le partenze mattutine sono enumerate in entrambe le direzioni; il JSON conserva quelle prive di bus utile, senza sostituire il dato con zero minuti. Una coincidenza soltanto nominalmente possibile non viene presentata come utile o robusta.

Per bus→treno si verifica lo STESSO bus scelto nominalmente nei nove casi di marcia/dwell ereditati, non un bus diverso in ciascuno scenario. Nessuna quota di casi favorevoli viene trasformata in probabilità. Nessuna domanda OD, miglioramento GJT demand-weighted o priorità ferroviaria inventata.

## Primo miglioramento concreto senza nuovi km

Confronto non adottato sul medesimo esempio: anticipare di **3 minuti solo le cinque partenze est della punta serale**, mantenendo ferme le partenze ovest della stessa corsa completa.

| Treno da Milano arriva | Partenza est prima | Partenza est confrontata | Attesa prima → dopo |
|---|---|---|---|
| 16:02 | 16:10 | 16:07 | 8 → 5 min |
| 16:32 | 16:40 | 16:37 | 8 → 5 min |
| 17:02 | 17:10 | 17:07 | 8 → 5 min |
| 17:32 | 17:40 | 17:37 | 8 → 5 min |
| 18:02 | 18:10 | 18:07 | 8 → 5 min |

Sono ancora cinque partenze a distanza di 30 minuti. **Zero metri di servizio aggiunti**, partenze ovest immutate; la sosta intermedia a FS si ALLUNGA di 3 minuti per ciascuna corsa interessata. Non si cambia strada, non si crea una corsa corta o inversa, non si raddoppia il servizio. Questo esempio NON risolve automaticamente le altre coincidenze: l'arrivo bus verso altri treni cambia e i viaggi intercomunali devono essere riverificati. Non è un orario pubblico né la selezione del servizio a 16 giri.

## Cosa resta, senza riaprire la geometria

Si può ora lavorare sull'orario a **16 giri completi**, tenendo il tracciato e gli eventi appena fissati. Il confronto deve usare il registro ferroviario corrente completo, salvaguardare H30 in punta e mostrare separatamente le attese dei quattro flussi e i buchi della morbida; nessuna falsa promessa di servire ogni singolo treno in pochi minuti. Il confronto da 17 giri non viene rinominato da 16. H30 nei due sensi resta rinviato dal chiamante.

Non è ancora chiuso l'orario finale: la diagnosi di tutte le chiamate è chiusa, non le garanzie di esercizio. Budget decisionale e uncertainty band restano input del chiamante; nessuno viene scelto qui.

## Evidenze e riproduzione

- [Posizione Calco adottata ed eventi corretti](../outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.json), [GeoJSON](../outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.geojson).
- [Tutte le chiamate datate, fonti SHA256 e riconciliazione RFI](../outputs/phase2/rt031_line8_local_shortcuts_v3/all_station_rail_20261001.json).
- [Tutti i flussi e confronto serale](../outputs/phase2/rt031_line8_local_shortcuts_v3/current_rail_connections_corrected_design.json).

```powershell
python -m scripts.phase2_adopt_rt031_line8_calco_stop_v3 --graph_dir C:/Users/sim11/AppData/Local/Temp/rt031-boundary-audit
python -m scripts.phase2_audit_rt031_all_station_rail_v3
python -m scripts.phase2_audit_rt031_line8_current_rail_connections_v3
```

Il comando ferroviario legge il cache datato e la sua metadata di acquisizione; `--fetch` richiede nuovamente le fonti ufficiali, senza toccare il vecchio cache S8 del 27 settembre. La riproduzione dipende dalla disponibilità dei cache dichiarati; i registri generati conservano hash e risultati verificabili.

`network_selected=false`, `primary_selection_authorised=false`, `runner_up_selection_authorised=false`, `decision_budget_km=null`, `uncertainty_band_min=null`.
