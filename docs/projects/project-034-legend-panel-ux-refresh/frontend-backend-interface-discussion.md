# Project 034: Frontend/Backend Interface Discussion

## Context

Project 034 currently leans toward "Python-first" interaction handling for legend UX (row state, visibility, CSS classing, and phase-gated hover behavior). That choice is intentional for maintainability and CI testability, but it can conflict with the long-term goal of a rich UI that runs both in notebooks and in a standalone Pyodide applet if every micro-interaction is routed through Python.

The key architectural question is not "Python or frontend"; it is **where to draw a stable boundary** so each side can evolve without coupling churn.

## What the current docs already get right

The current plan already introduces several strong foundations:

- A reusable row component boundary (`LegendRowWidget`) instead of manager sprawl.
- A resolved style-readback contract (`Plot.effective_style()`) instead of ad-hoc trace inspection.
- Semantic class-based state (`.legend-row`, `.is-hidden`, etc.) instead of inline styles.
- Phase-gating risky/high-coupling behaviors.

These are exactly the ingredients needed to evolve from "Python-first implementation" to a sustainable frontend/backend contract.

## Core recommendation

Adopt a **typed UI state and event protocol** between backend (Python) and frontend (widget/DOM runtime), and use it consistently across notebook and applet hosts.

In practical terms:

1. Backend owns durable domain state and business rules.
2. Frontend owns ephemeral interaction rendering and low-latency affordances.
3. Both communicate using explicit messages (state snapshots + events), not implicit trait poking or DOM assumptions.

## Why forcing everything through Python becomes limiting

Routing every UI interaction through Python can degrade the standalone direction in three ways:

1. **Latency sensitivity**
   - Hover, drag, and fine-grained pointer interactions require low-latency local handling.
   - Round-tripping these through Python (especially notebook kernels) creates jitter and race conditions.

2. **Host/runtime divergence**
   - Notebook widget stacks and Pyodide-hosted applets differ in lifecycle and transport details.
   - If interaction logic is expressed only as Python widget callbacks, portability suffers.

3. **Testing surface mismatch**
   - Pure Python tests are great for durable state transitions.
   - Rich interaction behavior still needs frontend-level contract tests to avoid regressions.

## A sustainable split of responsibilities

### Backend (Python)

Own and expose:

- Canonical plot/legend state (visibility, label text, resolved style metadata).
- Policy decisions (which interactions are permitted, feature flags, editability rules).
- Coarse events and intents (toggle visibility, apply style, reorder series).
- Persistence/serialization and notebook-friendly APIs.

### Frontend (UI runtime)

Own and expose:

- Pointer/keyboard interaction plumbing.
- Hover/press/focus visual states and micro-animations.
- Responsive layout and truncation behavior.
- Local optimistic UI response where safe.

### Contract between them

Use explicit message types, for example:

- `LegendStateSnapshot`
- `LegendRowUpdated`
- `LegendInteractionIntent` (e.g., `toggle_visibility`, `request_label_edit`)
- `LegendTransientInteraction` (e.g., `hover_start`, `hover_end`, optional)

This gives you a transport-agnostic protocol that can run over ipywidgets comms now and a different bridge in Pyodide later.

## Applying this to Project 034

For this project specifically:

1. Keep the Python-first baseline for durable actions (toggle visibility, disabled state, style synchronization).
2. Treat hover width amplification as explicitly optional and likely frontend-owned if/when added.
3. Introduce a small protocol document (or dataclasses + schema comments) for legend state/events now, even if initially implemented in Python only.
4. Ensure `Plot.effective_style()` is host-agnostic and does not leak transport details.
5. Add tests at two levels:
   - Python tests for state transitions and contracts.
   - Frontend/DOM tests (or minimal integration checks) for interaction fidelity.

## Decision framework for future features

When adding a behavior, ask:

- Is this durable domain state? -> backend.
- Is this ephemeral interaction feedback? -> frontend.
- Does this need sub-100ms responsiveness? -> frontend-first.
- Does this affect persisted model semantics? -> backend-first.

If both are involved, implement as:

- frontend optimistic interaction,
- backend authoritative reconciliation via contract messages.

## Bottom line

Your concern is valid: a strict "all GUI through Python" approach will eventually fight the Pyodide + rich UI trajectory.

The path forward is not a hard pivot away from Python; it is a **clear, versioned frontend/backend interface** where Python remains authoritative for model semantics, and frontend runtimes handle transient interaction detail. Project 034 can be the first place this boundary is made explicit.
