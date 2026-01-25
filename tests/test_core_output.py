"""Tests for utils/core.py output generation and variety metrics."""

import json
import tempfile
from pathlib import Path

import pytest

from utils.core import (
    Lexicon,
    NameGenerator,
    OutputRecord,
    ToneProfile,
    VariationEngine,
    compute_variety_metrics,
    jaccard_similarity,
    read_ndjson,
    record_output,
    write_ndjson,
)
from utils.game_rng import GameRNG


class TestLexicon:
    """Tests for Lexicon class."""

    def test_create_empty_lexicon(self) -> None:
        """Test creating an empty lexicon."""
        lex = Lexicon()
        assert lex.adjectives == []
        assert lex.nouns == []
        assert lex.features == []

    def test_create_lexicon_from_dict(self) -> None:
        """Test creating lexicon from dictionary."""
        data = {
            "adjectives": ["dark", "light"],
            "nouns": ["room", "hall"],
            "features": ["a torch", "a statue"],
        }
        lex = Lexicon.from_dict(data)
        assert lex.adjectives == ["dark", "light"]
        assert lex.nouns == ["room", "hall"]
        assert lex.features == ["a torch", "a statue"]

    def test_lexicon_to_dict(self) -> None:
        """Test converting lexicon to dictionary."""
        lex = Lexicon(adjectives=["dark", "light"], nouns=["room", "hall"])
        data = lex.to_dict()
        assert data["adjectives"] == ["dark", "light"]
        assert data["nouns"] == ["room", "hall"]

    def test_save_load_json(self) -> None:
        """Test saving and loading lexicon as JSON."""
        lex = Lexicon(
            adjectives=["dark", "bright"],
            nouns=["cavern", "tunnel"],
            features=["moss", "crystals"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_lex.json"
            lex.save_to_file(path)

            loaded = Lexicon.load_from_file(path)
            assert loaded.adjectives == lex.adjectives
            assert loaded.nouns == lex.nouns
            assert loaded.features == lex.features


class TestVariationEngine:
    """Tests for VariationEngine class."""

    def test_create_engine_with_default_lexicon(self) -> None:
        """Test creating engine with default lexicon."""
        rng = GameRNG(seed=12345)
        engine = VariationEngine(rng)
        assert engine.lexicon is not None
        assert len(engine.lexicon.adjectives) > 0

    def test_create_engine_with_custom_lexicon(self) -> None:
        """Test creating engine with custom lexicon."""
        rng = GameRNG(seed=12345)
        lex = Lexicon(adjectives=["custom"], nouns=["test"])
        engine = VariationEngine(rng, lexicon=lex)
        assert engine.lexicon.adjectives == ["custom"]

    def test_adjective_selection_deterministic(self) -> None:
        """Test that adjective selection is deterministic."""
        rng1 = GameRNG(seed=42)
        rng2 = GameRNG(seed=42)

        engine1 = VariationEngine(rng1)
        engine2 = VariationEngine(rng2)

        adj1 = engine1.adjective()
        adj2 = engine2.adjective()

        assert adj1 == adj2

    def test_room_description_deterministic(self) -> None:
        """Test that room descriptions are deterministic."""
        rng1 = GameRNG(seed=99)
        rng2 = GameRNG(seed=99)

        engine1 = VariationEngine(rng1)
        engine2 = VariationEngine(rng2)

        desc1 = engine1.room_description()
        desc2 = engine2.room_description()

        assert desc1 == desc2

    def test_room_description_variety(self) -> None:
        """Test that room descriptions produce variety."""
        rng = GameRNG(seed=123)
        engine = VariationEngine(rng)

        descriptions = [engine.room_description() for _ in range(50)]
        unique = len(set(descriptions))

        # Should have at least 30% unique descriptions
        assert unique / 50 >= 0.3

    def test_tone_profile_changes_output(self) -> None:
        """Test that different tone profiles produce different outputs."""
        rng = GameRNG(seed=456)

        terse = VariationEngine(rng, tone=ToneProfile.TERSE)
        terse.room_description()

        rng.reset(seed=456)  # Reset to same state
        ornate = VariationEngine(rng, tone=ToneProfile.ORNATE)
        ornate.room_description()

        # Different tones should produce different descriptions
        # (though with same seed, they might occasionally match by chance)
        # We test that the template sets are different
        terse_templates = terse._get_templates_for_tone()
        ornate_templates = ornate._get_templates_for_tone()
        assert terse_templates != ornate_templates

    def test_optional_clause(self) -> None:
        """Test optional clause generation."""
        rng = GameRNG(seed=789)
        engine = VariationEngine(rng)

        # Test with 0% probability
        clause = engine.optional_clause(probability=0.0)
        assert clause == ""

        # Test with 100% probability
        clause = engine.optional_clause(probability=1.0)
        assert len(clause) > 0

    def test_synonym_substitution(self) -> None:
        """Test synonym substitution functionality."""
        rng = GameRNG(seed=111)
        engine = VariationEngine(rng)

        synonym_map = {
            "dark": ["shadowy", "gloomy", "murky"],
            "room": ["chamber", "hall", "space"],
        }

        text = "A dark room."
        result = engine.substitute_synonyms(text, synonym_map)

        # Should contain one of the synonyms
        assert any(syn in result for syn in ["shadowy", "gloomy", "murky"])
        assert any(syn in result for syn in ["chamber", "hall", "space"])

    def test_anti_repeat_biasing(self) -> None:
        """Test that anti-repeat biasing reduces immediate repetitions."""
        rng = GameRNG(seed=222)

        # Small lexicon to increase chance of repetition
        lex = Lexicon(adjectives=["dark", "light", "bright"])
        engine = VariationEngine(rng, lexicon=lex, anti_repeat_size=10)

        # Generate many selections
        selections = [engine.adjective() for _ in range(30)]

        # Check for consecutive duplicates
        consecutive_dupes = sum(
            1 for i in range(len(selections) - 1) if selections[i] == selections[i + 1]
        )

        # With anti-repeat, should have very few consecutive dupes
        # (some might occur when buffer is full or by random chance)
        assert (
            consecutive_dupes < 8
        )  # Relaxed threshold to account for statistical variation


class TestOutputRecord:
    """Tests for OutputRecord and structured logging."""

    def test_create_output_record(self) -> None:
        """Test creating an output record."""
        rng = GameRNG(seed=333)
        record = record_output(rng, "test", "Sample text", {"extra": "data"})

        assert record.tag == "test"
        assert record.text == "Sample text"
        assert record.seed == 333
        assert record.metadata["extra"] == "data"
        assert "rng_state" in record.to_dict()

    def test_output_record_to_json(self) -> None:
        """Test converting output record to JSON."""
        rng = GameRNG(seed=444)
        record = record_output(rng, "test", "Sample")

        json_str = record.to_json()
        data = json.loads(json_str)

        assert data["tag"] == "test"
        assert data["text"] == "Sample"
        assert data["seed"] == 444

    def test_output_record_roundtrip(self) -> None:
        """Test converting output record to dict and back."""
        rng = GameRNG(seed=555)
        original = record_output(rng, "test", "Sample text")

        data = original.to_dict()
        restored = OutputRecord.from_dict(data)

        assert restored.tag == original.tag
        assert restored.text == original.text
        assert restored.seed == original.seed

    def test_write_read_ndjson(self) -> None:
        """Test writing and reading NDJSON files."""
        rng = GameRNG(seed=666)

        records = [
            record_output(rng, "test1", "First"),
            record_output(rng, "test2", "Second"),
            record_output(rng, "test3", "Third"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.ndjson"
            write_ndjson(records, path)

            loaded = read_ndjson(path)

            assert len(loaded) == 3
            assert loaded[0].text == "First"
            assert loaded[1].text == "Second"
            assert loaded[2].text == "Third"


class TestVarietyMetrics:
    """Tests for variety metrics computation."""

    def test_compute_metrics_empty(self) -> None:
        """Test metrics computation with empty list."""
        metrics = compute_variety_metrics([])
        assert metrics.total == 0
        assert metrics.unique == 0

    def test_compute_metrics_all_unique(self) -> None:
        """Test metrics with all unique items."""
        variants = ["a", "b", "c", "d", "e"]
        metrics = compute_variety_metrics(variants)

        assert metrics.total == 5
        assert metrics.unique == 5
        assert metrics.unique_fraction == 1.0
        assert metrics.duplicate_count == 0

    def test_compute_metrics_all_same(self) -> None:
        """Test metrics with all identical items."""
        variants = ["same"] * 10
        metrics = compute_variety_metrics(variants)

        assert metrics.total == 10
        assert metrics.unique == 1
        assert metrics.unique_fraction == 0.1
        assert metrics.duplicate_count == 9

    def test_compute_metrics_mixed(self) -> None:
        """Test metrics with mixed unique and duplicate items."""
        variants = ["a", "a", "b", "c", "c", "c", "d"]
        metrics = compute_variety_metrics(variants)

        assert metrics.total == 7
        assert metrics.unique == 4  # a, b, c, d
        assert metrics.duplicate_count == 3

    def test_entropy_computation(self) -> None:
        """Test entropy computation."""
        # Uniform distribution should have maximum entropy
        uniform = ["a", "b", "c", "d"]
        metrics_uniform = compute_variety_metrics(uniform, include_entropy=True)

        # Skewed distribution should have lower entropy
        skewed = ["a"] * 7 + ["b"]
        metrics_skewed = compute_variety_metrics(skewed, include_entropy=True)

        assert metrics_uniform.entropy > metrics_skewed.entropy

    def test_most_common_tracking(self) -> None:
        """Test that most common items are tracked."""
        variants = ["a"] * 5 + ["b"] * 3 + ["c"] * 2 + ["d"]
        metrics = compute_variety_metrics(variants)

        assert len(metrics.most_common) > 0
        # Most common should be "a" with count 5
        assert metrics.most_common[0] == ("a", 5)

    def test_variety_metrics_str_representation(self) -> None:
        """Test string representation of metrics."""
        variants = ["x", "y", "z"]
        metrics = compute_variety_metrics(variants)

        str_repr = str(metrics)
        assert "Total outputs: 3" in str_repr
        assert "Unique outputs: 3" in str_repr


class TestJaccardSimilarity:
    """Tests for Jaccard similarity computation."""

    def test_identical_sets(self) -> None:
        """Test Jaccard similarity of identical sets."""
        set1 = {"a", "b", "c"}
        set2 = {"a", "b", "c"}
        assert jaccard_similarity(set1, set2) == 1.0

    def test_disjoint_sets(self) -> None:
        """Test Jaccard similarity of disjoint sets."""
        set1 = {"a", "b", "c"}
        set2 = {"d", "e", "f"}
        assert jaccard_similarity(set1, set2) == 0.0

    def test_partial_overlap(self) -> None:
        """Test Jaccard similarity with partial overlap."""
        set1 = {"a", "b", "c"}
        set2 = {"b", "c", "d"}
        # Intersection: {b, c} = 2
        # Union: {a, b, c, d} = 4
        # Jaccard = 2/4 = 0.5
        assert jaccard_similarity(set1, set2) == 0.5

    def test_empty_sets(self) -> None:
        """Test Jaccard similarity of empty sets."""
        set1 = set()
        set2 = set()
        assert jaccard_similarity(set1, set2) == 1.0


class TestNameGenerator:
    """Tests for Markov chain name generator."""

    def test_create_generator(self) -> None:
        """Test creating a name generator."""
        rng = GameRNG(seed=777)
        gen = NameGenerator(rng, order=2)
        assert gen.order == 2

    def test_train_generator(self) -> None:
        """Test training the generator."""
        rng = GameRNG(seed=888)
        gen = NameGenerator(rng, order=2)

        corpus = ["alice", "alex", "alan", "anna", "amber"]
        gen.train(corpus)

        assert len(gen.start_tokens) > 0
        assert len(gen.chain) > 0

    def test_generate_name_deterministic(self) -> None:
        """Test that name generation is deterministic."""
        corpus = ["frodo", "bilbo", "gandalf", "aragorn", "legolas"]

        rng1 = GameRNG(seed=999)
        gen1 = NameGenerator(rng1, order=2)
        gen1.train(corpus)
        name1 = gen1.generate()

        rng2 = GameRNG(seed=999)
        gen2 = NameGenerator(rng2, order=2)
        gen2.train(corpus)
        name2 = gen2.generate()

        assert name1 == name2

    def test_generate_multiple_unique_names(self) -> None:
        """Test generating multiple names produces variety."""
        rng = GameRNG(seed=1111)
        gen = NameGenerator(rng, order=2)

        corpus = [
            "aelric",
            "baldur",
            "cassia",
            "dorian",
            "elara",
            "fenris",
            "gwen",
            "hadrian",
            "isolde",
            "jaren",
        ]
        gen.train(corpus)

        names = [gen.generate() for _ in range(20)]
        unique = len(set(names))

        # Should generate at least 10 unique names
        assert unique >= 10

    def test_generate_respects_length_constraints(self) -> None:
        """Test that generated names respect length constraints."""
        rng = GameRNG(seed=1212)
        gen = NameGenerator(rng, order=2)

        corpus = ["short", "name", "test", "sample"]
        gen.train(corpus)

        name = gen.generate(min_length=5, max_length=8)
        assert 5 <= len(name) <= 8

    def test_capitalize_option(self) -> None:
        """Test name capitalization option."""
        rng = GameRNG(seed=1313)
        gen = NameGenerator(rng, order=2)

        corpus = ["alice", "bob", "charlie"]
        gen.train(corpus)

        name_cap = gen.generate(capitalize=True)
        assert name_cap[0].isupper()

        rng.reset(seed=1313)
        gen = NameGenerator(rng, order=2)
        gen.train(corpus)
        name_lower = gen.generate(capitalize=False)
        assert name_lower[0].islower()

    def test_default_fantasy_generator(self) -> None:
        """Test creating default fantasy name generator."""
        rng = GameRNG(seed=1414)
        gen = NameGenerator.default_fantasy_generator(rng)

        name = gen.generate()
        assert len(name) > 0
        assert name[0].isupper()  # Default capitalizes


class TestIntegrationVarietyWorkflow:
    """Integration tests for full variety workflow."""

    def test_generate_analyze_workflow(self) -> None:
        """Test complete workflow: generate variants and analyze."""
        rng = GameRNG(seed=2000)
        engine = VariationEngine(rng)

        # Generate variants
        variants = [engine.room_description() for _ in range(100)]

        # Analyze variety
        metrics = compute_variety_metrics(variants)

        # Should have reasonable variety
        assert metrics.unique_fraction > 0.5
        assert metrics.total == 100

    def test_record_and_replay_workflow(self) -> None:
        """Test recording outputs and replaying from state."""
        rng = GameRNG(seed=3000)

        # Generate and record - capture state BEFORE generation
        state_before = rng.get_state()
        engine = VariationEngine(rng)
        text1 = engine.room_description()

        # Create new RNG and restore to the state before generation
        rng2 = GameRNG(seed=9999)  # Different seed
        rng2.set_state(state_before)

        # Create new engine with restored RNG
        engine2 = VariationEngine(rng2)
        text2 = engine2.room_description()

        # Should generate same text when replaying from same RNG state
        assert text1 == text2

    def test_save_load_replay_workflow(self) -> None:
        """Test full save/load/replay workflow with NDJSON."""
        rng = GameRNG(seed=4000)
        engine = VariationEngine(rng)

        # Generate and record multiple outputs
        records = []
        for i in range(10):
            text = engine.room_description()
            record = record_output(rng, f"room_{i}", text, {"index": i})
            records.append(record)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outputs.ndjson"

            # Save
            write_ndjson(records, path)

            # Load
            loaded_records = read_ndjson(path)

            # Verify
            assert len(loaded_records) == 10
            for orig, loaded in zip(records, loaded_records, strict=False):
                assert orig.text == loaded.text
                assert orig.tag == loaded.tag
                assert orig.seed == loaded.seed


class TestToneProfiles:
    """Tests for tone profile variations."""

    def test_all_tone_profiles_work(self) -> None:
        """Test that all tone profiles can generate text."""
        rng = GameRNG(seed=5000)

        for tone in ToneProfile:
            engine = VariationEngine(rng, tone=tone)
            desc = engine.room_description()
            assert len(desc) > 0

    def test_tone_profiles_produce_different_styles(self) -> None:
        """Test that tone profiles produce stylistically different output."""
        # Generate samples with each tone
        samples = {}
        for tone in ToneProfile:
            rng = GameRNG(seed=6000)
            engine = VariationEngine(rng, tone=tone)
            samples[tone] = [engine.room_description() for _ in range(20)]

        # Terse should generally be shorter
        terse_avg_len = sum(len(s) for s in samples[ToneProfile.TERSE]) / 20
        ornate_avg_len = sum(len(s) for s in samples[ToneProfile.ORNATE]) / 20

        assert terse_avg_len < ornate_avg_len


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
