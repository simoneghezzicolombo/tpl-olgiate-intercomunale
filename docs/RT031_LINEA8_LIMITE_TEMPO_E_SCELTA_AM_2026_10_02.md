# Linea 8 — chiusa la domanda sul tempo minimo, esplicita la scelta mattutina

La proposta unica confermata non è modificata: 16 giri completi, 27 siti, calendario feriale 2027 e H30 nelle banche di punta. Il controllo riguarda il residuo AM; non riapre il progetto intercomunale.

## Il grafo non nasconde una scorciatoia risolutiva

Verificati due obiettivi — distanza e marcia modellata — con tre livelli di protezione delle direzioni di arrivo: tutti gli archi entranti, solo San Zeno, oppure nodi soltanto. Stessi 14 eventi est ordinati, stessi archi FS, nessun passaggio FS interno, nessuna inversione immediata, Mirasole/Cartiglio/Tessitura esclusi. Le restrizioni a storia completa non sono certificate.

Sei ricerche restituiscono 4 tracciati distinti, su due coppie estreme di costo; la libertà di direzione cambia alcune occorrenze ma non migliora il costo minimo. Il minimo di distanza con direzioni protette riproduce la base. Il minimo di tempo aggiunge **41.62 m** e riduce la marcia modellata di **12.47 secondi** (circa 13.72 nello stress di marcia ×1,1). Anche il dominio con direzioni libere ha lo stesso minimo di tempo.

Il tratto diverso è a Calco: invece di Via Trieste/Vittorio Veneto, Via San Vigilio → rotatoria → Via Cornello → Via Notaio Carlo Mandelli. Non aggiunge una fermata a Cornello e non ne certifica accesso o sicurezza. Non viene adottato: il piccolo guadagno del proxy non dimostra un vantaggio reale di esercizio.

La finestra comune per servire con la stessa corsa i cinque arrivi da Milano a :02/:32 e le cinque partenze verso Milano a :26/:56 (54 minuti dopo il rispettivo arrivo) passa da **13.40 a 27.12 secondi**. Anche con fase continua bilanciata il limite è 13.56 secondi per lato. Vale soltanto per questo ordine, grafo e modello: non è impossibilità generale né una probabilità.

Il confronto completo minimo-tempo + Scarpone + sera +2 verifica i nove ledger, 27 blocchi e tutti i 296 flussi; 110504.085 km commerciali feriali 2027, massimo 4 mezzi condizionali. Non crea una soluzione mattutina robusta per definizione.

## Esempio completo di compromesso AM, non adottato

Sul tracciato confermato, con il bypass Scarpone già studiato e sera +2, è ricostruito il caso **prime cinque partenze est −2 minuti**: 06:03, 06:33, 07:03, 07:33, 08:03. FS intermedia conserva le partenze ovest; tutte le corse continuano a percorrere entrambe le ali.

Conserva H30, cap di attesa e 16 giri, 110334.948 km feriali 2027 e massimo 4 mezzi nei 27 casi. Il margine minimo verso Milano aumenta da 0,223 a 2,223 minuti dopo i 3 minuti assunti di cammino. Non è una soglia di affidabilità adottata. Servizio nominale aggiunto rispetto alla base: 21.006 minuti/giorno, 88.925 ore sui 254 giorni; non sono turni autista né costo certificato.

| Treno da Milano in arrivo FS | Bus est base | Bus est nel confronto | Attesa base → confronto |
|---|---|---|---|
| 06:02:00 | 06:05:00 | 06:33:00 | 3 → 31 min |
| 06:32:00 | 06:35:00 | 07:03:00 | 3 → 31 min |
| 07:02:00 | 07:05:00 | 07:33:00 | 3 → 31 min |
| 07:32:00 | 07:35:00 | 08:03:00 | 3 → 31 min |
| 08:02:00 | 08:05:00 | 09:00:00 | 3 → 58 min |

L’aumento dell’attesa non è occultato dalla copertura geografica o dall’assenza di nuovi km. Sono salvati tutti gli altri flussi Lecco/Milano, nominali e stress dello stesso bus. Anticipare −1, −3 o −4 resta un confronto, non una soluzione scelta: gli effetti per treno sono nel JSON.

## Conclusione che non rimanda a un nuovo giro di ricerca

**Chiusa la verifica interna del tempo minimo nel dominio dichiarato.** La soluzione non può essere proclamata pronta nascondendo il compromesso AM. Il committente deve scegliere se prioritizzare le cinque coincidenze verso Milano, accettando la perdita del bus immediato dai cinque arrivi, oppure mantenere la fase confermata finché tempi osservati giustifichino un margine diverso. Nessuna scelta viene attribuita automaticamente al committente.

Restano prove fisiche e operative non sostituibili con file: accosti/sagoma, tempi reali e trasferimento, permanenza a bordo, turni/deposito e costo completo; treni 2027 e sabato separato. Le località e i quartieri non già certificati restano esplicitamente tali nel dossier. Non si dichiara che tutti gli obiettivi storici siano soddisfatti.

[Audit macchina e registri](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_order_runtime_closure_20261002.json) · [Tracciati completi e tratto Calco](../outputs/phase2/rt031_line8_local_shortcuts_v3/fixed_order_runtime_comparison_20261002.geojson)
