# Linea 8 — ripartenza corretta: ogni corsa percorre tutto l’otto

**Il chiarimento del committente sostituisce l’impostazione a corse d’ala indipendenti.** Una sola linea, **stesso percorso completo per ogni corsa commerciale**, entrambe le ali, nessuna variante pubblica limitata a FS. La stazione è anche fermata intermedia con permanenza a bordo prevista, non un cambio obbligatorio per passare nell’altra ala.

La precedente proposta da **31 giri d’ala** non viene più presentata come soluzione finale. Non viene nemmeno trasformata in 31 giri completi: sarebbero circa 223.090 km/anno. I test precedenti restano prove del loro dominio, non prove che fosse soddisfatta questa richiesta.

## Cosa rimane confermato

- Geometria stradale di base, Olgiate sud e San Zeno/Via Cantù inclusi.
- Nuova fermata di progetto **Arlate/Via Nuova Provinciale**; esclusa N0655 in Via Indipendenza per la segnalazione del cavalcavia, senza spostamento automatico nelle immediate vicinanze.
- **29 siti di progetto**, non paline fisiche autorizzate.
- H30 nelle punte, utilità ferroviaria e intercomunale, attenzione al riferimento di 111.419 km. Il precedente assenso a +41,883 km per uno scenario diverso non è un nuovo budget generale.
- Manovre e fermate fisiche si verificano successivamente; i relativi limiti non sono rimossi.

## Conti ora espressi in corse complete

Un giro di entrambe le ali misura **27.678670 km**, senza nuove deviazioni. Il calendario da 260 giorni resta un’ipotesi comparativa, non il calendario approvato.

| Giri completi al giorno | Km di servizio/anno | Scostamento da 111.419 |
|---|---:|---:|
| 15 | 107946.813 | -3472.187 |
| 16 | 115143.267 | +3724.267 |
| 31 | 223090.079 | +111671.079 |

**Questa tabella è aritmetica, non dimostra che 15 o 16 corse soddisfino frequenze e treni.** Nessuno di questi numeri è adottato come nuovo orario.

## Primo orario ricostruito nel contratto corretto

Esaminate separatamente le due possibili partenze da FS sullo stesso otto diretto (prima ovest oppure prima est). **Ogni orario usa una sola sequenza, uguale per tutte le corse:** le due alternative non vengono mescolate. I percorsi completi, archi ordinati e passaggio intermedio a FS sono conservati nel file macchina.

FS intermedia ha un orario di passaggio/partenza fissato. Il bus può arrivare prima e attendere con il passeggero a bordo: questo tempo è dichiarato, non eliminato dal viaggio. Il recupero di 5/10/15 minuti è ora confrontato **una volta per giro completo**, non automaticamente ad ogni ala. La sosta pubblica intermedia è distinta dal recupero. Sono assunzioni ingegneristiche da validare, non nuovi dati osservati.

Nel confronto sono mantenuti, senza considerarli tutti preferenze esplicitamente scelte dall’utente:

- H30 per sito verso/dalla stazione nelle finestre comuni 07–09 e 16:55–18:55;
- attese massime ereditate 155/120 minuti, H60 alle estremità e servizio di riferimento 06:30–19:40;
- tutti i precedenti treni-obiettivo, per tutti i siti: cambio ipotizzato di 3 minuti e attesa treno→bus di 3–8 minuti;
- griglia corsa/sosta ereditata, senza trasformarla in probabilità empirica.

| Prima ala | Minuti da partenza iniziale a ripartenza intermedia FS | Minimo giri completi | Km/anno |
|---|---:|---:|---:|
| Ovest | 55 | 23 | 165518.446 |
| Ovest | 60 | 20 | 143929.084 |
| Ovest | 65 | 20 | 143929.084 |
| Ovest | 70 | 27 | 194304.263 |
| Ovest | 75 | 27 | 194304.263 |
| Ovest | 80 | 27 | 194304.263 |
| Ovest | 85 | 24 | 172714.900 |
| Est | 50 | 27 | 194304.263 |
| Est | 55 | 20 | 143929.084 |
| Est | 60 | 20 | 143929.084 |
| Est | 65 | 23 | 165518.446 |
| Est | 70 | 27 | 194304.263 |
| Est | 75 | 27 | 194304.263 |
| Est | 80 | 27 | 194304.263 |

**Minimo nel dominio esaminato: 20 giri completi, 143929.084 km/anno.** Non è una proposta di aumento del budget. È la dimostrazione che non basta rietichettare il vecchio orario mantenendone tutte le condizioni.

Il confronto usa partenze ogni cinque minuti e, per il passaggio intermedio, sette offset per ciascun ordine, dalla prima partenza compatibile con lo stress fino a +30 minuti. Non è un minimo globale su ogni possibile offset, capolinea o regola d’orario. I testimoni con meno corse possono iniziare il primo giro verso le 05:30 e terminare molto dopo l’ultima partenza: anche questo è esplicitato nel registro, **non approvato**. I mezzi calcolati sono quelli dei testimoni prodotti; non è stato ottimizzato separatamente il numero di mezzi fra tutti gli orari con lo stesso numero di corse.

La radice a FS è usata per questo confronto, non decide già il capolinea fisico. Attraversare FS **all’interno** della corsa completa è diverso da restare a bordo fra due corse complete successive: quest’ultima continuità va esplicitata nei blocchi mezzo, non dedotta dal nome della linea. Non si promettono tutti i viaggi intercomunali senza cambio sulla sola base dell’identità del percorso.

## Passo successivo circoscritto

**Riesaminare le condizioni temporali ereditate, non tornare a due servizi o introdurre corse corte.** In particolare distinguere l’obiettivo H30 in punta dalla scelta tecnica di finestre identiche al minuto per ogni sito, e l’integrazione ferroviaria dall’obbligo di servire tutti gli stessi treni da entrambe le ali con una finestra di soli 3–8 minuti. Queste scelte vanno confrontate con i tempi intercomunali, mantenendo visibile cosa si guadagna e cosa si perde. Nessuna riduzione di H30, rinuncia ai treni, modifica della geometria o maggiorazione di budget è adottata qui.

[Contratto corretto del committente](../config/rt031_uniform_complete_line_authority_v3.json) · [Percorsi completi, orari e prove (JSON gzip)](../outputs/phase2/rt031_line8_local_shortcuts_v3/uniform_complete_line_rebuild.json.gz)

Rigenerazione: `python -m scripts.phase2_rebuild_rt031_uniform_complete_line_v3` con `PYTHONPATH` su radice e `src`. Le prove usano il grafo e i tempi già fissati nelle fonti precedenti; nessuna autorizzazione stradale, di palina o di esercizio viene dedotta dal risolutore.
