import * as maplibreModule from './vendor/maplibre/maplibre-gl.mjs';

// MapLibre GL JS v6 is ESM-only. Keep the cinematic controller compatible
// with the existing global-oriented modules through a mutable facade.
window.maplibregl = { ...maplibreModule };

await import('./journey-effects.js');
await import('./journey-runtime-policy.js');
await import('./journey.js');
await import('./journey-director.js');
