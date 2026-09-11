from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter
from src.phase2_rt031_rt023_scoped_transition_v3 import RT023ScopedTransitionOracle, SCOPE


def edge(e,u,v,w):
    return {"edge_id":e,"u_node_id":u,"v_node_id":v,"osm_way_id":w}


def rule(r,k,via,fw,tw):
    return {"relation_id":r,"restriction":k,"via_node_id":via,"from_osm_way_id":fw,
            "to_osm_way_id":tw,"via_node_in_graph":"true"}


def adapter_incomplete():
    return FrozenRT017ViaNodeAdapter(
        [edge("a","A","X","1"),edge("b","X","B","2"),edge("c","X","C","3")],
        [rule("r","no_left_turn","X","1","2")], unresolved_external_via_way_count=2)


def test_scoped_proof_can_certify_nonrejected_rt023_transition_without_global_claim():
    a=adapter_incomplete()
    s=RT023ScopedTransitionOracle(a,{"a","b","c"},
        successor_via_way_irrelevance_certified=True,evidence_id="proof")
    assert a.audit.global_transition_completeness is False
    assert s.audit.scope == SCOPE
    assert s.audit.global_transition_completeness_claimed is False
    assert s.oracle(("a",),"c") is True


def test_known_frozen_rejection_remains_false_under_scoped_proof():
    s=RT023ScopedTransitionOracle(adapter_incomplete(),{"a","b","c"},
        successor_via_way_irrelevance_certified=True,evidence_id="proof")
    assert s.oracle(("a",),"b") is False


def test_without_successor_irrelevance_proof_nonrejection_remains_unknown():
    s=RT023ScopedTransitionOracle(adapter_incomplete(),{"a","b","c"},
        successor_via_way_irrelevance_certified=False,evidence_id="open")
    assert s.oracle(("a",),"c") is None


def test_outside_atomic_carrier_universe_is_unknown_even_with_proof():
    s=RT023ScopedTransitionOracle(adapter_incomplete(),{"a","c"},
        successor_via_way_irrelevance_certified=True,evidence_id="proof")
    assert s.oracle(("a",),"b") is False  # represented rule proves rejection first
    other=FrozenRT017ViaNodeAdapter(
        [edge("a","A","X","1"),edge("c","X","C","3"),edge("d","X","D","4")],[],
        unresolved_external_via_way_count=2)
    s2=RT023ScopedTransitionOracle(other,{"a","c"},
        successor_via_way_irrelevance_certified=True,evidence_id="proof")
    assert s2.oracle(("a",),"d") is None


def test_scoped_universe_must_be_subset_of_adapter_edges():
    import pytest
    with pytest.raises(ValueError, match="outside RT-017"):
        RT023ScopedTransitionOracle(adapter_incomplete(),{"a","missing"},
            successor_via_way_irrelevance_certified=True,evidence_id="proof")
