"""Durable world-wide surface-actor identity ledger.

Canonical birth keys are permanent identities. Numerical UInt32 IDs are
surrogates, allocated from the high half of the registry namespace.

The old surface_actor_ids.json format remains a valid checkpoint. New
reservations append one checksummed NDJSON batch to surface_actor_ids.log
and fsync it before any actor can spawn. Compaction is explicit, intended
for a save/checkpoint boundary outside the game loop.

A world save must have exactly one ledger writer. Two simultaneous processes
writing different IDs to the same files are not supported.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Collection, Iterable
from pathlib import Path
from threading import RLock
from typing import Final, cast

import orjson

LEDGER_FILENAME: Final[str] = "surface_actor_ids.json"
LEDGER_LOG_FILENAME: Final[str] = "surface_actor_ids.log"
_MAX_PROBES: Final[int] = 100_000
_LOG_VERSION: Final[int] = 1
_LOGGER = logging.getLogger(__name__)


def _json_bytes(document: dict[str, object]) -> bytes:
    return orjson.dumps(document, option=orjson.OPT_SORT_KEYS)


def _sync_directory(directory: Path) -> None:
    """Make newly created/renamed files durable on POSIX filesystems."""
    if not hasattr(os, "O_DIRECTORY"):
        return
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class SurfaceIdentityLedger:
    """Own all generated-actor numeric reservations in one saved world."""

    def __init__(
        self,
        assignments: dict[str, int] | None = None,
        *,
        directory: str | os.PathLike[str] | None = None,
    ) -> None:
        self._by_birth: dict[str, int] = {}
        self._by_id: dict[int, str] = {}
        self._directory = Path(directory) if directory is not None else None
        self._lock = RLock()
        self._write_failed = False
        for birth_key, actor_id in (assignments or {}).items():
            self._add_existing(birth_key, actor_id)

    def _add_existing(self, birth_key: str, actor_id: int) -> None:
        if not birth_key or not 0x80000000 <= actor_id <= 0xFFFFFFFF:
            raise ValueError("Invalid surface birth identity or numerical ID")
        existing_id = self._by_birth.get(birth_key)
        existing_birth = self._by_id.get(actor_id)
        if existing_id is not None or existing_birth is not None:
            if existing_id == actor_id and existing_birth == birth_key:
                return  # Replay after checkpoint replacement, before log trim.
            raise ValueError("Duplicate or conflicting surface birth identity or numerical ID")
        self._by_birth[birth_key] = actor_id
        self._by_id[actor_id] = birth_key

    @staticmethod
    def _candidate(birth_key: str, salt: int) -> int:
        digest = hashlib.sha256(f"surface-birth:{birth_key}:{salt}".encode()).digest()
        return 0x80000000 | (int.from_bytes(digest[:4], "big") & 0x7FFFFFFF)

    def id_for(self, birth_key: str) -> int | None:
        """Return an existing ID without allocating a new one."""
        with self._lock:
            return self._by_birth.get(birth_key)

    def owner_of(self, actor_id: int) -> str | None:
        """Return the canonical birth key reserving an integer ID."""
        with self._lock:
            return self._by_id.get(actor_id)

    def _append_batch(self, assignments: dict[str, int]) -> None:
        """One durable append regardless of how many actors are in the batch."""
        if self._directory is None or not assignments:
            return
        directory = self._directory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / LEDGER_LOG_FILENAME
        body: dict[str, object] = {
            "version": _LOG_VERSION,
            "assignments": dict(sorted(assignments.items())),
        }
        checksum = hashlib.sha256(_json_bytes(body)).hexdigest()
        row = {**body, "sha256": checksum}
        encoded = _json_bytes(row) + b"\n"
        created = not path.exists()
        try:
            with path.open("ab") as handle:
                count = handle.write(encoded)
                if count != len(encoded):
                    raise OSError("Incomplete surface identity log append")
                handle.flush()
                os.fsync(handle.fileno())
            if created:
                _sync_directory(directory)
        except OSError:
            # The append might have reached disk despite an fsync error.
            # Refuse further reservations until the ledger is reloaded.
            self._write_failed = True
            raise

    def reserve_many(
        self,
        birth_keys: Iterable[str],
        *,
        occupied_ids: Collection[int] = (),
    ) -> dict[str, int]:
        """Reserve IDs and durably append one batch before caller may spawn."""
        with self._lock:
            if self._write_failed:
                raise RuntimeError(
                    "Identity log write failed; reload the world ledger before "
                    "making any more reservations"
                )
            occupied = set(occupied_ids)
            assignments: dict[str, int] = {}
            staged: dict[int, str] = {}
            for birth_key in birth_keys:
                if birth_key in assignments:
                    continue
                known = self._by_birth.get(birth_key)
                if known is not None:
                    assignments[birth_key] = known
                    continue
                if not birth_key:
                    raise ValueError("Surface birth key must not be empty")
                for salt in range(_MAX_PROBES):
                    actor_id = self._candidate(birth_key, salt)
                    if (
                        actor_id in occupied
                        or actor_id in self._by_id
                        or actor_id in staged
                    ):
                        continue
                    assignments[birth_key] = actor_id
                    staged[actor_id] = birth_key
                    break
                else:
                    raise RuntimeError("Surface actor ID namespace exhausted by probes")

            if not staged:
                return assignments
            additions = {birth_key: actor_id for actor_id, birth_key in staged.items()}
            try:
                self._append_batch(additions)
            except OSError:
                self._write_failed = True
                raise
            for actor_id, birth_key in staged.items():
                self._add_existing(birth_key, actor_id)
            return assignments

    def reserve(
        self,
        birth_key: str,
        *,
        occupied_ids: Collection[int] = (),
    ) -> int:
        """Reserve one ID with the same durable semantics as a batch."""
        return self.reserve_many((birth_key,), occupied_ids=occupied_ids)[birth_key]

    def to_dict(self) -> dict[str, object]:
        """Return the legacy-compatible complete checkpoint document."""
        with self._lock:
            return {"version": 1, "assignments": dict(sorted(self._by_birth.items()))}

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, object],
        *,
        directory: str | os.PathLike[str] | None = None,
    ) -> SurfaceIdentityLedger:
        """Read a legacy snapshot, refusing malformed or conflicting IDs."""
        if payload.get("version") != 1:
            raise ValueError("Unsupported surface identity ledger version")
        raw = payload.get("assignments")
        if not isinstance(raw, dict):
            raise ValueError("Missing surface actor identity assignments")
        if any(
            not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool)
            for k, v in raw.items()
        ):
            raise ValueError("Malformed surface actor identity assignments")
        return cls(raw, directory=directory)

    @staticmethod
    def _decode_batch(encoded: bytes) -> dict[str, int]:
        """Reject complete-but-corrupt records; a partial tail is recoverable."""
        try:
            row = orjson.loads(encoded)
        except orjson.JSONDecodeError as exc:
            raise ValueError("Corrupt complete surface identity log record") from exc
        if not isinstance(row, dict):
            raise ValueError("Identity log record must be an object")
        if set(row) != {"version", "assignments", "sha256"}:
            raise ValueError("Malformed identity log record")
        body: dict[str, object] = {
            "version": row["version"],
            "assignments": row["assignments"],
        }
        if row["version"] != _LOG_VERSION or not isinstance(row["assignments"], dict):
            raise ValueError("Unsupported identity log record")
        checksum = hashlib.sha256(_json_bytes(body)).hexdigest()
        if row["sha256"] != checksum:
            raise ValueError("Surface identity log checksum mismatch")
        raw: dict[str, object] = row["assignments"]
        if any(
            not isinstance(key, str)
            or not isinstance(value, int)
            or isinstance(value, bool)
            for key, value in raw.items()
        ):
            raise ValueError("Malformed identity log assignments")
        return cast(dict[str, int], raw)

    @classmethod
    def load_or_create(
        cls, directory: str | os.PathLike[str]
    ) -> SurfaceIdentityLedger:
        """Read legacy checkpoint plus all complete append batches.

        An unterminated final log record represents a crashed append. It
        is truncated on recovery so the next append cannot concatenate
        with partial bytes. Complete malformed records fail closed.
        """
        base = Path(directory)
        snapshot = base / LEDGER_FILENAME
        if snapshot.exists():
            try:
                data = orjson.loads(snapshot.read_bytes())
            except orjson.JSONDecodeError as exc:
                raise ValueError("Corrupt surface identity checkpoint") from exc
            if not isinstance(data, dict):
                raise ValueError("Surface identity checkpoint must be an object")
            ledger = cls.from_dict(data, directory=base)
        else:
            ledger = cls(directory=base)

        log = base / LEDGER_LOG_FILENAME
        if not log.exists():
            return ledger
        content = log.read_bytes()
        last_complete = content.rfind(b"\n") + 1
        # Validate the durable prefix BEFORE truncating an interrupted tail.
        for record in content[:last_complete].splitlines():
            if not record:
                raise ValueError("Empty identity log record")
            for birth_key, actor_id in cls._decode_batch(record).items():
                ledger._add_existing(birth_key, actor_id)
        if last_complete != len(content):
            _LOGGER.warning(
                "Discarding incomplete identity log tail (%d bytes): %s",
                len(content) - last_complete,
                log,
            )
            with log.open("r+b") as handle:
                handle.truncate(last_complete)
                handle.flush()
                os.fsync(handle.fileno())
        return ledger

    def compact(
        self, directory: str | os.PathLike[str] | None = None
    ) -> Path:
        """Checkpoint all identities and truncate replay log off the hot path.

        Ordering is essential. After the checkpoint is fsynced and renamed,
        duplicate records remaining in the log replay idempotently. Only
        then is the log truncated. A crash at any point retains all IDs.
        """
        with self._lock:
            if self._write_failed:
                raise RuntimeError("Cannot compact a failed ledger without reloading")
            target_dir = Path(directory) if directory is not None else self._directory
            if target_dir is None:
                raise ValueError("Compaction requires a save directory")
            target_dir.mkdir(parents=True, exist_ok=True)
            checkpoint = target_dir / LEDGER_FILENAME
            temp = checkpoint.with_name(checkpoint.name + ".tmp")
            content = orjson.dumps(
                self.to_dict(), option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2
            )
            with temp.open("wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, checkpoint)
            _sync_directory(target_dir)

            log = target_dir / LEDGER_LOG_FILENAME
            if log.exists():
                with log.open("wb") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
            return checkpoint

    def write_atomic(self, directory: str | os.PathLike[str]) -> Path:
        """Compatibility alias for explicitly creating a full checkpoint."""
        return self.compact(directory)


__all__ = ["LEDGER_FILENAME", "LEDGER_LOG_FILENAME", "SurfaceIdentityLedger"]
