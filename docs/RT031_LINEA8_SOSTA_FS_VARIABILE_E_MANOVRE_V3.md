# Linea 8 — 16 giri: sosta FS variabile e manovre

## Esito

La sosta intermedia a Olgiate FS è stata resa **variabile per singolo giro completo**, senza creare due linee, cambiare il tracciato di 27,679 km o perdere alcuno dei 29 siti di progetto. Anche in questo dominio ampliato **non esiste** un orario di 16 giri che tenga H60 nelle spalle 06:45/06:50–10 e 16–19:40, H120 solo 10–16, cinque corse H30 abbinate ai treni centrali di ciascuna ala e i 22 obiettivi ferroviari del confronto. L'infeasibilità è provata dal solutore nel dominio qui definito, non per ogni possibile esercizio.

![Il tracciato stradale invariato della Linea 8, un solo giro completo in entrambe le ali](../outputs/phase2/rt031_line8_local_shortcuts_v3/linea8_16_giri_tracciato.png)

Persino sostituendo *a titolo diagnostico* i due treni-obiettivo dell'ala percorsa seconda (07:26 → 09:56 per Milano; 16:32 → 19:02 da Milano), **17 giri non bastano** per H60 nelle spalle. **18 giri** producono un testimone con sosta intermedia breve, ma costano **129.536,175 km/anno** su 260 giorni ipotizzati: **+16,26%** rispetto a 111.419. Non sono autorizzati.

Il miglior limite di spalla verificato con **16 giri**, nella griglia di cinque minuti, è **H95**: H90 è infeasible e H95 è fattibile in entrambe le precedenze. Però H95 vale già prima delle 10 e dopo le 16; non è il solo H90/H120 della morbida pesante discusso col committente. Inoltre l'orario deve usare in più corse una sosta a FS di circa **43,61 minuti nominali** se parte prima ovest, **39,84 minuti** se parte prima est. Tale attesa è *dentro* il viaggio intercomunale, non un cambio obbligatorio, ed è troppo onerosa per presentare questo testimone come soluzione finale. I due obiettivi ferroviari spostati non sono stati accettati. Nessun orientamento, orario, aumento di giri o treno sostitutivo è selezionato.

Un'ulteriore prova individua **perché non basta “mantenere H30” nel nome dell'orario**. Senza imporre i 22 treni-obiettivo originali, l'ordine prima est ammette 16 giri con H30 su entrambe le ali nelle punte, H60 nelle spalle e H120 10–16. Ma massimizzando poi il **numero di obiettivi ferroviari originali effettivamente compatibili**, ne risultano **solo 10 su 22** nel dominio esaminato. Restano scoperti tutti e cinque gli obiettivi mattutini dell'est, il primo dell'ovest e tutti e sei i serali dell'ovest. Nell'ordine prima ovest nemmeno la versione H30 senza ancoraggi ferroviari è fattibile a 16 giri. Il 10/22 è un limite di cardinalità su quei treni datati, **non un punteggio di utilità, una stima di passeggeri o una scelta di quali treni sacrificare**. Non si promuove quindi questo testimone a proposta ferroviaria.

| Test, stesso otto | 16 giri prima ovest | 16 giri prima est |
|---|---|---|
| H60 nelle spalle, H120 solo 10–16, obiettivi originali | Infeasible | Infeasible |
| H60 nelle spalle, due obiettivi sostituiti | Infeasible | Infeasible |
| H90 nelle spalle, due obiettivi sostituiti | Infeasible | Infeasible |
| H95 nelle spalle, due obiettivi sostituiti | Testimone; attesa FS massima 43,61 min | Testimone; attesa FS massima 39,84 min |
| H95, ma sosta intermedia limitata a 80/75 min dalla prima partenza FS | Infeasible | Infeasible |

La sosta indicata nell'ultima riga è un **offset di partenza**, non un'attesa a bordo: nell'ala ovest il tempo nominale di marcia+fermate prima di FS è 41,39 min, nell'est 40,16 min. Almeno un offset di 85/80 min è necessario per il testimone H95 nel rispettivo dominio. Il limite H95 non dichiara una frequenza pubblica uniforme: l'orario proposto dal solutore ha intervalli sino a H120 nella fascia centrale. La minimizzazione della somma degli offset serve solo a evitare attese a bordo inutili a parità di vincoli, non è un peso per selezionare la rete.

## Passaggi utili, non solo nomi delle fermate

Ogni giro del testimone include entrambe le ali nello stesso ordine, la fermata pubblica intermedia a FS e due occorrenze ordinate per **Olgiate sud** e due per **San Zeno/Via Cantù**. Nel modello nominale l'occorrenza iniziale consente il tratto rapido *da FS* (rispettivamente circa 4,32 e 2,54 min); l'ultima il tratto rapido *verso la successiva FS* (circa 4,14 e 2,61 min). L'artefatto registra per ciascuna delle 16 corse l'identificativo, l'ordine e il tempo di ogni evento di fermata. Questi sono tempi modellati e occorrenze di progetto, **non** garanzie di palina fisicamente autorizzata, accessibilità o affidabilità empirica.

I 16 giri mantengono **115.143,267 km/anno** su 260 giorni ipotetici, +3.724,267 km (+3,34%) rispetto al riferimento. Variare le soste non cambia i km di servizio, ma può aumentare il tempo a bordo e il fabbisogno mezzi. Nel testimone H95 con partenza prima est l'indice di sovrapposizione dei giri completi richiede quattro mezzi in tutti i 27 scenari deterministici dichiarati; prima ovest arriva a cinque nello stress più severo. Non sono disponibilità di flotta, turni autista o probabilità di ritardo.

## Manovre della stessa geometria

Il tracciato ancora contiene **sei inversioni immediate** di archi stradali (M1–M6: Hoè/Via Giovanni XXIII; Santa Maria Hoè/Via Como; Olgiate sud/Via Aldo Moro; Via Nazionale est; Calco/Via Nazionale; San Zeno/Via Cesare Cantù). Nessuna è autorizzata per un autobus. Una svolta ammessa dal grafo non equivale a una traiettoria materialmente eseguibile. Servono verifiche d'ingombro del mezzo, accosto e attraversamenti; correggere una manovra può cambiare geometria, km, tempi e quindi l'orario. Lo stato dettagliato e le coordinate sono nel [registro delle manovre](../outputs/phase2/rt031_line8_local_shortcuts_v3/stop_plan_and_additions.json.gz).

## Dominio e decisione

Partenze della prima FS 05:00–19:40 a passi di cinque minuti; sette possibili offset di ripartenza dalla FS intermedia per ogni giro, dal primo stress-fattibile a +30 minuti; stessi 29 siti e stessa sequenza stradale in tutte le corse di ciascun test; nove scenari comuni di marcia/sosta; H30 sui cinque eventi realmente abbinati ai treni centrali in ciascuna ala. I test H95 e H60 con due treni sostituiti non conservano tutti i 22 obiettivi ferroviari *originali*. Il modello non certifica ritardi indipendenti, manovre, paline, continuità fisica dei passeggeri o un esercizio completo.

**Conclusione operativa:** non c'è ancora una proposta unica che rispetti insieme i 16 giri adottati, H60 fuori dalla sola morbida pesante, gli obiettivi ferroviari originali e un viaggio intercomunale senza lunga attesa a FS. Non bisogna chiamare “soluzione” né H95 con 40 minuti a bordo né 18 giri senza copertura finanziaria. Per chiudere serve una scelta esplicita sul compromesso di servizio *oppure* una modifica stradale validata che liberi la produzione dei giri necessari senza perdere i due passaggi locali utili. `network_selected=false`; `primary_selection_authorised=false`; `runner_up_selection_authorised=false`.

[Risultati machine-readable, orari ed eventi ordinati (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/variable_fs_hold_16_full_trips.json.gz) · [Script riproducibile](../scripts/phase2_probe_rt031_line8_variable_fs_hold_v3.py) · [Audit precedente a sosta fissa](RT031_LINEA8_16_GIRI_COMPLETI_V3.md)
