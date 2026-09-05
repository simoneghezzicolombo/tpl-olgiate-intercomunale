"""Complete directed terminal-pair request and execution coverage contract V3."""
from __future__ import annotations

import hashlib

import pandas as pd


CONTRACT = "COMPLETE_DIRECTED_PAIR_TEST_UNIVERSE_NOT_NETWORK_SELECTION"
CAP_STATUS = "BLOCKED_COMPLETE_PAIR_MANIFEST_EXCEEDS_TECHNICAL_CAP"
EXECUTION_BLOCKED = "BLOCKED_INCOMPLETE_OR_INVALID_PAIR_EXECUTION"


def directed_pair_id(source: str, target: str) -> str:
    source = str(source).strip()
    target = str(target).strip()
    if not source or not target or source == target:
        raise ValueError("directed pair requires two distinct non-empty terminal IDs")
    digest = hashlib.sha256(f"{source}->{target}".encode("utf-8")).hexdigest()[:16].upper()
    return f"DIR_PAIR_{digest}"


def build_complete_directed_pair_manifest(
    terminals: pd.DataFrame,
    *,
    max_directed_pairs: int = 10_000,
) -> dict:
    if "routing_terminal_id" not in terminals.columns:
        raise ValueError("terminal universe missing routing_terminal_id")
    if max_directed_pairs < 1:
        raise ValueError("max_directed_pairs must be >= 1")

    terminal_ids = [str(value).strip() for value in terminals["routing_terminal_id"]]
    if any(not terminal_id for terminal_id in terminal_ids):
        raise ValueError("blank routing_terminal_id")
    if len(terminal_ids) != len(set(terminal_ids)):
        raise ValueError("routing_terminal_id must be unique")
    terminal_ids = sorted(terminal_ids)

    expected_count = len(terminal_ids) * max(len(terminal_ids) - 1, 0)
    if expected_count > max_directed_pairs:
        return {
            "status": CAP_STATUS,
            "complete": False,
            "manifest": pd.DataFrame(
                columns=[
                    "pair_id",
                    "source_routing_terminal_id",
                    "target_routing_terminal_id",
                    "reverse_pair_id",
                    "scope",
                ]
            ),
            "terminal_count": len(terminal_ids),
            "required_directed_pair_count": expected_count,
            "max_directed_pairs": max_directed_pairs,
            "contract": CONTRACT,
            "partial_manifest_returned": False,
        }

    rows: list[dict] = []
    for source in terminal_ids:
        for target in terminal_ids:
            if source == target:
                continue
            rows.append(
                {
                    "pair_id": directed_pair_id(source, target),
                    "source_routing_terminal_id": source,
                    "target_routing_terminal_id": target,
                    "reverse_pair_id": directed_pair_id(target, source),
                    "scope": CONTRACT,
                }
            )
    manifest = pd.DataFrame(rows).sort_values(
        ["source_routing_terminal_id", "target_routing_terminal_id"],
        kind="mergesort",
    ).reset_index(drop=True)

    return {
        "status": "PASS_COMPLETE_DIRECTED_PAIR_MANIFEST",
        "complete": True,
        "manifest": manifest,
        "terminal_count": len(terminal_ids),
        "directed_pair_count": len(manifest),
        "unordered_pair_count": len(manifest) // 2,
        "max_directed_pairs": max_directed_pairs,
        "contract": CONTRACT,
        "pair_selection_semantics": "ALL_ORDERED_NONSELF_PAIRS_NO_GEOGRAPHIC_OR_TOPOLOGIC_FILTER",
    }


def audit_pair_execution_completeness(
    manifest: pd.DataFrame,
    pair_results: pd.DataFrame,
) -> dict:
    required_manifest_cols = {
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
    }
    missing_manifest_cols = required_manifest_cols - set(manifest.columns)
    if missing_manifest_cols:
        raise ValueError(f"manifest missing columns: {sorted(missing_manifest_cols)}")

    required_result_cols = required_manifest_cols
    missing_result_cols = required_result_cols - set(pair_results.columns)
    if missing_result_cols:
        raise ValueError(f"pair results missing columns: {sorted(missing_result_cols)}")

    m = manifest.copy().fillna("")
    r = pair_results.copy().fillna("")
    for frame, label in [(m, "manifest"), (r, "pair results")]:
        for col in required_manifest_cols:
            frame[col] = frame[col].astype(str).str.strip()
            if frame[col].eq("").any():
                raise ValueError(f"blank {col} in {label}")

    manifest_duplicates = sorted(m.loc[m["pair_id"].duplicated(keep=False), "pair_id"].unique())
    result_duplicates = sorted(r.loc[r["pair_id"].duplicated(keep=False), "pair_id"].unique())

    manifest_ids = set(m["pair_id"])
    result_ids = set(r["pair_id"])
    missing_result_ids = sorted(manifest_ids - result_ids)
    unexpected_result_ids = sorted(result_ids - manifest_ids)

    manifest_by_id = m.set_index("pair_id") if not manifest_duplicates else None
    result_by_id = r.set_index("pair_id") if not result_duplicates else None
    endpoint_mismatches: list[str] = []
    if manifest_by_id is not None and result_by_id is not None:
        for pair_id in sorted(manifest_ids & result_ids):
            expected = manifest_by_id.loc[pair_id]
            observed = result_by_id.loc[pair_id]
            if (
                str(expected["source_routing_terminal_id"])
                != str(observed["source_routing_terminal_id"])
                or str(expected["target_routing_terminal_id"])
                != str(observed["target_routing_terminal_id"])
            ):
                endpoint_mismatches.append(pair_id)

    issues = {
        "manifest_duplicate_pair_ids": manifest_duplicates,
        "result_duplicate_pair_ids": result_duplicates,
        "missing_result_pair_ids": missing_result_ids,
        "unexpected_result_pair_ids": unexpected_result_ids,
        "endpoint_mismatch_pair_ids": endpoint_mismatches,
    }
    complete = not any(issues.values())
    return {
        "status": "PASS_COMPLETE_PAIR_EXECUTION" if complete else EXECUTION_BLOCKED,
        "complete": complete,
        "manifest_pair_count": len(m),
        "result_pair_count": len(r),
        **issues,
        "missing_result_semantics": "MISSING_OUTPUT_IS_INCOMPLETE_EXECUTION_NOT_NO_ROUTE",
        "contract": CONTRACT,
    }
