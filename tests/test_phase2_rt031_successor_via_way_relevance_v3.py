from src.phase2_rt031_successor_via_way_relevance_v3 import (
    extract_bus_applicable_via_way_relations, audit_rt023_carrier_relevance)


def rel(i, restriction="no_left_turn", via="20", exc=None):
    tags={"type":"restriction","restriction":restriction}
    if exc is not None: tags["except"]=exc
    return {"type":"relation","id":i,"tags":tags,"members":[
        {"type":"way","role":"from","ref":10},
        {"type":"way","role":"via","ref":int(via)},
        {"type":"way","role":"to","ref":30},
    ]}


def test_extracts_bus_applicable_via_way():
    rows=extract_bus_applicable_via_way_relations([rel(1)])
    assert rows[0]["via_way_ids"] == ("20",)


def test_bus_exempt_is_not_bus_applicable():
    assert extract_bus_applicable_via_way_relations([rel(1, exc="bus")]) == []


def test_absent_via_way_proves_irrelevance_to_carrier_universe():
    result=audit_rt023_carrier_relevance(extract_bus_applicable_via_way_relations([rel(1)]), {"10","30","99"})
    assert result["all_successor_via_way_irrelevant_to_rt023_composed_domain"] is True


def test_via_way_overlap_keeps_relevance_open():
    result=audit_rt023_carrier_relevance(extract_bus_applicable_via_way_relations([rel(1)]), {"20"})
    assert result["all_successor_via_way_irrelevant_to_rt023_composed_domain"] is False
    assert result["relations"][0]["relevant_to_any_rt023_composition"] is True
