from decimal import Decimal

from scripts.phase2_audit_rt031_south_resource_overlay_v3 import overlay_annual_km


def test_overlay_uses_declared_cycles_and_days_without_rounding():
    assert overlay_annual_km("10000", "3018.246") == Decimal("67694.87920")


def test_zero_spur_is_only_base_scenario():
    assert overlay_annual_km("21426.73", "0") == Decimal("111419.0") - Decimal("0.004")
