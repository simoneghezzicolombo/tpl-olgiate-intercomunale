from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

MODULE_PATH = Path("scripts/gate_d_structural_candidates_v4.py")
spec = importlib.util.spec_from_file_location("gate_d_structural_candidates_v4", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _row(tags: str):
    return pd.Series({"highway": "residential", "other_tags": tags})


def test_bus_yes_overrides_psv_no_and_generic_vehicle_no():
    eligible, reasons = module.bus_eligibility(
        _row('"vehicle"=>"no","psv"=>"no","bus"=>"yes"')
    )
    assert eligible
    assert not any("restriction" in reason for reason in reasons)


def test_bus_no_overrides_psv_yes():
    eligible, reasons = module.bus_eligibility(_row('"psv"=>"yes","bus"=>"no"'))
    assert not eligible
    assert reasons == ["explicit_bus_restriction"]


def test_psv_yes_overrides_generic_motor_vehicle_no_when_bus_unspecified():
    eligible, reasons = module.bus_eligibility(
        _row('"motor_vehicle"=>"no","psv"=>"yes"')
    )
    assert eligible
    assert not any("restriction" in reason for reason in reasons)


def test_psv_no_denies_when_bus_unspecified():
    eligible, reasons = module.bus_eligibility(_row('"psv"=>"no"'))
    assert not eligible
    assert reasons == ["explicit_psv_restriction"]


def test_conditional_bus_access_is_routable_but_flagged():
    eligible, reasons = module.bus_eligibility(_row('"bus"=>"destination","access"=>"no"'))
    assert eligible
    assert "conditional_bus=destination" in reasons


def test_unknown_bus_value_fails_closed():
    eligible, reasons = module.bus_eligibility(_row('"bus"=>"nonstandard_value","psv"=>"yes"'))
    assert not eligible
    assert reasons == ["unparsed_bus=nonstandard_value"]
