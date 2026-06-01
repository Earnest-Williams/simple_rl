from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast


def _load_scan_source() -> Callable[[str, str], list[str]]:
    checker_path = (
        Path(__file__).parents[1] / "scripts" / "check_deterministic_random.py"
    )
    namespace = runpy.run_path(str(checker_path))
    scan_source = namespace["_scan_source"]
    assert callable(scan_source)
    return cast("Callable[[str, str], list[str]]", scan_source)


_SCAN_SOURCE = _load_scan_source()


def test_scan_source_ignores_comments_strings_and_docstrings() -> None:
    source = '''
"""Documentation can mention import random and numpy.random safely."""

TEXT = "random.random and os.urandom are text, not code"
# import random
# np.random.random()
'''

    assert _SCAN_SOURCE(source, "example.py") == []


def test_scan_source_reports_disallowed_imports_and_alias_usage() -> None:
    source = """
import random as py_random
import numpy as np
import os

value = py_random.random()
other = np.random.default_rng(123)
bytes_value = os.urandom(8)
"""

    violations = _SCAN_SOURCE(source, "example.py")

    assert "import random" in violations
    assert "random" in violations
    assert "numpy.random" in violations
    assert "os.urandom" in violations


def test_scan_source_reports_from_import_entrypoints() -> None:
    source = """
from random import randint
from numpy import random as numpy_random
from uuid import uuid4

value = randint(1, 2)
other = numpy_random.default_rng(123)
identifier = uuid4()
"""

    violations = _SCAN_SOURCE(source, "example.py")

    assert "from random" in violations
    assert "from numpy import random" in violations
    assert "uuid.uuid4" in violations
