(() => {
  'use strict';
  const J = window.ANALYSIS_JOURNEY_DATA;
  const G = window.TRA_PAESI_GEO;
  if (!J || !G || !window.maplibregl) {
    document.querySelector('#loader p').textContent = 'Impossibile inizializzare il journey.';
    return;
  }

  const style = {
    version: 8,
    sources: {
      carto: {
        type: 'raster', tileSize: 256,
        tiles: [
          'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
          'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
          'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png'
        ], attribution: '© OpenStreetMap contributors © CARTO'
      }
    },
    layers: [
      {id:'bg', type:'background', paint:{'background-color':'#07131f'}},
      {id:'carto', type:'raster', source:'carto', paint:{'raster-opacity':0.42,'raster-saturation':-0.65,'raster-contrast':0.12,'raster-brightness-max':0.56}}
    ]
  };

  const map = new maplibregl.Map({
    container: 'map', style, center: [9.398, 45.732], zoom: 11.75, pitch: 58, bearing: -18,
    antialias: true, attributionControl: true, fadeDuration: 0, maxPitch: 78
  });
  map.dragRotate.disable();
  map.touchZoomRotate.disableRotation();

  const chapters = [...document.querySelectorAll('.chapter')];
  const rail = document.getElementById('chapterRail');
  const hudIndex = document.getElementById('sceneIndex');
  const hudName = document.getElementById('sceneName');
  const progressFill = document.getElementById('progressFill');
  const loader = document.getElementById('loader');
  let activeScene = 'intro';
  let roadLoaded = false;
  let roadLoading = false;
  let layersReady = false;

  chapters.forEach((c, i) => {
    const b = document.createElement('button');
    b.className = 'rail-dot' + (i === 0 ? ' active' : '');
    b.title = c.dataset.label;
    b.addEventListener('click', () => c.scrollIntoView({behavior:'smooth', block:'center'}));
    rail.appendChild(b);
  });
  const railDots = [...rail.children];

  const pcsGeo = {type:'FeatureCollection', features:J.pieces.map((r,i)=>({
    type:'Feature', id:i, properties:{pop:r[2],walk:r[3] == null ? 99 : r[3],muni:r[4]}, geometry:{type:'Point',coordinates:[r[0],r[1]]}
  }))};
  const candidatesGeo = {type:'FeatureCollection', features:J.candidates.map((r)=>({
    type:'Feature', properties:{id:r[0],muni:r[3],gain:r[4],highway:r[5],uncertainty:r[6]}, geometry:{type:'Point',coordinates:[r[1],r[2]]}
  }))};
  const existingGeo = {type:'FeatureCollection', features:J.existingStops.map((r)=>({
    type:'Feature', properties:{cluster:r[0],name:r[1],muni:r[4],routes:r[5]}, geometry:{type:'Point',coordinates:[r[2],r[3]]}
  }))};

  function currentRoutesGeo() {
    const features = [];
    G.currentPatterns.forEach(p => {
      const coords = p.stopIds.map(id => G.currentStops[id]).filter(Boolean).map(s => [s.lon,s.lat]);
      if (coords.length > 1) features.push({type:'Feature',properties:{route:p.route,direction:p.direction},geometry:{type:'LineString',coordinates:coords}});
    });
    return {type:'FeatureCollection',features};
  }
  function finalistGeo(span) {
    const features = [];
    G.proposedPackages[span].forEach((r,idx)=>{
      const coords = r.anchors.map(id => id === G.hub.id ? G.hub : G.proposedStops[id]).filter(Boolean).map(s => [s.lon,s.lat]);
      features.push({type:'Feature',properties:{span,route:r.id,ordinal:idx+1,phase:r.phase},geometry:{type:'LineString',coordinates:coords}});
    });
    return {type:'FeatureCollection',features};
  }
  const hubGeo = {type:'FeatureCollection',features:[{type:'Feature',properties:{name:G.hub.name},geometry:{type:'Point',coordinates:[G.hub.lon,G.hub.lat]}}]};

  async function loadBase64GzipJson(urls){
    const chunks = await Promise.all(urls.map(async url => {
      const r=await fetch(url); if(!r.ok) throw new Error(`${url} ${r.status}`); return (await r.text()).trim();
    }));
    const b64=chunks.join('');
    const bin=atob(b64); const bytes=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
    if(window.pako) return JSON.parse(pako.inflate(bytes,{to:'string'}));
    if('DecompressionStream' in window){
      const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
      return JSON.parse(new TextDecoder().decode(await new Response(stream).arrayBuffer()));
    }
    throw new Error('gzip decompression unavailable');
  }

  function addSource(id, data){ if(!map.getSource(id)) map.addSource(id,{type:'geojson',data}); }
  function addLayer(layer,before){ if(!map.getLayer(layer.id)) map.addLayer(layer,before); }
  function opacity(id, value){
    if(!map.getLayer(id)) return;
    const type=map.getLayer(id).type;
    const prop = type==='fill-extrusion'?'fill-extrusion-opacity':type==='fill'?'fill-opacity':type==='line'?'line-opacity':type==='circle'?'circle-opacity':type==='symbol'?'text-opacity':null;
    if(prop) map.setPaintProperty(id,prop,value);
  }

  async function prepareLayers(){
    const boundaries = await loadBase64GzipJson(J.meta.localAssets.boundaries);
    addSource('municipalities',boundaries);
    addLayer({id:'municipality-fill',type:'fill',source:'municipalities',paint:{'fill-color':'#143348','fill-opacity':0.08}});
    addLayer({id:'municipality-outline',type:'line',source:'municipalities',paint:{'line-color':'#c6f7ff','line-width':1.1,'line-opacity':0.55,'line-dasharray':[2,2]}});

    const [worldpopData, sectionsData, buildingsData] = await Promise.all([
      loadBase64GzipJson(['data-worldpop.geojson.gz.0.b64']),
      loadBase64GzipJson(['data-sections.geojson.gz.0.b64']),
      loadBase64GzipJson(['data-buildings.geojson.gz.0.b64','data-buildings.geojson.gz.1.b64','data-buildings.geojson.gz.2.b64','data-buildings.geojson.gz.3.b64','data-buildings.geojson.gz.4.b64'])
    ]);
    addSource('worldpop',worldpopData);
    addLayer({id:'worldpop-columns',type:'fill-extrusion',source:'worldpop',paint:{
      'fill-extrusion-color':['interpolate',['linear'],['get','pop'],0,'#17384c',3,'#296b80',12,'#57d7e8',28,'#ffd07d',50,'#ff9b61'],
      'fill-extrusion-height':['interpolate',['linear'],['get','pop'],0,1,50,130],
      'fill-extrusion-base':0,'fill-extrusion-opacity':0
    }});
    addLayer({id:'worldpop-wire',type:'line',source:'worldpop',paint:{'line-color':'#92edf7','line-width':0.45,'line-opacity':0}});

    addSource('sections',sectionsData);
    addLayer({id:'sections-fill',type:'fill-extrusion',source:'sections',paint:{
      'fill-extrusion-color':['interpolate',['linear'],['get','pop2025'],0,'#1e3444',80,'#376c78',250,'#cf965e',600,'#ff9b61'],
      'fill-extrusion-height':['interpolate',['linear'],['get','pop2025'],0,1,700,55],
      'fill-extrusion-opacity':0
    }});
    addLayer({id:'sections-outline',type:'line',source:'sections',paint:{'line-color':'#ffbd91','line-width':1,'line-opacity':0}});

    addSource('buildings',buildingsData);
    addLayer({id:'buildings-extrude',type:'fill-extrusion',source:'buildings',paint:{
      'fill-extrusion-color':['interpolate',['linear'],['get','pop'],0,'#42606c',2,'#72a6aa',8,'#7be2c7',22,'#ffe18f',60,'#ff9b61',180,'#ff6f61'],
      'fill-extrusion-height':['interpolate',['linear'],['get','pop'],0,1,2,4,8,11,22,22,60,45,180,85],
      'fill-extrusion-base':0,'fill-extrusion-opacity':0
    }});
    addLayer({id:'buildings-outline',type:'line',source:'buildings',paint:{'line-color':'#e9ffff','line-width':0.45,'line-opacity':0}});

    addSource('pieces',pcsGeo);
    addLayer({id:'piece-halo',type:'circle',source:'pieces',paint:{
      'circle-radius':['interpolate',['linear'],['get','pop'],0,1.2,15,4.5,60,8],
      'circle-color':['step',['get','walk'],'#55e1bf',5,'#57d7e8',8,'#f6d36f',10,'#ff9b61',12,'#ff6f61'],
      'circle-blur':0.35,'circle-opacity':0,'circle-stroke-width':0.4,'circle-stroke-color':'rgba(255,255,255,.55)'
    }});

    addSource('existing-stops',existingGeo);
    addLayer({id:'existing-stops-halo',type:'circle',source:'existing-stops',paint:{'circle-radius':10,'circle-color':'#ffffff','circle-opacity':0,'circle-blur':0.85}});
    addLayer({id:'existing-stops',type:'circle',source:'existing-stops',paint:{'circle-radius':3.2,'circle-color':'#ffffff','circle-opacity':0,'circle-stroke-width':1.3,'circle-stroke-color':'#07131f'}});

    addSource('candidates',candidatesGeo);
    addLayer({id:'candidate-halo',type:'circle',source:'candidates',paint:{'circle-radius':9,'circle-color':'#57d7e8','circle-opacity':0,'circle-blur':0.8}});
    addLayer({id:'candidates',type:'circle',source:'candidates',paint:{
      'circle-radius':['interpolate',['linear'],['get','gain'],0,2,100,3.2,350,5,800,7.5],
      'circle-color':['interpolate',['linear'],['get','gain'],0,'#5c7d89',80,'#57d7e8',250,'#55e1bf',700,'#ff9b61'],
      'circle-opacity':0,'circle-stroke-width':0.7,'circle-stroke-color':'#dfffff'
    }});

    addSource('current-routes',currentRoutesGeo());
    addLayer({id:'current-route-glow',type:'line',source:'current-routes',paint:{'line-color':['match',['get','route'],'D184','#4ca5ff','D185','#ff9b61','#fff'],'line-width':9,'line-blur':7,'line-opacity':0}});
    addLayer({id:'current-routes',type:'line',source:'current-routes',paint:{'line-color':['match',['get','route'],'D184','#4ca5ff','D185','#ff9b61','#fff'],'line-width':3.2,'line-opacity':0,'line-dasharray':[2,1]}});

    addSource('final16',finalistGeo('16'));
    addLayer({id:'final16-glow',type:'line',source:'final16',paint:{'line-color':'#57d7e8','line-width':12,'line-blur':9,'line-opacity':0}});
    addLayer({id:'final16',type:'line',source:'final16',paint:{'line-color':'#7ce8f5','line-width':4,'line-opacity':0,'line-dasharray':[2,0.65]}});
    addSource('final185',finalistGeo('18.5'));
    addLayer({id:'final185-glow',type:'line',source:'final185',paint:{'line-color':'#ff9b61','line-width':12,'line-blur':9,'line-opacity':0}});
    addLayer({id:'final185',type:'line',source:'final185',paint:{'line-color':'#ffb07f','line-width':4,'line-opacity':0,'line-dasharray':[2,0.65]}});

    addSource('hub',hubGeo);
    addLayer({id:'hub-glow',type:'circle',source:'hub',paint:{'circle-radius':18,'circle-color':'#ffffff','circle-opacity':0.12,'circle-blur':0.85}});
    addLayer({id:'hub',type:'circle',source:'hub',paint:{'circle-radius':5.5,'circle-color':'#ffffff','circle-opacity':1,'circle-stroke-width':2,'circle-stroke-color':'#07131f'}});
    const markerEl=document.createElement('div'); markerEl.className='hub-marker'; markerEl.innerHTML='<span></span><b>Olgiate-Calco-Brivio FS</b>';
    new maplibregl.Marker({element:markerEl,anchor:'bottom'}).setLngLat([G.hub.lon,G.hub.lat]).addTo(map);
    layersReady = true;
  }

  function resetLayers(){
    ['worldpop-columns','worldpop-wire','sections-fill','sections-outline','buildings-extrude','buildings-outline','piece-halo','existing-stops','existing-stops-halo','candidate-halo','candidates','current-route-glow','current-routes','final16-glow','final16','final185-glow','final185','road-shadow','road-network'].forEach(id=>opacity(id,0));
    opacity('municipality-fill',0.08); opacity('municipality-outline',0.45); opacity('hub',1); opacity('hub-glow',0.1); document.body.dataset.scene=activeScene;
  }
  function camera(opts){ map.easeTo({duration:1050,essential:true,...opts}); }

  function setScene(scene){
    if(!layersReady) return;
    activeScene = scene; resetLayers(); document.body.dataset.scene=scene;
    map.setPaintProperty('carto','raster-opacity',0.42);
    switch(scene){
      case 'intro':
        opacity('municipality-fill',0.10); opacity('municipality-outline',0.75); opacity('hub-glow',0.28);
        camera({center:[9.399,45.733],zoom:11.4,pitch:61,bearing:-18}); break;
      case 'grid':
        opacity('worldpop-columns',0.82); opacity('worldpop-wire',0.35); opacity('municipality-outline',0.18);
        map.setPaintProperty('carto','raster-opacity',0.24);
        camera({center:[9.399,45.731],zoom:12.2,pitch:64,bearing:-25}); break;
      case 'sections':
        opacity('worldpop-columns',0.12); opacity('sections-fill',0.64); opacity('sections-outline',0.58);
        map.setPaintProperty('carto','raster-opacity',0.18);
        camera({center:[9.397,45.731],zoom:12.15,pitch:57,bearing:14}); break;
      case 'buildings':
        opacity('sections-fill',0.07); opacity('sections-outline',0.10); opacity('buildings-extrude',0.92); opacity('buildings-outline',0.30);
        map.setPaintProperty('carto','raster-opacity',0.16);
        camera({center:[9.402,45.728],zoom:13.55,pitch:72,bearing:-34}); break;
      case 'walk':
        opacity('buildings-extrude',0.30); opacity('buildings-outline',0.08); opacity('piece-halo',0.72); opacity('existing-stops-halo',0.18); opacity('existing-stops',0.95);
        map.setPaintProperty('carto','raster-opacity',0.20);
        camera({center:[9.398,45.731],zoom:12.7,pitch:57,bearing:-12}); break;
      case 'roads':
        loadRoadGraph().then(()=>{if(activeScene==='roads'){opacity('road-shadow',0.40);opacity('road-network',0.72);}});
        opacity('municipality-outline',0.18); opacity('hub-glow',0.3);
        map.setPaintProperty('carto','raster-opacity',0.16);
        camera({center:[9.397,45.732],zoom:12.3,pitch:67,bearing:26}); break;
      case 'baseline':
        opacity('current-route-glow',0.34); opacity('current-routes',0.95); opacity('existing-stops',0.75); opacity('hub-glow',0.28);
        map.setPaintProperty('carto','raster-opacity',0.28);
        camera({center:[9.410,45.738],zoom:11.65,pitch:48,bearing:-13}); break;
      case 'candidates':
        loadRoadGraph().then(()=>{if(activeScene==='candidates'){opacity('road-network',0.15);}});
        opacity('candidate-halo',0.16); opacity('candidates',0.88); opacity('existing-stops',0.32); opacity('hub-glow',0.25);
        map.setPaintProperty('carto','raster-opacity',0.18);
        camera({center:[9.397,45.731],zoom:12.05,pitch:60,bearing:-25}); break;
      case 'finalists':
        opacity('candidates',0.08); opacity('final16-glow',0.28); opacity('final16',0.96); opacity('final185-glow',0.20); opacity('final185',0.82); opacity('hub-glow',0.38);
        map.setPaintProperty('carto','raster-opacity',0.22);
        camera({center:[9.393,45.733],zoom:12.1,pitch:57,bearing:9}); break;
      case 'time':
        opacity('final16-glow',0.22); opacity('final16',0.72); opacity('final185-glow',0.22); opacity('final185',0.72); opacity('hub-glow',0.55);
        map.setPaintProperty('carto','raster-opacity',0.14);
        camera({center:[G.hub.lon,G.hub.lat],zoom:15.05,pitch:68,bearing:-28}); break;
      case 'end':
        opacity('buildings-extrude',0.10); opacity('piece-halo',0.10); opacity('municipality-outline',0.25); opacity('final16',0.38); opacity('final185',0.38); opacity('hub-glow',0.40);
        if(roadLoaded) opacity('road-network',0.08);
        map.setPaintProperty('carto','raster-opacity',0.24);
        camera({center:[9.398,45.733],zoom:11.7,pitch:62,bearing:-18}); break;
    }
  }

  async function loadRoadGraph(){
    if(roadLoaded || roadLoading) return;
    roadLoading = true;
    try{
      const geo = await loadBase64GzipJson(J.meta.localAssets.roads);
      addSource('road-graph',geo);
      addLayer({id:'road-shadow',type:'line',source:'road-graph',paint:{'line-color':'#06101a','line-width':4.2,'line-opacity':0}});
      addLayer({id:'road-network',type:'line',source:'road-graph',paint:{'line-color':['case',['boolean',['get','uncertain'],false],'#ff9b61','#57d7e8'],'line-width':['interpolate',['linear'],['zoom'],10,.3,13,1.15,16,2.4],'line-opacity':0}});
      roadLoaded=true;
    }catch(err){
      console.warn('Frozen Gate D graph could not be loaded',err);
      document.body.classList.add('road-fallback');
    }finally{roadLoading=false;}
  }

  function updateActive(index){
    chapters.forEach((c,i)=>c.classList.toggle('is-active',i===index));
    railDots.forEach((d,i)=>d.classList.toggle('active',i===index));
    hudIndex.textContent = String(index+1).padStart(2,'0');
    hudName.textContent = chapters[index].dataset.label;
    setScene(chapters[index].dataset.scene);
  }

  map.on('load', async () => {
    try{
      await prepareLayers();
      if(window.gsap && window.ScrollTrigger){
        gsap.registerPlugin(ScrollTrigger);
        chapters.forEach((c,i)=>{
          ScrollTrigger.create({trigger:c,start:'top 55%',end:'bottom 45%',onEnter:()=>updateActive(i),onEnterBack:()=>updateActive(i)});
          if(c.dataset.scene==='grid') ScrollTrigger.create({trigger:c,start:'top 85%',end:'bottom 15%',scrub:true,onUpdate:self=>{
            if(activeScene==='grid'&&map.getLayer('worldpop-columns')) map.setPaintProperty('worldpop-columns','fill-extrusion-height',['interpolate',['linear'],['get','pop'],0,1,50,30+150*self.progress]);
          }});
          if(c.dataset.scene==='buildings') ScrollTrigger.create({trigger:c,start:'top 80%',end:'bottom 20%',scrub:true,onUpdate:self=>{
            if(activeScene==='buildings'){opacity('sections-fill',Math.max(0,.18-.16*self.progress));opacity('buildings-extrude',.3+.62*self.progress);}
          }});
        });
        ScrollTrigger.create({start:0,end:'max',onUpdate:self=>progressFill.style.width=`${(self.progress*100).toFixed(2)}%`});
      } else {
        const obs=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting) updateActive(chapters.indexOf(e.target));}),{threshold:.5}); chapters.forEach(c=>obs.observe(c));
        addEventListener('scroll',()=>{const max=document.documentElement.scrollHeight-innerHeight;progressFill.style.width=`${(scrollY/max)*100}%`;});
      }
      setScene('intro');
      setTimeout(()=>loader.classList.add('hidden'),380);
    }catch(err){
      console.error(err); loader.querySelector('p').textContent='Il layer territoriale non si è caricato. Ricarica la pagina.';
    }
  });

  let pulse=0;
  function animate(){
    pulse += 0.035;
    if(layersReady){
      if(map.getLayer('hub-glow')) map.setPaintProperty('hub-glow','circle-radius',15+5*Math.sin(pulse));
      if(activeScene==='candidates'&&map.getLayer('candidate-halo')) map.setPaintProperty('candidate-halo','circle-radius',7+4*(.5+.5*Math.sin(pulse*1.4)));
      if(activeScene==='time'&&map.getLayer('hub-glow')) map.setPaintProperty('hub-glow','circle-radius',20+10*(.5+.5*Math.sin(pulse*2)));
    }
    requestAnimationFrame(animate);
  }
  animate();

  document.getElementById('restartBtn').addEventListener('click',()=>scrollTo({top:0,behavior:'smooth'}));
  document.getElementById('worldpopCount').textContent = J.meta.worldpopCells.toLocaleString('it-IT');
  document.getElementById('buildingCount').textContent = J.meta.buildings.toLocaleString('it-IT');
})();
