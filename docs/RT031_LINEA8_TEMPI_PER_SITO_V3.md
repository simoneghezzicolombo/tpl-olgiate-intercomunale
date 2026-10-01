# Linea 8 — tempi nominali per sito, nei due versi

Audit del solo testimone **H90, ultima partenza FS 19:40**, non selezionato. Non è una nuova proposta e non approva H90. Tutti i 27 siti non-hub sono elencati; FS è il ventottesimo.

Minuti sul bus nel modello nominale: marcia +10% e soste di 30 secondi. Sono esclusi cammino, attesa e cambio treno. Nessuna soglia di accettabilità viene decisa qui. Le cifre sono arrotondate, non misure sul campo.

| Sito | Da FS, min | Verso FS, min | Passaggi distinti per viaggio breve nei due versi |
|---|---:|---:|---|
| Arlate - B.vio Brivio - Madonnina | 27.0 | 12.1 | No |
| Arlate - Cantina Pirovano | 23.1 | 16.0 | No |
| Brivio - Via Como (pizzeria / Bar Cristallo) | 15.9 | 23.3 | No |
| Calco - Via Virgilio | 31.5 | 7.7 | No |
| Olgiate Molgora - Scarpone | 8.4 | 32.4 | No |
| Olgiate Molgora - Via Della Salute | 31.2 | 9.7 | No |
| Olgiate Molgora - Via Statale | 33.2 | 7.7 | No |
| Perego - Statale / Via S. Caterina | 14.5 | 26.4 | No |
| Santa Maria Hoè - Alduno | 10.2 | 30.6 | No |
| Rovagnate - Statale / Via Lombardia | 13.0 | 27.9 | No |
| Rovagnate - Statale / AGIP | 11.9 | 29.0 | No |
| Santa Maria Hoè - Via Como / Alpino | 24.4 | 16.5 | No |
| Santa Maria Hoè - Via Giovanni XXIII / Tremonte-Via Leopardi | 26.7 | 14.2 | No |
| S. Maria Hoè - S.P. 58 ang. Via Cenisio | 28.6 | 12.3 | No |
| Brivio - Vaccarezza | 13.8 | 25.4 | No |
| Brivio - Via Bergamo (Scuola Materna) | 18.0 | 21.1 | No |
| Brivio - beverate (cariplo) | 8.4 | 30.8 | No |
| Brivio - beverate (paese) | 10.3 | 28.8 | No |
| Brivio - beverate (quattro strade) | 11.8 | 27.3 | No |
| Calco - via Nazionale | 28.8 | 10.4 | No |
| S.Maria Hoe' | 23.6 | 17.3 | No |
| Santa Maria Hoè - Tremonte / Via Trento | 25.6 | 15.2 | No |
| Hoe' | 21.5 | 19.4 | No |
| Rovagnate - vinicola ghezzi | 15.7 | 25.2 | No |
| Calco - via nazionale (peugeot) | 7.0 | 32.2 | No |
| San Zeno/Via Cantu | 2.5 | 2.6 | Sì |
| Olgiate sud | 4.3 | 4.1 | Sì |

## Come leggere il risultato

Il giro resta asimmetrico: risolvere i viaggi lunghi di Olgiate sud e San Zeno non rende brevi entrambi i versi in tutte le altre località. Una percentuale di accesso pedonale invariata non misura questi tempi. Non viene calcolata alcuna media pesata per passeggeri.

Per i siti ripetuti, il passaggio iniziale serve per scendere da FS; quello finale per salire verso FS. Il JSON conserva entrambi gli identificativi di occorrenza e la corsa: non sono una sola promessa di servizio. Paline, lato strada e continuità passeggeri non sono autorizzati. Non vengono concatenati viaggi appartenenti a corse diverse.

[Tracciato del testimone](../outputs/phase2/rt031_line8_local_shortcuts_v3/shorter_span_1940_witness.png) · [Audit macchina e occorrenze per corsa](../outputs/phase2/rt031_line8_local_shortcuts_v3/site_rides_audit.json) · [Confronto completo H60/H90/H120 e km](RT031_LINEA8_FASCIA_PIU_CORTA_E_BUDGET_V3.md)

Il riferimento richiesto resta H30 in punta/H60 fuori punta. H90 e H120 sono rilassamenti non approvati; non si può dichiarare conclusa la proposta scegliendo implicitamente uno dei due.
