#!/usr/bin/env python3
"""Persist the fail-closed RT-022 status before RT-021 real-corpus handoff."""
from __future__ import annotations

import json
from pathlib import Path

from src.phase2_territorial_structural_search_v3 import prepared_status_record


def main() -> int:
    out = Path("outputs/phase2/rt022_territorial_structural_search_v3")
    out.mkdir(parents=True, exist_ok=True)
    status = prepared_status_record()
    path = out / "rt022_prepared_status.json"
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
