from __future__ import annotations

import hashlib
from typing import Iterable, Mapping

import pandas as pd

from phase2_service_pattern_realization_bridge_v3 import (
    BridgeResult,
    RT023ContractError,
    build_rt014_service_pattern_from_fragment,
    compile_rt023_bridge as _compile_core,
    write_bridge_result,
)


CERTIFIED_STOP_UNIVERSE_CONTRACT = "RT023_FROZEN_36_STOP_ATTACHMENT_LAYER_V3"
SPECIAL_STOP_ID = "SPECIAL::CASA_DI_COMUNITA_OLGIATE"
EXPECTED_MATERIALIZATION_SEMANTICS = (
    "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE"
)


def _required_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise RT023ContractError(f"{label} missing required columns: {missing}")


def _as_bool(value: object, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise RT023ContractError(f"{label} must be boolean-like, got {value!r}")


def _canonical_sha256(df: pd.DataFrame, sort_cols: list[str]) -> str:
    stable = df.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    return hashlib.sha256(
        stable.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()


def _validate_frozen_stop_contract(
    *,
    stop_attachments: pd.DataFrame,
    corridor_stop_occurrences: pd.DataFrame,
    expected_graph_epoch_id: str | None,
) -> tuple[str, set[str]]:
    _required_columns(
        stop_attachments,
        (
            "stop_place_id",
            "service_class",
            "graph_node_id",
            "graph_epoch_id",
            "automatic_materialization_eligible",
            "automatic_exclusion_reason",
        ),
        "stop_attachments",
    )
    _required_columns(
        corridor_stop_occurrences,
        (
            "corridor_id",
            "stop_place_id",
            "graph_node_id",
            "graph_epoch_id",
            "service_class",
            "materialization_semantics",
        ),
        "corridor_stop_occurrences",
    )

    stops = stop_attachments.copy()
    occ = corridor_stop_occurrences.copy()

    if stops["stop_place_id"].duplicated().any():
        raise RT023ContractError("duplicate stop_place_id in frozen stop attachment layer")
    if len(stops) != 36:
        raise RT023ContractError(
            f"frozen stop attachment layer must contain exactly 36 stop places, got {len(stops)}"
        )

    conventional = stops[stops["service_class"].astype(str) == "CONVENTIONAL_TPL"].copy()
    special = stops[stops["service_class"].astype(str) == "SPECIAL_SERVICE"].copy()
    if len(conventional) != 35 or len(special) != 1:
        raise RT023ContractError(
            "frozen stop universe must be exactly 35 CONVENTIONAL_TPL + 1 SPECIAL_SERVICE"
        )
    if set(special["stop_place_id"].astype(str)) != {SPECIAL_STOP_ID}:
        raise RT023ContractError("unexpected SPECIAL_SERVICE identity in frozen stop universe")
    if not all(
        _as_bool(v, "conventional automatic_materialization_eligible")
        for v in conventional["automatic_materialization_eligible"]
    ):
        raise RT023ContractError("all 35 conventional stops must be automatic-materialization eligible")
    if any(
        _as_bool(v, "special automatic_materialization_eligible")
        for v in special["automatic_materialization_eligible"]
    ):
        raise RT023ContractError("SPECIAL_SERVICE must not be automatic-materialization eligible")

    stop_epochs = set(stops["graph_epoch_id"].astype(str))
    if len(stop_epochs) != 1:
        raise RT023ContractError(f"frozen stop layer must have one graph epoch, got {sorted(stop_epochs)}")
    stop_epoch = next(iter(stop_epochs))
    if expected_graph_epoch_id is not None and stop_epoch != str(expected_graph_epoch_id):
        raise RT023ContractError(
            f"stop attachment graph epoch mismatch: expected {expected_graph_epoch_id!r}, got {stop_epoch!r}"
        )
    occ_epochs = set(occ["graph_epoch_id"].astype(str))
    if occ_epochs != {stop_epoch}:
        raise RT023ContractError(
            f"occurrence graph epochs {sorted(occ_epochs)} != frozen stop epoch {stop_epoch!r}"
        )

    eligible_ids = set(conventional["stop_place_id"].astype(str))
    occurrence_ids = set(occ["stop_place_id"].astype(str))
    unknown = sorted(occurrence_ids - eligible_ids)
    if unknown:
        raise RT023ContractError(
            f"corridor occurrences contain stops outside frozen 35 conventional universe: {unknown}"
        )
    if set(occ["service_class"].astype(str)) != {"CONVENTIONAL_TPL"}:
        raise RT023ContractError("automatic corridor occurrences must be CONVENTIONAL_TPL only")
    if set(occ["materialization_semantics"].astype(str)) != {EXPECTED_MATERIALIZATION_SEMANTICS}:
        raise RT023ContractError("unexpected corridor stop materialization semantics")

    attachment_node = dict(
        zip(conventional["stop_place_id"].astype(str), conventional["graph_node_id"].astype(str))
    )
    for _, row in occ.iterrows():
        stop_id = str(row["stop_place_id"])
        if str(row["graph_node_id"]) != attachment_node[stop_id]:
            raise RT023ContractError(
                f"corridor occurrence graph node drift for stop {stop_id}"
            )
    return stop_epoch, eligible_ids


def compile_certified_rt023_bridge(
    *,
    reciprocal_links: pd.DataFrame,
    structures: pd.DataFrame,
    stop_attachments: pd.DataFrame,
    elementary_corridors: pd.DataFrame,
    corridor_stop_occurrences: pd.DataFrame,
    expected_graph_epoch_id: str | None = None,
    lineage: Mapping[str, str] | None = None,
) -> BridgeResult:
    """Certified RT-023 entry point with the frozen 36-stop RT-018 contract."""

    stop_epoch, _ = _validate_frozen_stop_contract(
        stop_attachments=stop_attachments,
        corridor_stop_occurrences=corridor_stop_occurrences,
        expected_graph_epoch_id=expected_graph_epoch_id,
    )

    result = _compile_core(
        reciprocal_links=reciprocal_links,
        structures=structures,
        elementary_corridors=elementary_corridors,
        corridor_stop_occurrences=corridor_stop_occurrences,
        expected_graph_epoch_id=expected_graph_epoch_id or stop_epoch,
        lineage=lineage,
    )

    realizations = result.realization_catalog.copy()
    lineage_map = dict(lineage or {})
    realizations["rt021_elementary_corridor_evidence_sha256"] = lineage_map.get(
        "elementary_corridors_for_reciprocity_sha256", ""
    )
    realizations["rt018_stop_attachment_layer_sha256"] = lineage_map.get(
        "stop_attachments_sha256", ""
    )
    realizations["rt018_stop_occurrence_corpus_sha256"] = lineage_map.get(
        "corridor_stop_occurrences_sha256", ""
    )

    audit = dict(result.audit)
    audit.update(
        {
            "frozen_stop_contract": CERTIFIED_STOP_UNIVERSE_CONTRACT,
            "frozen_stop_count": 36,
            "frozen_conventional_stop_count": 35,
            "frozen_special_service_stop_count": 1,
            "frozen_special_service_stop_id": SPECIAL_STOP_ID,
            "realization_catalog_sha256": _canonical_sha256(
                realizations,
                ["structural_link_id", "direction", "alternative_ordinal", "corridor_id"],
            ),
        }
    )
    negative = dict(audit["negative_assertions"])
    negative.update(
        {
            "accepts_old_43_stop_universe": False,
            "auto_materializes_special_service": False,
            "accepts_occurrence_outside_frozen_stop_layer": False,
        }
    )
    audit["negative_assertions"] = negative

    return BridgeResult(
        realization_catalog=realizations,
        structure_link_manifest=result.structure_link_manifest,
        rt014_pattern_fragments=result.rt014_pattern_fragments,
        audit=audit,
    )


__all__ = [
    "CERTIFIED_STOP_UNIVERSE_CONTRACT",
    "SPECIAL_STOP_ID",
    "RT023ContractError",
    "build_rt014_service_pattern_from_fragment",
    "compile_certified_rt023_bridge",
    "write_bridge_result",
]
