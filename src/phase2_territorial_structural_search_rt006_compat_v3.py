"""RT-022 compatibility layer for explicit RT-006 corridor-admissibility failures.

RT-017 road reachability and RT-006 corridor admissibility are different facts.
A direction may remain ``gate_d_route_found=True`` while the complete certified
RT-006 sensitivity grid admits no physical-loopless corridor. RT-021 records
such directions explicitly instead of silently dropping them.

The original RT-022 validator predates that explicit-failure status and assumes
every Gate-D-reachable pair must have corridor evidence. This module narrows
that assumption without changing any routing evidence: a missing corridor is
accepted only when the pair has a non-empty explicit failure reason and, when
available, ``corridor_count == 0``. The original pair evidence is restored
before RT-009, which already correctly classifies these directions as
``NO_ADMITTED_CORRIDOR_IN_DIRECTION``.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from src import phase2_territorial_structural_search_v3 as base

_BASE_VALIDATE = base.validate_rt021_bundle
REAL_RT006_EXPLICIT_FAILURE = (
    "NO_PHYSICAL_LOOPLESS_CORRIDOR_ADMITTED_WITHIN_VALIDATED_RT006_PARAMETER_GRID"
)


def _normalized_pair_results(pair_results: pd.DataFrame) -> pd.DataFrame:
    p = pair_results.copy().fillna("")
    required = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "gate_d_route_found",
    }
    missing = sorted(required - set(p.columns))
    if missing:
        raise ValueError(f"RT-021 pair results missing columns: {missing}")
    for column in (
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    ):
        p[column] = p[column].astype(str).str.strip()
    p["gate_d_route_found"] = [
        base._as_bool(value, field="gate_d_route_found")
        for value in p["gate_d_route_found"]
    ]
    return p


def explicit_rt006_missing_corridor_pair_ids(
    pair_results: pd.DataFrame,
    corridors: pd.DataFrame,
    *,
    require_real_rt021_pass: bool,
) -> set[str]:
    """Return road-reachable pairs with a valid explicit RT-006 no-corridor status.

    Fail closed on any road-reachable pair whose missing corridor evidence is
    silent or internally inconsistent.
    """
    p = _normalized_pair_results(pair_results)
    if "pair_id" not in corridors.columns:
        raise ValueError("RT-021 corridors missing pair_id")
    corridor_pair_ids = set(corridors["pair_id"].astype(str).str.strip())
    routed_pair_ids = set(p.loc[p["gate_d_route_found"], "pair_id"])
    missing_corridor_ids = routed_pair_ids - corridor_pair_ids
    if not missing_corridor_ids:
        return set()

    if "failure_reason" not in p.columns:
        raise ValueError(
            "Gate-D-reachable pair lacks corridor evidence and pair results expose no explicit failure_reason"
        )

    failures = p[p["pair_id"].isin(missing_corridor_ids)].copy()
    failures["failure_reason"] = failures["failure_reason"].astype(str).str.strip()
    silent = sorted(failures.loc[failures["failure_reason"].eq(""), "pair_id"])
    if silent:
        raise ValueError(
            "Gate-D-reachable pair has no retained corridor and no explicit RT-006 failure: "
            f"{silent[:20]}"
        )

    if "corridor_count" in failures.columns:
        counts = pd.to_numeric(failures["corridor_count"], errors="raise").astype(int)
        inconsistent = sorted(failures.loc[counts.ne(0), "pair_id"])
        if inconsistent:
            raise ValueError(
                "explicit RT-006 no-corridor pair reports nonzero corridor_count: "
                f"{inconsistent[:20]}"
            )

    if require_real_rt021_pass:
        wrong_reason = failures[
            failures["failure_reason"].ne(REAL_RT006_EXPLICIT_FAILURE)
        ]
        if not wrong_reason.empty:
            details = wrong_reason[["pair_id", "failure_reason"]].to_dict("records")
            raise ValueError(
                "real RT-021 missing-corridor direction has an unrecognized failure reason: "
                f"{details[:20]}"
            )

    return set(failures["pair_id"])


def validate_rt021_bundle_rt006_compatible(
    attachments: pd.DataFrame,
    pair_manifest: pd.DataFrame,
    pair_results: pd.DataFrame,
    corridors: pd.DataFrame,
    metadata: Mapping[str, object] | None = None,
    *,
    require_real_rt021_pass: bool = False,
) -> dict[str, object]:
    """Run the frozen RT-022 validator without conflating reachability and admission."""
    original_pairs = _normalized_pair_results(pair_results)
    explicit_failure_ids = explicit_rt006_missing_corridor_pair_ids(
        original_pairs,
        corridors,
        require_real_rt021_pass=require_real_rt021_pass,
    )

    # Compatibility view for the legacy validator only. This does NOT become
    # downstream evidence. It simply bypasses the obsolete invariant that every
    # Gate-D-reachable direction must have an RT-006 admitted corridor.
    validation_view = original_pairs.copy()
    if explicit_failure_ids:
        validation_view.loc[
            validation_view["pair_id"].isin(explicit_failure_ids),
            "gate_d_route_found",
        ] = False

    validated = _BASE_VALIDATE(
        attachments,
        pair_manifest,
        validation_view,
        corridors,
        metadata,
        require_real_rt021_pass=require_real_rt021_pass,
    )

    # Restore the actual frozen pair evidence before RT-009. RT-009 separately
    # checks admitted corridor count and therefore retains the correct status:
    # road reachable, but no admitted corridor in this direction.
    restored = original_pairs.sort_values("pair_id", kind="mergesort").reset_index(drop=True)
    validated["pair_results"] = restored
    validated["digests"]["pair_results_sha256"] = base.canonical_frame_sha256(
        restored,
        sort_by=["pair_id"],
    )
    validated["rt006_explicit_failure_compatibility"] = {
        "gate_d_route_found_preserved": True,
        "explicit_no_corridor_direction_count": len(explicit_failure_ids),
        "silent_missing_corridor_allowed": False,
        "real_failure_reason_contract": REAL_RT006_EXPLICIT_FAILURE,
    }
    return validated


def run_rt022_orchestrator_rt006_compatible(
    attachments: pd.DataFrame,
    pair_manifest: pd.DataFrame,
    pair_results: pd.DataFrame,
    corridors: pd.DataFrame,
    metadata: Mapping[str, object] | None = None,
    *,
    require_real_rt021_pass: bool = False,
    required_policy_groups: Sequence[str] = base.CORE_POLICY_GROUPS,
    min_edges: int = 1,
    max_edges: int | None = None,
    max_states: int = 100_000,
    max_structures: int = 20_000,
) -> dict[str, object]:
    """Run RT-022 with the explicit RT-006 failure semantic installed locally."""
    previous = base.validate_rt021_bundle
    base.validate_rt021_bundle = validate_rt021_bundle_rt006_compatible
    try:
        return base.run_rt022_orchestrator(
            attachments,
            pair_manifest,
            pair_results,
            corridors,
            metadata,
            require_real_rt021_pass=require_real_rt021_pass,
            required_policy_groups=required_policy_groups,
            min_edges=min_edges,
            max_edges=max_edges,
            max_states=max_states,
            max_structures=max_structures,
        )
    finally:
        base.validate_rt021_bundle = previous
