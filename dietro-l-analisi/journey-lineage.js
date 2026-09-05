(() => {
  'use strict';

  const reduceMotion = window.__analysisJourneyReduceMotion === true;
  const style = document.createElement('style');
  style.textContent = `
    .lineage-visual-note{display:block;margin-top:7px;padding-top:7px;border-top:1px solid rgba(255,255,255,.08);font:400 7px/1.4 "DM Mono",monospace;color:#617985;text-transform:uppercase;letter-spacing:.035em}
    .lineage-visual-note b{font-weight:500;color:#d7eaf0}
    @media(max-width:800px){.lineage-visual-note{display:none}}
  `;
  document.head.appendChild(style);

  let map = null;
  let installed = false;
  const IDS = ['lineage-16-fig','lineage-16-two','lineage-185-fig','lineage-185-two'];

  function paint(id, prop, value) {
    if (map?.getLayer(id)) map.setPaintProperty(id, prop, value);
  }

  function addLayers() {
    const specs = [
      ['lineage-16-fig','final16','#57d7e8',-10],
      ['lineage-16-two','final16','#c8f8ff',10],
      ['lineage-185-fig','final185','#ff9b61',-10],
      ['lineage-185-two','final185','#ffd0ad',10],
    ];
    specs.forEach(([id, source, color, offset]) => {
      if (map.getLayer(id)) return;
      map.addLayer({
        id, type:'line', source,
        paint:{
          'line-color':color,
          'line-width':2.7,
          'line-opacity':0,
          'line-offset':offset,
          'line-blur':.2,
        }
      });
    });
  }

  function apply(progress) {
    if (!map) return;
    const p = Math.max(0, Math.min(1, Number(progress) || 0));
    const separation = 10 * (1 - p);
    const opacity = .9 - .34 * p;
    paint('lineage-16-fig','line-offset',-separation);
    paint('lineage-16-two','line-offset',separation);
    paint('lineage-185-fig','line-offset',-separation);
    paint('lineage-185-two','line-offset',separation);
    IDS.forEach(id => paint(id,'line-opacity',opacity));
    document.body.dataset.lineageCollapse = p > .82 ? 'merged' : p > .35 ? 'converging' : 'separated';
  }

  function hide() {
    IDS.forEach(id => paint(id,'line-opacity',0));
    delete document.body.dataset.lineageCollapse;
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
      onEnter:() => apply(0),
      onEnterBack:() => apply(1),
      onLeave:hide,
      onLeaveBack:hide,
      onUpdate:self => {
        if (document.body.dataset.scene !== 'finalists') return;
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
      else if (reduceMotion) {
        // Static separated state preserves the explanatory comparison without
        // scroll-driven convergence for users requesting reduced motion.
        apply(.55);
      }
    });
    observer.observe(document.body,{attributes:true,attributeFilter:['data-scene']});
    if (reduceMotion && document.body.dataset.scene === 'finalists') apply(.55);

    window.__analysisJourneyLineage = {
      installed:true,
      reducedMotion:reduceMotion,
      layers:[...IDS],
      apply,
      hide,
    };
    return true;
  }

  let attempts=0;
  const waiter=setInterval(()=>{
    attempts += 1;
    if (install() || attempts >= 600) clearInterval(waiter);
  },200);
})();
