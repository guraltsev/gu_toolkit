# Project 020 — Figure Code Generation

## Rationale
`smart-figure-code-generation` exists to make figure-driven workflows easier to automate and reuse. The branch focuses on making symbolic/numeric plotting behavior programmatically composable, so users can generate or manipulate plotting logic without rewriting notebook glue each time.

Primary goals:
- reduce repetition in figure setup and parameter wiring,
- keep generated plotting behavior deterministic and testable,
- maintain compatibility with existing Figure/SmartFigure context patterns.

## Architecture
At a high level, the implemented design follows the existing toolkit split:

1. **Figure orchestration layer**
   - Manages active figure context (`with figure` patterns), render lifecycles, and plot registration.
2. **Expression/function layer**
   - Handles symbolic/numeric callable conversion and execution semantics.
   - Keeps callable behavior explicit around variable ordering and parameter substitution.
3. **Parameter binding layer**
   - Bridges runtime parameter values into generated/evaluated plotting functions.
   - Aligns behavior between direct dictionary bindings and figure-bound parameter sources.
4. **Validation layer (tests + docs)**
   - Regression tests pin down context binding, function vars semantics, and render-pipeline correctness.
   - Project documentation explains intent, migration details, and open follow-ups.

## Current status
Status: **ready for PR merge into `main`**.

Completed:
- figure-related callable semantics are covered by tests,
- project-020 implementation narrative has been consolidated and archived where appropriate,
- merge documentation for this branch is now colocated with project-020 docs.

## Remaining TODOs
- Add one focused integration test that exercises generated figure code end-to-end across parameter updates.
- Add a short user-facing example in developer docs showing a minimal “generate figure code -> execute -> update parameter” loop.
- Revisit naming consistency between legacy “SmartFigure” terms and current module naming in docs.
