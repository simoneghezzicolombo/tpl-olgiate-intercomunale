(() => {
  'use strict';

  const mapEl = document.getElementById('map');
  if (mapEl) {
    mapEl.removeAttribute('aria-hidden');
    mapEl.setAttribute('aria-label', 'Mappa interattiva della rete attuale e delle alternative finaliste');
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
        <p>Muoviti, fai zoom e clicca sulle linee e sulle fermate. Puoi confrontare la rete attuale con le quattro lineage finaliste e distinguere le fermate esistenti da quelle nuove ancora da verificare sul posto.</p>
        <div class="explore-key" aria-label="Legenda mappa esplorabile">
          <span><i class="explore-key__line explore-key__line--current"></i>rete attuale</span>
          <span><i class="explore-key__line explore-key__line--final"></i>linee finaliste</span>
          <span><i class="explore-key__dot explore-key__dot--new"></i>nuova fermata</span>
          <span><i class="explore-key__dot explore-key__dot--existing"></i>fermata esistente</span>
        </div>
        <p class="source-note">Geometrie certificate · GTFS ufficiale + Gate D + Reduced Path Matrix V2</p>
      </div>`;
    main.appendChild(section);
  }

  const style = document.createElement('style');
  style.dataset.journeyExplore = 'prelude';
  style.textContent = `
    .explore-chapter{min-height:135vh;align-items:flex-start;padding-top:16vh;padding-bottom:24vh}
    .copy--explore{width:min(470px,38vw);background:linear-gradient(145deg,rgba(6,18,28,.86),rgba(6,18,28,.50));box-shadow:0 28px 90px rgba(0,0,0,.34)}
    .explore-key{display:grid;grid-template-columns:1fr 1fr;gap:9px 14px;margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,.12)}
    .explore-key span{display:flex;align-items:center;gap:8px;font:500 9px var(--mono);text-transform:uppercase;letter-spacing:.04em;color:#aebbc4}
    .explore-key__line{width:24px;height:3px;border-radius:999px;background:#fff;box-shadow:0 0 10px rgba(255,255,255,.15)}
    .explore-key__line--current{background:linear-gradient(90deg,#4ca5ff 0 48%,#ff9b61 52% 100%)}
    .explore-key__line--final{background:linear-gradient(90deg,#57d7e8,#55e1bf,#ff9b61,#f6d36f)}
    .explore-key__dot{width:9px;height:9px;border-radius:50%;background:#fff;border:1px solid #07131f;box-shadow:0 0 0 2px rgba(255,255,255,.10)}
    .explore-key__dot--new{background:#ffd36d}.explore-key__dot--existing{background:#fff}
    body[data-scene="explore"] .vignette{background:radial-gradient(circle at 55% 48%,transparent 28%,rgba(2,9,16,.08) 66%,rgba(2,8,14,.42) 100%),linear-gradient(90deg,rgba(4,12,19,.45) 0%,rgba(4,12,19,.08) 38%,transparent 62%,rgba(4,12,19,.08) 100%)}
    body[data-scene="explore"] .grain{opacity:.035}
    body[data-scene="explore"] .maplibregl-canvas{cursor:grab}
    body[data-scene="explore"] .maplibregl-canvas:active{cursor:grabbing}
    .explore-controls{position:fixed;z-index:29;right:34px;bottom:34px;width:min(390px,calc(100vw - 28px));padding:13px;border-radius:18px;border:1px solid rgba(255,255,255,.15);background:rgba(6,18,28,.84);backdrop-filter:blur(20px) saturate(1.1);box-shadow:0 18px 55px rgba(0,0,0,.30);opacity:0;pointer-events:none;transform:translateY(8px);transition:.25s}
    body[data-scene="explore"] .explore-controls{opacity:1;pointer-events:auto;transform:none}
    .explore-controls__head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
    .explore-controls__head strong{font:600 11px var(--sans);color:#e9fbff}.explore-controls__head small{display:block;margin-top:2px;font:400 9px/1.35 var(--mono);color:#8ea1ae}
    .explore-controls__layers{display:flex;flex-wrap:wrap;gap:6px}
    .explore-controls button{appearance:none;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.04);color:#dff7ff;border-radius:999px;padding:8px 10px;font:600 10px var(--sans);cursor:pointer;transition:.2s}
    .explore-controls button:hover{border-color:rgba(255,255,255,.35)}.explore-controls button.is-active{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.42)}
    .explore-controls button i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px;background:var(--c,#fff)}
    .explore-controls__hint{margin-top:10px;font:400 9px/1.45 var(--mono);color:#8fa2ae}
    .maplibregl-popup{z-index:42}.maplibregl-popup-content{min-width:220px;max-width:310px;padding:14px 15px!important;border-radius:16px!important;border:1px solid rgba(255,255,255,.16);background:rgba(5,16,25,.94)!important;color:#eaf5f8;box-shadow:0 18px 55px rgba(0,0,0,.45);backdrop-filter:blur(18px);font-family:var(--sans)}
    .maplibregl-popup-tip{border-top-color:rgba(5,16,25,.94)!important;border-bottom-color:rgba(5,16,25,.94)!important}
    .maplibregl-popup-close-button{color:#9dafb9;font-size:18px;padding:4px 8px}.maplibregl-popup-close-button:hover{background:transparent;color:#fff}
    .map-card__eyebrow{font:500 9px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:#57d7e8;margin:0 22px 6px 0}.map-card__title{font:500 17px/1.15 var(--serif);margin:0 18px 9px 0;color:#fff}.map-card__body{font:400 10px/1.5 var(--sans);color:#b6c5cd;margin:0}.map-card__meta{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:10px}.map-card__meta span{padding:7px 8px;border:1px solid rgba(255,255,255,.10);border-radius:9px;background:rgba(255,255,255,.035);font:500 9px/1.25 var(--mono);color:#b8c7cf}.map-card__code{margin-top:9px;font:400 8px/1.35 var(--mono);color:#718692;word-break:break-word}
    @media(max-width:800px){.explore-chapter{min-height:145vh;padding-top:18vh}.copy--explore{width:100%;margin:0}.explore-key{grid-template-columns:1fr 1fr}.explore-controls{right:14px;bottom:14px;width:min(360px,calc(100vw - 28px));padding:11px}.explore-controls__head small,.explore-controls__hint{display:none}.explore-controls button{padding:7px 9px}.maplibregl-popup-content{max-width:260px}}
  `;
  document.head.appendChild(style);
})();
