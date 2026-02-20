# Project 035: Architecture Modularization Program (Backend + UI Contract)

## Status

**Discovery**

## Goal/Scope

Design and execute an ambitious, multi-phase architecture program that makes the toolkit substantially more maintainable, modular, concise, and extensible, with clear separation of concerns across backend logic and UI runtime concerns.

This project intentionally spans:

1. **Core backend decomposition and package structure** (building on project-022 and project-023).
2. **Domain boundary hardening** between plotting semantics and UI adapters.
3. **Frontend/backend interaction contract** for rich UI evolution (informed by project-034 discussion) so the toolkit scales to both notebook and standalone runtime targets.

Project stance for this effort:
- This is currently a **private project**.
- **Backward compatibility is not a requirement** for internal module paths or legacy helper surfaces during this modernization.

Non-goals for this project summary:
- No implementation in this project artifact.
- No blueprint/phase-by-phase implementation plan yet (that will be created later).

## Summary of design

### 1) Consolidation decision: coordinated umbrella, not scope collapse

After reviewing project-022 (Figure module decomposition), project-023 (package reorganization), and project-034 interface discussion, the preferred approach is:

- **Do not collapse 022 and 023 into one undifferentiated work item**.
- **Do create a single ambitious umbrella program** that coordinates them with explicit dependency/order and adds the frontend/backend contract workstream.

Rationale:
- **022** is primarily about reducing monolithic coordinator complexity and extracting responsibilities.
- **023** is primarily about codifying architectural layers in package topology.
- These are deeply related, but they operate at different abstraction levels and have different acceptance criteria/risk profiles.
- Treating them as separate execution tracks under one umbrella maximizes focus, allows parallelism where safe, and keeps regression analysis manageable.

### 2) Why this program is needed now (codebase evidence)

The current code shape confirms the need for an ambitious architecture program:

- Large monolith remains: `Figure.py` is still ~2.1k LOC.
- Flat package surface remains: ~29 top-level modules in root package.
- Naming inconsistency remains: many `PascalCase.py` modules mixed with `snake_case.py`.
- Transitional/re-export modules remain (`prelude*.py`, `numeric_callable.py`) and contribute to cognitive overhead.
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
- **WS-B — Package reorganization (extends 023):** move from flat top-level modules to layered subpackages and normalize naming conventions.
- **WS-C — DRY + shared primitives (aligns with 033):** centralize symbol resolution, constants, and normalization utilities with tests.
- **WS-D — Frontend/backend contract (new):** define typed legend/plot state snapshots and interaction intents; keep host-agnostic transport semantics.
- **WS-E — Governance/quality gates:** enforce import boundaries, naming policy, type/lint/test gates, and architecture policy docs.

### 5) Migration posture for a private project

Because this is private and backward compatibility is not required:

- Prefer **direct cutovers** to new module paths over long-lived compatibility shims.
- Allow **breaking internal API cleanup** where it materially improves architecture clarity.
- Use short transitional aliases only when needed to keep implementation phases tractable.
- Treat old module names and re-export shims as removable debt, not long-term support obligations.

## Open questions

1. **Cutover strategy:** big-bang branch merge vs phased merges with temporary adapters.
2. **How should we define the frontend/backend contract artifact?**
   - **Option A (lighter):** Python `@dataclass` + type hints + docstrings only.
   - **Option B (stricter):** A formal schema (for example JSON Schema or equivalent) in addition to Python types.
   - **Decision needed:** choose whether we optimize for speed/simplicity (A) or stronger cross-runtime validation and tooling (B).
ANSWER: OPTION A
3. **What should we standardize first: legend-only or whole-figure UI protocol?**
   - **Option A (narrow first):** define protocol v1 only for legend interactions/state.
   - **Option B (broad first):** define one unified protocol for legend + plot/view/parameter UI interactions.
   - **Decision needed:** choose whether we reduce risk with a focused legend slice (A) or invest early in a wider contract (B).
ANSWER: OPTION B

4. **Module naming policy:** whether to complete full snake_case normalization in one pass or incrementally per workstream.
ANSWER: INCREMENTALLY

## Challenges and mitigations

- **Challenge:** Refactor breadth can destabilize active feature work.
  - **Mitigation:** phased migration with strict test gates and incremental PR slicing.

- **Challenge:** Large module extraction risks semantic drift in plotting behavior.
  - **Mitigation:** lock behavior with characterization tests before extractions and require parity checks during moves.

- **Challenge:** Frontend/backend split can over-engineer early if too abstract.
  - **Mitigation:** start with concrete legend contract (state + intents) and grow protocol only when new UI surfaces require it.

- **Challenge:** Packaging moves can cause noisy merge conflicts.
  - **Mitigation:** sequence path moves after decomposition and prefer clear one-time path migrations.

## TODO

- [ ] Confirm this project as umbrella successor/coordinator for architecture modernization efforts.
- [ ] Link and map project-022, project-023, project-033, and project-034 outputs into this program charter.
- [ ] Define architecture invariants (layer boundaries, import rules, naming conventions, and ownership boundaries).
- [ ] Define minimal typed frontend/backend legend protocol v1 (state snapshot + interaction intents).
- [ ] Decide and document migration mode (big-bang vs phased cutover) for this private repo.
- [ ] Produce the implementation blueprint (`plan.md`) in phased, reversible milestones.

## Exit criteria

- [ ] Monolithic coordination is decomposed: `Figure.py` reduced to coordinator-focused responsibilities with extracted subsystems.
- [ ] Package topology reflects layered architecture with clear subpackages and enforced boundaries.
- [ ] Typed frontend/backend legend contract exists and is used by legend interactions.
- [ ] Legacy re-export/shim modules are removed or minimized to explicitly temporary adapters.
- [ ] Duplication targets (symbol resolution/constants/normalization helpers) are consolidated.
- [ ] Test/type/lint gates protect the new architecture and prevent regression to cross-layer coupling.
- [ ] Project-022 and project-023 are either completed under this umbrella or explicitly superseded with completion notes.

---

## Coordination update (2026-02-20)

For the ownership-matrix, deduplication, and boundary-contract execution slice of WS-A/WS-C, see project-037 (`docs/projects/project-037-ownership-boundaries-and-dedup/summary.md`). Project-036 remains concern analysis; project-037 tracks concrete execution artifacts.
