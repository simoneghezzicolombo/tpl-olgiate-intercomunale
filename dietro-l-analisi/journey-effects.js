(() => {
  'use strict';

  // Capture the single MapLibre world created by journey.js without coupling the
  // main scrollytelling controller to optional cinematic effects.
  const NativeMap = window.maplibregl && window.maplibregl.Map;
  if (NativeMap) {
    window.maplibregl.Map = new Proxy(NativeMap, {
      construct(Target, args) {
        const instance = Reflect.construct(Target, args, Target);
        window.__analysisJourneyMap = instance;
        return instance;
      }
    });
  }

  const css = document.createElement('style');
  css.textContent = `
    .walk-clock,.service-clock,.lineage-collapse{position:fixed;z-index:22;pointer-events:none;opacity:0;transform:translateY(12px);transition:opacity .35s,transform .35s;backdrop-filter:blur(18px);background:rgba(6,18,28,.64);border:1px solid rgba(255,255,255,.14);box-shadow:0 22px 70px rgba(0,0,0,.26)}
    .walk-clock{right:58px;bottom:28px;width:164px;border-radius:18px;padding:15px 16px}
    .walk-clock__kicker,.service-clock__kicker,.lineage-collapse__kicker{display:block;font:500 8px "DM Mono",monospace;text-transform:uppercase;letter-spacing:.12em;color:#8da1ad}
    .walk-clock__value{display:flex;align-items:baseline;gap:6px;margin-top:5px}.walk-clock__value b{font:400 43px "Newsreader",serif;color:#e9ffff;line-height:1}.walk-clock__value span{font:500 10px "DM Mono",monospace;color:#57d7e8}
    .walk-clock__track{height:3px;border-radius:8px;background:rgba(255,255,255,.09);overflow:hidden;margin-top:10px}.walk-clock__track i{display:block;width:0;height:100%;background:linear-gradient(90deg,#55e1bf,#57d7e8,#f6d36f,#ff9b61,#ff6f61)}
    .walk-clock small{display:block;margin-top:9px;font:400 8px/1.45 "DM Mono",monospace;color:#718894}
    body[data-scene="walk"] .walk-clock,body[data-scene="time"] .service-clock,body[data-scene="finalists"] .lineage-collapse{opacity:1;transform:none}
    .thresholds span.is-reached{border-color:rgba(87,215,232,.55);background:rgba(87,215,232,.09);color:#e9ffff;box-shadow:0 0 22px rgba(87,215,232,.08)}
    .service-clock{left:50%;bottom:28px;transform:translate(-50%,12px);width:min(430px,calc(100vw - 34px));padding:14px 17px;border-radius:18px}
    body[data-scene="time"] .service-clock{transform:translate(-50%,0)}
    .service-clock__row{display:flex;align-items:center;gap:14px;margin-top:7px}.service-clock__minute{font:400 37px "Newsreader",serif;min-width:73px}.service-clock__minute b{font-weight:400;color:white}.service-clock__minute span{color:#8295a1;font-size:18px}.service-clock__legend{display:grid;grid-template-columns:1fr 1fr;gap:5px 14px;flex:1}.service-clock__legend span{font:500 8px/1.4 "DM Mono",monospace;color:#91a3ad}.service-clock__legend i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;box-shadow:0 0 12px currentColor}.service-clock__legend .s16 i{background:#57d7e8;color:#57d7e8}.service-clock__legend .s185 i{background:#ff9b61;color:#ff9b61}.service-clock__note{margin-top:7px;font:400 7px/1.35 "DM Mono",monospace;color:#617985;text-transform:uppercase;letter-spacing:.04em}
    .lineage-collapse{right:58px;bottom:28px;width:260px;border-radius:18px;padding:14px 16px;overflow:hidden}.lineage-collapse__rows{display:grid;gap:8px;margin-top:9px}.lineage-collapse__row{height:28px;display:flex;align-items:center;position:relative}.lineage-pill{position:absolute;min-width:72px;text-align:center;padding:6px 9px;border:1px solid rgba(255,255,255,.15);border-radius:999px;font:500 8px "DM Mono",monospace;transition:transform .15s linear,opacity .15s linear}.lineage-pill.fig{left:0;color:#57d7e8}.lineage-pill.two{right:0;color:#f3f0e8}.lineage-collapse__row b{position:absolute;left:50%;transform:translateX(-50%);font:400 12px "Newsreader",serif;color:#93a7b2;opacity:0;transition:opacity .15s}.lineage-collapse__caption{font:400 8px/1.45 "DM Mono",monospace;color:#718894;margin-top:7px}
    @media(max-width:800px){.walk-clock{right:14px;top:82px;bottom:auto;width:140px}.walk-clock__value b{font-size:34px}.service-clock{bottom:12px}.lineage-collapse{right:14px;top:82px;bottom:auto;width:210px}.service-clock__legend{gap:3px 8px}}
    @media(prefers-reduced-motion:reduce){.walk-clock,.service-clock,.lineage-collapse{transition:none}}
  `;
  document.head.appendChild(css);

  const walkHud = document.createElement('div');
  walkHud.className = 'walk-clock';
  walkHud.innerHTML = '<span class="walk-clock__kicker">tempo di cammino · scroll</span><div class="walk-clock__value"><b>0,0</b><span>min</span></div><div class="walk-clock__track"><i></i></div><small>Le unità si accendono quando diventano raggiungibili sulla rete pedonale.</small>';
  document.body.appendChild(walkHud);

  const serviceHud = document.createElement('div');
  serviceHud.className = 'service-clock';
  serviceHud.innerHTML = '<span class="service-clock__kicker">un’ora tipo · movimento di servizio</span><div class="service-clock__row"><div class="service-clock__minute"><span>:</span><b>00</b></div><div class="service-clock__legend"><span class="s16"><i></i>16 h · due partenze :39</span><span class="s185"><i></i>18,5 h · partenze :03 / :07</span></div></div><div class="service-clock__note">Posizione interpolata lungo la sequenza certificata di anchor. È una rappresentazione del timing, non una traccia GPS del bus.</div>';
  document.body.appendChild(serviceHud);

  const lineageHud = document.createElement('div');
  lineageHud.className = 'lineage-collapse';
  lineageHud.innerHTML = '<span class="lineage-collapse__kicker">quattro lineage → due servizi visibili</span><div class="lineage-collapse__rows"><div class="lineage-collapse__row" data-row="16"><span class="lineage-pill fig">FIG · 16 h</span><b>stesso servizio</b><span class="lineage-pill two">TWO · 16 h</span></div><div class="lineage-collapse__row" data-row="185"><span class="lineage-pill fig">FIG · 18,5 h</span><b>stesso servizio</b><span class="lineage-pill two">TWO · 18,5 h</span></div></div><div class="lineage-collapse__caption">Nel diagnostic finale, dentro ciascuno span coincidono route pubbliche, anchor e departures.</div>';
  document.body.appendChild(lineageHud);

  function routeCoords(route, G) {
    return route.anchors.map(id => id === G.hub.id ? G.hub : G.proposedStops[id]).filter(Boolean).map(s => [s.lon, s.lat]);
  }
  function dist(a,b){
    const lat=(a[1]+b[1])*.5*Math.PI/180;
    const x=(b[0]-a[0])*Math.cos(lat)*111320;
    const y=(b[1]-a[1])*110540;
    return Math.hypot(x,y);
  }
  function pointAlong(coords, t){
    if(!coords.length) return [0,0];
    if(coords.length===1) return coords[0];
    const seg=[]; let total=0;
    for(let i=0;i<coords.length-1;i++){const d=dist(coords[i],coords[i+1]);seg.push(d);total+=d;}
    let target=Math.max(0,Math.min(1,t))*total;
    for(let i=0;i<seg.length;i++){
      if(target<=seg[i]){const q=seg[i]?target/seg[i]:0;return [coords[i][0]+(coords[i+1][0]-coords[i][0])*q,coords[i][1]+(coords[i+1][1]-coords[i][1])*q];}
      target-=seg[i];
    }
    return coords[coords.length-1];
  }

  function install() {
    const map = window.__analysisJourneyMap;
    const G = window.TRA_PAESI_GEO;
    if (!map || !G || !window.gsap || !window.ScrollTrigger || !map.isStyleLoaded() || !map.getLayer('piece-halo')) return false;
    window.clearInterval(waiter);
    gsap.registerPlugin(ScrollTrigger);

    const walkSection = document.querySelector('[data-scene="walk"]');
    const thresholdEls = [...document.querySelectorAll('.thresholds [data-min]')];
    ScrollTrigger.create({
      trigger: walkSection, start:'top 82%', end:'bottom 18%', scrub:true,
      onUpdate:self => {
        if(document.body.dataset.scene !== 'walk') return;
        const threshold = .35 + self.progress * 12.15;
        walkHud.querySelector('b').textContent = threshold.toFixed(1).replace('.',',');
        walkHud.querySelector('.walk-clock__track i').style.width = `${Math.min(100,threshold/12*100)}%`;
        thresholdEls.forEach(el => el.classList.toggle('is-reached', threshold >= Number(el.dataset.min)));
        map.setPaintProperty('piece-halo','circle-opacity',['case',['<=',['get','walk'],threshold],.88,.025]);
        map.setPaintProperty('piece-halo','circle-radius',['case',['<=',['get','walk'],threshold],['interpolate',['linear'],['get','pop'],0,1.5,15,5.2,60,9.5],1]);
      }
    });

    const finalists = document.querySelector('[data-scene="finalists"]');
    ScrollTrigger.create({
      trigger: finalists, start:'top 75%', end:'bottom 25%', scrub:true,
      onUpdate:self => {
        if(document.body.dataset.scene !== 'finalists') return;
        const p=Math.max(0,Math.min(1,(self.progress-.18)/.62));
        lineageHud.querySelectorAll('.lineage-pill.fig').forEach(el=>el.style.transform=`translateX(${p*42}px)`);
        lineageHud.querySelectorAll('.lineage-pill.two').forEach(el=>el.style.transform=`translateX(${-p*42}px)`);
        lineageHud.querySelectorAll('.lineage-collapse__row b').forEach(el=>el.style.opacity=String(Math.max(0,(p-.55)*2.22)));
        lineageHud.querySelectorAll('.lineage-pill').forEach(el=>el.style.opacity=String(1-p*.5));
      }
    });

    if(!map.getSource('service-movers')) map.addSource('service-movers',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
    if(!map.getLayer('service-movers-glow')) map.addLayer({id:'service-movers-glow',type:'circle',source:'service-movers',paint:{'circle-radius':12,'circle-color':['match',['get','package'],'16','#57d7e8','#ff9b61'],'circle-opacity':.22,'circle-blur':.75}});
    if(!map.getLayer('service-movers')) map.addLayer({id:'service-movers',type:'circle',source:'service-movers',paint:{'circle-radius':5,'circle-color':['match',['get','package'],'16','#8defff','#ffb07f'],'circle-opacity':.98,'circle-stroke-width':1.5,'circle-stroke-color':'#07131f'}});

    const movers=[];
    ['16','18.5'].forEach(pkg => G.proposedPackages[pkg].forEach((r,i)=>movers.push({pkg,route:r,coords:routeCoords(r,G),id:`${pkg}-${i+1}`})));
    const start=performance.now();
    function serviceFrame(now){
      const minute=((now-start)/330)%60; // one visible service hour every ~19.8 s
      serviceHud.querySelector('.service-clock__minute b').textContent=String(Math.floor(minute)).padStart(2,'0');
      const features=[];
      if(document.body.dataset.scene==='time'){
        movers.forEach(m=>{
          const elapsed=(minute-m.route.phase+60)%60;
          if(elapsed<=m.route.runtime){
            const pt=pointAlong(m.coords,elapsed/m.route.runtime);
            features.push({type:'Feature',properties:{package:m.pkg,route:m.id},geometry:{type:'Point',coordinates:pt}});
          }
        });
      }
      const src=map.getSource('service-movers'); if(src) src.setData({type:'FeatureCollection',features});
      requestAnimationFrame(serviceFrame);
    }
    requestAnimationFrame(serviceFrame);
    return true;
  }

  const waiter = window.setInterval(install, 120);
  window.setTimeout(() => window.clearInterval(waiter), 15000);
})();
