// MapLibre GL JS v6 is ESM-only. Keep the cinematic controller compatible
// with the existing global-oriented modules through a mutable facade.
try {
  const maplibreModule = await import("./vendor/maplibre/maplibre-gl.mjs");
  window.maplibregl = { ...maplibreModule };

  // Effects first captures the eventual Map instance. Runtime policy then fixes
  // contextual basemap behaviour. Experience policy applies responsive and OS
  // reduced-motion preferences before journey.js constructs the persistent map.
  await import("./journey-effects.js?v=20261008q");
  await import("./journey-runtime-policy.js");
  await import("./journey-experience-policy.js");

  const { storyMapPadding } = await import("./journey-map-ready.mjs?v=20261008q");
  window.__analysisJourneyMapFrame = () => {
    const scene = document.body.dataset.scene;
    const copy = document.querySelector(`main .chapter[data-scene="${scene}"] .copy`);
    return storyMapPadding({
      width: innerWidth,
      height: innerHeight,
      copyRect: scene === "intro" ? null : copy?.getBoundingClientRect(),
      side: copy?.classList.contains("copy--right") ? "right" : "left",
    });
  };

  // The exploration epilogue must exist before journey.js snapshots the chapter
  // list, otherwise it would not participate in the scroll director.
  await import("./journey-explore-prelude.js?v=20261008q");
  await import("./journey.js?v=20261008q");
  await import("./journey-director.js?v=20261008q");
  await import("./journey-lens.js?v=20261008q");

  // Current-service geometry is taken directly from the supplied official agency
  // KML LineStrings. Do not route, snap or repair D184/D185 through Gate D.
  await import("./journey-lineage.js?v=20261008q");
  await import("./journey-current-kml-exact.mjs?v=20261008q");
  await import("./journey-explore-v2.js?v=20261008q");
} catch (error) {
  window.__analysisJourneyBootError = true;
  document.body.classList.add("journey-runtime-unavailable");
  document.getElementById("loader")?.classList.add("hidden");
  const notice = document.createElement("p");
  notice.className = "journey-boot-notice";
  notice.textContent =
    "La mappa animata non è disponibile su questo dispositivo. Puoi leggere il racconto e aprire la vetrina Nodo8 dai collegamenti.";
  notice.setAttribute("role", "status");
  document.body.appendChild(notice);
  console.error("Journey runtime unavailable", error);
}
await import("./journey-nodo8.mjs?v=20261008q");
