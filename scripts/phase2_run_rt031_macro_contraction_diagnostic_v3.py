from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from phase2_macro_structure_decoupling_v3 import compile_macro_structures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e4", required=True)
    parser.add_argument("--e5", required=True)
    parser.add_argument("--e6", required=True)
    parser.add_argument("--realizations", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    frames = []
    for layer, path, expected in (
        ("E4", args.e4, 88),
        ("E5", args.e5, 4076),
        ("E6", args.e6, 108679),
    ):
        frame = pd.read_csv(path)
        if len(frame) != expected:
            raise ValueError(f"{layer} expected {expected}, got {len(frame)}")
        frame = frame.copy()
        frame["structural_layer"] = layer
        frames.append(frame)

    structures = pd.concat(frames, ignore_index=True)
    if len(structures) != 112843 or structures["structure_id"].astype(str).duplicated().any():
        raise ValueError("combined structure universe mismatch")

    realizations = pd.read_csv(args.realizations)
    summary, macro_edges, audit = compile_macro_structures(structures, realizations)
    meta = structures[["structure_id", "structural_layer", "topology_class"]]
    summary = summary.merge(meta, on="structure_id", validate="one_to_one").sort_values(
        "structure_id", kind="mergesort"
    ).reset_index(drop=True)
    macro_edges = macro_edges.merge(meta, on="structure_id", validate="many_to_one").sort_values(
        ["structure_id", "macro_edge_ordinal"], kind="mergesort"
    ).reset_index(drop=True)

    input_memberships = int(pd.to_numeric(structures["edge_count"]).sum())
    output_memberships = int(pd.to_numeric(macro_edges["elementary_link_count"]).sum())
    if input_memberships != output_memberships:
        raise ValueError("macro contraction did not preserve elementary link membership count")

    summary_path = outdir / "rt031_macro_structure_signatures.csv"
    edge_path = outdir / "rt031_macro_edge_chains.csv"
    summary.to_csv(summary_path, index=False, lineterminator="\n")
    macro_edges.to_csv(edge_path, index=False, lineterminator="\n")

    audit.update(
        {
            "status": "PASS_MACRO_CONTRACTION_DIAGNOSTIC_NOT_SEARCH_PASS",
            "layer_counts": {"E4": 88, "E5": 4076, "E6": 108679},
            "elementary_link_membership_count_input": input_memberships,
            "elementary_link_membership_count_output": output_memberships,
            "macro_topology_counts": {
                str(key): int(value)
                for key, value in summary["macro_topology_class"].value_counts().sort_index().items()
            },
            "max_elementary_links_per_macro_edge": int(macro_edges["elementary_link_count"].max()),
            "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            "macro_edges_sha256": hashlib.sha256(edge_path.read_bytes()).hexdigest(),
            "negative_assertions": {
                "selects_network": False,
                "uses_municipality_for_contraction": False,
                "infers_service_terminals": False,
                "deletes_passenger_vertices": False,
                "changes_rt023_geometry": False,
                "claims_rt031_search_pass": False,
            },
        }
    )
    audit_path = outdir / "rt031_macro_contraction_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
