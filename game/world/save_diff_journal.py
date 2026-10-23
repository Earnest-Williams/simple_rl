"""Save-Diff Journals: absolute physical persistence for surface chunks.

Implements Phase 4 of ``docs/Surface Map Plan.md``. Every modification to
the physical world (terrain broken, doors opened, items dropped, trees
chopped) is recorded as a Mutation Overlay in the chunk's Save-Diff
Journal. Generator-produced Polars/Arrow files stay strictly immutable;
journals live beside them as the only writable per-chunk state.

Design invariants:

* **Atomic writes.** Journals are serialized to a temporary file in the
  same directory and moved into place with :func:`os.replace`, so a crash
  or power loss can never leave a half-written primary file.
* **Backup recovery.** Each successful write first copies the previous
  primary file to a ``.bak`` sibling. Loading tries the primary first and
  falls back to ``.bak``; if both fail, the loader returns ``None`` and
  the caller regenerates the base chunk (sacrificing player mutations
  rather than crash-looping).
* **Compaction.** Mutation events append to an in-memory event log. When
  the log exceeds the compaction threshold (default 500 events), it is
  compacted away — the final state already lives in the overlay tables —
  keeping journal files bounded.
* **Delta categorization.** Journal data is strictly divided into
  physical tables: ``tile_mutations``, ``item_deltas``, and
  ``entity_snapshots``. Loading ignores any foreign keys, so malformed or
  future formats cannot smuggle unexpected state in.
* **Separation of player knowledge.** Exploration status, fog of war, and
  map discoveries are *cognitive* state, not physical state. This module
  deliberately provides no API to store them; they belong to a dedicated
  ``FactionKnowledgeStore`` (Phase 8) and never appear in journal files.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Final

from game.world.game_map import TILE_TYPES, GameMap
from game.world.surface_chunks import CHUNK_ID_PREFIX, chunk_id

JOURNAL_SCHEMA_VERSION: Final[int] = 2
"""Current Save-Diff Journal schema version."""

DEFAULT_COMPACTION_THRESHOLD: Final[int] = 500
"""Compact the event log once it holds more than this many events."""

JOURNAL_SUFFIX: Final[str] = ".json"
"""Save-Diff Journal file extension."""

BACKUP_SUFFIX: Final[str] = ".bak"
"""Suffix of the backup copy kept beside every primary journal."""

TEMP_SUFFIX: Final[str] = ".tmp"
"""Suffix of the in-progress atomic write file."""

_PHYSICAL_TABLE_KEYS: Final[frozenset[str]] = frozenset(
    {"tile_mutations", "tile_metadata", "item_deltas", "entity_snapshots", "population"}
)
"""The only mutation-overlay tables a journal may carry."""

_LOGGER = logging.getLogger(__name__)


def _coordinate_key(x: int, y: int) -> str:
    """Return the stable serialization key for a global tile coordinate."""
    return f"{x},{y}"


def _parse_coordinate_key(key: str) -> tuple[int, int]:
    """Parse a serialized ``"x,y"`` coordinate key back into a tuple."""
    left, right = key.split(",", 1)
    return int(left), int(right)


def _parse_chunk_id(identifier: str) -> tuple[int, int, int]:
    """Parse a chunk identifier string into ``(cx, cy, cz)``.

    Inverse of :func:`game.world.surface_chunks.chunk_id`.
    """
    parts = identifier.split("_")
    if len(parts) != 4 or parts[0] != CHUNK_ID_PREFIX:
        raise ValueError(f"Malformed chunk identifier: {identifier!r}")
    return int(parts[1]), int(parts[2]), int(parts[3])


class SaveDiffJournal:
    """Per-chunk mutation overlay journal with atomic persistence.

    The overlay tables are the authoritative compacted state:

    * ``tile_mutations``: ``(x, y) -> new_tile_type_id``
    * ``item_deltas``: ``(x, y) -> {"added": [...], "removed": [...]}``
    * ``entity_snapshots``: ``entity_id -> serialized_state_dict``

    A bounded event log records raw mutation events since the last
    compaction for debugging and history; the overlay tables are kept
    current on every record, so compacting (or truncating) the log never
    loses state.
    """

    def __init__(
        self,
        cx: int,
        cy: int,
        cz: int = 0,
        *,
        compaction_threshold: int = DEFAULT_COMPACTION_THRESHOLD,
    ) -> None:
        if compaction_threshold < 1:
            raise ValueError(
                "compaction_threshold must be a positive integer, got "
                f"{compaction_threshold}"
            )
        self._cx = cx
        self._cy = cy
        self._cz = cz
        self._compaction_threshold = compaction_threshold
        self._timestamp: int = 0
        self._tile_mutations: dict[tuple[int, int], int] = {}
        self._tile_metadata: dict[tuple[int, int], dict[str, float | int]] = {}
        self._population_initialized = False
        self._population_births: dict[str, int] = {}
        self._population_deaths: set[str] = set()
        self._item_deltas: dict[tuple[int, int], dict[str, list[str]]] = {}
        self._entity_snapshots: dict[str, dict[str, Any]] = {}
        self._event_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Identity and introspection
    # ------------------------------------------------------------------

    @property
    def cx(self) -> int:
        """Chunk x coordinate."""
        return self._cx

    @property
    def cy(self) -> int:
        """Chunk y coordinate."""
        return self._cy

    @property
    def cz(self) -> int:
        """Chunk z (plane) coordinate."""
        return self._cz

    @property
    def chunk_id(self) -> str:
        """Stable chunk identifier, e.g. ``chunk_3_-2_0``."""
        return chunk_id(self._cx, self._cy, self._cz)

    @property
    def timestamp(self) -> int:
        """Epoch timestamp of the last successful journal write."""
        return self._timestamp

    @property
    def tile_mutations(self) -> dict[tuple[int, int], int]:
        """Compacted tile overlay: global ``(x, y) -> tile_type_id``."""
        return dict(self._tile_mutations)

    @property
    def tile_metadata(self) -> dict[tuple[int, int], dict[str, float | int]]:
        """Explicit semantic overrides for mutated physical tiles."""
        return {xy: dict(row) for xy, row in self._tile_metadata.items()}

    @property
    def population_initialized(self) -> bool:
        """Whether this chunk's one-time initial population occurred."""
        return self._population_initialized

    @property
    def population_births(self) -> dict[str, int]:
        """Permanent birth-key to numerical-ID mapping in this chunk."""
        return dict(self._population_births)

    @property
    def population_deaths(self) -> frozenset[str]:
        """Birth keys permanently removed from this chunk's population."""
        return frozenset(self._population_deaths)

    def mark_population_initialized(self) -> None:
        """Prevent regenerated or revisited chunks from respawning actors."""
        self._population_initialized = True

    def record_population_birth(self, birth_key: str, actor_id: int) -> None:
        """Record an actual generated birth, including future dead actors."""
        previous = self._population_births.get(birth_key)
        if previous is not None and previous != actor_id:
            raise ValueError(f"Conflicting birth assignment: {birth_key}")
        if actor_id in self._population_births.values() and previous is None:
            raise ValueError(f"Duplicate birth actor ID: {actor_id}")
        self._population_births[birth_key] = int(actor_id)

    def mark_population_death(self, birth_key: str) -> None:
        """Retain a death tombstone without permitting future respawn."""
        actor_id = self._population_births[birth_key]
        self._population_deaths.add(birth_key)
        self._entity_snapshots.pop(str(actor_id), None)

    @property
    def item_deltas(self) -> dict[tuple[int, int], dict[str, list[str]]]:
        """Compacted item overlay per global tile coordinate."""
        return {
            coordinate: {
                "added": list(payload["added"]),
                "removed": list(payload["removed"]),
            }
            for coordinate, payload in self._item_deltas.items()
        }

    @property
    def entity_snapshots(self) -> dict[str, dict[str, Any]]:
        """Compacted entity snapshot overlay: ``entity_id -> state``."""
        return {key: dict(value) for key, value in self._entity_snapshots.items()}

    @property
    def event_log(self) -> list[dict[str, Any]]:
        """Raw mutation events since the last compaction."""
        return [dict(event) for event in self._event_log]

    @property
    def event_count(self) -> int:
        """Number of raw events currently held in the event log."""
        return len(self._event_log)

    @property
    def is_empty(self) -> bool:
        """Whether the journal holds no physical mutations at all."""
        return not (
            self._tile_mutations
            or self._tile_metadata
            or self._population_initialized
            or self._item_deltas
            or self._entity_snapshots
            or self._event_log
        )

    # ------------------------------------------------------------------
    # Recording physical mutations
    # ------------------------------------------------------------------

    def record_tile_mutation(
        self,
        x: int,
        y: int,
        tile_type_id: int,
        *,
        material: int | None = None,
        traversal: int | None = None,
        movement_cost: float | None = None,
        wetness: int | None = None,
        hydro: int | None = None,
    ) -> None:
        """Record a physical tile change at global ``(x, y)``.

        ``tile_type_id`` is a ``GameMap`` tile id (e.g.
        ``TILE_ID_FLOOR``). Later mutations of the same tile win.
        """
        self._tile_mutations[(x, y)] = int(tile_type_id)
        # A plain geometry mutation does not rewrite the generated
        # sidecar. Opening a genuinely impassable generated wall requires
        # an explicit traversal/material override from the mutation caller.
        overrides: dict[str, float | int] = {}
        for key, value in (
            ("material", material),
            ("traversal", traversal),
            ("movement_cost", movement_cost),
            ("wetness", wetness),
            ("hydro", hydro),
        ):
            if value is not None:
                overrides[key] = float(value) if key == "movement_cost" else int(value)
        if overrides:
            self._tile_metadata[(x, y)] = overrides
        else:
            self._tile_metadata.pop((x, y), None)
        self._append_event(
            {"kind": "tile", "x": int(x), "y": int(y), "tile_type_id": int(tile_type_id)}
        )

    def record_item_delta(
        self,
        x: int,
        y: int,
        *,
        added: tuple[str, ...] | list[str] = (),
        removed: tuple[str, ...] | list[str] = (),
    ) -> None:
        """Record items added to or removed from global tile ``(x, y)``."""
        payload = self._item_deltas.setdefault(
            (int(x), int(y)), {"added": [], "removed": []}
        )
        payload["added"].extend(added)
        payload["removed"].extend(removed)
        self._append_event(
            {
                "kind": "item",
                "x": int(x),
                "y": int(y),
                "added": list(added),
                "removed": list(removed),
            }
        )

    def record_entity_snapshot(self, entity_id: str, state: dict[str, Any]) -> None:
        """Record (or refresh) a serialized entity state snapshot.

        Snapshots are the dehydration records consumed by the Phase 5
        hydration flow; this journal only persists them as opaque
        JSON-serializable dicts.
        """
        if not isinstance(state, dict):
            raise TypeError(
                f"entity snapshot state must be a dict, got {type(state).__name__}"
            )
        self._entity_snapshots[entity_id] = dict(state)
        self._append_event({"kind": "entity", "entity_id": entity_id})

    def has_entity_snapshot(self, entity_id: str) -> bool:
        """Whether a dehydration record exists for ``entity_id``."""
        return entity_id in self._entity_snapshots

    def pop_entity_snapshot(self, entity_id: str) -> dict[str, Any] | None:
        """Remove and return the snapshot record for ``entity_id``.

        Hydration (Surface Map Plan Phase 5) *consumes* dehydration
        records: once an actor re-enters the active ECS registry it must
        exist only there, never both as a live entity and a journal
        record (the no-double-simulation rule).
        """
        return self._entity_snapshots.pop(entity_id, None)

    def _append_event(self, event: dict[str, Any]) -> None:
        self._event_log.append(event)
        if len(self._event_log) > self._compaction_threshold:
            self.compact()

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact(self) -> int:
        """Truncate the event log; returns the number of events dropped.

        Safe by construction: every event's effect already lives in the
        overlay tables, so compaction only discards redundant history.
        """
        dropped = len(self._event_log)
        self._event_log.clear()
        return dropped

    def needs_compaction(self) -> bool:
        """Whether the event log has exceeded the compaction threshold."""
        return len(self._event_log) > self._compaction_threshold

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable journal document.

        Top-level keys are exactly the header block plus the three
        physical mutation tables and the (bounded) event log. No player
        or faction cognitive state is ever included.
        """
        return {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "chunk_id": self.chunk_id,
            "timestamp": self._timestamp,
            "population": {
                "initialized": self._population_initialized,
                "births": dict(sorted(self._population_births.items())),
                "dead": sorted(self._population_deaths),
            },
            "tile_metadata": {
                _coordinate_key(x, y): dict(values)
                for (x, y), values in sorted(self._tile_metadata.items())
            },
            "tile_mutations": {
                _coordinate_key(x, y): tile_type_id
                for (x, y), tile_type_id in sorted(self._tile_mutations.items())
            },
            "item_deltas": {
                _coordinate_key(x, y): {
                    "added": list(payload["added"]),
                    "removed": list(payload["removed"]),
                }
                for (x, y), payload in sorted(self._item_deltas.items())
            },
            "entity_snapshots": {
                entity_id: dict(state)
                for entity_id, state in sorted(self._entity_snapshots.items())
            },
            "event_log": [dict(event) for event in self._event_log],
        }

    def to_json(self) -> str:
        """Return the journal document as a deterministic JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SaveDiffJournal:
        """Rebuild a journal from a deserialized document.

        Raises :class:`ValueError` on schema or chunk-identifier
        mismatches. Foreign top-level keys (anything outside the header
        and the physical tables) are ignored — knowledge state can never
        sneak in through a journal file.
        """
        if not isinstance(data, dict):
            raise ValueError(f"Journal document must be an object, got {type(data).__name__}")
        schema_version = data.get("schema_version")
        if schema_version not in (1, JOURNAL_SCHEMA_VERSION):
            raise ValueError(
                f"Unsupported journal schema_version: {schema_version!r} "
                f"(expected {JOURNAL_SCHEMA_VERSION})"
            )
        identifier = data.get("chunk_id")
        if not isinstance(identifier, str):
            raise ValueError("Journal document is missing a chunk_id string")
        cx, cy, cz = _parse_chunk_id(identifier)
        journal = cls(cx, cy, cz)
        journal._timestamp = int(data.get("timestamp", 0))

        tile_mutations = data.get("tile_mutations", {})
        if not isinstance(tile_mutations, dict):
            raise ValueError("tile_mutations must be an object")
        for key, tile_type_id in tile_mutations.items():
            x, y = _parse_coordinate_key(str(key))
            journal._tile_mutations[(x, y)] = int(tile_type_id)

        tile_metadata = data.get("tile_metadata", {})
        if not isinstance(tile_metadata, dict):
            raise ValueError("tile_metadata must be an object")
        for key, payload in tile_metadata.items():
            xy = _parse_coordinate_key(str(key))
            if not isinstance(payload, dict):
                raise ValueError("tile_metadata values must be objects")
            if any(k not in {
                "material", "traversal", "movement_cost", "wetness", "hydro"
            } for k in payload):
                raise ValueError("Unknown tile_metadata semantic key")
            if xy not in journal._tile_mutations:
                raise ValueError("Tile metadata requires a matching tile mutation")
            journal._tile_metadata[xy] = {
                str(k): float(v) if k == "movement_cost" else int(v)
                for k, v in payload.items()
            }

        population = data.get("population", {})
        if not isinstance(population, dict):
            raise ValueError("population must be an object")
        journal._population_initialized = bool(population.get("initialized", False))
        births = population.get("births", {})
        dead = population.get("dead", [])
        if not isinstance(births, dict) or not isinstance(dead, list):
            raise ValueError("Malformed population tracking")
        for birth_key, actor_id in births.items():
            journal.record_population_birth(str(birth_key), int(actor_id))
        for birth_key in dead:
            if not isinstance(birth_key, str) or birth_key not in births:
                raise ValueError("Death tombstone lacks a matching birth")
            journal._population_deaths.add(birth_key)

        item_deltas = data.get("item_deltas", {})
        if not isinstance(item_deltas, dict):
            raise ValueError("item_deltas must be an object")
        for key, payload in item_deltas.items():
            x, y = _parse_coordinate_key(str(key))
            if not isinstance(payload, dict):
                raise ValueError(f"item_deltas[{key!r}] must be an object")
            journal._item_deltas[(x, y)] = {
                "added": [str(item) for item in payload.get("added", [])],
                "removed": [str(item) for item in payload.get("removed", [])],
            }

        entity_snapshots = data.get("entity_snapshots", {})
        if not isinstance(entity_snapshots, dict):
            raise ValueError("entity_snapshots must be an object")
        for entity_id, state in entity_snapshots.items():
            if not isinstance(state, dict):
                raise ValueError(
                    f"entity_snapshots[{entity_id!r}] must be an object"
                )
            journal._entity_snapshots[str(entity_id)] = dict(state)

        event_log = data.get("event_log", [])
        if not isinstance(event_log, list):
            raise ValueError("event_log must be a list")
        journal._event_log = [dict(event) for event in event_log]
        return journal

    @classmethod
    def from_json(cls, text: str) -> SaveDiffJournal:
        """Rebuild a journal from a JSON string (see :meth:`from_dict`)."""
        return cls.from_dict(json.loads(text))

    # ------------------------------------------------------------------
    # Storage paths
    # ------------------------------------------------------------------

    @staticmethod
    def journal_filename(cx: int, cy: int, cz: int = 0) -> str:
        """Return the primary journal filename for chunk ``(cx, cy, cz)``."""
        return f"{chunk_id(cx, cy, cz)}{JOURNAL_SUFFIX}"

    def journal_path(self, directory: str | os.PathLike[str]) -> Path:
        """Return the primary journal path inside ``directory``."""
        return Path(directory) / f"{self.chunk_id}{JOURNAL_SUFFIX}"

    def backup_path(self, directory: str | os.PathLike[str]) -> Path:
        """Return the ``.bak`` recovery path inside ``directory``."""
        return Path(directory) / f"{self.chunk_id}{JOURNAL_SUFFIX}{BACKUP_SUFFIX}"

    # ------------------------------------------------------------------
    # Atomic persistence
    # ------------------------------------------------------------------

    def write_atomic(
        self,
        directory: str | os.PathLike[str],
        *,
        timestamp: int | None = None,
    ) -> Path:
        """Persist the journal atomically and return the primary path.

        The document is written to a temporary file in the same directory
        and moved over the primary with :func:`os.replace` (atomic on
        POSIX and Windows). The previous primary is first copied to the
        ``.bak`` sibling, so a corrupt primary can always fall back to
        the last known-good write.
        """
        path = self.journal_path(directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.backup_path(directory)
        if path.exists():
            # Only promote a parseable primary to .bak; a corrupt primary
            # must never overwrite the last known-good backup.
            try:
                SaveDiffJournal.from_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                _LOGGER.warning(
                    "Refusing to promote corrupt primary journal %s to backup",
                    path,
                )
            else:
                shutil.copyfile(path, backup)
        self._timestamp = int(time.time()) if timestamp is None else int(timestamp)
        temp_path = path.with_name(f"{path.name}{TEMP_SUFFIX}")
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(self.to_json())
        os.replace(temp_path, path)
        return path

    @classmethod
    def load(
        cls,
        directory: str | os.PathLike[str],
        cx: int,
        cy: int,
        cz: int = 0,
    ) -> SaveDiffJournal | None:
        """Load the journal for chunk ``(cx, cy, cz)`` if recoverable.

        Tries the primary file, then the ``.bak`` fallback. Returns
        ``None`` when neither is readable or both are corrupt; callers
        regenerate the base chunk in that case rather than crash-looping.
        """
        primary = Path(directory) / cls.journal_filename(cx, cy, cz)
        backup = primary.with_name(f"{primary.name}{BACKUP_SUFFIX}")
        for label, candidate in (("primary", primary), ("backup", backup)):
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                journal = cls.from_json(text)
            except (ValueError, TypeError, json.JSONDecodeError):
                _LOGGER.warning(
                    "Save-Diff Journal %s for chunk %s is corrupt; trying fallback",
                    label,
                    chunk_id(cx, cy, cz),
                )
                continue
            if (journal.cx, journal.cy, journal.cz) != (cx, cy, cz):
                _LOGGER.warning(
                    "Save-Diff Journal %s holds chunk %s, expected %s",
                    label,
                    journal.chunk_id,
                    chunk_id(cx, cy, cz),
                )
                continue
            return journal
        return None

    @classmethod
    def load_or_create(
        cls,
        directory: str | os.PathLike[str],
        cx: int,
        cy: int,
        cz: int = 0,
        *,
        compaction_threshold: int = DEFAULT_COMPACTION_THRESHOLD,
    ) -> SaveDiffJournal:
        """Load the chunk journal, or start a fresh empty one."""
        journal = cls.load(directory, cx, cy, cz)
        if journal is None:
            return cls(cx, cy, cz, compaction_threshold=compaction_threshold)
        return journal

    # ------------------------------------------------------------------
    # Runtime application
    # ------------------------------------------------------------------

    def apply_tile_mutations(
        self,
        game_map: GameMap,
        *,
        viewport_origin_x: int = 0,
        viewport_origin_y: int = 0,
    ) -> int:
        """Overlay explicit physical mutations onto a generated viewport.

        Geometry alone never changes the immutable generated material,
        traversal, hydrology or movement cost. Callers must record semantic
        overrides when a mutation truly changes those properties; applying
        the journal multiple times is therefore idempotent.
        """
        written = 0
        metadata = game_map.overland_metadata
        grid_names = {
            "material": "material_grid",
            "traversal": "traversal_class_grid",
            "movement_cost": "movement_cost_grid",
            "wetness": "wetness_grid",
            "hydro": "hydro_grid",
        }
        for (gx, gy), tile_type_id in self._tile_mutations.items():
            lx = gx - viewport_origin_x
            ly = gy - viewport_origin_y
            if not (0 <= lx < game_map.width and 0 <= ly < game_map.height):
                continue
            if int(tile_type_id) not in TILE_TYPES:
                raise ValueError(f"Unknown tile type ID {tile_type_id}")
            game_map.tiles[ly, lx] = tile_type_id
            if metadata is not None:
                for key, value in self._tile_metadata.get((gx, gy), {}).items():
                    grid = getattr(metadata, grid_names[key])
                    grid[ly, lx] = value
            written += 1
        if written:
            game_map.update_tile_transparency()
        return written

    def __repr__(self) -> str:
        """Return a compact debug representation."""
        return (
            f"SaveDiffJournal({self.chunk_id}, tiles={len(self._tile_mutations)}, "
            f"items={len(self._item_deltas)}, "
            f"entities={len(self._entity_snapshots)}, "
            f"events={len(self._event_log)})"
        )


__all__ = [
    "BACKUP_SUFFIX",
    "DEFAULT_COMPACTION_THRESHOLD",
    "JOURNAL_SCHEMA_VERSION",
    "JOURNAL_SUFFIX",
    "SaveDiffJournal",
    "TEMP_SUFFIX",
]
