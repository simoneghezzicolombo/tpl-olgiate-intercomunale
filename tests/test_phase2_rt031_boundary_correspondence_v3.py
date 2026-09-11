import pytest
from src.phase2_rt031_boundary_correspondence_v3 import build_boundary_catalog, CERTIFIED, UNKNOWN


def edge(e,u,v):
    return {"edge_id":e,"u_node_id":u,"v_node_id":v}


def corridor(cid,e,u,v):
    return {"corridor_id":cid,"path_edge_ids":e,"path_node_ids":f"{u};{v}","elementary_for_structural_reduction":"true"}


def pattern(rid,cid,s,t):
    return {"realization_id":rid,"corridor_id":cid,"source_endpoint_stop_id":s,"target_endpoint_stop_id":t}


def occ(rid,seq,stop,node,evidence="CERTIFIED_ATTACHMENT_NODE_ON_ORDERED_PATH"):
    return {"realization_id":rid,"stop_sequence":seq,"stop_place_id":stop,"path_node_id":node,
            "certified_attachment_node_id":node,"evidence_type":evidence}


def base():
    edges=[edge("a","A","X"),edge("b","X","B")]
    corridors=[corridor("c1","a","A","X"),corridor("c2","b","X","B")]
    patterns=[pattern("r1","c1","S1","SX"),pattern("r2","c2","SX","S2")]
    occurrences=[occ("r1",1,"S1","A"),occ("r1",2,"SX","X"),occ("r2",1,"SX","X"),occ("r2",2,"S2","B")]
    return patterns,occurrences,corridors,edges


def test_certifies_same_boundary_location_but_not_service_event():
    rows=build_boundary_catalog(*base())
    assert len(rows)==1
    r=rows[0]
    assert r["boundary_location_status"]==CERTIFIED
    assert r["same_service_event_certified"] is False
    assert r["automatic_occurrence_merge_authorized"] is False
    assert r["vehicle_continuity"] is None
    assert r["passenger_continuity"] is None


def test_nonnodal_boundary_stays_unknown_not_merged():
    p,o,c,e=base()
    o[1]["evidence_type"]="CERTIFIED_GLOBAL_NEAREST_PHYSICAL_SEGMENT_ON_ORDERED_PATH"
    rows=build_boundary_catalog(p,o,c,e)
    assert rows[0]["boundary_location_status"]==UNKNOWN
    assert rows[0]["automatic_occurrence_merge_authorized"] is False


def test_carrier_contiguous_stop_mismatch_fails_closed():
    p,o,c,e=base()
    p[1]["source_endpoint_stop_id"]="OTHER"
    o[2]["stop_place_id"]="OTHER"
    with pytest.raises(ValueError, match="boundary stop"):
        build_boundary_catalog(p,o,c,e)


def test_endpoint_occurrence_must_match_carrier_node():
    p,o,c,e=base()
    o[1]["path_node_id"]="Y"
    with pytest.raises(ValueError, match="carrier end node"):
        build_boundary_catalog(p,o,c,e)


def test_missing_occurrence_group_fails():
    p,o,c,e=base()
    o=[r for r in o if r["realization_id"]!="r2"]
    with pytest.raises(ValueError, match="missing occurrence"):
        build_boundary_catalog(p,o,c,e)
