"""Bounded relevance audit for successor-envelope OSM via-way restrictions."""
from __future__ import annotations

BUS_EXCEPTIONS = {"bus", "psv", "public_service_vehicle"}


def split_except(value) -> set[str]:
    text = str(value or "").lower().replace(",", ";")
    return {part.strip() for part in text.split(";") if part.strip()}


def extract_bus_applicable_via_way_relations(elements):
    rows = []
    seen = set()
    for raw in elements:
        if raw.get("type") != "relation":
            continue
        tags = dict(raw.get("tags") or {})
        if tags.get("type") != "restriction":
            continue
        restriction = str(tags.get("restriction") or "").strip().lower()
        if not restriction or not (restriction.startswith("no_") or restriction.startswith("only_")):
            continue
        if split_except(tags.get("except")) & BUS_EXCEPTIONS:
            continue
        via_way_ids = tuple(str(m.get("ref")) for m in raw.get("members", [])
                            if m.get("role") == "via" and m.get("type") == "way")
        if not via_way_ids:
            continue
        relation_id = str(raw.get("id", ""))
        if not relation_id or relation_id in seen:
            raise ValueError("missing/duplicate via-way relation id")
        seen.add(relation_id)
        from_way_ids = tuple(str(m.get("ref")) for m in raw.get("members", [])
                             if m.get("role") == "from" and m.get("type") == "way")
        to_way_ids = tuple(str(m.get("ref")) for m in raw.get("members", [])
                           if m.get("role") == "to" and m.get("type") == "way")
        rows.append({
            "relation_id": relation_id,
            "restriction": restriction,
            "from_way_ids": from_way_ids,
            "via_way_ids": via_way_ids,
            "to_way_ids": to_way_ids,
        })
    return sorted(rows, key=lambda r: r["relation_id"])


def audit_rt023_carrier_relevance(relations, carrier_way_ids):
    carrier = {str(v) for v in carrier_way_ids}
    if not carrier:
        raise ValueError("empty RT023 carrier way universe")
    rows = []
    for rel in relations:
        via_overlap = sorted(set(rel["via_way_ids"]) & carrier)
        rows.append({
            **rel,
            "via_way_overlap_with_rt023": tuple(via_overlap),
            "relevant_to_any_rt023_composition": bool(via_overlap),
        })
    complete = bool(rows) and not any(r["relevant_to_any_rt023_composition"] for r in rows)
    return {
        "relations": rows,
        "all_successor_via_way_irrelevant_to_rt023_composed_domain": complete,
        "proof_semantics": "A_VIA_WAY_RESTRICTION_CANNOT_APPLY_IF_NONE_OF_ITS_VIA_WAYS_OCCUR_IN_ANY_ATOMIC_RT023_CARRIER",
    }
