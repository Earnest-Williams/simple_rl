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

# All clause keywords recognised by the ledger grammar.
WORK_KEYWORDS: list[str] = [
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
    parser = create_work_grammar(WORK_KEYWORDS)
    try:
        parsed = parser.parse_string(source, parse_all=True)
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

    Clauses can appear in any order, but all required clauses must be present.

    Parameters
    ----------
    source:
        Text of the work declaration following the ledger grammar.

    Returns
    -------
    Work
        Executable representation of the work compiled from the declaration.
    """
    parser = create_work_grammar(WORK_KEYWORDS)
    try:
        parsed = parser.parse_string(source, parse_all=True)
    except ParseException as exc:
        raise ValueError("Failed to parse work declaration") from exc

    # Build a clauses dict directly from the structured pyparsing parse result,
    # avoiding the intermediate flat Token list produced by tokenize().
    clauses: dict[str, str] = {}
    for entry in parsed:
        kw = entry.get("keyword")
        if not kw:
            continue
        kw_upper = kw.upper()
        if kw_upper in clauses:
            raise ValueError(f"Duplicate {kw_upper} clause")
        # value may be None or empty string when pyparsing matches a keyword
        # with no trailing text; treat both as a missing value.
        val = entry.get("value")
        val = val.strip() if val is not None else ""
        if not val:
            raise ValueError(f"Expected value following {kw_upper} clause keyword")
        clauses[kw_upper] = val

    # Check that all required clauses are present
    required = ["ART", "BOUNDS", "BALANCES", "FLOW", "SEALS", "PROVISIONS", "INTENT"]
    for clause_name in required:
        if clause_name not in clauses:
            raise ValueError(f"Missing required clause {clause_name}")

    # Construct clause objects
    art = ArtClause(clauses["ART"])
    bounds = BoundsClause(clauses["BOUNDS"])
    balances = BalancesClause(clauses["BALANCES"])
    flow = FlowClause(clauses["FLOW"])
    seals = SealsClause(clauses["SEALS"])
    provisions = ProvisionsClause(clauses["PROVISIONS"])
    intent = IntentClause(clauses["INTENT"])

    # Optional clauses
    seat = SeatClause(clauses["SEAT"]) if "SEAT" in clauses else None
    tending = TendingClause(clauses["TENDING"]) if "TENDING" in clauses else None

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
