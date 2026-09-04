from src.phase2_current_service_baseline_v3 import (
    V2OfficialStop,
    localize_identity_rows_v3,
    v2_name_subset_cluster,
)


def stop(stop_id, name, cluster, routes=("D184",)):
    return V2OfficialStop(stop_id, name, cluster, frozenset(routes))


def test_strong_route_name_subset_resolves_one_cluster():
    result = v2_name_subset_cluster(
        route_id="D184",
        pdf_label="S. MARIA HOE' Tremonte incrocio via Leopardi",
        stops=[stop("300903", "S.Maria Hoe' - tremonte/via leopardi", "EX_033")],
    )
    assert result is not None
    assert result[0] == "EX_033"


def test_generic_one_word_label_is_not_promoted():
    result = v2_name_subset_cluster(
        route_id="D184",
        pdf_label="HOE'",
        stops=[stop("300873", "Hoe'", "EX_028")],
    )
    assert result is None


def test_same_name_multiple_clusters_remains_unresolved():
    result = v2_name_subset_cluster(
        route_id="D185",
        pdf_label="CALCO Via Virgilio",
        stops=[
            stop("300397", "Calco - via virgilio", "EX_007", ("D185",)),
            stop("L00397", "Calco - via virgilio", "EX_038", ("D185",)),
        ],
    )
    assert result is None


def test_wrong_route_does_not_match():
    result = v2_name_subset_cluster(
        route_id="D184",
        pdf_label="S. MARIA HOE' Alpino Via Como",
        stops=[stop("300902", "S.Maria Hoe' - alpino", "EX_032", ("D148",))],
    )
    assert result is None


def test_historical_ambiguity_is_never_overridden():
    rows = [{
        "route_id": "D185",
        "source_page": "1",
        "stop_sequence_on_page": "12",
        "stop_label_pdf": "CALCO Via Virgilio",
        "identity_status": "AMBIGUOUS_HISTORICAL_GTFS",
        "historical_gtfs_stop_id": "",
    }]
    localized = localize_identity_rows_v3(
        rows,
        v2_stops=(stop("300397", "Calco - via virgilio", "EX_007", ("D185",)),),
    )
    assert localized[0]["v2_physical_cluster_id"] == ""
    assert localized[0]["localization_status"] == "HISTORICAL_AMBIGUITY_NOT_SPATIALLY_USED"


def test_no_historical_name_match_can_be_bridged():
    rows = [{
        "route_id": "D184",
        "source_page": "1",
        "stop_sequence_on_page": "6",
        "stop_label_pdf": "S. MARIA HOE' Alpino Via Como",
        "identity_status": "NO_HISTORICAL_GTFS_NAME_MATCH",
        "historical_gtfs_stop_id": "",
    }]
    localized = localize_identity_rows_v3(
        rows,
        v2_stops=(stop("300902", "S.Maria Hoe' - alpino", "EX_032"),),
    )
    assert localized[0]["v2_physical_cluster_id"] == "EX_032"
    assert localized[0]["localization_status"] == "LOCALIZED_V2_ROUTE_NAME_SUBSET_UNIQUE_PHYSICAL_CLUSTER"
