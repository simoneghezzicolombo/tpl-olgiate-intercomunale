"""RT-022 topology-neutral territorial structural-search orchestrator V3.

This module composes already validated Phase 2 contracts without changing their
semantics:

RT-018 exact stop occurrences -> RT-019 elementary reduction -> RT-009
reciprocity -> RT-008 connected topology-neutral frontier search.

It does not select a service winner, infer service termini, prescribe a
topology, or use municipality boundaries as routing filters.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from typing import Iterable, Mapping, Sequence

import pandas as pd

from src.phase2_complete_directed_pairs_v3 import (
    audit_pair_execution_completeness,
    build_complete_directed_pair_manifest,
)
from src.phase2_corridor_reciprocity_v3 import build_reciprocal_structural_links
from src.phase2_elementary_corridor_reduction_v3 import (
    build_directional_elementary_availability,
    build_pair_query_anchor_table,
    classify_elementary_corridors,
    filter_elementary_corridors_for_reciprocity,
)
from src.phase2_final_stop_materialization_v3 import (
    CORE_MUNICIPALITY_COUNTS,
    EXPECTED_STOP_PLACE_COUNT,
    materialize_stop_occurrences,
)
from src.phase2_network_structure_frontier_v3 import (
    enumerate_connected_structures_frontier,
)
from src.phase2_network_structure_search_v3 import AbstractLink, structure_to_record


CONTRACT = "RT022_TERRITORIAL_STRUCTURAL_SEARCH_ORCHESTRATOR_V3"
PREPARED_STATUS = "PREPARED_BLOCKED_PENDING_RT021_REAL_CORPUS"
PASS_STATUS = "PASS_COMPLETE_TOPOLOGY_NEUTRAL_TERRITORIAL_STRUCTURE_UNIVERSE"
FIXTURE_PASS_STATUS = "PASS_CONTROLLED_ORCHESTRATOR_EXECUTION"
BLOCKED_NO_LINKS = "BLOCKED_NO_RECIPROCAL_ELEMENTARY_LINKS"
BLOCKED_FRONTIER = "BLOCKED_RT008_INCOMPLETE_OR_CAP_REACHED"

EXPECTED_CONVENTIONAL_COUNT = 35
EXPECTED_SPECIAL_COUNT = 1
EXPECTED_DIRECTED_PAIR_COUNT = 1190
EXPECTED_UNORDERED_PAIR_COUNT = 595
CONVENTIONAL_CLASS = "CONVENTIONAL_TPL"
SPECIAL_CLASS = "SPECIAL_SERVICE"
CORE_POLICY_GROUPS = tuple(sorted(CORE_MUNICIPALITY_COUNTS))

OCCURRENCE_COLUMNS = [
    "corridor_id",
    "stop_sequence",
    "path_node_position",
    "stop_place_id",
    "stop_occurrence_index",
    "stop_name",
    "municipality",
    "lat",
    "lon",
    "service_class",
    "graph_node_id",
    "attachment_status",
    "graph_epoch_id",
    "materialization_semantics",
]


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _as_bool(value: object, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean for {field}: {value!r}")


def _parse_path_nodes(value: object) -> tuple[str, ...]:
    if isinstance(value, (tuple, list)):
        nodes = tuple(str(part).strip() for part in value if str(part).strip())
    else:
        nodes = tuple(part.strip() for part in str(value).split(";") if part.strip())
    if len(nodes) < 2:
        raise ValueError("corridor path_node_ids must contain at least two nodes")
    return nodes


def canonical_frame_sha256(
    frame: pd.DataFrame,
    *,
    sort_by: Sequence[str],
    columns: Sequence[str] | None = None,
) -> str:
    """Hash a dataframe canonically, invariant to input row ordering."""
    if columns is None:
        columns = tuple(sorted(str(column) for column in frame.columns))
    else:
        columns = tuple(str(column) for column in columns)
    _require_columns(frame, set(columns) | set(sort_by), "canonical digest frame")
    canonical = frame.loc[:, list(columns)].copy().fillna("")
    if sort_by:
        canonical = canonical.sort_values(list(sort_by), kind="mergesort")
    canonical = canonical.reset_index(drop=True)
    payload = canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _metadata_text(metadata: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _assert_optional_digest(
    metadata: Mapping[str, object],
    *,
    calculated: str,
    keys: Sequence[str],
    label: str,
) -> None:
    claimed = _metadata_text(metadata, *keys)
    if not claimed:
        return
    normalized = claimed.lower().removeprefix("sha256:")
    if normalized != calculated.lower():
        raise ValueError(
            f"{label} digest mismatch: metadata={claimed!r}, calculated=sha256:{calculated}"
        )


def validate_rt021_bundle(
    attachments: pd.DataFrame,
    pair_manifest: pd.DataFrame,
    pair_results: pd.DataFrame,
    corridors: pd.DataFrame,
    metadata: Mapping[str, object] | None = None,
    *,
    require_real_rt021_pass: bool = False,
) -> dict[str, object]:
    """Validate a frozen RT-021 bundle before any structural reduction/search."""
    metadata = dict(metadata or {})

    attachment_required = {
        "stop_place_id",
        "stop_name",
        "municipality",
        "service_class",
        "graph_node_id",
        "route_ready",
        "attachment_status",
        "graph_epoch_id",
    }
    _require_columns(attachments, attachment_required, "RT-021 stop attachments")
    a = attachments.copy().fillna("")
    for column in (
        "stop_place_id",
        "stop_name",
        "municipality",
        "service_class",
        "graph_node_id",
        "attachment_status",
        "graph_epoch_id",
    ):
        a[column] = a[column].astype(str).str.strip()
    if len(a) != EXPECTED_STOP_PLACE_COUNT:
        raise ValueError(
            f"RT-021 attachments must contain exactly {EXPECTED_STOP_PLACE_COUNT} stop places; "
            f"got {len(a)}"
        )
    if a["stop_place_id"].eq("").any() or a["stop_place_id"].duplicated().any():
        raise ValueError("RT-021 attachments must preserve 36 unique non-empty stop_place_id values")

    class_counts = Counter(a["service_class"])
    if class_counts.get(CONVENTIONAL_CLASS, 0) != EXPECTED_CONVENTIONAL_COUNT:
        raise ValueError(
            f"expected {EXPECTED_CONVENTIONAL_COUNT} {CONVENTIONAL_CLASS} stops; "
            f"got {class_counts.get(CONVENTIONAL_CLASS, 0)}"
        )
    if class_counts.get(SPECIAL_CLASS, 0) != EXPECTED_SPECIAL_COUNT:
        raise ValueError(
            f"expected {EXPECTED_SPECIAL_COUNT} {SPECIAL_CLASS} stop; "
            f"got {class_counts.get(SPECIAL_CLASS, 0)}"
        )
    unexpected_classes = sorted(
        set(class_counts) - {CONVENTIONAL_CLASS, SPECIAL_CLASS}
    )
    if unexpected_classes:
        raise ValueError(f"unexpected service classes in RT-021 attachments: {unexpected_classes}")

    municipality_counts = Counter(a["municipality"])
    if dict(sorted(municipality_counts.items())) != dict(
        sorted(CORE_MUNICIPALITY_COUNTS.items())
    ):
        raise ValueError(
            "final 36-stop municipality counts changed: "
            f"observed={dict(sorted(municipality_counts.items()))}, "
            f"expected={CORE_MUNICIPALITY_COUNTS}"
        )

    a["route_ready"] = [_as_bool(value, field="route_ready") for value in a["route_ready"]]
    conventional = a[a["service_class"] == CONVENTIONAL_CLASS].copy()
    if not conventional["route_ready"].all():
        blocked = sorted(
            conventional.loc[~conventional["route_ready"], "stop_place_id"].astype(str)
        )
        raise ValueError(f"all conventional RT-021 stops must be route-ready; blocked={blocked}")
    if conventional["graph_node_id"].eq("").any():
        raise ValueError("route-ready conventional stop has blank graph_node_id")

    epochs = sorted(set(conventional["graph_epoch_id"]))
    if len(epochs) != 1 or not epochs[0]:
        raise ValueError(
            f"conventional stop attachments must expose one graph epoch; got {epochs}"
        )
    graph_epoch_id = epochs[0]
    if set(a["graph_epoch_id"]) != {graph_epoch_id}:
        raise ValueError("all 36 stop attachments must be bound to the same graph epoch")

    anchors = build_pair_query_anchor_table(a)
    if len(anchors) != EXPECTED_CONVENTIONAL_COUNT:
        raise AssertionError("RT-019 anchor contract did not reproduce exactly 35 anchors")
    if anchors["service_terminal_status_claimed"].map(bool).any():
        raise AssertionError("technical query anchors may not claim service-terminal status")

    rebuilt = build_complete_directed_pair_manifest(anchors)
    if not bool(rebuilt.get("complete")):
        raise ValueError(f"RT-010 manifest rebuild blocked: {rebuilt.get('status')}")
    expected_manifest = rebuilt["manifest"].copy()
    if len(expected_manifest) != EXPECTED_DIRECTED_PAIR_COUNT:
        raise AssertionError("35 anchors must yield exactly 1,190 directed pairs")

    manifest_required = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "reverse_pair_id",
    }
    _require_columns(pair_manifest, manifest_required, "RT-021 pair manifest")
    supplied_manifest = pair_manifest.copy().fillna("")
    for column in manifest_required:
        supplied_manifest[column] = supplied_manifest[column].astype(str).str.strip()
    if len(supplied_manifest) != EXPECTED_DIRECTED_PAIR_COUNT:
        raise ValueError(
            f"RT-021 pair manifest must contain exactly {EXPECTED_DIRECTED_PAIR_COUNT} rows"
        )
    compare_columns = [
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "reverse_pair_id",
    ]
    expected_compare = expected_manifest.loc[:, compare_columns].sort_values(
        "pair_id", kind="mergesort"
    ).reset_index(drop=True)
    supplied_compare = supplied_manifest.loc[:, compare_columns].sort_values(
        "pair_id", kind="mergesort"
    ).reset_index(drop=True)
    if not expected_compare.equals(supplied_compare):
        raise ValueError("RT-021 pair manifest differs from independently rebuilt RT-010 universe")

    pair_audit = audit_pair_execution_completeness(expected_manifest, pair_results)
    if not bool(pair_audit.get("complete")):
        raise ValueError(
            "RT-021 pair execution is incomplete or invalid: "
            f"{pair_audit.get('status')}"
        )

    pair_result_required = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "gate_d_route_found",
    }
    _require_columns(pair_results, pair_result_required, "RT-021 pair results")
    p = pair_results.copy().fillna("")
    for column in (
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ):
        p[column] = p[column].astype(str).str.strip()
    p["gate_d_route_found"] = [
        _as_bool(value, field="gate_d_route_found") for value in p["gate_d_route_found"]
    ]

    corridor_required = {
        "corridor_id",
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "path_node_ids",
        "admissible_for_corridor_pool",
    }
    _require_columns(corridors, corridor_required, "RT-021 corridors")
    c = corridors.copy().fillna("")
    for column in (
        "corridor_id",
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ):
        c[column] = c[column].astype(str).str.strip()
        if c[column].eq("").any():
            raise ValueError(f"blank {column} in RT-021 corridors")
    if c["corridor_id"].duplicated().any():
        raise ValueError("RT-021 corridor_id must be globally unique")
    c["admissible_for_corridor_pool"] = [
        _as_bool(value, field="admissible_for_corridor_pool")
        for value in c["admissible_for_corridor_pool"]
    ]
    c["path_node_ids"] = [";".join(_parse_path_nodes(value)) for value in c["path_node_ids"]]

    pair_lookup = expected_compare.set_index("pair_id")
    unknown_pairs = sorted(set(c["pair_id"]) - set(pair_lookup.index))
    if unknown_pairs:
        raise ValueError(f"corridors reference unknown RT-010 pairs: {unknown_pairs}")
    for row in c.itertuples(index=False):
        expected_pair = pair_lookup.loc[str(row.pair_id)]
        if (
            str(row.source_routing_terminal_id)
            != str(expected_pair["source_routing_terminal_id"])
            or str(row.target_routing_terminal_id)
            != str(expected_pair["target_routing_terminal_id"])
        ):
            raise ValueError(
                f"corridor endpoint mismatch for {row.corridor_id}: "
                f"pair={row.pair_id}"
            )

    routed_pair_ids = set(p.loc[p["gate_d_route_found"], "pair_id"])
    corridor_pair_ids = set(c["pair_id"])
    missing_routed_corridors = sorted(routed_pair_ids - corridor_pair_ids)
    if missing_routed_corridors:
        raise ValueError(
            "route_found pair has no retained corridor evidence: "
            f"{missing_routed_corridors[:20]}"
        )
    corridor_without_route = sorted(corridor_pair_ids - routed_pair_ids)
    if corridor_without_route:
        raise ValueError(
            "corridor evidence exists for pair marked no-route: "
            f"{corridor_without_route[:20]}"
        )

    if "graph_epoch_id" in c.columns:
        corridor_epochs = sorted(
            set(c["graph_epoch_id"].astype(str).str.strip()) - {""}
        )
        if corridor_epochs and corridor_epochs != [graph_epoch_id]:
            raise ValueError(
                f"corridor graph epoch mismatch: attachments={graph_epoch_id}, "
                f"corridors={corridor_epochs}"
            )

    metadata_epoch = _metadata_text(
        metadata, "graph_epoch_id", "frozen_graph_epoch_id", "rt017_graph_epoch_id"
    )
    if metadata_epoch and metadata_epoch != graph_epoch_id:
        raise ValueError(
            f"metadata graph epoch mismatch: attachments={graph_epoch_id}, "
            f"metadata={metadata_epoch}"
        )

    if require_real_rt021_pass:
        verdict = _metadata_text(metadata, "verdict", "status").upper()
        if not verdict.startswith("PASS"):
            raise ValueError(
                "territorial RT-022 run requires RT-021 metadata verdict/status starting with PASS"
            )
        evidence_kind = _metadata_text(metadata, "evidence_kind", "data_kind").upper()
        if evidence_kind and evidence_kind in {
            "CONTROLLED_TEST_FIXTURE",
            "SYNTHETIC",
            "TEST",
            "FIXTURE",
        }:
            raise ValueError("controlled/synthetic fixture cannot be used as territorial RT-021 evidence")

    attachment_digest = canonical_frame_sha256(
        a,
        sort_by=["stop_place_id"],
    )
    pair_manifest_digest = canonical_frame_sha256(
        expected_compare,
        sort_by=["pair_id"],
    )
    pair_results_digest = canonical_frame_sha256(
        p,
        sort_by=["pair_id"],
    )
    corridor_digest = canonical_frame_sha256(
        c,
        sort_by=["corridor_id"],
    )

    _assert_optional_digest(
        metadata,
        calculated=attachment_digest,
        keys=("stop_attachment_sha256", "attachment_sha256"),
        label="stop attachment",
    )
    _assert_optional_digest(
        metadata,
        calculated=pair_manifest_digest,
        keys=("pair_manifest_sha256",),
        label="pair manifest",
    )
    _assert_optional_digest(
        metadata,
        calculated=corridor_digest,
        keys=("corridor_corpus_sha256", "corridors_sha256"),
        label="corridor corpus",
    )

    return {
        "attachments": a.sort_values("stop_place_id", kind="mergesort").reset_index(drop=True),
        "anchors": anchors,
        "pair_manifest": expected_manifest,
        "pair_results": p.sort_values("pair_id", kind="mergesort").reset_index(drop=True),
        "corridors": c.sort_values("corridor_id", kind="mergesort").reset_index(drop=True),
        "pair_execution_audit": pair_audit,
        "graph_epoch_id": graph_epoch_id,
        "digests": {
            "stop_attachments_sha256": attachment_digest,
            "pair_manifest_sha256": pair_manifest_digest,
            "pair_results_sha256": pair_results_digest,
            "corridor_corpus_sha256": corridor_digest,
        },
    }


def materialize_occurrence_corpus(
    corridors: pd.DataFrame,
    attachments: pd.DataFrame,
) -> pd.DataFrame:
    """Materialize exact RT-018 stop occurrences for every corridor alternative."""
    frames: list[pd.DataFrame] = []
    for row in corridors.sort_values("corridor_id", kind="mergesort").itertuples(index=False):
        occurrence = materialize_stop_occurrences(
            str(row.corridor_id),
            _parse_path_nodes(row.path_node_ids),
            attachments,
        )
        frames.append(occurrence)
    if not frames:
        return pd.DataFrame(columns=OCCURRENCE_COLUMNS)
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(
        ["corridor_id", "stop_sequence"], kind="mergesort"
    ).reset_index(drop=True)


def _eligible_structural_links_to_abstract(
    pair_audit: pd.DataFrame,
) -> tuple[list[AbstractLink], pd.DataFrame]:
    required = {
        "structural_link_id",
        "terminal_a",
        "terminal_b",
        "eligible_for_bidirectional_undirected_structure",
    }
    _require_columns(pair_audit, required, "RT-009 pair audit")
    frame = pair_audit.copy().fillna("")
    frame["eligible_for_bidirectional_undirected_structure"] = [
        _as_bool(value, field="eligible_for_bidirectional_undirected_structure")
        for value in frame["eligible_for_bidirectional_undirected_structure"]
    ]
    eligible = frame[
        frame["eligible_for_bidirectional_undirected_structure"]
    ].copy()
    eligible = eligible.sort_values(
        "structural_link_id", kind="mergesort"
    ).reset_index(drop=True)
    links = [
        AbstractLink(
            link_id=str(row.structural_link_id),
            u=str(row.terminal_a),
            v=str(row.terminal_b),
        )
        for row in eligible.itertuples(index=False)
    ]
    return links, eligible


def _structure_record_with_id(structure: object) -> dict[str, object]:
    record = structure_to_record(structure)
    payload = str(record["link_ids"]).encode("utf-8")
    record["structure_id"] = (
        "RT022_STRUCT_" + hashlib.sha256(payload).hexdigest()[:16].upper()
    )
    return record


def run_rt022_orchestrator(
    attachments: pd.DataFrame,
    pair_manifest: pd.DataFrame,
    pair_results: pd.DataFrame,
    corridors: pd.DataFrame,
    metadata: Mapping[str, object] | None = None,
    *,
    require_real_rt021_pass: bool = False,
    required_policy_groups: Sequence[str] = CORE_POLICY_GROUPS,
    min_edges: int = 1,
    max_edges: int | None = None,
    max_states: int = 100_000,
    max_structures: int = 20_000,
) -> dict[str, object]:
    """Run the full RT-022 structural orchestration on one frozen corpus."""
    validated = validate_rt021_bundle(
        attachments,
        pair_manifest,
        pair_results,
        corridors,
        metadata,
        require_real_rt021_pass=require_real_rt021_pass,
    )
    a = validated["attachments"]
    anchors = validated["anchors"]
    p = validated["pair_results"]
    c = validated["corridors"]

    occurrences = materialize_occurrence_corpus(c, a)
    classification = classify_elementary_corridors(c, occurrences)
    directional_availability = build_directional_elementary_availability(classification)
    elementary_corridors = filter_elementary_corridors_for_reciprocity(c, classification)

    reciprocity = build_reciprocal_structural_links(p, elementary_corridors)
    pair_audit = reciprocity["pair_audit"]
    abstract_links, eligible_links = _eligible_structural_links_to_abstract(pair_audit)
    structural_links = eligible_links.copy()

    output_digests = {
        **validated["digests"],
        "occurrence_corpus_sha256": canonical_frame_sha256(
            occurrences,
            sort_by=["corridor_id", "stop_sequence"],
        ),
        "elementary_classification_sha256": canonical_frame_sha256(
            classification,
            sort_by=["corridor_id"],
        ),
        "directional_availability_sha256": canonical_frame_sha256(
            directional_availability,
            sort_by=["pair_id"],
        ),
        "rt009_pair_audit_sha256": canonical_frame_sha256(
            pair_audit,
            sort_by=["structural_link_id"],
        ),
        "reciprocal_structural_links_sha256": canonical_frame_sha256(
            structural_links,
            sort_by=["structural_link_id"],
        ) if not structural_links.empty else hashlib.sha256(b"").hexdigest(),
    }

    empty_structures = pd.DataFrame()
    if not abstract_links:
        return {
            "status": BLOCKED_NO_LINKS,
            "complete": False,
            "graph_epoch_id": validated["graph_epoch_id"],
            "attachments": a,
            "anchors": anchors,
            "pair_manifest": validated["pair_manifest"],
            "pair_results": p,
            "corridors": c,
            "occurrences": occurrences,
            "classification": classification,
            "directional_availability": directional_availability,
            "elementary_corridors_for_reciprocity": elementary_corridors,
            "rt009_pair_audit": pair_audit,
            "structural_links": structural_links,
            "eligible_structural_links": eligible_links,
            "structures": empty_structures,
            "frontier_metadata": {},
            "digests": output_digests,
        }

    terminal_policy_groups = {
        str(row.routing_terminal_id): (str(row.municipality),)
        for row in anchors.itertuples(index=False)
    }
    required_groups = tuple(sorted({str(group).strip() for group in required_policy_groups if str(group).strip()}))
    if set(required_groups) != set(CORE_POLICY_GROUPS):
        raise ValueError(
            "RT-022 territorial policy groups must be exactly the five frozen core municipalities"
        )

    frontier = enumerate_connected_structures_frontier(
        abstract_links,
        required_policy_groups=required_groups,
        terminal_policy_groups=terminal_policy_groups,
        min_edges=min_edges,
        max_edges=max_edges,
        max_states=max_states,
        max_structures=max_structures,
    )
    frontier_complete = bool(frontier.get("complete"))
    structures_list = frontier.get("structures", []) if frontier_complete else []
    structures = pd.DataFrame(
        [_structure_record_with_id(item) for item in structures_list]
    )
    if not structures.empty:
        structures = structures.sort_values(
            "structure_id", kind="mergesort"
        ).reset_index(drop=True)

    frontier_metadata = {
        key: value
        for key, value in frontier.items()
        if key != "structures"
    }
    output_digests["structure_universe_sha256"] = canonical_frame_sha256(
        structures,
        sort_by=["structure_id"] if "structure_id" in structures.columns else [],
    )

    if not frontier_complete:
        status = BLOCKED_FRONTIER
        complete = False
        structures = pd.DataFrame()
    else:
        status = PASS_STATUS if require_real_rt021_pass else FIXTURE_PASS_STATUS
        complete = True

    return {
        "status": status,
        "complete": complete,
        "graph_epoch_id": validated["graph_epoch_id"],
        "attachments": a,
        "anchors": anchors,
        "pair_manifest": validated["pair_manifest"],
        "pair_results": p,
        "corridors": c,
        "occurrences": occurrences,
        "classification": classification,
        "directional_availability": directional_availability,
        "elementary_corridors_for_reciprocity": elementary_corridors,
        "rt009_pair_audit": pair_audit,
        "structural_links": structural_links,
        "eligible_structural_links": eligible_links,
        "structures": structures,
        "frontier_metadata": frontier_metadata,
        "digests": output_digests,
    }


def prepared_status_record() -> dict[str, object]:
    """Status emitted before a frozen RT-021 real corpus exists."""
    return {
        "status": PREPARED_STATUS,
        "territorial_result_claimed": False,
        "rt021_required": True,
        "topology_prior": False,
        "service_terminal_selection": False,
        "primary_runner_up_selection": False,
        "contract": CONTRACT,
    }
