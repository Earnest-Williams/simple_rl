"""Enhanced output generation with reproducible variety.

This module provides tools for generating interesting, varied, and reproducible
output text using GameRNG for determinism. All variations are testable, replayable,
and integrate cleanly with the project's logging and testing infrastructure.

Key Features:
- VariationEngine: Template-driven text generation with seeded randomness
- Structured logging: JSON outputs with RNG state for reproducibility
- Variety metrics: Polars-based analysis of output diversity
- Anti-repeat biasing: LRU-based memory to avoid recent repetitions
- Name generation: Markov chain-based phonotactic generator
- Dual-mode output: Human-friendly pretty printing and machine-readable NDJSON

All randomness uses GameRNG, ensuring full reproducibility and replayability.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

if TYPE_CHECKING:
    from jinja2 import Environment

from utils.game_rng import GameRNG


# ---------------------------------------------------------------------------
# Enums and Constants
# ---------------------------------------------------------------------------


class ToneProfile(Enum):
    """Output tone/persona for variation generation."""
    TERSE = auto()
    NEUTRAL = auto()
    ORNATE = auto()
    WRY = auto()


class OutputMode(Enum):
    """Output format mode."""
    HUMAN = auto()  # Pretty, colored, with optional typing effects
    MACHINE = auto()  # Compact NDJSON with seed/state


# ---------------------------------------------------------------------------
# Core Variation Engine
# ---------------------------------------------------------------------------


@dataclass
class Lexicon:
    """Container for word lists used in text generation."""
    adjectives: list[str] = field(default_factory=list)
    nouns: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    verbs: list[str] = field(default_factory=list)
    adverbs: list[str] = field(default_factory=list)
    clauses: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, list[str]]) -> Lexicon:
        """Create lexicon from dictionary."""
        return cls(
            adjectives=data.get("adjectives", []),
            nouns=data.get("nouns", []),
            features=data.get("features", []),
            verbs=data.get("verbs", []),
            adverbs=data.get("adverbs", []),
            clauses=data.get("clauses", [])
        )

    @classmethod
    def load_from_file(cls, path: str | Path) -> Lexicon:
        """Load lexicon from JSON or YAML file."""
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            if path.suffix == '.json':
                data = json.load(f)
            elif path.suffix in {'.yaml', '.yml'}:
                import yaml
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, list[str]]:
        """Export lexicon to dictionary."""
        return {
            "adjectives": self.adjectives,
            "nouns": self.nouns,
            "features": self.features,
            "verbs": self.verbs,
            "adverbs": self.adverbs,
            "clauses": self.clauses
        }

    def save_to_file(self, path: str | Path) -> None:
        """Save lexicon to JSON or YAML file."""
        path = Path(path)
        with open(path, 'w', encoding='utf-8') as f:
            data = self.to_dict()
            if path.suffix == '.json':
                json.dump(data, f, indent=2)
            elif path.suffix in {'.yaml', '.yml'}:
                import yaml
                yaml.dump(data, f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")


class VariationEngine:
    """Reproducible text variation engine using GameRNG.

    Provides template-based text generation with seeded randomness,
    anti-repeat biasing, and tone profile support.
    """

    def __init__(
        self,
        rng: GameRNG,
        lexicon: Lexicon | None = None,
        tone: ToneProfile = ToneProfile.NEUTRAL,
        anti_repeat_size: int = 50
    ) -> None:
        """Initialize variation engine.

        Args:
            rng: GameRNG instance for deterministic randomness
            lexicon: Optional lexicon for word lists
            tone: Tone profile for text generation
            anti_repeat_size: Size of LRU buffer for anti-repeat biasing
        """
        self.rng = rng
        self.lexicon = lexicon or self._default_lexicon()
        self.tone = tone
        self.anti_repeat_size = anti_repeat_size
        self.recent_hashes: deque[str] = deque(maxlen=anti_repeat_size)

    def _default_lexicon(self) -> Lexicon:
        """Create default lexicon with basic fantasy/dungeon vocabulary."""
        return Lexicon(
            adjectives=[
                "damp", "musty", "echoing", "glittering", "shadowy",
                "ancient", "crumbling", "vast", "narrow", "twisted",
                "frozen", "scorched", "luminous", "dark", "silent"
            ],
            nouns=[
                "chamber", "corridor", "cavern", "passage", "hall",
                "vault", "alcove", "grotto", "tunnel", "crypt"
            ],
            features=[
                "a pool of ink-dark water",
                "stalagmites rising like teeth",
                "bioluminescent moss",
                "a broken altar",
                "ancient carvings",
                "scattered bones",
                "a cracked statue",
                "dripping stalactites",
                "a collapsed ceiling",
                "phosphorescent fungi"
            ],
            verbs=[
                "enter", "discover", "stumble into", "reach", "find"
            ],
            adverbs=[
                "cautiously", "quickly", "silently", "suddenly", "slowly"
            ],
            clauses=[
                "The air grows colder.",
                "You hear distant echoes.",
                "A faint breeze stirs.",
                "Water drips somewhere nearby.",
                "The walls seem to close in."
            ]
        )

    def _choose(self, options: Sequence[str], allow_repeats: bool = True) -> str:
        """Choose a random option with optional anti-repeat biasing.

        Args:
            options: Sequence of strings to choose from
            allow_repeats: If False, attempt to avoid recently used options

        Returns:
            Selected string
        """
        if not options:
            raise ValueError("options must be non-empty")

        if not allow_repeats and len(options) > 1:
            # Try up to 5 times to find a non-recent option
            for _ in range(5):
                idx = self.rng.get_int(0, len(options) - 1)
                candidate = options[idx]
                candidate_hash = hashlib.sha1(candidate.encode()).hexdigest()
                if candidate_hash not in self.recent_hashes:
                    self.recent_hashes.append(candidate_hash)
                    return candidate

        # Fallback: just pick randomly
        idx = self.rng.get_int(0, len(options) - 1)
        result = options[idx]
        result_hash = hashlib.sha1(result.encode()).hexdigest()
        self.recent_hashes.append(result_hash)
        return result

    def adjective(self) -> str:
        """Get a random adjective from lexicon."""
        return self._choose(self.lexicon.adjectives, allow_repeats=False)

    def noun(self) -> str:
        """Get a random noun from lexicon."""
        return self._choose(self.lexicon.nouns, allow_repeats=False)

    def feature(self) -> str:
        """Get a random feature description from lexicon."""
        return self._choose(self.lexicon.features, allow_repeats=False)

    def verb(self) -> str:
        """Get a random verb from lexicon."""
        return self._choose(self.lexicon.verbs, allow_repeats=True)

    def adverb(self) -> str:
        """Get a random adverb from lexicon."""
        return self._choose(self.lexicon.adverbs, allow_repeats=True)

    def optional_clause(self, probability: float = 0.3) -> str:
        """Get an optional clause with given probability.

        Args:
            probability: Chance (0.0-1.0) of including a clause

        Returns:
            A clause string or empty string
        """
        if self.rng.chance(probability) and self.lexicon.clauses:
            return " " + self._choose(self.lexicon.clauses)
        return ""

    def room_description(
        self,
        nouns: Sequence[str] | None = None,
        include_clause: bool = True
    ) -> str:
        """Generate a varied room description.

        Args:
            nouns: Optional sequence of nouns to choose from
            include_clause: Whether to potentially include an optional clause

        Returns:
            Generated description string
        """
        if nouns is None:
            nouns = self.lexicon.nouns

        templates = self._get_templates_for_tone()
        template = self._choose(templates, allow_repeats=False)

        # Build context dict with safe fallbacks for empty lists
        context = {
            "adj": self.adjective() if self.lexicon.adjectives else "empty",
            "noun": self._choose(nouns, allow_repeats=True) if nouns else "void",
            "feature": self.feature() if self.lexicon.features else "nothing",
            "verb": self.verb() if self.lexicon.verbs else "enter",
            "adverb": self.adverb() if self.lexicon.adverbs else "slowly"
        }

        result = template.format(**context)

        if include_clause:
            result += self.optional_clause()

        return result

    def _get_templates_for_tone(self) -> list[str]:
        """Get template list based on current tone profile."""
        base_templates = [
            "A {adj} {noun} dominated by {feature}.",
            "You {verb} a {adj} {noun}; {feature} catches your eye.",
            "A {adj}, low-ceilinged {noun} with {feature} scattered about.",
            "{adverb}, you enter a {adj} {noun}. {feature} here.",
            "This {adj} {noun} contains {feature}."
        ]

        if self.tone == ToneProfile.TERSE:
            return [
                "{adj} {noun}. {feature}.",
                "{adj} {noun}.",
                f"{noun}. {feature}."
            ]
        elif self.tone == ToneProfile.ORNATE:
            return [
                "You {verb} {adverb} into a {adj} {noun}, its vastness marked by {feature} that speak of ages past.",
                "A {adj} {noun} unfolds before you, dominated by {feature} of haunting beauty.",
                "The {adj} expanse of this {noun} is punctuated by {feature}, silent witnesses to forgotten times."
            ]
        elif self.tone == ToneProfile.WRY:
            return [
                "Yet another {adj} {noun}. At least this one has {feature}.",
                "A {adj} {noun}. {feature} here. How original.",
                "You {verb} a {adj} {noun}. {feature} greets you, as expected."
            ]
        else:  # NEUTRAL
            return base_templates

    def substitute_synonyms(
        self,
        text: str,
        synonym_map: dict[str, Sequence[str]]
    ) -> str:
        """Replace words in text with synonyms from a mapping.

        Args:
            text: Input text
            synonym_map: Dict mapping words to lists of synonyms

        Returns:
            Text with substitutions applied
        """
        tokens = text.split()
        result = []

        for token in tokens:
            # Strip punctuation for lookup
            clean_token = token.strip('.,;:!?').lower()

            if clean_token in synonym_map:
                options = synonym_map[clean_token]
                replacement = self._choose(options, allow_repeats=True)

                # Preserve capitalization
                if token[0].isupper():
                    replacement = replacement.capitalize()

                # Preserve punctuation
                if token[-1] in '.,;:!?':
                    replacement = replacement + token[-1]

                result.append(replacement)
            else:
                result.append(token)

        return " ".join(result)


# ---------------------------------------------------------------------------
# Structured Logging with RNG State
# ---------------------------------------------------------------------------


@dataclass
class OutputRecord:
    """Structured output record with RNG state for reproducibility."""
    tag: str
    text: str
    seed: int
    rng_state: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tag": self.tag,
            "text": self.text,
            "seed": self.seed,
            "rng_state": self.rng_state,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputRecord:
        """Create from dictionary."""
        return cls(
            tag=data["tag"],
            text=data["text"],
            seed=data["seed"],
            rng_state=data["rng_state"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )


def record_output(
    rng: GameRNG,
    tag: str,
    text: str,
    metadata: dict[str, Any] | None = None
) -> OutputRecord:
    """Create a structured output record with RNG state.

    Args:
        rng: GameRNG instance
        tag: Category/type tag for this output
        text: The generated text
        metadata: Optional additional metadata

    Returns:
        OutputRecord with full state for reproducibility
    """
    return OutputRecord(
        tag=tag,
        text=text,
        seed=rng.initial_seed,
        rng_state=rng.get_state(),
        metadata=metadata or {}
    )


def write_ndjson(records: Sequence[OutputRecord], path: str | Path) -> None:
    """Write records as newline-delimited JSON.

    Args:
        records: Sequence of OutputRecord instances
        path: Output file path
    """
    path = Path(path)
    with open(path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(record.to_json() + '\n')


def read_ndjson(path: str | Path) -> list[OutputRecord]:
    """Read records from newline-delimited JSON.

    Args:
        path: Input file path

    Returns:
        List of OutputRecord instances
    """
    path = Path(path)
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                records.append(OutputRecord.from_dict(data))
    return records


# ---------------------------------------------------------------------------
# Variety Metrics and Analysis
# ---------------------------------------------------------------------------


@dataclass
class VarietyMetrics:
    """Metrics for analyzing output variety."""
    total: int
    unique: int
    unique_fraction: float
    duplicate_count: int
    most_common: list[tuple[str, int]] = field(default_factory=list)
    entropy: float = 0.0

    def __str__(self) -> str:
        """Human-readable string representation."""
        lines = [
            f"Total outputs: {self.total}",
            f"Unique outputs: {self.unique}",
            f"Unique fraction: {self.unique_fraction:.3f}",
            f"Duplicates: {self.duplicate_count}",
            f"Entropy: {self.entropy:.3f}"
        ]
        if self.most_common:
            lines.append("\nMost common outputs:")
            for text, count in self.most_common[:5]:
                preview = text[:60] + "..." if len(text) > 60 else text
                lines.append(f"  {count}x: {preview}")
        return "\n".join(lines)


def compute_variety_metrics(
    variants: Sequence[str],
    include_entropy: bool = True
) -> VarietyMetrics:
    """Compute variety metrics for a list of text variants.

    Args:
        variants: Sequence of text strings to analyze
        include_entropy: Whether to compute Shannon entropy

    Returns:
        VarietyMetrics with analysis results
    """
    if not variants:
        return VarietyMetrics(0, 0, 0.0, 0)

    total = len(variants)

    # Use Polars if available for better performance
    if POLARS_AVAILABLE:
        df = pl.DataFrame({"text": variants})
        unique_count = df["text"].n_unique()
        value_counts = df["text"].value_counts()
        most_common = [
            (row["text"], row["count"])
            for row in value_counts.sort("count", descending=True).head(10).to_dicts()
        ]
    else:
        # Fallback to standard library
        from collections import Counter
        unique_count = len(set(variants))
        counter = Counter(variants)
        most_common = counter.most_common(10)

    unique_frac = unique_count / total
    duplicate_count = total - unique_count

    # Compute Shannon entropy if requested
    entropy = 0.0
    if include_entropy:
        if POLARS_AVAILABLE:
            counts = [row["count"] for row in value_counts.to_dicts()]
        else:
            counts = list(Counter(variants).values())

        for count in counts:
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

    return VarietyMetrics(
        total=total,
        unique=unique_count,
        unique_fraction=unique_frac,
        duplicate_count=duplicate_count,
        most_common=most_common,
        entropy=entropy
    )


def jaccard_similarity(set1: set, set2: set) -> float:
    """Compute Jaccard similarity between two sets.

    Args:
        set1: First set
        set2: Second set

    Returns:
        Jaccard similarity coefficient (0.0 to 1.0)
    """
    if not set1 and not set2:
        return 1.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Name Generator (Markov Chain)
# ---------------------------------------------------------------------------


class NameGenerator:
    """Markov chain-based name generator for fantasy names.

    Uses character-level Markov chains to generate pronounceable names
    that match the statistical patterns of a training corpus.
    """

    def __init__(self, rng: GameRNG, order: int = 2) -> None:
        """Initialize name generator.

        Args:
            rng: GameRNG instance for deterministic generation
            order: Markov chain order (number of previous characters to consider)
        """
        self.rng = rng
        self.order = order
        self.chain: dict[str, list[str]] = defaultdict(list)
        self.start_tokens: list[str] = []

    def train(self, names: Sequence[str]) -> None:
        """Train the Markov chain on a corpus of names.

        Args:
            names: Sequence of example names
        """
        self.chain.clear()
        self.start_tokens.clear()

        for name in names:
            name = name.lower().strip()
            if len(name) < self.order:
                continue

            # Add start token
            start = name[:self.order]
            self.start_tokens.append(start)

            # Build chain
            for i in range(len(name) - self.order):
                context = name[i:i + self.order]
                next_char = name[i + self.order]
                self.chain[context].append(next_char)

            # Add end marker
            if len(name) >= self.order:
                final_context = name[-self.order:]
                self.chain[final_context].append('\0')  # End marker

    def generate(
        self,
        min_length: int = 4,
        max_length: int = 12,
        capitalize: bool = True
    ) -> str:
        """Generate a new name.

        Args:
            min_length: Minimum name length
            max_length: Maximum name length
            capitalize: Whether to capitalize the first letter

        Returns:
            Generated name string
        """
        if not self.start_tokens:
            raise ValueError("Must train generator before generating names")

        # Try up to 10 times to generate a valid name
        for attempt in range(10):
            # Pick a random start
            name = self.rng.choice(self.start_tokens)

            # Generate characters
            for _ in range(max_length - self.order):
                context = name[-self.order:]

                if context not in self.chain:
                    break

                next_options = self.chain[context]
                next_char = self.rng.choice(next_options)

                if next_char == '\0':  # End marker
                    if len(name) >= min_length:
                        break
                    else:
                        # Too short but hit end marker, restart with new seed
                        break

                name += next_char

            # If name meets minimum length, return it
            if len(name) >= min_length:
                if capitalize:
                    name = name.capitalize()
                return name

        # Fallback: if all attempts failed, return padded start token
        name = self.rng.choice(self.start_tokens)
        if capitalize:
            name = name.capitalize()
        return name

    @classmethod
    def default_fantasy_generator(cls, rng: GameRNG) -> NameGenerator:
        """Create a generator pre-trained on fantasy name corpus.

        Args:
            rng: GameRNG instance

        Returns:
            Trained NameGenerator
        """
        generator = cls(rng, order=2)

        # Small corpus of fantasy names
        corpus = [
            "aelric", "baldur", "cassia", "dorian", "elara", "fenris",
            "gwendolyn", "hadrian", "isolde", "jaren", "kael", "lyra",
            "magnus", "nyx", "orion", "petra", "quinn", "raven",
            "soren", "thalia", "ulric", "vex", "wren", "xander",
            "yara", "zephyr", "aldric", "brynn", "cedric", "daria",
            "elden", "fiona", "gareth", "helena", "isen", "jorah",
            "kira", "leander", "mira", "nolan", "ophelia", "piers",
            "quintus", "rowan", "selene", "tristan", "ursula", "valen",
            "willow", "xenia", "yorick", "zara"
        ]

        generator.train(corpus)
        return generator


# ---------------------------------------------------------------------------
# Jinja2 Integration (optional, if jinja2 available)
# ---------------------------------------------------------------------------


def make_jinja_env(rng: GameRNG) -> "Environment":
    """Create a Jinja2 environment with RNG-based filters.

    Requires jinja2 to be installed.

    Args:
        rng: GameRNG instance

    Returns:
        Jinja2 Environment with custom filters
    """
    try:
        from jinja2 import Environment
    except ImportError:
        raise ImportError("jinja2 is required for template support")

    env = Environment(autoescape=False)

    # Add RNG-based choice filter
    def choice_filter(seq: Sequence[Any]) -> Any:
        if not seq:
            return ""
        idx = rng.get_int(0, len(seq) - 1)
        return seq[idx]

    env.filters['choice'] = choice_filter
    env.filters['rng_choice'] = choice_filter

    return env


# ---------------------------------------------------------------------------
# Pretty Output (optional rich integration)
# ---------------------------------------------------------------------------


def type_out(
    text: str,
    rng: GameRNG,
    stream_write: Callable[[str], None],
    base_delay: float = 0.002,
    jitter: float = 0.01
) -> None:
    """Type out text character by character with deterministic jitter.

    Args:
        text: Text to type out
        rng: GameRNG for jitter
        stream_write: Function to write each character
        base_delay: Base delay between characters (seconds)
        jitter: Maximum random jitter to add (seconds)
    """
    import sys
    for ch in text:
        stream_write(ch)
        sys.stdout.flush()
        time.sleep(base_delay + rng.get_float(0, jitter))


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


__all__ = [
    "ToneProfile",
    "OutputMode",
    "Lexicon",
    "VariationEngine",
    "OutputRecord",
    "VarietyMetrics",
    "NameGenerator",
    "record_output",
    "write_ndjson",
    "read_ndjson",
    "compute_variety_metrics",
    "jaccard_similarity",
    "make_jinja_env",
    "type_out",
]
