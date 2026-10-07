# Budget operativi della base confermata — 7 ottobre 2026

Il controllo `python -m scripts.phase2_closure_timing_20261007` restituisce su stdout 432 righe di budget (16 giri × 27 scenari), senza modificare gli artefatti condivisi. Usa `caller_confirmed_vehicle_blocks_accounting_20261001.json`, il relativo handoff confermato e `calco_centre_adopted_design.json`, verificando digest canonici, orario, griglia, decomposizione marcia/dwell, assegnazione completa e recupero. Il precedente `uniform_16_full_trip_vehicle_blocks.json` contiene altre fasi e non è la fonte dei blocchi confermati.

Il controllo autentica anche l'intero oggetto dei blocchi e l'intero handoff salvati contro i rispettivi produttori esistenti, mediante digest canonico; non basta conservare i riferimenti alle fonti dopo una modifica del contenuto. I produttori sono chiamati in lettura, senza i loro entry point di scrittura. Tutti i sei costi misurati sono obbligatori: `None` fallisce il controllo, non viene convertito in zero.

È chiusa la derivazione aritmetica dei limiti da confrontare con rilievi. RUNTIME resta aperto per misure rappresentative e accettazione operativa. Una compatibilità del mezzo nel modello non autorizza il servizio o il diritto a restare a bordo.

Per ogni giro:

- Marcia est + dwell delle 14 occorrenze non-FS + dwell minimo necessario FS ≤ partenza FS intermedia − partenza iniziale. Con il minuto FS ereditato, marcia+dwell est hanno budget 54 minuti; giri 7 e 16: 49 minuti. Il minuto è un'ipotesi, non una misura.
- L'attesa FS residua è separata dal dwell minimo. Non si somma nuovamente al tempo di giro: la partenza ovest è già fissa.
- Marcia ovest + dwell delle 14 occorrenze ≤ durata ovest dello scenario solo per riprodurne il rientro. Il rientro nominale usa 38,3027038045 minuti; è un risultato ingegneristico, non una promessa pubblica.
- Marcia ovest + dwell + recupero terminale ≤ prossima partenza dello stesso mezzo − partenza ovest. Ogni scenario conserva la propria assegnazione e il proprio recupero assunto (5/10/15 minuti). Negli ultimi giri di ciascun blocco il budget di prossimo impiego è `null`: non si inventa rientro deposito o scadenza di turno.

Nel nominale, per i giri 1–16, il budget ovest+dwell+recupero al prossimo impiego è rispettivamente 65, 90, 120, 205, 280, 345, 350, 260, 185, 95, 65, 95, null, null, null, null minuti. Il recupero di 10 minuti consuma questi budget; il margine residuo minimo è 16,6972961955 minuti. Questi intervalli non certificano disponibilità per altre linee.

`check_measurement` accetta i sei costi separati in minuti e produce slack per partenza FS, rientro di scenario e prossimo impiego. Richiede valori finiti non negativi. Non sceglie riserva né banda e non trasforma il superamento di uno scenario in probabilità di mancata coincidenza. Misure dell'intero giro senza separazione est/ovest non bastano; i soli totali non verificano gli eventi intermedi alle fermate.

FS_TRANSFER: la topologia corretta e confermata dal committente è bus → banchina 2 (~76,23 m) → raccordo geometrico di superficie esplicito 5,93 m → scala 1193795237 → sottopasso 784178060 → scala 1193795239 → banchina 1 (~108,16 m complessivi). Il grafo RT028 originale resta invariato. Restano da misurare distintamente entrambi i versi per ciascun binario, posizione effettiva del treno e delle porte, scale, percorso accessibile e apertura/chiusura porte. Nelle cinque coppie AM confermate, il budget treno→bus è 3 minuti; bus→treno nello stress est massimo è 3,2234063721 minuti. Trasferimento, ritardo e qualsiasi riserva dichiarata devono stare nello stesso budget; il proxy geometrico non è una misura.

FS_CONTINUITY: le righe dei blocchi attestano solo lo stesso mezzo di modello per il giro completo. Servono identificazione/conferma operativa del mezzo e conferma separata del diritto dei passeggeri a restare a bordo durante FS; eventuale cambio o discesa va accettato come modifica.

RAIL_2027: controllo ufficiale mirato del 7 ottobre sulla [pagina Trenord dell'orario](https://www.trenord.it/linee-e-orari/circolazione/orario-ferroviario/); il quadro 180 collegato conduce a [Q180_giugno_2026.pdf](https://www.trenord.it/fileadmin/contenuti/TRENORD/2-Linee_e_orari/Orario_ferroviario/ORARIO_in_vigore/Q180_giugno_2026.pdf). Questo controllo non stabilisce validità per il 2027 e non dimostra assenza di altre pubblicazioni. Restano necessari inventari ufficiali arrivi/partenze, chiamate e calendari validi per tutte le date 2027 coperte; una pubblicazione invernale non certifica automaticamente l'estate. Cache storico e orario bus non vengono aggiornati.

Nessuna nuova selezione o adozione: `physical_operation_ready=false`, `rail_2027_certified=false`, `operating_plan_adopted=false`, `decision_budget_km=null`, `uncertainty_band_min=null`. Una Linea 8, 27 siti, 28 occorrenze non-FS e tre ruoli FS, 16 giri, H30 confermati e base 254 feriali / 110.229,936 km restano invariati. Le quattro prove esterne RUNTIME/FS_TRANSFER/FS_CONTINUITY/RAIL_2027 restano aperte.

Verifica: `python -m unittest tests.test_closure_timing_20261007`.
