#!/usr/bin/env python3
"""Canonicalise generated current-service CSV files to LF line endings.

Python's csv module defaults to CRLF. The repository canonicalises generated
text artifacts to LF so `git diff --check` remains meaningful and byte-for-byte
regression is platform-independent. This script changes line endings only.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def normalize_csv_line_endings(root: Path) -> tuple[int, int]:
    files = sorted(root.glob("*.csv"))
    if not files:
        raise RuntimeError(f"No CSV files found under {root}")
    changed = 0
    total = 0
    for path in files:
        payload = path.read_bytes()
        if b"\r" in payload.replace(b"\r\n", b""):
            raise RuntimeError(f"Unexpected bare CR byte in {path}")
        canonical = payload.replace(b"\r\n", b"\n")
        if canonical != payload:
            path.write_bytes(canonical)
            changed += 1
        total += 1
    return total, changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    total, changed = normalize_csv_line_endings(Path(args.output_dir))
    print(f"Canonicalised CSV line endings: files={total}, changed={changed}")


if __name__ == "__main__":
    main()
