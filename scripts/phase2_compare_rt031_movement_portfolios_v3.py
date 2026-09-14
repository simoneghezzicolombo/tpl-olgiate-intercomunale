"""Pinned real one/two-movement comparison; all accessibility is conditional."""
import argparse
import csv
from decimal import Decimal
from fractions import Fraction
import gzip
import hashlib
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.phase2_rt031_movement_portfolios_v3 import enumerate_portfolios
from phase2_rt029_v4_substrate import validate_walk_matrix
from phase2_rt029_v4_metrics import evaluate_unique_stop_sets, _batch_access_metrics

POOL_HASH = 'b80e27f569b78d61a0cce8b0dbd5afd6723629ccf90e8822768ed4d7f3bd5751'
WALK_HASH = 'a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def threshold_vectors(stop_sets, substrate, exact_weights=None):
    """RT028 threshold reachability with exact decimal-source population ratios."""
    meta = substrate.population_meta
    core = meta['population_scope'].astype(str).to_numpy() == 'core'
    decimals = [Decimal(str(v)) for v in (exact_weights if exact_weights is not None
                else meta['population_weight_2025'].tolist())]
    scale = max(0, max(-v.as_tuple().exponent for v in decimals))
    integers = [int(v * (10 ** scale)) for v, use in zip(decimals, core) if use]
    if any(v < 0 for v in integers) or sum(integers) <= 0:
        raise ValueError('invalid population weights')
    codes = meta['population_municipality_code'].astype(str).to_numpy()[core]
    groups = [codes == c for c in sorted(set(codes))]
    matrix = substrate.walk_time_matrix[core]
    if not 0 < len(substrate.stop_index) <= 63:
        raise ValueError('stop mask domain exceeds supported exact integer representation')
    bits = np.left_shift(np.uint64(1), np.arange(len(substrate.stop_index), dtype=np.uint64))
    masks = np.array([sum(int(bits[substrate.stop_index[s]]) for s in stops) for stops in stop_sets], dtype=np.uint64)
    # Split large fixed-point integers into safe int64 limbs. No rounding and
    # no batch-dependent float summation can create a false Pareto distinction.
    base = 10 ** 9
    limb_count = max(1, (max(integers).bit_length() + 28) // 29)
    limbs = [np.array([(v // (base ** k)) % base for v in integers], dtype=np.int64)
             for k in range(limb_count)]
    if len(integers) * (base - 1) > np.iinfo(np.int64).max:
        raise ValueError('unsafe population accumulation size')
    def mass(inside, group):
        total = np.zeros(inside.shape[1], dtype=object)
        for k, limb in enumerate(limbs):
            total += np.sum(inside[group] * limb[group, None], axis=0, dtype=np.int64).astype(object) * (base ** k)
        return total
    all_group = np.ones(len(integers), dtype=bool)
    total_population = sum(integers)
    totals = [sum(v for v, use in zip(integers, g) if use) for g in groups]
    vectors = np.empty((len(stop_sets), 6), dtype=object)
    for ti, t in enumerate((5, 8, 10)):
        population_masks = np.sum(np.where(matrix <= t, bits, np.uint64(0)), axis=1, dtype=np.uint64)
        for start in range(0, len(masks), 256):
            inside = (population_masks[:, None] & masks[None, start:start + 256]) != 0
            vectors[start:start + 256, ti] = [Fraction(v, total_population) for v in mass(inside, all_group)]
            ratios = [[Fraction(v, total) for v in mass(inside, g)] for g, total in zip(groups, totals)]
            vectors[start:start + 256, ti + 3] = [min(values) for values in zip(*ratios)]
    return vectors


def pareto_indices(vectors, costs):
    """Exact no-tolerance nondominance in supplied pool; equal vectors survive."""
    front = []
    display = vectors.astype(float)
    for i in sorted(range(len(costs)), key=lambda k: (costs[k], k)):
        if front:
            f = np.asarray(front)
            # Monotone float projection is only a necessary-condition filter.
            # Every possible domination is confirmed using original exact ratios.
            possible = f[np.all(display[f] >= display[i], axis=1)]
            if any(np.all(vectors[j] >= vectors[i]) and
                   (costs[j] < costs[i] or np.any(vectors[j] > vectors[i])) for j in possible):
                continue
            front = [j for j in front if not (costs[i] <= costs[j] and np.all(display[i] >= display[j]) and
                np.all(vectors[i] >= vectors[j]) and
                (costs[i] < costs[j] or np.any(vectors[i] > vectors[j])))]
        front.append(i)
    return front


def zipped_csv(path, fields, rows):
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding='utf-8', newline='') as text:
                writer = csv.DictWriter(text, fieldnames=fields, lineterminator='\n')
                writer.writeheader()
                writer.writerows(rows)


def main(pool_path, walk_path, out):
    if sha(pool_path) != POOL_HASH or sha(walk_path) != WALK_HASH:
        raise ValueError('pinned input drift')
    pool = json.loads(pool_path.read_text(encoding='utf-8'))
    policy_path = Path('config/phase2_final_policy_contract_v3.json')
    # Windows text checkout may change line endings; pin logical LF bytes as well.
    if hashlib.sha256(policy_path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != '28909df6b9cdcf49608d4e7456f819959d35d1bf2c41dd1800d026bb06d963e0':
        raise ValueError('approved policy lineage drift')
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    cap = Decimal(str(policy['human_policy_decisions']['annual_bus_km_cap']))
    if cap != Decimal('111419') or pool['conditional_headway_min'] != 30 or pool['conditional_annual_days'] != 260:
        raise ValueError('source policy/context drift')
    budget = cap * 1000 / (32 * 260)
    if Decimal(pool['distance_budget_m']) != budget:
        raise ValueError('source distance envelope drift')
    result = enumerate_portfolios(pool['candidates'], distance_budget_m=budget)
    summaries = result.pop('availability_summaries')
    print(json.dumps({'stage': 'enumerated', 'portfolios': len(result['portfolios']), 'sets': len(summaries)}), flush=True)
    raw_walk = pd.read_csv(walk_path, dtype={'population_weight_2025': str})
    weight_map = raw_walk[['population_unit_id', 'population_weight_2025']].drop_duplicates().set_index('population_unit_id')['population_weight_2025'].to_dict()
    substrate = validate_walk_matrix(raw_walk)
    exact_weights = [weight_map[uid] for uid in substrate.population_meta['population_unit_id']]
    stop_sets = [r['available_stop_ids'] for r in summaries]
    vectors = threshold_vectors(stop_sets, substrate, exact_weights)
    print(json.dumps({'stage': 'exact_conditional_metrics_complete'}), flush=True)
    # Independently reconstruct source-decimal weighted sums on three real sets.
    core_mask = substrate.population_meta['population_scope'].astype(str).to_numpy() == 'core'
    weights = [Fraction(Decimal(w)) for w, use in zip(exact_weights, core_mask) if use]
    for i in sorted({0, len(summaries)//2, len(summaries)-1}):
        best = np.min(substrate.walk_time_matrix[core_mask][:, [substrate.stop_index[s] for s in stop_sets[i]]], axis=1)
        expected = [sum((w for w, inside in zip(weights, best <= t) if inside), Fraction(0)) / sum(weights) for t in (5, 8, 10)]
        if list(vectors[i, :3]) != expected:
            raise AssertionError('exact source threshold equivalence failed')
    costs = [Decimal(r['distance_m']) for r in summaries]
    front = pareto_indices(vectors, costs)
    fields = ['potential_core_share_5min', 'potential_core_share_8min', 'potential_core_share_10min',
              'potential_worst_municipality_share_5min', 'potential_worst_municipality_share_8min',
              'potential_worst_municipality_share_10min']
    for i, row in enumerate(summaries):
        row['stop_set_id'] = 'PORTFOLIO_' + hashlib.sha256(';'.join(row['available_stop_ids']).encode()).hexdigest()[:20]
        row.update(zip(fields, (float(x) for x in vectors[i])))
        row['exact_threshold_ratios'] = json.dumps([str(x) for x in vectors[i]])
        row['conditional_annual_carrier_km'] = str(costs[i] * 32 * 260 / 1000)
        row['available_stop_count'] = len(row['available_stop_ids'])
    out.mkdir(parents=True, exist_ok=True)
    id_map = {tuple(r['available_stop_ids']): r['stop_set_id'] for r in summaries}
    portfolio_rows = ({'source_walk_ids': json.dumps(r['source_walk_ids']),
                       'movement_count': r['movement_count'], 'distance_m': r['distance_m'],
                       'stop_set_id': id_map[tuple(r['available_stop_ids'])]} for r in result['portfolios'])
    zipped_csv(out / 'all_portfolios.csv.gz', ['source_walk_ids', 'movement_count', 'distance_m', 'stop_set_id'], portfolio_rows)
    summary_fields = ['stop_set_id', 'available_stop_count', 'distance_m', 'conditional_annual_carrier_km'] + fields + ['exact_threshold_ratios', 'available_stop_ids', 'minimum_distance_witnesses']
    zipped_csv(out / 'availability_comparison.csv.gz', summary_fields, (
        {**r, 'available_stop_ids': json.dumps(r['available_stop_ids']),
         'minimum_distance_witnesses': json.dumps(r['minimum_distance_witnesses'])} for r in summaries))
    frontier = [summaries[i] for i in front]
    (out / 'conditional_frontier.json').write_text(json.dumps(frontier, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    # Full RT029 diagnostics on the frontier only; the threshold comparison above covers every set.
    membership = pd.DataFrame([dict(stop_set_id=r['stop_set_id'], ordered_stop_place_ids=';'.join(r['available_stop_ids'])) for r in frontier])
    access, municipality, equity = evaluate_unique_stop_sets(membership, substrate)
    for name, frame in [('frontier_access.csv', access), ('frontier_municipality.csv', municipality), ('frontier_equity.csv', equity)]:
        frame.to_csv(out / name, index=False, lineterminator='\n')
    audit = {k: v for k, v in result.items() if k != 'portfolios'}
    audit.update(status='PASS_EXACT_SUPPLIED_POOL_COMPARISON_NOT_PRODUCTION_SEARCH',
        upstream_status=pool['status'], upstream_exhaustive=pool['exhaustive'],
        source_commit='0dc76ea21e511308319fd8ceaf4caf82cc4ad165', source_run=34547859460, source_artifact=10179715479,
        input_sha256={'pool': POOL_HASH, 'walk_matrix': WALK_HASH},
        policy_normalized_sha256=hashlib.sha256(policy_path.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        feasible_portfolios=len(result['portfolios']), unique_stop_sets=len(summaries), frontier_size=len(front),
        maximum_available_stop_count=max(map(len, stop_sets)),
        conditional_context={'headway_per_movement_min': 30, 'departures_per_movement_per_day': 32, 'assumed_days': 260,
                             'annual_bus_km_cap': str(cap), 'depot_movements_included': False},
        coverage_semantics='IF_AVAILABLE_STOPS_BECOME_PUBLICLY_SERVED; NO_TRANSFER_OR_ONBOARD_GUARANTEE',
        dominance_arithmetic='EXACT_SOURCE_DECIMAL_POPULATION_RATIOS_AND_DECIMAL_DISTANCE; FLOAT_COLUMNS_DISPLAY_ONLY',
        runtime_or_fleet_optimization=False, primary_selection_authorised=False, runner_up_selection_authorised=False,
        movement_count_is_complexity_objective=False, weighted_score=False,
        extrema={field: max(float(r[field]) for r in summaries) for field in fields},
        output_sha256={p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'audit.json'})
    (out / 'audit.json').write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(audit, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pool', type=Path, required=True)
    parser.add_argument('--walk-matrix', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.pool, args.walk_matrix, args.out)
