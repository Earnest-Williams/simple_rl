"""Tests for Save-Diff Journals (Surface Map Plan Phase 4).

Covers docs/Surface Map Plan.md Phase 4: per-chunk mutation overlay
journals with atomic os.replace writes, .bak corruption recovery,
event-log compaction, player-knowledge separation, and the reload flow
where a modified chunk is unloaded and reloaded with its physical
mutations intact.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from game.world.save_diff_journal import (
    DEFAULT_COMPACTION_THRESHOLD,
    JOURNAL_SCHEMA_VERSION,
    SaveDiffJournal,
)
from game.world.surface_chunks import chunk_id
from game.world.surface_materializer import (
    InMemoryPromiseSource,
    RegionalPromise,
    SurfaceFeatureKind,
    SurfaceMaterializer,
    apply_materialized_chunk,
)

_CHUNK = 16
_WORLD_SEED = "phase-four"


def _temp_save_dir():
    """Return a fresh saves directory as a context manager."""
    return tempfile.TemporaryDirectory()


def _journal(cx: int = 3, cy: int = -2, cz: int = 0, **kwargs) -> SaveDiffJournal:
    return SaveDiffJournal(cx, cy, cz, **kwargs)


def test_save_diff_journal_round_trip() -> None:
    """Recorded physical mutations survive a write/load cycle exactly."""
    with _temp_save_dir() as saves:
        journal = _journal()
        assert journal.chunk_id == "chunk_3_-2_0"
        journal.record_tile_mutation(51, -28, TILE_ID_FLOOR)
        journal.record_tile_mutation(52, -28, TILE_ID_WALL)
        journal.record_tile_mutation(52, -28, TILE_ID_FLOOR)  # last write wins
        journal.record_item_delta(51, -28, added=("axe", "rope"))
        journal.record_item_delta(51, -28, removed=("axe",))
        journal.record_entity_snapshot(
            "wolf-5345", {"hp": 12, "faction": "wild", "scar": "left_leg"}
        )
        path = journal.write_atomic(saves, timestamp=1781669340)
        assert path == Path(saves) / "chunk_3_-2_0.json"

        loaded = SaveDiffJournal.load(saves, 3, -2, 0)
        assert loaded is not None
        assert loaded.chunk_id == journal.chunk_id
        assert loaded.timestamp == 1781669340
        assert loaded.tile_mutations == {
            (51, -28): TILE_ID_FLOOR,
            (52, -28): TILE_ID_FLOOR,
        }
        assert loaded.item_deltas == {
            (51, -28): {"added": ["axe", "rope"], "removed": ["axe"]}
        }
        assert loaded.entity_snapshots == {
            "wolf-5345": {"hp": 12, "faction": "wild", "scar": "left_leg"}
        }
        # Raw events are preserved pre-compaction.
        assert loaded.event_count == 6


def test_save_diff_journal_negative_coordinates_and_z_layers() -> None:
    """Journals work for negative chunks and stacked Z planes."""
    with _temp_save_dir() as saves:
        journal = _journal(cx=-1, cy=2, cz=3)
        journal.record_tile_mutation(-70, 40, TILE_ID_FLOOR)
        journal.write_atomic(saves)
        assert (Path(saves) / "chunk_-1_2_3.json").exists()

        loaded = SaveDiffJournal.load(saves, -1, 2, 3)
        assert loaded is not None
        assert loaded.tile_mutations == {(-70, 40): TILE_ID_FLOOR}

        # Loading a different chunk plane finds nothing.
        assert SaveDiffJournal.load(saves, -1, 2, 0) is None


def test_surface_chunk_reload_preserves_mutations() -> None:
    """Modify, unload, reload: the chunk matches its modified state."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.FOREST,
                anchor_x=0,
                anchor_y=0,
                footprint_chunks=(1, 1),
            )
        ],
        chunk_size=_CHUNK,
    )
    materializer = SurfaceMaterializer(
        source, world_seed=_WORLD_SEED, chunk_size=_CHUNK, debris_fraction=0.15
    )
    with _temp_save_dir() as saves:
        # First visit: materialize, apply, then the player chops a tree
        # and drops an item.
        first_visit = GameMap(width=_CHUNK, height=_CHUNK)
        chunk = materializer.materialize_chunk(0, 0)
        apply_materialized_chunk(first_visit, chunk)
        journal = SaveDiffJournal.load_or_create(saves, 0, 0)
        tree = next(prop for prop in chunk.props if prop.kind == "tree")
        assert first_visit.tiles[tree.y, tree.x] == TILE_ID_WALL
        journal.record_tile_mutation(tree.x, tree.y, TILE_ID_FLOOR)
        journal.record_item_delta(tree.x, tree.y, added=("wood_log",))
        assert journal.apply_tile_mutations(first_visit) == 1
        assert first_visit.tiles[tree.y, tree.x] == TILE_ID_FLOOR
        journal.write_atomic(saves)  # unload: persist the mutation overlay

        # Reload from scratch: base chunk + journal overlay reproduces
        # the modified state exactly.
        second_visit = GameMap(width=_CHUNK, height=_CHUNK)
        rechunk = materializer.materialize_chunk(0, 0)
        apply_materialized_chunk(second_visit, rechunk)
        reloaded = SaveDiffJournal.load_or_create(saves, 0, 0)
        reloaded.apply_tile_mutations(second_visit)
        assert np.array_equal(first_visit.tiles, second_visit.tiles)
        assert reloaded.item_deltas[(tree.x, tree.y)] == {
            "added": ["wood_log"],
            "removed": [],
        }


def test_save_diff_atomic_replacement() -> None:
    """Interrupted writes and primary corruption recover via .bak."""
    with _temp_save_dir() as saves:
        journal = _journal()
        journal.record_tile_mutation(10, 10, TILE_ID_FLOOR)
        journal.write_atomic(saves)
        primary = Path(saves) / "chunk_3_-2_0.json"
        backup = Path(saves) / "chunk_3_-2_0.json.bak"

        # Second write: the previous primary becomes the .bak backup.
        journal.record_tile_mutation(11, 11, TILE_ID_WALL)
        journal.write_atomic(saves)
        assert backup.exists()
        assert SaveDiffJournal.load(saves, 3, -2, 0).tile_mutations == {
            (10, 10): TILE_ID_FLOOR,
            (11, 11): TILE_ID_WALL,
        }

        # Simulate an interrupted write: a stale .tmp file must not block
        # the next atomic write, and the primary stays intact.
        stale_tmp = primary.with_name(primary.name + ".tmp")
        stale_tmp.write_text("{interrupted", encoding="utf-8")
        assert SaveDiffJournal.load(saves, 3, -2, 0) is not None
        journal.record_tile_mutation(12, 12, TILE_ID_FLOOR)
        journal.write_atomic(saves)
        assert not stale_tmp.exists()  # replaced atomically

        # Corrupt the primary: the loader falls back to the last
        # known-good .bak instead of crashing.
        primary.write_text("{corrupt!", encoding="utf-8")
        recovered = SaveDiffJournal.load(saves, 3, -2, 0)
        assert recovered is not None
        assert (11, 11) in recovered.tile_mutations

        # A full successful write heals the primary and refreshes .bak.
        recovered.record_tile_mutation(13, 13, TILE_ID_FLOOR)
        recovered.write_atomic(saves)
        healed = SaveDiffJournal.load(saves, 3, -2, 0)
        assert healed is not None
        assert healed.tile_mutations == {
            (10, 10): TILE_ID_FLOOR,
            (11, 11): TILE_ID_WALL,
            (13, 13): TILE_ID_FLOOR,
        }


def test_save_diff_journal_total_corruption_falls_back_to_base() -> None:
    """If both primary and .bak fail, loading yields the base chunk."""
    with _temp_save_dir() as saves:
        journal = _journal()
        journal.record_tile_mutation(1, 1, TILE_ID_FLOOR)
        journal.write_atomic(saves)
        journal.record_tile_mutation(2, 2, TILE_ID_WALL)
        journal.write_atomic(saves)
        primary = Path(saves) / "chunk_3_-2_0.json"
        backup = Path(saves) / "chunk_3_-2_0.json.bak"
        primary.write_text("not json at all", encoding="utf-8")
        backup.write_text("[also, not] json", encoding="utf-8")
        # Both corrupt: the engine regenerates the base chunk (empty
        # journal) instead of crash-looping on unreadable saves.
        assert SaveDiffJournal.load(saves, 3, -2, 0) is None
        fresh = SaveDiffJournal.load_or_create(saves, 3, -2, 0)
        assert fresh.is_empty
        assert fresh.tile_mutations == {}


def test_save_diff_compaction() -> None:
    """Compaction bounds the event log without losing overlay state."""
    journal = _journal(compaction_threshold=10)
    for index in range(15):
        journal.record_tile_mutation(index, 0, TILE_ID_FLOOR)
    # The event log compacted itself once it exceeded the threshold.
    assert journal.event_count <= 10
    assert journal.tile_mutations == {
        (index, 0): TILE_ID_FLOOR for index in range(15)
    }

    # Explicit compaction empties the log and keeps the overlay intact.
    expected_events = journal.event_count
    dropped = journal.compact()
    assert dropped == expected_events
    assert journal.event_count == 0
    assert len(journal.tile_mutations) == 15

    # Round-tripping preserves compacted state and the truncated log.
    with _temp_save_dir() as saves:
        journal.write_atomic(saves)
        loaded = SaveDiffJournal.load(saves, 3, -2, 0)
        assert loaded is not None
        assert loaded.event_count == 0
        assert len(loaded.tile_mutations) == 15

    # The default threshold matches the plan's 500-event guideline.
    assert DEFAULT_COMPACTION_THRESHOLD == 500


def test_save_diff_player_knowledge_excluded() -> None:
    """Journals carry physical state only — no cognitive knowledge."""
    journal = _journal()
    journal.record_tile_mutation(5, 5, TILE_ID_FLOOR)
    journal.record_item_delta(5, 5, added=("wood_log",))
    journal.record_entity_snapshot("npc-1", {"hp": 10})
    document = journal.to_dict()

    # Exactly the header block plus the physical tables and event log.
    assert set(document.keys()) == {
        "schema_version",
        "chunk_id",
        "timestamp",
        "tile_mutations",
        "item_deltas",
        "entity_snapshots",
        "event_log",
    }
    serialized = json.dumps(document)
    for knowledge_key in (
        "explored",
        "fog_of_war",
        "player_knowledge",
        "faction_knowledge",
        "discovered",
    ):
        assert knowledge_key not in serialized

    # Loading ignores smuggled foreign keys instead of storing them.
    polluted = dict(document)
    polluted["player_knowledge"] = {"explored": [[1, 2]]}
    polluted["schema_version"] = JOURNAL_SCHEMA_VERSION
    loaded = SaveDiffJournal.from_dict(polluted)
    assert "player_knowledge" not in SaveDiffJournal.to_dict(loaded)
    assert loaded.tile_mutations == {(5, 5): TILE_ID_FLOOR}


def test_save_diff_journal_rejects_bad_documents() -> None:
    """Malformed or foreign journals are rejected, not crash-looped."""
    with pytest.raises(ValueError):
        SaveDiffJournal.from_dict({"schema_version": 999, "chunk_id": "chunk_0_0_0"})
    with pytest.raises(ValueError):
        SaveDiffJournal.from_dict(
            {"schema_version": JOURNAL_SCHEMA_VERSION, "chunk_id": "bogus"}
        )
    # Schema checks are strict even for valid-looking documents.
    with pytest.raises(ValueError):
        SaveDiffJournal.from_json(
            json.dumps(
                {
                    "schema_version": 1,
                    "chunk_id": "chunk_0_0_0",
                    "tile_mutations": "not-an-object",
                }
            )
        )
    # The chunk_id helper and journal filenames stay in sync.
    assert SaveDiffJournal.journal_filename(3, -2, 0) == f"{chunk_id(3, -2, 0)}.json"
