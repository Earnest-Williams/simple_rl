from __future__ import annotations

from pathlib import Path

from engine.glyphs import tile_id_for
from game.world.overland_presentation import (
    OVERLAND_MATERIAL_PRESENTATION,
    get_resolved_overland_presentation,
)


def test_overland_fallback_glyphs_all_exist() -> None:
    for pres in OVERLAND_MATERIAL_PRESENTATION.values():
        assert tile_id_for(pres.fallback_glyph_name, default=None) is not None


def test_overland_presentations_resolve_to_nonzero_glyph_indices() -> None:
    resolved = get_resolved_overland_presentation()
    assert resolved

    failures = [
        (mat_id, pres.glyph_name, pres.fallback_glyph_name)
        for mat_id, pres in resolved.items()
        if pres.glyph_index <= 0
    ]
    assert not failures


def test_missing_glyphs_doc_mentions_unavailable_desired_glyphs() -> None:
    doc = Path("docs/missing_glyphs.md").read_text(encoding="utf-8")
    for pres in OVERLAND_MATERIAL_PRESENTATION.values():
        if tile_id_for(pres.glyph_name, default=None) is None:
            assert pres.glyph_name in doc
            assert pres.fallback_glyph_name in doc
