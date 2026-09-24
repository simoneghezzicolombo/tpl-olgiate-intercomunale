# RT031 — Quartiere di Olgiate a sud della Statale e San Zeno/Via Cantù

**Correzione del committente, 24 settembre 2026.** La zona da servire è
**l'intera area residenziale cerchiata sulla mappa a sud della SS342/Statale**,
visivamente comprendente Canova–San Zeno e l'intorno di Via Piave. Il centro
sportivo, l'oratorio e la Casa di Comunità sono riferimenti nel quartiere,
non sostituti dell'obiettivo territoriale. La domanda progettuale è se un
servizio riconoscibile permetta a chi abita in questa zona di raggiungere
Olgiate FS con fermate accessibili, tempi e frequenze utili nei versi
necessari. La schermata annotata indica l'intento del committente ma non è
un poligono georeferenziato: i suoi bordi non sono stati convertiti in
coordinate o in un denominatore di popolazione. Perciò **nessuna percentuale
di copertura del quartiere** è ancora certificata.

I risultati che seguono sui singoli siti e sul POI sportivo restano validi
come verifiche *locali*, ma non rispondono da soli alla copertura dell'area
cerchiata. Anche il fatto che un percorso passi per Via Cantù non prova che
le residenze nella parte occidentale o interna del quartiere possano salire
e arrivare alla stazione con un viaggio competitivo. La prossima analisi
deve confrontare, sulla stessa base pedonale, le abitazioni dell'intera zona,
le fermate esistenti e ipotizzate, e i viaggi ordinati verso FS.

### Primo controllo delle strade del quartiere

L'[inventario riproducibile](../scripts/phase2_audit_rt031_local_stop_siting_v3.py)
ora misura i bordi RT017 percorsi su alcune strade nominate nella zona o
nelle verifiche precedenti. La corrispondenza è per *nome esatto della via*
nel rilievo OSM fissato; questi nomi sono indizi geografici, non il confine
del quartiere. Metri di percorso su una strada non equivalgono a residenti
serviti o a una fermata utilizzabile.

| Variante dell'unica linea progettuale | Via Piave | Via Aldo Moro | Via Buttero | Via Mondonico | Via Cesare Cantù, tutti i way omonimi |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordine richiesto, base | 259 m | 0 | 480 m | 0 | 0 |
| Ordine richiesto, Via Statale | 0 | 0 | 120 m | 0 | 0 |
| Ordine inverso, base | 0 | 0 | 609 m | 0 | 997 m |
| Ordine inverso, Via Statale | 0 | 0 | 120 m | 0 | 997 m |

I 997 m sommano *tutti* i way OSM denominati Via Cesare Cantù; i 980,10 m
della ricognizione sotto riguardano il solo way `581532442`. In particolare,
il passaggio parziale su Via Piave nella prima variante non dimostra un
collegamento delle abitazioni di Canova–San Zeno verso FS; nelle varianti
inverse il bus percorre Via Cantù, ma senza un evento di salita certificato.
La carenza del quartiere va perciò esaminata come combinazione di **punti di
salita, accesso pedonale dalle abitazioni, verso e tempo di viaggio**.

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
La [CI dell'inventario](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35750104153)
ha eseguito due repliche byte-per-byte identiche (artefatto `10705380537`,
SHA-256 `d3932f14bb550a98bc17620fe9067947380dcb2bd1df57920773891ea3075d6c`).

L'inventario ora esporta anche la sequenza orientata dei bordi RT017 di Via
Cantù, con coordinate dei nodi e posizione nell'itinerario, per la ricognizione
sul posto. Nelle due varianti inverse sono **44 bordi, 980,10 m modellati**;
nelle altre due, nessuno. Le due sequenze occupano rispettivamente gli indici
538–581 e 521–564 del percorso stradale completo. Sono segmenti da ispezionare,
non 44 possibili fermate e neppure una proposta di posizione. Nessun lato di
salita, attraversamento o spazio di arresto è ancora certificato.
La [CI aggiornata](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35979793544)
ha verificato due repliche identiche dell'inventario esteso: artefatto
`10799751009`, JSON SHA-256
`5218bc54076d0fe081d04b2cbc4bba09bcc7463deab9ef4cf3fa9d530e7b5b8e`.

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
La traversata su Via Cantù si trova nel **primo segmento dell'anello est
subito dopo Olgiate FS**: anche con una fermata, quella corsa sarebbe in
uscita dalla stazione. Da sola non garantirebbe a San Zeno un viaggio breve
*verso* FS. Occorre un passaggio utile nel senso opposto, oppure esplicitare
il giro residuo e valutarlo con gli eventi e l'orario; la sola vicinanza
geometrica non risolve la direttezza richiesta dal committente.

Una proposta di fermata può avanzare solo con evidenza su lato/sensi di
marcia, spazio bus e sicurezza, itinerario pedonale reale senza barriere,
identità del luogo servito, incremento di accesso sullo *stesso* substrato
del confronto RT031, e costo in km/tempo per i passeggeri già serviti.
Sicurezza e legalità sono prerequisiti; fra siti idonei, accesso e costo
restano dimensioni di confronto senza pesi imposti dal modello. Fino alla
verifica sul campo: `new_stop_selected=false`.

## Controfattuale sullo stesso grafo pedonale RT028

Il [calcolo condizionale](../scripts/phase2_audit_rt031_conditional_new_stop_access_v3.py)
usa **lo stesso** grafo, le stesse unità di popolazione e gli stessi quattro
pattern RT031 dell'audit di accesso precedente. Riproduce esattamente le
coperture base prima di aggiungere *ipoteticamente* ciascuna delle 40
posizioni, una alla volta. È finalmente una misura marginale comparabile
**per accesso a piedi**, ma assume una fermata accessibile e un evento di
salita che oggi non sono certificati: non calcola deviazione del bus,
orario, viaggio verso FS o idoneità fisica. Non si sommano guadagni di
fermate diverse, perché le loro aree pedonali possono sovrapporsi.
La [CI del controfattuale](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35751414710)
ha riprodotto due volte il risultato; artefatto `10706300279`, SHA-256 del JSON
`e7bda2387e560d355a310300d140934c502252312ee50399eb29d88c34b4b8b3`.
Il controllo generale di composizione sullo stesso commit è [verde](https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale/actions/runs/35751421664).

| Ipotesi | Dal POI sportivo approssimato sul grafo RT028 | Incremento Olgiate a 10 min, 8 base | Incremento Olgiate a 10 min, 8 + Via Statale | Scarto essenziale |
| --- | ---: | ---: | ---: | --- |
| `P2V2S_0082` · Via Buttero | 6,68 min | +2,66 punti | +1,49 punti | Già sul way dell'8 base, non sul way delle varianti Via Statale; sito e lato non verificati |
| `P2V2S_0092` · Via Mondonico | 2,38 min | +2,68 punti | +1,51 punti | Cammino modellato breve dal POI, ma fuori percorso e `sidewalk=no` in OSM |
| `P2V2S_0103` · Via Mondonico | 3,60 min | +3,77 punti | +2,60 punti | Più accesso residenziale modellato, ma fuori percorso e `sidewalk=no` in OSM |

I risultati delle due direzioni coincidono per queste tre ipotesi perché
le differenze dei rispettivi stop-set non cambiano il loro catchment
marginale; questo **non** certifica servizio bidirezionale alla fermata.
Il POI sportivo è approssimato e il suo connettore al grafo RT028 è di
73,34 m, vicino al limite modellistico di 90 m: resta prioritaria una
verifica indipendente del percorso e delle barriere. Un'ipotesi più lontana
dal centro sportivo può dare molti più punti di copertura comunale, ma
risponde a un'altra geografia e può imporre molto più percorso al bus.
Per San Zeno nessuna delle 40 ipotesi è sul way Via Cantù percorso dalla
variante inversa; il controfattuale non colma quel vuoto di generazione.

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
