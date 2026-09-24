#!/usr/bin/env python3
"""Assemble Gate F v2 metrics from B, C+E, D and E fragments."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_assembly import build_assembly_manifest, write_assembly_manifest  # noqa: E402
from src.gate_f_inputs_v2 import assemble_gate_f_inputs_v2  # noqa: E402


def _inside_repo(path: Path) -> Path:
    resolved = (path if path.is_absolute() else ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Gate F v2 artifacts must stay inside repository: {resolved}") from exc
    return resolved


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--gate-b", type=Path, required=True)
    p.add_argument("--gate-c", type=Path, required=True)
    p.add_argument("--gate-d", type=Path, required=True)
    p.add_argument("--gate-e", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("outputs/gate_f_v2/scenario_metrics.csv"))
    p.add_argument("--exclusions-output", type=Path, default=Path("outputs/gate_f_v2/excluded_scenarios.csv"))
    p.add_argument("--manifest-output", type=Path, default=Path("outputs/gate_f_v2/assembly_manifest.json"))
    args = p.parse_args()
    try:
        catalog = _inside_repo(args.catalog)
        gate_b = _inside_repo(args.gate_b)
        gate_c = _inside_repo(args.gate_c)
        gate_d = _inside_repo(args.gate_d)
        gate_e = _inside_repo(args.gate_e)
        output = _inside_repo(args.output)
        exclusions = _inside_repo(args.exclusions_output)
        manifest_path = _inside_repo(args.manifest_output)
        eligible, excluded = assemble_gate_f_inputs_v2(catalog, gate_b, gate_c, gate_d, gate_e)
        output.parent.mkdir(parents=True, exist_ok=True)
        exclusions.parent.mkdir(parents=True, exist_ok=True)
        eligible.to_csv(output, index=False)
        excluded.to_csv(exclusions, index=False)
        manifest = build_assembly_manifest(
            repo_root=ROOT,
            inputs={"catalog": catalog, "gate_b": gate_b, "gate_c": gate_c, "gate_d": gate_d, "gate_e": gate_e},
            metrics_output=output,
            exclusions_output=exclusions,
            eligible=eligible,
            excluded=excluded,
        )
        manifest["gate_f_contract_version"] = "V2_REAL_UPSTREAM"
        write_assembly_manifest(manifest_path, manifest)
        print(f"Gate F v2 eligible scenarios: {len(eligible)}; excluded: {len(excluded)}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GATE_F_V2_ASSEMBLY_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
