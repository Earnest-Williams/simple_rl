from __future__ import annotations

from pathlib import Path

import yaml

_cache: dict[Path, dict[str, int]] = {}


def _default_glyphs_path() -> Path:
    return Path(__file__).parent.parent / "fonts" / "glyphs.yaml"


def _coerce_tile_id(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def load_glyph_map(path: str | Path | None = None) -> dict[str, int]:
    """
    Returns a mapping name_or_alt_name -> tile_id (int).
    Caches result so repeated imports are cheap.
    """
    glyphs_path = Path(path) if path is not None else _default_glyphs_path()
    if glyphs_path in _cache:
        return _cache[glyphs_path]

    if not glyphs_path.exists():
        _cache[glyphs_path] = {}
        return {}

    data = yaml.safe_load(glyphs_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        _cache[glyphs_path] = {}
        return {}

    glyph_entries = data.get("glyphs", [])
    if not isinstance(glyph_entries, list):
        _cache[glyphs_path] = {}
        return {}

    out: dict[str, int] = {}
    for entry in glyph_entries:
        if not isinstance(entry, dict):
            continue
        tile_id = _coerce_tile_id(entry.get("tile_id"))
        if tile_id is None:
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            out[name] = tile_id
        alt_names = entry.get("alt_names", [])
        if isinstance(alt_names, list):
            for alt in alt_names:
                if isinstance(alt, str) and alt:
                    out[alt] = tile_id
    _cache[glyphs_path] = out
    return out


def tile_id_for(name: str, default: int | None = None) -> int | None:
    """Case-sensitive lookup first, then lower-case keys as fallback."""
    if not name:
        return default
    glyphs = load_glyph_map()
    if name in glyphs:
        return glyphs[name]
    lowered = name.lower()
    for key, value in glyphs.items():
        if key.lower() == lowered:
            return value
    return default


def name_for(tile_id: int) -> str | None:
    for name, value in load_glyph_map().items():
        if value == tile_id:
            return name
    return None
