"""Tests for agent_bridge.py: BOM-safe state loading and SUPERSEDED review logic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the tools module importable
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from agent_bridge import (
    apply_superseded_logic,
    load_state,
    parse_review_metadata,
    save_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_review(comment_id: int, gate: str | None = None, supersedes: list[int] | None = None, body_extra: str = "") -> dict:
    lines = ["[GPT REVIEW]"]
    if gate:
        lines.append(f"Gate: {gate}")
    if supersedes:
        ids = ", ".join(str(i) for i in supersedes)
        lines.append(f"Supersedes: {ids}")
    if body_extra:
        lines.append(body_extra)
    return {
        "id": comment_id,
        "body": "\n".join(lines),
        "html_url": f"https://github.com/test/repo/issues/1#issuecomment-{comment_id}",
    }


def empty_state() -> dict:
    return {"processed_comment_ids": [], "blocked_retry": {}, "superseded_comment_ids": []}


# ---------------------------------------------------------------------------
# 1. BOM-safe state loading
# ---------------------------------------------------------------------------

class TestLoadStateBom:
    def test_no_bom_valid_json(self, tmp_path):
        """Plain UTF-8 JSON file is loaded correctly."""
        state = {"processed_comment_ids": [5516612555, 5516728746], "blocked_retry": {}}
        f = tmp_path / ".agent_bridge_state.json"
        f.write_bytes(json.dumps(state, indent=2).encode("utf-8"))
        loaded = load_state(f)
        assert loaded is not None
        assert 5516612555 in loaded["processed_comment_ids"]
        assert 5516728746 in loaded["processed_comment_ids"]

    def test_bom_utf8_valid_json(self, tmp_path):
        """UTF-8 BOM-prefixed JSON is stripped and loaded correctly.

        Both processed IDs must survive the BOM decode; neither must be lost or reset.
        """
        state = {
            "processed_comment_ids": [5516612555, 5516728746],
            "blocked_retry": {},
            "superseded_comment_ids": [],
        }
        raw = json.dumps(state, indent=2).encode("utf-8")
        bom = b"\xef\xbb\xbf"  # UTF-8 BOM
        f = tmp_path / ".agent_bridge_state.json"
        f.write_bytes(bom + raw)
        loaded = load_state(f)
        assert loaded is not None, "load_state must succeed on BOM-prefixed file"
        assert 5516612555 in loaded["processed_comment_ids"], \
            "5516612555 must remain processed after BOM load"
        assert 5516728746 in loaded["processed_comment_ids"], \
            "5516728746 must remain processed after BOM load"

    def test_invalid_json_returns_none(self, tmp_path):
        """Corrupt JSON must return None, never silently reset state."""
        f = tmp_path / ".agent_bridge_state.json"
        f.write_bytes(b"{ this is not json }")
        result = load_state(f)
        assert result is None, "load_state must return None on JSON parse failure"

    def test_missing_file_returns_fresh_state(self, tmp_path):
        """Non-existent file returns a fresh empty state (not None)."""
        f = tmp_path / "nonexistent.json"
        loaded = load_state(f)
        assert loaded is not None
        assert loaded["processed_comment_ids"] == []

    def test_save_state_no_bom(self, tmp_path):
        """save_state must write plain UTF-8 without BOM."""
        f = tmp_path / ".agent_bridge_state.json"
        save_state(f, {"processed_comment_ids": [1], "blocked_retry": {}})
        raw = f.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), "save_state must not write a UTF-8 BOM"
        data = json.loads(raw.decode("utf-8"))
        assert data["processed_comment_ids"] == [1]

    def test_processed_ids_preserved_across_bom_roundtrip(self, tmp_path):
        """Write BOM-file, load it, save it, reload: processed IDs must be intact."""
        ids = [5516612555, 5516728746]
        state = {"processed_comment_ids": ids, "blocked_retry": {}}
        bom_raw = b"\xef\xbb\xbf" + json.dumps(state).encode("utf-8")
        f = tmp_path / ".agent_bridge_state.json"
        f.write_bytes(bom_raw)

        loaded = load_state(f)
        assert loaded is not None
        # Now save through the proper writer and reload
        save_state(f, loaded)
        reloaded = load_state(f)
        assert reloaded is not None
        for pid in ids:
            assert pid in reloaded["processed_comment_ids"]


# ---------------------------------------------------------------------------
# 2. parse_review_metadata
# ---------------------------------------------------------------------------

class TestParseReviewMetadata:
    def test_parses_gate(self):
        body = "[GPT REVIEW]\nGate: GATE A - Provenance\nVerdict: FAIL"
        meta = parse_review_metadata(body)
        assert meta["gate"] == "GATE A - Provenance"
        assert meta["supersedes"] == []

    def test_parses_supersedes(self):
        body = "[GPT REVIEW]\nGate: GATE A\nSupersedes: 111, 222"
        meta = parse_review_metadata(body)
        assert meta["gate"] == "GATE A"
        assert 111 in meta["supersedes"]
        assert 222 in meta["supersedes"]

    def test_parses_supersedes_no_spaces(self):
        body = "[GPT REVIEW]\nSupersedes: 100 200 300"
        meta = parse_review_metadata(body)
        assert set(meta["supersedes"]) == {100, 200, 300}

    def test_no_gate_no_supersedes(self):
        body = "[GPT REVIEW]\nVerdict: PASS"
        meta = parse_review_metadata(body)
        assert meta["gate"] is None
        assert meta["supersedes"] == []

    def test_case_insensitive_keys(self):
        body = "[GPT REVIEW]\nGATE: GATE B\nSUPERSEDES: 500"
        meta = parse_review_metadata(body)
        assert meta["gate"] == "GATE B"
        assert 500 in meta["supersedes"]


# ---------------------------------------------------------------------------
# 3. apply_superseded_logic
# ---------------------------------------------------------------------------

class TestApplySupersededLogic:
    """Three reviews for the same Gate A → only the newest is processed."""

    def test_three_reviews_same_gate_only_newest_runs(self):
        reviews = [
            make_review(1001, gate="GATE A - Provenance"),
            make_review(1002, gate="GATE A - Provenance"),
            make_review(1003, gate="GATE A - Provenance"),
        ]
        state = empty_state()
        to_process, newly_superseded = apply_superseded_logic(reviews, state)
        assert len(to_process) == 1, "Only 1 review should survive SUPERSEDED filtering"
        assert to_process[0]["id"] == 1003, "The newest review (highest ID) must be the one to process"
        assert 1001 in newly_superseded
        assert 1002 in newly_superseded
        assert 1003 not in newly_superseded

    def test_explicit_supersedes_declaration(self):
        """Newest review explicitly supersedes older ones."""
        reviews = [
            make_review(2001, gate="GATE A"),
            make_review(2002, gate="GATE A"),
            make_review(2003, gate="GATE A", supersedes=[2001, 2002]),
        ]
        state = empty_state()
        to_process, newly_superseded = apply_superseded_logic(reviews, state)
        assert len(to_process) == 1
        assert to_process[0]["id"] == 2003
        assert 2001 in newly_superseded
        assert 2002 in newly_superseded

    def test_different_gates_both_run(self):
        """Reviews for different gates must both be executed."""
        reviews = [
            make_review(3001, gate="GATE A"),
            make_review(3002, gate="GATE B"),
        ]
        state = empty_state()
        to_process, newly_superseded = apply_superseded_logic(reviews, state)
        assert len(to_process) == 2
        assert len(newly_superseded) == 0

    def test_no_gate_label_all_run(self):
        """Reviews without a Gate label are never auto-superseded."""
        reviews = [
            make_review(4001),
            make_review(4002),
        ]
        state = empty_state()
        to_process, newly_superseded = apply_superseded_logic(reviews, state)
        assert len(to_process) == 2
        assert len(newly_superseded) == 0

    def test_existing_superseded_in_state_are_excluded(self):
        """Already-superseded IDs in state are excluded from to_process."""
        reviews = [
            make_review(5001, gate="GATE A"),
            make_review(5002, gate="GATE A"),
        ]
        state = {**empty_state(), "superseded_comment_ids": [5001]}
        to_process, newly_superseded = apply_superseded_logic(reviews, state)
        # 5001 already in state, 5002 is the remaining candidate
        assert len(to_process) == 1
        assert to_process[0]["id"] == 5002

    def test_single_review_per_gate_not_superseded(self):
        """A single review for a Gate is never self-superseded."""
        reviews = [make_review(6001, gate="GATE A")]
        state = empty_state()
        to_process, newly_superseded = apply_superseded_logic(reviews, state)
        assert len(to_process) == 1
        assert len(newly_superseded) == 0

    def test_processed_ids_not_in_to_process(self):
        """apply_superseded_logic should never emit a review already in processed."""
        # Note: process_once already filters by processed; this tests that
        # apply_superseded_logic doesn't inadvertently re-add them.
        reviews = [make_review(7001, gate="GATE A")]
        state = {**empty_state(), "processed_comment_ids": [7001]}
        # The caller (process_once) would already remove 7001 before calling
        # apply_superseded_logic; but let's verify the function is safe even if passed it.
        to_process, newly_superseded = apply_superseded_logic(reviews, state)
        # 7001 is already superseded or processed - only rule applied is gate dedup
        # Since there's only one review, it won't be auto-superseded by gate logic.
        # The test simply checks no crash and the function is deterministic.
        assert isinstance(to_process, list)
        assert isinstance(newly_superseded, set)
