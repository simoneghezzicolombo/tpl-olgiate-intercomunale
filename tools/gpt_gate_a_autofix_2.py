#!/usr/bin/env python3
from pathlib import Path

path = Path("scripts/audit_01_fetch_real_inputs.py")
text = path.read_text(encoding="utf-8")
old = "without local/manual dependencies"
new = "without pre-existing local files or interactive acquisition"
count = text.count(old)
if count != 1:
    raise RuntimeError(f"Expected one POSAS provenance wording match, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Updated POSAS provenance wording.")
