from __future__ import annotations

import pytest

from src.phase2_overpass_consistent_acquisition_v3 import (
    HistoricalOverpassLevelAcquirer,
    merge_consistent_tiles,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def node(version: int = 1):
    return {
        "type": "node",
        "id": 527417230,
        "lat": 45.73,
        "lon": 9.40,
        "version": version,
        "timestamp": "2026-09-05T12:00:00Z",
    }


def test_conflicting_backend_is_rejected_whole_and_next_backend_is_locked():
    calls = {"a": 0, "b": 0}

    def post(url, **kwargs):
        calls[url] += 1
        if url == "a":
            # All four tiles are acquired from A, then the merge detects that A
            # is internally inconsistent at the requested historical epoch.
            version = 2 if calls[url] == 2 else 1
            return FakeResponse({"elements": [node(version)]})
        return FakeResponse({"elements": [node(1)]})

    acquirer = HistoricalOverpassLevelAcquirer(
        endpoints=("a", "b"),
        snapshot_timestamp="2026-09-05T13:45:50Z",
        user_agent="test",
        attempts_per_tile=1,
        post=post,
        sleep=lambda _: None,
    )
    payload, used = acquirer.acquire_level_snapshot((45.0, 9.0, 46.0, 10.0))

    assert acquirer.locked_endpoint == "b"
    assert used == ["b", "b", "b", "b"]
    assert calls == {"a": 4, "b": 4}
    assert len(payload["elements"]) == 1
    assert payload["elements"][0]["version"] == 1


def test_locked_backend_is_used_for_later_levels_without_replica_switching():
    calls = {"a": 0, "b": 0}

    def post(url, **kwargs):
        calls[url] += 1
        if url == "a":
            # First level rejects A by an internal duplicate-object conflict.
            version = 2 if calls[url] == 2 else 1
            return FakeResponse({"elements": [node(version)]})
        return FakeResponse({"elements": [node(1)]})

    acquirer = HistoricalOverpassLevelAcquirer(
        endpoints=("a", "b"),
        snapshot_timestamp="2026-09-05T13:45:50Z",
        user_agent="test",
        attempts_per_tile=1,
        post=post,
        sleep=lambda _: None,
    )
    acquirer.acquire_level_snapshot((45.0, 9.0, 46.0, 10.0))
    calls_after_first = calls.copy()
    _, used = acquirer.acquire_level_snapshot((44.9, 8.9, 46.1, 10.1))

    assert used == ["b", "b", "b", "b"]
    assert calls["a"] == calls_after_first["a"]
    assert calls["b"] == calls_after_first["b"] + 4


def test_locked_backend_failure_fails_closed_instead_of_switching_mid_run():
    state = {"b_fail": False}
    calls = {"a": 0, "b": 0, "c": 0}

    def post(url, **kwargs):
        calls[url] += 1
        if url == "a":
            version = 2 if calls[url] == 2 else 1
            return FakeResponse({"elements": [node(version)]})
        if url == "b" and state["b_fail"]:
            raise RuntimeError("backend unavailable")
        return FakeResponse({"elements": [node(1)]})

    acquirer = HistoricalOverpassLevelAcquirer(
        endpoints=("a", "b", "c"),
        snapshot_timestamp="2026-09-05T13:45:50Z",
        user_agent="test",
        attempts_per_tile=1,
        post=post,
        sleep=lambda _: None,
    )
    acquirer.acquire_level_snapshot((45.0, 9.0, 46.0, 10.0))
    assert acquirer.locked_endpoint == "b"
    state["b_fail"] = True
    a_before, c_before = calls["a"], calls["c"]

    with pytest.raises(RuntimeError, match="backend unavailable"):
        acquirer.acquire_level_snapshot((44.9, 8.9, 46.1, 10.1))

    assert calls["a"] == a_before
    assert calls["c"] == c_before


def test_merge_rejects_conflicting_object_versions_even_with_same_id():
    with pytest.raises(AssertionError, match="conflicting OSM element versions"):
        merge_consistent_tiles([
            {"elements": [node(1)]},
            {"elements": [node(2)]},
        ])
