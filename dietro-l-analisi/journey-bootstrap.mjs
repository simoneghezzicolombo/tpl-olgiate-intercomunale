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
await import('./journey.js');
await import('./journey-director.js');
await import('./journey-lens.js');
await import('./journey-lineage.js');
