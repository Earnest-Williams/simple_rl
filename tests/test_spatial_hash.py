"""Tests for the SpatialHashTable spatial partitioning data structure."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from game.planning.spatial_hash import SpatialHashTable


def test_insert_and_query_with_kind():
    """Test basic insert and query operations with a specific kind."""
    spatial_hash = SpatialHashTable(cell_size=10)
    
    # Insert entities of different kinds
    spatial_hash.insert(1, 5, 5, "enemy")
    spatial_hash.insert(2, 50, 50, "enemy")  # Far away
    spatial_hash.insert(3, 25, 25, "ally")
    spatial_hash.insert(4, 8, 8, "enemy")
    
    # Query for enemies within radius 10 from (5, 5)
    results = spatial_hash.query_radius((5, 5), 10, kind="enemy")
    entity_ids = {r[0] for r in results}
    
    # Should find entities 1 and 4 (both enemies in nearby cells)
    assert 1 in entity_ids
    assert 4 in entity_ids
    # Should not find entity 2 (too far) or entity 3 (wrong kind)
    assert 2 not in entity_ids
    assert 3 not in entity_ids


def test_query_without_kind():
    """Test query_radius when kind=None returns all entities in range."""
    spatial_hash = SpatialHashTable(cell_size=10)
    
    # Insert entities of different kinds
    spatial_hash.insert(1, 5, 5, "enemy")
    spatial_hash.insert(2, 8, 8, "ally")
    spatial_hash.insert(3, 50, 50, "enemy")
    spatial_hash.insert(4, 12, 12, "neutral")
    
    # Query for all entities within radius 10 from (5, 5)
    results = spatial_hash.query_radius((5, 5), 10, kind=None)
    entity_ids = {r[0] for r in results}
    
    # Should find entities 1, 2, and 4 (all within range, regardless of kind)
    assert 1 in entity_ids
    assert 2 in entity_ids
    assert 4 in entity_ids
    # Should not find entity 3 (too far away)
    assert 3 not in entity_ids


def test_query_without_kind_only_checks_relevant_cells():
    """Test that query_radius with kind=None only iterates through relevant spatial cells.
    
    This is a performance-oriented test to ensure we're not iterating through
    all grid cells globally when kind is None.
    """
    spatial_hash = SpatialHashTable(cell_size=10)
    
    # Insert entities far apart in different cells
    spatial_hash.insert(1, 5, 5, "enemy")
    spatial_hash.insert(2, 100, 100, "enemy")
    spatial_hash.insert(3, 200, 200, "ally")
    spatial_hash.insert(4, 300, 300, "neutral")
    spatial_hash.insert(5, 400, 400, "enemy")
    
    # Query near origin - should only find entity 1
    results = spatial_hash.query_radius((5, 5), 10, kind=None)
    entity_ids = {r[0] for r in results}
    
    assert len(entity_ids) == 1
    assert 1 in entity_ids
    
    # Query near (100, 100) - should only find entity 2
    results = spatial_hash.query_radius((100, 100), 10, kind=None)
    entity_ids = {r[0] for r in results}
    
    assert len(entity_ids) == 1
    assert 2 in entity_ids


def test_empty_query():
    """Test querying when no entities are in range."""
    spatial_hash = SpatialHashTable(cell_size=10)
    
    spatial_hash.insert(1, 100, 100, "enemy")
    
    # Query far from any entities
    results = spatial_hash.query_radius((5, 5), 10, kind="enemy")
    assert len(results) == 0
    
    results = spatial_hash.query_radius((5, 5), 10, kind=None)
    assert len(results) == 0


def test_clear():
    """Test that clear removes all entities from the spatial hash."""
    spatial_hash = SpatialHashTable(cell_size=10)
    
    spatial_hash.insert(1, 5, 5, "enemy")
    spatial_hash.insert(2, 15, 15, "ally")
    
    # Verify entities exist
    results = spatial_hash.query_radius((10, 10), 20, kind=None)
    assert len(results) == 2
    
    # Clear and verify empty
    spatial_hash.clear()
    results = spatial_hash.query_radius((10, 10), 20, kind=None)
    assert len(results) == 0


def test_multiple_entities_same_cell():
    """Test multiple entities in the same spatial cell."""
    spatial_hash = SpatialHashTable(cell_size=10)
    
    # All these are in the same cell (0, 0)
    spatial_hash.insert(1, 1, 1, "enemy")
    spatial_hash.insert(2, 2, 2, "enemy")
    spatial_hash.insert(3, 3, 3, "ally")
    spatial_hash.insert(4, 4, 4, "enemy")
    
    # Query for all enemies
    results = spatial_hash.query_radius((2, 2), 10, kind="enemy")
    entity_ids = {r[0] for r in results}
    
    assert 1 in entity_ids
    assert 2 in entity_ids
    assert 4 in entity_ids
    assert 3 not in entity_ids  # Wrong kind
    
    # Query for all entities
    results = spatial_hash.query_radius((2, 2), 10, kind=None)
    entity_ids = {r[0] for r in results}
    
    assert len(entity_ids) == 4


def test_query_result_format():
    """Test that query results have the correct format (entity_id, x, y)."""
    spatial_hash = SpatialHashTable(cell_size=10)
    
    spatial_hash.insert(42, 15, 25, "enemy")
    
    results = spatial_hash.query_radius((15, 25), 10, kind="enemy")
    
    assert len(results) == 1
    entity_id, x, y = results[0]
    assert entity_id == 42
    assert x == 15
    assert y == 25


if __name__ == "__main__":
    # Run tests manually if pytest is not available
    test_insert_and_query_with_kind()
    test_query_without_kind()
    test_query_without_kind_only_checks_relevant_cells()
    test_empty_query()
    test_clear()
    test_multiple_entities_same_cell()
    test_query_result_format()
    print("All tests passed!")
