from src.phase2_territorial_commuting_addressability_v2 import (
    ODRelation,
    canonical_place,
    directed_edges,
    evaluate_scenario,
)


def rel(origin: str, destination: str, workers: int, category: str = "OTHER_CORE") -> ODRelation:
    return ODRelation(
        origin_name=origin,
        destination_name=destination,
        origin_key=canonical_place(origin),
        destination_key=canonical_place(destination),
        workers=workers,
        category=category,
    )


def test_repeated_anchor_is_valid_and_direction_is_respected():
    anchors = {
        "H": frozenset({canonical_place("Olgiate Molgora")}),
        "B": frozenset({canonical_place("Brivio")}),
        "C": frozenset({canonical_place("Calco")}),
    }
    result = evaluate_scenario(
        public_route_anchor_sequences=[("H", "C", "B", "C")],
        anchor_municipalities=anchors,
        relations=(
            rel("Olgiate Molgora", "Brivio", 10),
            rel("Brivio", "Olgiate Molgora", 20),
        ),
    )
    assert result.addressable_relation_count == 1
    assert result.addressable_worker_mass == 10


def test_same_anchor_transfer_across_public_routes_is_allowed():
    anchors = {
        "A": frozenset({canonical_place("Brivio")}),
        "X": frozenset({canonical_place("Calco")}),
        "B": frozenset({canonical_place("Merate")}),
    }
    result = evaluate_scenario(
        public_route_anchor_sequences=[("A", "X"), ("X", "B")],
        anchor_municipalities=anchors,
        relations=(rel("Brivio", "Merate", 105, "OTHER_EXTERNAL"),),
    )
    assert result.addressable_worker_mass == 105
    assert result.other_external_addressable_worker_mass == 105


def test_technical_return_cannot_enter_interface_implicitly():
    anchors = {
        "H": frozenset({canonical_place("Olgiate Molgora")}),
        "B": frozenset({canonical_place("Brivio")}),
    }
    # Public service H->B only. A vehicle-only B->H closure is deliberately not
    # supplied to evaluate_scenario, so B->H must remain unsupported.
    result = evaluate_scenario(
        public_route_anchor_sequences=[("H", "B")],
        anchor_municipalities=anchors,
        relations=(rel("Brivio", "Olgiate Molgora", 62),),
    )
    assert result.addressable_worker_mass == 0


def test_unknown_route_anchor_fails_closed():
    anchors = {"A": frozenset({canonical_place("Brivio")})}
    try:
        evaluate_scenario(
            public_route_anchor_sequences=[("A", "UNKNOWN")],
            anchor_municipalities=anchors,
            relations=(rel("Brivio", "Calco", 1),),
        )
    except ValueError as exc:
        assert "unknown routing anchors" in str(exc)
    else:
        raise AssertionError("unknown routing anchor did not fail closed")


def test_directed_edges_preserve_loop_repetition():
    assert directed_edges(("H", "A", "H", "B")) == {("H", "A"), ("A", "H"), ("H", "B")}
