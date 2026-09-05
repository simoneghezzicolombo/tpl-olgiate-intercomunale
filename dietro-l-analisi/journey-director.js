(() => {
  'use strict';

  const style = document.createElement('style');
  style.textContent = `
    .representation-meter,.search-compression{position:fixed;z-index:23;pointer-events:none;opacity:0;transform:translateY(12px);transition:opacity .35s,transform .35s;backdrop-filter:blur(20px);background:rgba(6,18,28,.66);border:1px solid rgba(255,255,255,.14);box-shadow:0 22px 70px rgba(0,0,0,.28)}
    .representation-meter{left:28px;bottom:55px;width:310px;padding:15px 16px;border-radius:18px}
    .representation-meter__kicker,.search-compression__kicker{display:block;font:500 8px "DM Mono",monospace;text-transform:uppercase;letter-spacing:.12em;color:#8da1ad}
    .representation-meter__line{height:3px;border-radius:6px;background:rgba(255,255,255,.09);margin:12px 0 10px;overflow:hidden}.representation-meter__line i{display:block;height:100%;width:0;background:linear-gradient(90deg,#57d7e8,#f6d36f,#ff9b61);transition:width .1s linear}
    .representation-meter__steps{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.representation-meter__steps span{padding:7px 8px;border-radius:10px;border:1px solid rgba(255,255,255,.08);font:500 8px/1.35 "DM Mono",monospace;color:#6f8490;transition:.2s}.representation-meter__steps span b{display:block;font:400 15px "Newsreader",serif;color:#8fa0aa;margin-top:2px}.representation-meter__steps span.is-on{color:#dffbff;border-color:rgba(87,215,232,.4);background:rgba(87,215,232,.07)}.representation-meter__steps span.is-on b{color:#fff}
    .representation-meter__note{margin-top:9px;font:400 7px/1.45 "DM Mono",monospace;color:#657b87;text-transform:uppercase;letter-spacing:.035em}
    body[data-scene="grid"] .representation-meter,body[data-scene="sections"] .representation-meter,body[data-scene="buildings"] .representation-meter,body[data-scene="candidates"] .search-compression{opacity:1;transform:none}
    .search-compression{right:58px;bottom:30px;width:278px;padding:14px 16px;border-radius:18px}.search-compression__number{font:400 45px/1 "Newsreader",serif;color:#e9ffff;margin:6px 0 3px}.search-compression__label{font:500 8px/1.35 "DM Mono",monospace;color:#9db0ba;min-height:22px}.search-compression__stages{display:grid;gap:5px;margin-top:10px}.search-compression__stage{display:grid;grid-template-columns:32px 1fr 46px;align-items:center;gap:7px;padding:5px 7px;border-radius:8px;color:#667d89;font:500 7px "DM Mono",monospace;transition:.2s}.search-compression__stage i{height:2px;background:rgba(255,255,255,.08);position:relative;overflow:hidden}.search-compression__stage i:after{content:"";position:absolute;inset:0;background:#57d7e8;transform:scaleX(0);transform-origin:left;transition:transform .22s}.search-compression__stage b{font-weight:500;text-align:right}.search-compression__stage.is-done,.search-compression__stage.is-current{color:#dffbff;background:rgba(87,215,232,.05)}.search-compression__stage.is-done i:after,.search-compression__stage.is-current i:after{transform:scaleX(1)}.search-compression__stage.is-current{outline:1px solid rgba(87,215,232,.28)}
    .search-compression__note{margin-top:9px;font:400 7px/1.4 "DM Mono",monospace;color:#637985;text-transform:uppercase;letter-spacing:.035em}
    .departure-strip{display:flex;align-items:center;gap:7px;margin-top:9px;padding-top:8px;border-top:1px solid rgba(255,255,255,.08)}.departure-strip span{font:500 8px "DM Mono",monospace;color:#758b96}.departure-strip b{position:relative;padding:4px 7px;border-radius:999px;font:500 8px "DM Mono",monospace;border:1px solid rgba(255,255,255,.12);color:#b8c7ce}.departure-strip b.cyan{border-color:rgba(87,215,232,.35);color:#8defff}.departure-strip b.orange{border-color:rgba(255,155,97,.35);color:#ffb07f}.departure-strip b.is-live{background:currentColor;box-shadow:0 0 20px currentColor;color:#07131f}
    .evidence-stack{position:fixed;z-index:22;right:30px;top:50%;transform:translateY(-50%);pointer-events:none;display:grid;gap:7px;opacity:0;transition:opacity .35s}.evidence-stack span{padding:7px 9px;border-left:2px solid rgba(255,255,255,.14);background:rgba(6,18,28,.48);backdrop-filter:blur(10px);font:500 7px/1.35 "DM Mono",monospace;color:#81949e}.evidence-stack b{display:block;font:400 18px "Newsreader",serif;color:#dffbff}.evidence-stack .human{border-color:#ff9b61;color:#c7a992}.evidence-stack .human b{color:#ffbd91}body[data-scene="end"] .evidence-stack{opacity:1}
    @media(max-width:800px){.representation-meter{left:14px;right:14px;bottom:12px;width:auto}.representation-meter__note{display:none}.search-compression{right:14px;top:82px;bottom:auto;width:224px}.search-compression__stage{grid-template-columns:24px 1fr 40px}.evidence-stack{display:none}}
    @media(prefers-reduced-motion:reduce){.representation-meter,.search-compression,.evidence-stack{transition:none}}
  `;
  document.head.appendChild(style);

  const representation = document.createElement('div');
  representation.className = 'representation-meter';
  representation.innerHTML = '<span class="representation-meter__kicker">una popolazione · tre rappresentazioni successive</span><div class="representation-meter__line"><i></i></div><div class="representation-meter__steps"><span data-stage="grid">01 · griglia<b>4.283 celle</b></span><span data-stage="sections">02 · sezioni<b>229 sezioni</b></span><span data-stage="buildings">03 · edifici<b>4.226 sagome</b></span></div><div class="representation-meter__note">Non è un tracciamento cella→edificio. Sono rappresentazioni successive dello stesso problema, con geometrie e vincoli diversi.</div>';
  document.body.appendChild(representation);

  const funnelStages = [
    ['01','campioni stradali con accesso pedonale',3858],
    ['02','seed su gap a 8 minuti',1686],
    ['03','seed prima del thinning',1074],
    ['04','candidate prima del pruning finale',292],
    ['05','candidate finali persistite',155]
  ];
  const search = document.createElement('div');
  search.className = 'search-compression';
  search.innerHTML = `<span class="search-compression__kicker">compressione dello spazio di ricerca</span><div class="search-compression__number">3.858</div><div class="search-compression__label">${funnelStages[0][1]}</div><div class="search-compression__stages">${funnelStages.map((s,i)=>`<div class="search-compression__stage${i===0?' is-current':''}" data-i="${i}"><span>${s[0]}</span><i></i><b>${s[2].toLocaleString('it-IT')}</b></div>`).join('')}</div><div class="search-compression__note">La mappa visualizza soltanto le 155 candidate persistite. Per gli stadi scartati mostriamo solo conteggi aggregati: nessuna coordinata viene inventata.</div>`;
  document.body.appendChild(search);

  const evidence = document.createElement('div');
  evidence.className = 'evidence-stack';
  evidence.innerHTML = '<span><b>5</b>comuni core</span><span><b>4.226</b>edifici popolati</span><span><b>4.348</b>unità di accessibilità</span><span><b>155</b>candidate persistite</span><span><b>4 → 2</b>lineage → assetti visibili</span><span class="human"><b>0</b>vincitori automatici</span>';
  document.body.appendChild(evidence);

  function install() {
    const map = window.__analysisJourneyMap;
    if (!map || !window.gsap || !window.ScrollTrigger || !map.getLayer('buildings-extrude')) return false;
    clearInterval(waiter);
    gsap.registerPlugin(ScrollTrigger);

    if (map.getSource('pieces') && !map.getLayer('dasymetric-sparks')) {
      map.addLayer({id:'dasymetric-sparks',type:'circle',source:'pieces',paint:{'circle-radius':1.2,'circle-color':'#dffbff','circle-opacity':0,'circle-blur':0.15}});
    }
    if (map.getSource('hub') && !map.getLayer('departure-cyan-a')) {
      ['departure-cyan-a','departure-cyan-b'].forEach(id=>map.addLayer({id,type:'circle',source:'hub',paint:{'circle-radius':6,'circle-color':'rgba(0,0,0,0)','circle-opacity':0,'circle-stroke-width':2,'circle-stroke-color':'#57d7e8','circle-stroke-opacity':0}}));
      map.addLayer({id:'departure-orange',type:'circle',source:'hub',paint:{'circle-radius':6,'circle-color':'rgba(0,0,0,0)','circle-opacity':0,'circle-stroke-width':2,'circle-stroke-color':'#ff9b61','circle-stroke-opacity':0}});
    }

    const repSteps = [...representation.querySelectorAll('[data-stage]')];
    const repLine = representation.querySelector('.representation-meter__line i');
    const repScenes = [
      ['grid',0],['sections',1],['buildings',2]
    ];
    repScenes.forEach(([scene,index]) => {
      const section = document.querySelector(`[data-scene="${scene}"]`);
      ScrollTrigger.create({
        trigger:section,start:'top 82%',end:'bottom 18%',scrub:true,
        onUpdate:self=>{
          if(document.body.dataset.scene!==scene) return;
          repSteps.forEach((el,i)=>el.classList.toggle('is-on',i<=index));
          repLine.style.width=`${((index+self.progress)/3)*100}%`;
          if(scene==='grid'){
            if(map.getLayer('worldpop-columns')) map.setPaintProperty('worldpop-columns','fill-extrusion-opacity',.45+.4*self.progress);
            map.setBearing(-25+15*self.progress); map.setPitch(60+7*self.progress);
          }
          if(scene==='sections'){
            if(map.getLayer('worldpop-columns')) map.setPaintProperty('worldpop-columns','fill-extrusion-opacity',Math.max(0,.25-.24*self.progress));
            if(map.getLayer('sections-fill')) map.setPaintProperty('sections-fill','fill-extrusion-opacity',.28+.48*self.progress);
            if(map.getLayer('sections-outline')) map.setPaintProperty('sections-outline','line-opacity',.2+.5*self.progress);
            map.setBearing(4+18*self.progress); map.setPitch(54+8*self.progress);
          }
          if(scene==='buildings'){
            if(map.getLayer('sections-fill')) map.setPaintProperty('sections-fill','fill-extrusion-opacity',Math.max(0,.16-.15*self.progress));
            if(map.getLayer('sections-outline')) map.setPaintProperty('sections-outline','line-opacity',Math.max(0,.16-.15*self.progress));
            if(map.getLayer('buildings-extrude')) map.setPaintProperty('buildings-extrude','fill-extrusion-opacity',.38+.57*self.progress);
            if(map.getLayer('buildings-outline')) map.setPaintProperty('buildings-outline','line-opacity',.08+.34*self.progress);
            if(map.getLayer('dasymetric-sparks')){
              const spark = Math.sin(Math.PI*Math.max(0,Math.min(1,(self.progress-.12)/.72)));
              map.setPaintProperty('dasymetric-sparks','circle-opacity',Math.max(0,spark*.42));
              map.setPaintProperty('dasymetric-sparks','circle-radius',.8+2.4*spark);
            }
            map.setBearing(-34+24*self.progress); map.setPitch(66+7*self.progress);
          }
        }
      });
    });

    const candidatesSection = document.querySelector('[data-scene="candidates"]');
    const stageEls = [...search.querySelectorAll('.search-compression__stage')];
    const bigNumber = search.querySelector('.search-compression__number');
    const stageLabel = search.querySelector('.search-compression__label');
    ScrollTrigger.create({
      trigger:candidatesSection,start:'top 80%',end:'bottom 20%',scrub:true,
      onUpdate:self=>{
        if(document.body.dataset.scene!=='candidates') return;
        const idx=Math.min(funnelStages.length-1,Math.floor(self.progress*funnelStages.length));
        const stage=funnelStages[idx];
        bigNumber.textContent=stage[2].toLocaleString('it-IT'); stageLabel.textContent=stage[1];
        stageEls.forEach((el,i)=>{el.classList.toggle('is-done',i<idx);el.classList.toggle('is-current',i===idx);});
        if(map.getLayer('candidates')){
          map.setPaintProperty('candidates','circle-opacity',.42+.5*self.progress);
          map.setPaintProperty('candidates','circle-stroke-width',.45+1.25*self.progress);
        }
        if(map.getLayer('candidate-halo')) map.setPaintProperty('candidate-halo','circle-opacity',.06+.18*Math.sin(Math.PI*self.progress));
        if(map.getLayer('hub-glow')) map.setPaintProperty('hub-glow','circle-radius',16+18*self.progress);
      }
    });

    const serviceClock = document.querySelector('.service-clock');
    if (serviceClock && !serviceClock.querySelector('.departure-strip')) {
      const strip=document.createElement('div'); strip.className='departure-strip';
      strip.innerHTML='<span>partenze:</span><b class="orange" data-minute="3">:03</b><b class="orange" data-minute="7">:07</b><b class="cyan" data-minute="39">:39 ×2</b>';
      serviceClock.appendChild(strip);
    }

    function burst(layer, delay=0){
      if(!map.getLayer(layer)) return;
      const o={p:0};
      gsap.to(o,{p:1,duration:.62,delay,ease:'power2.out',onUpdate:()=>{
        const p=o.p; map.setPaintProperty(layer,'circle-radius',8+58*p); map.setPaintProperty(layer,'circle-stroke-opacity',(1-p)*.9); map.setPaintProperty(layer,'circle-stroke-width',2.4-1.6*p);
      }});
    }
    let previousMinute=null;
    function watchClock(){
      const minuteEl=document.querySelector('.service-clock__minute b');
      const minute=minuteEl?Number(minuteEl.textContent):NaN;
      document.querySelectorAll('.departure-strip [data-minute]').forEach(el=>el.classList.toggle('is-live',Number(el.dataset.minute)===minute));
      if(document.body.dataset.scene==='time' && Number.isFinite(minute) && minute!==previousMinute){
        if(minute===39){burst('departure-cyan-a');burst('departure-cyan-b',.08);}
        if(minute===3 || minute===7) burst('departure-orange');
      }
      previousMinute=minute;
      requestAnimationFrame(watchClock);
    }
    requestAnimationFrame(watchClock);

    const endSection=document.querySelector('[data-scene="end"]');
    ScrollTrigger.create({
      trigger:endSection,start:'top 80%',end:'bottom 20%',scrub:true,
      onUpdate:self=>{
        if(document.body.dataset.scene!=='end') return;
        if(map.getLayer('buildings-extrude')) map.setPaintProperty('buildings-extrude','fill-extrusion-opacity',.06+.12*self.progress);
        if(map.getLayer('candidates')) map.setPaintProperty('candidates','circle-opacity',.02+.08*self.progress);
        if(map.getLayer('final16')) map.setPaintProperty('final16','line-opacity',.26+.22*self.progress);
        if(map.getLayer('final185')) map.setPaintProperty('final185','line-opacity',.26+.22*self.progress);
        if(map.getLayer('road-network')) map.setPaintProperty('road-network','line-opacity',.03+.07*self.progress);
        map.setBearing(-18+10*self.progress);
      }
    });
    return true;
  }

  const waiter=setInterval(install,120);
  setTimeout(()=>clearInterval(waiter),120000);
})();
