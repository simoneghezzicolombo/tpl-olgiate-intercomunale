from __future__ import annotations

import csv
import json

import pytest

from scripts.phase2_build_territorial_commuting_addressability_v2 import (
    load_routes,
    parse_json_list,
)
from src.phase2_territorial_commuting_addressability_v2 import (
    RouteGeometry,
    WorkOD,
    reachable_municipalities,
    summarise_addressability,
)


ANCHORS = {
    "H": frozenset({"Olgiate Molgora"}),
    "B": frozenset({"Brivio"}),
    "C": frozenset({"Calco"}),
    "V": frozenset({"La Valletta Brianza"}),
}


def od(origin: str, destination: str, workers: float, category: str) -> WorkOD:
    return WorkOD(
        origin_code=f"O-{origin}",
        origin_name=origin,
        destination_code=f"D-{destination}",
        destination_name=destination,
        workers=workers,
        category=category,
    )


def test_directionality_is_preserved() -> None:
    route = RouteGeometry("R", ("H", "B"))
    forward = reachable_municipalities([route], ANCHORS, "Olgiate Molgora")
    reverse = reachable_municipalities([route], ANCHORS, "Brivio")

    assert "Brivio" in forward
    assert "Olgiate Molgora" not in reverse


def test_closed_loop_repeated_hub_supports_return_direction() -> None:
    route = RouteGeometry("LOOP", ("H", "B", "H"))

    assert "Brivio" in reachable_municipalities(
        [route], ANCHORS, "Olgiate Molgora"
    )
    assert "Olgiate Molgora" in reachable_municipalities(
        [route], ANCHORS, "Brivio"
    )


def test_transfer_at_exact_shared_anchor_is_structurally_reachable() -> None:
    first = RouteGeometry("R1", ("H", "B"))
    second = RouteGeometry("R2", ("B", "C"))

    reachable = reachable_municipalities(
        [first, second], ANCHORS, "Olgiate Molgora"
    )
    assert "Calco" in reachable


def test_open_route_has_no_technical_closure_passenger_edge() -> None:
    open_public_route = RouteGeometry("OPEN", ("H", "B"))

    reachable = reachable_municipalities(
        [open_public_route], ANCHORS, "Brivio"
    )
    assert "Olgiate Molgora" not in reachable


def test_self_od_is_retained_but_excluded_from_addressable_mass() -> None:
    rows = [
        od("Olgiate Molgora", "Olgiate Molgora", 25.0, "SELF"),
        od("Olgiate Molgora", "Brivio", 40.0, "OTHER_CORE"),
    ]
    summary = summarise_addressability(
        rows,
        [RouteGeometry("R", ("H", "B"))],
        ANCHORS,
    )

    assert summary["self_worker_od_mass_unresolved"] == 25.0
    assert summary["structurally_addressable_worker_od_mass_upper_bound"] == 40.0
    assert summary["structurally_addressable_od_relation_count"] == 1


def test_category_masses_remain_separate() -> None:
    rows = [
        od("Olgiate Molgora", "Brivio", 10.0, "OTHER_CORE"),
        od("Olgiate Molgora", "Calco", 20.0, "S8_DIRECT"),
        od("Olgiate Molgora", "La Valletta Brianza", 30.0, "OTHER_EXTERNAL"),
    ]
    route = RouteGeometry("R", ("H", "B", "C"))
    summary = summarise_addressability(rows, [route], ANCHORS)

    assert summary["other_core_addressable_worker_od_mass_upper_bound"] == 10.0
    assert summary["s8_direct_addressable_worker_od_mass_upper_bound"] == 20.0
    assert summary["other_external_addressable_worker_od_mass_upper_bound"] == 0
    assert summary["structurally_addressable_worker_od_mass_upper_bound"] == 30.0


def test_adding_extension_cannot_reduce_structural_addressability() -> None:
    rows = [
        od("Olgiate Molgora", "Brivio", 10.0, "OTHER_CORE"),
        od("Olgiate Molgora", "Calco", 20.0, "S8_DIRECT"),
    ]
    base = [RouteGeometry("BASE", ("H", "B"))]
    extended = base + [RouteGeometry("EXT", ("B", "C"))]

    base_summary = summarise_addressability(rows, base, ANCHORS)
    extended_summary = summarise_addressability(rows, extended, ANCHORS)

    assert (
        extended_summary["structurally_addressable_worker_od_mass_upper_bound"]
        >= base_summary["structurally_addressable_worker_od_mass_upper_bound"]
    )


def test_json_parser_allows_repeated_route_anchors_only_when_requested() -> None:
    raw = json.dumps(["H", "B", "H"])

    with pytest.raises(ValueError, match="Duplicate IDs"):
        parse_json_list(raw, "route_ids")
    assert parse_json_list(raw, "anchors_json", unique=False) == ["H", "B", "H"]


def test_route_loader_preserves_legitimate_repeated_anchor(tmp_path) -> None:
    path = tmp_path / "routes.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "route_id",
                "anchors_json",
                "public_service_starts_at_hub",
                "vehicle_closure_added",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "route_id": "LOOP",
                "anchors_json": json.dumps(["H", "B", "H"]),
                "public_service_starts_at_hub": "true",
                "vehicle_closure_added": "false",
            }
        )

    routes = load_routes(path, ANCHORS)
    assert routes["LOOP"].anchors == ("H", "B", "H")
