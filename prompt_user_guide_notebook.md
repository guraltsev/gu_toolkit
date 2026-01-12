# Prompt: Create a Comprehensive **User Guide Notebook** (manual execution)

You are an expert Python engineer and technical writer. You are writing a **single Jupyter notebook** that serves as the **primary, example-driven user guide** for an existing Python package.

This notebook is a **teaching + reference artifact** aimed at:
- a professional researcher in mathematics,
- students who may use the tool in coursework,
- collaborators who need a quick but accurate overview.

The notebook must be **self-explanatory**, **text-first**, and organized so that readers can skim headings to find what they need.

---

## Inputs you have access to

- The installed / editable Python package.
- Its source tree (to understand design and intended usage).
- Its docstrings / README (if present).

No network access.

---

## Deliverable

Create **one notebook file**:

- `UserGuide_<PACKAGE_NAME>.ipynb`

---

## Non-negotiable quality constraints (from the Coding Style Guide)

- Prefer standard library + core scientific stack; avoid niche dependencies unless required.
- Examples should be deterministic and reproducible.
- If the package has notebook/UI components:
  - separate “construct UI object” from “display side effect” when applicable,
  - ensure UI state is reconstructible from underlying state,
  - avoid leaking callbacks/handlers; show cleanup patterns.

(These constraints are mandated by the provided CodingStyle document.)

---

## Acceptance criteria

Your notebook must:

1. **Cover the full public API surface** at a user level:
   - Identify public entrypoints (`__all__`, documented APIs, public members of public classes).
   - Ensure every major feature is explained and demonstrated at least once.
2. Provide a **Quickstart** that works in <5 minutes.
3. Provide **common workflows** with clean, minimal code.
4. Provide **nice applications**:
   - Choose 2–4 realistic, mathematically-flavored applications appropriate for a researcher/educator
     (e.g., numerical experiments, symbolic-to-numeric workflows, plotting/interactive exploration, small reproducible “mini-projects”).
   - Applications must still be comprehensible to advanced undergraduates / beginning grad students.
5. End with an **Advanced Guide**:
   - configuration options
   - extension points
   - performance and scaling notes (pragmatic, no premature optimization)
   - troubleshooting and diagnostics
   - how to contribute (where to add features/tests)

---

## Notebook structure (required)

Use this outline, customizing headings to the package domain:

1. `# <PACKAGE_NAME>: User Guide`

2. `## What this package is for (and what it is not)`
   - Purpose and non-goals in plain language.
   - A short “mental model” of how the package is organized (core vs adapters vs UI if applicable).

3. `## Installation & Requirements`
   - Minimal requirements and optional extras.
   - Mention optional dependencies and what features they unlock.

4. `## Quickstart (5 minutes)`
   - The smallest working example that demonstrates the package’s “center of gravity”.
   - Include:
     - imports
     - minimal configuration
     - one meaningful output (value, object, plot, file, etc.)
   - Explain *why* each line exists.

5. `## Core Concepts`
   - 2–5 short sections explaining the key objects and workflow.
   - For each concept:
     - a paragraph of explanation
     - one short example (preferably 10–25 lines)
     - a “Gotchas” bullet list (only real ones; no filler)

6. `## Common Tasks / Recipes`
   - Several “recipe cards”:
     - *Task name* → *minimal code* → *what to look for / how to verify it worked*
   - Make recipes searchable via headings.

7. `## Applications (2–4 mini-projects)`
   Each application must include:
   - a motivating question
   - a step-by-step workflow
   - one or more visualizations or concrete outputs (as applicable)
   - a short summary of what was learned / how to adapt it

   Requirements:
   - deterministic outputs
   - no giant datasets
   - avoid unnecessary dependencies

8. `## Advanced Guide`
   Include subsections as applicable:
   - **Customization & configuration**
   - **Extending the package**
     - show extension points (plugins, subclassing, callbacks, registries, etc.)
     - state invariants that extensions must preserve
   - **Performance & scaling**
     - how to profile at a high level
     - typical bottlenecks and safe optimizations
   - **Interoperability**
     - how to integrate with numpy/scipy/pandas/plotting, etc.
   - **Troubleshooting**
     - common errors and how to fix them
     - how to produce a minimal reproducible example

9. `## API Reference (lightweight)`
   - A curated, user-facing index of the most important functions/classes.
   - Do not paste full docstrings; summarize with links/anchors inside the notebook.
   - Point to docstrings for authoritative parameter details.

10. `## Next Steps`
   - Suggested reading order (if the package has deeper concepts).
   - Where tests live and how users can validate their setup (mention the TestSuite notebook).

---

## Writing and example style rules

- Assume the reader is smart but busy.
- Prefer:
  - small code blocks
  - explicit variable names
  - “verify” steps (e.g., assert shapes, print summaries, check invariants)
- Avoid:
  - large walls of prose
  - abstract marketing language
  - excessive screenshots or manual “click this” instructions
- If showing plots:
  - keep them simple and support them with programmatic checks where possible (e.g., assert arrays, shapes, key values).

---

## Optional dependency behavior (must be documented)

If the package has optional extras:
- Include a table:
  - optional package name
  - install hint (generic)
  - which feature becomes available
- Demonstrate graceful failure:
  - try to use the feature without the dependency (if feasible in the environment),
  - show the error message users should expect,
  - show how to resolve it.

---

## Output format

Return **only** the completed notebook content (as an `.ipynb`), ready to save.
If your interface only allows text output, emit:
1) a Markdown outline with cell-by-cell content, and
2) the corresponding JSON `.ipynb` structure.

