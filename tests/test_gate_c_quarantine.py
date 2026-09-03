from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_live_bus_module():
    path = ROOT / "scripts" / "gate_c_live_bus_timetables.py"
    spec = importlib.util.spec_from_file_location("gate_c_live_bus_timetables", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_timetable_note_date_semantics():
    module = _load_live_bus_module()
    assert module._note_allows("A", date(2026, 8, 1)) is False
    assert module._note_allows("A", date(2026, 9, 3)) is True
    assert module._note_allows("B", date(2026, 8, 1)) is True
    assert module._note_allows("B", date(2026, 9, 3)) is False
    assert module._note_allows("D", date(2026, 8, 1)) is False  # Saturday in exception window
    assert module._note_allows("D", date(2026, 8, 3)) is True
    assert module._note_allows("D", date(2026, 9, 5)) is True  # Saturday after exception window
    assert module._note_allows("V", date(2026, 9, 3)) is True


def test_invalidated_legacy_transit_scripts_fail_closed():
    for relative in (
        "scripts/02_parse_gtfs.py",
        "scripts/05_current_service.py",
        "scripts/11_train_coordination.py",
    ):
        completed = subprocess.run(
            [sys.executable, str(ROOT / relative)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode != 0, relative
        assert "fail-closed" in completed.stderr.lower(), (relative, completed.stderr)


def test_quarantined_scripts_do_not_import_invalidated_engines():
    contents = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "scripts/02_parse_gtfs.py",
            "scripts/05_current_service.py",
            "scripts/11_train_coordination.py",
        )
    )
    assert "from src.gtfs_loader" not in contents
    assert "from src.timetable_engine" not in contents
    assert "network_2026_emergency" in contents  # retained only in explicit invalidation explanation
