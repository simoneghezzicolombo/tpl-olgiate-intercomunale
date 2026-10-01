# Linea 8 — sera e punte: verifica congiunta, senza nuovi tagli nascosti

## Conclusione

**Spostare corse verso la sera è possibile, ma non basta per dichiarare chiusa la proposta.** Abbiamo ora misurato le finestre H30 effettive per i passeggeri nel modello, non soltanto contato le partenze di punta. Il confronto conserva tutti i 28 siti, i due tracciati già analizzati e l'ultima partenza FS alle 20:40.

Il calendario da 115.800 km con H90 intermedio mantiene le cinque partenze di punta, ma la finestra H30 comune a tutte le località, nei due versi e in tutti i casi marcia/sosta, è di circa **106 minuti al mattino e 109 al pomeriggio**. Il percorso locale corretto arriva a circa **110 e 109 minuti**. Non sono due ore. Questo quantifica il limite già esplicitamente non certificato nel confronto precedente, non introduce una nuova approvazione o una nuova fascia obbligatoria.

Il riferimento di due ore è quello già confrontato nelle analisi delle punte. Cerchiamo anche finestre anticipate, come richiesto dall'utente; non imponiamo 07–09/17–19 come legge. Il risultato non dimostra che H30 sia impossibile a 111.419 km su qualunque altra rete o altro orario.

## Tre compromessi espliciti

Tutti i numeri sono **km di servizio su 260 giorni**, esclusi extra e deposito. A sinistra il percorso con controflusso locale lungo; a destra quello con collegamenti locali brevi in entrambi i versi.

| Confronto | Due ore comuni H30 AM e PM nel modello | Intervallo intermedio massimo | Km: precedente / corretto | Mezzi nominali condizionali: precedente / corretto |
|---|---|---:|---:|---:|
| Estensione serale H90 già costruita | No | 90 min | 115.800 / 130.567 | 4 / 4–5 |
| Ridistribuzione più forte, stessa quantità di corse | Sì, esempio 06:45–08:45 e 16:30–18:30 | 111 min, oppure 120 con orari più regolari | 115.800 / 130.567 | 6 / 6–7 |
| Conservare il calendario H90 e aggiungere quattro corse d'ala | Sì, esempio 06:45–08:45 e 17–19 | 90 min | 128.717 / 145.166 | 6 / 6 |

“Nominale” significa marcia +10%, 30 secondi di sosta per evento, recupero 5/10/15 minuti per corsa d'ala. I massimi nelle sensibilità sono rispettivamente **5 / 6**, **7 / 8**, **6 / 7** mezzi. Non sono turni validati né preventivi dell'operatore.

**Non proponiamo di adottare automaticamente nessuna riga.** La seconda conserva i km ma concentra corse al mattino e chiede più autobus contemporanei. La terza mantiene H90, non H60, nel mezzo e costa di più. Nessuna riga combina già piccolo sforamento, H60 intermedio, due ore H30 comuni, collegamenti locali brevi e tutti gli altri requisiti.

## Perché cinque partenze H30 possono non bastare

Ogni singola sequenza di cinque partenze ogni trenta minuti copre fino a 150 minuti di disponibilità per un passeggero disposto ad aspettare al massimo trenta minuti. Ma le fermate lungo un giro vedono quelle partenze in orari diversi. La finestra che vale **contemporaneamente per tutti**, anche considerando marcia e soste diverse, può essere più corta di due ore.

La metrica parte dall'istante in cui il passeggero è pronto alla salita: non include cammino alla fermata, viaggio sul bus o coincidenza ferroviaria. Perciò un successo H30 **non elimina i 31–32 minuti di controflusso** del percorso precedente.

## Testimoni agli stessi km: cosa cambia concretamente

Le cinque partenze mattutine originali restano immutate. Si anticipa una corsa REST per ala e si distribuiscono le altre come segue; A/B indicano gli orientamenti dei percorsi, non nuove linee pubbliche:

| Blocco REST | Ovest B | Est A |
|---|---|---|
| Rinforzo mattutino | 08:25, 08:55 | 08:18, 08:48 |
| Variante intermedia con massimo 111 minuti | 10:39, 12:29, 14:20 | Uguale |
| Oppure variante intermedia a due ore | 10:10, 12:10, 14:10 | Uguale |
| Banca pomeridiana ampliata | 16:10, 16:40, 17:10, 17:40, 18:10, 18:40 | Uguale |
| Sera, invariata | 19:40, 20:40 | Uguale |

Sono sempre 18 corse per ala, con gli stessi conteggi per percorso: dunque stessi km. Gli orari 10:39/12:29/14:20 sono un testimone tecnico, **non una proposta di orario pubblico memorabile**. La variante a due ore esplicita un'alternativa più regolare ma meno frequente. Il rinforzo mattutino si sovrappone alle ultime corse nell'altro orientamento: il calcolo dei mezzi include tale sovrapposizione.

Le finestre 06:45–08:45 e 16:30–18:30 passano il controllo indipendente in entrambi i versi per tutti i 27 siti non-hub e tutti i nove casi marcia/sosta. Il risultato resta condizionato a salite ipotetiche e all'unione ottimistica delle occorrenze: nessuna certificazione fisica di fermata o continuità passeggeri.

## Riparazione per sola aggiunta: dominio dichiarato

Abbiamo esaminato **tutti i 16 sottoinsiemi** delle seguenti quattro aggiunte, separatamente per i due percorsi:

- Ovest A alle 09:04 nel percorso precedente, 09:03 in quello corretto.
- Est B alle 08:57.
- Ovest B alle 19:10.
- Est A alle 19:10.

Solo il sottoinsieme completo supera il confronto delle due ore comuni nelle due punte, nei due versi e in tutta la griglia. Il minimo chilometrico **in questo dominio di sola aggiunta** è quindi 128.717 / 145.166 km. Non è un minimo globale: i testimoni di redistribuzione appena descritti passano a meno km, con peggioramento della morbida e del fabbisogno di mezzi.

Le cinque corse AM e le partenze 19:40/20:40 restano immutate: conservano quindi i treni mattutini obiettivo 07:26–09:26 e le due opportunità serali 19:32/20:32 del giorno congelato. Altre coincidenze possono cambiare con la redistribuzione; **non abbiamo verificato un orario ferroviario corrente**. Non stimiamo probabilità empiriche di coincidenza né domanda da Google Popular Times.

## Decisione progettuale ancora aperta

Questo lavoro separa le scelte reali, invece di mascherarle con la dicitura “H30 in punta”:

1. Durata, posizione e direzioni della promessa di punta da comunicare al passeggero.
2. Minima frequenza accettabile nel mezzo della giornata: H60, H90 o circa H120 non sono equivalenti.
3. Compromesso fra tempi locali nei due versi, produzione chilometrica e mezzi contemporanei.

Non è registrata alcuna nuova preferenza numerica, nessun budget aggiuntivo e nessuna selezione PRIMARY/RUNNER-UP. Serve scegliere fra compromessi verificati, oppure autorizzare una diversa ricerca: **non presentiamo una soluzione conforme a tutto quando nessun testimone lo è**.

## Evidenze riproducibili

- [36 confronti: 32 per sola aggiunta e quattro redistribuzioni](../outputs/phase2/rt031_line8_local_shortcuts_v3/evening_peak_closure.json).
- [Generatore e algebra degli intervalli](../scripts/phase2_audit_rt031_line8_evening_peak_closure_v3.py), [test indipendenti](../tests/test_phase2_rt031_line8_evening_peak_closure_v3.py).
- [Orari di partenza e mappe invariati per famiglia](RT031_LINEA8_SPOSTARE_CORSE_ALLA_SERA_V3.md).

```powershell
$env:PYTHONPATH='.;src'
python -m scripts.phase2_audit_rt031_line8_evening_peak_closure_v3
python -m unittest discover -s tests -p test_phase2_rt031_line8_evening_peak_closure_v3.py
```

Le intersezioni sono continue, non campionate ogni cinque o quindici minuti. Le occorrenze sono conservate nei dati; solo la metrica esplicitamente ottimistica aggrega le identità. Le finestre devono valere uguali in tutti i casi, non cambiare con lo scenario. Vincoli stradali completi, salite autorizzate, turni, deposito e costi totali restano non certificati.
