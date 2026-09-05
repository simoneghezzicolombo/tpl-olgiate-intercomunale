from __future__ import annotations

import pandas as pd
import pytest
from pyproj import Transformer

from src.phase2_final_stop_materialization_v3 import (
    CORE_MUNICIPALITY_COUNTS,
    attach_stop_places_to_graph,
    materialize_stop_occurrences,
    summarise_stop_occurrences,
    validate_final_stop_places,
)


def stop_fixture() -> pd.DataFrame:
    rows = []
    number = 0
    for municipality, count in CORE_MUNICIPALITY_COUNTS.items():
        for local_index in range(count):
            number += 1
            service_class = "SPECIAL_SERVICE" if number == 25 else "CONVENTIONAL_TPL"
            rows.append(
                {
                    "operational_stop_no": number,
                    "stop_place_id": f"STOP::{number:02d}",
                    "stop_name": f"Stop {number:02d}",
                    "municipality": municipality,
                    "lat": 45.72 + number * 0.00005,
                    "lon": 9.38 + number * 0.00005,
                    "source_families": "TEST_SOURCE",
                    "source_native_ids": f"N{number:02d}",
                    "known_routes": "T0",
                    "existence_confidence": "TEST_CONFIDENCE",
                    "service_class": service_class,
                    "notes": "controlled fixture",
                }
            )
    assert number == 36
    return pd.DataFrame(rows)


def graph_for_stops(stops: pd.DataFrame, *, epoch: str = "test-epoch") -> pd.DataFrame:
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    xs, ys = transformer.transform(stops["lon"].astype(float).tolist(), stops["lat"].astype(float).tolist())
    return pd.DataFrame(
        {
            "node_id": [f"NODE::{i:02d}" for i in range(1, len(stops) + 1)],
            "x_m_epsg32632": xs,
            "y_m_epsg32632": ys,
            "epoch_id": epoch,
        }
    )


def test_validate_accepts_exact_final_semantics_and_is_order_invariant() -> None:
    original = stop_fixture()
    shuffled = original.sample(frac=1.0, random_state=17).reset_index(drop=True)
    a = validate_final_stop_places(original)
    b = validate_final_stop_places(shuffled)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 36
    assert a["stop_place_id"].is_unique


def test_validate_rejects_wrong_count() -> None:
    with pytest.raises(ValueError, match="exactly 36"):
        validate_final_stop_places(stop_fixture().iloc[:-1].copy())


def test_validate_rejects_duplicate_identity() -> None:
    frame = stop_fixture()
    frame.loc[1, "stop_place_id"] = frame.loc[0, "stop_place_id"]
    with pytest.raises(ValueError, match="must be unique"):
        validate_final_stop_places(frame)


def test_validate_rejects_changed_municipality_counts() -> None:
    frame = stop_fixture()
    frame.loc[0, "municipality"] = "Calco"
    with pytest.raises(ValueError, match="municipality counts changed"):
        validate_final_stop_places(frame)


def test_validate_rejects_invalid_coordinates() -> None:
    frame = stop_fixture()
    frame.loc[0, "lat"] = 999
    with pytest.raises(ValueError, match="Invalid latitude"):
        validate_final_stop_places(frame)


def test_attachment_is_deterministic_under_input_reordering() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    a = attach_stop_places_to_graph(stops, nodes)
    b = attach_stop_places_to_graph(
        stops.sample(frac=1.0, random_state=3).reset_index(drop=True),
        nodes.sample(frac=1.0, random_state=4).reset_index(drop=True),
    )
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 36
    assert a["stop_place_id"].is_unique
    assert set(a["attachment_status"]) == {"ROUTE_READY_LE_75M"}


def test_attachment_rejects_duplicate_graph_node_identity() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    nodes.loc[1, "node_id"] = nodes.loc[0, "node_id"]
    with pytest.raises(ValueError, match="node_id must be unique"):
        attach_stop_places_to_graph(stops, nodes)


def test_attachment_keeps_unresolved_stop_explicit_instead_of_dropping() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    far_x, far_y = transformer.transform(10.5, 46.5)
    # Remove the matching node for STOP::01 and replace it with a far irrelevant node.
    nodes.loc[0, "x_m_epsg32632"] = far_x
    nodes.loc[0, "y_m_epsg32632"] = far_y
    attached = attach_stop_places_to_graph(stops, nodes)
    row = attached.loc[attached["stop_place_id"] == "STOP::01"].iloc[0]
    assert len(attached) == 36
    # Its nearest remaining fixture node is nearby, so move every other node far too for this test.
    # Rebuild a graph with a single far node to guarantee explicit unresolved status.
    one_far = pd.DataFrame(
        {
            "node_id": ["FAR"],
            "x_m_epsg32632": [far_x],
            "y_m_epsg32632": [far_y],
            "epoch_id": ["test-epoch"],
        }
    )
    unresolved = attach_stop_places_to_graph(stops, one_far)
    target = unresolved.loc[unresolved["stop_place_id"] == "STOP::01"].iloc[0]
    assert target["attachment_status"] == "OUTSIDE_250M"
    assert not bool(target["route_ready"])
    assert len(unresolved) == 36


def test_review_attachment_is_not_automatically_materialization_ready() -> None:
    stops = stop_fixture()
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    x, y = transformer.transform(float(stops.iloc[0]["lon"]), float(stops.iloc[0]["lat"]))
    nodes = pd.DataFrame(
        {
            "node_id": ["REVIEW_NODE"],
            "x_m_epsg32632": [x + 100.0],
            "y_m_epsg32632": [y],
            "epoch_id": ["test-epoch"],
        }
    )
    # Other stops may differ, but the first one is deliberately in review range.
    attached = attach_stop_places_to_graph(stops, nodes)
    row = attached.loc[attached["stop_place_id"] == "STOP::01"].iloc[0]
    assert row["attachment_status"] == "REVIEW_75_250M"
    assert not bool(row["automatic_materialization_eligible"])


def test_special_service_is_preserved_but_not_auto_promoted_to_conventional_pattern() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    attached = attach_stop_places_to_graph(stops, nodes)
    special = attached.loc[attached["service_class"] == "SPECIAL_SERVICE"].iloc[0]
    assert bool(special["route_ready"])
    assert not bool(special["service_class_automatic"])
    assert not bool(special["automatic_materialization_eligible"])

    path = [special["graph_node_id"]]
    conventional = materialize_stop_occurrences("C", path, attached)
    assert conventional.empty
    explicit = materialize_stop_occurrences(
        "C",
        path,
        attached,
        allowed_service_classes=("CONVENTIONAL_TPL", "SPECIAL_SERVICE"),
    )
    assert explicit["stop_place_id"].tolist() == [special["stop_place_id"]]


def test_loop_repeats_same_stop_place_as_distinct_occurrences() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    attached = attach_stop_places_to_graph(stops, nodes)
    node_a = attached.loc[attached["stop_place_id"] == "STOP::01", "graph_node_id"].iloc[0]
    node_b = attached.loc[attached["stop_place_id"] == "STOP::02", "graph_node_id"].iloc[0]
    occurrences = materialize_stop_occurrences("LOOP", [node_a, node_b, node_a], attached)
    stop_1 = occurrences.loc[occurrences["stop_place_id"] == "STOP::01"]
    assert stop_1["stop_occurrence_index"].tolist() == [1, 2]
    assert stop_1["path_node_position"].tolist() == [0, 2]
    assert occurrences["stop_sequence"].tolist() == list(range(1, len(occurrences) + 1))


def test_multiple_stop_places_on_same_node_have_deterministic_stable_id_order() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    attached = attach_stop_places_to_graph(stops, nodes)
    first_node = attached.loc[attached["stop_place_id"] == "STOP::01", "graph_node_id"].iloc[0]
    attached.loc[attached["stop_place_id"] == "STOP::02", "graph_node_id"] = first_node
    occurrences = materialize_stop_occurrences("SAME_NODE", [first_node], attached)
    assert occurrences["stop_place_id"].tolist()[:2] == ["STOP::01", "STOP::02"]


def test_empty_materialization_is_valid_and_has_stable_schema() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    attached = attach_stop_places_to_graph(stops, nodes)
    occurrences = materialize_stop_occurrences("NONE", ["NODE::NOT_PRESENT"], attached)
    assert occurrences.empty
    assert "stop_place_id" in occurrences.columns
    summary = summarise_stop_occurrences(occurrences)
    assert summary["stop_occurrences"] == 0
    assert summary["all_five_core_municipalities_have_stop"] is False


def test_summary_distinguishes_occurrences_from_unique_stop_places() -> None:
    stops = stop_fixture()
    nodes = graph_for_stops(stops)
    attached = attach_stop_places_to_graph(stops, nodes)
    node_a = attached.loc[attached["stop_place_id"] == "STOP::01", "graph_node_id"].iloc[0]
    occurrences = materialize_stop_occurrences("REPEAT", [node_a, node_a], attached)
    summary = summarise_stop_occurrences(occurrences)
    assert summary["stop_occurrences"] == 2
    assert summary["unique_stop_places"] == 1
