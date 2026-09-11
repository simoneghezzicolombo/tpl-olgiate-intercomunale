#!/usr/bin/env python3
"""Evaluate complete declared real routes; no territorial search or service claim."""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
from scripts.phase2_audit_rt031_real_pairwise_compatible_domain_v3 import (
    load_inputs, validate_via_way_evidence, sha256_file, canonical,
    build_realization_catalog, build_boundary_catalog, FrozenRT017ViaNodeAdapter,
    RT023ScopedTransitionOracle, build_pairwise_compatibility)
from src.phase2_rt031_hamiltonian_expressiveness_v3 import (
    FrozenStructuralGraph, find_hamiltonian_path, find_hamiltonian_cycle, verify_witness)
from src.phase2_rt031_complete_chain_distance_v3 import optimize_chain
from src.phase2_rt031_exact_resource_screen_v3 import closed_walk_metric_mst_bound
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import evaluate_realization_chain, LEGAL


def main(root, evidence, out):
    tables, hashes = load_inputs(root)
    validate_via_way_evidence(evidence)
    catalog, by_slot = build_realization_catalog(tables['patterns'], tables['corridors'], tables['edges'])
    boundary = build_boundary_catalog(tables['patterns'], tables['occurrences'], tables['corridors'], tables['edges'])
    adapter = FrozenRT017ViaNodeAdapter(tables['edges'], tables['rules'], unresolved_external_via_way_count=2)
    scoped = RT023ScopedTransitionOracle(adapter, sorted({e for r in catalog.values() for e in r['edge_ids']}),
        successor_via_way_irrelevance_certified=True, evidence_id='RT031_SUCCESSOR_VIA_WAY::'+sha256_file(evidence))
    for r in catalog.values():
        if evaluate_realization_chain([r], boundary, scoped.oracle)['status'] != LEGAL:
            raise ValueError('uncertified atomic legality')
    pairwise = build_pairwise_compatibility(catalog,boundary,scoped.oracle,history_locality_certified=True)
    adjacency, links, directional = defaultdict(set), {}, {}
    for slot, variants in by_slot.items():
        r = variants[0]
        a,b = r['source_stop_id'],r['target_stop_id']
        key = tuple(sorted((a,b)))
        if key in links and links[key] != slot[0]: raise ValueError('parallel structural identity')
        links[key] = slot[0]
        adjacency[a].add(b)
        directional[a,b] = slot
    if len(adjacency)!=35 or len(links)!=110 or len(directional)!=220:
        raise ValueError('frozen graph cardinality changed')
    if any((b,a) not in directional for a,b in directional): raise ValueError('nonreciprocal graph')
    graph = FrozenStructuralGraph(tuple(sorted(adjacency)),{v:tuple(sorted(n)) for v,n in adjacency.items()},links)
    path,cycle = find_hamiltonian_path(graph),find_hamiltonian_cycle(graph)
    verify_witness(graph,path,cycle=False); verify_witness(graph,cycle,cycle=True)
    if not path.feasible or not cycle.feasible: raise ValueError('structural witnesses absent')
    p,c = list(path.ordered_vertices),list(cycle.ordered_vertices)
    declarations = {
        'all_stop_path_forward':(p,False),
        'all_stop_path_reverse':(p[::-1],False),
        'all_stop_path_out_return':(p+p[-2::-1],False),
        'all_stop_path_repeating_out_return':(p+p[-2::-1],True),
        'all_stop_cycle_forward':(c+[c[0]],True),
        'all_stop_cycle_reverse':([c[0]]+c[:0:-1]+[c[0]],True),
    }
    edges = {e['edge_id']:e for e in tables['edges']}
    weights = {rid:sum((Decimal(edges[e]['length_m']) for e in r['edge_ids']),Decimal(0)) for rid,r in catalog.items()}
    # A stop available inside any atom need not be an endpoint of a selected atom.
    # Exclude ALL such possibilities, not only universally guaranteed interiors.
    interiors = set()
    for pattern in tables['patterns']:
        interiors.update(pattern['ordered_passenger_stop_ids'].split(';')[1:-1])
    mandatory = set(graph.vertices) - interiors
    bound = closed_walk_metric_mst_bound(
        [(r['source_stop_id'],r['target_stop_id'],weights[rid]) for rid,r in catalog.items()],mandatory)
    bound['excluded_possible_interior_stop_ids'] = sorted(interiors)
    results = []
    for name,(vertices,closed) in declarations.items():
        slots = [directional[a,b] for a,b in zip(vertices,vertices[1:])]
        result = optimize_chain(slots,by_slot,pairwise,weights,closed=closed,
            atomic_legality_certified=True,history_locality_certified=True)
        result.update(scenario_id=name,ordered_stop_vertices=vertices,ordered_slots=slots,
                      distinct_structural_stops=len(set(vertices)),
                      independent_slot_distance_lower_bound_m=str(sum(min(weights[r['realization_id']] for r in by_slot[s]) for s in slots)),
                      pickup_dropoff_assignment=None,operating_frequency=None,cycle_time_minutes=None,
                      annual_vehicle_km=None,service_cost_eur=None)
        if result['realization_ids']:
            selected = [catalog[r] for r in result['realization_ids']]
            # Independent full-history replay, including the circuit seam.
            replay = selected + ([selected[0]] if closed else [])
            if evaluate_realization_chain(replay,boundary,scoped.oracle)['status'] != LEGAL:
                raise AssertionError('selected witness fails full-history replay')
            if sum(weights[r] for r in result['realization_ids']) != Decimal(result['minimum_distance_m']):
                raise AssertionError('distance recomputation failed')
            result['full_history_replay_pass'] = True
        else: result['full_history_replay_pass'] = None
        results.append(result)
    payload = dict(contract='RT031_DECLARED_COMPLETE_ROUTE_PHYSICAL_EVALUATION_V3',
                   source_sha256=hashes,via_way_evidence_sha256=sha256_file(evidence),
                   scenarios=results,production_rt031_pass=False,
                   all_stop_single_closed_walk_lower_bound=bound,
                   scope='Six deterministic structural stress scenarios, not a territorial candidate frontier or an operated service.',
                   missing_for_service_evaluation=['evidence-backed service events','operating context and timetable','travel-time calibration','operating budget','production search contract'])
    out.mkdir(parents=True,exist_ok=True)
    (out/'complete_route_evaluation.json').write_bytes(canonical(payload))
    lines=['# Complete-route physical evaluation','',
           'Six predeclared structural stress scenarios. All cover 35 structural stops; this is not a passenger service or a recommended network.','',
           '| Scenario | Traversals | Closed seam | Compatible realizations | Minimum carrier km |',
           '|---|---:|---|---:|---:|']
    for r in results:
        km = '—' if r['minimum_distance_m'] is None else f"{Decimal(r['minimum_distance_m'])/1000:.3f}"
        lines.append(f"| {r['scenario_id']} | {r['slot_count']} | {r['closed']} | {r['compatible_sequence_count']} | {km} |")
    lines += ['', 'Distances count every carrier traversal, including repeats. They exclude an unprovided depot/repositioning plan. No times, frequencies, annual bus-km, euro costs or passenger continuity are inferred. Zero means no compatible realization for this exact ordered scenario in the frozen atom domain, not impossibility of every all-stop network.','']
    (out/'complete_route_comparison.md').write_text('\n'.join(lines))
    print('\n'.join(lines))
    print(json.dumps({'all_stop_single_closed_walk_lower_bound':bound},sort_keys=True))
    return payload


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--via-way-evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.inputs,a.via_way_evidence,a.out)
