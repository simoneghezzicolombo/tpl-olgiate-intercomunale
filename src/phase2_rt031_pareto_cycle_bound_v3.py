from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

STATUS = "PASS_SAFE_PARETO_CYCLE_RANK_BOUND_DIAGNOSTIC_NOT_SEARCH_PASS"


class CycleBoundError(ValueError):
    pass


def _ids(value: object) -> tuple[str, ...]:
    out = tuple(x.strip() for x in str(value).split(";") if x.strip())
    if not out:
        raise CycleBoundError("empty stop sequence")
    return out


def derive(
    links: pd.DataFrame,
    patterns: pd.DataFrame,
    realizations: pd.DataFrame,
    *,
    expected_vertices: int = 35,
    expected_links: int = 110,
) -> tuple[pd.DataFrame, dict[str, object]]:
    required = (
        (links, {"structural_link_id", "terminal_a", "terminal_b"}, "links"),
        (patterns, {"realization_id", "structural_link_id", "direction", "alternative_ordinal", "ordered_passenger_stop_ids"}, "patterns"),
        (realizations, {"structural_link_id", "direction", "distance_m"}, "realizations"),
    )
    for frame, columns, label in required:
        missing = sorted(columns - set(frame.columns))
        if missing:
            raise CycleBoundError(f"{label} missing {missing}")
    if len(links) != expected_links or links.structural_link_id.astype(str).nunique() != expected_links:
        raise CycleBoundError("unexpected structural-link universe")
    vertices = sorted(set(links.terminal_a.astype(str)) | set(links.terminal_b.astype(str)))
    if len(vertices) != expected_vertices:
        raise CycleBoundError("unexpected vertex universe")
    endpoints = {
        str(row.structural_link_id): {str(row.terminal_a), str(row.terminal_b)}
        for row in links.itertuples(index=False)
    }
    if set(patterns.structural_link_id.astype(str)) != set(endpoints):
        raise CycleBoundError("pattern link universe mismatch")
    if set(realizations.structural_link_id.astype(str)) != set(endpoints):
        raise CycleBoundError("realization link universe mismatch")

    r = realizations.copy()
    r["distance_m"] = pd.to_numeric(r["distance_m"], errors="coerce")
    burden = (
        r.groupby(["structural_link_id", "direction"], sort=True)["distance_m"].min()
        .groupby("structural_link_id").sum()
    )
    if burden.isna().any() or (burden <= 0).any():
        raise CycleBoundError("lower-envelope link burden must be strictly positive")

    rows = []
    global_interiors: set[str] = set()
    for link_id, group in patterns.groupby("structural_link_id", sort=True):
        directional = []
        for _, direction_group in group.groupby("direction", sort=True):
            alternatives = [set(_ids(value)) for value in direction_group["ordered_passenger_stop_ids"]]
            directional.append(set.intersection(*alternatives))
        guaranteed = set.union(*directional)
        if not endpoints[str(link_id)].issubset(guaranteed):
            raise CycleBoundError(f"{link_id} endpoints not guaranteed")
        interior = sorted(guaranteed - endpoints[str(link_id)])
        global_interiors.update(interior)
        rows.append({
            "structural_link_id": str(link_id),
            "guaranteed_interior_stop_ids": ";".join(interior),
            "guaranteed_interior_stop_count": len(interior),
            "minimum_bidirectional_link_distance_m": float(burden.loc[str(link_id)]),
        })

    edge_table = pd.DataFrame(rows).sort_values("structural_link_id", kind="mergesort").reset_index(drop=True)
    bound = len(global_interiors)
    audit = {
        "status": STATUS,
        "structural_vertex_universe_count": len(vertices),
        "structural_link_universe_count": len(links),
        "global_guaranteed_interior_stop_ids": sorted(global_interiors),
        "global_guaranteed_interior_stop_count": bound,
        "safe_pareto_cycle_rank_upper_bound": bound,
        "safe_pareto_elementary_edge_upper_bound": len(vertices) - 1 + bound,
        "strictly_positive_lower_envelope_burden_all_links": True,
        "proof": "Under the current RT-029 access/equity/P90 plus strictly-positive additive lower-envelope distance burden, deleting any non-bridge edge whose guaranteed passenger stops are all served by the remaining connected graph preserves all access metrics and strictly lowers burden. Each cycle-rank basis therefore needs a distinct exclusive interior passenger-stop identity. Hence cycle_rank cannot exceed the global number of possible guaranteed interior identities.",
        "scope_caveat": "This dominance bound is lossless only under the current objective semantics. It must be recomputed if a future objective rewards redundancy, cycle robustness, frequency, transfers or another benefit of retaining cycle edges.",
        "negative_assertions": {
            "imposes_topology_preference": False,
            "sets_arbitrary_cycle_cap": False,
            "sets_arbitrary_elementary_edge_cap": False,
            "selects_network": False,
            "uses_random_search": False,
        },
    }
    return edge_table, audit


def write_outputs(links: pd.DataFrame, patterns: pd.DataFrame, realizations: pd.DataFrame, outdir: str | Path) -> dict[str, object]:
    table, audit = derive(links, patterns, realizations)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "rt031_edge_guaranteed_interior_stop_evidence.csv", index=False, lineterminator="\n")
    (out / "rt031_safe_pareto_cycle_bound_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit
