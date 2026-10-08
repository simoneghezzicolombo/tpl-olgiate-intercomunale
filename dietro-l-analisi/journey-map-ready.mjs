/* Sources decoded from cache may arrive before the initial MapLibre style. */
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
