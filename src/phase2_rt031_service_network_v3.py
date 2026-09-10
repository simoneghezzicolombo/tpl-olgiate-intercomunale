"""Explicit linked service-network contract on finite physical compositions.

Bounded representation gate only. No service policy, operational assignment,
territorial candidate, transfer, timetable or equivalence class is inferred.
"""
from dataclasses import asdict, dataclass
from decimal import Decimal

from src.phase2_rt031_occurrence_binding_v3 import concatenate_available, decimal
from src.phase2_rt031_rt023_physical_compatible_domain_v3 import (
    evaluate_realization_chain, LEGAL, ILLEGAL, UNKNOWN,
)
from src.phase2_rt031_typed_composition_v3 import payload_hash


@dataclass(frozen=True)
class MacroEdge:
    edge_id: str
    source_stop: str
    target_stop: str
    realization_ids: tuple[str, ...]


@dataclass(frozen=True)
class ServiceEvent:
    event_id: str
    atom_slot: int
    source_stop_sequence: int
    event_kind: str
    pickup: bool | None
    dropoff: bool | None
    passenger_through: bool | None
    vehicle_through: bool | None
    evidence_id: str


@dataclass(frozen=True)
class ServiceComponent:
    component_id: str
    macro_edge_ids: tuple[str, ...]
    events: tuple[ServiceEvent, ...]
    public_atoms: tuple[bool | None, ...]
    applicability: str | None


@dataclass(frozen=True)
class PublicPattern:
    pattern_id: str
    component_id: str
    event_ids: tuple[str, ...]
    applicability: str | None
    evidence_id: str


@dataclass(frozen=True)
class Movement:
    movement_id: str
    component_id: str
    multiplicity: int | None
    applicability: str | None
    evidence_id: str


def _index(records, field):
    result = {}
    for row in records:
        key = getattr(row, field)
        if not key or key in result:
            raise ValueError("missing/duplicate " + field)
        result[key] = row
    return result


def build_service_network(macro_edges, components, patterns, movements, *,
                          bound, catalog, boundary_rows, transition_oracle,
                          evidence_scope_id: str, applicability: str | None):
    """Bind full directed incidence, carriers, events, labels and movements.

Input order of keyed records is irrelevant; order INSIDE every chain/pattern is
preserved. Parallel edges, self-loops and repeated traversals are not deduped.
Positive road status never becomes a positive service or search certificate.
"""
    if not evidence_scope_id:
        raise ValueError("physical evidence scope must be identified")
    contexts = [applicability] + [c.applicability for c in components]
    if any(c is not None and (not isinstance(c, str) or not c.strip()) for c in contexts):
        raise ValueError("applicability must be a nonempty context identity or None")
    macros = _index(macro_edges, "edge_id")
    comps = _index(components, "component_id")
    pats = _index(patterns, "pattern_id")
    moves = _index(movements, "movement_id")
    if not macros or not comps:
        raise ValueError("explicit nonempty macro graph and service components required")
    for edge in macros.values():
        if not edge.realization_ids:
            raise ValueError("empty macro expansion")
        chain = [catalog[r] for r in edge.realization_ids]
        if (edge.source_stop, edge.target_stop) != (chain[0]["source_stop_id"], chain[-1]["target_stop_id"]):
            raise ValueError("macro incidence does not match directed expansion")
        for left, right in zip(chain, chain[1:]):
            if left["target_stop_id"] != right["source_stop_id"]:
                raise ValueError("macro expansion discontinuity")
    used_macros, realized = set(), {}
    for cid, comp in sorted(comps.items()):
        if not comp.macro_edge_ids:
            raise ValueError("empty component expansion")
        chain_macros = [macros[e] for e in comp.macro_edge_ids]
        used_macros.update(comp.macro_edge_ids)
        for left, right in zip(chain_macros, chain_macros[1:]):
            if left.target_stop != right.source_stop:
                raise ValueError("component macro incidence discontinuity")
        rids = tuple(r for edge in chain_macros for r in edge.realization_ids)
        if len(comp.public_atoms) != len(rids):
            raise ValueError("one explicit public state per atom required")
        if any(x is not None and type(x) is not bool for x in comp.public_atoms):
            raise ValueError("public states must be boolean or None")
        for rid in rids:
            item = bound[rid]
            if item["sha256"] != payload_hash(item["payload"]):
                raise ValueError("mutated binding payload")
            carrier = tuple(e["source_edge"]["edge_id"] for e in item["payload"]["carrier"])
            if carrier != tuple(catalog[rid]["edge_ids"]):
                raise ValueError("catalog/binding carrier mismatch")
            pattern = item["payload"]["source_pattern"]
            for source, target in (("realization_id", "realization_id"),
                                   ("source_endpoint_stop_id", "source_stop_id"),
                                   ("target_endpoint_stop_id", "target_stop_id"),
                                   ("structural_link_id", "structural_link_id"), ("direction", "direction")):
                if pattern[source] != catalog[rid][target]:
                    raise ValueError("catalog/binding source identity mismatch")
            source_carrier = item["payload"]["carrier"]
            if (catalog[rid]["source_graph_node_id"], catalog[rid]["target_graph_node_id"]) != (
                    source_carrier[0]["source_edge"]["u_node_id"], source_carrier[-1]["source_edge"]["v_node_id"]):
                raise ValueError("catalog/binding graph endpoint mismatch")
        location = concatenate_available(bound, rids)
        physical = evaluate_realization_chain([catalog[r] for r in rids], boundary_rows, transition_oracle)
        source_visits = {}
        for visit in location["payload"]["visits"]:
            seq = int(decimal(visit["source_visit"]["source_occurrence"]["stop_sequence"]))
            key = (visit["slot"], seq)
            if key in source_visits:
                raise ValueError("duplicate bound source visit")
            source_visits[key] = visit
        _index(comp.events, "event_id")
        event_rows, previous = [], Decimal(-1)
        for event in comp.events:
            if type(event.atom_slot) is not int or type(event.source_stop_sequence) is not int:
                raise ValueError("event source ordinal must be integer")
            key = (event.atom_slot, event.source_stop_sequence)
            if key not in source_visits or not event.evidence_id or not event.event_kind:
                raise ValueError("event requires exact source visit and service evidence")
            if any(x is not None and type(x) is not bool for x in
                   (event.pickup, event.dropoff, event.passenger_through, event.vehicle_through)):
                raise ValueError("event semantics must be boolean or None")
            if event.passenger_through is True and event.vehicle_through is not True:
                raise ValueError("onboard through requires vehicle continuity")
            if event.event_kind == "COMPULSORY_ALIGHT" and event.passenger_through is not False:
                raise ValueError("compulsory alight cannot imply through-service")
            visit = source_visits[key]
            position = decimal(visit["composed_position"])
            if position < previous:
                raise ValueError("service event order reverses carrier")
            previous = position
            event_rows.append({"event": asdict(event), "source_visit": visit})
        spans, offset = [], 0
        for rid, public in zip(rids, comp.public_atoms):
            count = len(catalog[rid]["edge_ids"])
            spans.append((offset, offset + count, public))
            offset += count
        context_known = applicability is not None and comp.applicability == applicability
        service_defined = (context_known and bool(event_rows)
                            and all(p is not None for p in comp.public_atoms)
                            and all(x is not None for e in comp.events for x in
                                    (e.pickup, e.dropoff, e.passenger_through, e.vehicle_through)))
        onboard = []
        if physical["status"] == LEGAL and context_known:
            for i, start in enumerate(comp.events):
                for j in range(i + 1, len(comp.events)):
                    finish = comp.events[j]
                    p = decimal(event_rows[i]["source_visit"]["composed_position"])
                    q = decimal(event_rows[j]["source_visit"]["composed_position"])
                    if (p < q and start.pickup is True and finish.dropoff is True
                            and all(e.passenger_through is True for e in comp.events[i + 1:j])
                            and all(public is True for a, b, public in spans if a < q and b > p)):
                        onboard.append([start.event_id, finish.event_id])
        realized[cid] = {"component": asdict(comp), "location_expansion": location,
                         "physical_status": physical["status"], "physical_evidence": physical,
                         "events": event_rows, "supported_onboard_event_pairs": onboard,
                         "service_definition_complete": service_defined,
                         "service_relations_complete": service_defined and physical["status"] == LEGAL,
                         "traversal_length_m": str(sum(decimal(e["source_edge"]["length_m"])
                                                        for e in location["payload"]["carrier"]))}
    if used_macros != set(macros):
        raise ValueError("macro graph has unbound service incidence")
    for pat in pats.values():
        if pat.component_id not in comps or not pat.evidence_id or not pat.event_ids:
            raise ValueError("pattern requires component/events/evidence")
        event_ids = [e.event_id for e in comps[pat.component_id].events]
        if len(pat.event_ids) != len(set(pat.event_ids)) or any(e not in event_ids for e in pat.event_ids):
            raise ValueError("invalid pattern event reference")
        indexes = [event_ids.index(e) for e in pat.event_ids]
        if indexes != sorted(indexes):
            raise ValueError("pattern reverses service events")
        if pat.applicability != comps[pat.component_id].applicability:
            raise ValueError("pattern applicability differs from component")
    movement_distance = Decimal(0)
    movement_complete = bool(moves) and applicability is not None
    assigned = set()
    for move in moves.values():
        if move.component_id not in comps or not move.evidence_id:
            raise ValueError("movement requires component and evidence")
        if move.multiplicity is not None and (type(move.multiplicity) is not int or move.multiplicity < 1):
            raise ValueError("movement multiplicity must be a positive integer or None")
        assigned.add(move.component_id)
        comp = realized[move.component_id]
        known = (move.multiplicity is not None and move.applicability == applicability
                 and comps[move.component_id].applicability == applicability
                 and all(e.vehicle_through is True for e in comps[move.component_id].events[1:-1])
                 and comp["physical_status"] == LEGAL)
        movement_complete &= known
        if known:
            movement_distance += decimal(comp["traversal_length_m"]) * move.multiplicity
    movement_complete &= assigned == set(comps)
    statuses = [r["physical_status"] for r in realized.values()]
    status = ILLEGAL if ILLEGAL in statuses else UNKNOWN if UNKNOWN in statuses else LEGAL
    payload = {"macro_incidence": [asdict(macros[k]) for k in sorted(macros)],
               "components": realized, "patterns": [asdict(pats[k]) for k in sorted(pats)],
               "movements": [asdict(moves[k]) for k in sorted(moves)],
               "applicability": applicability, "physical_evidence_scope_id": evidence_scope_id}
    return {"network_sha256": payload_hash(payload), "payload": payload,
            "physical_composition_status": status,
            "service_relations_complete": all(r["service_relations_complete"] for r in realized.values()),
            "movement_assignment_complete": bool(movement_complete),
            "declared_movement_traversal_distance_m": str(movement_distance) if movement_complete else None,
            "annual_bus_km": None, "cross_component_transfers": None,
            "production_rt031_pass": False, "network_selected": False}
