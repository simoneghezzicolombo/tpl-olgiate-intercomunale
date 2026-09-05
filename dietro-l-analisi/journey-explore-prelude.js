(() => {
  'use strict';

  const mapEl = document.getElementById('map');
  if (mapEl) {
    mapEl.removeAttribute('aria-hidden');
    mapEl.setAttribute('aria-label', 'Mappa interattiva dei dati territoriali, della rete attuale e delle alternative finaliste');
  }

  const main = document.querySelector('main');
  if (main && !document.querySelector('[data-scene="explore"]')) {
    const section = document.createElement('section');
    section.id = 'esplora-mappa';
    section.className = 'chapter explore-chapter';
    section.dataset.scene = 'explore';
    section.dataset.label = 'Esplora';
    section.innerHTML = `
      <div class="copy copy--explore">
        <p class="eyebrow">12 · La mappa resta aperta</p>
        <h2>Adesso puoi <em>esplorarla davvero.</em></h2>
        <p>Qui ritrovi tutto quello che hai visto nello scroll: popolazione, sezioni, edifici, accessibilità pedonale, grafo stradale, candidate, rete attuale e quattro lineage finaliste. Entra nella modalità libera, accendi i layer che vuoi e clicca direttamente sugli oggetti.</p>
        <div class="explore-key" aria-label="Legenda mappa esplorabile">
          <span><i class="explore-key__dot explore-key__dot--population"></i>territorio</span>
          <span><i class="explore-key__dot explore-key__dot--walk"></i>accessibilità</span>
          <span><i class="explore-key__line explore-key__line--current"></i>rete attuale</span>
          <span><i class="explore-key__line explore-key__line--final"></i>linee finaliste</span>
          <span><i class="explore-key__dot explore-key__dot--candidate"></i>candidate</span>
          <span><i class="explore-key__dot explore-key__dot--existing"></i>fermate</span>
        </div>
        <button class="explore-enter" type="button" data-explore-enter>
          <span>Esplora la mappa</span><b>→</b>
        </button>
        <p class="source-note">KML ufficiali D184/D185 + GTFS fermate + WorldPop/ISTAT/DBGT + Gate D + Reduced Path Matrix V2</p>
      </div>`;
    main.appendChild(section);
  }

  const style = document.createElement('style');
  style.dataset.journeyExplore = 'prelude';
  style.textContent = `
    .explore-chapter{min-height:135vh;align-items:flex-start;padding-top:16vh;padding-bottom:24vh}
    .copy--explore{width:min(500px,40vw);background:linear-gradient(145deg,rgba(6,18,28,.89),rgba(6,18,28,.56));box-shadow:0 28px 90px rgba(0,0,0,.34);transition:opacity .32s,transform .32s,visibility .32s}
    .explore-key{display:grid;grid-template-columns:1fr 1fr;gap:9px 14px;margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,.12)}
    .explore-key span{display:flex;align-items:center;gap:8px;font:500 9px var(--mono);text-transform:uppercase;letter-spacing:.04em;color:#aebbc4}
    .explore-key__line{width:24px;height:3px;border-radius:999px;background:#fff;box-shadow:0 0 10px rgba(255,255,255,.15)}
    .explore-key__line--current{background:linear-gradient(90deg,#4ca5ff 0 48%,#ff9b61 52% 100%)}
    .explore-key__line--final{background:linear-gradient(90deg,#57d7e8,#55e1bf,#ff9b61,#f6d36f)}
    .explore-key__dot{width:9px;height:9px;border-radius:50%;background:#fff;border:1px solid #07131f;box-shadow:0 0 0 2px rgba(255,255,255,.10)}
    .explore-key__dot--population{background:#57d7e8}.explore-key__dot--walk{background:#55e1bf}.explore-key__dot--candidate{background:#ffd36d}.explore-key__dot--existing{background:#fff}
    .explore-enter{margin-top:20px;width:100%;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:14px 17px;border:1px solid rgba(87,215,232,.42);border-radius:14px;background:linear-gradient(110deg,rgba(87,215,232,.17),rgba(85,225,191,.08));color:#eaffff;font:650 12px var(--sans);cursor:pointer;transition:.2s}
    .explore-enter:hover{transform:translateY(-1px);border-color:rgba(87,215,232,.75);background:linear-gradient(110deg,rgba(87,215,232,.25),rgba(85,225,191,.13))}.explore-enter b{font:400 20px var(--serif);color:#57d7e8}
    body[data-scene="explore"] .vignette{background:radial-gradient(circle at 55% 48%,transparent 28%,rgba(2,9,16,.08) 66%,rgba(2,8,14,.42) 100%),linear-gradient(90deg,rgba(4,12,19,.45) 0%,rgba(4,12,19,.08) 38%,transparent 62%,rgba(4,12,19,.08) 100%)}
    body[data-scene="explore"] .grain{opacity:.035}
    body[data-scene="explore"] .maplibregl-canvas{cursor:default}
    html.is-map-exploring,html.is-map-exploring body{overflow:hidden!important;overscroll-behavior:none}
    body.is-map-exploring main{pointer-events:none}
    body.is-map-exploring #map{pointer-events:auto}
    body.is-map-exploring .copy--explore{opacity:0!important;visibility:hidden;transform:translateY(16px) scale(.985)!important;pointer-events:none!important}
    body.is-map-exploring .vignette{background:radial-gradient(circle at 50% 48%,transparent 38%,rgba(2,8,14,.20) 100%)}
    body.is-map-exploring .maplibregl-canvas{cursor:grab}
    body.is-map-exploring .maplibregl-canvas:active{cursor:grabbing}
    .explore-controls{position:fixed;z-index:29;right:34px;bottom:34px;width:min(430px,calc(100vw - 28px));max-height:min(72vh,680px);overflow:auto;padding:14px;border-radius:19px;border:1px solid rgba(255,255,255,.15);background:rgba(6,18,28,.90);backdrop-filter:blur(22px) saturate(1.12);box-shadow:0 18px 60px rgba(0,0,0,.36);opacity:0;pointer-events:none;transform:translateY(10px);transition:.25s}
    body.is-map-exploring .explore-controls{opacity:1;pointer-events:auto;transform:none}
    .explore-controls__head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:11px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.09)}
    .explore-controls__head strong{font:650 12px var(--sans);color:#e9fbff}.explore-controls__head small{display:block;margin-top:3px;font:400 8px/1.35 var(--mono);color:#8ea1ae}
    .explore-controls__exit{appearance:none;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.04);color:#dff7ff;border-radius:10px;padding:7px 9px;font:600 9px var(--sans);cursor:pointer;white-space:nowrap}.explore-controls__exit:hover{border-color:rgba(255,255,255,.35);background:rgba(255,255,255,.08)}
    .explore-controls__group{margin-top:10px}.explore-controls__group:first-of-type{margin-top:0}.explore-controls__group>span{display:block;margin:0 0 6px 2px;font:500 7px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:#718895}
    .explore-controls__layers{display:flex;flex-wrap:wrap;gap:6px}
    .explore-controls button[data-layer],.explore-controls button[data-action]{appearance:none;border:1px solid rgba(255,255,255,.13);background:rgba(255,255,255,.035);color:#dff7ff;border-radius:999px;padding:8px 10px;font:600 9px var(--sans);cursor:pointer;transition:.18s}
    .explore-controls button[data-layer]:hover,.explore-controls button[data-action]:hover{border-color:rgba(255,255,255,.32)}.explore-controls button[data-layer].is-active{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.38)}
    .explore-controls button i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px;background:var(--c,#fff)}
    .explore-controls__footer{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:11px;padding-top:10px;border-top:1px solid rgba(255,255,255,.09)}
    .explore-controls__hint{font:400 8px/1.4 var(--mono);color:#879aa6;max-width:250px}
    .maplibregl-popup{z-index:42}.maplibregl-popup-content{min-width:220px;max-width:315px;padding:14px 15px!important;border-radius:16px!important;border:1px solid rgba(255,255,255,.16);background:rgba(5,16,25,.95)!important;color:#eaf5f8;box-shadow:0 18px 55px rgba(0,0,0,.45);backdrop-filter:blur(18px);font-family:var(--sans)}
    .maplibregl-popup-tip{border-top-color:rgba(5,16,25,.95)!important;border-bottom-color:rgba(5,16,25,.95)!important}
    .maplibregl-popup-close-button{color:#9dafb9;font-size:18px;padding:4px 8px}.maplibregl-popup-close-button:hover{background:transparent;color:#fff}
    .map-card__eyebrow{font:500 9px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:#57d7e8;margin:0 22px 6px 0}.map-card__title{font:500 17px/1.15 var(--serif);margin:0 18px 9px 0;color:#fff}.map-card__body{font:400 10px/1.5 var(--sans);color:#b6c5cd;margin:0}.map-card__meta{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:10px}.map-card__meta span{padding:7px 8px;border:1px solid rgba(255,255,255,.10);border-radius:9px;background:rgba(255,255,255,.035);font:500 9px/1.25 var(--mono);color:#b8c7cf}.map-card__code{margin-top:9px;font:400 8px/1.35 var(--mono);color:#718692;word-break:break-word}
    @media(max-width:800px){.explore-chapter{min-height:145vh;padding-top:18vh}.copy--explore{width:100%;margin:0}.explore-key{grid-template-columns:1fr 1fr}.explore-controls{right:10px;left:10px;bottom:10px;width:auto;max-height:48vh;padding:11px}.explore-controls__head small,.explore-controls__hint{display:none}.explore-controls button[data-layer],.explore-controls button[data-action]{padding:7px 9px;font-size:8px}.maplibregl-popup-content{max-width:260px}.explore-controls__footer{justify-content:flex-end}}
    @media(prefers-reduced-motion:reduce){.copy--explore,.explore-controls,.explore-enter{transition:none}}
  `;
  document.head.appendChild(style);
})();
