from __future__ import annotations

from ..model import Settlement, TerrainCode

ASCII = {
    TerrainCode.VOID: " ",
    TerrainCode.GRASS: ".",
    TerrainCode.FOREST: "f",
    TerrainCode.DENSE_FOREST: "F",
    TerrainCode.FARMLAND: ",",
    TerrainCode.ORCHARD: "o",
    TerrainCode.PASTURE: "p",
    TerrainCode.HILL: "^",
    TerrainCode.MOUNTAIN: "A",
    TerrainCode.ROAD: "#",
    TerrainCode.PLAZA: "=",
    TerrainCode.WATER: "~",
    TerrainCode.DEEP_WATER: "~",
    TerrainCode.SHORE: ":",
    TerrainCode.MARSH: ";",
    TerrainCode.SWAMP: "%",
    TerrainCode.BRIDGE: "+",
    TerrainCode.WALL: "W",
    TerrainCode.PALISADE: "P",
    TerrainCode.GATE: "G",
    TerrainCode.BUILDING: "B",
    TerrainCode.RUIN: "x",
    TerrainCode.CEMETERY: "t",
    TerrainCode.DOCK: "D",
    TerrainCode.DYKE: "_",
    TerrainCode.MAGIC: "*",
    TerrainCode.FIELD: ",",
    TerrainCode.EMPTY_LOT: "-",
    TerrainCode.MOAT: "~",
}

UNICODE_ASCII = {
    **ASCII,
    TerrainCode.FOREST: "♣",
    TerrainCode.DENSE_FOREST: "♠",
    TerrainCode.MOUNTAIN: "▲",
    TerrainCode.WALL: "█",
    TerrainCode.PALISADE: "ǂ",
    TerrainCode.GATE: "╬",
    TerrainCode.CEMETERY: "†",
}


def render_ascii(
    settlement: Settlement,
    *,
    unicode: bool = False,
    crop: tuple[int, int, int, int] | None = None,
) -> str:
    """Render a settlement as text for logs/tests/dev tools.

    This is deliberately outside the generator. Games should consume the data
    model directly and use their own tile renderer.
    """
    chars = UNICODE_ASCII if unicode else ASCII
    grid = settlement.combined_grid()
    if crop:
        x, y, w, h = crop
        grid = grid[y : y + h, x : x + w]
    lines: list[str] = []
    for row in grid:
        lines.append("".join(chars.get(TerrainCode(int(v)), "?") for v in row))
    return "\n".join(lines)
