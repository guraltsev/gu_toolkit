# Project 031: Static Analysis Tooling

**Status:** Backlog
**Priority:** High

## Goal/Scope

Add linting, type-checking, and formatting enforcement to CI so that the
existing high-quality type annotations and coding conventions are verified
automatically rather than relying on contributor discipline.

## Context

The codebase already has comprehensive modern type annotations (`from
__future__ import annotations`, `X | Y` unions, `@runtime_checkable`
Protocols, `TypeAlias`, `@dataclass(frozen=True)`, `__slots__`). However,
no static analysis tool validates these annotations in CI. Similarly,
coding style is consistent by convention but not enforced by any formatter
or linter.

Adding static analysis is low-effort and immediately valuable: it catches
type regressions at near-zero setup cost and makes subsequent refactoring
projects (022, 023) safer to execute.

## Proposed toolchain

1. **ruff** — Linting and formatting (replaces flake8, isort, black).
   Fast, Python-native, low-configuration. Configure in `pyproject.toml`
   with a rule set appropriate for a scientific library (enable `E`, `F`,
   `W`, `I` at minimum; consider `UP` for Python upgrade checks).

2. **mypy** (or pyright) — Type checking. The codebase is already
   well-annotated. Start with `--strict` on a subset of modules (e.g.,
   `core/`, `snapshot/`) and gradually expand. Allow `# type: ignore` for
   SymPy interop edge cases where stubs are incomplete.

3. **pre-commit** — Git hooks to run ruff format and ruff check before
   commits. This prevents style drift at the source.

## TODO checklist

- [ ] Add `ruff` configuration to `pyproject.toml` (rule selection,
      line length, target Python version).
- [ ] Add `mypy` configuration to `pyproject.toml` (per-module overrides,
      SymPy stub exclusions).
- [ ] Add ruff and mypy to the `[dev]` optional dependency group.
- [ ] Add a `lint` job to `.github/workflows/tests.yml` (or a separate
      workflow) that runs `ruff check`, `ruff format --check`, and `mypy`.
- [ ] Fix any existing violations surfaced by initial ruff/mypy runs.
- [ ] Add `.pre-commit-config.yaml` with ruff hooks.
- [ ] Document the lint/format workflow in `develop_guide/`.

## Exit criteria

- [ ] `ruff check` and `ruff format --check` pass in CI on every PR.
- [ ] `mypy` passes on at least the `core/` and `snapshot/` modules
      (expanding over time).
- [ ] Pre-commit hooks are configured and documented.
- [ ] New contributors can run `pre-commit run --all-files` locally.

## Challenges and mitigations

- **Challenge:** mypy may produce many errors from SymPy interop due to
  incomplete upstream stubs.
  **Mitigation:** Start with per-module opt-in (`mypy` overrides in
  `pyproject.toml`); use `# type: ignore[import-untyped]` for SymPy where
  needed.

- **Challenge:** Existing code may have minor formatting inconsistencies
  that produce a large initial diff.
  **Mitigation:** Run `ruff format` once as a dedicated formatting commit
  before enabling CI enforcement. This isolates formatting changes from
  logic changes in git blame.

- **Challenge:** Pre-commit hooks add friction for contributors unfamiliar
  with them.
  **Mitigation:** Document setup in developer guide; make hooks optional
  locally (CI is the gate of record).
