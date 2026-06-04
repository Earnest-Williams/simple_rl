# Configuration and data reference

This reference lists the repository's checked-in configuration and data files,
who consumes them, and the high-level shape expected by current code. It is not
a replacement for runtime validation; update it whenever configuration semantics
change.

## Runtime configuration

| File | Consumer | Shape and notes |
| --- | --- | --- |
| `config/config.yaml` | `tools/play_from_arrow.py`, `engine/window_manager.py`, rendering and gameplay setup | Main application settings. Top-level keys include tileset path and tile size, map dimensions, dungeon seed, player settings, engine toggles, lighting, memory fade, height visualization, gameplay rules, and AI defaults. |
| `config/keybindings.toml` | `tools/play_from_arrow.py`, `engine/window_manager_modules/input_handler.py` | TOML table of active keybindings. The input handler reads the `bindings` table and maps configured keys to movement or UI actions. |
| `config/overlays.toml` | `engine/window_manager_modules/ui_overlay_manager.py` | Optional UI overlay definitions. The manager reads repeated `overlay` entries for text or image overlays with position and display settings. |
| `config/sounds.yaml` | `game/systems/sound.py` | Sound-event and music configuration. Supports file-backed and generated effects, per-effect settings, volume, pitch variation, conditions, and ambience/music settings. |
| `config/ai_mappings.yaml` | AI configuration loaded into game state and read by `game/systems/ai_system.py` | Maps entity `species` values to AI adapters and `intelligence` tiers to GOAP planning depth. |
| `config/entities.yaml` | Entity template loading | `templates` mapping keyed by template ID. Templates may include glyph, color, name, movement blocking, portal targets, hit points, species, and intelligence. |
| `config/items.yaml` | Item registry loading | `templates` mapping keyed by item template ID. Templates describe item name, glyph, foreground color, item type, equipment slot, flags, attributes, effects, mount points, and attachment metadata. |
| `config/effects.yaml` | Effect-system configuration | `effects` mapping keyed by effect ID. Entries describe effect type, target category, logic handler, trigger event or conditions when applicable, params, and description. |

## Data files

| File or group | Consumer | Shape and notes |
| --- | --- | --- |
| `data/items.json` | Item/content data consumers | JSON item data retained separately from YAML item templates. Keep IDs stable when referenced externally. |
| `data/monsters.json` | Monster/content data consumers | JSON monster definitions for content experiments and integration. |
| `data/lexica/*.json`, `data/lexica/*.yaml` | `tools/sample_variants.py` and narrative/template generation | Lexicon files contain word lists such as `adjectives`, `nouns`, `features`, `verbs`, `adverbs`, and `clauses`. |
| `data/templates/room_templates.json` | `tools/sample_variants.py` and room-description generation | Maps style names such as `terse`, `neutral`, `ornate`, and `wry` to format strings that consume lexicon keys. |
| `data/templates/jinja_examples.txt` | Template examples and documentation | Example Jinja-style text templates; treat as documentation/sample data unless promoted to a runtime input. |

## Generated and derived metadata

| File | Source | Policy |
| --- | --- | --- |
| `fonts/glyphs.yaml` | `python scripts/generate_glyphs.py` | Checked-in generated runtime metadata; regenerate when glyph mappings or source charts change. |
| `fonts/glyphs_report.txt` | `python scripts/generate_glyphs.py` | Checked-in generated review report for glyph metadata changes. |
| `fonts/tree.txt` | Historical local inventory | Archival diagnostic snapshot only; use `rg --files fonts` for current inventory. |

See `docs/ASSET_PIPELINE.md` for the detailed asset policy.

## Change guidelines

1. Prefer adding validation in loaders before broadening a schema.
2. Keep IDs stable; migrations should preserve old IDs or document the breaking
   change clearly.
3. Do not commit local generated gameplay outputs unless a document explains why
   the artifact is a stable fixture or review asset.
4. When adding a new config file, document its path, consumer, schema shape, and
   owner in this reference as part of the same change.
