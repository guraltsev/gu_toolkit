# Project 020: Figure Code Generation — Summary

## Rationale
Figure code generation is intended to make plot construction reproducible and portable by turning interactive figure state into explicit, inspectable Python code. This reduces manual notebook editing overhead and supports:

- reproducibility in research workflows,
- easier sharing of plots as source code,
- clearer review/diff ergonomics compared with binary notebook state.

## Architecture (current understanding)
The current toolkit architecture appears centered on:

- **Figure orchestration layer** (`Figure.py`, `figure_plot.py`, `figure_layout.py`) for managing traces, layout, and panel behavior,
- **Parameter and reference model** (`ParamRef.py`, `ParameterSnapshot.py`, `ParamEvent.py`) for state and dependency tracking,
- **Expression/numeric utilities** (`numpify.py`, `numeric_operations.py`, `numeric_callable.py`) to support symbolic/numeric transformation and callable execution,
- **Integration surface** (`__init__.py`, `prelude*.py`, `symbolic_extensions.py`) for import ergonomics and extension wiring.

In this model, figure code generation should remain a thin, deterministic serialization layer over validated figure/parameter state rather than embedding hidden execution side effects.

## Current status
- A dedicated merge source branch (`/claude/smart-figure-code-generation-0bZri`) was requested for integration into `main`.
- In this workspace snapshot, that source ref and a local `main` ref are not discoverable, so a literal in-repo merge could not be executed yet.
- Project documentation scaffolding for this merge has been created under this folder so concrete conflict details can be added immediately once refs are available.

## Recommended next TODOs
1. Restore or fetch missing refs (`main` and `/claude/smart-figure-code-generation-0bZri`).
2. Execute merge on an integration branch.
3. Record concrete conflict-by-conflict decisions in `conflicts.md`.
4. Add/adjust tests for any behavior changed during conflict resolution.
5. Finalize release notes describing figure code-generation capabilities and known limitations.
