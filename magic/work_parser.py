from __future__ import annotations

from typing import List, Tuple

from pyparsing import (
    CaselessKeyword,
    ParserElement,
    ParseException,
    Regex,
    SkipTo,
    ZeroOrMore,
    pyparsing_common,
)

from .models import (
    ArtClause,
    BalancesClause,
    BoundsClause,
    FlowClause,
    IntentClause,
    ProvisionsClause,
    SealsClause,
    SeatClause,
    TendingClause,
    WorkDecl,
    compile_ledger_work,
    Work,
)

# Enable packrat parsing for better performance
ParserElement.enablePackrat()

Token = Tuple[str, str]


def create_work_grammar() -> ParserElement:
    """
    Create pyparsing grammar for Work declarations.

    Grammar structure:
        work := ART value BOUNDS value BALANCES value FLOW value
                SEALS value PROVISIONS value INTENT value
                [SEAT value] [TENDING value]

    Returns:
        ParserElement that can parse work declarations
    """
    # Define keywords (case-insensitive)
    art_kw = CaselessKeyword("ART")
    bounds_kw = CaselessKeyword("BOUNDS")
    balances_kw = CaselessKeyword("BALANCES")
    flow_kw = CaselessKeyword("FLOW")
    seals_kw = CaselessKeyword("SEALS")
    provisions_kw = CaselessKeyword("PROVISIONS")
    intent_kw = CaselessKeyword("INTENT")
    seat_kw = CaselessKeyword("SEAT")
    tending_kw = CaselessKeyword("TENDING")

    # Keywords that can follow a value
    next_keyword = (
        art_kw
        | bounds_kw
        | balances_kw
        | flow_kw
        | seals_kw
        | provisions_kw
        | intent_kw
        | seat_kw
        | tending_kw
    )

    # Value: everything up to the next keyword (or end of string)
    # SkipTo will capture text until it encounters the next keyword
    value = SkipTo(next_keyword | pyparsing_common.stringEnd).setResultsName(
        "value", listAllMatches=True
    )

    # Define clauses
    art_clause = art_kw + value
    bounds_clause = bounds_kw + value
    balances_clause = balances_kw + value
    flow_clause = flow_kw + value
    seals_clause = seals_kw + value
    provisions_clause = provisions_kw + value
    intent_clause = intent_kw + value
    seat_clause = seat_kw + value
    tending_clause = tending_kw + value

    # Complete grammar: required clauses + optional clauses
    work_decl = (
        art_clause
        + bounds_clause
        + balances_clause
        + flow_clause
        + seals_clause
        + provisions_clause
        + intent_clause
        + ZeroOrMore(seat_clause | tending_clause)
    )

    return work_decl


def tokenize(source: str) -> List[Token]:
    """
    Tokenize source string into clause keywords and values using pyparsing.

    This function is kept for backward compatibility but now uses pyparsing
    instead of regex, complying with AGENTS.md Section 1.6.
    """
    tokens: List[Token] = []

    # Define keywords
    keywords = [
        "ART",
        "BOUNDS",
        "BALANCES",
        "FLOW",
        "SEALS",
        "PROVISIONS",
        "INTENT",
        "SEAT",
        "TENDING",
    ]

    # Create a grammar for a single keyword
    keyword_parser = None
    for kw in keywords:
        kw_elem = CaselessKeyword(kw)
        if keyword_parser is None:
            keyword_parser = kw_elem
        else:
            keyword_parser = keyword_parser | kw_elem

    # Parse the source to extract keywords and values
    pos = 0
    while pos < len(source):
        source_remaining = source[pos:].lstrip()
        if not source_remaining:
            break

        # Try to match a keyword at current position
        try:
            result = keyword_parser.parseString(source_remaining, parseAll=False)
            keyword = result[0].upper()
            tokens.append(("KEYWORD", keyword))
            # Move past the keyword
            match_len = len(result[0])
            pos += len(source[pos:]) - len(source_remaining) + match_len
            continue
        except ParseException:
            # Not a keyword, extract value until next keyword
            next_kw_pos = None
            for kw in keywords:
                try:
                    kw_parser = CaselessKeyword(kw)
                    # Find next keyword position
                    for i in range(len(source_remaining)):
                        try:
                            kw_parser.parseString(source_remaining[i:], parseAll=False)
                            if next_kw_pos is None or i < next_kw_pos:
                                next_kw_pos = i
                            break
                        except ParseException:
                            continue
                except ParseException:
                    continue

            if next_kw_pos is not None:
                value = source_remaining[:next_kw_pos].strip()
            else:
                value = source_remaining.strip()

            if value:
                tokens.append(("VALUE", value))
                pos += len(source[pos:]) - len(source_remaining) + len(value)
            else:
                # Avoid infinite loop
                pos += 1

    return tokens


def parse(source: str) -> Work:
    """Parse a ledger work declaration and compile it into a ``Work``.

    This function now uses pyparsing instead of regex for structured parsing,
    complying with AGENTS.md Section 1.6 (regex as last resort).

    The function first constructs a :class:`~magic.models.WorkDecl` AST composed of
    clause dataclasses (:class:`ArtClause`, :class:`BoundsClause`, etc.).  The
    resulting declaration is then converted into an engine-level
    :class:`~magic.models.Work` using :func:`compile_ledger_work`.

    Parameters
    ----------
    source:
        Text of the work declaration following the ledger grammar.

    Returns
    -------
    Work
        Executable representation of the work compiled from the declaration.
    """

    tokens = tokenize(source)
    index = 0

    def expect_keyword(name: str) -> None:
        nonlocal index
        if index >= len(tokens) or tokens[index] != ("KEYWORD", name):
            raise ValueError(f"Expected clause {name}")
        index += 1

    def read_value() -> str:
        nonlocal index
        if index >= len(tokens) or tokens[index][0] != "VALUE":
            raise ValueError("Expected value following clause keyword")
        value = tokens[index][1]
        index += 1
        return value

    expect_keyword("ART")
    art = ArtClause(read_value())
    expect_keyword("BOUNDS")
    bounds = BoundsClause(read_value())
    expect_keyword("BALANCES")
    balances = BalancesClause(read_value())
    expect_keyword("FLOW")
    flow = FlowClause(read_value())
    expect_keyword("SEALS")
    seals = SealsClause(read_value())
    expect_keyword("PROVISIONS")
    provisions = ProvisionsClause(read_value())
    expect_keyword("INTENT")
    intent = IntentClause(read_value())

    seat: SeatClause | None = None
    tending: TendingClause | None = None
    while index < len(tokens):
        token_type, token_value = tokens[index]
        if token_type != "KEYWORD":
            raise ValueError(f"Unexpected token {token_value}")
        if token_value == "SEAT":
            if seat is not None:
                raise ValueError("Duplicate SEAT clause")
            index += 1
            seat = SeatClause(read_value())
        elif token_value == "TENDING":
            if tending is not None:
                raise ValueError("Duplicate TENDING clause")
            index += 1
            tending = TendingClause(read_value())
        else:
            raise ValueError(f"Unexpected clause {token_value}")

    if index != len(tokens):
        raise ValueError("Unexpected trailing tokens")

    decl = WorkDecl(
        art=art,
        bounds=bounds,
        balances=balances,
        flow=flow,
        seals=seals,
        provisions=provisions,
        intent=intent,
        seat=seat,
        tending=tending,
    )
    return compile_ledger_work(decl)
