from src.phase2_rt031_rt023_physical_compatible_domain_v3 import (
    build_realization_catalog, evaluate_realization_chain, compose_slot_domain,
    LEGAL, ILLEGAL, UNKNOWN, RESOURCE)


def edge(e,u,v):
    return {"edge_id":e,"u_node_id":u,"v_node_id":v}


def corridor(cid,edge_ids,nodes):
    return {"corridor_id":cid,"path_edge_ids":";".join(edge_ids),"path_node_ids":";".join(nodes)}


def pattern(rid,cid,link,direction,alt,s,t):
    return {"realization_id":rid,"corridor_id":cid,"structural_link_id":link,
            "direction":direction,"alternative_ordinal":alt,
            "source_endpoint_stop_id":s,"target_endpoint_stop_id":t}


def boundary(l,r,status="CERTIFIED_SAME_BOUNDARY_LOCATION"):
    return {"left_realization_id":l,"right_realization_id":r,
            "boundary_correspondence_id":f"b-{l}-{r}","boundary_location_status":status}


def fixture():
    edges=[edge("a","A","X"),edge("a2","A","X"),edge("b","X","B"),edge("b2","X","B")]
    corridors=[corridor("c1",["a"],["A","X"]),corridor("c1b",["a2"],["A","X"]),
               corridor("c2",["b"],["X","B"]),corridor("c2b",["b2"],["X","B"])]
    patterns=[pattern("r1","c1","L1","A_TO_B",1,"S1","SX"),
              pattern("r1b","c1b","L1","A_TO_B",2,"S1","SX"),
              pattern("r2","c2","L2","A_TO_B",1,"SX","S2"),
              pattern("r2b","c2b","L2","A_TO_B",2,"SX","S2")]
    return patterns,corridors,edges


def test_catalog_preserves_all_slot_alternatives():
    catalog,by=build_realization_catalog(*fixture())
    assert len(catalog)==4
    assert [r["realization_id"] for r in by[("L1","A_TO_B")]]==["r1","r1b"]


def test_all_true_oracle_yields_complete_four_way_domain():
    _,by=build_realization_catalog(*fixture())
    bounds=[boundary(a,b) for a in ("r1","r1b") for b in ("r2","r2b")]
    result=compose_slot_domain([("L1","A_TO_B"),("L2","A_TO_B")],by,bounds,
                               lambda history,nxt: True,
                               alternatives_complete=True,max_compositions=10)
    assert result["status"]==LEGAL
    assert result["complete"] is True
    assert result["declared_alternative_product_size"]==4
    assert result["legal_composition_count"]==4


def test_one_rejected_combination_is_removed_but_domain_stays_complete():
    _,by=build_realization_catalog(*fixture())
    bounds=[boundary(a,b) for a in ("r1","r1b") for b in ("r2","r2b")]
    def oracle(history,nxt):
        return False if history[-1]=="a" and nxt=="b" else True
    result=compose_slot_domain([("L1","A_TO_B"),("L2","A_TO_B")],by,bounds,oracle,
                               alternatives_complete=True,max_compositions=10)
    assert result["status"]==LEGAL
    assert result["complete"] is True
    assert result["legal_composition_count"]==3
    assert result["illegal_composition_count"]==1


def test_unknown_transition_blocks_exact_compatible_sequence_claim():
    _,by=build_realization_catalog(*fixture())
    bounds=[boundary(a,b) for a in ("r1","r1b") for b in ("r2","r2b")]
    result=compose_slot_domain([("L1","A_TO_B"),("L2","A_TO_B")],by,bounds,
                               lambda history,nxt: None,
                               alternatives_complete=True,max_compositions=10)
    assert result["status"]==UNKNOWN
    assert result["complete"] is False
    assert result["compatible_realization_id_sequences"] is None


def test_unknown_boundary_location_blocks_legal_claim():
    catalog,by=build_realization_catalog(*fixture())
    chain=[catalog["r1"],catalog["r2"]]
    result=evaluate_realization_chain(chain,[boundary("r1","r2","UNKNOWN_BOUNDARY_LOCATION")],
                                      lambda history,nxt: True)
    assert result["status"]==UNKNOWN


def test_resource_limit_is_not_search_completeness():
    _,by=build_realization_catalog(*fixture())
    bounds=[boundary(a,b) for a in ("r1","r1b") for b in ("r2","r2b")]
    result=compose_slot_domain([("L1","A_TO_B"),("L2","A_TO_B")],by,bounds,
                               lambda history,nxt: True,
                               alternatives_complete=True,max_compositions=2)
    assert result["status"]==RESOURCE
    assert result["complete"] is False
    assert result["compatible_realization_id_sequences"] is None


def test_structural_endpoint_discontinuity_is_infeasible():
    catalog,by=build_realization_catalog(*fixture())
    bad=dict(catalog["r2"]); bad["source_stop_id"]="OTHER"
    result=evaluate_realization_chain([catalog["r1"],bad],[boundary("r1","r2")],
                                      lambda history,nxt: True)
    assert result["status"]==ILLEGAL


def test_service_semantics_never_inferred():
    catalog,_=build_realization_catalog(*fixture())
    result=evaluate_realization_chain([catalog["r1"],catalog["r2"]],[boundary("r1","r2")],
                                      lambda history,nxt: True)
    assert result["service_semantics_assigned"] is False
    assert result["vehicle_continuity_inferred"] is False
    assert result["passenger_continuity_inferred"] is False
