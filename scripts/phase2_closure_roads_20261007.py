"""Read-only, exact-route exclusion proof for two known successor via-way rules.

Absence of a via way excludes patterns contained within a route or its cyclic
repetitions, but does not exclude an active prefix inherited from a deadhead.
For the two known no_* rules here, absence of every to way is the stronger
proof: no prohibited target can be traversed, including at the first edge.
This does not certify bus permissions,
physical suitability, or completeness of restrictions outside frozen evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / 'cache/rt031-certified-via-way/rt031-successor-via-way-relevance.json'
DESIGN = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3/calco_centre_adopted_design.json'
DESIGN_HASH = '8c5f6d445e7ec3e03f6802b686ef7401e7a89efffde6bf928caa98d7d3e14661'
EVIDENCE_HASH = '14e39b47c09c4afe0d26d13b7369b906299db15d14690ba0e5d06e11b2fd7b7c'
EXPECTED = {'18628850': ('no_u_turn', ['1042024466']),
            '19594435': ('no_left_turn', ['238064377'])}


def load_pinned(path, expected_hash):
    data = Path(path).read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError(f'Pinned evidence drift: {path}')
    return json.loads(data)


def exclusion_proof(edge_ids, relations, active_initial_relation_ids=()):
    ways = {edge.split(':')[1] for edge in edge_ids}
    results = []
    for relation in relations:
        via = relation['via_way_ids']
        if not via:
            raise ValueError('A via-way exclusion proof requires explicit via ways')
        overlap = sorted(ways.intersection(via))
        from_overlap = sorted(ways.intersection(relation.get('from_way_ids', [])))
        to_ways = relation.get('to_way_ids', [])
        to_overlap = sorted(ways.intersection(to_ways))
        initial_active = relation['relation_id'] in active_initial_relation_ids
        # Unknown incoming history remains possible. Only a no_* rule with
        # explicit targets absent throughout the route is excluded regardless.
        all_history_excluded = (relation['restriction'].startswith('no_')
                                and bool(to_ways) and not to_overlap)
        first_way = edge_ids[0].split(':')[1] if edge_ids else None
        results.append(dict(relation_id=relation['relation_id'],
                            restriction=relation['restriction'],
                            from_way_ids=relation.get('from_way_ids', []),
                            to_way_ids=to_ways,
                            via_way_ids=via, complete_route_overlap=overlap,
                            from_way_overlap=from_overlap, to_way_overlap=to_overlap,
                            internal_and_cyclic_pattern_excluded=not overlap,
                            first_route_way=first_way,
                            first_edge_is_prohibited_target=first_way in to_ways,
                            supplied_initial_prefix_active=initial_active,
                            supplied_active_prefix_forbids_first_target=(initial_active
                                and relation['restriction'].startswith('no_')
                                and first_way in to_ways),
                            unknown_initial_history_excluded=all_history_excluded,
                            inapplicability_proved=all_history_excluded))
    return results


def build(evidence_path):
    design = load_pinned(DESIGN, DESIGN_HASH)
    evidence = load_pinned(evidence_path, EVIDENCE_HASH)
    relations = evidence['successor_via_way_relations']
    if {r['relation_id']: (r['restriction'], r['via_way_ids']) for r in relations} != EXPECTED:
        raise ValueError('Known relation universe drift')
    edges = [edge for wing in ('east_A', 'west_B')
             for edge in design['loops'][wing]['edge_ids']]
    if len(edges) != 1435:
        raise ValueError('Complete adopted route edge count drift')
    results = exclusion_proof(edges, relations)
    return dict(contract='RT031_EXACT_ADOPTED_ROUTE_KNOWN_VIA_WAY_EXCLUSION_20261007',
                route_directed_edge_count=len(edges),
                route_osm_way_count=len({e.split(':')[1] for e in edges}),
                route_distance_m=design['complete_path_distance_m'],
                design_normalized_sha256=DESIGN_HASH,
                successor_evidence_normalized_sha256=EVIDENCE_HASH,
                relation_results=results,
                two_known_restrictions_inapplicable=all(r['inapplicability_proved'] for r in results),
                initial_history_assumption='UNKNOWN_INCLUDING_PRECEDING_DEADHEAD; absent explicit no_* targets exclude inherited effects for these two relations',
                full_world_road_legality_certified=False,
                physical_operation_ready=False, physical_boarding_authorised=False,
                network_selected=False, decision_budget_km=None, uncertainty_band_min=None,
                scope='Only the two pinned successor-envelope no_* relations on the exact adopted complete route and repetitions; all from/via/to ways absent, including prohibited targets at FS boundary. No last-edge legality or complete-world domain assumption.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--via-way-evidence', type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    print(json.dumps(build(args.via_way_evidence), indent=2))
