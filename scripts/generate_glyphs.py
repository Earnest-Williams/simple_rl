"""Generate fonts/glyphs.yaml and fonts/glyphs_report.txt from glyph chart."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Final, List, Sequence, Tuple

# Parsing tokens
AMBIGUITY_TOKENS: Final[Tuple[str, ...]] = (
    "best-effort",
    "unclear",
    "uncertain",
    "ambiguous",
)
USER_CLARIFIED_TOKENS: Final[Tuple[str, ...]] = (
    "user clarified",
    "user noted",
)  # tokens indicating explicit confirmation
PLACEHOLDER_TOKENS: Final[frozenset[str]] = frozenset(
    {"", "-", "—", "n/a", "na"}
)  # filename placeholders
TABLE_HEADER: Final[str] = (
    "png filename | svg filename | proposed_name | alternate_proposed_name | notes"
)  # markdown table header
PAREN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\([^)]*\)"
)  # parenthetical content remover
USER_LABEL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*(user clarified|user noted)\s*:\s*", re.IGNORECASE
)  # leading label remover


@dataclass(frozen=True)
class GlyphRow:
    tile_id: int
    name: str
    png: str | None
    svg: str | None
    alt_names: List[str]
    notes: str
    confirmed: bool
    raw_notes: str


@dataclass(frozen=True)
class GlyphEntry:
    tile_id: int
    name: str
    png: str | None
    svg: str | None
    alt_names: List[str]
    notes: str
    confirmed: bool
    raw_notes: List[str]


def main() -> int:
    repo_root: Path = resolve_repo_root()
    chart_path: Path = repo_root / "fonts" / "glyph_name_chart.md"
    png_dir: Path = repo_root / "fonts" / "classic_roguelike_sliced"
    svg_dir: Path = repo_root / "fonts" / "classic_roguelike_sliced_svgs"
    output_yaml: Path = repo_root / "fonts" / "glyphs.yaml"
    output_report: Path = repo_root / "fonts" / "glyphs_report.txt"

    if not chart_path.exists():
        raise FileNotFoundError(f"Glyph chart not found: {chart_path}")

    lines: List[str] = chart_path.read_text(encoding="utf-8").splitlines()
    start_index: int | None = find_table_header(lines)
    if start_index is None:
        raise ValueError("Glyph table header not found in glyph_name_chart.md")

    rows: List[GlyphRow] = []
    skipped_rows: List[str] = []
    missing_images: List[str] = []

    for line in iter_table_lines(lines, start_index):
        row, warnings = parse_row(
            line, png_dir=png_dir, svg_dir=svg_dir
        )
        skipped_rows.extend(warnings)
        if row is None:
            continue
        if row.png is None or row.svg is None:
            missing_images.append(
                format_missing_image(row.tile_id, row.png, row.svg)
            )
        rows.append(row)

    merged: List[GlyphEntry] = merge_rows(rows)
    merged.sort(key=lambda entry: entry.tile_id)

    write_yaml(output_yaml, merged)
    write_report(output_report, skipped_rows, missing_images, merged)
    return 0


def resolve_repo_root() -> Path:
    script_path: Path = Path(__file__)
    if script_path.exists():
        return script_path.parent.parent
    return Path.cwd()


def find_table_header(lines: Sequence[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.strip().startswith(TABLE_HEADER):
            return index
    return None


def iter_table_lines(lines: Sequence[str], start_index: int) -> List[str]:
    table_lines: List[str] = []
    started: bool = False
    for line in lines[start_index + 2 :]:
        if not line.strip():
            if started:
                break
            continue
        if "|" not in line:
            if started:
                break
            continue
        started = True
        table_lines.append(line)
    return table_lines


def parse_row(
    line: str, *, png_dir: Path, svg_dir: Path
) -> Tuple[GlyphRow | None, List[str]]:
    warnings: List[str] = []
    parts: List[str] = [segment.strip() for segment in line.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]

    if len(parts) < 5:
        warnings.append(f"Skipped row (fewer than 5 columns): {line}")
        return None, warnings
    if len(parts) > 5:
        extras_parts: List[str] = [segment.strip() for segment in parts[4:]]
        notes_raw: str = "|".join(extras_parts).strip()
        notes_raw = notes_raw.strip("|").strip()
        parts = [parts[0], parts[1], parts[2], parts[3], notes_raw]

    png_cell, svg_cell, proposed_name, alt_cell, notes_cell = parts
    if not proposed_name:
        warnings.append(f"Skipped row (missing proposed_name): {line}")
        return None, warnings

    png_value: str | None = normalize_filename(png_cell, ".png")
    svg_value: str | None = normalize_filename(svg_cell, ".svg")

    tile_id: int | None = extract_tile_id(png_value)
    if tile_id is None:
        tile_id = extract_tile_id(svg_value)
    if tile_id is None:
        warnings.append(f"Skipped row (missing tile_id): {line}")
        return None, warnings

    if png_value is not None:
        png_path: Path = png_dir / png_value
        if not png_path.exists():
            warnings.append(
                f"Missing PNG file for tile {tile_id}: {png_value}"
            )
            png_value = None

    if svg_value is not None:
        svg_path: Path = svg_dir / svg_value
        if not svg_path.exists():
            warnings.append(
                f"Missing SVG file for tile {tile_id}: {svg_value}"
            )
            svg_value = None

    alt_names: List[str] = split_alt_names(alt_cell)
    notes_cleaned, confirmed = clean_notes(notes_cell)
    if png_value is None or svg_value is None:
        confirmed = False

    row = GlyphRow(
        tile_id=tile_id,
        name=proposed_name,
        png=png_value,
        svg=svg_value,
        alt_names=alt_names,
        notes=notes_cleaned,
        confirmed=confirmed,
        raw_notes=notes_cell,
    )
    return row, warnings


def normalize_filename(value: str, suffix: str) -> str | None:
    if not value:
        return None
    lowered: str = value.strip().lower()
    if lowered in PLACEHOLDER_TOKENS:
        return None
    if not value.endswith(suffix):
        return None
    return value.strip()


def extract_tile_id(filename: str | None) -> int | None:
    if filename is None:
        return None
    stem: str = Path(filename).stem
    if "_" not in stem:
        return None
    tail: str = stem.rsplit("_", 1)[-1]
    if not tail.isdigit():
        return None
    return int(tail)


def split_alt_names(value: str) -> List[str]:
    if not value:
        return []
    parts: List[str] = [segment.strip() for segment in value.split(",")]
    return [part for part in parts if part]


def clean_notes(raw_notes: str) -> Tuple[str, bool]:
    raw_lower: str = raw_notes.lower()
    has_user_clarified: bool = any(
        token in raw_lower for token in USER_CLARIFIED_TOKENS
    )
    has_ambiguity: bool = any(token in raw_lower for token in AMBIGUITY_TOKENS)

    cleaned: str = PAREN_PATTERN.sub("", raw_notes)
    cleaned = USER_LABEL_PATTERN.sub("", cleaned)
    cleaned = cleaned.strip()

    for token in AMBIGUITY_TOKENS:
        cleaned = cleaned.replace(token, "")
    cleaned = cleaned.replace("(", "")
    cleaned = cleaned.replace(")", "")
    cleaned = cleaned.strip()

    if cleaned:
        cleaned = " ".join(cleaned.split())

    confirmed: bool
    if has_ambiguity:
        confirmed = False
    elif has_user_clarified and cleaned:
        confirmed = True
    elif cleaned:
        confirmed = True
    else:
        confirmed = False

    return cleaned, confirmed


def merge_rows(rows: Sequence[GlyphRow]) -> List[GlyphEntry]:
    grouped: dict[int, List[GlyphRow]] = {}
    for row in rows:
        grouped.setdefault(row.tile_id, []).append(row)

    merged: List[GlyphEntry] = []
    for tile_id, tile_rows in grouped.items():
        merged.append(merge_tile_rows(tile_id, tile_rows))
    return merged


def merge_tile_rows(tile_id: int, rows: Sequence[GlyphRow]) -> GlyphEntry:
    name: str = rows[0].name
    confirmed_names: List[str] = [row.name for row in rows if row.confirmed]
    if confirmed_names:
        name = confirmed_names[0]

    alt_names: List[str] = []
    for row in rows:
        for alt in row.alt_names:
            if alt not in alt_names:
                alt_names.append(alt)

    notes_list: List[str] = []
    for row in rows:
        if row.notes and row.notes not in notes_list:
            notes_list.append(row.notes)

    notes: str = "; ".join(notes_list)
    confirmed: bool = any(row.confirmed for row in rows)
    png_value: str | None = select_filename(rows, "png")
    svg_value: str | None = select_filename(rows, "svg")

    raw_notes: List[str] = [row.raw_notes for row in rows if row.raw_notes]
    return GlyphEntry(
        tile_id=tile_id,
        name=name,
        png=png_value,
        svg=svg_value,
        alt_names=alt_names,
        notes=notes,
        confirmed=confirmed,
        raw_notes=raw_notes,
    )


def select_filename(rows: Sequence[GlyphRow], field: str) -> str | None:
    for row in rows:
        value: str | None
        if field == "png":
            value = row.png
        else:
            value = row.svg
        if value is not None:
            return value
    return None


def yaml_quote(value: str) -> str:
    escaped: str = value.replace("'", "''")
    return f"'{escaped}'"


def write_yaml(path: Path, entries: Sequence[GlyphEntry]) -> None:
    lines: List[str] = ["glyphs:"]
    for entry in entries:
        lines.append(f"  - name: {yaml_quote(entry.name)}")
        lines.append(f"    tile_id: {entry.tile_id}")
        lines.append(f"    png: {format_optional(entry.png)}")
        lines.append(f"    svg: {format_optional(entry.svg)}")
        if entry.alt_names:
            lines.append("    alt_names:")
            for alt in entry.alt_names:
                lines.append(f"      - {yaml_quote(alt)}")
        else:
            lines.append("    alt_names: []")
        if entry.notes:
            lines.append(f"    notes: {yaml_quote(entry.notes)}")
        else:
            lines.append("    notes: ''")
        lines.append(f"    confirmed: {str(entry.confirmed).lower()}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def format_optional(value: str | None) -> str:
    if value is None:
        return "null"
    return yaml_quote(value)


def format_missing_image(tile_id: int, png: str | None, svg: str | None) -> str:
    if png is None and svg is None:
        return f"tile {tile_id}: missing png and svg"
    if png is None:
        return f"tile {tile_id}: missing png"
    if svg is None:
        return f"tile {tile_id}: missing svg"
    return f"tile {tile_id}: missing images"


def write_report(
    path: Path,
    skipped_rows: Sequence[str],
    missing_images: Sequence[str],
    entries: Sequence[GlyphEntry],
) -> None:
    lines: List[str] = []
    if skipped_rows:
        lines.append("Skipped rows:")
        for warning in skipped_rows:
            lines.append(f"- {warning}")
        lines.append("")
    if missing_images:
        lines.append("Missing image files:")
        for warning in missing_images:
            lines.append(f"- {warning}")
        lines.append("")
    ambiguous: List[str] = []
    for entry in entries:
        if not entry.confirmed:
            notes_blob: str = "; ".join(entry.raw_notes)
            if not notes_blob:
                notes_blob = "(no notes)"
            ambiguous.append(f"tile {entry.tile_id}: {notes_blob}")
    if ambiguous:
        lines.append("Ambiguous glyphs:")
        for item in ambiguous:
            lines.append(f"- {item}")
        lines.append("")
    if not lines:
        lines.append("No issues found.")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
