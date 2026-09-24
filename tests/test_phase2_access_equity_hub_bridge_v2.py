from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.phase2_run_access_equity_v2_hub_bridge import (
    OFFICIAL_STOP_ID,
    PHYSICAL_CLUSTER_ID,
    RAIL_ANCHOR_ID,
    bridged_explicit_stop_anchors,
    bridged_load_anchor_source_members,
    verify_official_station_stop,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_station_stop_evidence_passes_only_for_expected_official_identity(tmp_path: Path) -> None:
    path = tmp_path / "stops.csv"
    fields = ["stop_id", "stop_name", "official_routes_reference_gtfs", "stop_type", "physical_cluster_id"]
    _write_csv(path, fields, [{
        "stop_id": OFFICIAL_STOP_ID,
        "stop_name": "Olgiate Molgora (stazione f.s.)",
        "official_routes_reference_gtfs": "D184|D185",
        "stop_type": "EXISTING_OFFICIAL_STOP",
        "physical_cluster_id": PHYSICAL_CLUSTER_ID,
    }])
    row = verify_official_station_stop(path)
    assert row["physical_cluster_id"] == PHYSICAL_CLUSTER_ID


def test_station_stop_evidence_fails_closed_on_wrong_cluster(tmp_path: Path) -> None:
    path = tmp_path / "stops.csv"
    fields = ["stop_id", "stop_name", "official_routes_reference_gtfs", "stop_type", "physical_cluster_id"]
    _write_csv(path, fields, [{
        "stop_id": OFFICIAL_STOP_ID,
        "stop_name": "Olgiate Molgora (stazione f.s.)",
        "official_routes_reference_gtfs": "D184|D185",
        "stop_type": "EXISTING_OFFICIAL_STOP",
        "physical_cluster_id": "EX_WRONG",
    }])
    with pytest.raises(ValueError, match="belongs to"):
        verify_official_station_stop(path)


def test_anchor_member_bridge_changes_only_rail_access_source(tmp_path: Path) -> None:
    path = tmp_path / "anchors.csv"
    fields = ["anchor_id", "source_kind", "source_members"]
    _write_csv(path, fields, [
        {"anchor_id": RAIL_ANCHOR_ID, "source_kind": "HUB_RAIL", "source_members": ""},
        {"anchor_id": f"existing:{PHYSICAL_CLUSTER_ID}", "source_kind": "EXISTING_PHYSICAL_STOP_CLUSTER", "source_members": f"existing:{PHYSICAL_CLUSTER_ID}"},
        {"anchor_id": "P_TEST", "source_kind": "PROPOSED_STOP", "source_members": ""},
    ])
    members, kinds = bridged_load_anchor_source_members(path)
    assert kinds[RAIL_ANCHOR_ID] == "HUB_RAIL"
    assert members[RAIL_ANCHOR_ID] == (("EXISTING_PHYSICAL_STOP_CLUSTER", PHYSICAL_CLUSTER_ID),)
    assert members[f"existing:{PHYSICAL_CLUSTER_ID}"] == (("EXISTING_PHYSICAL_STOP_CLUSTER", PHYSICAL_CLUSTER_ID),)
    assert members["P_TEST"] == (("PROPOSED_STOP", "P_TEST"),)


def test_explicit_access_set_adds_only_the_station_hub_when_present() -> None:
    kinds = {
        RAIL_ANCHOR_ID: "HUB_RAIL",
        "rail:OTHER": "HUB_RAIL",
        "P_TEST": "PROPOSED_STOP",
    }
    routes = [[RAIL_ANCHOR_ID, "P_TEST", "rail:OTHER"]]
    result = bridged_explicit_stop_anchors(routes, anchor_kinds=kinds)
    assert result == frozenset({RAIL_ANCHOR_ID, "P_TEST"})


def test_explicit_access_set_does_not_add_station_when_route_does_not_use_it() -> None:
    kinds = {RAIL_ANCHOR_ID: "HUB_RAIL", "P_TEST": "PROPOSED_STOP"}
    result = bridged_explicit_stop_anchors([["P_TEST", "P_TEST"]], anchor_kinds=kinds)
    assert result == frozenset({"P_TEST"})
