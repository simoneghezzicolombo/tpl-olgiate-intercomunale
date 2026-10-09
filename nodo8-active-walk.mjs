/* Potential spatial walking access on frozen RT028, selected networks only. */
export const ACTIVE_WALK_NETWORKS = Object.freeze(["NODO8", "D184", "D185"]);
const COLUMNS = ["population_unit_id", "longitude", "latitude", "municipality_code", "population_weight_2025", ...ACTIVE_WALK_NETWORKS];
const validMinutes = value => value === null || (Number.isFinite(value) && value >= 0);

export function validateActiveWalkAsset(asset, proposal) {
  if (asset?.contract !== "nodo8_active_network_population_walk_v1" ||
      asset.population_scope !== "core" || asset.population_unit_count !== 4283 ||
      asset.full_rt016_population_unit_count !== 10230 ||
      asset.population_coordinate_join !== "EXACT_RT016_UNIT_ID_TO_RT028_POPULATION_UNIT_ID" ||
      asset.walk_speed_m_per_min !== 80 || asset.max_connector_m !== 90 ||
      asset.union_rule !== "MINIMUM_OF_ENABLED_NETWORK_TIMES" || asset.s8_contributes !== false ||
      asset.current_service_date !== "2026-05-06" ||
      asset.pedestrian_snapshot_timestamp !== "2026-09-06T12:00:00Z" ||
      asset.pedestrian_graph_digest !== "aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4" ||
      asset.null_semantics !== "UNREACHABLE_OR_UNATTACHED_IN_FROZEN_RT028_MODEL" ||
      asset.proposal_coverage_reproduced !== true ||
      JSON.stringify(asset.network_names) !== JSON.stringify(ACTIVE_WALK_NETWORKS) ||
      JSON.stringify(asset.columns) !== JSON.stringify(COLUMNS) ||
      JSON.stringify(asset.thresholds_min) !== "[5,8,10]" ||
      JSON.stringify(asset.connectors_included) !== '["population","stop"]' ||
      !Array.isArray(asset.rows) || asset.rows.length !== asset.population_unit_count)
    throw new Error("Accesso pedonale alle reti attive non verificato.");
  for (const key of ["access_is_observed_demand", "live_or_gps", "latest_2026_27_timetable", "useful_direction_or_frequency_certified",
                     "physical_boarding_authorised", "external_population_included", "outside_frozen_graph_stops_rematerialized"])
    if (asset.limitations?.[key] !== false) throw new Error("Limiti del modello pedonale mancanti.");
  for (const key of ["population_coordinates", "walk_matrix", "pedestrian_osm", "pedestrian_snapshot_metadata", "proposal", "dated_current_service"])
    if (!asset.sources?.[key]?.path || !/^[a-f0-9]{64}$/.test(asset.sources[key].sha256))
      throw new Error("Provenienza del modello pedonale mancante.");
  const ids = new Set(), municipalityCodes = new Set(["97010", "97012", "97058", "97074", "97092"]);
  for (const row of asset.rows) {
    if (!Array.isArray(row) || row.length !== COLUMNS.length || !/^WP_\d{5}$/.test(row[0]) || ids.has(row[0]) ||
        !Number.isFinite(row[1]) || Math.abs(row[1]) > 180 || !Number.isFinite(row[2]) || Math.abs(row[2]) > 90 ||
        !municipalityCodes.has(row[3]) || !Number.isFinite(row[4]) || row[4] < 0 || !row.slice(5).every(validMinutes))
      throw new Error("Unità di popolazione o tempi pedonali incoerenti.");
    ids.add(row[0]);
  }
  for (const code of ["TOTAL", ...municipalityCodes]) {
    const rows = asset.rows.filter(row => code === "TOTAL" || row[3] === code);
    const weight = rows.reduce((sum, row) => sum + row[4], 0);
    if (!(weight > 0)) throw new Error("Peso di popolazione del modello mancante.");
    for (const limit of [5, 8, 10]) {
      const actual = 100 * rows.reduce((sum, row) => sum + (row[5] !== null && row[5] <= limit ? row[4] : 0), 0) / weight;
      const expected = asset.nodo8_percent?.[code]?.[limit];
      const proposalPercent = proposal?.coverage?.[code]?.[limit];
      if (!Number.isFinite(expected) || Math.abs(actual - expected) > 1e-7 ||
          (proposal && (!Number.isFinite(proposalPercent) || Math.abs(expected - proposalPercent) > 1e-7)))
        throw new Error("Copertura Nodo8 del modello pedonale non riprodotta.");
    }
  }
  return asset;
}

export function activeWalkNetworks({ nodo8 = false, current = false, currentRouteChoice = "ALL" } = {}) {
  const networks = nodo8 ? ["NODO8"] : [];
  if (current) for (const route of ["D184", "D185"])
    if (currentRouteChoice === "ALL" || currentRouteChoice === route) networks.push(route);
  return networks;
}

function selectedNetworks(networkNames) {
  const names = new Set(Array.isArray(networkNames) ? networkNames : []);
  return ACTIVE_WALK_NETWORKS.filter(name => names.has(name));
}

export function activeWalkFeatureCollection(asset, networkNames = []) {
  const networks = selectedNetworks(networkNames);
  if (!networks.length) return { type: "FeatureCollection", features: [] };
  const indexes = networks.map(name => COLUMNS.indexOf(name));
  return { type: "FeatureCollection", features: asset.rows.map(row => {
    const values = indexes.map(index => row[index]).filter(value => value !== null);
    const walk = values.length ? Math.min(...values) : null;
    return { type: "Feature", id: row[0], geometry: { type: "Point", coordinates: [row[1], row[2]] },
      properties: { source_population_unit_id: row[0], municipality_code: row[3], population_weight: row[4],
                    walk_min: walk, walk_band: walk === null ? "unreachable" : walk <= 5 ? "5" : walk <= 8 ? "8" : walk <= 10 ? "10" : "over10",
                    active_networks: networks.join("+") } };
  }) };
}

export function activeWalkLabel(networkNames = []) {
  const labels = selectedNetworks(networkNames).map(name => name === "NODO8" ? "Nodo8" : name);
  return labels.length ? labels.join(" + ") : "Nessuna rete bus attiva";
}
