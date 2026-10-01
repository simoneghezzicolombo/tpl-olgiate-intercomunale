# Linea 8 unica — quanti autobus per i 16 giri completi?

**Non esiste una flotta «per ala».** Ogni corsa modellata è atomica: FS → prima ala → FS (sosta intermedia) → seconda ala → FS, sullo stesso autobus. Le parole «ovest» ed «est» nelle due righe del confronto indicano soltanto **l'ordine delle ali**. I 16 giri e i 29 siti sono gli stessi; non si propone una biforcazione pubblica.

Abbiamo esplicitato i blocchi veicolo dei due orari diagnostici a massimo intervallo 115 minuti contenuti in `uniform_16_full_trips.json.gz`. Ogni giro completo è assegnato una sola volta a un autobus modello. Per ripartire sul giro successivo, il mezzo deve aver concluso *entrambe* le ali e disporre del recupero terminale. Un controllo indipendente del massimo di intervalli sovrapposti conferma il minimo di mezzi calcolato dai blocchi.

| Ordine del giro completo | Scenario | Durata completa | Durata + recupero | Minimo di autobus modello |
|---|---|---:|---:|---:|
| Ovest → Est | marcia ×1,1; 0,5 min/sito; recupero 10 min | 100,16 min | 110,16 min | **4** |
| Est → Ovest | stesso scenario | 96,39 min | 106,39 min | **4** |
| Ovest → Est | marcia ×1,1; 1 min/sito; recupero 15 min | 107,16 min | **122,16 min** | **5** |
| Est → Ovest | stesso scenario lento | 104,39 min | **119,39 min** | **4** |

La ragione del quinto mezzo è concreta: cinque partenze H30 consecutive si collocano a 0, 30, 60, 90 e **120 minuti**. Nello scenario lento ovest-prima, il primo autobus è pronto per un altro giro completo solo dopo **122,16 minuti**, quindi non può prendere la quinta partenza. Est-prima è pronto dopo **119,39 minuti**. Non sono mezzi «assegnati all'est» o «all'ovest»; è il fabbisogno **totale** dello stesso servizio quando cambia l'ordine dell'otto.

Sui 27 scenari dichiarati, ovest-prima richiede quattro autobus in 26 casi e cinque in uno; est-prima ne richiede tre in un caso e quattro negli altri 26. Nel nominale, quattro mezzi coprono tutti i 16 giri in entrambi gli ordini. I blocchi completi, con partenze, passaggio intermedio a FS, arrivi e soste fra giri, sono nel [registro verificato](../outputs/phase2/rt031_line8_local_shortcuts_v3/uniform_16_full_trip_vehicle_blocks.json). Gli identificativi B1–B5 sono **etichette di una copertura matematica**, non turni assegnati ad autobus o autisti reali.

**Non selezioniamo automaticamente est-prima.** Guadagna margine sul fabbisogno nel caso lento, ma anticipazione del servizio e collegamenti ferroviari cambiano fra le ali; i due orari sono tuttora diagnostici e non soddisfano H60 nelle spalle. L'aumento del numero di autobus non modifica i chilometri commerciali dei 16 giri, ma può incidere su deposito, corse a vuoto, personale e costi, che qui non sono stati misurati.

La continuità dello *stesso mezzo modellato* attraverso la FS intermedia è verificata dal fatto che il giro è indivisibile. Restano da certificare continuità fisica del veicolo e dei passeggeri, banchina/lato di fermata, manovre, tempi osservati, disponibilità dei mezzi, deposito e turni autisti. `operating_plan_adopted=false`, `network_selected=false`, `primary_selection_authorised=false`, `runner_up_selection_authorised=false`.
