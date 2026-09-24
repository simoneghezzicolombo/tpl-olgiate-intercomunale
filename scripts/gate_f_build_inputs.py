#!/usr/bin/env python3
"""Build the canonical Gate F scenario table from upstream gate fragments."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_f_assembly import build_assembly_manifest, write_assembly_manifest  # noqa: E402
from src.gate_f_inputs import assemble_gate_f_inputs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--gate-b", required=True, type=Path)
    parser.add_argument("--gate-c", required=True, type=Path)
    parser.add_argument("--gate-d", required=True, type=Path)
    parser.add_argument("--gate-e", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/gate_f_scenario_metrics.csv"))
    parser.add_argument("--exclusions-output", type=Path, default=Path("outputs/gate_f/excluded_scenarios.csv"))
    parser.add_argument("--manifest-output", type=Path, default=Path("outputs/gate_f/assembly_manifest.json"))
    return parser.parse_args()


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    catalog = _rooted(args.catalog)
    gate_b = _rooted(args.gate_b)
    gate_c = _rooted(args.gate_c)
    gate_d = _rooted(args.gate_d)
    gate_e = _rooted(args.gate_e)
    output = _rooted(args.output)
    exclusions_output = _rooted(args.exclusions_output)
    manifest_output = _rooted(args.manifest_output)
    try:
        eligible, excluded = assemble_gate_f_inputs(catalog, gate_b, gate_c, gate_d, gate_e)
        output.parent.mkdir(parents=True, exist_ok=True)
        eligible.to_csv(output, index=False)
        exclusions_output.parent.mkdir(parents=True, exist_ok=True)
        excluded.to_csv(exclusions_output, index=False)
        manifest = build_assembly_manifest(
            repo_root=ROOT,
            inputs={"catalog": catalog, "gate_b": gate_b, "gate_c": gate_c, "gate_d": gate_d, "gate_e": gate_e},
            metrics_output=output,
            exclusions_output=exclusions_output,
            eligible=eligible,
            excluded=excluded,
        )
        write_assembly_manifest(manifest_output, manifest)
    except (OSError, ValueError) as exc:
        print(f"GATE_F_INPUT_FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"Gate F canonical scenario table written: {output} ({len(eligible)} eligible)")
    print(f"Gate F exclusions written: {exclusions_output} ({len(excluded)} excluded)")
    print(f"Gate F deterministic assembly manifest written: {manifest_output}")
    warning = manifest["comparison_scope"]["candidate_diversity_warning"]
    if warning:
        print(f"GATE_F_SCOPE_WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
