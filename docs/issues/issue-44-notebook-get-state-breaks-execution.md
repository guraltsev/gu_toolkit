# Issue: The notebook calls an unsupported `get_state()` method and fails in the repo's own execution environment

## Summary
The shipped showcase notebook is not fully runnable as committed. Cell 14 calls `identifier_widget.get_state()`, but the public MathLive widget stack in this repo does not provide that method in the fallback widget runtime used by tests.

As a result, the notebook fails its own execution test even though the surrounding cells are otherwise runnable.

## Evidence
- Notebook cell 14 consists of `identifier_widget.get_state()`.
- Running `PYTHONPATH=src pytest tests/semantic_math/test_showcase_notebooks.py -q` fails with `AttributeError: 'IdentifierInput' object has no attribute 'get_state'` when executing that cell.
- A direct runtime check in the repo environment shows `hasattr(IdentifierInput(), "get_state") == False`.
- The widget MRO in this environment is `IdentifierInput -> _SemanticMathInput -> MathLiveField -> _FallbackAnyWidget -> Widget`, so the notebook is running against the fallback anywidget implementation.
- `src/gu_toolkit/_widget_stubs.py` falls back to `_FallbackAnyWidget` when `anywidget` is unavailable; in the current repo environment `ANYWIDGET_IS_FALLBACK == True` because `anywidget` is not installed.
- A repo-wide search under `src/gu_toolkit/` finds no `get_state()` implementation for the MathLive widgets.
- After replacing only that one cell with a harmless placeholder, the notebook executes successfully end to end under `NotebookClient`, which isolates the runtime failure to this unsupported method call.

## TODO / Approach to solution
- Remove the `get_state()` cell from the tutorial, or replace it with a supported inspection path.
- If state inspection is actually useful for readers, expose it through a documented helper or show the relevant public traits explicitly (`value`, `math_json`, `semantic_context`, `transport_valid`, `transport_errors`).
- Keep notebook examples aligned with the repo's supported fallback runtime, not only with a fully provisioned local notebook setup.

## Exit criteria
- The showcase notebook executes successfully in the repo's documented test/runtime environment.
- No cell calls undocumented or environment-specific widget methods.
- Any state inspection shown in the notebook uses supported public API.
