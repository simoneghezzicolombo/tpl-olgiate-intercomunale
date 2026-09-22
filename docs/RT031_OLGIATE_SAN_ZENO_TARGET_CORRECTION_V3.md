# RT031 — Centro sportivo di Olgiate e San Zeno/Via Cantù

**Correzione del committente, 22 settembre 2026.** La copertura debole di
Olgiate nelle quattro [prove della figura a otto](RT031_HUB_SPLIT_FIG8_DIAGNOSTIC_V3.md)
non va interpretata come prova che Olgiate sia poco servibile: quelle prove
non hanno richiesto una fermata nella zona residenziale del centro sportivo
né a San Zeno. La nuova preferenza di progetto è cercare un unico servizio
riconoscibile che tocchi anche questi due corridoi, conservando il confronto
con alternative non-8. Non è un filtro di ammissibilità globale né un peso
numerico inventato.

| Luogo | Evidenza localizzativa | Cosa è ancora da provare |
| --- | --- | --- |
| Centro sportivo comunale | Il [Comune](https://www.comune.olgiatemolgora.lc.it/Vivere-il-comune/Eventi/COLORUN-2026) lo colloca in Via Aldo Moro; il vecchio `data/processed/poi_dataset.csv` dà una coordinata approssimata 45.7345, 9.3980 | Identità esatta dell'eventuale fermata, lato strada, accesso pedonale senza barriere, idoneità e continuità di percorso |
| «Oratorio» di Olgiate | La denominazione non identifica da sola quale edificio/intorno il committente intenda | Identità del luogo e del punto di salita: non equiparare automaticamente oratorio, centro sportivo e San Zeno |
| San Zeno / Via Cesare Cantù | L'ancora di progetto `SAN_ZENO` in `data/phase2/frozen_gate_d/source/structural_anchor_evidence.csv` è in Piazza San Zenone, 45.735223, 9.407099, con stato `ASSUMPTION`; il grafo OSM contiene Via Cesare Cantù (`osm_way_id=581532442`) accanto all'ancora | Punto di salita valido, senso di marcia, marciapiede/barriere, manovra del bus e tempo verso FS nei due versi |

Una ricognizione riproducibile sui bordi RT017 e sulle realizzazioni RT023
del [pattern tipizzato](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35745433362)
mostra che **le due varianti inverse percorrono il way OSM 581532442**, con
un nodo di percorso a circa 48 m in linea d'aria dall'ancora provvisoria
di San Zeno. Le due varianti nell'ordine richiesto non percorrono quel way
e si avvicinano all'ancora solo a circa 302 m in linea d'aria. Nessuna
variante ha un evento di salita a San Zeno: **passare su Via Cantù non
equivale ancora a servire San Zeno**. La distanza fra percorso e luogo
non è distanza pedonale e non assegna una fermata.

Per il centro sportivo, il nodo fisico più vicino dei quattro percorsi
rimane a circa 210–383 m *in linea d'aria* dalla vecchia coordinata POI.
Questa misura è solo una diagnosi preliminare della lacuna, non un catchment
pedonale: il precedente [audit RT-006](PHASE2_NETWORK_DESIGN_CODE_AUDIT_V3.md)
ha già segnalato il rischio di snap/attraversamento barriere proprio nel
caso «Olgiate-sud/Centro Sportivo». Non si attribuisce alcuna nuova
percentuale di copertura finché una fermata non sia identificata e verificata.
Nel catalogo delle **ipotesi**, `P2V2S_0092` si trova a circa 151 m in linea
d'aria dal POI approssimato; il suo stato è `FIELD_CHECK_PENDING`, non
fermata esistente o scelta. Il catalogo non contiene una candidata sul way
`581532442` di Via Cesare Cantù. Questi sono punti di partenza per
ricognizione, non boarding events da aggiungere automaticamente alla linea.

## Audit di localizzazione senza scelta discrezionale

Lo [script di inventario](../scripts/phase2_audit_rt031_local_stop_siting_v3.py)
verifica **tutte e 40** le ipotesi di Olgiate presenti nel catalogo fissato;
nessuna è già fisicamente certificata. Per ciascuna espone separatamente
distanza in linea d'aria dai luoghi, nome/attributi stradali, indicatore di
popolazione aggiuntiva del *vecchio substrato V2 rispetto alle fermate
ufficiali esistenti*, e relazione con i quattro percorsi RT031. Quest'ultimo
indicatore di popolazione **non è** il guadagno marginale della nuova linea
e non si somma alle percentuali RT028. Non c'è punteggio, raggio di
ammissione o «migliore fermata» calcolata.

Tre esempi mostrano perché il punto più vicino non è automaticamente giusto:

| Ipotesi | Strada | Dal POI sportivo approssimato | Sul way già percorso dall'8 base? | Popolazione aggiuntiva V2 a 10 min | Evidenza fisica ancora mancante |
| --- | --- | ---: | --- | ---: | --- |
| `P2V2S_0082` | Via Buttero | 254 m | Sì, nei due pattern base; non nelle varianti Via Statale | 118 | Lato strada, spazio di arresto, accesso a piedi; marciapiede non indicato |
| `P2V2S_0092` | Via Mondonico | 151 m | No | 151 | OSM indica `sidewalk=no`; larghezza, lato e accesso da verificare; servirebbe valutare una deviazione |
| `P2V2S_0103` | Via Mondonico | 259 m | No | 264 | Come sopra; maggiore catchment V2 non prova utilità per la linea proposta |

Le distanze sono rettilinee e i numeri di popolazione sono arrotondati:
nessuno dei tre numeri prova che il centro sportivo sia raggiungibile in
sicurezza o entro un tempo pedonale dato. Per Via Cantù il problema è
diverso: il percorso inverso usa il way corretto, ma **non esiste nel
catalogo un'ipotesi di fermata su quel way**. La prossima azione non è
scegliere la candidata più vicina su un'altra via: è enumerare e verificare
le possibili posizioni di salita nei due sensi lungo il tratto percorso.

Una proposta di fermata può avanzare solo con evidenza su lato/sensi di
marcia, spazio bus e sicurezza, itinerario pedonale reale senza barriere,
identità del luogo servito, incremento di accesso sullo *stesso* substrato
del confronto RT031, e costo in km/tempo per i passeggeri già serviti.
Sicurezza e legalità sono prerequisiti; fra siti idonei, accesso e costo
restano dimensioni di confronto senza pesi imposti dal modello. Fino alla
verifica sul campo: `new_stop_selected=false`.

Infine, le coordinate di `S_SAN_ZENO` nei vecchi GTFS di scenario
`data/raw/gtfs/network_structural/stops.txt` (45.7248, 9.3821) sono a circa
**2,26 km** dall'ancora Piazza San Zenone più recente. Quel record è di
scenario, non una fermata ufficiale certificata. Le vecchie conclusioni
«+7,5 minuti, ciclo oltre 60, dunque escluso» erano condizionate a quel
tracciato e a un ciclo fisso di 60 minuti: non escludono Via Cantù nel
progetto attuale. Non provano neppure che un bus possa fermarsi lì.

**Prossima verifica decisiva:** definire una o più posizioni di salita
*candidate* per Via Aldo Moro e Via Cesare Cantù, verificarle sul posto con
ente/operatori, poi rieseguire accesso pedonale, geometria bus, entrambi i
versi e tempi località→FS. Solo allora si confronta l'8 corretto con le
alternative sulla stessa base. `network_selected=false`;
`primary_selection_authorised=false`;
`runner_up_selection_authorised=false`.
