# Issue: Published showcase notebook still contains author-only review content and has drifted from its own tracker/tests

## Summary
`examples/MathLive_identifier_system_showcase.ipynb` is still carrying author-facing review material instead of a finished teaching narrative. The current notebook contains a pure-comment review cell and multiple `# BUG` / `#BUG` comments in executable cells.

That is not just cosmetic drift. It now contradicts both the repo's regression test and the closed tracker entry that says this cleanup already happened.

## Evidence
- The notebook currently has **11 markdown cells and 11 code cells**. One of the code cells (cell 8) is comment-only review text rather than executable tutorial content.
- Notebook cell 8 is a pure-comment critique of the notebook structure, for example "This showcase note book is BAD" and "Completely revisit your approach from here down." That is author-review content, not user-facing tutorial material.
- Notebook cell 13 still contains `# BUG` / `#BUG` comments about splitting manual examples from integration checks.
- Notebook cell 16 still contains a `#BUG` comment about abolishing custom LaTeX rendering helpers.
- `tests/semantic_math/test_showcase_notebooks.py:47-50` explicitly asserts that showcase notebooks must not contain `#BUG` or `# BUG` markers.
- `docs/issues/_closed/issue-037-mathlive-showcase-is-not-markdown-first-and-still-contains-author-only-bug-cells.md:7-25` claims the notebook was already cleaned up, that the markers were removed, and that the notebook reads like a finished tutorial.
- Reproducing `PYTHONPATH=src pytest tests/semantic_math/test_showcase_notebooks.py -q` fails on the shipped notebook because those markers are still present.

## TODO / Approach to solution
- Remove or convert author-review comments into real markdown explanations aimed at readers.
- Convert comment-only code cells into markdown cells.
- Reopen or replace the stale closed tracker entry so the issue tracker matches the repository state.
- Strengthen notebook-quality tests so they also catch comment-only review cells, not only `#BUG` markers.

## Exit criteria
- The published notebook contains no author-only review comments in code cells.
- Markdown cells clearly outnumber code cells because tutorial narrative is not being stored in executable cells.
- The closed/open issue tracker state matches the actual notebook contents.
- `tests/semantic_math/test_showcase_notebooks.py` passes and also protects against regression back to comment-only review cells.
