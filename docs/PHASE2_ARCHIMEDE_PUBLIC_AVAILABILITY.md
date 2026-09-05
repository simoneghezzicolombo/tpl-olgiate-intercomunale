# Phase 2 — disponibilità pubblica ARCH.I.M.E.DE. per OD comunali recenti

## Verdetto

**`NOT_PUBLICLY_MATERIALISED_FOR_MUNICIPAL_OD_2020_2023`**

La base ISTAT **Popolazioni che usano un territorio e loro mobilità – ARCH.I.M.E.DE.** è metodologicamente molto interessante per estendere l'analisi oltre il 2021. La documentazione ufficiale specifica infatti che i record aggregati distinguono:

- provincia e comune di origine;
- provincia e comune di destinazione;
- tipo di insistenza sul territorio;
- tipo di attività dell'individuo.

Una base completa con questa struttura consentirebbe di ricostruire matrici comunali annuali lavoro/studio.

## Audit dei download pubblici

Il 3 settembre 2026 sono stati scaricati direttamente dai link `METADATI` della pagina ISTAT gli archivi 2019, 2020, 2021, 2022 e 2023.

Tutti gli ZIP sono validi e sono stati verificati con checksum. Il dettaglio riproducibile è registrato in:

`outputs/phase2/archimede_public_availability.json`

Gli archivi contengono:

- tracciato record;
- classificazioni;
- note metodologiche;
- ReadMe;
- in alcune annualità, un piccolo file `ESEMPIO_META`.

Lo schema dei file di esempio conferma le variabili:

`N`, `COD_PRO_ORI`, `COD_COM_ORI`, `COD_PRO_DES`, `COD_COM_DES`, `CITY_USER`, `TIPO_IND`.

Gli esempi sono però soltanto campioni strutturali di poche decine di righe e **non costituiscono il dataset nazionale**. Non contengono dati utilizzabili per ricostruire Olgiate Molgora, Merate o il Meratese.

## Cross-check SDMX

È stata interrogata anche la dataflow comunale ISTAT:

`DF_DCSS_ISTR_LAV_PEN_2_TV_5`

sull'intervallo 2018-2024 e senza restringere preventivamente le categorie di motivo/destinazione.

Risultato:

- anni restituiti: **2018 e 2019 soltanto**;
- indicatore: `RP_COM_DAY`;
- motivo: `ALL`, `STD`, `WK`;
- localizzazione: `ALL`, `OMPUR`, `SMPUR`;
- nessuna osservazione comunale 2020-2024 nella dataflow.

Questa verifica esclude che le annualità recenti fossero semplicemente nascoste dalla query 2019 usata nel primo script di contesto.

## Conseguenza metodologica

Per la Phase 2 sono quindi ammesse le seguenti fonti temporali:

- **2011:** matrice OD comunale lavoro canonica ricostruita dalla matrice censuaria ufficiale;
- **2018-2019:** indicatore comunale lavoro/studio dentro/fuori comune, non OD completa;
- **2021:** matrice OD comunale lavoro del Censimento permanente;
- **2019 e 2021-2024:** occupati residenti 15+;
- **2019-2024:** popolazione residente;
- **2019-2023:** contesto nazionale della popolazione insistente.

Non sono ammesse matrici OD comunali 2020, 2022 o 2023 costruite per interpolazione, estrapolazione o uso dei file `ESEMPIO_META`.

Per estendere davvero la serie OD oltre il 2021 serve ottenere la base integrata completa attraverso un canale ufficiale di accesso ISTAT o una futura pubblicazione open equivalente.
