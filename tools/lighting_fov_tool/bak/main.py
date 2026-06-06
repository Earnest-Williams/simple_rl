#!/usr/bin/env python3
"""Entry point for the Lighting/FOV Tool.

This tool provides a visual interface for adjusting tile colors, tile assignments,
and light source parameters in a fixed dungeon scene. Configuration can be exported
to a text file for reference or integration into the main game.

Usage:
    python -m tools.lighting_fov_tool.main

Or from the project root:
    python tools/lighting_fov_tool/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_in_path() -> None:
    """Ensure the project root is in sys.path for imports."""
    # Find project root (contains CLAUDE.md or pyproject.toml)
    current = Path(__file__).resolve().parent
    for _ in range(5):  # Max 5 levels up
        if (current / "CLAUDE.md").exists() or (current / "pyproject.toml").exists():
            if str(current) not in sys.path:
                sys.path.insert(0, str(current))
            return
        current = current.parent


def main() -> int:
    """Launch the Lighting/FOV Tool window."""
    _ensure_project_in_path()

    # Import after path setup
    from PySide6.QtWidgets import QApplication

    from tools.lighting_fov_tool.tool_window import LightingFovToolWindow

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Lighting/FOV Tool")

    # Create and show window
    window = LightingFovToolWindow()
    window.show()

    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
