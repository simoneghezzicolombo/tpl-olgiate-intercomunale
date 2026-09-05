(() => {
  'use strict';

  const MUNICIPALITIES = {
    '097010': 'Brivio',
    '097012': 'Calco',
    '097058': 'Olgiate Molgora',
    '097074': 'Santa Maria Hoè',
    '097092': 'La Valletta Brianza',
  };
  const reduceMotion = window.__analysisJourneyReduceMotion === true;

  const style = document.createElement('style');
  style.textContent = `
    .depth-stack{position:fixed;z-index:22;right:58px;top:104px;width:194px;padding:13px 14px 14px;border-radius:17px;border:1px solid rgba(255,255,255,.13);background:rgba(5,17,27,.61);backdrop-filter:blur(18px);box-shadow:0 20px 60px rgba(0,0,0,.25);opacity:0;transform:translateY(8px);transition:opacity .28s,transform .28s;pointer-events:none}
    .depth-stack__kicker{font:500 7px "DM Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:#7f949f}.depth-stack__axis{position:relative;height:112px;margin-top:10px;border-left:1px solid rgba(255,255,255,.14);margin-left:8px}.depth-stack__axis:after{content:"z";position:absolute;left:-4px;top:-9px;font:500 7px "DM Mono",monospace;color:#5f7784}
    .depth-stack__layer{position:absolute;left:13px;right:0;display:grid;grid-template-columns:12px 1fr;align-items:center;gap:7px;font:500 7px/1.25 "DM Mono",monospace;color:#758b96;transition:color .2s,transform .2s}.depth-stack__layer i{height:2px;border-radius:8px;background:currentColor;box-shadow:0 0 13px currentColor}.depth-stack__layer b{display:block;font:400 14px "Newsreader",serif;color:#c5d4db}.depth-stack__layer[data-layer="grid"]{top:7px;color:#57d7e8}.depth-stack__layer[data-layer="sections"]{top:46px;color:#ffb07f}.depth-stack__layer[data-layer="buildings"]{top:84px;color:#55e1bf}.depth-stack__layer.is-active{color:#fff;transform:translateX(4px)}.depth-stack__layer.is-active i{box-shadow:0 0 18px currentColor}
    body[data-scene="grid"] .depth-stack,body[data-scene="sections"] .depth-stack,body[data-scene="buildings"] .depth-stack{opacity:1;transform:none}
    .analysis-lens{position:fixed;z-index:45;width:270px;left:0;top:0;padding:14px 15px 13px;border:1px solid rgba(255,255,255,.17);border-radius:17px;background:linear-gradient(145deg,rgba(5,17,27,.92),rgba(8,26,39,.82));backdrop-filter:blur(22px) saturate(1.12);box-shadow:0 24px 80px rgba(0,0,0,.38);opacity:0;transform:translateY(7px) scale(.985);transition:opacity .15s,transform .15s;pointer-events:none;color:#eafcff}.analysis-lens.is-visible{opacity:1;transform:none}.analysis-lens__kicker{font:500 7px "DM Mono",monospace;text-transform:uppercase;letter-spacing:.11em;color:#78dce8}.analysis-lens__title{font:400 23px/1.05 "Newsreader",serif;margin:7px 0 10px;color:#fff}.analysis-lens__metric{display:flex;align-items:baseline;gap:7px;padding:10px 0;border-top:1px solid rgba(255,255,255,.09);border-bottom:1px solid rgba(255,255,255,.09)}.analysis-lens__metric b{font:400 31px/1 "Newsreader",serif;color:#dffbff}.analysis-lens__metric span{font:500 7px/1.35 "DM Mono",monospace;text-transform:uppercase;color:#91a5af}.analysis-lens__rows{display:grid;gap:5px;margin-top:9px}.analysis-lens__row{display:flex;justify-content:space-between;gap:12px;font:500 7px/1.35 "DM Mono",monospace;color:#788e99}.analysis-lens__row b{font-weight:500;color:#c8d7de;text-align:right;max-width:155px;overflow:hidden;text-overflow:ellipsis}.analysis-lens__note{margin:9px 0 0;font:400 7px/1.4 "DM Mono",monospace;color:#617985}.analysis-lens__status{color:#ffbd91!important}
    @media(max-width:800px){.depth-stack{display:none}.analysis-lens{left:12px!important;right:12px!important;top:auto!important;bottom:12px;width:auto;transform:translateY(14px)}.analysis-lens.is-visible{transform:none}.analysis-lens__title{font-size:20px}.analysis-lens__metric b{font-size:27px}}
    @media(prefers-reduced-motion:reduce){.depth-stack,.depth-stack__layer,.analysis-lens{transition:none}}
  `;
  document.head.appendChild(style);

  const depth = document.createElement('div');
  depth.className = 'depth-stack';
  depth.setAttribute('aria-hidden', 'true');
  depth.innerHTML = '<span class="depth-stack__kicker">exploded evidence stack · quota visuale</span><div class="depth-stack__axis"><span class="depth-stack__layer" data-layer="grid"><i></i><span>WorldPop 100 m<b>4.283 celle</b></span></span><span class="depth-stack__layer" data-layer="sections"><i></i><span>Sezioni ISTAT<b>229 sezioni</b></span></span><span class="depth-stack__layer" data-layer="buildings"><i></i><span>DBGT edifici<b>4.226 sagome</b></span></span></div>';
  document.body.appendChild(depth);

  const lens = document.createElement('div');
  lens.className = 'analysis-lens';
  lens.setAttribute('role', 'status');
  lens.setAttribute('aria-live', 'polite');
  document.body.appendChild(lens);

  let map = null;
  let installed = false;

  function fmt(value, digits = 1) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString('it-IT', {maximumFractionDigits: digits}) : 'n.d.';
  }
  function muni(code) { return MUNICIPALITIES[String(code || '').padStart(6, '0')] || String(code || 'territorio core'); }
  function row(label, value, cls = '') { return `<div class="analysis-lens__row"><span>${label}</span><b class="${cls}">${value}</b></div>`; }

  function inspect(kind, props, point = {x: 24, y: 110}) {
    if (!props) return hide();
    let html = '';
    if (kind === 'building') {
      html = `<span class="analysis-lens__kicker">edificio DBGT · modello dasimetrico</span><div class="analysis-lens__title">${muni(props.muni)}</div><div class="analysis-lens__metric"><b>${fmt(props.pop, 1)}</b><span>residenti modellati<br>nell’edificio</span></div><div class="analysis-lens__rows">${row('building id', String(props.building_id || 'n.d.'))}${row('sezioni intercettate', fmt(props.pieces, 0))}</div><p class="analysis-lens__note">Stima spaziale modellata. Non è un dato anagrafico attribuito a un civico.</p>`;
    } else if (kind === 'piece') {
      const walk = Number(props.walk);
      html = `<span class="analysis-lens__kicker">unità edificio × sezione</span><div class="analysis-lens__title">${muni(props.muni)}</div><div class="analysis-lens__metric"><b>${Number.isFinite(walk) && walk < 90 ? fmt(walk, 1) : 'n.d.'}</b><span>minuti alla fermata<br>esistente più vicina</span></div><div class="analysis-lens__rows">${row('popolazione modellata', fmt(props.pop, 1))}${row('metrica', 'network walking time')}</div><p class="analysis-lens__note">Il tempo segue la rete pedonale del modello, non una distanza in linea d’aria.</p>`;
    } else if (kind === 'candidate') {
      html = `<span class="analysis-lens__kicker">candidate stop · Stop Universe V2</span><div class="analysis-lens__title">${String(props.id || 'candidata')}</div><div class="analysis-lens__metric"><b>${fmt(props.gain, 0)}</b><span>residenti aggiuntivi<br>entro 10 minuti</span></div><div class="analysis-lens__rows">${row('comune', muni(props.muni))}${row('classe stradale', String(props.highway || 'n.d.'))}${row('implementazione', 'FIELD_CHECK_PENDING', 'analysis-lens__status')}${props.uncertainty ? row('uncertainty flag', String(props.uncertainty)) : ''}</div><p class="analysis-lens__note">È una candidata di ricerca su rete bus-eligible, non una fermata già raccomandata o verificata sul campo.</p>`;
    } else return hide();
    lens.innerHTML = html;
    const mobile = innerWidth <= 800;
    if (!mobile) {
      const width = 270;
      const height = 230;
      const x = Math.max(12, Math.min(innerWidth - width - 12, Number(point.x || 24) + 18));
      const y = Math.max(86, Math.min(innerHeight - height - 12, Number(point.y || 110) + 18));
      lens.style.left = `${x}px`;
      lens.style.top = `${y}px`;
    }
    lens.classList.add('is-visible');
    return true;
  }
  function hide() {
    lens.classList.remove('is-visible');
    if (map) map.getCanvas().style.cursor = '';
    return true;
  }
  function setStackOpacity(worldpop, sections, buildings) {
    if (!map) return;
    [['worldpop-stack', worldpop], ['sections-stack', sections], ['buildings-stack', buildings]].forEach(([id, value]) => {
      if (map.getLayer(id)) map.setPaintProperty(id, 'fill-extrusion-opacity', value);
    });
  }
  function activeDepth(scene) {
    depth.querySelectorAll('[data-layer]').forEach(el => el.classList.toggle('is-active', el.dataset.layer === scene));
  }

  function addStackLayers() {
    if (!map.getLayer('worldpop-stack')) map.addLayer({
      id:'worldpop-stack', type:'fill-extrusion', source:'worldpop', paint:{
        'fill-extrusion-color':'#57d7e8', 'fill-extrusion-base':155,
        'fill-extrusion-height':['+',155,['interpolate',['linear'],['get','pop'],0,4,50,74]],
        'fill-extrusion-opacity':0, 'fill-extrusion-vertical-gradient':false
      }
    });
    if (!map.getLayer('sections-stack')) map.addLayer({
      id:'sections-stack', type:'fill-extrusion', source:'sections', paint:{
        'fill-extrusion-color':'#ff9b61', 'fill-extrusion-base':78,
        'fill-extrusion-height':['+',78,['interpolate',['linear'],['get','pop2025'],0,5,700,46]],
        'fill-extrusion-opacity':0, 'fill-extrusion-vertical-gradient':false
      }
    });
    if (!map.getLayer('buildings-stack')) map.addLayer({
      id:'buildings-stack', type:'fill-extrusion', source:'buildings', paint:{
        'fill-extrusion-color':'#55e1bf', 'fill-extrusion-base':8,
        'fill-extrusion-height':['+',8,['interpolate',['linear'],['get','pop'],0,2,2,5,8,12,22,22,60,42,180,68]],
        'fill-extrusion-opacity':0, 'fill-extrusion-vertical-gradient':false
      }
    });
  }

  function installInspectors() {
    const bind = (layer, kind, scenes) => {
      map.on('mousemove', layer, e => {
        if (!scenes.includes(document.body.dataset.scene) || !e.features?.length) return;
        map.getCanvas().style.cursor = 'crosshair';
        inspect(kind, e.features[0].properties, e.point);
      });
      map.on('mouseleave', layer, hide);
      map.on('click', layer, e => {
        if (!scenes.includes(document.body.dataset.scene) || !e.features?.length) return;
        inspect(kind, e.features[0].properties, e.point);
      });
    };
    bind('buildings-extrude', 'building', ['buildings']);
    bind('piece-halo', 'piece', ['walk']);
    bind('candidates', 'candidate', ['candidates']);
    map.on('click', e => {
      if (!['buildings','walk','candidates'].includes(document.body.dataset.scene)) hide();
    });
  }

  function installStackDirector() {
    if (reduceMotion || !window.gsap || !window.ScrollTrigger) return;
    gsap.registerPlugin(ScrollTrigger);
    const sections = document.querySelector('[data-scene="sections"]');
    const buildings = document.querySelector('[data-scene="buildings"]');
    ScrollTrigger.create({
      trigger:sections, start:'top 78%', end:'bottom 22%', scrub:true,
      onUpdate:self => {
        if (document.body.dataset.scene !== 'sections') return;
        const p = Math.sin(Math.PI * self.progress);
        setStackOpacity(.26*p, .46*p, .13*p);
      }
    });
    ScrollTrigger.create({
      trigger:buildings, start:'top 82%', end:'55% 45%', scrub:true,
      onUpdate:self => {
        if (document.body.dataset.scene !== 'buildings') return;
        const p = Math.max(0, 1 - self.progress);
        setStackOpacity(.18*p, .32*p, .24*p);
      }
    });
  }

  function install() {
    map = window.__analysisJourneyMap;
    if (!map || !map.getLayer('buildings-extrude') || !map.getSource('worldpop') || !map.getSource('sections') || !map.getSource('buildings')) return false;
    if (installed) return true;
    installed = true;
    addStackLayers();
    installInspectors();
    installStackDirector();
    if (reduceMotion) setStackOpacity(0,0,0);

    const observer = new MutationObserver(() => {
      const scene = document.body.dataset.scene;
      activeDepth(scene);
      if (!['sections','buildings'].includes(scene)) setStackOpacity(0,0,0);
      if (!['buildings','walk','candidates'].includes(scene)) hide();
    });
    observer.observe(document.body, {attributes:true, attributeFilter:['data-scene']});
    activeDepth(document.body.dataset.scene);

    window.__analysisJourneyLens = {
      inspect,
      hide,
      stackLayers:['worldpop-stack','sections-stack','buildings-stack'],
      reducedMotion: reduceMotion,
      installed: true,
    };
    return true;
  }

  let attempts = 0;
  const waiter = setInterval(() => {
    attempts += 1;
    if (install() || attempts >= 600) clearInterval(waiter);
  }, 200);
})();
