// Existing-service trips are not physical vehicles. The dated calendar and
// exact trip.shape_id come from the same immutable official GTFS archive.
export const CURRENT_COLOURS = {D184:"#4ca5ff",D185:"#ff9b61"};

export function currentPosition(shape, distance) {
  let lo = 0, hi = shape.distances.length - 1;
  const target = Math.max(shape.distances[0], Math.min(shape.distances.at(-1), distance));
  while (lo < hi) {const mid = (lo + hi) >>> 1; if (shape.distances[mid] < target) lo = mid + 1; else hi = mid;}
  if (!lo) return shape.coordinates[0];
  const span = shape.distances[lo] - shape.distances[lo - 1];
  const f = span ? (target - shape.distances[lo - 1]) / span : 0;
  return shape.coordinates[lo - 1].map((v, axis) => v + (shape.coordinates[lo][axis] - v) * f);
}

export function buildCurrent(data) {
  if (data.contract !== "nodo8_existing_service_dated_simulation_v1" || data.service_date !== "2026-05-06" ||
      data.source?.sha256 !== "f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b" ||
      data.semantics?.live !== false || data.semantics?.latest_2026_27_timetable !== false ||
      data.semantics?.vehicle_identity_certified !== false || data.semantics?.missing_stop_times_inferred !== false ||
      data.semantics?.trip_to_shape !== "EXACT_GTFS_SHAPE_ID" || data.trips?.length !== 34)
    throw new Error("Unsupported dated existing-service contract");
  for (const shape of Object.values(data.shapes)) {
    if (shape.coordinates.length < 3 || shape.distances.length !== shape.coordinates.length ||
        !shape.coordinates.every(c => c.length === 2 && c.every(Number.isFinite)) ||
        shape.distances.some((d,i)=>!Number.isFinite(d) || (i && d < shape.distances[i-1])))
      throw new Error("Invalid official shape");
  }
  const ids = new Set();
  for (const trip of data.trips) {
    const shape = data.shapes[trip.shape_id];
    if (ids.has(trip.id) || !CURRENT_COLOURS[trip.route] || !shape || trip.calls.length < 2 ||
        trip.calls.some((c,i)=> !Number.isFinite(c.arrival_min) || !Number.isFinite(c.departure_min) ||
          !Number.isFinite(c.distance) || c.departure_min < c.arrival_min ||
          c.distance < shape.distances[0] || c.distance > shape.distances.at(-1) + 0.01 ||
          (i && (c.sequence <= trip.calls[i-1].sequence || c.arrival_min <= trip.calls[i-1].departure_min || c.distance < trip.calls[i-1].distance))))
      throw new Error("Invalid dated stop sequence or shape assignment");
    ids.add(trip.id);
  }
  for (const [r,n] of Object.entries({D184:15,D185:19}))
    if (data.trips.filter(t=>t.route===r).length !== n) throw new Error("Incomplete dated inventory");
  return data;
}

export function currentTripsAt(data, minute, selection="ALL") {
  if (!Number.isFinite(minute) || !["ALL","D184","D185"].includes(selection)) throw new Error("Invalid current-service clock or selection");
  return data.trips.filter(t=>selection==="ALL" || t.route===selection).flatMap(trip=> {
    if (minute < trip.calls[0].arrival_min || minute > trip.calls.at(-1).departure_min) return [];
    for (let i=0;i<trip.calls.length;i++) {
      const call=trip.calls[i], next=trip.calls[i+1];
      if (minute >= call.arrival_min && minute <= call.departure_min)
        return [{...trip,coordinates:currentPosition(data.shapes[trip.shape_id],call.distance),status:"stop",label:call.name}];
      if (next && minute > call.departure_min && minute < next.arrival_min) {
        const f=(minute-call.departure_min)/(next.arrival_min-call.departure_min);
        return [{...trip,coordinates:currentPosition(data.shapes[trip.shape_id],call.distance+(next.distance-call.distance)*f),status:"moving",label:`Verso ${next.name}`}];
      }
    }
    return [];
  });
}

export async function installCurrent(map) {
  const response=await fetch("../assets/nodo8-current-simulation.json?v=20261008s");
  if (!response.ok) throw new Error("Dated existing-service data unavailable");
  const data=buildCurrent(await response.json());
  const pairs=[...new Map(data.trips.map(t=>[`${t.route}:${t.shape_id}`,t])).values()];
  map.addSource("current-dated-routes",{type:"geojson",data:{type:"FeatureCollection",features:pairs.map(t=>({type:"Feature",properties:{route:t.route},geometry:{type:"LineString",coordinates:data.shapes[t.shape_id].coordinates}}))}});
  map.addLayer({id:"current-dated-routes",type:"line",source:"current-dated-routes",paint:{"line-color":["match",["get","route"],"D184",CURRENT_COLOURS.D184,CURRENT_COLOURS.D185],"line-width":3,"line-dasharray":[3,1],"line-opacity":0}},"nodo8-glow");
  map.addLayer({id:"current-dated-hit",type:"line",source:"current-dated-routes",paint:{"line-color":"#fff","line-width":18,"line-opacity":0}},"nodo8-glow");
  const stops=new Map();
  for (const trip of data.trips) for (const call of trip.calls) {
    const key=`${trip.route}:${call.stop_id}`;
    if (!stops.has(key)) stops.set(key,{type:"Feature",properties:{route:trip.route,name:call.name,stop_id:call.stop_id},geometry:{type:"Point",coordinates:call.coordinates}});
  }
  map.addSource("current-dated-stops",{type:"geojson",data:{type:"FeatureCollection",features:[...stops.values()]}});
  map.addLayer({id:"current-dated-stops",type:"circle",source:"current-dated-stops",paint:{"circle-color":["match",["get","route"],"D184",CURRENT_COLOURS.D184,CURRENT_COLOURS.D185],"circle-radius":3,"circle-opacity":0}},"nodo8-sites");
  const markers=new Map();
  return {data,
    render({minute,visible,selection="ALL",showStops=true}) {
      map.setPaintProperty("current-dated-routes","line-opacity",visible?0.9:0);
      map.setFilter("current-dated-routes",selection==="ALL"?null:["==",["get","route"],selection]);
      map.setPaintProperty("current-dated-hit","line-opacity",visible?0.001:0);
      map.setFilter("current-dated-hit",selection==="ALL"?null:["==",["get","route"],selection]);
      map.setPaintProperty("current-dated-stops","circle-opacity",visible && showStops?0.95:0);
      map.setFilter("current-dated-stops",selection==="ALL"?null:["==",["get","route"],selection]);
      const states=visible?currentTripsAt(data,minute,selection):[];
      const present=new Set(states.map(t=>t.id));
      for (const [id,e] of markers) if (!present.has(id)) {e.marker.remove();markers.delete(id);}
      for (const state of states) {
        if (!markers.has(state.id)) {
          const icon=document.createElement("div"); icon.className="current-bus-marker";icon.setAttribute("role","img");
          icon.innerHTML=`<svg viewBox="0 0 34 42" width="34" height="42" aria-hidden="true"><rect x="4" y="2" width="26" height="34" rx="7" fill="${CURRENT_COLOURS[state.route]}" stroke="#fffdf8" stroke-width="2"/><rect x="8" y="7" width="18" height="10" rx="2" fill="#173c33"/><text x="17" y="29" text-anchor="middle" fill="#07131f" font-size="8" font-weight="800">${state.route}</text><circle cx="10" cy="33" r="2" fill="#ffe4a4"/><circle cx="24" cy="33" r="2" fill="#ffe4a4"/><path d="M9 37v3m16-3v3" stroke="#173c33" stroke-width="4"/></svg>`;
          const marker=new window.maplibregl.Marker({element:icon,anchor:"center"}).setLngLat(state.coordinates).addTo(map);
          markers.set(state.id,{marker,icon});
        }
        const e=markers.get(state.id);
        const label=`${state.route} · ${state.label} · corsa GTFS del 6 maggio 2026, non identità del mezzo`;
        e.icon.setAttribute("aria-label",label);e.icon.title=label;e.icon.dataset.trip=state.id;
        e.marker.setLngLat(state.coordinates);
      }
      document.documentElement.dataset.currentBusCount=String(states.length);
      document.documentElement.dataset.currentBusVisible=String(visible);
      const status=document.getElementById("currentBusStatus");
      if (status) {status.hidden=!visible;const label=`${states.length} corse in viaggio · riferimento 06/05/2026`;if(status.textContent!==label)status.textContent=label;}
    },
  };
}
