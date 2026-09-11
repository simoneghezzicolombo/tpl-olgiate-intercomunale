"""Controlled fixtures only: no synthetic territorial evidence."""
from dataclasses import replace
from itertools import product

import pytest

from src.phase2_rt031_typed_composition_v3 import (
    Boundary, Edge, Fragment, RestrictionDomain, StopEvent, compose, compose_domain, payload_hash,
)
from src.phase2_macro_structure_decoupling_v3 import contract_structure


def graph(spec):
    return {eid: Edge(eid, u, v, eid, 10.0, "epoch") for eid, u, v in spec}


def event(s, pos, node=None, pickup=True, dropoff=True, role="ORDINARY"):
    return StopEvent(s + str(pos), s, pos, node or s, pickup, dropoff, "attachment:" + s, role)


def frag(name, ids, events=()):
    return Fragment(name, tuple(ids), tuple(events), (True,) * len(ids),
                    (True,) * (len(ids) - 1), ("line",), "weekday", "epoch")


def domain(rules=(), complete=True):
    return RestrictionDomain("restriction-fixture", "epoch", "weekday", complete, tuple(rules))


def run(fs, edges, rules=(), boundaries=None, **kwargs):
    return compose(tuple(fs), tuple(boundaries or [Boundary(True, True, "boundary")] * (len(fs) - 1)),
                   edges, domain(rules), applicability="weekday", **kwargs)


def test_history_counterexample_and_independent_exhaustive_oracle():
    edges = graph([("x", "U", "V"), ("y", "W", "V"), ("b", "V", "J"), ("c", "J", "Z")])
    slots = ((frag("X", ["x"]), frag("Y", ["y"])), (frag("B", ["b"]),), (frag("C", ["c"]),))
    result = compose_domain(slots, (Boundary(True, True, "b"),) * 2, edges,
                            domain((("x", "b", "c"),)), applicability="weekday",
                            alternatives_complete=True, max_compositions=2)
    # Independent complete-tuple oracle: no production history/dedup helper.
    oracle = {tuple(e for f in choice for e in f.edge_ids) for choice in product(*slots)
              if tuple(e for f in choice for e in f.edge_ids) != ("x", "b", "c")}
    actual = {tuple(e["edge_id"] for e in r["payload"]["carrier"])
              for r in result["realizations"] if r["status"] == "CERTIFIED_FEASIBLE"}
    assert actual == oracle == {("y", "b", "c")}
    assert result["complete"]


def test_forbidden_internal_transition_and_oracle_full_history():
    g = graph([("a", "A", "X"), ("b", "X", "B"), ("c", "B", "C")])
    seen = []
    def oracle(history, nxt):
        seen.append((history, nxt))
        return history != ("a", "b")
    r = run([frag("f", ["a", "b", "c"])], g, transition_oracle=oracle)
    assert r["status"] == "PROVEN_INFEASIBLE"
    assert seen[-1] == (("a", "b"), "c")


def test_same_vehicle_does_not_imply_through_passengers():
    g = graph([("a", "A", "X"), ("b", "X", "B")])
    fs = [frag("a", ["a"], [event("A", 0), event("X", 1, role="COMPULSORY_ALIGHT")]),
          frag("b", ["b"], [event("X", 0), event("B", 1)])]
    through = run(fs, g)
    transfer = run(fs, g, boundaries=[Boundary(False, True, "compulsory-transfer")])
    unknown = run(fs, g, boundaries=[Boundary(None, True, "unknown")])
    assert through["candidate_sha256"] != transfer["candidate_sha256"] != unknown["candidate_sha256"]
    assert [0, 3] in through["supported_onboard_event_pairs"]
    assert [0, 3] not in transfer["supported_onboard_event_pairs"]
    assert [0, 3] not in unknown["supported_onboard_event_pairs"]
    assert not unknown["service_relations_complete"]
    macro = contract_structure("m", ["a", "b"], ["A", "X", "B"], {"a": ("A", "X"), "b": ("X", "B")})
    assert macro.macro_edge_count == 1
    assert transfer["payload"]["events"][1]["service_role"] == "COMPULSORY_ALIGHT"


def test_repeated_stop_identity_is_not_common_service_occurrence():
    g = graph([("a", "A", "S"), ("b", "S", "B"), ("c", "B", "S"), ("d", "S", "C")])
    p = frag("P", list(g), [event("S", 1), event("B", 2), event("S", 3, pickup=False, dropoff=False), event("C", 4)])
    q = replace(p, realization_id="Q", events=(event("S", 1, pickup=False, dropoff=False), event("B", 2), event("S", 3), event("C", 4)))
    r = compose_domain(((p, q),), (), g, domain(), applicability="weekday", alternatives_complete=True, max_compositions=2)
    assert r["guaranteed_stop_identities"] == ["B", "C", "S"]
    a, b = r["realizations"]
    assert [0, 1] in a["supported_onboard_event_pairs"] and [0, 1] not in b["supported_onboard_event_pairs"]
    assert [1, 2] not in a["supported_onboard_event_pairs"] and [1, 2] in b["supported_onboard_event_pairs"]
    assert r["cross_realization_event_guarantees"] is None
    assert len(a["payload"]["events"]) == 4


def test_boundary_reconciliation_requires_explicit_correspondence():
    g = graph([("a", "A", "X"), ("b", "X", "B")])
    fs = [frag("a", ["a"], [event("X", 1)]), frag("b", ["b"], [event("X", 0)])]
    separate = run(fs, g)
    joined = run(fs, g, boundaries=[Boundary(True, True, "same-visit-proof", (("X1", "X0"),))])
    assert len(separate["payload"]["events"]) == 2
    assert len(joined["payload"]["events"]) == 1
    assert len(joined["payload"]["events"][0]["sources"]) == 2
    bad = replace(fs[1], events=(event("X", 0, pickup=False),))
    with pytest.raises(ValueError, match="same service visit"):
        run([fs[0], bad], g, boundaries=[Boundary(True, True, "bad", (("X1", "X0"),))])


@pytest.mark.parametrize("mode", ["oracle", "restriction", "context", "alternatives", "limit"])
def test_unknown_and_resource_limit_prevent_exact_guarantees(mode):
    g = graph([("a", "A", "B")])
    f = frag("a", ["a"], [event("A", 0)])
    # Oracle needs a transition; duplicate directed cycle below supplies one.
    if mode == "oracle":
        g = graph([("a", "A", "B"), ("b", "B", "A")])
        f = frag("a", ["a", "b"], [event("A", 0)])
    r = compose_domain(((f, replace(f, realization_id="alt")),), (), g,
                       domain(complete=mode != "restriction"),
                       applicability="other" if mode == "context" else "weekday",
                       alternatives_complete=mode != "alternatives",
                       max_compositions=1 if mode == "limit" else 2,
                       transition_oracle=(lambda h, n: None) if mode == "oracle" else None)
    assert not r["complete"] and not r["exact_identity_guarantees"]
    assert r["guaranteed_stop_identities"] is None


def test_empty_domain_never_vacuous_guarantees():
    r = compose_domain(((),), (), {}, domain(), applicability="weekday", alternatives_complete=True, max_compositions=1)
    assert r["status"] == "PROVEN_INFEASIBLE"
    assert r["guaranteed_stop_identities"] is None


def test_filtering_changes_exact_identity_intersection():
    g = graph([("a", "A", "B"), ("b", "A", "X"), ("c", "X", "B")])
    short = frag("short", ["a"], [event("A", 0)])
    long = frag("long", ["b", "c"], [event("A", 0), event("X", 1)])
    r = compose_domain(((short, long),), (), g, domain((("a",),)), applicability="weekday", alternatives_complete=True, max_compositions=2)
    assert r["guaranteed_stop_identities"] == ["A", "X"]


def test_deadhead_and_unknown_pickup_do_not_create_passenger_rights():
    g = graph([("a", "A", "B")])
    f = frag("a", ["a"], [event("A", 0), event("B", 1)])
    assert not run([replace(f, public_segments=(False,))], g)["supported_onboard_event_pairs"]
    u = replace(f, events=(event("A", 0, pickup=None, dropoff=False), event("B", 1)))
    r = compose_domain(((u,),), (), g, domain(), applicability="weekday", alternatives_complete=True, max_compositions=1)
    assert not r["exact_identity_guarantees"]


def test_multiplicity_direction_and_start_are_identity_not_set():
    g = graph([("a", "A", "B"), ("b", "B", "A")])
    f = frag("f", ["a", "b", "a", "b"])
    r = run([f], g)
    assert r["directed_pattern_traversal_length_m"] == 40
    assert r["unique_physical_carrier_length_m"] == 20
    assert r["vehicle_run_distance_m"] is None
    assert r["candidate_sha256"] != run([replace(f, edge_ids=("b", "a", "b", "a"))], g)["candidate_sha256"]
    labelled = run([replace(f, route_labels=("line1", "line2"))], g)
    assert labelled["directed_pattern_traversal_length_m"] == 40


@pytest.mark.parametrize("bad", ["edge", "epoch", "position", "direction", "nan", "order"])
def test_invalid_carrier_or_attachment_fails_closed(bad):
    g = graph([("a", "A", "B"), ("b", "B", "C")])
    f = frag("f", ["a", "b"], [event("A", 0), event("C", 2)])
    if bad == "edge": f = replace(f, edge_ids=("missing", "b"))
    if bad == "epoch": f = replace(f, epoch="other")
    if bad == "position": f = replace(f, events=(event("elsewhere", 1),))
    if bad == "direction": f = replace(f, edge_ids=("b", "a"))
    if bad == "nan": g["a"] = replace(g["a"], length_m=float("nan"))
    if bad == "order": f = replace(f, events=tuple(reversed(f.events)))
    with pytest.raises(ValueError): run([f], g)


def test_deterministic_complete_linked_payload():
    g = graph([("a", "A", "B")])
    f = frag("f", ["a"], [event("A", 0)])
    assert run([f], g) == run([f], dict(reversed(list(g.items()))))


def test_theta_barbell_same_summaries_distinct_full_macro_incidence():
    theta = {"a": ("X", "P"), "b": ("P", "Y"), "c": ("X", "Q"),
             "d": ("Q", "Y"), "e": ("X", "R"), "f": ("R", "Y")}
    barbell = {"a": ("X", "P"), "b": ("P", "Q"), "c": ("Q", "X"),
               "d": ("X", "Y"), "e": ("Y", "R"), "f": ("R", "S"), "g": ("S", "Y")}
    def contract(edges):
        return contract_structure("controlled", tuple(edges),
                                  tuple(sorted({v for ends in edges.values() for v in ends})), edges)
    a, b = contract(theta), contract(barbell)
    assert a.branch_degree_sequence == b.branch_degree_sequence == (3, 3)
    assert a.cycle_rank == b.cycle_rank == 2
    # Theta retains three parallel macro edges; barbell retains two self loops.
    assert all(chain[0] != chain[-1] for chain in a.macro_edges)
    assert sum(chain[0] == chain[-1] for chain in b.macro_edges) == 2
    assert payload_hash(a.macro_edges) != payload_hash(b.macro_edges)


def test_long_subdivision_preserves_macro_class_and_all_service_events():
    def build(n):
        g = graph([(str(i), str(i), str(i + 1)) for i in range(n)])
        macro = contract_structure("path", tuple(g), tuple(str(i) for i in range(n + 1)),
                                   {k: (e.u, e.v) for k, e in g.items()})
        f = frag("path", tuple(g), [event(str(i), i, role="TIMING" if i == 1 else "ORDINARY") for i in range(n + 1)])
        return macro, run([f], g)
    short, _ = build(2)
    long, result = build(15)
    assert short.macro_topology_class == long.macro_topology_class == "PATH_CORE"
    assert len(result["payload"]["events"]) == 16
    assert result["payload"]["events"][1]["service_role"] == "TIMING"
    assert tuple(e["edge_id"] for e in result["payload"]["carrier"]) == tuple(str(i) for i in range(15))


def test_no_vacuous_guarantees_when_every_realization_is_forbidden():
    g = graph([("a", "A", "B")])
    f = frag("f", ["a"], [event("A", 0)])
    r = compose_domain(((f,),), (), g, domain((("a",),)), applicability="weekday", alternatives_complete=True, max_compositions=1)
    assert r["complete"] and r["status"] == "PROVEN_INFEASIBLE"
    assert r["guaranteed_stop_identities"] is None


def test_inconsistent_passenger_vehicle_continuity_rejected():
    g = graph([("a", "A", "B"), ("b", "B", "C")])
    with pytest.raises(ValueError, match="vehicle continuity"):
        run([frag("a", ["a"]), frag("b", ["b"])], g,
            boundaries=[Boundary(True, False, "different-vehicle")])
