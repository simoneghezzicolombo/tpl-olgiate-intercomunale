(() => {
  'use strict';
  const maplibre=window.maplibregl;
  if(!maplibre||!maplibre.Map) return;

  const CapturedMap=maplibre.Map;
  maplibre.Map=new Proxy(CapturedMap,{
    construct(Target,args){
      const options=args[0]||{};
      const style=options.style;
      if(style?.sources?.carto){
        style.sources.carto.tiles=['https://tile.openstreetmap.org/{z}/{x}/{y}.png'];
        style.sources.carto.attribution='© OpenStreetMap contributors';
        style.sources.carto.maxzoom=19;
      }
      const raster=style?.layers?.find(x=>x.id==='carto');
      if(raster?.paint){
        raster.paint['raster-saturation']=-1;
        raster.paint['raster-contrast']=.18;
        raster.paint['raster-brightness-min']=0;
        raster.paint['raster-brightness-max']=.24;
        raster.paint['raster-opacity']=.24;
      }
      const map=Reflect.construct(Target,args);
      map.scrollZoom?.disable();map.dragPan?.disable();map.dragRotate?.disable();map.touchZoomRotate?.disable();map.doubleClickZoom?.disable();map.boxZoom?.disable();map.keyboard?.disable();
      const canvas=map.getCanvas?.();if(canvas)canvas.style.touchAction='pan-y';
      return map;
    }
  });

  const css=document.createElement('style');css.textContent='.maplibregl-canvas{touch-action:pan-y!important}.vignette{background:linear-gradient(90deg,rgba(3,10,17,.42) 0%,rgba(3,10,17,.12) 35%,transparent 62%,rgba(3,10,17,.08) 100%)!important}.hub-marker{filter:none!important}.hub-marker span{display:none!important}.service-clock,.lineage-collapse{display:none!important}';document.head.appendChild(css);

  function paint(map,id,prop,value){
    if(!map?.getLayer(id)) return;
    try{map.setPaintProperty(id,prop,value);}catch(_){ }
  }
  function hygiene(){
    const map=window.__analysisJourneyMap;
    if(!map) return;
    const scene=document.body.dataset.scene||'intro';
    paint(map,'piece-halo','circle-stroke-opacity',scene==='walk'?.72:0);
    paint(map,'existing-stops','circle-stroke-opacity',scene==='walk'?.9:scene==='candidates'?.32:0);
    paint(map,'candidates','circle-stroke-opacity',scene==='candidates'?.8:0);
    paint(map,'current-gtfs-stops','circle-stroke-opacity',scene==='baseline'?.95:0);
    paint(map,'final-anchors','circle-stroke-opacity',['finalists','time','end'].includes(scene)?.95:0);
    paint(map,'hub','circle-stroke-opacity',1);
    paint(map,'hub-glow','circle-opacity',0);
    paint(map,'hub-glow','circle-radius',0);
    paint(map,'service-movers','circle-opacity',0);paint(map,'service-movers-glow','circle-opacity',0);
    ['departure-cyan-a','departure-cyan-b','departure-orange'].forEach(id=>paint(map,id,'circle-stroke-opacity',0));
    if(scene!=='buildings') paint(map,'dasymetric-sparks','circle-opacity',0);
  }
  new MutationObserver(hygiene).observe(document.body,{attributes:true,attributeFilter:['data-scene']});
  const timer=setInterval(()=>{if(window.__analysisJourneyMap){hygiene();if(window.__analysisJourneyMap.getLayer('final-routes'))clearInterval(timer);}},120);
  setTimeout(()=>clearInterval(timer),120000);
})();
