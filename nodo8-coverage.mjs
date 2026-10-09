/* Same-substrate spatial comparison only, never demand or service ranking. */
export function validateCoverageComparison(comparison, proposal) {
  if (comparison?.contract !== "nodo8_same_substrate_spatial_coverage_comparison_v1" ||
      comparison.proposal_coverage_reproduced !== true ||
      comparison.all_unattached_points_proven_outside_core_thresholds !== true ||
      comparison.baseline_trip_level_current_activation_certified !== false ||
      comparison.temporary_bridge_disruption_included !== false ||
      comparison.additional_resident_count_inferred !== false)
    throw new Error("Confronto spaziale non verificato.");
  if (!Array.isArray(comparison.distant_unattached_points) || comparison.distant_unattached_points.some(point =>
      !Number.isFinite(point.minimum_core_distance_lower_bound_m) || point.minimum_core_distance_lower_bound_m <= 800))
    throw new Error("Fermata irrisolta che potrebbe cambiare la copertura.");
  const codes = ["TOTAL", ...proposal.municipalities.map(m => m.code)];
  for (const code of codes) for (const time of ["5", "8", "10"]) {
    const before = comparison.baseline_percent?.[code]?.[time];
    const after = comparison.proposal_percent?.[code]?.[time];
    const delta = comparison.delta_percentage_points?.[code]?.[time];
    if (![before, after, delta].every(Number.isFinite) || before < 0 || before > 100 ||
        after < 0 || after > 100 || Math.abs(after - proposal.coverage[code][time]) > 1e-7 ||
        Math.abs(delta - (after - before)) > 1e-7)
      throw new Error("Coperture o differenza incoerenti.");
  }
  return comparison;
}
export function coverageChangeLabel(delta) {
  if (!Number.isFinite(delta)) throw new Error("Differenza non disponibile.");
  return (delta > 0 ? "+" : delta < 0 ? "−" : "") +
    new Intl.NumberFormat("it-IT", {maximumFractionDigits: 2}).format(Math.abs(delta)) + " p.p.";
}
