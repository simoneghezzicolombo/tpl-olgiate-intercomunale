# Linea 8 — stato unico della proposta e controllo H30 passeggeri

Il riferimento contabile invariato è ora disponibile [corsa per corsa](RT031_LINEA8_109K_CONTO_CORSE_V3.md), con [tutti i passaggi per località](RT031_LINEA8_109K_PASSAGGI_PER_LOCALITA_V3.md). Distingue esplicitamente le 34 corse del caso 109k dalle 38 del confronto 121k: traslare soltanto gli orari non cambia i chilometri.

## Il risultato che corregge la lettura precedente

**109.285,990 km/anno non sono ancora il costo di un servizio H30 in punta validato.** Sono il costo del testimone con 17 corse per ala, soste ipotetiche di mezzo minuto e +10% sulla marcia. Il nuovo controllo delle attese al luogo di salita mostra che quel calendario non soddisfa la promessa nelle due ore di riferimento.

Non bastano quattro partenze ogni mezz'ora: un passeggero che arriva dopo l'ultima deve trovare un'altra opportunità entro trenta minuti. Contiamo quindi esattamente gli intervalli di tempo in cui, essendo pronto alla fermata, non trova una partenza entro trenta minuti. Per il ritorno il punto di partenza è FS verso la specifica località. Non è una misura del tempo totale di viaggio né una garanzia di coincidenza.

## Copertura temporale del testimone attuale

| Finestra di confronto | Luoghi con intera finestra H30 verso FS | Luoghi con intera finestra H30 da FS |
|---|---:|---:|
| 07–09 | 0/27 | 0/27 |
| 17–19 | 12/27 | 0/27 |
| 06:30–08:30 | 1/27 | 27/27 |
| 16:30–18:30 | 15/27 | 27/27 |

Questi numeri **non dicono che non passa nessun bus**: dicono quanti luoghi hanno l'intera finestra coperta senza un'attesa potenziale oltre 30 minuti. Sono conteggi di identità ipotetiche, non percentuali di popolazione. Il controllo è già ottimistico: presume accessibili e utilizzabili tutte le occorrenze, senza distinguere l'eventuale attraversamento fra lati. Un fallimento confuta la promessa per questo testimone; un successo non autorizza le fermate.

07–09/17–19 rimangono un riferimento diagnostico, non una legge imposta all'utente. Anticipare la punta per i treni è ammissibile come confronto, ma occorre verificare entrambe le direzioni di viaggio, non soltanto cambiare l'etichetta alla fascia.

## Quanto costa correggerlo soltanto aggiungendo corse?

È stato risolto un problema di copertura a variabili intere: minimo numero di **chilometri aggiuntivi** fra 344 corse complete d'ala possibili, entrambi gli orientamenti, partenze ogni cinque minuti fra 06:00–09:30 e 16:00–19:30. Tutte le corse esistenti restano ferme. L'obiettivo è il costo chilometrico della riparazione, non un punteggio politico o la selezione di una rete.

Il minimo trovato e verificato continuamente sugli intervalli è **74,196637 km/giorno aggiuntivi**. Un testimone ottimo usa sei corse d'ala: la produzione sale a **128.577,116 km/anno**, prima degli extra, **17.158,116 km oltre il tetto**. Non è dimostrata l'unicità delle corse scelte. Questo risultato NON prova l'impossibilità di H30 entro 111.419 km: prova che aggiungere corse a questo preciso calendario, nel dominio esplorato, non basta a rispettare il tetto.

Non proponiamo quindi di spendere 128.577 km, né di rinunciare a H30. Il prossimo problema da risolvere è la **ricostruzione congiunta dell'orario**, permettendo di spostare e sostituire corse, con copertura temporale passeggeri come requisito esplicito. Accumulare riparazioni del testimone attuale è una strada quantitativamente sfavorevole.

## Ricostruzione da zero eseguita nello stesso avanzamento

Abbiamo quindi rimosso tutti i vincoli sulle vecchie partenze e risolto anche questo problema: quattro cammini d'ala, **676 corse possibili** su griglia di cinque minuti fra 06 e 20, disponibilità passeggeri 06–19, attesa massima 30 minuti nelle punte di riferimento e 60 nel resto. Soste di mezzo minuto, marcia +10%; nessuna soglia di qualità ferroviaria o peso di domanda aggiunti.

Il minimo chilometrico nel dominio è **127.490,206 km/anno prima degli extra**: **16.071,206 oltre il tetto**. Il testimone usa 40 corse d'ala (20 per ala) e supera il ricontrollo continuo di tutti gli intervalli per le 27 identità non-FS, in entrambi i versi di viaggio. Le corse vecchie non sono obbligatorie: il superamento non è quindi soltanto un effetto dell'aggiunta di corse al vecchio orario.

È un risultato limitato ma più forte: **nel dominio di quelle quattro ali e di quella griglia, l'orario non basta a far rientrare il confronto 06–19 con H30/H60 passeggeri nel tetto**. Non esclude percorsi più corti, corse parziali, altri calendari o altre fasce concordate. La regolarità dei minuti, i tempi di viaggio e le coincidenze non sono ottimizzati, e l'uso di tutte le occorrenze rimane ipotetico: il risultato è già favorevole al modello, non una proposta approvata.

La flotta di 5/6/6 mezzi calcolata sui blocchi del testimone con 5/10/15 minuti di recupero **non è il minimo di flotta fra tutti gli orari a pari chilometri**. Il solver minimizza soltanto i km; le soluzioni equivalenti possono avere fasi e sovrapposizioni diverse. Non attribuiamo quel fabbisogno a ogni possibile orario.

Artefatto: `rebuilt_timetable.json`, con partenze, dominio, ottimalità del problema finito e blocchi del testimone. Una soluzione finale richiede adesso modificare un elemento esplicito del problema o ampliare il dominio fisico, non continuare ad aggiustare soltanto i minuti della medesima famiglia.

## Anche le punte anticipate sono state ricostruite, non solo etichettate

Su indicazione dell'utente si confrontano fasce anticipate, senza considerare 07–09/17–19 una legge. Stesso orizzonte passeggeri 06–19, stesso H60 nel resto, stessa geometria e soste; in ogni caso tutte le partenze sono ricostruite da zero.

| Finestre H30 lato passeggeri | Minimo km annuo nel dominio, prima degli extra | Differenza dal cap |
|---|---:|---:|
| 07–09 e 17–19 | 127.490,206 | +16.071,206 |
| 06:45–08:45 e 16:45–18:45 | **121.115,696** | **+9.696,696** |
| 06:30–08:30 e 16:30–18:30 | 127.490,206 | +16.071,206 |

La differenza dipende dalla sovrapposizione fra intervalli coperti e transizioni, non da domanda stimata. Il confronto a −15 minuti usa 38 corse d'ala (19 per ala) nel testimone. Non viene selezionato per il solo minor costo: viaggi diretti, semplicità, flotta e coincidenze restano dimensioni separate, e la fermata fisica è ancora ipotetica. Nessun risultato è un limite inferiore continuo oltre la griglia e i quattro cammini fissati.

Questo riduce il divario del confronto più economico esaminato a circa **8,0% della sua produzione**, ma non elimina il deposito né autorizza un taglio territoriale. I 260 giorni sono ancora un'ipotesi annuale, non un calendario dell'operatore. Artefatto: `rebuilt_peak_comparison.json`.

## Fermate: ora un registro unico

`provisional_stop_register.csv` elenca **28 identità/siti**, includendo FS: 26 identità d'inventario incontrate e due esigenze nuove (Olgiate sud e San Zeno/Via Cantù). Sono luoghi da validare, non 28 paline autorizzate né un conteggio di piattaforme direzionali. Ogni riga esplicita `boarding_authorised=false`.

Geometria, accessibilità potenziale e siti restano quelli già documentati; non sono stati eliminati territori o fermate per migliorare il risultato.

## Chiusura delle evidenze

`proposal_readiness.json` riunisce i requisiti, la fonte utilizzabile, la semantica e ciò che manca. Restano non chiusi: orario che soddisfi davvero la promessa H30/H60, fermate e lati utilizzabili, tempi osservati, deposito/calendario effettivi, orario ferroviario applicabile e conto economico. Il fabbisogno di quattro mezzi del testimone precedente non certifica quello della riparazione.

Non autorizziamo PRIMARY o RUNNER-UP, non scegliamo `decision_budget_km` o `uncertainty_band_min`, non inventiamo domanda passeggeri né probabilità. Non si dichiara pronto per Agenzia/operatore un orario che questi controlli hanno confutato.
