# Prompt: Create a Comprehensive **Notebook-Based Test Suite** (manual execution)

You are an expert Python engineer and test author. You are writing a **single Jupyter notebook** that serves as a **comprehensive verification suite** for an existing Python package.

This notebook is **not** a demo and **not** a tutorial: it is a **manual-run test suite** intended to validate *all* functionality of the package in a deterministic, reproducible way.

---

## Inputs you have access to

- The installed / editable Python package under test (PUT).
- Its source tree (you can read it, but tests should primarily target *public behavior*).
- Its docstrings / README (if present).

You must not rely on network access.

---

## Non-negotiable constraints from the Coding Style Guide

Follow these test-notebook rules:

- The notebook **MUST** use clear Markdown headings describing each tested behavior.
- The notebook **MUST** include short Markdown context explaining why each behavior matters.
- Code cells that perform tests **MUST** use `assert` statements or programmatic validation.
- Each tested behavior should be validated by one focused test; if a behavior needs multiple cells, group them under a lower-level heading.
- Print a short success message **only if** all assertions pass; otherwise fail loudly.  
  (No “soft failures”, no “looks good” based on eyeballing.)
- Tests **MUST** be deterministic (no timing dependence, no network, no uncontrolled randomness).  
  If randomness is inherent, set explicit seeds and assert stable properties.

(These requirements are mandated by the provided CodingStyle document.)

---

## Deliverable

Create **one notebook file**:

- `TestSuite_<PACKAGE_NAME>.ipynb`

The notebook should be runnable top-to-bottom by a human. It should stop at the first failure with a useful error.

---

## Acceptance criteria (what “comprehensive” means)

Your notebook must:

1. **Inventory the public API** and prove coverage:
   - Identify what counts as public:
     - items in `__all__`
     - items documented as public
     - public members of public classes
   - Build a “coverage matrix” (a small table in Markdown) listing:
     - each public symbol / feature area
     - the section heading(s) where it is tested
     - notes on any intentionally untested item (must be justified)
2. **Test each public entrypoint** at least at the “happy path” level, plus key edge cases.
3. Validate:
   - core functionality and correctness
   - parameter validation and error messages (actionable, not vague)
   - state and invariants (especially for mutable objects)
   - adapter boundaries (I/O, plotting backends, optional deps) without leaking UI complexity into core
   - optional dependency behavior (importability without optional deps, and clear error messages at feature boundaries)
4. Include at least:
   - one test that exercises “round-trip” behavior (serialize/deserialize, save/load, export/import, etc.) **if** the package has such features
   - one test for backward-compat / shim behavior **if** the package supports multiple dependency versions
   - one test that ensures cleanup / resource lifecycle for interactive components **if** the package has them (widgets/callbacks/handlers)

---

## Notebook structure (required)

Use **exactly this high-level outline**, adapting headings to the package:

1. `# Test Suite: <PACKAGE_NAME>`

2. `## Environment & Reproducibility`
   - Print Python version and key dependency versions.
   - Set global deterministic configuration (seeds, numpy print options, warnings filters).
   - Define a helper `ok(msg: str) -> None` used to print succinct success messages.

3. `## Public API Inventory`
   - Programmatically:
     - import the top-level package
     - read/print `package.__all__` if present
     - list top-level attributes that appear intended for public use
   - Summarize in a Markdown table: “Public surface to be tested”.

4. `## Core Behavior Tests`
   - One subsection per feature area.
   - Each subsection:
     - short context Markdown
     - small setup cell
     - one or more assertion cells
   - Favor testing through the public API.

5. `## Error Handling & Diagnostics`
   - For representative failures:
     - assert the **exception type**
     - assert **actionable** message content (brief “what/why/next”)
   - Include at least one test for each major “user mistake” category in the package.

6. `## State, Mutability, and Invariants`
   - For each stateful class/object:
     - test default invariants
     - test state transitions
     - test invariants after transitions
     - if global mutable state exists, show how to reset it for tests

7. `## Optional Dependencies & Adapter Boundaries`
   - If the package has optional deps:
     - demonstrate that importing the core package works without them (as much as feasible)
     - verify that feature-specific imports raise clear errors that name the missing package and the feature
   - If the package has plotting/UI adapters:
     - test that “construct UI” can be separated from “display side effect” if applicable
     - avoid relying on manual inspection of figures; assert properties programmatically

8. `## Interactive / Notebook-First Components (if applicable)`
   - Callbacks:
     - ensure they are small / delegated (test via behavior, not code style)
     - ensure exceptions surface actionable diagnostics
   - Resource lifecycle:
     - create and dispose/cleanup objects; assert handlers aren’t accumulating unexpectedly

9. `## Regression Tests`
   - Add tests for any known bugs that have been fixed previously (if history exists).
   - Each regression test should reference the symptom and the expected invariant.

10. `## Coverage Matrix (Required)`
   - Final Markdown table mapping public symbols → tested section(s).

11. `## “All Tests Passed” Marker`
   - Final cell prints a single “✅ All tests passed.” message.

---

## Implementation rules for the notebook

- Keep cells short; prefer multiple cells over one long cell.
- No hidden state:
  - Avoid depending on variable values set far above without re-stating context.
  - If a section depends on earlier setup, explicitly reference it in Markdown.
- Do not skip tests behind interactive widgets, manual clicks, or “look at the output”.
  - If interactivity is unavoidable, still assert observable state transitions programmatically.
- No network calls.
- Avoid timing-based assertions (no “should finish within X seconds”).
- Use only widely established dependencies (standard library + core scientific stack) unless the package requires others.
- If tests require temporary files/directories, use `tempfile.TemporaryDirectory()` and clean up.

---

## What you should NOT do

- Do not create a separate `tests/` folder or a pytest suite: this deliverable is the notebook only.
- Do not write a tutorial or extended narrative beyond what’s needed to justify tests.
- Do not rely on eyeballing plots/tables to “verify” correctness.

---

## Output format

Return **only** the completed notebook content (as an `.ipynb`), ready to save.
If your interface only allows text output, emit:
1) a Markdown outline with cell-by-cell content, and
2) the corresponding JSON `.ipynb` structure.

