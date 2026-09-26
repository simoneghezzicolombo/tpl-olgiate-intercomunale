# Linea 8 — esito della correzione dell'orario

## Conclusione operativa

**Non è stata ottenuta una proposta che soddisfi insieme tutti i requisiti. Il caso 109k non deve essere presentato come soluzione finale.**

Sono stati eseguiti due lavori distinti: una ricerca libera degli orari sui quattro percorsi esistenti, e la costruzione di un orario regolare a 34 corse con tutti i siti. Il secondo funziona per una promessa di servizio diversa e più corta: non viene adottato automaticamente.

Il tetto resta **111.419 km/anno**. Non si eliminano paesi, non si riduce H30 a H60 in punta e non si autorizzano PRIMARY/RUNNER-UP. Mancano inoltre ancora i riscontri fisici e operativi indicati in fondo.

## 1. Spostare soltanto gli orari: controllo ampliato

La verifica non si limita più a traslare mattina e sera dello stesso numero di minuti:

- Tutte le partenze sono libere, fra 06:00 e 20:00, ogni cinque minuti.
- Mattina e sera possono scegliere **indipendentemente** l'inizio della punta: 06:30–07:00 e 16:30–17:00, ogni cinque minuti; durata 120 minuti ciascuna.
- Per ciascuna località il confronto richiede una partenza utile entro 30 minuti durante l'intera punta e 60 nel resto, sia verso sia da FS, per la finestra di disponibilità 06–19.
- Le due ali sono persino risolte separatamente, ammettendo quindi fasi differenti: è una verifica più permissiva del problema con fasi comuni.
- Si mantengono quattro cammini completi, 260 giorni ipotetici, marcia +10% e 30 secondi di sosta per nodo distinto. Si assume ottimisticamente che tutte le occorrenze siano utilizzabili.

**Entrambe le ali risultano impossibili con al massimo 17 corse in questo dominio.** Ogni eventuale soluzione congiunta deve quindi averne almeno 18 per ala. Contando tutte e 18 sul cammino più corto di ciascuna ala, si ottiene:

**18 × (12,623834 + 11,893513) × 260 = 114.741,185 km/anno.**

È un **limite inferiore**, non un orario costruito né un preventivo: supera il cap di almeno **3.322,185 km**, senza deposito. L'orario effettivamente costruito nei precedenti confronti da 121.115,696 km resta un altro oggetto, non viene sostituito da questo limite.

Il risultato esclude il cap solo nel dominio dichiarato. Non prova l'impossibilità su altri percorsi, su un orologio continuo, con corse parziali o con una diversa promessa di servizio. **06–19 e due ore simultanee in tutte le località sono ipotesi del confronto, non nuove decisioni attribuite all'utente.**

Fonti riproducibili: `flexible_peaks_west_max17.json`, `flexible_peaks_east_max17.json`, `flexible_peak_km_floor.json`. La verifica con tetto direttamente nel problema congiunto ha raggiunto il limite di tempo e non è stata usata come prova; la conclusione sopra deriva dalle due verifiche indipendenti concluse.

È stato tentato anche il raffinamento a un minuto: est terminato per limite di tempo senza conclusione, ovest interrotto senza risultato dopo oltre quattro minuti. **La prova rimane quindi sulla griglia di cinque minuti.** Il tentativo inconcluso est è conservato in `flexible_peaks_east_max17_one_minute.json`; nessuno dei due tentativi estende il limite al tempo continuo.

## 2. Un orario realmente costruito a 34 corse: cosa comporta

Partenze da FS uguali per le due ali, mantenendo ciascuna nello stesso senso per tutta la giornata:

| Periodo | Partenze FS per ciascuna ala |
|---|---|
| Prima punta, cinque corse | 06:40, 07:10, 07:40, 08:10, 08:40 |
| Morbida | 09:40, 10:40, 11:40, 12:40, 13:40, 14:40, 15:40 |
| Seconda punta, cinque corse | 16:40, 17:10, 17:40, 18:10, 18:40 |

**Non c'è più il cambio di senso che concentrava due passaggi e poi lasciava un'ora di intervallo.** Ogni singola occorrenza ordinata ha cinque partenze esattamente ogni 30 minuti in ciascun gruppo di punta e intervalli di 60 minuti fra i gruppi. Le occorrenze ripetute della stessa identità rimangono distinte: non si uniscono due lati per fingere una frequenza.

Ma questo comporta **12 ore fra prima e ultima partenza**, non 13–14 ore. Le fasce locali si spostano del tempo necessario a raggiungere la fermata. L'intersezione di disponibilità H30 simultanea in tutte le località è di circa 116–118 minuti, **non 120**. I due concetti di frequenza sono esplicitamente separati e il confronto 06–19 rimane non soddisfatto.

### Costo e conseguenza del senso fisso

Non è stato scelto un senso tramite un punteggio inventato. Ecco le quattro combinazioni, sul medesimo orario:

| Sensi ovest / est | Km di servizio annui | Residuo prima del deposito | Olgiate sud: verso / da FS | San Zeno: verso / da FS |
|---|---:|---:|---:|---:|
| A / A | 108.366,675 | 3.052,325 | 4,1 / 30,9 min | 31,2 / 2,5 min |
| A / B | 110.745,576 | 673,424 | 4,1 / 30,9 min | 2,6 / 32,4 min |
| B / A | 108.836,886 | 2.582,114 | 31,3 / 4,3 min | 31,2 / 2,5 min |
| B / B | 111.215,787 | 203,213 | 31,3 / 4,3 min | 2,6 / 32,4 min |

Tempi ipotetici a bordo, non GJT: non comprendono accesso e attesa. I tempi verso FS sono dalla partenza della fermata, quelli da FS fino all'arrivo alla fermata. **Il percorso a senso fisso non può essere venduto come collegamento rapido in entrambi i versi per Olgiate sud e San Zeno.** La combinazione A/B conserva i sensi mattutini del vecchio caso, ma allunga entrambi i ritorni e lascia solo 2,59 km/giorno per gli extra: non è una soluzione di budget chiusa.

Le 27 combinazioni di marcia/soste/recupero esaminate richiedono al massimo quattro mezzi nella copertura condizionata delle corse. Non sono turni autisti o blocchi con deposito. Le coincidenze di riferimento collegano nel modello cinque S8 verso Milano (07:26–09:26) e cinque arrivi da Milano (16:32–18:32), sul solo giorno ferroviario congelato **3 settembre 2026** e con tre minuti di trasferimento; non sono una verifica del servizio odierno né una probabilità di coincidenza.

Fonte: `regular_12h_compromise.json`, con tutte le partenze per occorrenza, tempi a bordo, coincidenze nominali, scenari mezzi e fallimenti rispetto alla promessa più estesa. `user_acceptance_recorded=false`.

## 3. Territorio e tracciato non sono stati ridotti

Entrambi i lavori mantengono i quattro cammini stradali di partenza. Le varianti regolari incontrano le stesse **28 identità/siti includendo FS**: non sono 28 paline autorizzate. Olgiate sud e San Zeno/Via Cantù restano esigenze separate e incluse.

![Cammini stradali esistenti del confronto, non nuovi percorsi approvati](../outputs/phase2/rt031_line8_local_shortcuts_v3/full_retention_context.png)

La copertura pedonale potenziale a 10 minuti, condizionata all'utilizzabilità dei siti, rimane quella dell'artefatto territoriale: Brivio 89,09%, **Calco 68,21%**, Olgiate 84,56%, Santa Maria Hoè 95,75%, La Valletta Brianza 67,85%; totale 79,16%. Non certifica accessibilità temporale, domanda o convenienza del viaggio.

È stato ricontrollato anche il confronto stradale già presente: le opzioni molto corte imperniate su Beverate/SS Briantea non sono semplici correzioni prive di conseguenze. Nell'audit pedonale corrispondente la copertura potenziale di Brivio scende fino a circa 35%, rispetto all'89% del contesto mantenuto. Non vengono introdotte di nascosto per far tornare il cap. Fonti: `brivio_existing_sites.json` e `brivio_existing_sites_walk.json`; non si trasferisce automaticamente un orario a un'altra geometria.

## 4. Il punto che richiede una scelta, non un'altra etichetta

Il progetto non è concluso. Il compromesso a 34 corse mostra concretamente che conservare i siti e avere gruppi H30 regolari è possibile nel conto dei soli km, ma **12 ore e sensi fissi con viaggi lunghi sono concessioni**, non il rispetto automatico di tutto quanto richiesto.

Per procedere a una proposta unica occorre quindi accettare esplicitamente una modifica della promessa di servizio o del percorso; altrimenti il confronto temporale completo resta fuori dal cap nel dominio verificato. Il modello non ha l'autorità di scegliere quale requisito sacrificare. Il tetto e le preferenze territoriali non sono stati modificati.

Qualunque proposta tecnica eventualmente accettata deve inoltre essere sottoposta a verifica di fermate/lati, percorribilità autobus e restrizioni complete, tempi osservati, calendario reale, coincidenze applicabili, deposito, costi e turni. Non viene affermata una solidità operativa del 100% in assenza di tali evidenze.
