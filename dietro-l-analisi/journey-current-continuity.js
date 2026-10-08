(() => {
  'use strict';

  const map = window.__analysisJourneyMap;
  const patches = window.CURRENT_ROUTE_CONTINUITY_PATCHES || {};
  if (!map || !Object.keys(patches).length) return;

  const same = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length >= 2 && b.length >= 2 && a[0] === b[0] && a[1] === b[1];

  function install() {
    const lineage = window.__analysisJourneyLineage;
    if (!lineage?.installed || !lineage.currentData) {
      requestAnimationFrame(install);
      return;
    }

    let applied = 0;
    const affected = [];
    for (const feature of lineage.currentData.features) {
      const shapeId = feature?.properties?.shape_id;
      const patch = patches[shapeId];
      if (!patch) continue;
      const coords = feature?.geometry?.coordinates;
      if (!Array.isArray(coords) || coords.length < 2 || patch.length < 2 || !same(coords[0], patch[0]) || !same(coords[1], patch[patch.length - 1])) {
        console.error('Current-route continuity patch endpoint mismatch', shapeId);
        continue;
      }
      feature.geometry.coordinates = patch.concat(coords.slice(2));
      feature.properties = {
        ...feature.properties,
        continuity_repair: 'GATE_D_BUS_ELIGIBLE_ROAD_GRAPH',
        continuity_repair_reason: 'IMPOSSIBLE_GTFS_POINT_JUMP_GT_60M'
      };
      applied += 1;
      affected.push(shapeId);
    }

    map.getSource('current-routes')?.setData(lineage.currentData);
    const note = document.querySelector('.route-controls.current small');
    if (note) note.textContent = 'GTFS ufficiale; 7 salti geometrici impossibili sono ricuciti sul grafo stradale Gate D.';

    window.__analysisJourneyCurrentContinuity = {
      installed: true,
      applied,
      expected: Object.keys(patches).length,
      affected,
      method: 'official GTFS + Gate D road-continuity repair',
      kmlEquivalenceClaimed: false
    };

    if (applied !== Object.keys(patches).length) {
      console.error(`Current-route continuity repair incomplete: ${applied}/${Object.keys(patches).length}`);
    }
  }

  install();
})();
