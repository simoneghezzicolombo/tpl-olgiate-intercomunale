"""RT-031 adapter for the frozen RT-017 represented via-node turn rules.

This module can prove a movement INFEASIBLE when a frozen RT-017 via-node rule
forbids it. It does not by itself prove global route legality: RT-017 expansion
levels contain via-way restrictions outside the frozen level-0 snapshot whose
relevance to arbitrary future multi-fragment compositions has not yet been
certified. Callers must therefore keep global composition completeness UNKNOWN
until that separate proof closes.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping


SUPPORTED_PREFIXES = ("no_", "only_")


@dataclass(frozen=True)
class AdapterAudit:
    edge_count: int
    rule_count_observed: int
    active_rule_count: int
    inactive_rule_count: int
    active_rule_types: tuple[str, ...]
    represented_via_node_semantics_complete: bool
    global_transition_completeness: bool
    completeness_reason: str


class FrozenRT017ViaNodeAdapter:
    """Exact parity adapter for RT-017's frozen via-node transition semantics."""

    def __init__(self, edge_rows: Iterable[Mapping], rule_rows: Iterable[Mapping], *,
                 unresolved_external_via_way_count: int = 0):
        self.edges = {}
        for raw in edge_rows:
            row = dict(raw)
            eid = str(row.get("edge_id", ""))
            if not eid or eid in self.edges:
                raise ValueError("missing/duplicate RT-017 edge_id")
            for field in ("u_node_id", "v_node_id", "osm_way_id"):
                if str(row.get(field, "")) == "":
                    raise ValueError("RT-017 edge missing transition identity")
            self.edges[eid] = {
                "u": str(row["u_node_id"]),
                "v": str(row["v_node_id"]),
                "way": str(row["osm_way_id"]),
            }

        self.rules = defaultdict(list)
        observed = active = inactive = 0
        active_types = set()
        seen_rule_rows = set()
        represented_complete = True
        for raw in rule_rows:
            row = dict(raw)
            observed += 1
            relation_id = str(row.get("relation_id", ""))
            kind = str(row.get("restriction", ""))
            via = str(row.get("via_node_id", ""))
            from_way = str(row.get("from_osm_way_id", ""))
            to_way = str(row.get("to_osm_way_id", ""))
            in_graph = str(row.get("via_node_in_graph", "")).lower() == "true"
            key = (relation_id, kind, via, from_way, to_way, in_graph)
            if not all((relation_id, kind, via, from_way, to_way)) or key in seen_rule_rows:
                raise ValueError("invalid/duplicate RT-017 turn-rule record")
            seen_rule_rows.add(key)
            if not in_graph:
                inactive += 1
                continue
            active += 1
            active_types.add(kind)
            if not kind.startswith(SUPPORTED_PREFIXES):
                represented_complete = False
            self.rules[(via, from_way)].append({
                "restriction": kind,
                "to_way": to_way,
                "relation_id": relation_id,
            })
        for key in self.rules:
            self.rules[key].sort(key=lambda x: (x["restriction"], x["to_way"], x["relation_id"]))

        if type(unresolved_external_via_way_count) is not int or unresolved_external_via_way_count < 0:
            raise ValueError("unresolved_external_via_way_count must be a nonnegative integer")
        global_complete = represented_complete and unresolved_external_via_way_count == 0
        reason = ("COMPLETE_FOR_FROZEN_REPRESENTED_VIA_NODE_DOMAIN_ONLY"
                  if represented_complete and not global_complete else
                  "NO_UNRESOLVED_EXTERNAL_VIA_WAY_EVIDENCE" if global_complete else
                  "UNSUPPORTED_FROZEN_RULE_TYPE")
        self.audit = AdapterAudit(
            edge_count=len(self.edges),
            rule_count_observed=observed,
            active_rule_count=active,
            inactive_rule_count=inactive,
            active_rule_types=tuple(sorted(active_types)),
            represented_via_node_semantics_complete=represented_complete,
            global_transition_completeness=global_complete,
            completeness_reason=reason,
        )

    def decision(self, history: tuple[str, ...], next_edge_id: str) -> dict:
        if not history:
            raise ValueError("transition decision requires nonempty carrier history")
        if next_edge_id not in self.edges or any(e not in self.edges for e in history):
            return {"allowed": None, "status": "UNKNOWN_EDGE", "matched_rules": []}
        prior = self.edges[history[-1]]
        out = self.edges[next_edge_id]
        if prior["v"] != out["u"]:
            return {"allowed": False, "status": "DISCONNECTED_DIRECTED_CARRIER", "matched_rules": []}

        matched = []
        allowed = True
        for rule in self.rules.get((prior["v"], prior["way"]), []):
            kind, to_way = rule["restriction"], rule["to_way"]
            rejects = False
            if kind == "no_u_turn":
                rejects = out["way"] == to_way and out["v"] == prior["u"]
            elif kind == "only_u_turn":
                rejects = not (out["way"] == to_way and out["v"] == prior["u"])
            elif kind.startswith("no_"):
                rejects = out["way"] == to_way
            elif kind.startswith("only_"):
                rejects = out["way"] != to_way
            else:
                return {"allowed": None, "status": "UNKNOWN_RULE_TYPE", "matched_rules": matched}
            if rejects:
                allowed = False
                matched.append({**rule, "effect": "REJECT"})
            else:
                matched.append({**rule, "effect": "ALLOW_UNDER_THIS_RULE"})
        return {
            "allowed": allowed,
            "status": "REJECTED_BY_FROZEN_VIA_NODE_RULE" if not allowed else "NO_FROZEN_VIA_NODE_RULE_REJECTION",
            "matched_rules": matched,
        }

    def oracle(self, history: tuple[str, ...], next_edge_id: str) -> bool | None:
        """Compatible with phase2_rt031_typed_composition_v3.compose()."""
        return self.decision(history, next_edge_id)["allowed"]
