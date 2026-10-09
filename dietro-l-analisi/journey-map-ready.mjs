/* Sources decoded from cache may arrive before the initial MapLibre style. */
// Presentation framing only: reserve the actual narrative column, rather than
// centering the evidence under an opaque card. Never alter route coordinates.
export function storyMapPadding({ width, height, copyRect, side = "left" }) {
  const padding = { top: 100, bottom: 70, left: 40, right: 58 };
  if (width <= 800) return { top: 90, bottom: 70, left: 25, right: 25 };
  if (!copyRect || !Number.isFinite(copyRect.width)) return padding;
  // Keep a useful map window even on small laptops or very wide text chapters.
  const reserveLimit = Math.max(40, width - 350 - padding.right);
  if (side === "right") {
    padding.right = Math.min(Math.max(58, width - copyRect.left + 20), reserveLimit);
  } else {
    padding.left = Math.min(Math.max(40, copyRect.right + 20), reserveLimit);
  }
  padding.top = Math.min(padding.top, height * 0.2);
  padding.bottom = Math.min(padding.bottom, height * 0.15);
  return padding;
}

export async function waitForPreparedMap(
  map,
  { timeoutMs = 60000, pollMs = 50 } = {},
) {
  const started = performance.now();
  while (performance.now() - started < timeoutMs) {
    // Sentinels installed by the primary map load handler, not tile readiness.
    if (map.getLayer("hub") && map.getSource("current-routes")) return map;
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw new Error("Primary map layers were not prepared before the deadline.");
}
