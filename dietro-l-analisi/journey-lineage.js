(() => {
  'use strict';

  const reduceMotion = window.__analysisJourneyReduceMotion === true;
  const style = document.createElement('style');
  style.textContent = `
    .lineage-visual-note{display:block;margin-top:7px;padding-top:7px;border-top:1px solid rgba(255,255,255,.08);font:400 7px/1.4 "DM Mono",monospace;color:#617985;text-transform:uppercase;letter-spacing:.035em}
    .lineage-visual-note b{font-weight:500;color:#d7eaf0}
    .chapter[data-scene="finalists"] .copy--wide{width:min(650px,48vw);padding:24px 26px}
    .chapter[data-scene="finalists"] .copy--wide h2{font-size:clamp(38px,3.55vw,62px)}
    .chapter[data-scene="finalists"] .finalist-grid{gap:8px;margin:20px 0 15px}
    .chapter[data-scene="finalists"] .finalist-grid article{padding:13px 12px}
    .chapter[data-scene="finalists"] .insight{font-size:16px!important;line-height:1.25}
    @media(max-width:800px){.lineage-visual-note{display:none}.chapter[data-scene="finalists"] .copy--wide{width:100%;padding:21px 20px}.chapter[data-scene="finalists"] .copy--wide h2{font-size:clamp(38px,11vw,56px)}}
  `;
  document.head.appendChild(style);

  let map = null;
  let installed = false;
  let focused = false;
  const IDS = ['lineage-16-fig','lineage-16-two','lineage-185-fig','lineage-185-two'];

  function paint(id, prop, value) {
    if (map?.getLayer(id)) map.setPaintProperty(id, prop, value);
  }

  function addLayers() {
    const specs = [
      ['lineage-16-fig','final16','#34e7ff',-12],
      ['lineage-16-two','final16','#e2fbff',12],
      ['lineage-185-fig','final185','#ff8548',-12],
      ['lineage-185-two','final185','#ffe0c5',12],
    ];
    specs.forEach(([id, source, color, offset]) => {
      if (map.getLayer(id)) return;
      map.addLayer({
        id, type:'line', source,
        paint:{
          'line-color':color,
          'line-width':4.1,
          'line-opacity':0,
          'line-offset':offset,
          'line-blur':.25,
        }
      });
    });
  }

  function focusFinalists() {
    if (!map || focused || innerWidth <= 800) return;
    focused = true;
    map.easeTo({
      center:[9.397,45.733],
      zoom:11.55,
      pitch:59,
      bearing:8,
      offset:[315,18],
      duration:reduceMotion ? 0 : 900,
      essential:!reduceMotion,
    });
  }

  function apply(progress) {
    if (!map) return;
    const p = Math.max(0, Math.min(1, Number(progress) || 0));
    const separation = 12 * (1 - p);
    const echoOpacity = .96 - .46 * p;
    paint('lineage-16-fig','line-offset',-separation);
    paint('lineage-16-two','line-offset',separation);
    paint('lineage-185-fig','line-offset',-separation);
    paint('lineage-185-two','line-offset',separation);
    IDS.forEach(id => paint(id,'line-opacity',echoOpacity));

    // During the explanatory separation, dim the two real public-route layers.
    // As the lineage collapse, restore them so the visual ends on the actual
    // two service geometries rather than on four decorative echoes.
    paint('final16','line-opacity',.16 + .70*p);
    paint('final185','line-opacity',.14 + .64*p);
    paint('final16-glow','line-opacity',.07 + .21*p);
    paint('final185-glow','line-opacity',.06 + .17*p);
    document.body.dataset.lineageCollapse = p > .82 ? 'merged' : p > .35 ? 'converging' : 'separated';
  }

  function hide() {
    IDS.forEach(id => paint(id,'line-opacity',0));
    delete document.body.dataset.lineageCollapse;
    focused = false;
  }

  function installCaption() {
    const caption = document.querySelector('.lineage-collapse__caption');
    if (!caption || caption.querySelector('.lineage-visual-note')) return;
    const note = document.createElement('span');
    note.className = 'lineage-visual-note';
    note.innerHTML = '<b>Offset solo grafico:</b> separa temporaneamente linee coincidenti per rendere visibili le quattro lineage. A fine scroll tornano sulla stessa geometria.';
    caption.appendChild(note);
  }

  function installDirector() {
    const section = document.querySelector('[data-scene="finalists"]');
    if (!section) return;
    if (reduceMotion || !window.gsap || !window.ScrollTrigger) return;
    gsap.registerPlugin(ScrollTrigger);
    ScrollTrigger.create({
      trigger:section, start:'top 78%', end:'bottom 22%', scrub:true,
      onEnter:() => { focusFinalists(); apply(0); },
      onEnterBack:() => { focusFinalists(); apply(1); },
      onLeave:hide,
      onLeaveBack:hide,
      onUpdate:self => {
        if (document.body.dataset.scene !== 'finalists') return;
        focusFinalists();
        const p = Math.max(0, Math.min(1, (self.progress - .08) / .84));
        apply(p);
      }
    });
  }

  function install() {
    map = window.__analysisJourneyMap;
    if (!map || !map.getSource('final16') || !map.getSource('final185') || !map.getLayer('final16') || !map.getLayer('final185')) return false;
    if (installed) return true;
    installed = true;
    addLayers();
    installCaption();
    installDirector();

    const observer = new MutationObserver(() => {
      const scene = document.body.dataset.scene;
      if (scene !== 'finalists') hide();
      else {
        focusFinalists();
        if (reduceMotion) {
          // Static separated state preserves the explanatory comparison without
          // scroll-driven convergence for users requesting reduced motion.
          apply(.55);
        }
      }
    });
    observer.observe(document.body,{attributes:true,attributeFilter:['data-scene']});
    if (document.body.dataset.scene === 'finalists') {
      focusFinalists();
      if (reduceMotion) apply(.55);
    }

    window.__analysisJourneyLineage = {
      installed:true,
      reducedMotion:reduceMotion,
      layers:[...IDS],
      apply,
      hide,
      focus:focusFinalists,
    };
    return true;
  }

  let attempts=0;
  const waiter=setInterval(()=>{
    attempts += 1;
    if (install() || attempts >= 600) clearInterval(waiter);
  },200);
})();
