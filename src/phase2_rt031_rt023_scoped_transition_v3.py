"""RT-031 transition oracle scoped to compositions of frozen RT-023 carriers.

This wrapper never upgrades the global RT-017 adapter. It permits a positive
legality result only when a separate certified proof establishes that unresolved
successor-envelope via-way evidence is irrelevant to the exact atomic RT-023
carrier universe, and every edge occurrence in the proposed history belongs to
that frozen universe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


SCOPE = "ONLY_COMPOSITIONS_OF_THE_288_CERTIFIED_RT023_ATOMIC_CARRIERS"


@dataclass(frozen=True)
class ScopedAudit:
    evidence_id: str
    scope: str
    atomic_carrier_edge_count: int
    represented_via_node_semantics_complete: bool
    successor_via_way_irrelevance_certified: bool
    scoped_transition_completeness: bool
    global_transition_completeness_claimed: bool = False


class RT023ScopedTransitionOracle:
    def __init__(
        self,
        adapter: FrozenRT017ViaNodeAdapter,
        atomic_carrier_edge_ids: Iterable[str],
        *,
        successor_via_way_irrelevance_certified: bool,
        evidence_id: str,
    ):
        edges = frozenset(str(v) for v in atomic_carrier_edge_ids)
        if not edges or not evidence_id:
            raise ValueError("scoped transition proof requires edge universe and evidence identity")
        if not edges <= set(adapter.edges):
            raise ValueError("scoped carrier universe contains edge outside RT-017 adapter")
        if type(successor_via_way_irrelevance_certified) is not bool:
            raise ValueError("successor via-way irrelevance must be explicit boolean")
        self.adapter = adapter
        self.atomic_carrier_edge_ids = edges
        self.audit = ScopedAudit(
            evidence_id=evidence_id,
            scope=SCOPE,
            atomic_carrier_edge_count=len(edges),
            represented_via_node_semantics_complete=adapter.audit.represented_via_node_semantics_complete,
            successor_via_way_irrelevance_certified=successor_via_way_irrelevance_certified,
            scoped_transition_completeness=(
                adapter.audit.represented_via_node_semantics_complete
                and successor_via_way_irrelevance_certified
            ),
        )

    def decision(self, history: tuple[str, ...], next_edge_id: str) -> dict:
        if not history:
            raise ValueError("scoped transition decision requires nonempty history")
        decision = self.adapter.decision(history, next_edge_id)
        if decision["allowed"] is False:
            return {**decision, "scope_status": "PROVEN_INFEASIBLE"}
        used = set(history) | {str(next_edge_id)}
        if not used <= self.atomic_carrier_edge_ids:
            return {
                "allowed": None,
                "status": "OUTSIDE_CERTIFIED_RT023_CARRIER_SCOPE",
                "matched_rules": decision.get("matched_rules", []),
                "scope_status": "UNKNOWN_EVIDENCE",
            }
        if decision["allowed"] is None:
            return {**decision, "scope_status": "UNKNOWN_EVIDENCE"}
        if not self.audit.scoped_transition_completeness:
            return {
                **decision,
                "allowed": None,
                "status": "RT023_SCOPED_RESTRICTION_COMPLETENESS_NOT_CERTIFIED",
                "scope_status": "UNKNOWN_EVIDENCE",
            }
        return {
            **decision,
            "allowed": True,
            "status": "CERTIFIED_LEGAL_WITHIN_FROZEN_RT023_COMPOSED_DOMAIN",
            "scope_status": "CERTIFIED_FEASIBLE",
        }

    def oracle(self, history: tuple[str, ...], next_edge_id: str) -> bool | None:
        return self.decision(history, next_edge_id)["allowed"]
