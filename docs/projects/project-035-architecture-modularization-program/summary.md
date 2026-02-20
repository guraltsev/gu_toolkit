# Project 035: Architecture Modularization Program (Backend + UI Contract)

## Status

**Discovery**

## Goal/Scope

Design and execute an ambitious, multi-phase architecture program that makes the toolkit substantially more maintainable, modular, concise, and extensible while preserving the existing notebook-facing public API.

This project intentionally spans:

1. **Core backend decomposition and package structure** (building on project-022 and project-023).
2. **Domain boundary hardening** between plotting semantics and UI widgets.
3. **Frontend/backend interaction contract** for rich UI evolution (informed by project-034 discussion) so the toolkit scales to both notebook and standalone runtime targets.

Non-goals for this project summary:
- No implementation in this project artifact.
- No blueprint/phase-by-phase implementation plan yet (that will be created later).

## Summary of design

### 1) Consolidation decision: coordinated umbrella, not scope collapse

After reviewing project-022 (Figure module decomposition), project-023 (package reorganization), and project-034 interface discussion, the preferred approach is:

- **Do not merge 022 and 023 into one undifferentiated work item**.
- **Do create a single ambitious umbrella program** that coordinates them with explicit dependency/order and adds the missing frontend/backend contract workstream.

Rationale:
- **022** is primarily about reducing monolithic coordinator complexity and extracting responsibilities.
- **023** is primarily about codifying architectural layers in package topology and migration compatibility.
- These are deeply related, but they operate at different abstraction levels and have different acceptance tests/risk profiles.
- Treating them as separate execution tracks under one umbrella maximizes focus, allows parallelism where safe, and keeps rollback/regression analysis manageable.

### 2) Why this program is needed now (codebase evidence)

The current code shape confirms the need for an ambitious architecture program:

- Large monolith remains: `Figure.py` is still ~2.1k LOC.
- Flat package surface remains: ~29 top-level modules in root package.
- Naming inconsistency remains: many `PascalCase.py` modules mixed with `snake_case.py`.
- Re-export shims and compatibility layers remain (e.g., `prelude*.py`, `numeric_callable.py`).
- DRY hotspots remain (`_resolve_symbol` duplication, Greek-letter constants, complex `_normalize_vars`).
- Frontend/backend evolution risk remains unless legend/UI behaviors are governed by an explicit state/event interface (as identified in project-034 discussion).

### 3) Proposed architecture target (north star)

Establish a layered architecture with explicit contracts:

- **Domain core (Python):** symbolic/numeric semantics, parameter lifecycle, snapshot/state model, persistence/export.
- **Application orchestration (Python):** figure/view/plot lifecycle coordination, state transitions, policy decisions.
- **UI adapters (Notebook now, applet-ready later):** widget composition, rendering adapters, event transport.
- **Frontend interaction layer:** transient interaction fidelity (hover/focus/micro-feedback), consuming typed state/events.

Key principle: **durable semantic state is backend-authoritative; transient interaction behavior is frontend-owned; both communicate via explicit typed messages/state snapshots.**

### 4) Program workstreams (high level)

- **WS-A — Figure decomposition (extends 022):** extract input normalization, view management, module-level API wrappers, and stale-state orchestration out of monolithic coordinator.
- **WS-B — Package reorganization (extends 023):** move from flat top-level modules to layered subpackages while preserving public imports via compatibility re-exports.
- **WS-C — DRY + shared primitives (aligns with 033):** centralize symbol resolution, constants, and normalization utilities with tests.
- **WS-D — Frontend/backend contract (new):** define typed legend/plot state snapshots and interaction intents; keep host-agnostic transport semantics.
- **WS-E — Governance/quality gates:** enforce import boundaries, naming policy, type/lint/test gates, and migration policy docs.

### 5) Compatibility and migration posture

- Preserve `from gu_toolkit import ...` as stable API contract during migration.
- Introduce deprecation warnings and transitional import paths for internal module moves.
- Prefer additive compatibility shims first, removals only after deprecation windows and test coverage prove safety.

## Open questions

1. **Versioning policy for architecture migration:** whether to batch into one major release boundary or a staged minor-release sequence with progressive deprecations.
2. **Contract representation:** dataclasses + Python typing only vs schema-backed protocol artifacts for cross-runtime validation.
3. **Adapter surface priority:** whether to stabilize legend contract first (high leverage, project-034 alignment) or define a broader figure-wide UI protocol first.
4. **Deprecation horizon:** explicit timeline for retiring legacy re-export shims.

## Challenges and mitigations

- **Challenge:** Refactor breadth can destabilize active feature work.
  - **Mitigation:** phased migration with strict compatibility gates and incremental PR slicing.

- **Challenge:** Large module extraction risks semantic drift in plotting behavior.
  - **Mitigation:** lock behavior with characterization tests before extractions and require parity checks during moves.

- **Challenge:** Frontend/backend split can over-engineer early if too abstract.
  - **Mitigation:** start with concrete legend contract (state + intents) and grow protocol only when new UI surfaces require it.

- **Challenge:** Packaging moves can cause noisy merge conflicts.
  - **Mitigation:** sequence path moves after decomposition, keep shims stable, and provide contributor migration notes.

## TODO

- [ ] Confirm this project as umbrella successor/coordinator for architecture modernization efforts.
- [ ] Link and map project-022, project-023, project-033, and project-034 outputs into this program charter.
- [ ] Define architecture invariants (layer boundaries, import rules, naming conventions, API stability guarantees).
- [ ] Define minimal typed frontend/backend legend protocol v1 (state snapshot + interaction intents).
- [ ] Define migration policy for compatibility shims and deprecations.
- [ ] Produce the implementation blueprint (`plan.md`) in phased, reversible milestones.

## Exit criteria

- [ ] Monolithic coordination is decomposed: `Figure.py` reduced to coordinator-focused responsibilities with extracted subsystems.
- [ ] Package topology reflects layered architecture with clear subpackages and enforced boundaries.
- [ ] Typed frontend/backend legend contract exists and is used by legend interactions.
- [ ] Public top-level API remains stable (or changes are explicitly versioned/deprecated with migration docs).
- [ ] Duplication targets (symbol resolution/constants/normalization helpers) are consolidated.
- [ ] Test/type/lint gates protect the new architecture and prevent regression to cross-layer coupling.
- [ ] Project-022 and project-023 are either completed under this umbrella or explicitly superseded with completion notes.
