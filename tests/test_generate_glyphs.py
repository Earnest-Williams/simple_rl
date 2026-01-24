from __future__ import annotations

from pathlib import Path
from typing import List

from scripts.generate_glyphs import (
    GlyphRow,
    find_table_header,
    main,
    normalize_filename,
    select_filename,
)


def resolve_repo_root() -> Path:
    test_path: Path = Path(__file__)
    if test_path.exists():
        return test_path.resolve().parents[1]
    return Path.cwd()


def test_find_table_header_variants() -> None:
    variants: List[str] = [
        "PNG Filename | SVG Filename | Proposed_Name | Alternate_Proposed_Name | Notes",
        "notes | png filename | svg filename | proposed_name | alternate_proposed_name",
        "png filename|svg filename|proposed_name|alternate_proposed_name|notes",
    ]
    for header in variants:
        lines: List[str] = ["intro", header, "--- | --- | --- | --- | ---"]
        assert find_table_header(lines) == 1


def test_normalize_filename_case_insensitive() -> None:
    assert normalize_filename("Classic_Roguelike_01.PNG", ".png") == (
        "Classic_Roguelike_01.PNG"
    )


def test_select_filename_preference() -> None:
    rows: List[GlyphRow] = [
        GlyphRow(
            tile_id=1,
            name="a",
            png=None,
            svg=None,
            alt_names=[],
            notes="",
            confirmed=False,
            raw_notes="",
        ),
        GlyphRow(
            tile_id=1,
            name="b",
            png="b.png",
            svg=None,
            alt_names=[],
            notes="",
            confirmed=True,
            raw_notes="",
        ),
        GlyphRow(
            tile_id=1,
            name="c",
            png="c.png",
            svg="c.svg",
            alt_names=[],
            notes="",
            confirmed=False,
            raw_notes="",
        ),
        GlyphRow(
            tile_id=1,
            name="d",
            png="d.png",
            svg="d.svg",
            alt_names=[],
            notes="",
            confirmed=True,
            raw_notes="",
        ),
    ]
    assert select_filename(rows, "png") == "d.png"
    assert select_filename(rows, "svg") == "d.svg"


def test_write_yaml_deterministic(tmp_path: Path) -> None:
    repo_root: Path = resolve_repo_root()
    chart_path: Path = repo_root / "fonts" / "glyph_name_chart.md"
    png_dir: Path = repo_root / "fonts" / "classic_roguelike_sliced"
    svg_dir: Path = repo_root / "fonts" / "classic_roguelike_sliced_svgs"
    output_yaml: Path = tmp_path / "glyphs.yaml"
    output_report: Path = tmp_path / "glyphs_report.txt"
    committed_yaml: Path = repo_root / "fonts" / "glyphs.yaml"

    result: int = main(
        chart_path=chart_path,
        png_dir=png_dir,
        svg_dir=svg_dir,
        output_yaml=output_yaml,
        output_report=output_report,
    )

    assert result == 0
    assert output_yaml.read_text(encoding="utf-8") == committed_yaml.read_text(
        encoding="utf-8"
    )
