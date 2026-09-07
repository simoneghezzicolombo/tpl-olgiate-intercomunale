"""Exact bounded physical compatible-domain composition for frozen RT-023 atoms.

The caller supplies an ordered finite sequence of structural-link directions. All
certified RT-023 alternatives for each slot are traversed lazily. This layer
certifies only directed carrier continuity / restriction legality within the
provided transition oracle's scope plus certified shared boundary location.

It never infers public service, pickup/dropoff, passenger or vehicle continuity,
route identity, operated movement, timetable reachability or a network winner.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import product
from typing import Callable, Iterable, Mapping


LEGAL = "CERTIFIED_PHYSICAL_CARRIER_LEGAL_WITHIN_DECLARED_SCOPE"
ILLEGAL = "PROVEN_PHYSICAL_CARRIER_INFEASIBLE"
UNKNOWN = "UNKNOWN_PHYSICAL_CARRIER_LEGALITY"
RESOURCE = "RESOURCE_LIMIT_INCOMPLETE"


def _unique(rows: Iterable[Mapping], key: str) -> dict[str, dict]:
    out = {}
    for raw in rows:
        row = dict(raw)
        value = str(row.get(key, ""))
        if not value or value in out:
            raise ValueError(f"missing/duplicate {key}")
        out[value] = row
    return out


def build_realization_catalog(patterns, corridors, edges):
    """Validate atomic RT-023 identity and return carrier-aware realization records."""
    pmap = _unique(patterns, "realization_id")
    cmap = _unique(corridors, "corridor_id")
    emap = _unique(edges, "edge_id")
    catalog = {}
    by_slot = defaultdict(list)
    slot_endpoints = {}
    for rid, pattern in sorted(pmap.items()):
        corridor_id = str(pattern.get("corridor_id", ""))
        if corridor_id not in cmap:
            raise ValueError("realization references unknown corridor")
        corridor = cmap[corridor_id]
        edge_ids = tuple(e for e in str(corridor.get("path_edge_ids", "")).split(";") if e)
        nodes = tuple(str(corridor.get("path_node_ids", "")).split(";"))
        if not edge_ids or len(nodes) != len(edge_ids) + 1:
            raise ValueError("invalid atomic carrier dimensions")
        for i, eid in enumerate(edge_ids):
            if eid not in emap:
                raise ValueError("atomic carrier references unknown edge")
            if (str(emap[eid]["u_node_id"]), str(emap[eid]["v_node_id"])) != (nodes[i], nodes[i + 1]):
                raise ValueError("atomic carrier edge/node mismatch")
        link = str(pattern.get("structural_link_id", ""))
        direction = str(pattern.get("direction", ""))
        if not link or not direction:
            raise ValueError("missing structural slot identity")
        slot = (link, direction)
        source = str(pattern.get("source_endpoint_stop_id", ""))
        target = str(pattern.get("target_endpoint_stop_id", ""))
        if not source or not target or source == target:
            raise ValueError("invalid atomic endpoint identity")
        previous = slot_endpoints.setdefault(slot, (source, target))
        if previous != (source, target):
            raise ValueError("alternatives in one structural slot disagree on endpoints")
        ordinal = int(pattern.get("alternative_ordinal"))
        record = {
            "realization_id": rid,
            "structural_link_id": link,
            "direction": direction,
            "alternative_ordinal": ordinal,
            "source_stop_id": source,
            "target_stop_id": target,
            "edge_ids": edge_ids,
            "source_graph_node_id": nodes[0],
            "target_graph_node_id": nodes[-1],
        }
        catalog[rid] = record
        by_slot[slot].append(record)
    for slot in by_slot:
        by_slot[slot].sort(key=lambda r: (r["alternative_ordinal"], r["realization_id"]))
        ordinals = [r["alternative_ordinal"] for r in by_slot[slot]]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("duplicate alternative ordinal within structural slot")
    return catalog, dict(by_slot)


def _boundary_index(boundary_rows):
    out = {}
    for raw in boundary_rows:
        row = dict(raw)
        key = (str(row.get("left_realization_id", "")), str(row.get("right_realization_id", "")))
        if not all(key) or key in out:
            raise ValueError("invalid/duplicate boundary correspondence pair")
        out[key] = row
    return out


def evaluate_realization_chain(
    realization_chain,
    boundary_rows,
    transition_oracle: Callable[[tuple[str, ...], str], bool | None],
):
    if not realization_chain:
        raise ValueError("empty realization chain")
    boundaries = _boundary_index(boundary_rows)
    reasons = []
    unknown = False
    full_history: list[str] = []
    boundary_evidence = []

    for slot, realization in enumerate(realization_chain):
        edges = tuple(realization["edge_ids"])
        if not edges:
            raise ValueError("realization without directed carrier")
        if slot:
            left = realization_chain[slot - 1]
            if left["target_stop_id"] != realization["source_stop_id"]:
                reasons.append("STRUCTURAL_STOP_DISCONTINUITY")
            if left["target_graph_node_id"] != realization["source_graph_node_id"]:
                reasons.append("DIRECTED_CARRIER_BOUNDARY_DISCONTINUITY")
            b = boundaries.get((left["realization_id"], realization["realization_id"]))
            if b is None:
                unknown = True
                boundary_evidence.append({"status": "MISSING_BOUNDARY_CORRESPONDENCE"})
            else:
                status = str(b.get("boundary_location_status", ""))
                boundary_evidence.append({
                    "boundary_correspondence_id": b.get("boundary_correspondence_id"),
                    "boundary_location_status": status,
                })
                if status != "CERTIFIED_SAME_BOUNDARY_LOCATION":
                    unknown = True

        for eid in edges:
            if full_history:
                allowed = transition_oracle(tuple(full_history), eid)
                if allowed is False:
                    reasons.append("FORBIDDEN_OR_DISCONNECTED_TRANSITION")
                elif allowed is None:
                    unknown = True
                elif type(allowed) is not bool:
                    raise ValueError("transition oracle must return bool or None")
            full_history.append(eid)

    status = ILLEGAL if reasons else UNKNOWN if unknown else LEGAL
    return {
        "status": status,
        "realization_ids": [r["realization_id"] for r in realization_chain],
        "structural_slots": [[r["structural_link_id"], r["direction"]] for r in realization_chain],
        "directed_edge_count": len(full_history),
        "failure_reasons": sorted(set(reasons)),
        "boundary_location_evidence": boundary_evidence,
        "service_semantics_assigned": False,
        "vehicle_continuity_inferred": False,
        "passenger_continuity_inferred": False,
        "network_selected": False,
    }


def compose_slot_domain(
    ordered_slots,
    by_slot,
    boundary_rows,
    transition_oracle,
    *,
    alternatives_complete: bool,
    max_compositions: int,
):
    """Lazily exhaust the caller-declared finite slot decomposition."""
    if not ordered_slots or type(alternatives_complete) is not bool:
        raise ValueError("explicit nonempty slot decomposition/completeness required")
    if type(max_compositions) is not int or max_compositions < 1:
        raise ValueError("positive max_compositions required")
    alternatives = []
    normalized_slots = []
    for raw_slot in ordered_slots:
        if len(raw_slot) != 2:
            raise ValueError("slot must be (structural_link_id, direction)")
        slot = (str(raw_slot[0]), str(raw_slot[1]))
        if slot not in by_slot or not by_slot[slot]:
            raise ValueError("slot has no certified RT-023 alternatives")
        alternatives.append(tuple(by_slot[slot]))
        normalized_slots.append(slot)

    rows = []
    exhausted = False
    total_product = 1
    for slot in alternatives:
        total_product *= len(slot)
    for choice in product(*alternatives):
        if len(rows) == max_compositions:
            exhausted = True
            break
        rows.append(evaluate_realization_chain(choice, boundary_rows, transition_oracle))

    complete = alternatives_complete and not exhausted and len(rows) == total_product
    legal = [r for r in rows if r["status"] == LEGAL]
    illegal = [r for r in rows if r["status"] == ILLEGAL]
    unknown = [r for r in rows if r["status"] == UNKNOWN]
    if exhausted:
        status = RESOURCE
    elif not complete or unknown:
        status = UNKNOWN
    elif legal:
        status = LEGAL
    else:
        status = ILLEGAL
    return {
        "status": status,
        "complete": complete and not unknown,
        "ordered_slots": [list(s) for s in normalized_slots],
        "declared_alternative_product_size": total_product,
        "checked_compositions": len(rows),
        "legal_composition_count": len(legal),
        "illegal_composition_count": len(illegal),
        "unknown_composition_count": len(unknown),
        "compatible_realization_id_sequences": [r["realization_ids"] for r in legal] if complete and not unknown else None,
        "realizations": rows,
        "service_semantics_assigned": False,
        "territorial_search_performed": False,
        "network_selected": False,
    }
