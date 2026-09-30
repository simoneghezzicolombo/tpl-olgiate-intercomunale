"""Render the confirmed road geometry and 29 design sites for the current 16-trip scope.

This is an explanatory map, not boarding or operating approval. It leaves the
two possible first-wing timetable orders unselected.
"""

import argparse
import csv
import gzip
import json
import re
from pathlib import Path

from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/phase2/rt031_line8_local_shortcuts_v3"
GEOMETRY = BASE / "deep_offpeak_witness.geojson"
ADDITIONS = BASE / "stop_plan_and_additions.geojson"
EDGES = ROOT / "outputs/phase2/frozen_gate_d/graph_edges.csv.gz"
def node_xy(node):
    match = re.fullmatch(r"n:([0-9.]+):([0-9.]+)", node)
    return (float(match[1]), float(match[2])) if match else None


def background_roads(lines):
    points = [point for line in lines for point in line["geometry"]["coordinates"]]
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    xy = [transformer.transform(*point) for point in points]
    xmin = min(p[0] for p in xy) - 300
    xmax = max(p[0] for p in xy) + 300
    ymin = min(p[1] for p in xy) - 300
    ymax = max(p[1] for p in xy) + 300
    inverse = Transformer.from_crs(32632, 4326, always_xy=True)
    roads = []
    seen = set()
    with gzip.open(EDGES, "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            a = node_xy(row["u_node_id"])
            b = node_xy(row["v_node_id"])
            if a is None or b is None:
                continue
            if not (xmin <= a[0] <= xmax and ymin <= a[1] <= ymax
                    and xmin <= b[0] <= xmax and ymin <= b[1] <= ymax):
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            roads.append([[round(c, 5) for c in inverse.transform(*a)],
                          [round(c, 5) for c in inverse.transform(*b)]])
    return roads


def build(output):
    source = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    lines = [f for f in source["features"] if f["geometry"]["type"] == "LineString"]
    stops = [f for f in source["features"] if f["geometry"]["type"] == "Point"]
    additions = json.loads(ADDITIONS.read_text(encoding="utf-8"))
    new = [f for f in additions["features"] if f["properties"].get("candidate_id") == "N1212"]
    if len(lines) != 2 or len(stops) != 28 or len(new) != 1:
        raise ValueError("confirmed geometry or stop count drift")
    if new[0]["properties"].get("boarding_authorised") is not False:
        raise ValueError("new design stop unexpectedly authorised")
    stops.append({"type": "Feature", "geometry": new[0]["geometry"],
                  "properties": {"name": "Arlate · Via Nuova Provinciale", "candidate_id": "N1212",
                                 "boarding_authorised": False}})
    data = {
        "lines": [{"type": "Feature", "geometry": f["geometry"],
                   "properties": {"pattern": f["properties"]["pattern"]}} for f in lines],
        "stops": [{"coordinates": f["geometry"]["coordinates"],
                   "name": f["properties"].get("name", "Fermata di progetto"),
                   "new": f["properties"].get("candidate_id") == "N1212"} for f in stops],
        "roads": background_roads(lines),
    }
    html = '''<div id="rt031-map-16" style="width:100%;color:var(--foreground)">
  <h2>Linea 8 · 16 giri completi</h2>
  <div class="text-muted">Un solo itinerario a otto, 29 siti di progetto</div>
  <svg role="img" aria-label="Tracciato stradale confermato dell'unica Linea 8: ala ovest via Olgiate sud, Perego, Rovagnate e Santa Maria; ala est via Calco, Arlate, Brivio, Beverate e San Zeno; incontro a Olgiate FS. Le 16 corse attraversano entrambe le ali."></svg>
  <div class="viz-row text-small"><span style="color:var(--viz-series-1)">━ Ovest</span><span style="color:var(--viz-series-2)">━ Est</span><span>◆ Nuova fermata di progetto ad Arlate, non approvata fisicamente</span></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script>
(() => {
  const root = document.getElementById('rt031-map-16');
  const data = __DATA__;
  const svg = d3.select(root).select('svg');
  const labelTerms = [
    ['Olgiate FS', /Olgiate.*(Stazione|FS|Ferrovia)/i, 5, -12],
    ['Olgiate sud', /Olgiate sud/i, 8, 17],
    ['San Zeno', /San Zeno|Via Cantù/i, 7, -12],
    ['Perego', /Perego/i, -7, 17],
    ['Santa Maria', /Santa Maria/i, 7, -12],
    ['Brivio', /Brivio.*Bergamo/i, -6, -12],
    ['Arlate · Via Nuova Provinciale', /Via Nuova Provinciale/i, -8, 18]
  ];
  const all = {type:'FeatureCollection',features:data.lines};
  function draw(){
    const width = Math.max(320, root.clientWidth);
    const height = Math.max(350, Math.min(510, width * .63));
    svg.attr('viewBox',`0 0 ${width} ${height}`).attr('width',width).attr('height',height);
    svg.selectAll('*').remove();
    const projection = d3.geoMercator().fitExtent([[45,38],[width-45,height-30]],all);
    const path = d3.geoPath(projection);
    const roads = svg.append('g').attr('fill','none').attr('stroke','var(--border)').attr('stroke-width',.55).attr('opacity',.55);
    roads.selectAll('path').data(data.roads).join('path')
      .attr('d', d => path({type:'LineString',coordinates:d}));
    svg.append('g').attr('fill','none').attr('stroke-linecap','round').attr('stroke-linejoin','round')
      .selectAll('path').data(data.lines).join('path')
      .attr('d',path).attr('stroke',d => d.properties.pattern === 'west_B' ? 'var(--viz-series-1)' : 'var(--viz-series-2)')
      .attr('stroke-width',3.4);
    const marks = svg.append('g').selectAll('circle').data(data.stops.filter(d=>!d.new)).join('circle')
      .attr('cx',d=>projection(d.coordinates)[0]).attr('cy',d=>projection(d.coordinates)[1])
      .attr('r',2.8).attr('fill','var(--foreground)');
    marks.append('title').text(d=>d.name + ' · sito di progetto; palina/fermata da verificare');
    const candidate = data.stops.find(d=>d.new);
    const [cx,cy] = projection(candidate.coordinates);
    svg.append('path').attr('d',`M${cx},${cy-6}L${cx+6},${cy}L${cx},${cy+6}L${cx-6},${cy}Z`)
      .attr('fill','var(--viz-series-3)').append('title').text('Arlate · Via Nuova Provinciale · nuova fermata proposta, non approvata');
    for(const [label,pattern,dx,dy] of labelTerms){
      if(width < 500 && !['Olgiate FS','Olgiate sud','San Zeno'].includes(label)) continue;
      const stop = data.stops.find(d=>pattern.test(d.name));
      if(!stop) continue;
      const [x,y]=projection(stop.coordinates);
      svg.append('text').attr('x',x+dx).attr('y',y+dy)
        .attr('text-anchor',dx<0?'end':'start').attr('font-size',12).attr('font-weight',500)
        .attr('paint-order','stroke').attr('stroke','var(--background)').attr('stroke-width',3)
        .attr('fill','var(--foreground)').text(label);
    }
  }
  new ResizeObserver(draw).observe(root);
  draw();
})();
</script>
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html.replace("__DATA__", json.dumps(data, separators=(",", ":"), ensure_ascii=False)),
                      encoding="utf-8")
    if output.stat().st_size >= 1_000_000:
        raise ValueError("inline map exceeds 1 MB")
    print(f"{output} ({output.stat().st_size} bytes; {len(data['roads'])} background roads)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
