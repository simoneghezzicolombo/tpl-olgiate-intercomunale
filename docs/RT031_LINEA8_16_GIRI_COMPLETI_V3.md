# Linea 8 — 16 giri completi: scelta registrata, orario ancora da accettare

**Scelta del committente: 16 corse complete al giorno, tutte sullo stesso otto.** Con geometria invariata sono **115.143,267 km di servizio/anno** su 260 giorni ipotizzati: **+3.724,267 km (+3,34%)** sul riferimento di 111.419. Non è approvazione del calendario, di un budget complessivo, di più mezzi o dell’esercizio.

Restano 29 siti di progetto: Arlate/Via Nuova Provinciale inclusa, aggiunta N0655 sul cavalcavia esclusa; Olgiate sud e San Zeno/Via Cantù mantenuti. Nessuna corsa limitata a un’ala.

![Tracciato unico confermato della Linea 8: entrambe le ali sono percorse in ognuno dei 16 giri; 29 siti di progetto](../outputs/phase2/rt031_line8_local_shortcuts_v3/linea8_16_giri_tracciato.png)

La mappa unisce la geometria stradale già confermata alla nuova fermata di progetto N1212 ad Arlate. I punti non certificano posizione o autorizzazione fisica delle paline. I colori distinguono le ali del medesimo giro, **non due linee**; la precedenza di percorrenza resta da scegliere. Rigenerazione della mappa interattiva: `python scripts/phase2_render_rt031_16_route_inline_v3.py --output <percorso-html>`.

## Risultato concreto e limite da non nascondere

**Esistono esempi a 16 giri che conservano tutti i treni-obiettivo e vere sequenze H30, ma nel confronto lasciano due intervalli di 215 minuti (3 ore e 35): 08:30–12:05 e 12:05–15:40 alla partenza del giro nell’esempio prima ovest. Questo peggioramento non è stato accettato e non è la proposta finale.**

Con i precedenti limiti centrali di 155 minuti ovest / 120 est, il minimo resta **18 giri** nel nuovo dominio. Non si passa automaticamente a quel numero: la scelta corrente resta 16.

Sono stati confrontati separatamente due ordini del medesimo otto, con sette offset di ripartenza intermedia da FS ciascuno, partenze ogni cinque minuti. I 14 test a 16 giri e limite di 210 minuti sono infeasibili; alcuni test a 215 passano. Il limite riguarda questo dominio, non ogni possibile orario, capolinea o regolazione.

## Miglioramento del confronto a 16 giri: 115 minuti

**Due orari diagnostici mantengono i 16 giri completi, le 29 fermate di progetto e le sequenze H30 sui cinque treni centrali di punta per ciascuna ala; il massimo intervallo tra partenze scende a 115 minuti.** La copertura garantita comincia alle **06:45** se parte prima l’ala ovest, alle **06:50** se parte prima l’est: non alle 07:00 del precedente confronto. La prima corsa da FS parte prima, perché deve attraversare entrambe le ali. Restano le due sostituzioni di treni-obiettivo nella seconda ala; non sono né cancellazioni di treni reali né scelte già accettate.

| Prima ala del giro unico | Copertura garantita da | Prima/ultima partenza FS | Prosecuzione intermedia FS | Massimo intervallo | Sosta intermedia nominale | Mezzi nominali / massimo nei 27 scenari |
|---|---|---|---:|---:|---:|---:|
| Ovest | 06:45 | 06:00 / 19:40 | +60 min | 115 min | 18.61 min | 4 / 5 |
| Est | 06:50 | 06:05 / 19:40 | +55 min | 115 min | 14.84 min | 4 / 4 |

Partenze dei **16 giri completi da Olgiate FS**, non orario adottato. Ogni giro torna a FS a metà e prosegue nell’altra ala, con la sosta intermedia contata nel viaggio:

| Giro | Prima ovest, FS | Prima est, FS |
|---:|---|---|
| 1 | 06:00 | 06:05 |
| 2 | 06:30 | 06:35 |
| 3 | 07:00 | 07:05 |
| 4 | 07:30 | 07:35 |
| 5 | 08:00 | 08:05 |
| 6 | 08:30 | 08:35 |
| 7 | 10:25 | 10:25 |
| 8 | 12:20 | 12:20 |
| 9 | 14:15 | 14:15 |
| 10 | 16:10 | 16:10 |
| 11 | 16:40 | 16:40 |
| 12 | 17:10 | 17:10 |
| 13 | 17:40 | 17:40 |
| 14 | 18:10 | 18:10 |
| 15 | 18:40 | 18:40 |
| 16 | 19:40 | 19:40 |

I 22 obiettivi ala/treno restano 22, ma due cambiano rispetto ai precedenti: nella seconda ala 07:26 → 09:56 verso Milano e 16:32 → 19:02 da Milano. Restano 308 controlli sito/treno per ciascun esempio; non viene inferita domanda passeggeri. Nel dominio di sette offset intermedi per ciascuna delle due precedenze e partenze ogni cinque minuti, **nessun test con copertura dalle 06:30 e limite 120 minuti riesce**; con le coperture 06:45/06:50 **nessun test con limite 110 minuti riesce**. Queste sono prove finite nel dominio dichiarato, non impossibilità universali.

**Resta una rinuncia reale:** H115 appare già dopo la punta mattutina e quindi non rispetta H60 fuori dalla sola morbida pesante 10–16. Né il primo ramo né le due sostituzioni ferroviarie né questi intervalli sono autorizzati. La continuità di veicolo e passeggeri, le paline e il fabbisogno di flotta restano condizionali.

**Quanto costa conservare H60 fuori 10–16?** Anche usando i due obiettivi ferroviari sostituiti nella seconda ala, e consentendo H120 fra le 10 e le 16, il minimo esatto nei 14 offset del dominio è **18 giri completi**. A 260 giorni ipotizzati sono **129.536,175 km/anno**, circa **+16,26%** rispetto a 111.419: un confronto, non una proposta di aumento. Perciò i 16 giri scelti e la combinazione H60 nelle spalle + H120 solo nella morbida pesante non coesistono in questo dominio. Il risultato non dimostra impossibilità su ogni possibile regolazione stradale o orario continuo.

## Confronto precedente a 120 minuti, conservato per tracciabilità

**Due ulteriori orari diagnostici mantengono 16 giri e riducono il massimo intervallo fra partenze a 120 minuti, senza togliere siti di progetto o cambiare percorso.** Non sono automaticamente accettati: iniziano la finestra di servizio garantita alle **07:00 anziché 06:30**, portano l’H90/H120 già dalle **08:30–08:35** in alcune ore, e sostituiscono **due precisi treni-obiettivo dell’ala che parte seconda**. Non sono soppressioni dei treni reali: la connessione diretta e breve a quei due treni non è più garantita nel confronto. Tutti i nuovi treni-obiettivo esistono nel GTFS datato.

| Ala percorsa per prima | Due obiettivi modificati solo nella seconda ala | Primo/ultimo giro da FS | Max intervallo tra partenze |
|---|---|---|---:|
| Ovest | Est: 07:26 → 09:56 per Milano; 16:32 → 19:02 da Milano | 06:00 / 19:40 | 120 min |
| Est | Ovest: 07:26 → 09:56 per Milano; 16:32 → 19:02 da Milano | 06:05 / 19:40 | 120 min |

Entrambe le alternative conservano cinque **corse complete H30 abbinate ai treni di punta** in ciascuna ala, 29 siti di progetto, gli stessi 16 giri e 115.143,267 km/anno ipotizzati. Hanno 22 obiettivi ala/treno e 308 verifiche ciascuna, ma **non gli stessi 22 del precedente confronto**: due cambiano. L’ala servita più presto non viene scelta dai dati sull’utenza, che mancano. La stessa impronta geografica non implica uguale accessibilità nelle diverse ore. I 120 minuti sono un limite per tutte le ore diurne del confronto: **non soddisfano H60 fuori dalla sola morbida pesante 10–16**. Non viene selezionata una delle due.

Una partenza FS rappresenta l’inizio del giro completo, non tutte le partenze dalle 29 fermate. Il JSON registra anche **ogni passaggio nominale ordinato alle fermate in ciascuno dei 16 giri** e la sosta intermedia. Le verifiche sono ingegneristiche condizionali, non orari approvati o domanda passeggeri osservata.

## Confronto che conserva tutti i precedenti treni

### Cosa significa H30 in questo confronto

Ogni punta contiene almeno cinque corse **complete** consecutive a 30 minuti. Sono H30 le corse effettivamente abbinate ai cinque treni mattutini e ai primi cinque arrivi serali di ciascuna ala, non soltanto una sequenza regolare altrove nella giornata. La sequenza si ritrova a ogni occorrenza di fermata, con l’orario traslato del tempo di viaggio. Sono mantenuti entrambi gli obiettivi ferroviari di ciascuna ala, non due servizi separati. Non si dichiara però la stessa finestra 07–09 / 16:55–18:55 simultanea per tutti i siti. Le finestre per sito sono esportate; la loro utilità e accettazione rimangono aperte. Gli scenari comuni non sono una probabilità di affidabilità o un test di ritardi indipendenti.

Tutti i 22 abbinamenti ala/treno precedenti sono conservati: cinque treni mattutini verso Milano 07:26–09:26, sei arrivi serali 16:32, 17:02, 17:32, 18:02, 18:32, 19:32 per ciascuna ala. Sono 308 verifiche per sito sui dati ferroviari già fissati al 28 settembre–2 ottobre 2026. Cambio minimo ipotizzato di tre minuti e limiti d’attesa precedenti invariati. Una stessa corsa d’ala non viene ricontata come due distinte coincidenze consecutive.

### Esempi completi, non orari selezionati

Le due tabelle sono alternative diagnostiche, **non due linee né due tipi di corsa nello stesso orario**. La partenza finale dal capolinea non è l’ultimo passaggio: il giro continua per entrambe le ali.

### Esempio: prima ovest

Sosta nominale a FS intermedia **18.61 minuti**, contata nel viaggio intercomunale. Mezzi condizionali: **4 nominali / 5** nel peggiore caso della griglia; non disponibilità certificata.

| Giro completo | Partenza FS verso prima ala | Prosecuzione FS verso seconda ala | Fine giro nominale |
|---:|---|---|---|
| 1 | 05:30 | 06:30 | 07:10 |
| 2 | 06:00 | 07:00 | 07:40 |
| 3 | 06:30 | 07:30 | 08:10 |
| 4 | 07:00 | 08:00 | 08:40 |
| 5 | 07:30 | 08:30 | 09:10 |
| 6 | 08:00 | 09:00 | 09:40 |
| 7 | 08:30 | 09:30 | 10:10 |
| 8 | 12:05 | 13:05 | 13:45 |
| 9 | 15:40 | 16:40 | 17:20 |
| 10 | 16:10 | 17:10 | 17:50 |
| 11 | 16:40 | 17:40 | 18:20 |
| 12 | 17:10 | 18:10 | 18:50 |
| 13 | 17:40 | 18:40 | 19:20 |
| 14 | 18:10 | 19:10 | 19:50 |
| 15 | 18:40 | 19:40 | 20:20 |
| 16 | 19:40 | 20:40 | 21:20 |

Sequenze H30 massimali alla partenza del giro: 05:30–08:30, 15:40–18:40.

### Esempio: prima est

Sosta nominale a FS intermedia **14.84 minuti**, contata nel viaggio intercomunale. Mezzi condizionali: **4 nominali / 4** nel peggiore caso della griglia; non disponibilità certificata.

| Giro completo | Partenza FS verso prima ala | Prosecuzione FS verso seconda ala | Fine giro nominale |
|---:|---|---|---|
| 1 | 05:35 | 06:30 | 07:11 |
| 2 | 06:05 | 07:00 | 07:41 |
| 3 | 06:35 | 07:30 | 08:11 |
| 4 | 07:05 | 08:00 | 08:41 |
| 5 | 07:35 | 08:30 | 09:11 |
| 6 | 08:05 | 09:00 | 09:41 |
| 7 | 08:35 | 09:30 | 10:11 |
| 8 | 12:05 | 13:00 | 13:41 |
| 9 | 15:40 | 16:35 | 17:16 |
| 10 | 16:10 | 17:05 | 17:46 |
| 11 | 16:40 | 17:35 | 18:16 |
| 12 | 17:10 | 18:05 | 18:46 |
| 13 | 17:40 | 18:35 | 19:16 |
| 14 | 18:10 | 19:05 | 19:46 |
| 15 | 18:40 | 19:35 | 20:16 |
| 16 | 19:40 | 20:35 | 21:16 |

Sequenze H30 massimali alla partenza del giro: 05:35–08:35, 15:40–18:40.

## Cosa è chiuso e cosa no

- **Chiusi come scelte di progetto:** 16 giri completi, stesso percorso, geometria e scelte fermate. I 18 giri del confronto H60/H120 non sono adottati.
- **Non chiusi:** un orario utile che rispetti insieme le esigenze; né i 215 minuti con tutti i vecchi treni né le alternative migliorate a 115 minuti con copertura 06:45/06:50 e due obiettivi ferroviari cambiati sono autorizzati.
- Il confronto esplicita la scelta ancora necessaria: quali primi treni/prime ore garantire in ciascuna ala e quale intervallo è tollerabile già dopo la punta mattutina. Se non è accettabile nessuna delle due alternative migliorate a 115 minuti, il conteggio di 16 giri non ha ancora un orario conclusivo nel dominio esaminato. Non si eliminano di nascosto treni, H30, territori o chilometri.
- Restano aperti manovre, paline, tempi osservati, blocchi completi, continuità fra giri successivi, calendario e costi extra-servizio. Nessuna approvazione operativa o PRIMARY/RUNNER-UP.

[Scelta dei 16 giri](../config/rt031_16_full_trips_authority_v3.json) · [Confronti e verifiche riproducibili (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/uniform_16_full_trips.json.gz)

Rigenerazione: `python -m scripts.phase2_close_rt031_line8_16_full_trips_v3` con `PYTHONPATH=.;src` su Windows.
