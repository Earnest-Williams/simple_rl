# Supplemental Style Rules

REFER TO THE AGENTS.md IN THE ROOT OF THE REPO.

In addition to the base rules, all code must adhere to these "maximalist" performance and typing standards. Violations of these rules are considered "Critical."

## 1. Type Declaration & PEP 604
* **Rule:** Use `X | None`, never `Optional[X]`.
* **Rule:** All types must be explicit. No type inference. 
* **Rule:** Function signatures must have full annotations, including `-> None`.
* **Rule:** Pass `mypy --strict` compliance at all times.

## 2. High-Performance Primitives
* **Rule:** Prefer `pathlib.Path` over strings for all filesystem interactions.
* **Rule:** Data modeling: Use `Polars` for state, `Numba` for loops, and `msgpack`/`orjson` for serialization. `Pandas` is prohibited.
* **Rule:** If it involves scale, use `mmap`, `numpy`, or `vectorized operations`. No slow for-loops.

## 3. String & Regex Constraints
* **Rule:** Regex is a last resort. Use `pyparsing` or `pydantic` for structured data.
* **Rule:** f-string expressions must be precomputed into variables if they exceed a single line's clarity.

## 4. Architectural Purity
* **Rule:** Object-Oriented "clutter" is suspect. Prefer structural clarity and throughput.
* **Rule:** Code must be `black`-formatted to an 88-character limit.
