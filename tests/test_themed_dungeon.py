# tests/test_themed_dungeon.py
from __future__ import annotations

import polars as pl

from common.constants import Material
from Dungeon.core import CaveGenerator
from Dungeon.processor import process_backbone_graph
from Dungeon.shaper import generate_shaped_cave
from utils.game_rng import GameRNG
from worldgen.overland.schema import EvidenceTag, Substrate


def _generate_themed_cave(payload: dict) -> pl.DataFrame:
    rng = GameRNG(seed=42)
    generator = CaveGenerator(
        max_nodes=30, max_depth=6, rng=rng, transition_payload=payload
    )
    generator.grow()
    raw_backbone = {"nodes": [n.to_dict() for n in generator.nodes]}

    augmented_nodes, augmented_node_map = process_backbone_graph(raw_backbone)
    shaped_map = generate_shaped_cave(
        augmented_nodes,
        augmented_node_map,
        rng=rng,
        ca_iterations=2,
        transition_payload=payload,
    )
    return generator, shaped_map


def test_dungeon_without_payload() -> None:
    generator, shaped_map = _generate_themed_cave({})
    assert shaped_map is not None
    # By default, floor tiles are CAVE_FLOOR
    materials = shaped_map.get_column("material_id").to_list()
    assert int(Material.CAVE_FLOOR) in materials
    assert int(Material.LAVA_TUBE_FLOOR) not in materials


def test_basalt_substrate_themed_dungeon() -> None:
    payload = {
        "substrate": int(Substrate.BASALT),
        "cave_type": "lava_tube_skylight",
        "evidence_tags": [],
    }
    generator, shaped_map = _generate_themed_cave(payload)
    assert shaped_map is not None

    materials = shaped_map.get_column("material_id").to_list()
    # Floor tiles should be LAVA_TUBE_FLOOR instead of CAVE_FLOOR
    assert int(Material.LAVA_TUBE_FLOOR) in materials
    assert int(Material.CAVE_FLOOR) not in materials


def test_flow_group_flooded_themed_dungeon() -> None:
    payload = {
        "substrate": int(Substrate.LIMESTONE),
        "flow_group": 3,
        "evidence_tags": [],
    }
    generator, shaped_map = _generate_themed_cave(payload)
    assert shaped_map is not None

    materials = shaped_map.get_column("material_id").to_list()
    # Deepest floor tiles should be flooded with UNDERGROUND_WATER
    assert int(Material.UNDERGROUND_WATER) in materials
    assert int(Material.CAVE_FLOOR) in materials  # non-flooded part remains floor


def test_evidence_tags_themed_backbone() -> None:
    payload = {
        "substrate": int(Substrate.LIMESTONE),
        "evidence_tags": [
            int(EvidenceTag.PRECURSOR_OCCUPATION),
            int(EvidenceTag.PRIOR_EXPEDITION),
        ],
    }
    generator, shaped_map = _generate_themed_cave(payload)

    # Check that at least one node has a precursor or prior expedition feature
    features = [n.feature for n in generator.nodes if n.feature]
    assert any("precursor_ruin" in f or "prior_expedition_camp" in f for f in features)
