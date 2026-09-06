from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pandas as pd

from phase2_rt029_v4_common import *  # re-export public contract surface
from phase2_rt029_v4_common import (
    _assert_no_common_mojibake, _canonical_sha256, _canonical_stop_string,
    _split_unique_ids,
)
from phase2_rt029_v4_substrate import validate_walk_matrix, normalize_passenger_patterns, derive_structure_stop_sets
from phase2_rt029_v4_metrics import build_operating_envelope, evaluate_unique_stop_sets
from phase2_rt029_v4_pareto import build_candidate_decision_metrics, pareto_front_fast, build_pareto_outputs

def readiness_audit(
    *,
    structure_layers: Mapping[int, pd.DataFrame],
    rt023_realizations: pd.DataFrame,
    walk_matrix: pd.DataFrame,
    lineage: Mapping[str, str] | None = None,
    expected_layer_counts: Mapping[int, int] | None = EXPECTED_LAYER_COUNTS,
    expected_population_units: int | None = 10230,
) -> dict[str, object]:
    structures = validate_structure_layers(structure_layers, expected_layer_counts)
    required_links: set[str] = set()
    for value in structures["link_ids"]:
        required_links.update(_split_unique_ids(value, "link_ids"))
    realizations = validate_rt023_realizations(rt023_realizations, required_links)
    substrate = validate_walk_matrix(
        walk_matrix, expected_population_units=expected_population_units
    )
    vertex_keys = structures["vertex_ids"].map(
        lambda value: _canonical_stop_string(_split_unique_ids(value, "vertex_ids"))
    )
    return {
        "contract": READINESS_CONTRACT,
        "status": "PASS_PREPARED_WAITING_PASSENGER_STOP_REALIZATION",
        "structure_count": int(len(structures)),
        "layer_counts": {
            str(edge): int((structures["edge_count"] == edge).sum())
            for edge in sorted(EXPECTED_LAYER_COUNTS)
        },
        "required_structural_link_count": int(len(required_links)),
        "rt023_realization_count": int(len(realizations)),
        "population_unit_count": int(len(substrate.population_meta)),
        "rt028_stop_count": int(len(substrate.service_map)),
        "conventional_stop_count": int(len(substrate.conventional_stop_ids)),
        "display_label_normalization_count": int(substrate.display_label_normalization_count),
        "municipality_identity_semantics": "ISTAT_CODE_FOR_CALCULATION_NORMALIZED_NAME_FOR_DISPLAY_ONLY",
        "current_vertex_set_count_diagnostic_only": int(vertex_keys.nunique()),
        "final_passenger_stop_set_count": None,
        "pareto_run_performed": False,
        "passenger_stop_realization_required": True,
        "lineage": dict(sorted((lineage or {}).items())),
        "negative_assertions": {
            "treats_vertex_set_count_as_final_passenger_stop_set_count": False,
            "runs_pareto_before_passenger_stop_realization": False,
            "selects_primary_or_runner_up": False,
            "uses_weighted_composite_score": False,
            "uses_random_search": False,
            "uses_municipality_name_as_equity_identity": False,
            "reruns_pedestrian_routing": False,
            "uses_euclidean_fallback": False,
            "claims_complete_e7_search": False,
            "claims_e6_is_final_complexity_cap": False,
        },
    }


def compile_rt029_e456(
    *,
    structure_layers: Mapping[int, pd.DataFrame],
    rt023_realizations: pd.DataFrame,
    passenger_patterns: pd.DataFrame,
    walk_matrix: pd.DataFrame,
    lineage: Mapping[str, str] | None = None,
    expected_layer_counts: Mapping[int, int] | None = EXPECTED_LAYER_COUNTS,
    expected_population_units: int | None = 10230,
) -> RT029V4Result:
    structures = validate_structure_layers(structure_layers, expected_layer_counts)
    required_links: set[str] = set()
    for value in structures["link_ids"]:
        required_links.update(_split_unique_ids(value, "link_ids"))
    realizations = validate_rt023_realizations(rt023_realizations, required_links)
    substrate = validate_walk_matrix(
        walk_matrix, expected_population_units=expected_population_units
    )
    patterns = normalize_passenger_patterns(passenger_patterns, realizations)
    mapping, unique_sets = derive_structure_stop_sets(
        structures, patterns, substrate.service_map
    )
    operating = build_operating_envelope(structures, realizations)
    access, municipality, equity = evaluate_unique_stop_sets(unique_sets, substrate)
    candidate_metrics = build_candidate_decision_metrics(
        structures, mapping, access, equity, operating
    )
    frontiers, shortlist, pareto_diagnostics = build_pareto_outputs(candidate_metrics)
    audit = {
        "contract": CONTRACT,
        "status": "PASS",
        "structure_count": int(len(structures)),
        "layer_counts": {
            str(edge): int((structures["edge_count"] == edge).sum())
            for edge in sorted(EXPECTED_LAYER_COUNTS)
        },
        "rt023_realization_count": int(len(realizations)),
        "display_label_normalization_count": int(substrate.display_label_normalization_count),
        "municipality_identity_semantics": "ISTAT_CODE_FOR_CALCULATION_NORMALIZED_NAME_FOR_DISPLAY_ONLY",
        "unique_passenger_stop_set_count_all_scenarios": int(len(unique_sets)),
        "decision_passenger_stop_set_count": int(
            mapping.loc[mapping["scenario"] == DECISION_SCENARIO, "stop_set_id"].nunique()
        ),
        "frontier_row_count": int(len(frontiers)),
        "shortlist_count": int(len(shortlist)),
        **pareto_diagnostics,
        "structure_stop_sets_sha256": _canonical_sha256(
            mapping, ["structure_id", "scenario"]
        ),
        "unique_stop_sets_sha256": _canonical_sha256(unique_sets, ["stop_set_id"]),
        "stop_set_accessibility_sha256": _canonical_sha256(
            access, ["stop_set_id", "scope"]
        ),
        "stop_set_municipality_accessibility_sha256": _canonical_sha256(
            municipality, ["stop_set_id", "municipality_code"]
        ),
        "stop_set_equity_sha256": _canonical_sha256(
            equity, ["stop_set_id", "threshold_min"]
        ),
        "operating_envelope_sha256": _canonical_sha256(operating, ["structure_id"]),
        "candidate_decision_metrics_sha256": _canonical_sha256(
            candidate_metrics, ["structure_id"]
        ),
        "pareto_frontiers_sha256": _canonical_sha256(
            frontiers, ["threshold_min", "structure_id"]
        ),
        "pareto_shortlist_sha256": _canonical_sha256(shortlist, ["structure_id"]),
        "lineage": dict(sorted((lineage or {}).items())),
        "negative_assertions": {
            "uses_possible_passenger_union_for_pareto": False,
            "auto_adds_structural_vertices_to_passenger_pattern": False,
            "uses_special_service_stop": False,
            "uses_weighted_composite_score": False,
            "ranks_shortlist": False,
            "selects_primary_or_runner_up": False,
            "chooses_realization_alternative": False,
            "reruns_pedestrian_routing": False,
            "uses_euclidean_fallback": False,
            "drops_unreachable_population_from_threshold_denominator": False,
            "uses_random_search": False,
            "uses_municipality_name_as_equity_identity": False,
            "claims_complete_e7_search": False,
            "claims_e6_is_final_complexity_cap": False,
        },
    }
    return RT029V4Result(
        structure_stop_sets=mapping,
        unique_stop_sets=unique_sets,
        stop_set_accessibility=access,
        stop_set_municipality_accessibility=municipality,
        stop_set_equity=equity,
        operating_envelope=operating,
        candidate_decision_metrics=candidate_metrics,
        pareto_frontiers=frontiers,
        pareto_shortlist=shortlist,
        audit=audit,
    )


def write_outputs(result: RT029V4Result, output_dir: str | Path) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "rt029_e456_structure_stop_sets_v4.csv": result.structure_stop_sets,
        "rt029_e456_unique_passenger_stop_sets_v4.csv": result.unique_stop_sets,
        "rt029_e456_stop_set_accessibility_v4.csv": result.stop_set_accessibility,
        "rt029_e456_stop_set_municipality_accessibility_v4.csv": result.stop_set_municipality_accessibility,
        "rt029_e456_stop_set_equity_v4.csv": result.stop_set_equity,
        "rt029_e456_operating_envelope_v4.csv": result.operating_envelope,
        "rt029_e456_candidate_decision_metrics_v4.csv": result.candidate_decision_metrics,
        "rt029_e456_pareto_frontiers_v4.csv": result.pareto_frontiers,
        "rt029_e456_pareto_shortlist_v4.csv": result.pareto_shortlist,
    }
    for name, frame in outputs.items():
        _assert_no_common_mojibake(frame, name)
        frame.to_csv(out / name, index=False, lineterminator="\n", encoding="utf-8")
    (out / "rt029_e456_candidate_accessibility_pareto_audit_v4.json").write_text(
        json.dumps(result.audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
