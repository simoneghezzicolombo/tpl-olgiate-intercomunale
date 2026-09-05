import * as maplibreModule from './vendor/maplibre/maplibre-gl.mjs';

// MapLibre GL JS v6 is ESM-only. Keep the cinematic controller compatible
// with the existing global-oriented modules through a mutable facade.
window.maplibregl = { ...maplibreModule };

// Effects first captures the eventual Map instance. Runtime policy then fixes
// contextual basemap behaviour. Experience policy applies responsive and OS
// reduced-motion preferences before journey.js constructs the persistent map.
await import('./journey-effects.js');
await import('./journey-runtime-policy.js');
await import('./journey-experience-policy.js');

// The exploration epilogue must exist before journey.js snapshots the chapter
// list, otherwise it would not participate in the scroll director.
await import('./journey-explore-prelude.js');
await import('./journey.js');
await import('./journey-director.js');
await import('./journey-lens.js');

// The frozen agency GTFS contains seven impossible point-to-point teleports in
// D184/D185. Keep the raw source intact, then replace only those chords with
// connectors on the certified Gate D bus-eligible road graph.
await import('./current-route-continuity-patches.js');
await import('./journey-lineage.js');
await import('./journey-current-continuity.js');
await import('./journey-explore.js');
