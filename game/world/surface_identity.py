"""World-scoped registry for stable generated-actor birth identities.

A birth key is the permanent identity; the UInt32 number is an engine-local
surrogate. Allocations persist before the corresponding actor is spawned.
The high half of UInt32 is reserved for generated surface actors.

Hash collision recovery uses an ordered salt probe and a persistent ledger.
A numeric surrogate can differ across brand-new worlds if colliding birth keys
are first encountered in different orders. The canonical birth keys do not.
Stable surrogates across save/load require the same persisted world ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Collection, Iterable
from pathlib import Path
from threading import RLock
from typing import Final

LEDGER_FILENAME: Final[str] = "surface_actor_ids.json"
_MAX_PROBES: Final[int] = 100_000


class SurfaceIdentityLedger:
    """Own the numerical namespace of a single persistent world."""

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
        for birth_key, actor_id in (assignments or {}).items():
            self._add_existing(birth_key, actor_id)

    def _add_existing(self, birth_key: str, actor_id: int) -> None:
        if not birth_key or not 0x80000000 <= actor_id <= 0xFFFFFFFF:
            raise ValueError("Invalid surface birth identity or numerical ID")
        if birth_key in self._by_birth or actor_id in self._by_id:
            raise ValueError("Duplicate surface birth identity or numerical ID")
        self._by_birth[birth_key] = actor_id
        self._by_id[actor_id] = birth_key

    @staticmethod
    def _candidate(birth_key: str, salt: int) -> int:
        digest = hashlib.sha256(f"surface-birth:{birth_key}:{salt}".encode()).digest()
        return 0x80000000 | (int.from_bytes(digest[:4], "big") & 0x7FFFFFFF)

    def id_for(self, birth_key: str) -> int | None:
        """Return an existing ID, without allocating a new one."""
        with self._lock:
            return self._by_birth.get(birth_key)

    def owner_of(self, actor_id: int) -> str | None:
        """Return the canonical birth key holding a numerical reservation."""
        with self._lock:
            return self._by_id.get(actor_id)

    def reserve_many(
        self,
        birth_keys: Iterable[str],
        *,
        occupied_ids: Collection[int] = (),
    ) -> dict[str, int]:
        """Reserve a batch, writing the ledger once before any actor spawn.

        All new assignments are staged under the world lock. A failed
        persistence attempt rolls back the in-memory reservations; callers
        must not spawn actors until this method has returned successfully.
        """
        with self._lock:
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
            for actor_id, birth_key in staged.items():
                self._add_existing(birth_key, actor_id)
            try:
                if self._directory is not None:
                    self.write_atomic(self._directory)
            except OSError:
                for actor_id, birth_key in staged.items():
                    del self._by_birth[birth_key]
                    del self._by_id[actor_id]
                raise
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
        """JSON-compatible world ledger, sorted for reproducible saves."""
        with self._lock:
            return {
                "version": 1,
                "assignments": dict(sorted(self._by_birth.items())),
            }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, object],
        *,
        directory: str | os.PathLike[str] | None = None,
    ) -> SurfaceIdentityLedger:
        """Refuse corrupt ledgers rather than silently reusing world IDs."""
        if payload.get("version") != 1:
            raise ValueError("Unsupported surface identity ledger version")
        raw = payload.get("assignments")
        if not isinstance(raw, dict):
            raise ValueError("Missing surface actor identity assignments")
        if any(
            not isinstance(k, str) or not isinstance(v, int) for k, v in raw.items()
        ):
            raise ValueError("Malformed surface actor identity assignments")
        assignments = {str(k): int(v) for k, v in raw.items()}
        return cls(assignments, directory=directory)

    def write_atomic(self, directory: str | os.PathLike[str]) -> Path:
        """Commit the world ledger before materializing reserved actors."""
        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / LEDGER_FILENAME
        temp = target.with_name(target.name + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
        return target

    @classmethod
    def load_or_create(
        cls,
        directory: str | os.PathLike[str],
    ) -> SurfaceIdentityLedger:
        """Load an existing world ledger or create a durable new one."""
        path = Path(directory) / LEDGER_FILENAME
        if not path.exists():
            return cls(directory=directory)
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("Surface identity ledger must contain a JSON object")
        return cls.from_dict(document, directory=directory)


__all__ = ["LEDGER_FILENAME", "SurfaceIdentityLedger"]
