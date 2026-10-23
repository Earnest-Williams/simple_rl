# ASM Development Directory

## Purpose

This directory serves as the **staging area** for Assembly (ASM) language ports and optimizations. It contains experimental implementations, prototypes, and development branches for ASM-based performance enhancements to the simple_rl project.

Code under `asm_dev/` is not imported by the package runtime and should not be treated as canonical implementation code.

The canonical production implementation for accepted ports lives outside this tree, for example under `utils/` or the relevant package module.

## Workflow

Subfolders in this directory represent active development efforts for specific ASM ports. Once a port has been:

- Thoroughly tested and validated
- Integrated into the main codebase
- Deemed production-ready and sufficiently stable

...the corresponding development subfolder will be **removed** or **archived**, with the stable implementation promoted to the appropriate location in the production code.

## Structure

Each subfolder typically contains:
- Experimental ASM implementations
- Benchmarking and testing utilities
- Documentation specific to that port
- Development notes and iterations

## Status

| Port | State |
| --- | --- |
| `los_line_of_sight/` | Promoted. The maintained kernel, wrapper, and Makefile live in `utils/los/`; build `liblos.so` there with `make -C utils/los`. Without the library, `utils.los.los_wrapper.los_many` uses a Numba implementation verified identical to the assembly kernel. This staging copy is kept for reference; without its own `liblos.so` it delegates to `utils.los`. |


⚠️ **Note**: Code in this directory should be considered **unstable** and for development purposes only. Use production releases for stable, performance-critical implementations.
