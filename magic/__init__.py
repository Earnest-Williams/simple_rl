"""Utilities for simple magic system involving Works, Wards and Counterseals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import *  # noqa: F401,F403

if TYPE_CHECKING:
    from .executor import ExecutionResult, Work, execute_work
    from .library import MagicLibrary, learn_work, research_work
    from .library import Work as LibraryWork
    from .wards import Counterseal, Ward, is_blocked

__all__: list[str] = [
    "MagicLibrary",
    "LibraryWork",
    "Work",
    "ExecutionResult",
    "learn_work",
    "research_work",
    "execute_work",
    "Ward",
    "Counterseal",
    "is_blocked",
]


def __getattr__(name: str) -> object:
    if name in {
        "MagicLibrary",
        "LibraryWork",
        "learn_work",
        "research_work",
    }:
        from .library import (
            MagicLibrary,
            learn_work,
            research_work,
        )
        from .library import (
            Work as LibraryWork,
        )

        lookup = {
            "MagicLibrary": MagicLibrary,
            "LibraryWork": LibraryWork,
            "learn_work": learn_work,
            "research_work": research_work,
        }
        return lookup[name]

    if name in {"Work", "ExecutionResult", "execute_work"}:
        from .executor import ExecutionResult, Work, execute_work

        lookup = {
            "Work": Work,
            "ExecutionResult": ExecutionResult,
            "execute_work": execute_work,
        }
        return lookup[name]

    if name in {"Ward", "Counterseal", "is_blocked"}:
        from .wards import Counterseal, Ward, is_blocked

        lookup = {"Ward": Ward, "Counterseal": Counterseal, "is_blocked": is_blocked}
        return lookup[name]

    raise AttributeError(f"module 'magic' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
