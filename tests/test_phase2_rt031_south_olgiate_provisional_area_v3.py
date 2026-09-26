from scripts.phase2_audit_rt031_south_olgiate_provisional_area_v3 import (
    INNER_BOUNDS, ROAD_WAYS_WEST_TO_EAST, exact_weight,
    south_of_road_envelopes,
)


def test_provisional_envelopes_keep_candidate_inside_and_station_outside():
    import pytest
    pytest.importorskip("shapely")
    points = [
        (9.3920542, 45.7310602),
        (9.4032248, 45.7271443),
        (9.4036767, 45.7268922),
        (9.404763, 45.7262542),
        (9.4054814, 45.7258756),
    ]
    roads = {"features": [{
        "properties": {"osm_id": way_id, "name": "Via Como",
                       "other_tags": '"ref"=>"SS342"'},
        "geometry": {"type": "LineString", "coordinates": [right, left]},
    } for way_id, left, right in zip(ROAD_WAYS_WEST_TO_EAST,
                                     points, points[1:])]}
    areas = south_of_road_envelopes(roads)
    from shapely.geometry import Point
    candidate = Point(9.397265069842808, 45.72130999924538)
    station = Point(9.40441, 45.72917)
    old_poi = Point(9.3980, 45.7345)
    assert areas["inner"].difference(areas["outer"]).area < 1e-12
    assert areas["inner"].bounds[0] >= INNER_BOUNDS[0]
    for area in areas.values():
        assert area.covers(candidate)
        assert not area.covers(station)
        assert not area.covers(old_poi)


def test_exact_weight_preserves_decimal_population_sum():
    import numpy as np
    assert exact_weight(["a", "b"], {"a": "1.25", "b": "2.05"},
                        np.array([True, True])) == "3.30"
