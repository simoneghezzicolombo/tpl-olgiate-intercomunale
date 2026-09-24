from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from phase2_rt031_hamiltonian_expressiveness_v3 import sha256_file, write_outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reciprocal-links", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--expected-sha256", default=None)
    args = parser.parse_args()
    source = Path(args.reciprocal_links)
    digest = sha256_file(source)
    if args.expected_sha256 and digest != args.expected_sha256:
        raise SystemExit(f"reciprocal-link SHA256 mismatch: expected {args.expected_sha256}, got {digest}")
    audit = write_outputs(pd.read_csv(source), reciprocal_link_file_sha256=digest, outdir=args.outdir)
    print(audit["status"])
    print(f"Hamiltonian path feasible: {audit['hamiltonian_path_feasible']}")
    print(f"Hamiltonian cycle feasible: {audit['hamiltonian_cycle_feasible']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
