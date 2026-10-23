"""Append-only surface identity ledger migration and crash-recovery tests."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import orjson
import pytest

from game.world.surface_identity import (
    LEDGER_FILENAME,
    LEDGER_LOG_FILENAME,
    SurfaceIdentityLedger,
)


def test_legacy_json_checkpoint_migrates_without_rewriting_per_chunk() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old = {"version": 1, "assignments": {"legacy": 0x80000001}}
        checkpoint = root / LEDGER_FILENAME
        checkpoint.write_text(json.dumps(old), encoding="utf-8")
        original_bytes = checkpoint.read_bytes()

        ledger = SurfaceIdentityLedger.load_or_create(directory)
        assert ledger.id_for("legacy") == 0x80000001
        assigned = ledger.reserve_many(("new-a", "new-b"))
        assert len(set(assigned.values())) == 2
        assert checkpoint.read_bytes() == original_bytes
        log = root / LEDGER_LOG_FILENAME
        assert log.exists()
        assert log.read_bytes().count(b"\n") == 1

        loaded = SurfaceIdentityLedger.load_or_create(directory)
        assert loaded.id_for("legacy") == 0x80000001
        assert all(loaded.id_for(key) == value for key, value in assigned.items())

        # Explicit compaction moves all reservations into an orjson
        # checkpoint; removing the replay log never loses the older ones.
        loaded.compact()
        assert log.read_bytes() == b""
        assert (
            orjson.loads(checkpoint.read_bytes())["assignments"]["legacy"] == 0x80000001
        )
        again = SurfaceIdentityLedger.load_or_create(directory)
        assert again.to_dict() == loaded.to_dict()


def test_append_cost_independent_of_checkpoint_actor_count() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old = {
            "version": 1,
            "assignments": {f"actor-{idx}": 0x80000000 + idx for idx in range(10_000)},
        }
        checkpoint = root / LEDGER_FILENAME
        checkpoint.write_bytes(orjson.dumps(old))
        original_bytes = checkpoint.read_bytes()
        ledger = SurfaceIdentityLedger.load_or_create(directory)

        allocated = ledger.reserve_many(("new-a", "new-b"))
        assert checkpoint.read_bytes() == original_bytes
        log_bytes = (root / LEDGER_LOG_FILENAME).read_bytes()
        assert len(log_bytes) < 500
        assert log_bytes.count(b"\n") == 1
        recovered = SurfaceIdentityLedger.load_or_create(directory)
        assert recovered.id_for("actor-9999") == 0x80000000 + 9999
        assert all(recovered.id_for(key) == value for key, value in allocated.items())


def test_interrupted_tail_is_discarded_before_following_appends(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        ledger = SurfaceIdentityLedger.load_or_create(directory)
        first = ledger.reserve("actor-a")
        log = Path(directory) / LEDGER_LOG_FILENAME
        with log.open("ab") as handle:
            handle.write(b'{"version":1,"assignments":{"interrupted":')
        recovered = SurfaceIdentityLedger.load_or_create(directory)
        assert recovered.id_for("actor-a") == first
        assert recovered.id_for("interrupted") is None
        assert b"interrupted" not in log.read_bytes()
        assert "incomplete identity log tail" in caplog.text

        second = recovered.reserve("actor-b")
        fully_recovered = SurfaceIdentityLedger.load_or_create(directory)
        assert fully_recovered.id_for("actor-a") == first
        assert fully_recovered.id_for("actor-b") == second
        assert log.read_bytes().count(b"\n") == 2


def test_bad_complete_log_record_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as directory:
        ledger = SurfaceIdentityLedger.load_or_create(directory)
        ledger.reserve("actor-a")
        log = Path(directory) / LEDGER_LOG_FILENAME
        with log.open("ab") as handle:
            handle.write(b'{"version":1,"assignments":{},"sha256":"invalid"}\n')
        with pytest.raises(ValueError, match="checksum"):
            SurfaceIdentityLedger.load_or_create(directory)


def test_compaction_crash_window_replays_duplicate_batches() -> None:
    with tempfile.TemporaryDirectory() as directory:
        ledger = SurfaceIdentityLedger.load_or_create(directory)
        allocated = ledger.reserve_many(("actor-a", "actor-b"))
        log = Path(directory) / LEDGER_LOG_FILENAME
        before_compaction = log.read_bytes()

        # Model a crash just after the atomic checkpoint replacement but
        # before old, now-redundant log records were trimmed.
        ledger.compact()
        log.write_bytes(before_compaction)
        recovered = SurfaceIdentityLedger.load_or_create(directory)
        assert recovered.to_dict() == ledger.to_dict()
        assert all(recovered.id_for(key) == value for key, value in allocated.items())

        recovered.compact()
        assert log.stat().st_size == 0
        assert (
            SurfaceIdentityLedger.load_or_create(directory).to_dict()
            == recovered.to_dict()
        )


def test_successful_append_followed_by_reported_failure_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        ledger = SurfaceIdentityLedger.load_or_create(directory)
        original = ledger._append_batch

        def append_then_fail(batch: dict[str, int]) -> None:
            original(batch)
            raise OSError("fsync status unknown")

        monkeypatch.setattr(ledger, "_append_batch", append_then_fail)
        with pytest.raises(OSError, match="fsync status unknown"):
            ledger.reserve_many(("survivor",))
        assert ledger.id_for("survivor") is None
        with pytest.raises(RuntimeError, match="reload"):
            ledger.reserve_many(("another",))

        # Even if a full record made it to disk before an I/O exception,
        # the next load recovers its immutable reservation.
        recovered = SurfaceIdentityLedger.load_or_create(directory)
        assigned = recovered.id_for("survivor")
        assert assigned is not None
        assert recovered.reserve("survivor") == assigned


def test_log_rejects_conflicting_record_after_valid_checksum() -> None:
    with tempfile.TemporaryDirectory() as directory:
        ledger = SurfaceIdentityLedger.load_or_create(directory)
        existing = ledger.reserve("actor-a")
        body: dict[str, Any] = {
            "version": 1,
            "assignments": {"actor-b": existing},
        }
        checksum = hashlib.sha256(
            orjson.dumps(body, option=orjson.OPT_SORT_KEYS)
        ).hexdigest()
        row = {**body, "sha256": checksum}
        with (Path(directory) / LEDGER_LOG_FILENAME).open("ab") as handle:
            handle.write(orjson.dumps(row, option=orjson.OPT_SORT_KEYS) + b"\n")
        with pytest.raises(ValueError, match="Duplicate"):
            SurfaceIdentityLedger.load_or_create(directory)
