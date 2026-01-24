"""Shared helpers for glyph tooling."""

from __future__ import annotations

from pathlib import Path


def resolve_repo_root() -> Path:
    script_path: Path = Path(__file__)
    if script_path.exists():
        return script_path.resolve().parents[1]
    return Path.cwd()
