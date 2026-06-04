"""Repository-local bridge for the bundled settlement generator."""

from __future__ import annotations

import importlib
import sys

_SUBMODULES: tuple[str, ...] = (
    "acceleration",
    "algorithms",
    "config",
    "export",
    "facilities",
    "generator",
    "model",
)

for _name in _SUBMODULES:
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(
        f"{__name__}.settlegen.{_name}"
    )

from .settlegen import *  # noqa: E402,F403
from .settlegen import __all__ as __all__  # noqa: E402
