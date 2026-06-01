#!/usr/bin/env python3
"""CLI tool for sampling and analyzing text variants.

This tool allows writers and testers to:
- Generate N variants from templates/lexica
- Replay specific seeds for debugging
- Measure variety metrics
- Export results as NDJSON for regression testing
"""

import argparse
import json
import sys
from pathlib import Path

from utils.core import (
    Lexicon,
    NameGenerator,
    ToneProfile,
    VariationEngine,
    compute_variety_metrics,
    read_ndjson,
    write_ndjson,
)
from utils.game_rng import GameRNG


def load_lexicon_file(path: str) -> Lexicon:
    """Load lexicon from file path."""
    try:
        return Lexicon.load_from_file(path)
    except FileNotFoundError:
        print(f"Error: Lexicon file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading lexicon: {e}", file=sys.stderr)
        sys.exit(1)


def parse_tone(tone_str: str) -> ToneProfile:
    """Parse tone profile from string."""
    tone_map = {
        "terse": ToneProfile.TERSE,
        "neutral": ToneProfile.NEUTRAL,
        "ornate": ToneProfile.ORNATE,
        "wry": ToneProfile.WRY,
    }
    tone_lower = tone_str.lower()
    if tone_lower not in tone_map:
        print(
            f"Error: Unknown tone '{tone_str}'. Valid: {list(tone_map.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)
    return tone_map[tone_lower]


def generate_variants(args) -> None:
    """Generate text variants and optionally analyze them."""
    # Setup RNG
    rng = GameRNG(seed=args.seed)

    # Load lexicon if specified
    lexicon = None
    if args.lexicon:
        lexicon = load_lexicon_file(args.lexicon)

    # Parse tone
    tone = parse_tone(args.tone)

    # Create engine
    engine = VariationEngine(rng, lexicon=lexicon, tone=tone)

    # Generate variants
    print(f"Generating {args.count} variants with seed {args.seed}...")
    variants = []
    records = []

    for i in range(args.count):
        # Capture RNG state BEFORE generation for reproducibility
        state_before = rng.get_state() if args.output else None

        if args.mode == "room":
            text = engine.room_description()
        elif args.mode == "name":
            name_gen = NameGenerator.default_fantasy_generator(rng)
            text = name_gen.generate()
        else:
            print(f"Error: Unknown mode '{args.mode}'", file=sys.stderr)
            sys.exit(1)

        variants.append(text)

        # Create record if saving (using pre-generation state)
        if args.output and state_before is not None:
            # Create record with pre-generation state for proper replay
            from utils.core import OutputRecord

            record = OutputRecord(
                tag=args.mode,
                text=text,
                seed=rng.initial_seed,
                rng_state=state_before,
                metadata={"index": i},
            )
            records.append(record)

        # Print if requested
        if args.print:
            print(f"{i + 1:4d}. {text}")

    # Compute metrics if requested
    if args.metrics:
        print("\n" + "=" * 70)
        print("VARIETY METRICS")
        print("=" * 70)
        metrics = compute_variety_metrics(variants, include_entropy=True)
        print(metrics)
        print("=" * 70)

        # Check threshold if specified
        if args.threshold is not None:
            if metrics.unique_fraction < args.threshold:
                print(
                    f"\nWARNING: Unique fraction {metrics.unique_fraction:.3f} "
                    f"below threshold {args.threshold:.3f}"
                )
                sys.exit(1)
            else:
                print(
                    f"\nPASS: Unique fraction {metrics.unique_fraction:.3f} "
                    f"meets threshold {args.threshold:.3f}"
                )

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        if output_path.suffix == ".ndjson":
            write_ndjson(records, output_path)
            print(f"\nWrote {len(records)} records to {output_path}")
        elif output_path.suffix == ".json":
            with open(output_path, "w", encoding="utf-8") as f:
                data = [r.to_dict() for r in records]
                json.dump(data, f, indent=2)
            print(f"\nWrote {len(records)} records to {output_path}")
        else:
            # Plain text
            with open(output_path, "w", encoding="utf-8") as f:
                for variant in variants:
                    f.write(variant + "\n")
            print(f"\nWrote {len(variants)} variants to {output_path}")


def replay_from_file(args) -> None:
    """Replay generation from saved NDJSON file."""
    path = Path(args.replay_file)

    if not path.exists():
        print(f"Error: Replay file not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading records from {path}...")
    records = read_ndjson(path)
    print(f"Loaded {len(records)} records")

    if args.index is not None:
        # Replay specific index
        if args.index >= len(records):
            print(
                f"Error: Index {args.index} out of range (0-{len(records) - 1})",
                file=sys.stderr,
            )
            sys.exit(1)

        record = records[args.index]
        print(f"\nRecord {args.index}:")
        print(f"  Tag: {record.tag}")
        print(f"  Seed: {record.seed}")
        print(f"  Text: {record.text}")
        print(f"  Metadata: {record.metadata}")

        # Replay generation
        print("\nReplaying generation...")
        rng = GameRNG(seed=record.seed)
        rng.set_state(record.rng_state)

        # Note: We can't perfectly replay without knowing the exact sequence of calls,
        # but we can verify the state is correctly loaded
        print("RNG state successfully restored")

    else:
        # List all records
        print("\nRecords:")
        for i, record in enumerate(records):
            preview = record.text[:60] + "..." if len(record.text) > 60 else record.text
            print(f"{i:4d}. [{record.tag}] {preview}")


def analyze_file(args) -> None:
    """Analyze variety metrics from a file of variants."""
    path = Path(args.file)

    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    # Load variants
    variants = []
    if path.suffix == ".ndjson":
        records = read_ndjson(path)
        variants = [r.text for r in records]
    elif path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # List of records or strings
                if data and isinstance(data[0], dict):
                    variants = [d["text"] for d in data]
                else:
                    variants = data
    else:
        # Plain text, one per line
        with open(path, encoding="utf-8") as f:
            variants = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(variants)} variants from {path}")

    # Compute metrics
    metrics = compute_variety_metrics(variants, include_entropy=True)

    print("\n" + "=" * 70)
    print("VARIETY METRICS")
    print("=" * 70)
    print(metrics)
    print("=" * 70)

    # Check threshold if specified
    if args.threshold is not None:
        if metrics.unique_fraction < args.threshold:
            print(
                f"\nFAIL: Unique fraction {metrics.unique_fraction:.3f} "
                f"below threshold {args.threshold:.3f}"
            )
            sys.exit(1)
        else:
            print(
                f"\nPASS: Unique fraction {metrics.unique_fraction:.3f} "
                f"meets threshold {args.threshold:.3f}"
            )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sample and analyze text variants for variety testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 100 room descriptions with default settings
  %(prog)s generate -n 100 --print

  # Generate with custom lexicon and save to file
  %(prog)s generate -n 500 --lexicon data/lexica/dungeon_default.json -o output.ndjson

  # Generate with ornate tone and compute metrics
  %(prog)s generate -n 1000 --tone ornate --metrics

  # Generate and check against variety threshold
  %(prog)s generate -n 1000 --metrics --threshold 0.6

  # Generate names instead of room descriptions
  %(prog)s generate -n 50 --mode name --print

  # Analyze existing file
  %(prog)s analyze output.ndjson

  # Replay specific record from file
  %(prog)s replay output.ndjson --index 42
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate text variants")
    gen_parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=100,
        help="Number of variants to generate (default: 100)",
    )
    gen_parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=12345,
        help="RNG seed for reproducibility (default: 12345)",
    )
    gen_parser.add_argument(
        "--mode",
        choices=["room", "name"],
        default="room",
        help="Generation mode (default: room)",
    )
    gen_parser.add_argument(
        "--lexicon", type=str, help="Path to lexicon JSON/YAML file"
    )
    gen_parser.add_argument(
        "--tone",
        type=str,
        default="neutral",
        choices=["terse", "neutral", "ornate", "wry"],
        help="Tone profile (default: neutral)",
    )
    gen_parser.add_argument(
        "-o", "--output", type=str, help="Output file (.ndjson, .json, or .txt)"
    )
    gen_parser.add_argument(
        "-p", "--print", action="store_true", help="Print variants to stdout"
    )
    gen_parser.add_argument(
        "-m",
        "--metrics",
        action="store_true",
        help="Compute and display variety metrics",
    )
    gen_parser.add_argument(
        "--threshold",
        type=float,
        help="Minimum unique fraction threshold (fails if below)",
    )

    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay from saved file")
    replay_parser.add_argument(
        "replay_file", type=str, help="NDJSON file to replay from"
    )
    replay_parser.add_argument(
        "--index", type=int, help="Specific record index to replay"
    )

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze variety metrics")
    analyze_parser.add_argument(
        "file", type=str, help="File to analyze (.ndjson, .json, or .txt)"
    )
    analyze_parser.add_argument(
        "--threshold",
        type=float,
        help="Minimum unique fraction threshold (fails if below)",
    )

    args = parser.parse_args()

    if args.command == "generate":
        generate_variants(args)
    elif args.command == "replay":
        replay_from_file(args)
    elif args.command == "analyze":
        analyze_file(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
