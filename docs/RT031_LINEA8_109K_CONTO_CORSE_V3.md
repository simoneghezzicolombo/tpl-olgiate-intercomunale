# Le 17 corse per ala: conto fermo del candidato da 109 mila km

**Questo documento non modifica nessuna corsa.** Fissa il testimone `JOINT_PHASE_18_20_17_TRIPS_PER_WING` già pubblicato, non una nuova proposta approvata.

## Come leggere gli orari

Orari calcolati, non orario al pubblico: marcia +10%, sosta ipotetica di 30 secondi a ogni nodo di fermata distinto. I secondi servono a rendere verificabili i conti, non indicano precisione osservata. Il rientro a FS comprende le soste intermedie ma non il recupero successivo. Le fermate e le piattaforme restano da autorizzare.

## Tutte le corse, senza aggiunte

| Corse | Partenza FS | Ovest: rientro FS | Ovest km | Est: rientro FS | Est km |
|---|---|---|---:|---|---:|
| O01 / E01 | 06:42:00 | 07:17:31 | 12.624 | 07:17:28 | 12.432 |
| O02 / E02 | 07:12:00 | 07:47:31 | 12.624 | 07:47:28 | 12.432 |
| O03 / E03 | 07:42:00 | 08:17:31 | 12.624 | 08:17:28 | 12.432 |
| O04 / E04 | 08:12:00 | 08:47:31 | 12.624 | 08:47:28 | 12.432 |
| O05 / E05 | 08:40:00 | 09:16:07 | 12.730 | 09:14:18 | 11.894 |
| O06 / E06 | 09:40:00 | 10:16:07 | 12.730 | 10:14:18 | 11.894 |
| O07 / E07 | 10:40:00 | 11:16:07 | 12.730 | 11:14:18 | 11.894 |
| O08 / E08 | 11:40:00 | 12:16:07 | 12.730 | 12:14:18 | 11.894 |
| O09 / E09 | 12:40:00 | 13:16:07 | 12.730 | 13:14:18 | 11.894 |
| O10 / E10 | 13:40:00 | 14:16:07 | 12.730 | 14:14:18 | 11.894 |
| O11 / E11 | 14:40:00 | 15:16:07 | 12.730 | 15:14:18 | 11.894 |
| O12 / E12 | 15:40:00 | 16:16:07 | 12.730 | 16:14:18 | 11.894 |
| O13 / E13 | 16:40:00 | 17:16:07 | 12.730 | 17:14:18 | 11.894 |
| O14 / E14 | 17:10:00 | 17:46:07 | 12.730 | 17:44:18 | 11.894 |
| O15 / E15 | 17:40:00 | 18:16:07 | 12.730 | 18:14:18 | 11.894 |
| O16 / E16 | 18:10:00 | 18:46:07 | 12.730 | 18:44:18 | 11.894 |
| O17 / E17 | 18:40:00 | 19:16:07 | 12.730 | 19:14:18 | 11.894 |

**34 corse d’ala/giorno = 420.330729 km/giorno.**
**× 260 giorni ipotetici = 109285.990 km/anno.** Deposito e riposizionamenti esclusi.
I km in tabella sono arrotondati; il totale utilizza le distanze non arrotondate. Cambiare soltanto l’ora di una di queste corse lascia invariato questo totale.

Le prime quattro corse sono ovest A/est B. Dalla quinta diventano ovest B/est A. I sensi hanno distanze leggermente diverse: questa differenza è esplicita nel conto.

## Passaggi nei luoghi e intervalli

[Tabella completa di tutti i passaggi, luogo per luogo](RT031_LINEA8_109K_PASSAGGI_PER_LOCALITA_V3.md). Ogni riga ha corsa, occorrenza, arrivo, partenza, rientro FS e intervallo dal passaggio precedente. I cambi di senso sono segnalati.

Un intervallo fra identità incontrate non prova che il passeggero possa usare entrambi i lati: la tabella non autorizza le fermate. Il [controllo delle punte](RT031_LINEA8_SCHEDA_CONCLUSIVA_DI_AVANZAMENTO_V3.md) mostra dove la promessa H30 del testimone non è soddisfatta per l’intera finestra. Non cambiamo il significato di H30 per dichiararlo valido.

## Perché un confronto precedente risultava da 121 mila km

**Era un altro insieme di corse, non il medesimo orario traslato.** Questo è solo il ponte contabile con quel risultato storico, non una modifica del candidato sopra.

| Giro d’ala | Corse/giorno qui | Corse/giorno nel confronto | Variazione km/anno |
|---|---:|---:|---:|
| east_A | 13 | 19 | +18553.880 |
| east_B | 4 | 0 | -12928.995 |
| west_A | 4 | 19 | +49232.954 |
| west_B | 13 | 0 | -43028.133 |

Totale: **34 → 38 corse d’ala/giorno**, oltre alla diversa composizione dei sensi. La differenza non è causata dai minuti sull’orologio.

## Un problema concreto da risolvere, senza cambiare i conti

A Olgiate sud le corse O04, O05 e O06 passano rispettivamente alle **08:43:23, 08:44:49, 09:44:49**. Il cambio di senso concentra due passaggi a circa un minuto e mezzo di distanza, seguiti da un intervallo di un’ora. Sono passaggi modellati, non una garanzia di salita su entrambi i lati.

Questo esempio localizza una transizione punta/morbida da verificare; da solo non dimostra né che basti traslare le corse né che servano necessariamente più km. Prima di dichiarare conclusa la proposta occorre verificare H30/H60 lungo l’intera finestra di servizio di ogni località, in relazione ai treni e al senso utile al passeggero. Ogni correzione dovrà riportare separatamente le corse spostate e quelle eventualmente aggiunte o modificate.

## Cosa è dimostrato e cosa no

Dimostrati nel modello: elenco delle corse, somma dei km, tempi ottenuti dalle ipotesi dichiarate. Non dimostrati: servizio H30 completo nelle punte, fermate autorizzate, coincidenze affidabili, costi e km di deposito, calendario reale. Nessuna selezione PRIMARY/RUNNER-UP è autorizzata.

Il prossimo eventuale cambiamento va registrato come spostamento, aggiunta, soppressione o modifica del percorso, con variazione chilometrica separata. Questa tabella resta il riferimento invariato.
