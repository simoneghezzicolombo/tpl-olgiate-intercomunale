"""Deterministic controlled RT-031 counterexample replay; no territorial data."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from src.phase2_rt031_typed_composition_v3 import (
    Boundary, Edge, Fragment, RestrictionDomain, StopEvent, compose,
)


def audit():
    edges = {e: Edge(e, u, v, e, 10.0, "fixture") for e, u, v in
             [("x", "U", "V"), ("y", "W", "V"), ("b", "V", "J"), ("c", "J", "Z")]}
    restriction = RestrictionDomain("CONTROLLED_FIXTURE", "fixture", "declared", True, (("x", "b", "c"),))
    def path(first):
        return Fragment(first, (first, "b", "c"), (), (True,) * 3, (True,) * 2, (), "declared", "fixture")
    blocked = compose((path("x"),), (), edges, restriction, applicability="declared")
    allowed = compose((path("y"),), (), edges, restriction, applicability="declared")
    assert blocked["status"] == "PROVEN_INFEASIBLE"
    assert allowed["status"] == "CERTIFIED_FEASIBLE"
    e = {k: Edge(k, u, v, k, 10.0, "fixture") for k, u, v in [("a", "A", "X"), ("b", "X", "B")]}
    def stop(s, p):
        return StopEvent(s, s, p, s, True, True, "fixture-attachment", "ORDINARY")
    a = Fragment("a", ("a",), (stop("A", 0),), (True,), (), (), "declared", "fixture")
    b = Fragment("b", ("b",), (stop("B", 1),), (True,), (), (), "declared", "fixture")
    rules = replace(restriction, forbidden_sequences=())
    through = compose((a, b), (Boundary(True, True, "fixture-through"),), e, rules, applicability="declared")
    transfer = compose((a, b), (Boundary(False, True, "fixture-transfer"),), e, rules, applicability="declared")
    assert through["supported_onboard_event_pairs"] == [[0, 1]]
    assert transfer["supported_onboard_event_pairs"] == []
    return {"status": "PASS_BOUNDED_TYPED_COMPOSITION_REPLAY_ONLY", "epistemic_status": "DERIVED",
            "input_kind": "CONTROLLED_TEST_FIXTURE", "forbidden_history": blocked["status"],
            "positive_history_control": allowed["status"],
            "through_payload_sha256": through["candidate_sha256"],
            "transfer_payload_sha256": transfer["candidate_sha256"],
            "production_certified": False, "territorial_search_performed": False,
            "primary_selection_authorised": False, "runner_up_selection_authorised": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(audit(), indent=2, sort_keys=True) + "\n")
