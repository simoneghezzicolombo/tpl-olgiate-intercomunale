from scripts.phase2_build_zero_band_tiebreak_v2 import (
    best_achievable_worst_route_gap,
    profile_key,
    select_group,
)


VALIDATION = {
    "passenger_maximise_axes_within_service_context": ["coverage"],
    "passenger_minimise_axes_within_service_context": ["gjt"],
    "global_additional_availability_maximise_axes": ["annual_service_days", "span_minutes"],
}


def row(plan, *, coverage=0.5, gjt=30.0, days=260, span=960, s8="ALL_PUBLIC_ROUTES_HAVE_SOME_COMPLETE_MATCH_PHASE", share=1.0, gap=8.0, routes=2, km=100000.0, field=1):
    return {
        "plan_id": plan,
        "scenario_id": plan,
        "coverage": str(coverage),
        "gjt": "" if gjt is None else str(gjt),
        "annual_service_days": str(days),
        "span_minutes": str(span),
        "s8_opportunity_class": s8,
        "s8_public_complete_match_route_share": str(share),
        "s8_roundtrip_route_count": "1",
        "s8_roundtrip_best_complete_gap_min_max": str(gap),
        "s8_rail_to_bus_only_route_count": "0",
        "s8_rail_to_bus_only_best_complete_gap_min_max": "",
        "public_route_count": str(routes),
        "annual_bus_km": str(km),
        "public_explicit_field_check_pending_count": str(field),
    }


def test_profile_key_includes_passenger_and_availability_not_resources():
    a = row("A", km=90000, routes=1)
    b = row("B", km=120000, routes=4)
    assert profile_key(a, VALIDATION) == profile_key(b, VALIDATION)
    c = row("C", coverage=0.6)
    assert profile_key(a, VALIDATION) != profile_key(c, VALIDATION)


def test_reliability_precedes_simplicity_and_km():
    reliable = row("R", s8="ALL_PUBLIC_ROUTES_HAVE_SOME_COMPLETE_MATCH_PHASE", routes=4, km=110000)
    unreliable = row("U", s8="NO_PUBLIC_ROUTE_HAS_COMPLETE_MATCH_PHASE", routes=1, km=80000)
    survivors, meta = select_group([unreliable, reliable])
    assert [r["plan_id"] for r in survivors] == ["R"]
    assert meta["tie_break_invoked"] is True


def test_smaller_gap_breaks_equal_s8_class_and_share():
    a = row("A", gap=6.0)
    b = row("B", gap=10.0)
    survivors, _ = select_group([b, a])
    assert [r["plan_id"] for r in survivors] == ["A"]


def test_simplicity_then_km_then_field_checks_follow_declared_order():
    simple = row("simple", routes=1, km=120000, field=5)
    complex_cheap = row("complex", routes=2, km=70000, field=0)
    survivors, _ = select_group([complex_cheap, simple])
    assert [r["plan_id"] for r in survivors] == ["simple"]

    cheap = row("cheap", routes=1, km=90000, field=5)
    expensive = row("expensive", routes=1, km=100000, field=0)
    survivors, _ = select_group([expensive, cheap])
    assert [r["plan_id"] for r in survivors] == ["cheap"]

    verified = row("verified", routes=1, km=90000, field=0)
    pending = row("pending", routes=1, km=90000, field=2)
    survivors, _ = select_group([pending, verified])
    assert [r["plan_id"] for r in survivors] == ["verified"]


def test_exact_supported_tie_is_preserved():
    a = row("A")
    b = row("B")
    survivors, meta = select_group([b, a])
    assert [r["plan_id"] for r in survivors] == ["A", "B"]
    assert meta["survivor_count"] == 2
    assert meta["continuity_tie_break_applied"] is False


def test_best_gap_uses_worst_nonempty_passenger_support_class():
    r = row("A", gap=5.0)
    r["s8_rail_to_bus_only_route_count"] = "1"
    r["s8_rail_to_bus_only_best_complete_gap_min_max"] = "9.0"
    assert best_achievable_worst_route_gap(r) == 9.0
