# Issue 037: The MathLive showcase notebook is not markdown-first and still contains author-only BUG cells

## Status
Open

## Summary
`examples/MathLive_identifier_system_showcase.ipynb` violates the repository’s own contract for showcase notebooks. It contains author-only `#BUG` review notes, including two code cells that contain nothing except comments, which pushes the notebook past the code-heavy threshold and makes the teaching flow noisier than intended.

This is already caught by the existing semantic-math notebook regression test.

## Evidence
- `docs/guides/semantic-math-refactoring-philosophy.md:96-110` says the showcase notebooks are part of the architecture and “should remain markdown-heavy, minimal in code, and runnable as lightweight integration examples.”
- Notebook inspection shows:
  - 8 markdown cells
  - 9 code cells
  - 2 code cells (cells 5 and 6) that contain only comments
- Cells 5, 6, 7, and 9 include author-facing `#BUG` review notes rather than final user guidance.
- `tests/semantic_math/test_showcase_notebooks.py:39-53` enforces `len(markdown_cells) >= len(code_cells)`.
- Local run during analysis:
  - `pytest tests/semantic_math -q`
  - result: one failure, specifically `test_showcase_notebooks_are_markdown_first_and_cover_their_topic`
  - failure reason: `8 >= 9` is false for `MathLive_identifier_system_showcase.ipynb`
- If the two comment-only code cells were converted to markdown, the notebook would move from `8 markdown / 9 code` to `10 markdown / 7 code`.

## TODO / Approach to solution
- Remove or convert all author-only BUG notes into proper markdown explanations.
- Convert pure-comment code cells to markdown or delete them entirely.
- Keep executable assertions only where they serve the narrative; move review commentary out of code cells.
- Add a notebook-quality check that rejects author-only markers such as `#BUG` in published showcase notebooks.
- Adjust test suite to allow short inline code comments to explain what is going on in the code, but include rule in docs/guides/semantic-math-refactoring-philosophy.md that all more substantial explanation should be in the markdown cells. 

## Exit criteria
- The notebook contains no author-only `#BUG` placeholders.
- Markdown cells are at least as numerous as code cells.
- `pytest tests/semantic_math -q` passes without the markdown-first failure.
- The notebook reads like a finished tutorial rather than a draft with embedded review notes.
