"""Platform surface identity cannot erase underground level or invent rails crossings."""
import copy

import pytest

from scripts.phase2_rt031_station_platform_surface_v3 import (
    augment_platform_surfaces, surface_nodes, MODEL_KIND,
)


def fixture():
    coords = {'b': [0,0], 'q': [.001,0], 'r': [.001,.001], 's': [0,.001],
              'upper': [.0002,.0002], 'lower': [.0003,.0003], 'far': [.0004,.0004],
              'bus': [-.0001,0]}
    nodes = {n: dict(coordinates_lon_lat=c, tags={}) for n,c in coords.items()}
    ways = {
        'platform': dict(nodes=['b','q','r','s','b'], tags={'railway':'platform','area':'yes','ref':'1'}),
        'steps': dict(nodes=['upper','lower'], tags={'highway':'steps'}),
        'tunnel': dict(nodes=['lower','far'], tags={'highway':'footway','tunnel':'yes','layer':'-1'}),
    }
    adjacency = {'bus':[('b',10)], 'b':[('bus',10)], 'upper':[('lower',10)],
                 'lower':[('upper',10),('far',10)], 'far':[('lower',10)]}
    provenance = {(u,v):[dict(osm_way_id='native',tags={'highway':'footway'})]
                  for u, edges in adjacency.items() for v, _ in edges}
    return adjacency, provenance, nodes, ways


def test_native_internal_stair_top_is_included_but_underground_projection_is_not():
    adjacency, _, nodes, ways = fixture()
    _, boundary, tops, stairs, underground = surface_nodes(ways['platform'],ways,nodes,set(adjacency))
    assert boundary == {'b'} and tops == {'upper'}
    assert 'lower' in underground and 'far' in underground
    assert 'lower' not in tops and 'far' not in tops
    assert stairs[0]['upper_not_platform_boundary']


def test_surface_connection_is_explicit_inference_and_original_graph_is_immutable():
    adjacency, provenance, nodes, ways = fixture()
    before_adj, before_sources = copy.deepcopy(adjacency), copy.deepcopy(provenance)
    augmented, reverse, sources, surfaces = augment_platform_surfaces(adjacency,provenance,nodes,ways,{'1':'platform'})
    assert adjacency == before_adj and provenance == before_sources
    assert any(v == 'upper' for v, _ in augmented['b'])
    assert any(v == 'b' for v, _ in reverse['upper'])
    witness = sources['b','upper'][0]
    assert witness['geometry_kind'] == MODEL_KIND and not witness['original_osm_highway_edge']
    assert witness['inside_same_platform_polygon'] and not witness['surface_rail_crossing']
    assert not witness['physical_walk_clearance_certified']
    assert 'lower' in surfaces['1']['underground_nodes_excluded_as_surface_targets']


def test_no_surface_shortcut_across_a_track_even_inside_bad_platform_outline():
    adjacency, provenance, nodes, ways = fixture()
    nodes['rail_a'] = dict(coordinates_lon_lat=[.0001,-.001],tags={})
    nodes['rail_b'] = dict(coordinates_lon_lat=[.0001,.001],tags={})
    ways['rail'] = dict(nodes=['rail_a','rail_b'], tags={'railway':'rail'})
    augmented, _, _, surfaces = augment_platform_surfaces(adjacency,provenance,nodes,ways,{'1':'platform'})
    assert augmented['b'] == adjacency['b']
    assert surfaces['1']['modelled_surface_edges'] == []


def test_concave_platform_does_not_allow_straight_line_outside_its_area():
    adjacency, provenance, nodes, ways = fixture()
    nodes['b']['coordinates_lon_lat'] = [0,.001]
    nodes['upper']['coordinates_lon_lat'] = [.0009,.0001]
    outline = [[0,.001],[0,0],[.001,0],[.001,.0003],[.0003,.0003],[.0003,.001],[0,.001]]
    ids = ['b']
    for i, c in enumerate(outline[1:-1]):
        name = 'corner'+str(i); nodes[name]=dict(coordinates_lon_lat=c,tags={}); ids.append(name)
    ways['platform']['nodes'] = ids+['b']
    augmented, _, _, surfaces = augment_platform_surfaces(adjacency,provenance,nodes,ways,{'1':'platform'})
    assert augmented['b'] == adjacency['b']
    assert surfaces['1']['modelled_surface_edges'] == []


@pytest.mark.parametrize('tags', [{'access':'private'}, {'foot':'no'}, {'layer':'-1'}, {'layer':'ambiguous'}])
def test_restricted_or_underground_platform_fails_closed(tags):
    adjacency, provenance, nodes, ways = fixture()
    ways['platform']['tags'].update(tags)
    with pytest.raises(ValueError, match='Public surface'):
        augment_platform_surfaces(adjacency,provenance,nodes,ways,{'1':'platform'})


def test_private_steps_do_not_supply_a_public_stair_top():
    adjacency, _, nodes, ways = fixture()
    ways['steps']['tags']['foot'] = 'no'
    _, _, tops, bindings, _ = surface_nodes(ways['platform'],ways,nodes,set(adjacency))
    assert tops == set() and bindings == []
