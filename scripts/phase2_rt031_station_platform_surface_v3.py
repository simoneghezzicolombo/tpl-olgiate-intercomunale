"""Local station surface attachment; leave the certified RT028 graph intact.

Native stair tops inside a published platform polygon are real access nodes,
not just its boundary vertices. Modelling a short walk within that polygon is
explicit geometric inference, not a new OSM highway or a measured door path.
Underground nodes inside its 2-D projection must NEVER become surface targets.
"""
from itertools import combinations
from shapely.geometry import LineString, Point, Polygon

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
    _allows_foot, _haversine_m, BLOCKING_ACCESS, FOOT_OVERRIDE_ALLOW,
)

MODEL_KIND = 'MODELLED_WALK_WITHIN_SOURCE_PLATFORM_AREA'


def negative_layer(tags):
    try:
        return float(tags.get('layer', '0')) < 0
    except ValueError:
        return True  # ambiguous layers cannot establish surface access


def surface_nodes(platform_way, ways, nodes, graph_nodes):
    tags = platform_way['tags']
    if (tags.get('railway') != 'platform' or tags.get('area') != 'yes'
            or tags.get('foot') in BLOCKING_ACCESS
            or (tags.get('access') in BLOCKING_ACCESS and tags.get('foot') not in FOOT_OVERRIDE_ALLOW)
            or negative_layer(tags)):
        raise ValueError('Public surface platform polygon required')
    if platform_way['nodes'][0] != platform_way['nodes'][-1]:
        raise ValueError('Closed platform area required')
    polygon = Polygon([nodes[n]['coordinates_lon_lat'] for n in platform_way['nodes']])
    if not polygon.is_valid or polygon.is_empty:
        raise ValueError('Valid platform polygon required')
    underground = {n for w in ways.values()
                   if _allows_foot(w['tags']) and w['tags'].get('tunnel') == 'yes'
                   and negative_layer(w['tags']) for n in w['nodes']}
    boundary = (set(platform_way['nodes']) & set(graph_nodes))-underground
    boundary = {n for n in boundary if not negative_layer(nodes[n]['tags'])}
    tops, bindings = set(), []
    for wid, way in ways.items():
        if not _allows_foot(way['tags']) or way['tags'].get('highway') != 'steps':
            continue
        if len(way['nodes']) < 2:
            continue
        first, last = way['nodes'][0], way['nodes'][-1]
        for upper, lower in ((first, last), (last, first)):
            if (lower in underground and upper not in underground and upper in graph_nodes
                    and not negative_layer(nodes[upper]['tags'])
                    and polygon.covers(Point(nodes[upper]['coordinates_lon_lat']))):
                tops.add(upper)
                bindings.append(dict(upper_node_id=upper, underground_node_id=lower, steps_osm_way_id=wid,
                                     upper_not_platform_boundary=upper not in platform_way['nodes'],
                                     upper_surface_assignment_is_topology_inference=True))
    return polygon, boundary, tops, bindings, underground


def augment_platform_surfaces(adjacency, provenance, nodes, ways, platform_ids):
    # Copies: never mutate the certified graph, its digest or its shared lists.
    augmented = {u: list(edges) for u, edges in adjacency.items()}
    sources = {pair: list(records) for pair, records in provenance.items()}
    graph_nodes = set(adjacency)
    tracks = [LineString([nodes[n]['coordinates_lon_lat'] for n in w['nodes']])
              for w in ways.values() if w['tags'].get('railway') == 'rail'
              and not negative_layer(w['tags']) and len(w['nodes']) >= 2]
    platforms = {}
    for ref, wid in platform_ids.items():
        area, boundary, tops, stairs, underground = surface_nodes(ways[wid], ways, nodes, graph_nodes)
        targets = boundary | tops
        connections = []
        for u, v in combinations(sorted(targets), 2):
            coords = [nodes[n]['coordinates_lon_lat'] for n in (u, v)]
            geom = LineString(coords)
            if not area.covers(geom) or any(geom.intersects(track) for track in tracks):
                continue
            length = _haversine_m(coords[0][1], coords[0][0], coords[1][1], coords[1][0])
            if length <= 0:
                continue
            for a, b in ((u,v), (v,u)):
                if any(nxt == b for nxt, _ in augmented[a]):
                    continue
                augmented[a].append((b, length))
                sources[a,b] = [dict(osm_way_id=wid, tags=ways[wid]['tags'],
                    geometry_kind=MODEL_KIND, original_osm_highway_edge=False,
                    inside_same_platform_polygon=True, surface_rail_crossing=False,
                    physical_walk_clearance_certified=False)]
                connections.append(dict(u=a, v=b, length_m=length, platform_osm_way_id=wid,
                    geometry_kind=MODEL_KIND, coordinates_lon_lat=[nodes[n]['coordinates_lon_lat'] for n in (a,b)]))
        platforms[ref] = dict(surface_access_node_ids=sorted(targets),
            original_boundary_access_node_ids=sorted(boundary), native_internal_stair_top_ids=sorted(tops),
            stair_top_to_underground_bindings=stairs, modelled_surface_edges=connections,
            underground_nodes_excluded_as_surface_targets=sorted(underground & set(graph_nodes)
                & {n for n in graph_nodes if area.covers(Point(nodes[n]['coordinates_lon_lat']))}),
            topology_or_surface_geometry_is_physical_certificate=False)
    reverse = {u: [] for u in augmented}
    for u, edges in augmented.items():
        for v, length in edges:
            reverse[v].append((u,length))
    return augmented, reverse, sources, platforms
