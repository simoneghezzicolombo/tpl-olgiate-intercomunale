from src.phase2_rt031_rt023_pairwise_compatibility_v3 import (
    build_pairwise_compatibility, exact_slot_sequence_count, LEGAL, ILLEGAL, UNKNOWN)


def rec(rid,link,direction,s,t,edges,u,v):
    return {"realization_id":rid,"structural_link_id":link,"direction":direction,
            "source_stop_id":s,"target_stop_id":t,"edge_ids":tuple(edges),
            "source_graph_node_id":u,"target_graph_node_id":v}


def b(l,r,status="CERTIFIED_SAME_BOUNDARY_LOCATION"):
    return {"left_realization_id":l,"right_realization_id":r,
            "boundary_correspondence_id":f"b-{l}-{r}","boundary_location_status":status}


def fixture():
    cat={
        "a1":rec("a1","L1","A_TO_B","A","X",["e1"],"nA","nX"),
        "a2":rec("a2","L1","A_TO_B","A","X",["e2"],"nA","nX"),
        "b1":rec("b1","L2","A_TO_B","X","Y",["e3"],"nX","nY"),
        "b2":rec("b2","L2","A_TO_B","X","Y",["e4"],"nX","nY"),
        "c1":rec("c1","L3","A_TO_B","Y","Z",["e5"],"nY","nZ"),
    }
    by={
        ("L1","A_TO_B"):[cat["a1"],cat["a2"]],
        ("L2","A_TO_B"):[cat["b1"],cat["b2"]],
        ("L3","A_TO_B"):[cat["c1"]],
    }
    bounds=[b(a,x) for a in ("a1","a2") for x in ("b1","b2")]
    bounds += [b(x,"c1") for x in ("b1","b2")]
    return cat,by,bounds


def test_pairwise_graph_classifies_all_conceptual_adjacencies():
    cat,_,bounds=fixture()
    rows=build_pairwise_compatibility(cat,bounds,lambda h,n: True,history_locality_certified=True)
    assert len(rows)==6
    assert all(r["status"]==LEGAL for r in rows)


def test_known_rejection_is_illegal():
    cat,_,bounds=fixture()
    rows=build_pairwise_compatibility(cat,bounds,
        lambda h,n: False if h[-1]=="e1" and n=="e3" else True,
        history_locality_certified=True)
    lookup={(r["left_realization_id"],r["right_realization_id"]):r for r in rows}
    assert lookup[("a1","b1")]["status"]==ILLEGAL
    assert lookup[("a1","b2")]["status"]==LEGAL


def test_positive_oracle_without_history_locality_stays_unknown():
    cat,_,bounds=fixture()
    rows=build_pairwise_compatibility(cat,bounds,lambda h,n: True,history_locality_certified=False)
    assert all(r["status"]==UNKNOWN for r in rows)


def test_missing_boundary_evidence_stays_unknown():
    cat,_,bounds=fixture()
    bounds=[r for r in bounds if not (r["left_realization_id"]=="a1" and r["right_realization_id"]=="b1")]
    rows=build_pairwise_compatibility(cat,bounds,lambda h,n: True,history_locality_certified=True)
    lookup={(r["left_realization_id"],r["right_realization_id"]):r for r in rows}
    assert lookup[("a1","b1")]["status"]==UNKNOWN


def test_dp_counts_without_materializing_cartesian_product():
    cat,by,bounds=fixture()
    rows=build_pairwise_compatibility(cat,bounds,lambda h,n: True,history_locality_certified=True)
    result=exact_slot_sequence_count(
        [("L1","A_TO_B"),("L2","A_TO_B"),("L3","A_TO_B")],by,rows)
    assert result["exact"] is True
    assert result["compatible_sequence_count"]==4
    assert result["cartesian_product_not_materialized"] is True


def test_dp_respects_pairwise_rejections():
    cat,by,bounds=fixture()
    rows=build_pairwise_compatibility(cat,bounds,
        lambda h,n: False if h[-1]=="e1" and n=="e3" else True,
        history_locality_certified=True)
    result=exact_slot_sequence_count(
        [("L1","A_TO_B"),("L2","A_TO_B"),("L3","A_TO_B")],by,rows)
    assert result["exact"] is True
    assert result["compatible_sequence_count"]==3


def test_unknown_relevant_pair_blocks_exact_count():
    cat,by,bounds=fixture()
    rows=build_pairwise_compatibility(cat,bounds,
        lambda h,n: None if h[-1]=="e1" and n=="e3" else True,
        history_locality_certified=True)
    result=exact_slot_sequence_count([("L1","A_TO_B"),("L2","A_TO_B")],by,rows)
    assert result["exact"] is False
    assert result["compatible_sequence_count"] is None


def test_unknown_unreachable_pair_does_not_poison_later_stage():
    cat,by,bounds=fixture()
    # a1 cannot reach any L2 alternative; an unknown transition from b1 later
    # is still relevant because b1 is reachable via a2, so exactness must fail.
    def oracle(h,n):
        if h[-1]=="e1" and n in {"e3","e4"}: return False
        if h[-1]=="e3" and n=="e5": return None
        return True
    rows=build_pairwise_compatibility(cat,bounds,oracle,history_locality_certified=True)
    result=exact_slot_sequence_count(
        [("L1","A_TO_B"),("L2","A_TO_B"),("L3","A_TO_B")],by,rows)
    assert result["exact"] is False
