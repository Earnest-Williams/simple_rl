#!/usr/bin/env python3
# tools/ocr_and_update_glyph_chart.py
"""
Rasterize SVG glyphs, OCR keyboard/ANSI block 112..179, template-match as fallback,
and update fonts/glyph_name_chart.md replacing low-confidence keyboard rows.

Usage:
    python tools/ocr_and_update_glyph_chart.py

Requirements (recommended):
    pip install cairosvg pillow numpy pytesseract
    sudo dnf install tesseract   # or appropriate package for your OS
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# cairosvg may be required; import error will be raised when needed
from cairosvg import svg2png  # type: ignore
from PIL import Image, ImageDraw, ImageFont

# Optional OCR
try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore

# === Configuration (adjust if you put files elsewhere) ===
REPO_ROOT: Path = Path(__file__).resolve().parents[1]
FONTS_DIR: Path = REPO_ROOT / "fonts"
SVG_DIR: Path = FONTS_DIR / "classic_roguelike_sliced_svgs"
PNG_DIR: Path = FONTS_DIR / "classic_roguelike_sliced"
PREVIEW_COLOR: Path = FONTS_DIR / "classic_roguelike_preview.png"
GLYPH_CHART: Path = FONTS_DIR / "glyph_name_chart.md"

# Keyboard block to OCR (inclusive start, exclusive end)
KBD_RANGE = range(112, 180)

# Render size for OCR / template matching
RENDER_SIZE: int = 256

# Background color in PNGs that the engine treats as transparent
BG_COLOR = (21, 21, 21)

# Printable ASCII characters (for template rendering fallback)
PRINTABLE_CHARS: list[str] = [chr(c) for c in range(33, 127)]


def clean_tile_background(img: Image.Image) -> Image.Image:
    """Convert BG_COLOR pixels to transparent and return RGBA image.

    NOTE: copy the numpy array to ensure it is writable (avoids 'read-only' error).
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    # create a writable copy of the image data as a numpy array
    arr = np.array(img).copy()
    if arr.shape[2] < 4:
        # Ensure alpha channel exists
        alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
        arr = np.concatenate([arr[:, :, :3], alpha], axis=2)
    mask = np.all(arr[:, :, :3] == BG_COLOR, axis=2)
    arr[mask, 3] = 0
    return Image.fromarray(arr, "RGBA")


def rasterize_svg(svg_path: Path, size: int = RENDER_SIZE) -> Image.Image:
    """
    Rasterize an SVG to a PIL Image at `size` × `size` using cairosvg.
    Raises RuntimeError on failure.
    """
    try:
        png_bytes: bytes = svg2png(
            url=str(svg_path), output_width=size, output_height=size
        )
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        return img
    except Exception as exc:
        raise RuntimeError(f"Failed to rasterize SVG {svg_path}: {exc}")


def ocr_single_char(img: Image.Image) -> tuple[str | None, float]:
    """
    Try to OCR a single character using pytesseract (if installed).
    Returns (character_or_None, confidence 0..1).
    If pytesseract is unavailable, returns (None, 0.0).
    """
    if pytesseract is None:
        return None, 0.0

    # Convert to grayscale, scale down/up to remove aliasing if needed
    gray = img.convert("L")
    # Try to threshold adaptively by mean
    arr = np.asarray(gray).astype(np.float32)
    # If fully blank, return
    if arr.mean() > 250:
        return None, 0.0
    thresh = max(1, int(arr.mean() * 0.9))
    bw = Image.fromarray((arr < thresh).astype("uint8") * 255)
    # pytesseract config: psm 10 single char, whitelist of printable characters
    config = "--psm 10 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()-_=+[]{}\\|;:'\",.<>/?`~"
    try:
        txt = pytesseract.image_to_string(bw, config=config, lang="eng")
        txt = txt.strip()
        if not txt:
            return None, 0.0
        ch = txt[0]
        # Try to get confidence via image_to_data (more robust)
        try:
            data = pytesseract.image_to_data(
                bw, config=config, lang="eng", output_type=pytesseract.Output.DICT
            )
            if "conf" in data and len(data["conf"]) > 0:
                # conf list could be strings; convert safe
                try:
                    conf_vals = [float(c) for c in data["conf"] if c != "-1"]
                    conf_val = conf_vals[0] if conf_vals else 0.0
                    # Normalize 0..100 -> 0..1
                    return ch, max(0.0, min(1.0, conf_val / 100.0))
                except Exception:
                    pass
        except Exception:
            pass
        # As fallback return high confidence since a char was recognized
        return ch, 0.9
    except Exception:
        return None, 0.0


def render_ascii_templates(
    chars: list[str], size: int = RENDER_SIZE
) -> dict[str, Image.Image]:
    """Render ASCII char templates into grayscale images sized `size`×`size`.

    Centers glyphs robustly using textbbox/getsize/textsize depending on Pillow version.
    """
    templates: dict[str, Image.Image] = {}
    # candidate monospace fonts
    font_paths: list[str] = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font_path: str | None = None
    for p in font_paths:
        if Path(p).exists():
            font_path = p
            break
    if font_path:
        font = ImageFont.truetype(font_path, size=int(size * 0.72))
    else:
        font = ImageFont.load_default()  # type: ignore

    for ch in chars:
        img = Image.new("L", (size, size), 255)
        draw = ImageDraw.Draw(img)
        # compute centered offset using available APIs
        try:
            bbox = draw.textbbox((0, 0), ch, font=font)  # left, top, right, bottom
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            offset_x = (size - w) / 2.0 - bbox[0]
            offset_y = (size - h) / 2.0 - bbox[1]
        except Exception:
            try:
                w, h = font.getsize(ch)
                offset_x = (size - w) / 2.0
                offset_y = (size - h) / 2.0
            except Exception:
                try:
                    w, h = draw.textsize(ch, font=font)  # older Pillow
                    offset_x = (size - w) / 2.0
                    offset_y = (size - h) / 2.0
                except Exception:
                    offset_x = size * 0.1
                    offset_y = size * 0.1
        draw.text((offset_x, offset_y), ch, fill=0, font=font)
        templates[ch] = img
    return templates


def mse(a: np.ndarray, b: np.ndarray) -> float:
    """Mean squared error between two arrays."""
    diff = a.astype(np.float32) - b.astype(np.float32)
    return float(np.mean(diff * diff))


def template_match_char(
    img: Image.Image, templates: dict[str, Image.Image]
) -> tuple[str | None, float]:
    """Return the best matching character and a crude confidence (1/(1+mse))."""
    gray = img.convert("L").resize((RENDER_SIZE, RENDER_SIZE), Image.NEAREST)
    a = np.asarray(gray).astype(np.float32)
    best_ch: str | None = None
    best_score = float("inf")
    for ch, tpl in templates.items():
        b = np.asarray(tpl).astype(np.float32)
        score = mse(a, b)
        if score < best_score:
            best_score = score
            best_ch = ch
    if best_ch is None:
        return None, 0.0
    conf = 1.0 / (1.0 + best_score)
    return best_ch, conf


def char_to_kbd_name(ch: str) -> str:
    """Convert a single char to a friendly kbd_ name."""
    mapping: dict[str, str] = {
        "!": "kbd_exclamation",
        "@": "kbd_at",
        "#": "kbd_hash",
        "$": "kbd_dollar",
        "%": "kbd_percent",
        "^": "kbd_caret",
        "&": "kbd_ampersand",
        "*": "kbd_asterisk",
        "(": "kbd_paren_open",
        ")": "kbd_paren_close",
        "-": "kbd_minus",
        "_": "kbd_underscore",
        "=": "kbd_equal",
        "+": "kbd_plus",
        "[": "kbd_bracket_open",
        "]": "kbd_bracket_close",
        "{": "kbd_brace_open",
        "}": "kbd_brace_close",
        "\\": "kbd_backslash",
        "|": "kbd_pipe",
        ";": "kbd_semicolon",
        ":": "kbd_colon",
        "'": "kbd_apostrophe",
        '"': "kbd_quote",
        ",": "kbd_comma",
        ".": "kbd_period",
        "<": "kbd_less",
        ">": "kbd_greater",
        "/": "kbd_slash",
        "?": "kbd_question",
        "`": "kbd_backtick",
        "~": "kbd_tilde",
    }
    if ch.isalpha():
        return f"kbd_{ch.lower()}"
    if ch.isdigit():
        return f"kbd_{ch}"
    return mapping.get(ch, f"kbd_ord_{ord(ch)}")


@dataclass
class ChartRow:
    png: str
    svg: str
    proposed_name: str
    alternate: str
    notes: str


def read_chart(md_path: Path) -> tuple[list[str], dict[str, ChartRow]]:
    """
    Read an existing glyph_name_chart.md into:
      - header lines (list of leading markdown lines)
      - rows mapping keyed by png filename (e.g., 'classic_roguelike_01.png')
    """
    text = md_path.read_text(encoding="utf8")
    lines = text.splitlines()
    header: list[str] = []
    rows: dict[str, ChartRow] = {}

    # Collect header until we reach the table header separator (line with '--- | ---')
    i = 0
    while i < len(lines):
        header.append(lines[i])
        if lines[i].strip().startswith("--- |"):
            i += 1
            break
        i += 1

    # The remaining lines after i are table rows
    for ln in lines[i:]:
        if not ln.strip():
            continue
        parts = [p.strip() for p in ln.split("|")]
        # table might include the header row as well; skip non-row lines
        if len(parts) < 5:
            continue
        png = parts[0]
        svg = parts[1]
        proposed = parts[2]
        alt = parts[3]
        notes = parts[4]
        # store raw strings (we preserve formatting when writing)
        rows[png] = ChartRow(
            png=png, svg=svg, proposed_name=proposed, alternate=alt, notes=notes
        )
    return header, rows


def write_chart(md_path: Path, header: list[str], rows: dict[str, ChartRow]) -> None:
    """Write the chart back to markdown, sorting rows by numeric glyph index."""
    out_lines: list[str] = []
    out_lines.extend(header)
    out_lines.append("")  # spacer
    out_lines.append(
        "png filename | svg filename | proposed_name | alternate_proposed_name | notes"
    )
    out_lines.append("--- | --- | --- | --- | ---")

    def keyfn(k: str) -> int:
        m = re.search(r"_(\d+)\.png", k)
        return int(m.group(1)) if m else 0

    for png in sorted(rows.keys(), key=keyfn):
        r = rows[png]
        out_lines.append(
            f"{r.png} | {r.svg} | {r.proposed_name} | {r.alternate} | {r.notes}"
        )

    md_path.write_text("\n".join(out_lines), encoding="utf8")


def update_keyboard_block(header: list[str], rows: dict[str, ChartRow]) -> None:
    """
    For indices in KBD_RANGE: rasterize SVG, OCR with pytesseract if available,
    otherwise template-match against generated ASCII glyph templates.
    Update rows dict in-place.
    """
    templates = render_ascii_templates(PRINTABLE_CHARS, size=RENDER_SIZE)
    for idx in KBD_RANGE:
        png_name = f"classic_roguelike_{idx}.png"
        svg_name = f"classic_roguelike_{idx}.svg"
        svg_path = SVG_DIR / svg_name
        if not svg_path.exists():
            # If SVG missing, skip
            continue
        try:
            img = rasterize_svg(svg_path, size=RENDER_SIZE)
        except Exception as e:
            # If rasterization fails, note and continue
            note = f"rasterize_failed: {e}"
            if png_name in rows:
                rows[png_name].notes = note
            else:
                rows[png_name] = ChartRow(
                    png=png_name,
                    svg=svg_name,
                    proposed_name=f"kbd_unknown_{idx}",
                    alternate=f"kbd_unknown_{idx}",
                    notes=note,
                )
            continue

        img = clean_tile_background(img)
        # Crop inner area to reduce margin noise (center the glyph)
        w, h = img.size
        crop = img.crop((int(w * 0.08), int(h * 0.06), int(w * 0.92), int(h * 0.94)))

        detected_char: str | None = None
        confidence: float = 0.0
        method: str = "none"

        # Try OCR first
        ch, conf = ocr_single_char(crop)
        if ch is not None and conf >= 0.35:
            detected_char = ch
            confidence = conf
            method = "ocr"

        # Fallback to template matching
        if detected_char is None:
            t_ch, t_conf = template_match_char(crop, templates)
            if t_ch is not None:
                detected_char = t_ch
                confidence = t_conf
                method = "template"

        if detected_char is None:
            proposed = f"kbd_unknown_{idx}"
            alt = proposed
            note = "detection_failed_low_confidence"
        else:
            proposed = char_to_kbd_name(detected_char)
            alt = f"kbd_{detected_char}"
            note = f"detected_by_{method}_conf_{confidence:.2f}"

        if png_name in rows:
            row = rows[png_name]
            row.proposed_name = proposed
            row.alternate = alt
            row.notes = note
        else:
            rows[png_name] = ChartRow(
                png=png_name,
                svg=svg_name,
                proposed_name=proposed,
                alternate=alt,
                notes=note,
            )


def main() -> None:
    if not GLYPH_CHART.exists():
        raise RuntimeError(
            "glyph_name_chart.md not found; run initial pass first and place the file in fonts/"
        )
    header, rows = read_chart(GLYPH_CHART)

    # Immediate manual correction from user: classic_roguelike_03 is a plant tile
    key03 = "classic_roguelike_03.png"
    if key03 in rows:
        rows[key03].proposed_name = "vegetation_bush_small"
        rows[key03].alternate = "plant_clump"
        rows[key03].notes = "plant tile (user_confirmed)"

    # Run OCR/template pass for the keyboard block
    update_keyboard_block(header, rows)

    # Write updated chart back
    write_chart(GLYPH_CHART, header, rows)
    print(
        f"Updated {GLYPH_CHART} for keyboard block {KBD_RANGE.start}..{KBD_RANGE.stop - 1}"
    )


if __name__ == "__main__":
    main()
