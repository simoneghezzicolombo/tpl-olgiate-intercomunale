(() => {
  'use strict';

  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
  window.__analysisJourneyReduceMotion = reduceMotion;
  document.documentElement.dataset.journeyMotion = reduceMotion ? 'reduced' : 'full';

  // Keep the analytical world intact while making the mobile HUDs behave like
  // editorial captions rather than desktop panels squeezed into 390 px.
  const style = document.createElement('style');
  style.textContent = `
    @media (max-width:800px){
      body .search-compression{top:76px!important;right:12px!important;bottom:auto!important;width:178px!important;padding:9px 10px!important;border-radius:13px!important;background:rgba(6,18,28,.78)!important}
      body .search-compression__kicker{font-size:6px!important;letter-spacing:.09em!important}
      body .search-compression__number{font-size:29px!important;margin:3px 0 1px!important}
      body .search-compression__label{font-size:6px!important;line-height:1.25!important;min-height:0!important}
      body .search-compression__stages,body .search-compression__note{display:none!important}

      body .service-clock{left:12px!important;right:12px!important;bottom:10px!important;transform:translateY(12px)!important;width:auto!important;padding:8px 10px!important;border-radius:13px!important}
      body[data-scene="time"] .service-clock{transform:none!important}
      body .service-clock__kicker{font-size:6px!important}
      body .service-clock__row{gap:9px!important;margin-top:3px!important}
      body .service-clock__minute{font-size:27px!important;min-width:52px!important}
      body .service-clock__minute span{font-size:13px!important}
      body .service-clock__legend{display:none!important}
      body .service-clock__note{display:none!important}
      body .departure-strip{margin-top:4px!important;padding-top:5px!important;gap:5px!important}
      body .departure-strip span,body .departure-strip b{font-size:6px!important}
      body .departure-strip b{padding:3px 5px!important}

      body .walk-clock{top:76px!important;right:12px!important;width:124px!important;padding:9px 10px!important;border-radius:13px!important}
      body .walk-clock__kicker{font-size:6px!important}
      body .walk-clock__value b{font-size:29px!important}
      body .walk-clock small{display:none!important}
      body .walk-clock__track{margin-top:6px!important}

      body .representation-meter{left:12px!important;right:12px!important;bottom:9px!important;width:auto!important;padding:9px 10px!important;border-radius:13px!important}
      body .representation-meter__kicker{font-size:6px!important}
      body .representation-meter__line{margin:6px 0!important}
      body .representation-meter__steps{gap:4px!important}
      body .representation-meter__steps span{padding:5px 6px!important;font-size:6px!important}
      body .representation-meter__steps span b{font-size:12px!important;margin-top:1px!important}
      body .representation-meter__note{display:none!important}
    }
    @media (prefers-reduced-motion:reduce){
      *,*::before,*::after{scroll-behavior:auto!important;animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}
      .maplibregl-canvas{filter:saturate(.65) contrast(1.02)!important}
    }
  `;
  document.head.appendChild(style);

  if (!reduceMotion) return;

  // The main controller asks MapLibre for 1050 ms camera eases and marks them
  // essential. Respect the user's OS-level preference without changing the
  // analytical camera targets: same center/zoom/pitch/bearing, instant change.
  const maplibre = window.maplibregl;
  if (!maplibre?.Map) return;
  const CapturedMap = maplibre.Map;
  maplibre.Map = new Proxy(CapturedMap, {
    construct(Target, args) {
      const instance = Reflect.construct(Target, args, Target);
      const nativeEaseTo = instance.easeTo.bind(instance);
      instance.easeTo = (options = {}, eventData) => nativeEaseTo(
        {...options, duration:0, essential:false, animate:false},
        eventData,
      );
      return instance;
    }
  });
})();
