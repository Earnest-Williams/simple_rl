# `utils/core.py` - Enhanced Output Generation

This module provides reproducible, varied text generation using the project's deterministic `GameRNG` system. All variation is testable, replayable, and integrates cleanly with the logging and testing infrastructure.

## Features

### 🎲 VariationEngine - Template-driven Text Generation

Generate varied, interesting text using templates and lexica with full determinism:

```python
from utils.game_rng import GameRNG
from utils.core import VariationEngine, ToneProfile

rng = GameRNG(seed=12345)
engine = VariationEngine(rng, tone=ToneProfile.ORNATE)

description = engine.room_description()
# => "You venture cautiously into a shadowy cavern, its vastness
#     marked by bioluminescent moss that speak of ages past."
```

**Key features:**
- **Deterministic**: Same seed produces identical output
- **Anti-repeat biasing**: LRU buffer prevents immediate repetitions
- **Tone profiles**: TERSE, NEUTRAL, ORNATE, WRY
- **Data-driven**: Load lexica from JSON/YAML files

### 📝 Structured Logging with RNG State

Record outputs with full RNG state for reproducibility:

```python
from utils.core import record_output, write_ndjson

rng = GameRNG(seed=42)
engine = VariationEngine(rng)

# Generate and record
text = engine.room_description()
record = record_output(rng, "room_desc", text, metadata={"level": 1})

# Save to file
write_ndjson([record], "outputs.ndjson")

# Later: replay from saved state
loaded = read_ndjson("outputs.ndjson")
rng.set_state(loaded[0].rng_state)  # Restore exact RNG state
```

### 📊 Variety Metrics and Analysis

Measure output diversity with comprehensive metrics:

```python
from utils.core import compute_variety_metrics

variants = [engine.room_description() for _ in range(1000)]
metrics = compute_variety_metrics(variants, include_entropy=True)

print(metrics)
# => Total outputs: 1000
#    Unique outputs: 687
#    Unique fraction: 0.687
#    Entropy: 9.243
```

**Metrics tracked:**
- Unique count and fraction
- Duplicate count
- Most common outputs
- Shannon entropy
- Supports Polars for performance (optional)

### 🏷️ Name Generator - Markov Chain Based

Generate pronounceable fantasy names using character-level Markov chains:

```python
from utils.core import NameGenerator

rng = GameRNG(seed=123)
gen = NameGenerator.default_fantasy_generator(rng)

names = [gen.generate() for _ in range(10)]
# => ['Aldric', 'Selene', 'Gareth', 'Isolde', ...]
```

**Train on custom corpus:**
```python
gen = NameGenerator(rng, order=2)
gen.train(["thor", "loki", "freya", "odin", "baldur"])
name = gen.generate(min_length=4, max_length=8)
```

### 📚 Lexicon System

Data-driven word lists for template generation:

```python
from utils.core import Lexicon

# Load from file
lexicon = Lexicon.load_from_file("data/lexica/dungeon_default.json")

# Or create programmatically
custom = Lexicon(
    adjectives=["dark", "bright", "shadowy"],
    nouns=["chamber", "corridor", "hall"],
    features=["a torch", "ancient carvings", "moss"]
)

# Use with engine
engine = VariationEngine(rng, lexicon=custom)
```

**Example lexicon structure** (`data/lexica/dungeon_default.json`):
```json
{
  "adjectives": ["damp", "musty", "echoing", "glittering"],
  "nouns": ["chamber", "corridor", "cavern", "passage"],
  "features": [
    "a pool of ink-dark water",
    "stalagmites rising like teeth",
    "bioluminescent moss"
  ],
  "verbs": ["enter", "discover", "stumble into"],
  "adverbs": ["cautiously", "quickly", "silently"],
  "clauses": [
    "The air grows colder.",
    "You hear distant echoes."
  ]
}
```

### 🎨 Jinja2 Integration (Optional)

Use Jinja2 templates with RNG-based filters:

```python
from utils.core import make_jinja_env

env = make_jinja_env(rng)
template = env.from_string(
    "You see {{ ['a torch', 'a statue', 'a pool'] | choice }}."
)
result = template.render()
# => "You see a statue."  (deterministic with seed)
```

## CLI Tool

The `tools/sample_variants.py` script provides command-line access to generation and analysis:

### Generate Variants

```bash
# Generate 100 room descriptions with metrics
python tools/sample_variants.py generate -n 100 --print --metrics

# Use custom lexicon and save to file
python tools/sample_variants.py generate \
  -n 500 \
  --lexicon data/lexica/combat.json \
  --tone ornate \
  -o output.ndjson

# Generate with variety threshold check (for CI)
python tools/sample_variants.py generate \
  -n 1000 \
  --metrics \
  --threshold 0.6
```

### Generate Names

```bash
# Generate 50 fantasy names
python tools/sample_variants.py generate \
  -n 50 \
  --mode name \
  --print
```

### Analyze Existing Files

```bash
# Analyze variety from saved file
python tools/sample_variants.py analyze output.ndjson

# Check against threshold (fails if below)
python tools/sample_variants.py analyze output.ndjson --threshold 0.6
```

### Replay from Saved State

```bash
# List all records in file
python tools/sample_variants.py replay output.ndjson

# Inspect specific record
python tools/sample_variants.py replay output.ndjson --index 42
```

## Testing

### Unit Tests

```bash
# Run all core output tests
pytest tests/test_core_output.py -v

# Run variety coverage tests (CI thresholds)
pytest tests/test_variety_coverage.py -v
```

### Variety Coverage CI

The `tests/test_variety_coverage.py` file contains regression tests that ensure output variety stays above minimum thresholds:

```python
def test_room_description_variety_threshold(self):
    """Ensure room descriptions meet minimum variety threshold."""
    rng = GameRNG(seed=42)
    engine = VariationEngine(rng)
    variants = [engine.room_description() for _ in range(1000)]
    metrics = compute_variety_metrics(variants)

    # Must maintain at least 60% unique outputs
    assert metrics.unique_fraction >= 0.6
```

**Current thresholds:**
- Room descriptions (neutral): ≥60% unique (n=1000)
- Room descriptions (terse): ≥40% unique (n=500)
- Room descriptions (ornate): ≥50% unique (n=500)
- Name generation: ≥70% unique (n=200)

## Integration with Project Workflow

### 1. Generation → Logging → Replay

```python
# Generate with logging
rng = GameRNG(seed=args.seed)
engine = VariationEngine(rng)

records = []
for i in range(100):
    text = engine.room_description()
    record = record_output(rng, "room", text, {"index": i})
    records.append(record)

# Save for analysis/replay
write_ndjson(records, "session.ndjson")
```

### 2. Bug Reproduction

When a bug is reported with specific output:

```python
# Load the problematic record
records = read_ndjson("bug_report.ndjson")
problem_record = records[42]

# Restore exact RNG state
rng = GameRNG(seed=problem_record.seed)
rng.set_state(problem_record.rng_state)

# Reproduce the exact sequence leading to the bug
engine = VariationEngine(rng)
reproduced = engine.room_description()

assert reproduced == problem_record.text  # Should match exactly
```

### 3. CI/CD Integration

```bash
# Add to CI pipeline
pytest tests/test_variety_coverage.py --tb=short

# Or use CLI tool with threshold
python tools/sample_variants.py generate \
  -n 1000 \
  --metrics \
  --threshold 0.6 \
  || exit 1
```

## Example Lexica

The project includes several pre-built lexica in `data/lexica/`:

- `dungeon_default.json` - Dungeon/cave exploration vocabulary
- `combat.json` - Combat action descriptions
- `treasure.json` - Treasure and loot discoveries
- `nature.yaml` - Natural environment descriptions

Load and use them:

```python
lex = Lexicon.load_from_file("data/lexica/combat.json")
engine = VariationEngine(rng, lexicon=lex, tone=ToneProfile.WRY)
action = engine.room_description()
# => "Yet another brutal strike. At least this one has blood spattering the ground."
```

## Advanced: Synonym Substitution

Replace words with synonyms for additional variety:

```python
synonym_map = {
    "dark": ["shadowy", "gloomy", "murky"],
    "room": ["chamber", "hall", "space"]
}

text = "A dark room."
varied = engine.substitute_synonyms(text, synonym_map)
# => "A shadowy chamber."
```

## Performance Notes

- **Polars integration**: If Polars is available, variety metrics use DataFrame operations for 10-100x speedup on large datasets
- **Anti-repeat LRU**: Buffer size of 50 by default; tune with `anti_repeat_size` parameter
- **Lexicon loading**: Cache loaded lexica in production; file I/O only needed once

## Design Philosophy

This module follows the project's core principles:

1. **Determinism**: All randomness uses `GameRNG` for reproducibility
2. **Performance**: Optional Polars integration, efficient data structures
3. **Data-driven**: Lexica and templates separate from code
4. **Testability**: Full test coverage with CI regression tests
5. **Replayability**: Save/load RNG state for debugging and QA

## API Reference

See inline documentation in `utils/core.py` for full API details:

```python
help(VariationEngine)
help(compute_variety_metrics)
help(NameGenerator)
```
