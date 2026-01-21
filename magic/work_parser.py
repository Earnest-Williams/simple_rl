from __future__ import annotations

from pyparsing import (
    CaselessKeyword,
    Group,
    MatchFirst,
    OneOrMore,
    ParseException,
    ParserElement,
    SkipTo,
    StringEnd,
)
from pyparsing import Optional as PPOptional

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
    Work,
    WorkDecl,
    compile_ledger_work,
)

# Token is a pair ("KEYWORD" | "VALUE", text)
Token = tuple[str, str]


def create_work_grammar(keywords: list[str]) -> ParserElement:
    """
    Return a pyparsing grammar that recognizes repeated
    KEYWORD [VALUE] entries.

    Each entry is a case-insensitive keyword followed by the text
    up to the next keyword (or end-of-string).
    """
    # Build a MatchFirst of CaselessKeyword objects for case-insensitive
    # keyword recognition.
    kw_parsers = [CaselessKeyword(kw) for kw in keywords]
    any_kw = MatchFirst(kw_parsers)

    # VALUE: everything up to the next keyword or the end of the string.
    value_expr = SkipTo(any_kw | StringEnd(), include=False)

    # An entry is "keyword" [value]
    entry = Group(any_kw("keyword") + PPOptional(value_expr("value")))

    # One or more entries in sequence
    return OneOrMore(entry)


def tokenize(source: str) -> list[Token]:
    """
    Tokenize source string into clause keywords and values using pyparsing.

    Returns a list of ("KEYWORD", <UPPERKEY>) and ("VALUE", <string>)
    tokens. If parsing fails, a ValueError is raised so callers receive a
    clear error.
    """
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

    parser = create_work_grammar(keywords)
    try:
        parsed = parser.parseString(source, parseAll=False)
    except ParseException as exc:
        raise ValueError("Failed to tokenize work declaration") from exc

    tokens: list[Token] = []

    # parsed is a list of groups; each group has "keyword" and optional "value".
    for entry in parsed:
        kw = entry.get("keyword")
        if kw:
            tokens.append(("KEYWORD", kw.upper()))
        # value may be None or an empty string; strip whitespace.
        val = (entry.get("value") or "").strip()
        if val:
            tokens.append(("VALUE", val))

    return tokens


def parse(source: str) -> Work:
    """Parse a ledger work declaration and compile it into a ``Work``.

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
