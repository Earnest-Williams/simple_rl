from __future__ import annotations

import pytest

from magic import work_parser
from magic.models import Work

VALID_WORK_SOURCE = """
ART ward
BOUNDS target self
BALANCES cost low
FLOW immediate
SEALS sigil
PROVISIONS mana
INTENT protect
"""


def test_parse_valid_work_declaration() -> None:
    work = work_parser.parse(VALID_WORK_SOURCE)

    assert isinstance(work, Work)


def test_parse_rejects_missing_required_clause() -> None:
    with pytest.raises(ValueError, match="Missing required clause INTENT"):
        work_parser.parse(
            """
ART ward
BOUNDS target self
BALANCES cost low
FLOW immediate
SEALS sigil
PROVISIONS mana
"""
        )


def test_tokenize_rejects_unknown_text() -> None:
    with pytest.raises(ValueError, match="Failed to tokenize work declaration"):
        work_parser.tokenize("UNKNOWN clause")
