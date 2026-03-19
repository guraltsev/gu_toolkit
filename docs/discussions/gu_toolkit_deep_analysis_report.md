# Deep Analysis of gu_toolkit

**Repository reviewed from archive:** `gu_toolkit.zip`  
**Date:** March 19, 2026

## Executive summary

`gu_toolkit` is in a strong intermediate architecture state. It has a real ownership model, meaningful subsystem extraction, thoughtful notebook ergonomics, and unusually rich internal documentation for a toolkit of this size. The codebase is not sloppy; it is clearly being actively designed.

The main extensibility problem is not “lack of separation of concerns.” It is almost the opposite: concern-level separation is mostly good, but common workflows still cross too many modules while the central coordinator remains too heavy. That makes the system easy to justify module-by-module, but harder to follow end-to-end when adding or modifying behavior.

My overall judgment is: keep most of the current module split, do not collapse the Figure ecosystem back into fewer large files, but introduce a missing workflow/orchestration layer, shrink the densest paths in `Figure.py`, remove compatibility debt aggressively, and tighten the public import/testing seams. In other words, the repo needs less fragmentation of workflows, not less separation of concerns.

## Methodology and repo snapshot

This assessment combined static architecture review, file-structure and dependency analysis, hotspot measurement, documentation review, and a test-suite run. I reviewed the core source tree under `src/gu_toolkit`, the developer guide and project summaries under `docs/`, the package surface in `__init__.py` and `Notebook.py`, and the current regression test state via `pytest`.

| Metric                                      | Value                                                                 |
|---------------------------------------------|-----------------------------------------------------------------------|
| Source modules (.py) under `src/gu_toolkit` | 34                                                                    |
| Source lines of code                        | 12,861                                                                |
| Figure ecosystem modules reviewed           | 16                                                                    |
| Figure ecosystem LOC                        | 6,736                                                                 |
| Largest source file                         | `Figure.py` (1,829 lines)                                             |
| Tests                                       | 40 Python test files + 6 notebooks                                    |
| Pytest result                               | 199 passed, 7 failed, 1 skipped, 1,449 warnings                       |
| Docs                                        | 63 Markdown files + 6 notebooks                                       |
| Examples                                    | 16 notebooks                                                          |
| Notable secondary hotspots                  | `numpify.py` (1,162), `PlotlyPane.py` (1,035), `figure_plot.py` (994) |

I did not treat notebook/browser behavior as fully validated because this review was based on repository analysis and automated tests rather than manual interactive notebook sessions.

## Current architecture: what is good already

One of the best traits of this repository is that the intended architecture is explicitly documented and mostly reflected in the code. The development guide describes `Figure` as coordinator, `View` as the public per-view runtime object, `FigureLayout` as widget composition owner, `ViewManager` as registry/policy owner, `ParameterManager` / `InfoPanelManager` / `LegendPanelManager` as dedicated subsystem owners, and snapshots/codegen as the reproducibility layer. That is a mature mental model, not an after-the-fact justification.

| Owner / layer               | Current responsibility                              | Assessment                          |
|-----------------------------|-----------------------------------------------------|-------------------------------------|
| Figure                      | Public facade and orchestration hub                 | Correct role, but still too broad   |
| FigureLayout                | Widget tree, geometry intent, persistent view hosts | Good separation                     |
| View / FigureViews          | Public per-view state and facade                    | Conceptually strong                 |
| ViewManager                 | Registry, active view id, stale tracking            | Good boundary, but API drift exists |
| ParameterManager            | Parameter lifecycle and controls                    | Clear owner                         |
| InfoPanelManager            | Info cards and raw outputs                          | Clear owner                         |
| LegendPanelManager          | Toolkit legend sidebar                              | Clear owner                         |
| Plot / figure_plot          | Per-curve sampling and trace updates                | Appropriate owner                   |
| figure_plot_normalization   | Stateless plot-input normalization                  | High-value extraction               |
| figure_plot_style           | Metadata-driven style contract                      | Excellent extraction                |
| figure_context / figure_api | Current-figure routing and notebook helpers         | Good ergonomics                     |
| FigureSnapshot / codegen    | Persistence and reproducibility                     | Valuable subsystem                  |

The problem is that `Figure` remains the hub for too many workflow steps. In the current code, `Figure` imports 21 internal toolkit modules. That is not automatically wrong for a coordinator, but it confirms that most user-facing flows still route through one dominant class.

## Major strengths

1. The architecture has explicit intent. The module docstring in `src/gu_toolkit/Figure.py` and the development guide in `docs/develop_guide/develop_guide.md` are unusually good. They define ownership boundaries instead of leaving future contributors to reverse-engineer them.
2. The subsystem extractions are mostly real, not cosmetic. `figure_plot_normalization.py`, `figure_plot_style.py`, `figure_context.py`, `figure_view_manager.py`, `figure_layout.py`, `figure_parameters.py`, `figure_info.py`, and `figure_legend.py` each own a recognizable concern.
3. The style-contract design is especially strong. `figure_plot_style.py` centralizes accepted plot-style keywords, alias resolution, validation, and discoverability from one metadata source. That is a clean pattern worth reusing elsewhere.
4. Notebook ergonomics are thoughtfully prioritized. The current-figure stack, module-level helper API, and notebook convenience namespace reflect the product’s actual usage model rather than a purely library-centric design.
5. The repository has strong process signals: `pyproject` tooling, CI workflow, issue/project documentation, examples, notebooks, and a meaningful regression test suite. Many codebases with similar complexity have none of this.
6. The logging and diagnostics direction is promising. `layout_logging.py`, `PlotlyPane` instrumentation, and the generic `QueuedDebouncer` are signs that the maintainers are trying to make UI behavior observable instead of magical.
7. Documentation discipline is genuinely a strength, even when it increases LOC. `Agents.md` explicitly requires comprehensive docstrings and examples, and the code largely follows that rule.

## Main weaknesses and sources of extension friction

### 1. The coordinator is still too heavy

`Figure.py` is still the dominant hotspot at 1,829 lines. The two biggest concentrated pain points are `Figure.__init__` (191 lines, ~28 branch points) and `Figure.plot` (280 lines, ~35 branch points). The constructor still mixes deprecated-argument handling, default coercion, logging configuration, layout and manager wiring, debouncer setup, initial view creation, and sidebar synchronization (roughly lines 217–407). The `plot()` method still mixes input normalization, range resolution, samples-alias handling, style validation, parameter autodetection, sidebar updates, create-vs-update routing, color assignment, and legend notifications (roughly lines 1030–1309).

This is the single biggest reason the logic feels hard to follow. The code is not badly factored in the small; it is overburdened at the orchestration level.

### 2. Workflow traceability is weaker than concern traceability

The repo is good at answering “which module owns this concern?” but weaker at answering “what happens when the user does X?” For example, a single `fig.plot(...)` call flows through `Figure.plot` -> `figure_plot_normalization.normalize_plot_inputs` -> `figure_plot_style.validate_style_kwargs` -> `ParameterManager` -> `FigureLayout` sidebar sync -> `Plot` or `Plot.update` -> `LegendPanelManager` -> possible reflow. A view switch similarly crosses `Figure`, `ViewManager`, `View`, `FigureLayout`, `InfoPanelManager`, `LegendPanelManager`, and the pane reflow path.

That is why the code can simultaneously have good separation of concerns and still feel fragmented during feature work.

### 3. The change surface for cross-cutting features is too wide

The development guide itself makes this visible. Adding a new style option is documented as touching at least five places: `figure_plot_style.py`, `Figure.plot(...)`, `figure_api.plot(...)`, `Plot.update(...)`, and code generation when round-tripping matters. Adding a new per-view property is documented as touching at least six places: `View`, `ViewManager`, `Figure`, snapshots, `Figure.snapshot()`, and `codegen.figure_to_code()`. That is disciplined, but it is also a real extension tax.

This kind of touch count is acceptable only if the workflow is extremely obvious. Right now, it is documented, but still more diffuse than it should be.

### 4. Compatibility layers and alias support add noise to the hot paths

A lot of branchiness comes from supporting old and new spellings or transitional APIs: `samples` vs `sampling_points`, `x_range` vs `default_x_range`, `y_range` vs `default_y_range`, `width` vs `thickness`, `alpha` vs `opacity`, `show` vs `display`, deprecated `Figure.view(...)`, deprecated `Figure.active_view_id`, and compatibility wrappers in `figure_layout.py` (`set_plot_widget`, `set_view_plot_widget`, `set_view_tabs`, `trigger_reflow_for_view`, `observe_tab_selection`).

These are reasonable during migration windows, but once enough of them accumulate they become an architecture tax. They make `Figure` and `FigureLayout` look more complicated than the durable design really is.

### 5. The public import surface is powerful but overly broad

The package-level API is designed for convenience, but it is also quite fragile. `src/gu_toolkit/__init__.py` re-exports a large surface, performs a wildcard import from `Notebook.py`, and then explicitly rebinds `plot` to avoid SymPy shadowing. `Notebook.py` itself performs `from sympy import *` and injects a large prelude of symbols and helpers into the namespace. That is great for notebook convenience, but it increases the risk of name collisions, authority ambiguity, and maintenance drift.

This is not merely theoretical: the issue tracker already records import-surface concerns around top-level `plot` shadowing and codegen/API contract mismatch.

### 6. Test seams are brittle in some important places

Several of the current test failures are not random defects; they expose extension seams that are too rigid. `Figure` uses `__slots__`, which makes instance monkeypatching of methods like `_request_active_view_reflow` impossible in tests. `figure_layout.attach_view_widget` assumes an `ipywidgets.Widget` child, which makes lightweight pane/test doubles awkward. Refactors around relayout and `ViewManager` have also drifted away from older architecture tests.

These are signs that the internal contracts are not yet stable enough for painless evolution.

### 7. Warning debt is significant

The test run produced 1,449 warnings, dominated by traitlets `DeprecationWarning` messages about unsupported `Layout` kwargs such as `border_radius`, `box_sizing`, `gap`, `position`, `background_color`, `opacity`, `box_shadow`, and `z_index`. Today that is noisy but survivable. In a future traitlets version, it may become an outright break. This is maintainability debt in the UI layer, not just cosmetic warning spam.

### 8. Some docs and architecture signals have drifted

The codebase is well documented, but not perfectly synchronized. `docs/README.md` still references `Discussions/` and `guides/` even though the actual tree uses `develop_guide/` and `issues/_closed/`. `docs/issues/project-037-css-and-plot-layout-logging.md` starts with the header “Project 036.” Closed project summaries report earlier `Figure.py` line counts that no longer match the current file. These mismatches do not make the architecture bad, but they slightly reduce trust when contributors are using the docs as navigation tools.

## Is the Figure subsystem split into too many files?

Mostly no. The current split is more justified than it first appears. There are real and useful boundaries between layout, view state, view selection policy, parameter controls, info cards, legend UI, plot rendering, plot normalization, plot style metadata, current-figure context, snapshots, codegen, and layout logging/debouncing. Re-merging those back into one or two files would make the code easier to scan briefly but harder to maintain safely.

The actual problem is that the code is missing a workflow-focused middle layer. Today it effectively has:

```text
Public facade:    Figure, figure_api, __init__, Notebook
Concern owners:   layout / views / params / info / legend / plot / snapshots
Missing middle:   small workflow helpers that explain and own the busiest call sequences
```

Because that middle layer is weak, contributors experience the current module split as fragmentation. The answer is not “fewer files at all costs”; it is “better workflow ownership and fewer compatibility hops.”

## What should stay vs what should change

| Category | Recommendation                                                                  | Rationale                                                                                         |
|----------|---------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| Keep     | `figure_plot_normalization.py` and `figure_plot_style.py`                       | These are high-value extractions that centralize contracts cleanly.                               |
| Keep     | `FigureLayout` / `ParameterManager` / `InfoPanelManager` / `LegendPanelManager` | These are real subsystem owners, not arbitrary file splits.                                       |
| Keep     | `figure_context.py` and `figure_api.py`                                         | The current-figure routing model fits notebook usage well.                                        |
| Change   | `Figure.plot()`                                                                 | Extract dense upsert/orchestration helper(s); keep `Figure` as short orchestration script.        |
| Change   | `Figure.__init__` and view runtime creation                                     | Split bootstrap/wiring from public constructor and consider consolidating runtime ownership.      |
| Change   | Compatibility wrappers and deprecated aliases                                   | They currently add too much noise relative to their value.                                        |
| Change   | `__init__.py` / `Notebook.py` import strategy                                   | Keep convenience, but separate stable package API from broad notebook prelude more clearly.       |
| Avoid    | A broad merge of `figure_*` files back into `Figure.py`                         | That would reduce file count while making real ownership worse.                                   |
| Avoid    | Premature large abstractions like `RenderEngine` or `FigureUIAdapter`           | The repo’s own architecture notes are right: these would add indirection before they add clarity. |

## Recommended improvements

### Priority 1: stabilize the current architecture before inventing more of it

- Fix the seven failing tests and treat them as architecture signals, not just red CI. The failures point to contract drift in relayout naming, codegen imports, `ViewManager` behavior, and the expected reduction of `Figure.py`.
- Burn down the traitlets deprecation warnings in the widget layer. Unsupported `Layout` kwargs should be replaced with supported styling mechanisms or wrapped more safely.
- Clean repository hygiene: remove `.pytest_cache`, `__pycache__`, and `.ipynb_checkpoints` from the archive/repo; fix `docs/README.md` path drift and project numbering mismatches.

### Priority 2: add the missing workflow layer

This is the most important architectural recommendation. Add a thin workflow-oriented layer that makes the busiest sequences explicit without creating big new frameworks.

- Extract the create-vs-update path from `Figure.plot` into a helper or small workflow module. This should own ID generation, new-vs-existing routing, and the construction of update/create payloads. `Figure.plot` should become a short orchestration script: normalize -> validate -> ensure parameters -> upsert -> sync legend/sidebar -> return.
- Split constructor bootstrap from public `Figure.__init__`. For example, move manager/layout/debouncer wiring and initial main-view setup into one internal bootstrap helper. That would reduce the feeling that the constructor is also an integration test.
- Consider consolidating view runtime creation with view management. Today view selection policy lives in `ViewManager`, while `Figure._create_view` still owns figure widget and pane runtime creation. Those responsibilities are adjacent enough that contributors have to reason about both together.

The key idea is to reduce cross-file jumping for one common workflow without undoing the subsystem ownership boundaries.

### Priority 3: enforce a stricter deprecation budget

- Set an explicit rule for how long transitional aliases and compatibility wrappers stay alive.
- Remove layout compatibility wrappers after the migration window if they are no longer needed.
- Trim deprecated Figure accessors and constructor aliases once downstream docs/examples are updated.

The current design already has the cleaner target shape. What is missing is the courage to retire the scaffolding fast enough.

### Priority 4: improve discoverability for contributors

- Add a short architecture index at the repo root or docs root: “If you are changing X, start in Y.” The existing development guide is good, but it is longer and more conceptual than a contributor navigation card.
- Add workflow maps for four core paths: plot add/update, parameter change -> render, view activation, and snapshot/codegen round-trip.
- Maintain a method ownership matrix for `Figure` so reviewers can tell which methods are facade-only, which are orchestration-only, and which still contain owner-level logic.

### Priority 5: separate stable API from notebook prelude more clearly

- Keep package-level convenience, but stop treating the notebook prelude as the same thing as the stable API surface.
- Consider making the broad prelude live behind an explicit import path such as `gu_toolkit.Notebook` or `gu_toolkit.notebook` while keeping `gu_toolkit` itself more deliberate.
- Add import-surface contract tests so names like `plot`, `info`, and `parameter` cannot silently drift or be shadowed.

This would reduce ambiguity without sacrificing the notebook-first user experience.

### Priority 6: make extension and testing seams more flexible

- Either relax `__slots__` where it blocks legitimate extension/test seams, or provide explicit hook/factory injection points that make monkeypatch-style testing unnecessary.
- Introduce lightweight factory seams or protocols for pane/widget runtime creation so tests and future alternate transports are not forced through exact concrete widget objects.
- Strengthen contract tests around codegen, import surface, relayout behavior, and view lifecycle transitions.

### Priority 7: keep future abstractions trigger-based

The repo’s own project analysis is right to resist large speculative layers. A `RenderEngine` is only justified if render orchestration grows materially beyond its current simple loop. A `FigureUIAdapter` is only justified if there is a real transport boundary beyond direct widget managers. The correct near-term move is not more nouns; it is better ownership of the dense workflows that already exist.

## Recommended target shape

```text
Layer 1: Public facades
  - Figure
  - figure_api
  - package __init__
  - Notebook prelude

Layer 2: Workflow helpers (missing / underdeveloped today)
  - plot upsert workflow
  - figure bootstrap / runtime assembly
  - possibly view activation / reflow workflow if it grows further

Layer 3: Concern owners
  - FigureLayout
  - View / ViewManager
  - ParameterManager
  - InfoPanelManager
  - LegendPanelManager
  - Plot
  - normalization / style metadata
  - snapshots / codegen
  - logging / debouncing
```

That middle layer is the missing piece that would let the current decomposition feel coherent rather than merely well-intentioned.

## Overall conclusion

This toolkit is generally in good shape, and the maintainers’ instincts about separation of concerns are mostly correct. The friction you are feeling is real, but it comes from an architecture that is mid-transition rather than fundamentally misguided. The repo already knows what its subsystems are; it now needs to make the cross-subsystem workflows smaller, clearer, and less compatibility-heavy.

The practical headline is: keep the concern-based module split, add a workflow layer, shrink `Figure`’s dense methods, stabilize contracts and imports, and clean up warning/deprecation debt. That would preserve the current strengths while removing most of the extension friction.

## Appendix A: structural hotspots

| Module | LOC | Why it matters |
|---|---:|---|
| `Figure.py` | 1,829 | Main orchestration hotspot; cognitive center of the toolkit. |
| `numpify.py` | 1,162 | Large symbolic-to-numeric bridge; another important complexity center. |
| `PlotlyPane.py` | 1,035 | Notebook/browser integration layer; likely source of UI fragility and warning debt. |
| `figure_plot.py` | 994 | Per-curve lifecycle and rendering logic; substantial but appropriately isolated. |
| `Slider.py` | 833 | Parameter control complexity; supports advanced UI behavior. |
| `figure_layout.py` | 635 | Widget tree owner, but also carries compatibility wrappers. |
| `figure_parameters.py` | 615 | Parameter lifecycle owner; central to interactivity. |
| `ParamRef.py` | 602 | Widely reused parameter abstraction. |
| `codegen.py` | 506 | Round-trip reproducibility surface; currently shows contract drift. |
| `figure_info.py` | 471 | Well-scoped manager with dynamic behavior and sidebar integration. |

## Appendix B: densest methods observed

| Method / function | Approx. length | Why it matters |
|---|---:|---|
| `Figure.plot` | 280 lines | Mixes many policies; top candidate for workflow extraction. |
| `Figure.__init__` | 191 lines | Constructor carries too much integration logic. |
| `codegen.figure_to_code` | 146 lines | Important reproducibility path; already showing API drift. |
| `Plot.update` | 125 lines | Dense curve-update logic; acceptable but should be watched. |
| `figure_plot_normalization.normalize_plot_inputs` | 121 lines | Useful extraction, still moderately complex. |
| `ParameterManager.parameter` | 107 lines | Central parameter-creation workflow. |

## Appendix C: current test failures and what they imply

| Failure | Signal | Implication |
|---|---|---|
| `_throttled_relayout` missing in Figure tests | Refactor/compat drift | Relayout naming or compatibility contract changed without synchronized test/API update. |
| Codegen expected `set_title` import, actual code omitted it | Codegen contract drift | Exported code no longer matches test/documented authoring expectations. |
| Monkeypatch of `_request_active_view_reflow` blocked | `__slots__` seam rigidity | Testing/extensibility is harder than it needs to be. |
| `attach_view_widget` rejects plain figure in patched runtime test | Concrete widget coupling | Pane/layout abstraction is too tightly tied to `ipywidgets.Widget` assumptions. |
| ViewManager architecture test expects add/switch/remove API not present | Boundary drift | The intended view-management contract is still moving. |
| Figure.py line-count guard fails (`<1700` expected, `1828` actual) | Coordinator regression | The decomposition effort has partially regressed or at least grown again. |

## Appendix D: documentation and hygiene notes

- `docs/README.md` references `Discussions/` and `guides/`, while the current tree uses `develop_guide/` and `issues/_closed/`.
- `docs/issues/project-037-css-and-plot-layout-logging.md` begins with the header “Project 036.”
- Closed project summaries describe an earlier `Figure.py` line count (1,564) that no longer matches the current file (1,829).
- The archive includes `.pytest_cache`, `__pycache__`, and `.ipynb_checkpoints` directories.
- Module naming is mixed between historical CamelCase files (`Figure.py`, `PlotlyPane.py`, `ParamRef.py`, etc.) and newer snake_case files (`figure_layout.py`, `figure_plot_style.py`, etc.).
- There is no root `README.md`, so onboarding relies on `docs/` plus code-level docstrings.
