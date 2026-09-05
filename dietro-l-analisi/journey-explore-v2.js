(() => {
  'use strict';

  const map = window.__analysisJourneyMap;
  const J = window.ANALYSIS_JOURNEY_DATA;
  if (!map || !window.maplibregl) return;

  const COLORS = {D184:'#4ca5ff',D185:'#ff9b61',R2_23d58cd05658247380d7:'#57d7e8',R2_65db885119e69d50c7d4:'#55e1bf',R2_b2032eeb31cba06561f0:'#ff9b61',R2_2ffb6743b10bb3f0a97d:'#f6d36f'};
  const LABELS = {R2_23d58cd05658247380d7:'16 h · linea 1',R2_65db885119e69d50c7d4:'16 h · linea 2',R2_b2032eeb31cba06561f0:'18 h 30 · linea 1',R2_2ffb6743b10bb3f0a97d:'18 h 30 · linea 2'};
  const compatibilityState = {proposals:true,current:false,stops:true};
  const layers = {worldpop:false,sections:false,buildings:false,walk:false,roads:false,candidates:false,current:false,proposals:true,stops:true};
  let lineage = null;
  let popup = null;
  let active = false;
  let fitted = false;
  let roadPromise = null;
  let controls = null;

  const esc = v => String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const fmt = (v,d=1) => Number.isFinite(Number(v)) ? Number(v).toLocaleString('it-IT',{maximumFractionDigits:d}) : 'n.d.';
  const toArray = v => { if(Array.isArray(v)) return v; if(v==null) return []; if(typeof v!=='string') return [String(v)]; try{const p=JSON.parse(v);return Array.isArray(p)?p:[v];}catch(_){return v.includes(',')?v.split(',').map(x=>x.trim()).filter(Boolean):[v];} };

  function opacity(id,value){
    if(!map.getLayer(id)) return;
    const t=map.getLayer(id).type;
    const p=t==='fill-extrusion'?'fill-extrusion-opacity':t==='fill'?'fill-opacity':t==='line'?'line-opacity':t==='circle'?'circle-opacity':t==='symbol'?'text-opacity':null;
    if(p) map.setPaintProperty(id,p,value);
  }
  function addLayer(def){ if(!map.getLayer(def.id)) map.addLayer(def); }
  function card(kicker,title,body,meta=[],code=''){
    return `<div class="map-card"><p class="map-card__eyebrow">${esc(kicker)}</p><h3 class="map-card__title">${esc(title)}</h3><p class="map-card__body">${body}</p>${meta.length?`<div class="map-card__meta">${meta.filter(Boolean).map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}${code?`<div class="map-card__code">${esc(code)}</div>`:''}</div>`;
  }
  function show(lngLat,html){ if(popup) popup.remove(); popup=new maplibregl.Popup({closeButton:true,closeOnClick:false,maxWidth:'320px',offset:10}).setLngLat(lngLat).setHTML(html).addTo(map); }

  function buildRouteLayers(){
    const finalColor=['match',['get','route_id'],'R2_23d58cd05658247380d7',COLORS.R2_23d58cd05658247380d7,'R2_65db885119e69d50c7d4',COLORS.R2_65db885119e69d50c7d4,'R2_b2032eeb31cba06561f0',COLORS.R2_b2032eeb31cba06561f0,'R2_2ffb6743b10bb3f0a97d',COLORS.R2_2ffb6743b10bb3f0a97d,'#fff'];
    const currentColor=['match',['get','route'],'D184',COLORS.D184,'D185',COLORS.D185,'#fff'];
    const has184=['>=',['index-of','D184',['get','routes']],0],has185=['>=',['index-of','D185',['get','routes']],0];
    addLayer({id:'explore-current-glow',type:'line',source:'current-routes',paint:{'line-color':currentColor,'line-width':10,'line-blur':8,'line-opacity':0}});
    addLayer({id:'explore-current-routes',type:'line',source:'current-routes',paint:{'line-color':currentColor,'line-width':['interpolate',['linear'],['zoom'],9,2.1,12,3.1,15,4.2],'line-opacity':0,'line-dasharray':[2,1.4]}});
    addLayer({id:'explore-current-hit',type:'line',source:'current-routes',paint:{'line-color':'#fff','line-width':17,'line-opacity':0}});
    addLayer({id:'explore-current-stops-halo',type:'circle',source:'current-gtfs-stops',paint:{'circle-radius':['interpolate',['linear'],['zoom'],9,4.2,12,6.2,15,8],'circle-color':['case',has184,COLORS.D184,has185,COLORS.D185,'#fff'],'circle-opacity':0}});
    addLayer({id:'explore-current-stops',type:'circle',source:'current-gtfs-stops',paint:{'circle-radius':['interpolate',['linear'],['zoom'],9,2.4,12,3.8,15,5.2],'circle-color':['case',has185,COLORS.D185,has184,COLORS.D184,'#fff'],'circle-opacity':0,'circle-stroke-width':1.2,'circle-stroke-color':'#07131f','circle-stroke-opacity':.75}});
    addLayer({id:'explore-final-glow',type:'line',source:'final-routes-exact',paint:{'line-color':finalColor,'line-width':13,'line-blur':9,'line-opacity':0}});
    addLayer({id:'explore-final-routes',type:'line',source:'final-routes-exact',paint:{'line-color':finalColor,'line-width':['interpolate',['linear'],['zoom'],9,3,12,4.6,15,6],'line-opacity':0}});
    addLayer({id:'explore-final-hit',type:'line',source:'final-routes-exact',paint:{'line-color':'#fff','line-width':19,'line-opacity':0}});
    addLayer({id:'explore-final-anchors',type:'circle',source:'final-anchors-exact',paint:{'circle-radius':['case',['==',['get','kind'],'RAIL_HUB'],8,['==',['get','kind'],'PROPOSED_STOP'],6,4.5],'circle-color':['case',['==',['get','kind'],'PROPOSED_STOP'],'#ffd36d','#fff'],'circle-opacity':0,'circle-stroke-width':['case',['==',['get','kind'],'PROPOSED_STOP'],2,1.4],'circle-stroke-color':['case',['==',['get','kind'],'PROPOSED_STOP'],'#6b551f','#07131f'],'circle-stroke-opacity':0}});
  }

  async function loadGzip(urls){
    const parts=await Promise.all(urls.map(async u=>{const r=await fetch(u);if(!r.ok)throw new Error(`${u} ${r.status}`);return (await r.text()).trim();}));
    const bin=atob(parts.join('')),bytes=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);
    if(window.pako)return JSON.parse(window.pako.inflate(bytes,{to:'string'}));
    const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));return JSON.parse(new TextDecoder().decode(await new Response(stream).arrayBuffer()));
  }
  async function ensureRoads(){
    if(map.getLayer('road-network')) return true;
    if(roadPromise) return roadPromise;
    roadPromise=(async()=>{const geo=await loadGzip(J.meta.localAssets.roads);if(!map.getSource('road-graph'))map.addSource('road-graph',{type:'geojson',data:geo});addLayer({id:'road-shadow',type:'line',source:'road-graph',paint:{'line-color':'#06101a','line-width':4.2,'line-opacity':0}});addLayer({id:'road-network',type:'line',source:'road-graph',paint:{'line-color':['case',['boolean',['get','uncertain'],false],'#ff9b61','#57d7e8'],'line-width':['interpolate',['linear'],['zoom'],10,.3,13,1.15,16,2.4],'line-opacity':0}});return true;})().finally(()=>roadPromise=null);
    return roadPromise;
  }

  function addControls(){
    controls=document.createElement('div');controls.className='explore-controls';
    controls.innerHTML=`<div class="explore-controls__head"><div><strong>Esplora tutto il modello</strong><small>gli stessi layer dello scroll, ora liberi e cliccabili</small></div><button class="explore-controls__exit" data-action="exit" type="button">Torna allo scroll</button></div>
      <div class="explore-controls__group"><span>Territorio</span><div class="explore-controls__layers"><button data-layer="worldpop" type="button"><i style="--c:#57d7e8"></i>WorldPop 100 m</button><button data-layer="sections" type="button"><i style="--c:#ffb07f"></i>Sezioni ISTAT</button><button data-layer="buildings" type="button"><i style="--c:#55e1bf"></i>Edifici DBGT</button></div></div>
      <div class="explore-controls__group"><span>Accessibilità e ricerca</span><div class="explore-controls__layers"><button data-layer="walk" type="button"><i style="--c:#55e1bf"></i>Cammino</button><button data-layer="roads" type="button"><i style="--c:#57d7e8"></i>Grafo bus</button><button data-layer="candidates" type="button"><i style="--c:#ffd36d"></i>155 candidate</button></div></div>
      <div class="explore-controls__group"><span>Rete</span><div class="explore-controls__layers"><button data-layer="current" type="button"><i style="--c:#4ca5ff"></i>D184 / D185</button><button data-layer="proposals" class="is-active" type="button"><i style="--c:#57d7e8"></i>4 finaliste</button><button data-layer="stops" class="is-active" type="button"><i style="--c:#fff"></i>Fermate</button></div></div>
      <div class="explore-controls__footer"><div class="explore-controls__hint">Trascina, zooma, ruota e clicca su celle, edifici, strade, candidate, linee e fermate.</div><div class="explore-controls__layers"><button data-action="clear" type="button">spegni tutto</button><button data-action="reset" type="button">↺ vista</button></div></div>`;
    document.body.appendChild(controls);
    controls.querySelectorAll('[data-layer]').forEach(btn=>btn.addEventListener('click',async()=>{const k=btn.dataset.layer;layers[k]=!layers[k];if(k in compatibilityState)compatibilityState[k]=layers[k];btn.classList.toggle('is-active',layers[k]);if(k==='roads'&&layers.roads){btn.disabled=true;try{await ensureRoads();}catch(e){console.warn('Gate D graph explore load failed',e);layers.roads=false;btn.classList.remove('is-active');}finally{btn.disabled=false;}}render();}));
    controls.querySelector('[data-action="reset"]').addEventListener('click',()=>fit(true));
    controls.querySelector('[data-action="clear"]').addEventListener('click',()=>{Object.keys(layers).forEach(k=>layers[k]=false);Object.keys(compatibilityState).forEach(k=>compatibilityState[k]=false);controls.querySelectorAll('[data-layer]').forEach(b=>b.classList.remove('is-active'));render();});
    controls.querySelector('[data-action="exit"]').addEventListener('click',exit);
  }

  function render(){
    const scene=document.body.dataset.scene==='explore',interactive=scene&&active,preview=scene&&!active;
    ['current-route-glow','current-routes','final16-glow','final16','final185-glow','final185','existing-stops','existing-stops-halo','worldpop-stack','sections-stack','buildings-stack','dasymetric-sparks'].forEach(id=>opacity(id,0));
    opacity('worldpop-columns',interactive&&layers.worldpop?.72:0);opacity('worldpop-wire',interactive&&layers.worldpop?.26:0);
    opacity('sections-fill',interactive&&layers.sections?.58:0);opacity('sections-outline',interactive&&layers.sections?.52:0);
    opacity('buildings-extrude',interactive&&layers.buildings?.82:0);opacity('buildings-outline',interactive&&layers.buildings?.26:0);
    opacity('piece-halo',interactive&&layers.walk?.76:0);opacity('candidate-halo',interactive&&layers.candidates?.12:0);opacity('candidates',interactive&&layers.candidates?.9:0);
    opacity('road-shadow',interactive&&layers.roads?.3:0);opacity('road-network',interactive&&layers.roads?.66:0);
    const cur=interactive&&layers.current,fin=preview||(interactive&&layers.proposals),showStops=(preview||interactive)&&layers.stops;
    opacity('explore-current-glow',cur?.12:0);opacity('explore-current-routes',cur?.64:0);opacity('explore-current-hit',cur?.001:0);
    opacity('explore-current-stops-halo',showStops&&(cur||layers.walk)?.72:0);opacity('explore-current-stops',showStops&&(cur||layers.walk)?.96:0);
    opacity('explore-final-glow',fin?(preview?.16:.22):0);opacity('explore-final-routes',fin?(preview?.96:.96):0);opacity('explore-final-hit',interactive&&layers.proposals?.001:0);opacity('explore-final-anchors',showStops&&fin?.98:0);if(map.getLayer('explore-final-anchors'))map.setPaintProperty('explore-final-anchors','circle-stroke-opacity',showStops&&fin?.9:0);
    opacity('municipality-fill',scene?.055:.08);opacity('municipality-outline',scene?.30:.45);opacity('hub',1);opacity('hub-glow',scene?.24:.1);if(map.getLayer('carto'))map.setPaintProperty('carto','raster-opacity',scene?.24:.42);
    if(controls)controls.style.pointerEvents=scene?'auto':'none';
    if(!scene&&popup){popup.remove();popup=null;}
  }

  function fit(force=false){
    if(!lineage||(!force&&fitted))return;const b=new maplibregl.LngLatBounds();
    [...lineage.currentData.features,...lineage.finalData.features,...lineage.anchorData.features].forEach(f=>{const c=f.geometry.coordinates;if(f.geometry.type==='Point')b.extend(c);else c.forEach(x=>b.extend(x));});
    map.fitBounds(b,{padding:innerWidth<800?{top:85,right:24,bottom:195,left:24}:{top:100,right:460,bottom:75,left:60},maxZoom:12.5,duration:window.__analysisJourneyReduceMotion?0:900,pitch:50,bearing:3});fitted=true;
  }
  function interactions(on){if(on){map.dragPan?.enable();map.scrollZoom?.enable();map.doubleClickZoom?.enable();map.boxZoom?.enable();map.keyboard?.enable();map.touchZoomRotate?.enable();map.dragRotate?.enable();}else{map.dragRotate?.disable();map.touchZoomRotate?.disableRotation();}}
  function enter(){if(document.body.dataset.scene!=='explore'||active)return;active=true;document.body.classList.add('is-map-exploring');document.documentElement.classList.add('is-map-exploring');interactions(true);render();requestAnimationFrame(()=>fit(true));}
  function exit(){if(!active)return;active=false;document.body.classList.remove('is-map-exploring');document.documentElement.classList.remove('is-map-exploring');interactions(false);if(popup){popup.remove();popup=null;}render();}

  function inspect(kind,f,lngLat){
    const p=f.properties||{};
    if(kind==='anchor'){const k=p.kind;if(k==='PROPOSED_STOP')return show(f.geometry.coordinates,card('Nuova fermata candidata','Fermata da verificare sul posto','Appartiene alla lineage certificata ma resta <strong>FIELD CHECK PENDING</strong>.',toArray(p.routes).map(x=>LABELS[x]||x),p.anchor_id));if(k==='RAIL_HUB')return show(f.geometry.coordinates,card('Nodo ferroviario',p.label||'Olgiate-Calco-Brivio FS','Nodo di interscambio attorno al quale vengono valutati gli assetti finalisti.',[],p.anchor_id));return show(f.geometry.coordinates,card('Fermata esistente riutilizzata',p.label||p.anchor_id,'Fermata già presente nella baseline ufficiale.',toArray(p.routes).map(x=>LABELS[x]||x),p.anchor_id));}
    if(kind==='stop')return show(f.geometry.coordinates,card('Fermata della rete attuale',p.name||p.cluster_id,'Fermata fisica dal GTFS ufficiale congelato.',toArray(p.routes),p.cluster_id));
    if(kind==='candidate')return show(lngLat,card('Candidate stop · Stop Universe V2',p.id||'candidata','Punto emerso dai gap di accessibilità su rete bus-eligible. Non è una raccomandazione e resta <strong>FIELD CHECK PENDING</strong>.',[`+${fmt(p.gain,0)} residenti entro 10 min`,p.highway||'classe n.d.'],p.uncertainty||''));
    if(kind==='walk')return show(lngLat,card('Accessibilità pedonale',Number(p.walk)<90?`${fmt(p.walk,1)} minuti`:'tempo n.d.','Tempo di rete pedonale verso la fermata esistente più vicina, non distanza in linea d’aria.',[`${fmt(p.pop,1)} residenti`,'unità edificio × sezione']));
    if(kind==='building')return show(lngLat,card('Edificio DBGT · modello dasimetrico',`${fmt(p.pop,1)} residenti modellati`,'Stima spaziale su sagoma edilizia compatibile con uso residenziale, non dato anagrafico a un civico.',[p.pieces?`${fmt(p.pieces,0)} unità`:'DBGT'],p.building_id||''));
    if(kind==='section')return show(lngLat,card('Sezione di censimento',`${fmt(p.pop2025,1)} residenti 2025`,'Struttura territoriale ISTAT riallineata ai totali comunali POSAS 2025.',['ISTAT','POSAS 2025'],p.SEZ2011||p.section_id||''));
    if(kind==='worldpop')return show(lngLat,card('WorldPop · griglia 100 m',`${fmt(p.pop,1)} residenti modellati`,'Prima rappresentazione spaziale della popolazione usata nello scroll.',['cella 100 m','rappresentazione iniziale']));
    if(kind==='road')return show(lngLat,card('Grafo stradale Gate D',p.uncertain?'Arco con incertezza':'Arco bus-eligible','Segmento del grafo congelato usato per i percorsi finalisti, con sensi unici, accessi e restrizioni di svolta.',[p.highway||'classe n.d.',p.uncertain?'uncertainty flag':'strutturale'],p.way_id||p.osm_way_id||''));
  }

  function clickEvents(){
    map.on('mousemove',e=>{if(!active||document.body.dataset.scene!=='explore')return;const ids=interactiveIds();const hits=ids.length?map.queryRenderedFeatures(e.point,{layers:ids}):[];map.getCanvas().style.cursor=hits.length?'pointer':'grab';});
    map.on('click',e=>{if(!active||document.body.dataset.scene!=='explore')return;const ids=interactiveIds(),hits=ids.length?map.queryRenderedFeatures(e.point,{layers:ids}):[];if(!hits.length){if(popup)popup.remove();popup=null;return;}const find=id=>hits.find(x=>x.layer.id===id);let f;if((f=find('explore-final-anchors')))return inspect('anchor',f,e.lngLat);if((f=find('explore-current-stops')))return inspect('stop',f,e.lngLat);if((f=find('candidates')))return inspect('candidate',f,e.lngLat);if((f=find('piece-halo')))return inspect('walk',f,e.lngLat);if((f=find('buildings-extrude')))return inspect('building',f,e.lngLat);if((f=find('sections-fill')))return inspect('section',f,e.lngLat);if((f=find('worldpop-columns')))return inspect('worldpop',f,e.lngLat);if((f=find('road-network')))return inspect('road',f,e.lngLat);const finals=hits.filter(x=>x.layer.id==='explore-final-hit');if(finals.length){const uniq=[...new Map(finals.map(x=>[x.properties.route_id,x])).values()];return show(e.lngLat,card(uniq.length>1?'Tratto condiviso':'Linea finalista',uniq.map(x=>LABELS[x.properties.route_id]||x.properties.route_id).join(' + '),'Geometria Gate D validata contro la Reduced Path Matrix V2.',uniq.flatMap(x=>[`${fmt(x.properties.distance_km,2)} km`,`${fmt(x.properties.runtime_min,1)} min`])));}const current=hits.filter(x=>x.layer.id==='explore-current-hit');if(current.length){const rs=[...new Set(current.map(x=>x.properties.route).filter(Boolean))];return show(e.lngLat,card('Rete attuale · KML ufficiale',rs.join(' + '),'LineString presi direttamente dai KML ufficiali forniti. Nessun routing, snapping o riparazione sul grafo Gate D.',rs,'CURRENT_SERVICE_KML_GEOMETRY_V1'));}});
  }
  function interactiveIds(){const a=[];if(layers.proposals)a.push('explore-final-anchors','explore-final-hit');if(layers.stops&&(layers.current||layers.walk))a.push('explore-current-stops');if(layers.current)a.push('explore-current-hit');if(layers.candidates)a.push('candidates');if(layers.walk)a.push('piece-halo');if(layers.buildings)a.push('buildings-extrude');if(layers.sections)a.push('sections-fill');if(layers.worldpop)a.push('worldpop-columns');if(layers.roads)a.push('road-network');return a.filter(id=>map.getLayer(id));}

  function sceneChanged(){const here=document.body.dataset.scene==='explore';if(here){render();requestAnimationFrame(()=>fit(false));}else{if(active)exit();fitted=false;render();}}
  function install(){
    lineage=window.__analysisJourneyLineage;if(!lineage?.installed||!lineage.exactRoutes||!window.__analysisJourneyCurrentKmlExact?.installed)return false;
    if(!['current-routes','current-gtfs-stops','final-routes-exact','final-anchors-exact','worldpop','sections','buildings','pieces','candidates'].every(id=>map.getSource(id)))return false;
    buildRouteLayers();addControls();clickEvents();document.querySelector('[data-explore-enter]')?.addEventListener('click',enter);document.addEventListener('keydown',e=>{if(e.key==='Escape'&&active)exit();});new MutationObserver(sceneChanged).observe(document.body,{attributes:true,attributeFilter:['data-scene']});sceneChanged();
    window.__analysisJourneyExplore={installed:true,state:compatibilityState,layers,render,fit:()=>fit(true),enter,exit,isActive:()=>active,ensureRoadGraph:ensureRoads,showAnchor:id=>{const f=lineage.anchorData.features.find(x=>x.properties.anchor_id===id);if(f)inspect('anchor',f,f.geometry.coordinates);return!!f;},showCurrentStop:id=>{const f=lineage.stopData.features.find(x=>x.properties.cluster_id===id);if(f)inspect('stop',f,f.geometry.coordinates);return!!f;}};return true;
  }
  let tries=0;const timer=setInterval(()=>{tries++;if(install()||tries>240)clearInterval(timer);},50);
})();
