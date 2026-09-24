#!/usr/bin/env python3
"""Normalize known UTF-8-as-Latin-1 mojibake in generated Phase 2 text outputs.

The official ISTAT 2026 municipal shapefile is read through GDAL/pyogrio. On some
runner stacks its DBF text encoding can be interpreted as Latin-1 even when the
original municipality name bytes are UTF-8, yielding strings such as `BarzanÃ²`.
This post-generation normalization changes text labels only, never codes, flows,
coordinates or classifications. It fails if suspicious mojibake markers remain.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "outputs/phase2/od_2021_destinations_by_origin.csv",
    ROOT / "outputs/phase2/od_2021_top_destinations_aggregate.csv",
    ROOT / "outputs/phase2/od_2021_inbound_origins_by_destination.csv",
    ROOT / "outputs/phase2/s8_station_municipalities.csv",
    ROOT / "docs/PHASE2_DEMAND_PROFILE_2021.md",
]

# UTF-8 byte sequences commonly mis-decoded as Latin-1/Windows-1252 for Italian
# municipality names. Keeping this mapping explicit makes the transformation
# auditable and prevents any change to numeric evidence.
REPLACEMENTS = {
    "Ã€": "À",
    "Ãˆ": "È",
    "Ã‰": "É",
    "ÃŒ": "Ì",
    "Ã’": "Ò",
    "Ã™": "Ù",
    "Ã ": "à",
    "Ã¨": "è",
    "Ã©": "é",
    "Ã¬": "ì",
    "Ã²": "ò",
    "Ã¹": "ù",
    "Ã§": "ç",
    "Ãª": "ê",
    "Ã´": "ô",
    "Â°": "°",
    "Âª": "ª",
}
SUSPICIOUS = ("Ã", "Â")


def normalize(text: str) -> str:
    for broken, fixed in REPLACEMENTS.items():
        text = text.replace(broken, fixed)
    return text


def main() -> int:
    changed = []
    for path in TARGETS:
        if not path.exists():
            raise FileNotFoundError(path)
        original = path.read_text(encoding="utf-8")
        cleaned = normalize(original)
        if any(marker in cleaned for marker in SUSPICIOUS):
            sample = next(line for line in cleaned.splitlines() if any(m in line for m in SUSPICIOUS))
            raise RuntimeError(f"Unresolved text-encoding marker in {path}: {sample[:240]}")
        if cleaned != original:
            path.write_text(cleaned, encoding="utf-8", newline="")
            changed.append(str(path.relative_to(ROOT)))
    print(f"normalized text labels in {len(changed)} files: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
