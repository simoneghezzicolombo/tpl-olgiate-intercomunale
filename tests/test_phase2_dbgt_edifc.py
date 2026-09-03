import pandas as pd
import pytest

from src.phase2_dbgt_edifc import consolidate_active_edifc


def test_single_active_edifc_row_is_preserved():
    raw = pd.DataFrame([{
        "OBJECTID": 1,
        "CLASSID": "A",
        "EDIFC_STAT": "03",
        "EDIFC_TY": "01",
        "COD_CONS": "x",
    }])
    out, metrics = consolidate_active_edifc(raw)
    assert len(out) == 1
    assert out.loc[0, "EDIFC_STAT"] == "03"
    assert out.loc[0, "EDIFC_TY"] == "01"
    assert metrics["classid_with_multiple_active_edifc_rows"] == 0


def test_repeated_rows_with_same_semantics_are_collapsed():
    raw = pd.DataFrame([
        {"OBJECTID": 1, "CLASSID": "A", "EDIFC_STAT": "03", "EDIFC_TY": "01", "COD_CONS": "x"},
        {"OBJECTID": 2, "CLASSID": "A", "EDIFC_STAT": "03", "EDIFC_TY": "01", "COD_CONS": "y"},
    ])
    out, metrics = consolidate_active_edifc(raw)
    assert len(out) == 1
    assert out.loc[0, "active_edifc_source_row_count"] == 2
    assert out.loc[0, "COD_CONS_source_values"] == "x|y"
    assert metrics["extra_active_edifc_rows_collapsed"] == 1


def test_null_plus_single_value_is_consensus_not_conflict():
    raw = pd.DataFrame([
        {"CLASSID": "A", "EDIFC_STAT": None, "EDIFC_TY": "01"},
        {"CLASSID": "A", "EDIFC_STAT": "03", "EDIFC_TY": None},
    ])
    out, _ = consolidate_active_edifc(raw)
    assert out.loc[0, "EDIFC_STAT"] == "03"
    assert out.loc[0, "EDIFC_TY"] == "01"


def test_conflicting_status_fails_closed():
    raw = pd.DataFrame([
        {"CLASSID": "A", "EDIFC_STAT": "03", "EDIFC_TY": "01"},
        {"CLASSID": "A", "EDIFC_STAT": "02", "EDIFC_TY": "01"},
    ])
    with pytest.raises(RuntimeError, match="semantic conflicts"):
        consolidate_active_edifc(raw)


def test_conflicting_type_fails_closed():
    raw = pd.DataFrame([
        {"CLASSID": "A", "EDIFC_STAT": "03", "EDIFC_TY": "01"},
        {"CLASSID": "A", "EDIFC_STAT": "03", "EDIFC_TY": "06"},
    ])
    with pytest.raises(RuntimeError, match="semantic conflicts"):
        consolidate_active_edifc(raw)


def test_blank_classid_fails_closed():
    raw = pd.DataFrame([
        {"CLASSID": None, "EDIFC_STAT": "03", "EDIFC_TY": "01"},
    ])
    with pytest.raises(RuntimeError, match="blank CLASSID"):
        consolidate_active_edifc(raw)
