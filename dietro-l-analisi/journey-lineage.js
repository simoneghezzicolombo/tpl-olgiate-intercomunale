(() => {
  'use strict';
  const map=window.__analysisJourneyMap;
  if(!map) return;

  const FILES={
    currentRoutes:['current-routes-gtfs.geojson.gz.b64.0','current-routes-gtfs.geojson.gz.b64.1'],
    currentStops:['current-stops-gtfs.geojson.gz.b64.0'],
    finalRoutes:['finalist-routes-gated.geojson.gz.b64.0','finalist-routes-gated.geojson.gz.b64.1','finalist-routes-gated.geojson.gz.b64.2'],
    finalAnchors:['finalist-route-anchors.geojson.gz.b64.0']
  };
  const COLORS={
    D184:'#4ca5ff',D185:'#ff9b61',
    R2_23d58cd05658247380d7:'#57d7e8',
    R2_65db885119e69d50c7d4:'#55e1bf',
    R2_b2032eeb31cba06561f0:'#ff9b61',
    R2_2ffb6743b10bb3f0a97d:'#f6d36f'
  };
  const LABELS={
    R2_23d58cd05658247380d7:'16 h · linea 1',
    R2_65db885119e69d50c7d4:'16 h · linea 2',
    R2_b2032eeb31cba06561f0:'18 h 30 · linea 1',
    R2_2ffb6743b10bb3f0a97d:'18 h 30 · linea 2'
  };
  let currentSelection='ALL',finalSelection='ALL';
  let currentData,stopData,finalData,anchorData;

  async function load(names){
    const parts=await Promise.all(names.map(async n=>{const r=await fetch(n);if(!r.ok)throw new Error(`${n} ${r.status}`);return (await r.text()).trim();}));
    const bin=atob(parts.join(''));const bytes=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);
    return JSON.parse(pako.inflate(bytes,{to:'string'}));
  }
  function opacity(id,v){if(map.getLayer(id))map.setPaintProperty(id,map.getLayer(id).type==='line'?'line-opacity':'circle-opacity',v);}
  function bounds(data){
    const b=new maplibregl.LngLatBounds();
    data.features.forEach(f=>{const c=f.geometry.coordinates;(f.geometry.type==='Point'?[c]:c).forEach(x=>b.extend(x));});
    return b;
  }
  function addControls(){
    const style=document.createElement('style');style.textContent=`
      .route-controls{position:fixed;z-index:28;right:34px;bottom:34px;width:min(340px,calc(100vw - 28px));padding:12px;border-radius:18px;border:1px solid rgba(255,255,255,.14);background:rgba(6,18,28,.78);backdrop-filter:blur(18px);box-shadow:0 18px 55px rgba(0,0,0,.25);opacity:0;pointer-events:none;transform:translateY(8px);transition:.25s}
      body[data-scene="baseline"] .route-controls.current,body[data-scene="finalists"] .route-controls.final{opacity:1;pointer-events:auto;transform:none}
      .route-controls p{margin:0 0 8px;font:600 10px Manrope,system-ui,sans-serif;color:#d9eef5}.route-controls small{display:block;margin-top:8px;font:500 9px/1.35 Manrope,system-ui,sans-serif;color:#90a5af}
      .route-controls__row{display:flex;gap:6px;flex-wrap:wrap}.route-controls button{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.04);color:#dff7ff;border-radius:999px;padding:7px 9px;font:600 10px Manrope,system-ui,sans-serif;cursor:pointer}.route-controls button.is-active{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.4)}
      .route-controls i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;background:var(--c,#fff)}
      @media(max-width:800px){.route-controls{right:14px;bottom:14px;width:min(310px,calc(100vw - 28px));padding:10px}.route-controls small{display:none}}
    `;document.head.appendChild(style);
    const c=document.createElement('div');c.className='route-controls current';c.innerHTML='<p>D184 e D185</p><div class="route-controls__row"><button data-r="ALL" class="is-active">Entrambe</button><button data-r="D184"><i style="--c:#4ca5ff"></i>D184</button><button data-r="D185"><i style="--c:#ff9b61"></i>D185</button></div><small>Tracciati e fermate dal GTFS ufficiale.</small>';document.body.appendChild(c);
    const f=document.createElement('div');f.className='route-controls final';f.innerHTML='<p>Le quattro linee finali</p><div class="route-controls__row"><button data-f="ALL" class="is-active">Tutte</button>'+Object.entries(LABELS).map(([id,l])=>`<button data-f="${id}"><i style="--c:${COLORS[id]}"></i>${l}</button>`).join('')+'</div><small>Se due linee passano sulla stessa strada, si sovrappongono davvero.</small>';document.body.appendChild(f);
    c.querySelectorAll('button').forEach(btn=>btn.onclick=()=>{currentSelection=btn.dataset.r;c.querySelectorAll('button').forEach(x=>x.classList.toggle('is-active',x===btn));applyCurrent();});
    f.querySelectorAll('button').forEach(btn=>btn.onclick=()=>{finalSelection=btn.dataset.f;f.querySelectorAll('button').forEach(x=>x.classList.toggle('is-active',x===btn));applyFinal();});
  }
  function applyCurrentStopColors(){
    const hasD184=['>=',['index-of','D184',['get','routes']],0];
    const hasD185=['>=',['index-of','D185',['get','routes']],0];
    const outer=currentSelection==='D184'?COLORS.D184:currentSelection==='D185'?COLORS.D185:['case',hasD184,COLORS.D184,hasD185,COLORS.D185,'#fff'];
    const inner=currentSelection==='D184'?COLORS.D184:currentSelection==='D185'?COLORS.D185:['case',hasD185,COLORS.D185,hasD184,COLORS.D184,'#fff'];
    if(map.getLayer('current-gtfs-stops-halo'))map.setPaintProperty('current-gtfs-stops-halo','circle-color',outer);
    if(map.getLayer('current-gtfs-stops'))map.setPaintProperty('current-gtfs-stops','circle-color',inner);
  }
  function applyCurrent(){
    const filter=currentSelection==='ALL'?null:['==',['get','route'],currentSelection];
    ['current-routes','current-route-glow'].forEach(id=>{if(map.getLayer(id))map.setFilter(id,filter);});
    const sf=currentSelection==='ALL'?null:['>=',['index-of',currentSelection,['get','routes']],0];
    ['current-gtfs-stops','current-gtfs-stops-halo'].forEach(id=>{if(map.getLayer(id))map.setFilter(id,sf);});
    applyCurrentStopColors();
  }
  function applyFinal(){
    const filter=finalSelection==='ALL'?null:['==',['get','route_id'],finalSelection];
    ['final-routes-exact','final-routes-exact-glow'].forEach(id=>{if(map.getLayer(id))map.setFilter(id,filter);});
    if(map.getLayer('final-anchors-exact')) map.setFilter('final-anchors-exact',finalSelection==='ALL'?['!=',['get','anchor_id'],'rail:S01514']:['all',['!=',['get','anchor_id'],'rail:S01514'],['>=',['index-of',finalSelection,['get','routes']],0]]);
  }
  function scene(){
    const s=document.body.dataset.scene;
    const baseline=s==='baseline', finals=['finalists','time','end'].includes(s);
    opacity('current-routes',baseline?.92:0);opacity('current-route-glow',baseline?.22:0);opacity('current-gtfs-stops',baseline?.98:0);opacity('current-gtfs-stops-halo',baseline?.82:0);
    opacity('final16',0);opacity('final16-glow',0);opacity('final185',0);opacity('final185-glow',0);
    opacity('final-routes-exact',finals?(s==='finalists'?.96:.62):0);opacity('final-routes-exact-glow',finals?(s==='finalists'?.20:.10):0);opacity('final-anchors-exact',finals?(s==='finalists'?.96:.60):0);
    if(baseline) map.fitBounds(bounds(currentData),{padding:innerWidth<800?35:70,maxZoom:12,duration:window.__analysisJourneyReduceMotion?0:850,pitch:40,bearing:-8});
    if(s==='finalists') map.fitBounds(bounds(finalData),{padding:innerWidth<800?45:80,maxZoom:12.7,duration:window.__analysisJourneyReduceMotion?0:850,pitch:54,bearing:8});
  }
  async function install(){
    [currentData,stopData,finalData,anchorData]=await Promise.all([load(FILES.currentRoutes),load(FILES.currentStops),load(FILES.finalRoutes),load(FILES.finalAnchors)]);
    map.getSource('current-routes')?.setData(currentData);
    if(!map.getSource('current-gtfs-stops'))map.addSource('current-gtfs-stops',{type:'geojson',data:stopData});
    if(!map.getLayer('current-gtfs-stops-halo'))map.addLayer({id:'current-gtfs-stops-halo',type:'circle',source:'current-gtfs-stops',paint:{'circle-radius':['interpolate',['linear'],['zoom'],9,4.2,12,6.2,15,8],'circle-color':'#fff','circle-opacity':0,'circle-blur':.08}});
    if(!map.getLayer('current-gtfs-stops'))map.addLayer({id:'current-gtfs-stops',type:'circle',source:'current-gtfs-stops',paint:{'circle-radius':['interpolate',['linear'],['zoom'],9,2.4,12,3.8,15,5.2],'circle-color':'#fff','circle-opacity':0,'circle-stroke-width':1.2,'circle-stroke-color':'#07131f','circle-stroke-opacity':.7}});
    if(!map.getSource('final-routes-exact'))map.addSource('final-routes-exact',{type:'geojson',data:finalData});
    const color=['match',['get','route_id'],'R2_23d58cd05658247380d7',COLORS.R2_23d58cd05658247380d7,'R2_65db885119e69d50c7d4',COLORS.R2_65db885119e69d50c7d4,'R2_b2032eeb31cba06561f0',COLORS.R2_b2032eeb31cba06561f0,'R2_2ffb6743b10bb3f0a97d',COLORS.R2_2ffb6743b10bb3f0a97d,'#fff'];
    map.addLayer({id:'final-routes-exact-glow',type:'line',source:'final-routes-exact',paint:{'line-color':color,'line-width':11,'line-blur':8,'line-opacity':0}});
    map.addLayer({id:'final-routes-exact',type:'line',source:'final-routes-exact',paint:{'line-color':color,'line-width':['interpolate',['linear'],['zoom'],9,2.6,12,4.2,15,5.5],'line-opacity':0}});
    map.addSource('final-anchors-exact',{type:'geojson',data:anchorData});
    map.addLayer({id:'final-anchors-exact',type:'circle',source:'final-anchors-exact',filter:['!=',['get','anchor_id'],'rail:S01514'],paint:{'circle-radius':['interpolate',['linear'],['zoom'],9,2.8,12,4.2,15,6],'circle-color':['case',['==',['get','kind'],'PROPOSED_STOP'],'#ffd36d','#fff'],'circle-opacity':0,'circle-stroke-width':1.4,'circle-stroke-color':'#07131f','circle-stroke-opacity':0}});
    addControls();applyCurrent();applyFinal();
    new MutationObserver(scene).observe(document.body,{attributes:true,attributeFilter:['data-scene']});
    scene();
    window.__analysisJourneyLineage={installed:true,exactRoutes:true,currentData,stopData,finalData,anchorData,apply:scene};
  }
  install().catch(err=>console.error('Exact route geometry failed',err));
})();
