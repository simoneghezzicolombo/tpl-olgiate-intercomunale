"""Bounded service/network examples, not territorial service assignments."""
from dataclasses import replace

import pytest

from src.phase2_rt031_service_network_v3 import (
    MacroEdge, ServiceEvent, ServiceComponent, PublicPattern, Movement, build_service_network,
)
from src.phase2_rt031_typed_composition_v3 import payload_hash
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import LEGAL, UNKNOWN, ILLEGAL


def inputs():
    bound, catalog = {}, {}
    for rid, u, v in (("a", "A", "X"), ("b", "X", "B"), ("c", "B", "X"), ("d", "X", "A")):
        edge = dict(edge_id=rid, u_node_id=u, v_node_id=v, length_m="10")
        visits = [{"binding": {"position": str(i)}, "source_occurrence": {"stop_sequence": str(i + 1),
                   "stop_place_id": stop}, "availability_only": True} for i, stop in enumerate((u, v))]
        payload = {"graph_epoch": "FIXTURE", "carrier": [{"ordinal": 0, "source_edge": edge}], "visits": visits,
                   "source_pattern": dict(realization_id=rid, source_endpoint_stop_id=u, target_endpoint_stop_id=v,
                                          structural_link_id=rid, direction="explicit")}
        bound[rid] = {"payload": payload, "sha256": payload_hash(payload)}
        catalog[rid] = dict(realization_id=rid, source_stop_id=u, target_stop_id=v,
                            source_graph_node_id=u, target_graph_node_id=v, edge_ids=(rid,),
                            structural_link_id=rid, direction="explicit")
    boundaries = [dict(left_realization_id=a, right_realization_id=b, boundary_correspondence_id=a+b,
                       boundary_location_status="CERTIFIED_SAME_BOUNDARY_LOCATION")
                  for a in catalog for b in catalog if catalog[a]["target_stop_id"] == catalog[b]["source_stop_id"]]
    return dict(bound=bound, catalog=catalog, boundary_rows=boundaries, transition_oracle=lambda h, e: True,
                evidence_scope_id="CONTROLLED_FIXTURE", applicability="school-day")


def event(eid, slot, seq, through=True, kind="ORDINARY"):
    return ServiceEvent(eid, slot, seq, kind, True, True, through, True, "CONTROLLED_SERVICE_DECLARATION")


def model():
    macro = MacroEdge("path", "A", "B", ("a", "b"))
    comp = ServiceComponent("component", ("path",),
                            (event("A", 0, 1), event("X", 0, 2), event("B", 1, 2)),
                            (True, True), "school-day")
    pattern = PublicPattern("line", "component", ("A", "X", "B"), "school-day", "fixture")
    return (macro,), (comp,), (pattern,), ()


def build(model_args=None, **kwargs):
    data = inputs(); data.update(kwargs)
    return build_service_network(*(model_args or model()), **data)


def test_through_transfer_and_unknown_are_distinct_and_match_event_oracle():
    m, cs, ps, moves = model()
    hashes = set()
    for through in (True, False, None):
        events = (cs[0].events[0], replace(cs[0].events[1], passenger_through=through), cs[0].events[2])
        r = build((m, (replace(cs[0], events=events),), ps, moves))
        hashes.add(r["network_sha256"])
        # Independent occurrence-index reachability oracle for this finite public carrier.
        expected = [[events[i].event_id, events[j].event_id] for i in range(3) for j in range(i + 1, 3)
                    if all(events[k].passenger_through is True for k in range(i + 1, j))]
        assert r["payload"]["components"]["component"]["supported_onboard_event_pairs"] == expected
        assert r["physical_composition_status"] == LEGAL
        assert r["service_relations_complete"] == (through is not None)
    assert len(hashes) == 3


def test_two_labels_one_movement_vs_two_operated_movements():
    m, cs, ps, _ = model()
    labels = ps + (replace(ps[0], pattern_id="second-label"),)
    one = Movement("movement1", "component", 1, "school-day", "fixture-assignment")
    r1 = build((m, cs, labels, (one,)))
    r2 = build((m, cs, labels, (one, replace(one, movement_id="movement2"))))
    assert r1["declared_movement_traversal_distance_m"] == "20"
    assert r2["declared_movement_traversal_distance_m"] == "40"
    assert r1["network_sha256"] != r2["network_sha256"]
    assert r1["annual_bus_km"] is None
    assert build((m, cs, labels, (replace(one, multiplicity=None),)))["declared_movement_traversal_distance_m"] is None
    assert build()["movement_assignment_complete"] is False


@pytest.mark.parametrize("oracle,expected", [(None, UNKNOWN), (False, ILLEGAL)])
def test_road_unknown_or_illegal_never_gets_service_journeys(oracle, expected):
    r = build(transition_oracle=lambda h, e: oracle)
    assert r["physical_composition_status"] == expected
    assert not r["service_relations_complete"]
    assert r["payload"]["components"]["component"]["supported_onboard_event_pairs"] == []


def test_missing_operating_context_does_not_mix_variants():
    r = build(applicability=None)
    assert not r["service_relations_complete"]
    assert r["payload"]["components"]["component"]["supported_onboard_event_pairs"] == []
    assert r["cross_component_transfers"] is None


def test_deadhead_breaks_passenger_path_without_changing_physical_carrier():
    m, cs, ps, moves = model()
    r = build((m, (replace(cs[0], public_atoms=(True, False)),), ps, moves))
    assert r["physical_composition_status"] == LEGAL
    assert r["payload"]["components"]["component"]["supported_onboard_event_pairs"] == [["A", "X"]]


def test_distinct_boundary_arrival_departure_events_not_automatically_merged():
    m, cs, _, moves = model()
    evs = (event("A", 0, 1), event("arriveX", 0, 2, False, "COMPULSORY_ALIGHT"),
           event("departX", 1, 1), event("B", 1, 2))
    r = build((m, (replace(cs[0], events=evs),), (), moves))
    component = r["payload"]["components"]["component"]
    assert len(component["events"]) == 4
    assert ["A", "B"] not in component["supported_onboard_event_pairs"]
    assert ["departX", "B"] in component["supported_onboard_event_pairs"]


def test_repeated_carrier_visits_and_self_loop_incidence_preserved():
    m = (MacroEdge("loop", "A", "A", ("a", "b", "c", "d")),)
    evs = (event("start", 0, 1), event("X1", 0, 2), event("B", 1, 2), event("X2", 2, 2), event("end", 3, 2))
    comp = ServiceComponent("loop-service", ("loop",), evs, (True,) * 4, "school-day")
    r = build((m, (comp,), (), ()))
    assert r["payload"]["macro_incidence"][0]["source_stop"] == r["payload"]["macro_incidence"][0]["target_stop"]
    assert len(r["payload"]["components"]["loop-service"]["events"]) == 5
    assert len(r["payload"]["components"]["loop-service"]["location_expansion"]["payload"]["visits"]) == 8


def test_parallel_macro_edges_keep_full_incidence_and_assignment_identity():
    m, cs, ps, moves = model()
    parallel = m + (replace(m[0], edge_id="parallel"),)
    comps = cs + (replace(cs[0], component_id="parallel-component", macro_edge_ids=("parallel",)),)
    r = build((parallel, comps, ps, moves))
    assert len(r["payload"]["macro_incidence"]) == 2
    assert r["network_sha256"] != build()["network_sha256"]
    assert r == build((tuple(reversed(parallel)), tuple(reversed(comps)), ps, moves))


@pytest.mark.parametrize("field", ["pickup", "dropoff", "passenger_through", "event_kind", "evidence_id"])
def test_service_field_mutations_change_whole_network_identity(field):
    m, cs, ps, moves = model()
    value = False if field in ("pickup", "dropoff", "passenger_through") else "changed"
    evs = (cs[0].events[0], replace(cs[0].events[1], **{field: value}), cs[0].events[2])
    assert build((m, (replace(cs[0], events=evs),), ps, moves))["network_sha256"] != build()["network_sha256"]


@pytest.mark.parametrize("bad", ["incidence", "unused", "source_visit", "vehicle", "alight", "order", "pattern_context", "multiplicity", "binding"])
def test_contract_violations_fail_closed(bad):
    m, cs, ps, moves = model(); data = inputs()
    if bad == "incidence": m = (replace(m[0], target_stop="OTHER"),)
    if bad == "unused": m += (replace(m[0], edge_id="unused"),)
    if bad == "source_visit": cs = (replace(cs[0], events=(replace(cs[0].events[0], atom_slot=99),)),)
    if bad == "vehicle": cs = (replace(cs[0], events=(replace(cs[0].events[0], vehicle_through=False),)),)
    if bad == "alight": cs = (replace(cs[0], events=(replace(cs[0].events[0], event_kind="COMPULSORY_ALIGHT"),)),)
    if bad == "order": cs = (replace(cs[0], events=tuple(reversed(cs[0].events))),)
    if bad == "pattern_context": ps = (replace(ps[0], applicability="holiday"),)
    if bad == "multiplicity": moves = (Movement("m", "component", True, "school-day", "fixture"),)
    if bad == "binding": data["bound"]["a"]["payload"]["graph_epoch"] = "changed"
    with pytest.raises(ValueError): build_service_network(m, cs, ps, moves, **data)


def test_catalog_cannot_relabel_certified_source_stop_identity():
    data = inputs(); data["catalog"]["a"]["source_stop_id"] = "invented"
    m, cs, ps, moves = model()
    with pytest.raises(ValueError, match="source identity"):
        build_service_network((replace(m[0], source_stop="invented"),), cs, ps, moves, **data)
