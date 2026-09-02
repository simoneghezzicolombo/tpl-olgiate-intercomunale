#!/usr/bin/env python3
"""
13_maps.py
Generazione della mappa geografica interattiva HTML (basata su Leaflet.js)
con controllo selettivo di accensione/spegnimento di tutti i layer tematici richiesti:
1. Popolazione Granulare WorldPop Calibrata 100m
2. Fermate TPL Esistenti
3. Linee TPL Attuali (D184 e D185 Strutturale)
4. Deviazione Emergenziale 2026 (Ponte di Brivio via Calolziocorte)
5. Generatori di Domanda (POI: Scuole, Sanità, Municipi, Imprese)
6. Scenario Ottimale - Senso Orario (CW)
7. Scenario Ottimale - Senso Antiorario (CCW)
8. Punti Critici Viari e Field Checks
Salva outputs/maps/mappa_interattiva_rete_tpl_olgiate.html.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import json
import pandas as pd

OUT_MAP_HTML = "outputs/maps/mappa_interattiva_rete_tpl_olgiate.html"

def main():
    print("=== 13: GENERAZIONE MAPPA INTERATTIVA MULTI-LAYER (LEAFLET) ===")
    os.makedirs("outputs/maps", exist_ok=True)
    
    # Carica dati
    cells_df = pd.read_csv("data/processed/walk_isochrones_cells.csv")
    poi_df = pd.read_csv("data/processed/poi_dataset.csv")
    field_df = pd.read_csv("outputs/field_checks.csv")
    stops_df = pd.read_csv("outputs/stop_analysis.csv")
    
    # Campiona le celle più significative per alleggerire l'HTML
    cells_sample = cells_df[cells_df["pop_calibrated"] >= 4.0].copy()
    
    cells_geojson_features = []
    for _, r in cells_sample.iterrows():
        cells_geojson_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {
                "pop": float(r["pop_calibrated"]),
                "comune": r["comune"],
                "frazione": r["frazione"],
                "walk_min": float(r["walk_min_slope"]),
                "elev": float(r["elevation_m"])
            }
        })
    cells_json = json.dumps({"type": "FeatureCollection", "features": cells_geojson_features})
    
    # POI Features
    poi_features = []
    for _, r in poi_df.iterrows():
        poi_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {
                "nome": r["nome"],
                "categoria": r["categoria"],
                "comune": r["comune"],
                "peso": int(r["peso"])
            }
        })
    poi_json = json.dumps({"type": "FeatureCollection", "features": poi_features})
    
    # Field Checks
    field_features = []
    for _, r in field_df.iterrows():
        field_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {
                "punto": r["punto_critico"],
                "comune": r["comune"],
                "problema": r["problema_rilevato"],
                "incertezza": r["livello_incertezza"],
                "azione": r["cosa_verificare"]
            }
        })
    field_json = json.dumps({"type": "FeatureCollection", "features": field_features})

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mappa Interattiva TPL Olgiate Intercomunale | Studio di Rete a Doppio Verso</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body, html {{ margin: 0; padding: 0; height: 100%; font-family: 'Outfit', sans-serif; background: #080c14; color: #f8fafc; }}
    #map {{ width: 100%; height: 100vh; }}
    .map-header {{
      position: absolute; top: 12px; left: 60px; z-index: 1000;
      background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(12px);
      padding: 10px 16px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }}
    .map-header h1 {{ margin: 0; font-size: 1.15rem; font-weight: 800; color: #38bdf8; }}
    .map-header p {{ margin: 2px 0 0; font-size: 0.78rem; color: #94a3b8; }}
    .leaflet-control-layers {{
      background: rgba(15, 23, 42, 0.92) !important;
      backdrop-filter: blur(12px) !important;
      border: 1px solid rgba(255,255,255,0.12) !important;
      border-radius: 10px !important;
      color: #f8fafc !important;
      font-family: 'Outfit', sans-serif !important;
      font-size: 0.82rem !important;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5) !important;
    }}
    .legend-box {{
      position: absolute; bottom: 24px; left: 16px; z-index: 1000;
      background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(12px);
      padding: 12px 16px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);
      font-size: 0.75rem; max-width: 280px; line-height: 1.4;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
    .color-pill {{ width: 14px; height: 14px; border-radius: 4px; display: inline-block; }}
  </style>
</head>
<body>
  <div class="map-header">
    <h1>RETE TPL INTERCOMUNALE OLGIATE-CALCO-BRIVIO</h1>
    <p>Studio Territoriale di Rete a Doppio Verso (Modello Merate) | Scenario Ottimale Pareto</p>
  </div>

  <div id="map"></div>

  <div class="legend-box">
    <strong>LEGENDA STRATI</strong>
    <div class="legend-item"><span class="color-pill" style="background:#0284c7;"></span> Anello Ovest (Orario CW)</div>
    <div class="legend-item"><span class="color-pill" style="background:#10b981;"></span> Anello Est (Orario CW)</div>
    <div class="legend-item"><span class="color-pill" style="background:#a855f7;"></span> Anello Antiorario (CCW)</div>
    <div class="legend-item"><span class="color-pill" style="background:#ef4444;"></span> Punti Critici Viari (Field Checks)</div>
    <div class="legend-item"><span class="color-pill" style="background:#f59e0b;"></span> Generatori di Domanda (POI)</div>
    <div class="legend-item"><span class="color-pill" style="background:#e0f2fe; opacity:0.6;"></span> Popolazione Calibrata (~100m)</div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const map = L.map('map', {{ center: [45.734, 9.405], zoom: 13 }});
    
    // Base Tile CartoDB Dark
    const cartoDark = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      attribution: '&copy; OpenStreetMap, &copy; CARTO', maxZoom: 19
    }}).addTo(map);

    const osmStandard = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors'
    }});

    // 1. Popolazione Granulare
    const popData = {cells_json};
    const popLayer = L.geoJSON(popData, {{
      pointToLayer: (feature, latlng) => {{
        const pop = feature.properties.pop;
        const color = feature.properties.walk_min <= 8 ? '#38bdf8' : (feature.properties.walk_min <= 12 ? '#f59e0b' : '#ef4444');
        return L.circleMarker(latlng, {{
          radius: Math.min(10, Math.max(2.5, Math.sqrt(pop) * 1.6)),
          fillColor: color,
          color: '#080c14',
          weight: 0.5,
          opacity: 0.8,
          fillOpacity: 0.65
        }}).bindPopup(`<strong>${{feature.properties.comune}} (${{feature.properties.frazione}})</strong><br>Popolazione: <strong>${{pop.toFixed(1)}} ab</strong><br>Accesso a piedi fermata: <strong>${{feature.properties.walk_min.toFixed(1)}} min</strong> (slope-adjusted)<br>Quota altimetrica: ${{feature.properties.elev}} m slm`);
      }}
    }}).addTo(map);

    // 2. Tracciato Scenario Ottimale Orario (CW)
    const westCWCoords = [
      [45.73145, 9.40321], // Olgiate FS
      [45.73380, 9.40110], // Olgiate Centro
      [45.73680, 9.38890], // Scarpone
      [45.73890, 9.36950], // Rovagnate
      [45.74320, 9.36420], // Perego
      [45.74560, 9.37340], // S. Maria Hoè
      [45.74210, 9.39230], // Monticello Olg.
      [45.73850, 9.39720], // Mondonico
      [45.73145, 9.40321]  // Olgiate FS
    ];
    const trackWestCW = L.polyline(westCWCoords, {{ color: '#0284c7', weight: 5, opacity: 0.9, dashArray: null }}).bindPopup("<strong>Anello Ovest (Senso Orario CW)</strong><br>Olgiate FS -> Perego -> S.Maria Hoè -> Mondonico -> Olgiate FS<br>Tempo: 26 min | Lunghezza: 9.5 km");

    const eastCWCoords = [
      [45.73145, 9.40321], // Olgiate FS
      [45.72620, 9.41240], // Calco Naz
      [45.73510, 9.42450], // Beverate
      [45.74410, 9.44420], // Brivio Castello
      [45.74280, 9.44550], // Brivio Porto
      [45.71640, 9.43210], // Arlate
      [45.72620, 9.41240], // Calco Sud
      [45.73145, 9.40321]  // Olgiate FS
    ];
    const trackEastCW = L.polyline(eastCWCoords, {{ color: '#10b981', weight: 5, opacity: 0.9 }}).bindPopup("<strong>Anello Est (Senso Orario CW)</strong><br>Olgiate FS -> Calco -> Beverate -> Brivio -> Arlate -> Olgiate FS<br>Tempo: 29 min | Lunghezza: 10.3 km");

    const layerOptimalCW = L.layerGroup([trackWestCW, trackEastCW]).addTo(map);

    // 3. Tracciato Scenario Ottimale Antiorario (CCW)
    const westCCWCoords = [...westCWCoords].reverse();
    const eastCCWCoords = [...eastCWCoords].reverse();
    const trackWestCCW = L.polyline(westCCWCoords, {{ color: '#a855f7', weight: 4, opacity: 0.8, dashArray: '6 6' }}).bindPopup("<strong>Anello Ovest (Senso Antiorario CCW)</strong><br>Olgiate FS -> Mondonico -> S.Maria Hoè -> Perego -> Rovagnate -> Olgiate FS");
    const trackEastCCW = L.polyline(eastCCWCoords, {{ color: '#d946ef', weight: 4, opacity: 0.8, dashArray: '6 6' }}).bindPopup("<strong>Anello Est (Senso Antiorario CCW)</strong><br>Olgiate FS -> Arlate -> Brivio -> Beverate -> Calco -> Olgiate FS");
    const layerOptimalCCW = L.layerGroup([trackWestCCW, trackEastCCW]).addTo(map);

    // 4. Linea D184 Attuale Spola Ravellino
    const d184Coords = [
      [45.73145, 9.40321], [45.73380, 9.40110], [45.73680, 9.38890],
      [45.73890, 9.36950], [45.74320, 9.36420], [45.74560, 9.37340],
      [45.76210, 9.36540], [45.76890, 9.37120]
    ];
    const trackD184 = L.polyline(d184Coords, {{ color: '#64748b', weight: 3, dashArray: '4 4' }}).bindPopup("<strong>Linea D184 Storica Attuale</strong><br>Olgiate FS - Santa Maria Hoè - Ravellino (Spola)");

    // 5. Linea D185 Attuale Strutturale (con attraversamento Ponte Brivio)
    const d185Coords = [
      [45.73145, 9.40321], [45.72620, 9.41240], [45.73510, 9.42450],
      [45.74410, 9.44420], [45.74620, 9.44850], [45.74480, 9.46820],
      [45.74950, 9.48210], [45.75380, 9.49350]
    ];
    const trackD185 = L.polyline(d185Coords, {{ color: '#94a3b8', weight: 3, dashArray: '4 4' }}).bindPopup("<strong>Linea D185 Storica Strutturale</strong><br>Olgiate FS - Calco - Brivio - Cisano - Caprino - Celana");

    const layerHistoric = L.layerGroup([trackD184, trackD185]);

    // 6. Deviazione Emergenziale 2026 (Ponte di Brivio via Calolziocorte)
    const emergCoords = [
      [45.74410, 9.44420], // Brivio
      [45.77250, 9.42310], // Capiate Olginate
      [45.78320, 9.42150], // Ponte Cantù
      [45.78110, 9.43420], // Calolzio Bisone
      [45.74950, 9.48210]  // Caprino
    ];
    const trackEmerg = L.polyline(emergCoords, {{ color: '#f97316', weight: 3, dashArray: '8 4' }}).bindPopup("<strong>Deviazione Emergenziale 2026 (Cantiere Ponte Brivio)</strong><br>Transito da Capiate, Ponte Cantù e Calolziocorte Bisone (+14 km, +25 min)");
    const layerEmergency = L.layerGroup([trackEmerg]);

    // 7. POI Generatori di Domanda
    const poiData = {poi_json};
    const poiLayer = L.geoJSON(poiData, {{
      pointToLayer: (f, latlng) => {{
        return L.circleMarker(latlng, {{
          radius: 6, fillColor: '#f59e0b', color: '#ffffff', weight: 1.5, opacity: 1, fillOpacity: 0.9
        }}).bindPopup(`<strong>${{f.properties.nome}}</strong><br>Categoria: <strong>${{f.properties.categoria}}</strong><br>Comune: ${{f.properties.comune}}<br>Peso Attrattività: ${{f.properties.peso}}/10`);
      }}
    }});

    // 8. Field Checks
    const fieldData = {field_json};
    const fieldLayer = L.geoJSON(fieldData, {{
      pointToLayer: (f, latlng) => {{
        return L.circleMarker(latlng, {{
          radius: 9, fillColor: '#dc2626', color: '#ffffff', weight: 2, opacity: 1, fillOpacity: 0.9
        }}).bindPopup(`<strong>PUNTO CRITICO: ${{f.properties.punto}}</strong><br>Incertezza: <strong>${{f.properties.incertezza}}</strong><br>Problema: ${{f.properties.problema}}<br>Verifica: ${{f.properties.azione}}`);
      }}
    }}).addTo(map);

    // Control Layer Toggles
    const baseMaps = {{
      "CartoDB Dark": cartoDark,
      "OpenStreetMap": osmStandard
    }};

    const overlayMaps = {{
      "Popolazione Granulare (100m)": popLayer,
      "Scenario Ottimale (Orario CW)": layerOptimalCW,
      "Scenario Ottimale (Antiorario CCW)": layerOptimalCCW,
      "Punti Critici Viari (Field Checks)": fieldLayer,
      "Generatori di Domanda (POI)": poiLayer,
      "Linee Storiche Attuali (D184/D185)": layerHistoric,
      "Deviazione Cantiere 2026 (Ponte Adda)": layerEmergency
    }};

    L.control.layers(baseMaps, overlayMaps, {{ collapsed: false }}).addTo(map);
  </script>
</body>
</html>
"""
    with open(OUT_MAP_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] Mappa interattiva generata con successo in {OUT_MAP_HTML}.")

if __name__ == "__main__":
    main()
