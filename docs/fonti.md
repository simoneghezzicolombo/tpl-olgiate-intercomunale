# Repertorio Ufficiale delle Fonti Dati e Tracciabilità

Tutti i dati utilizzati nello studio provengono da fonti istituzionali e ufficiali, e sono registrati con checksum crittografico SHA256 all'interno di [`data/manifest.csv`](file:///d:/linea_8_olgiate/data/manifest.csv).

---

## 1. Dati Demografici e Censuari
- **Ente**: ISTAT (Istituto Nazionale di Statistica).
- **Dataset**: *POSAS 2025 - Popolazione residente per età, sesso e stato civile al 1° gennaio 2025*.
- **Riferimento Territoriale**: Provincia di Lecco (codice 097).
- **File Locale**: `data/raw/istat/POSAS_2025_it_097_Lecco.csv`.
- **Licenza**: Italian Open Data License (IODL 2.0).
- **Validità temporale**: 1° gennaio 2025.
- **Utilizzo**: Calibrazione della popolazione comunale per Olgiate Molgora (6.332), Calco (5.460), Brivio (4.357), La Valletta Brianza (4.656) e Santa Maria Hoè (2.109).

---

## 2. Dati della Mobilità Sistematica (Matrice Origine-Destinazione)
- **Ente**: ISTAT / Regione Lombardia (Direzione Generale Trasporti e Mobilità).
- **Dataset**: *Matrice del Pendolarismo per Lavoro e Studio (Mobilità Sistematica)*.
- **Riferimento**: Censimento permanente e modelli regionali di traffico aggiornati.
- **File Locale**: `outputs/od_matrix_core.csv`.
- **Utilizzo**: Stima dei vettori di spostamento pendolare tra i cinque comuni core e verso i poli esterni (Merate, Lecco, Milano, Monza, Vimercate).

---

## 3. Servizio Ferroviario Regionale (Linea S8 Milano-Lecco)
- **Ente**: Regione Lombardia / Trenord / RFI (Rete Ferroviaria Italiana).
- **Dataset**: 
  1. *Frequentazione delle stazioni del Servizio Ferroviario Regionale (SFR 2015-2025)* - Rilevazioni ufficiali saliti/discesi giorno feriale.
  2. *Orario Ufficiale Ferroviario Vigente Trenord Linea S8*.
- **File Locale**: `data/raw/sfr/stazioni_s8_indice_2015_2025.csv`.
- **Risultato Storico Olgiate-Calco-Brivio FS**: 
  - 2019: 1.420 saliti/giorno
  - 2024: 1.830 saliti/giorno
  - 2025: 2.400 saliti/giorno (**+69,01%**).

---

## 4. Servizio di Trasporto Pubblico su Gomma (TPL)
- **Ente**: Agenzia per il Trasporto Pubblico Locale del Bacino di Como, Lecco e Varese / Arriva Italia S.r.l. / LineeLecco.
- **Documenti Ufficiali**:
  1. *Programma di Bacino (PdB) - Aggiornamento Relazione Generale e Schede di Linea*.
  2. *Orari Ufficiali di Esercizio Feriale Estivo/Invernale Linee D184, D185, D150, D170*.
  3. *Avvisi e Disposizioni di Esercizio per i Lavori Straordinari al Ponte di Brivio sull'Adda (Maggio 2026)*.
- **Dataset GTFS Costruiti**:
  - `data/raw/gtfs/network_structural/` (rete strutturale ordinaria).
  - `data/raw/gtfs/network_2026_emergency/` (rete contingente deviata via Capiate / Ponte Cantù / Calolziocorte).

---

## 5. Dati Geospaziali e Altimetrici
- **Rete Viaria e Pedonale**: OpenStreetMap (OSM) contributors (Licenza ODbL).
- **Distribuzione Spaziale di Dettaglio**: WorldPop (University of Southampton / School of Geography and Environmental Science), raster $100 \times 100 \text{ m}$ (`ita_ppp_2020_UNadj.tif`), calcolato e calibrato con snap al grafo stradale.
- **Modello Digitale di Elevazione**: Copernicus DEM (European Space Agency / European Union) a risoluzione 30 metri per le pendenze.
