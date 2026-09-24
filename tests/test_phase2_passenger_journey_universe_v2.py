import csv
import json

from scripts.phase2_build_passenger_journey_universe_v2 import (
    load_sensitivity_cases,
    materialise_universe,
)


def test_materialise_universe_keeps_only_certified_s8_direct_rows(tmp_path):
    addressability = tmp_path / "addressability.csv"
    validation = tmp_path / "validation.json"
    with addressability.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "procom_res", "origin_name", "procom_lav", "destination_name",
                "workers", "category", "rail_addressability",
                "feeder_objective_eligible", "rail_semantics",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "procom_res": "1", "origin_name": "A", "procom_lav": "9", "destination_name": "X",
            "workers": "8", "category": "S8_DIRECT", "rail_addressability": "DIRECT_S8_GTFS_VERIFIED",
            "feeder_objective_eligible": "True",
            "rail_semantics": "INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE",
        })
        writer.writerow({
            "procom_res": "1", "origin_name": "A", "procom_lav": "8", "destination_name": "Y",
            "workers": "2", "category": "OTHER_EXTERNAL", "rail_addressability": "NOT_RAIL_ASSIGNED",
            "feeder_objective_eligible": "False",
            "rail_semantics": "INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE",
        })
    validation.write_text(json.dumps({
        "source_scope": "ISTAT_2021_WORK_COMMUTING_ONLY",
        "s8_direct_workers": 8,
        "core_codes": ["1", "2", "3", "4", "5"],
    }))
    rows, _ = materialise_universe(addressability, validation)
    assert len(rows) == 1
    assert rows[0]["demand_weight"] == "8.000000000"
    assert rows[0]["category"] == "S8_DIRECT"
    assert rows[0]["rail_addressability"] == "DIRECT_S8_GTFS_VERIFIED"
    assert rows[0]["spatial_allocation_status"] == "MUNICIPAL_OD_ONLY_NO_SPATIAL_ALLOCATION"
    assert rows[0]["full_gjt_ready"] == "false"


def test_sensitivity_grid_cardinality_is_explicit(tmp_path):
    config = tmp_path / "sensitivity.json"
    config.write_text(json.dumps({
        "contract": "PHASE2_PASSENGER_GJT_SENSITIVITY_V2",
        "status": "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL",
        "expected_full_factorial_case_count": 2,
        "parameter_grid": {
            "bus_ivt_weight": [1.0, 1.4],
            "walk_weight": [1.5],
            "wait_weight": [2.0],
            "transfer_penalty_min": [6.0],
            "missed_connection_cost_multiplier": [1.0],
        },
    }))
    _, cases = load_sensitivity_cases(config)
    assert [row["sensitivity_id"] for row in cases] == ["GJT2_000", "GJT2_001"]
